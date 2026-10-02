import json
import os
import sys
import subprocess
import tempfile
import uuid
import time
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Tuple, Optional, List

from review_ledger.events import LedgerEvent, EventLog, WorkflowIntegrityError
from review_ledger.projections import ReviewProjection, FindingProjection
from review_ledger.finding_fsm import validate_finding_transition
from review_ledger.bead_fsm import validate_bead_transition
from review_ledger.lease import (LeaseError, is_lease_active, validate_lease_for_write, format_utc_timestamp)
from review_ledger.renderer import render_review_markdown
from review_ledger.git_adapter import SourceCheckpoint, create_source_checkpoint
from review_ledger.schema import EventActions
from review_ledger.source_identity import canonicalize_scope
from workflow_core.atomic import atomic_write_many
from workflow_core.identity import AcceptanceIdentity, RepositorySnapshot
from review_ledger.cleanup import cleanup_review_ledgers, is_bead_closed

try:
    import fcntl as _fcntl
except ImportError:  # Windows
    _fcntl = None
    import msvcrt as _msvcrt


def _lock_stream(stream) -> None:
    if _fcntl is not None:
        _fcntl.flock(stream.fileno(), _fcntl.LOCK_EX)
        return
    stream.seek(0)
    if not stream.read(1):
        stream.write(bytes((0,)))
        stream.flush()
    while True:
        try:
            stream.seek(0)
            _msvcrt.locking(stream.fileno(), _msvcrt.LK_NBLCK, 1)
            return
        except OSError:
            time.sleep(0.05)


def _unlock_stream(stream) -> None:
    stream.seek(0)
    if _fcntl is not None:
        _fcntl.flock(stream.fileno(), _fcntl.LOCK_UN)
    else:
        _msvcrt.locking(stream.fileno(), _msvcrt.LK_UNLCK, 1)


def dict_raise_on_duplicates(ordered_pairs):
    d = {}
    for k, v in ordered_pairs:
        if k in d:
            raise WorkflowIntegrityError(f"Duplicate JSON key detected: {k}")
        d[k] = v
    return d

def safe_json_loads(s: str) -> Dict[str, Any]:
    try:
        return json.loads(s, object_pairs_hook=dict_raise_on_duplicates)
    except Exception as e:
        raise WorkflowIntegrityError(f"Invalid JSON: {e}")

def get_ledger_paths(bead_id: str, base_dir: Optional[str] = None) -> Tuple[str, str]:
    """Returns the paths to the review.json and review.md files."""
    if not base_dir:
        base_dir = os.getcwd()
    scoped_dir = os.path.join(base_dir, ".planning", "reviews", bead_id)
    legacy_dir = os.path.join(base_dir, ".planning", bead_id)
    if not os.path.exists(os.path.join(scoped_dir, "review.json")) and os.path.exists(os.path.join(legacy_dir, "review.json")):
        dir_path = legacy_dir
    else:
        dir_path = scoped_dir
    return (
        os.path.join(dir_path, "review.json"),
        os.path.join(dir_path, "review.md")
    )

@contextmanager
def ledger_lock(bead_id: str, base_dir: Optional[str] = None):
    json_path, _ = get_ledger_paths(bead_id, base_dir)
    directory = os.path.dirname(json_path)
    os.makedirs(directory, exist_ok=True)
    lock_path = os.path.join(directory, ".review.lock")
    with open(lock_path, "a+b") as stream:
        _lock_stream(stream)
        try:
            yield
        finally:
            _unlock_stream(stream)


# `workflow_id`, `attempt_id`, and `task_id` are optional acceptance-identity
# fields carried on `source-checkpoint-created` and `review-approved` payloads.
# They are absent on every ledger written before identity threading existed, so
# readers must always treat them as optional.


def build_acceptance_identity(
    *,
    task_id: str,
    workflow_id: str,
    attempt_id: str,
    repositories: List[Dict[str, Any]],
) -> AcceptanceIdentity:
    """Assemble the canonical AcceptanceIdentity for a ledger repository list.

    Mirrors ReviewLedgerProvider._acceptance_identity()'s snapshot shape without
    its Git re-verification: the ledger repository dicts are taken as recorded.
    Raises ValueError when the repositories cannot form a complete identity.
    """
    snapshots = []
    for repository in repositories:
        try:
            snapshots.append(
                RepositorySnapshot(
                    repository_id=repository["repository_id"],
                    source_scope_hash=repository["source_scope_hash"],
                    source_tree_hash=repository["source_tree_hash"],
                    checkpoint_sha=repository["checkpoint_sha"],
                    checkpoint_ref=repository["checkpoint_ref"],
                )
            )
        except KeyError as error:
            raise ValueError(
                f"repository is missing source identity field: {error.args[0]}"
            ) from error
    return AcceptanceIdentity(workflow_id, attempt_id, task_id, tuple(snapshots))


def build_acceptance_identity_payload(
    *,
    task_id: str,
    workflow_id: Optional[str],
    attempt_id: Optional[str],
    repositories: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Return the optional identity fields to merge into a mutation payload.

    Returns an empty dict when no identity is supplied, so callers that omit the
    identity emit exactly the payload they emitted before identity threading.
    Raises ValueError when only half an identity is supplied, or when the ledger
    repositories cannot form a complete AcceptanceIdentity, so a malformed
    identity fails before it is appended to the append-only log.
    """
    workflow_id = (workflow_id or "").strip()
    attempt_id = (attempt_id or "").strip()
    if not workflow_id and not attempt_id:
        return {}
    if not workflow_id or not attempt_id:
        raise ValueError("workflow_id and attempt_id must be supplied together")
    build_acceptance_identity(
        task_id=task_id,
        workflow_id=workflow_id,
        attempt_id=attempt_id,
        repositories=repositories,
    )
    return {
        "workflow_id": workflow_id,
        "attempt_id": attempt_id,
        "task_id": task_id,
    }


def resolve_acceptance_identity_payload(
    *,
    log: EventLog,
    task_id: str,
    workflow_id: Optional[str],
    attempt_id: Optional[str],
    repositories: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build an explicit identity or inherit the latest ledger identity.

    Refresh commands commonly omit the identity flags after initialization.
    In that case, retain the workflow and attempt IDs while rebuilding the
    repository snapshots from the newly created checkpoint. A ledger that has
    never carried identity remains a legacy ledger and still emits no fields.
    """
    explicit = build_acceptance_identity_payload(
        task_id=task_id,
        workflow_id=workflow_id,
        attempt_id=attempt_id,
        repositories=repositories,
    )
    if explicit:
        return explicit

    identity_actions = {
        EventActions.LEDGER_CREATED,
        EventActions.SOURCE_CHECKPOINT_CREATED,
        EventActions.REVIEW_APPROVED,
    }
    for event in reversed(log.events):
        if event.action not in identity_actions:
            continue
        inherited_workflow_id = str(event.payload.get("workflow_id") or "").strip()
        inherited_attempt_id = str(event.payload.get("attempt_id") or "").strip()
        if not inherited_workflow_id and not inherited_attempt_id:
            continue
        inherited_task_id = str(event.payload.get("task_id") or task_id).strip()
        if inherited_task_id != task_id:
            raise ValueError(
                "latest acceptance identity task_id does not match the ledger bead_id"
            )
        return build_acceptance_identity_payload(
            task_id=task_id,
            workflow_id=inherited_workflow_id,
            attempt_id=inherited_attempt_id,
            repositories=repositories,
        )
    return {}


def _find_ledger_event(log: EventLog, event_id: str, action: str):
    """Return (event, ledger_revision) for a matching event, else (None, None)."""
    for index, event in enumerate(log.events):
        if event.event_id == event_id:
            if event.action != action:
                return None, None
            return event, index + 1
    return None, None


def _event_acceptance_identity(
    event: LedgerEvent,
    *,
    bead_id: str,
    repositories_key: str,
) -> Optional[AcceptanceIdentity]:
    payload = event.payload
    workflow_id = str(payload.get("workflow_id") or "").strip()
    attempt_id = str(payload.get("attempt_id") or "").strip()
    if not workflow_id or not attempt_id:
        return None
    return build_acceptance_identity(
        task_id=str(payload.get("task_id") or bead_id),
        workflow_id=workflow_id,
        attempt_id=attempt_id,
        repositories=payload.get(repositories_key) or [],
    )


def get_checkpoint_identity_record(
    bead_id: str,
    checkpoint_event_id: str,
    base_dir: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Return the identity-bearing record for one `source-checkpoint-created` event.

    Returns None when the event does not exist, is not a source checkpoint, or
    carries no acceptance identity (every ledger written before identity
    threading). The returned mapping is the checkpoint evidence source shape
    consumed by CompositeEvidenceAuthority._checkpoint(); `repositories` is taken
    straight from `acceptance_identity` so the two are equal by construction.
    """
    log, _projection = load_ledger(bead_id, base_dir)
    event, _revision = _find_ledger_event(
        log, checkpoint_event_id, EventActions.SOURCE_CHECKPOINT_CREATED
    )
    if event is None:
        event, _revision = _find_ledger_event(
            log, checkpoint_event_id, EventActions.LEDGER_CREATED
        )
    if event is None:
        return None
    identity = _event_acceptance_identity(
        event, bead_id=bead_id, repositories_key="repositories"
    )
    if identity is None:
        return None
    identity_dict = identity.to_dict()
    return {
        "task_id": identity_dict["task_id"],
        "checkpoint_event_id": event.event_id,
        "acceptance_identity": identity_dict,
        "repositories": identity_dict["repositories"],
        "recorded_at": event.timestamp,
    }


def get_review_identity_record(
    bead_id: str,
    review_event_id: str,
    base_dir: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Return the identity-bearing record for one `review-approved` event.

    `review_event_id` is the ledger event ID of the approval itself (the same ID
    surfaced as ApprovalProjection.event_id), not the earlier `review-started`
    event; that one is returned separately as `review_started_event_id`.

    Returns None when the event does not exist, is not an approval, or carries no
    acceptance identity. `terminal` is True only while this approval is still the
    live approval (no later invalidation, scope change, or failed verification).

    The result is the review evidence source shape consumed by
    CompositeEvidenceAuthority._review() except for `verification_event_id`,
    which the review ledger does not own: callers must merge it in from the
    verification record store.
    """
    log, projection = load_ledger(bead_id, base_dir)
    event, revision = _find_ledger_event(
        log, review_event_id, EventActions.REVIEW_APPROVED
    )
    if event is None:
        return None
    identity = _event_acceptance_identity(
        event, bead_id=bead_id, repositories_key="approved_repositories"
    )
    if identity is None:
        return None
    identity_dict = identity.to_dict()
    active = projection.active_approval
    return {
        "task_id": identity_dict["task_id"],
        "review_event_id": event.event_id,
        "review_started_event_id": str(event.payload.get("review_event_id") or ""),
        "ledger_revision": revision,
        "acceptance_identity": identity_dict,
        "repositories": identity_dict["repositories"],
        "status": "approved",
        "terminal": active is not None and active.event_id == event.event_id,
        "recorded_at": event.timestamp,
    }


def initialize_ledger(
    *,
    bead_id: str,
    repository_id: str,
    role: str,
    repo_path: str,
    review_ref: str,
    base_ref: str,
    scope: Dict[str, Any],
    actor_role: str,
    actor_id: str,
    base_dir: Optional[str] = None,
    workflow_id: Optional[str] = None,
    attempt_id: Optional[str] = None,
) -> SourceCheckpoint:
    """Checkpoint the declared source and initialize a complete replay identity."""
    canonical_scope = canonicalize_scope(scope)
    checkpoint = create_source_checkpoint(
        repo_path,
        canonical_scope,
        bead_id,
        base_ref=base_ref,
        review_ref=review_ref,
        repository_id=repository_id,
    )
    resolved_base = subprocess.run(
        ["git", "rev-parse", "--verify", f"{base_ref}^{{commit}}"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    ledger_root = os.path.abspath(base_dir or os.getcwd())
    resolved_repo = os.path.abspath(repo_path)
    repository_path = os.path.relpath(resolved_repo, ledger_root).replace(os.sep, "/")
    payload = {
        "repositories": [{
            "repository_id": repository_id,
            "role": role,
            "repository_path": repository_path,
            "review_ref": checkpoint.checkpoint_ref,
            "checkpoint_ref": checkpoint.checkpoint_ref,
            "review_base_sha": resolved_base,
            "reviewed_source_sha": checkpoint.checkpoint_sha,
            "checkpoint_sha": checkpoint.checkpoint_sha,
            "source_scope_hash": checkpoint.source_scope_hash,
            "source_tree_hash": checkpoint.source_tree_hash,
            "reviewed_source_tree_hash": checkpoint.source_tree_hash,
            "source_identity_status": "complete",
        }],
        "source_scope": canonical_scope,
    }
    payload.update(
        build_acceptance_identity_payload(
            task_id=bead_id,
            workflow_id=workflow_id,
            attempt_id=attempt_id,
            repositories=payload["repositories"],
        )
    )
    mutate_ledger(
        bead_id,
        "ledger-created",
        payload,
        actor_role,
        actor_id,
        base_dir=base_dir,
    )
    return checkpoint


def load_ledger(bead_id: str, base_dir: Optional[str] = None) -> Tuple[EventLog, ReviewProjection]:
    """Loads and validates a review ledger, replaying the event log to verify invariants."""
    json_path, _ = get_ledger_paths(bead_id, base_dir)
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"Ledger file not found: {json_path}")
        
    with open(json_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    data = safe_json_loads(content)
    
    events_list = data.get("events", [])
    log = EventLog.from_list(events_list)
    
    # Deriving projections from replaying log
    proj = ReviewProjection.replay(log.events)
    
    # Verify projections match stored values
    # Revision comparison
    stored_rev = data.get("ledger_revision", 0)
    if stored_rev != proj.ledger_revision:
        raise WorkflowIntegrityError(
            f"Stored revision {stored_rev} does not match replayed revision {proj.ledger_revision}"
        )
        
    stored_state = data.get("review_state", "implementation-in-progress")
    if stored_state != proj.review_state:
        raise WorkflowIntegrityError(
            f"Stored state '{stored_state}' does not match replayed state '{proj.review_state}'"
        )
        
    return log, proj

def save_ledger(
    bead_id: str,
    log: EventLog,
    proj: ReviewProjection,
    base_dir: Optional[str] = None
) -> None:
    """Saves the review.json and updates the rendered review.md file."""
    json_path, md_path = get_ledger_paths(bead_id, base_dir)
    os.makedirs(os.path.dirname(json_path), exist_ok=True)
    
    # Structure json matching spec
    data = {
        "schema_version": "1.0",
        "review_state": proj.review_state,
        "repositories": proj.repositories,
        "source_scope": proj.source_scope,
        "active_lease": proj.active_lease.to_dict() if proj.active_lease else None,
        "ledger_revision": proj.ledger_revision,
        "next_finding_number": proj.next_finding_number,
        "findings": {fid: f.to_dict() for fid, f in proj.findings.items()},
        "events": log.to_list()
    }
    
    json_content = json.dumps(data, indent=2).encode("utf-8")
    md_content = render_review_markdown(proj, log).encode("utf-8")
    atomic_write_many({
        Path(json_path): json_content,
        Path(md_path): md_content,
    })

# Maps a ledger event action to the bead state it produces. This is the single
# source of truth: the mutation path validates against it, and the CLI resolves
# a requested target state back through it.
BEAD_ACTION_STATES = {
    "implementation-complete": "implementation-complete",
    "review-requested": "review-requested",
    "review-started": "review-in-progress",
    "changes-requested": "changes-requested",
    "implementation-in-progress": "implementation-in-progress",
    "review-approved": "review-approved",
    "review-approval-invalidated": "implementation-in-progress",
    "verification-started": "verification-in-progress",
    "verification-passed": "ready-to-ship",
    "verification-failed": "implementation-in-progress",
    "shipping-started": "ready-to-ship",
    "shipping-failed": "shipping-failed",
    "shipping-completed": "closed",
}

# Two actions can produce the same state. Name the one a state request means.
_PREFERRED_STATE_ACTIONS = {
    "ready-to-ship": "verification-passed",
}


def resolve_bead_state_action(state: str) -> str:
    """Return the event action that drives the bead into `state`.

    Raises ValueError for a state no action produces, rather than letting the
    caller append an event the projection will silently ignore.
    """
    candidates = [a for a, s in BEAD_ACTION_STATES.items() if s == state]
    if not candidates:
        reachable = ", ".join(sorted(set(BEAD_ACTION_STATES.values())))
        raise ValueError(
            f"No ledger action produces bead state '{state}'. "
            f"Reachable states: {reachable}."
        )
    if len(candidates) == 1:
        return candidates[0]
    if state in _PREFERRED_STATE_ACTIONS:
        return _PREFERRED_STATE_ACTIONS[state]
    if state in candidates:
        return state
    return sorted(candidates)[0]


def _mutate_ledger_unlocked(
    bead_id: str,
    action: str,
    payload: Dict[str, Any],
    actor_role: str,
    actor_id: str,
    base_dir: Optional[str] = None,
    lease_id: Optional[str] = None,
    bypass_lease: bool = False
) -> Tuple[EventLog, ReviewProjection]:
    """Loads, validates, FSM-checks, appends event, and saves review ledger."""
    now = datetime.now(timezone.utc)
    timestamp = format_utc_timestamp(now)

    # 1. Handle Init Case
    if action == "ledger-created":
        log = EventLog()
        proj = ReviewProjection()
        
        event = LedgerEvent(
            event_id="EV-000001",
            action=action,
            timestamp=timestamp,
            actor={"role": actor_role, "actor_id": actor_id},
            payload=payload,
            previous_event_hash=None
        )
        log.append(event)
        proj.apply_event(event)
        save_ledger(bead_id, log, proj, base_dir)
        return log, proj

    # Load existing
    log, proj = load_ledger(bead_id, base_dir)

    # 2. Lease Check
    # Skip lease validation for lease-acquired, lease-broken, recovery-performed
    if not bypass_lease and action not in (
        "lease-acquired", "lease-broken", "lease-resynced", "recovery-performed"
    ):
        # An expired lease no longer blocks other writers; presenting it is still refused.
        if proj.active_lease and (lease_id or is_lease_active(proj.active_lease, now)):
            if not lease_id:
                raise ValueError("Active lease exists, but no --lease-id was provided.")
            validate_lease_for_write(proj, lease_id, now)

    # 3. FSM / Validation Checks
    # a. Finding Status Transitions
    if "finding_id" in payload:
        fid = payload["finding_id"]
        # Determine next status
        status_map = {
            "finding-created": "open",
            "finding-reopened": "open",
            "finding-fixed": "fixed-awaiting-verification",
            "finding-disputed": "disputed",
            "clarification-requested": "clarification-requested",
            "clarification-provided": "clarification-provided",
            "deferral-proposed": "deferral-proposed",
            "deferral-approved": "deferred-verified",
            "finding-verified": "verified",
            "finding-withdrawn": "withdrawn",
            "finding-accepted-as-is": "accepted-as-is",
            "human-decision-required": "human-decision-required",
            "human-decision-recorded": "human-decision-recorded",
            "finding-waived": "human-waived"
        }
        if action in status_map:
            next_status = status_map[action]
            finding = proj.findings.get(fid)
            if not finding:
                if action == "finding-created":
                    # Brand new finding
                    pass
                else:
                    raise KeyError(f"Finding {fid} not found in projection.")
            else:
                if action == "finding-created":
                    raise WorkflowIntegrityError(f"Finding {fid} already exists in projection.")
                validate_finding_transition(
                    current_status=finding.status,
                    next_status=next_status,
                    severity=finding.severity,
                    actor_role=actor_role,
                    clarification_count=finding.clarification_count
                )

    # b. Bead State Transitions
    if action in BEAD_ACTION_STATES:
        next_state = BEAD_ACTION_STATES[action]
        finding_statuses = [f.status for f in proj.findings.values()]
        validate_bead_transition(
            current_state=proj.review_state,
            next_state=next_state,
            actor_role=actor_role,
            finding_statuses=finding_statuses
        )

    # Append Event
    next_idx = proj.ledger_revision + 1
    event_id = f"EV-{next_idx:06d}"
    
    event = LedgerEvent(
        event_id=event_id,
        action=action,
        timestamp=timestamp,
        actor={"role": actor_role, "actor_id": actor_id},
        payload=payload,
        previous_event_hash=log.events[-1].event_hash if log.events else None
    )
    log.append(event)
    proj.apply_event(event)

    save_ledger(bead_id, log, proj, base_dir)
    return log, proj


def mutate_ledger(
    bead_id: str,
    action: str,
    payload: Dict[str, Any],
    actor_role: str,
    actor_id: str,
    base_dir: Optional[str] = None,
    lease_id: Optional[str] = None,
    bypass_lease: bool = False,
) -> Tuple[EventLog, ReviewProjection]:
    """Apply one ledger mutation while holding the stable cross-process lock."""
    with ledger_lock(bead_id, base_dir):
        return _mutate_ledger_unlocked(
            bead_id, action, payload, actor_role, actor_id,
            base_dir=base_dir, lease_id=lease_id, bypass_lease=bypass_lease,
        )


def mutate_ledger_batch(
    bead_id: str,
    operations: List[Tuple[str, Dict[str, Any], str, str]],
    *,
    base_dir: Optional[str] = None,
    lease_id: Optional[str] = None,
    _already_locked: bool = False,
) -> Tuple[EventLog, ReviewProjection]:
    """Validate a mutation batch off-disk and replace JSON/Markdown together."""
    def apply_batch():
        real_json, real_md = get_ledger_paths(bead_id, base_dir)
        with tempfile.TemporaryDirectory() as directory:
            temp_json, temp_md = get_ledger_paths(bead_id, directory)
            os.makedirs(os.path.dirname(temp_json), exist_ok=True)
            if os.path.exists(real_json):
                Path(temp_json).write_bytes(Path(real_json).read_bytes())
            if os.path.exists(real_md):
                Path(temp_md).write_bytes(Path(real_md).read_bytes())
            result = None
            for index, (action, payload, actor_role, actor_id) in enumerate(operations):
                result = _mutate_ledger_unlocked(
                    bead_id, action, payload, actor_role, actor_id,
                    base_dir=directory,
                    lease_id=lease_id,
                    bypass_lease=index > 0,
                )
            if result is None:
                raise ValueError("ledger mutation batch cannot be empty")
            atomic_write_many({
                Path(real_json): Path(temp_json).read_bytes(),
                Path(real_md): Path(temp_md).read_bytes(),
            })
            return result

    if _already_locked:
        return apply_batch()
    with ledger_lock(bead_id, base_dir):
        return apply_batch()


def mutate_ledger_transaction(
    bead_id: str,
    operation_builder,
    *,
    base_dir: Optional[str] = None,
    lease_id: Optional[str] = None,
) -> Tuple[EventLog, ReviewProjection]:
    """Build and commit a batch against one locked, freshly replayed revision."""
    with ledger_lock(bead_id, base_dir):
        _, projection = load_ledger(bead_id, base_dir)
        built = operation_builder(projection)
        effective_lease_id = lease_id
        if isinstance(built, tuple):
            operations, effective_lease_id = built
        else:
            operations = built
        return mutate_ledger_batch(
            bead_id,
            operations,
            base_dir=base_dir,
            lease_id=effective_lease_id,
            _already_locked=True,
        )


def build_start_review_operations(
    projection: ReviewProjection,
    actor_id: str,
    *,
    requested_lease_id: Optional[str] = None,
    ttl_seconds: int = 600,
    actor_role: str = "reviewer",
    now: Optional[datetime] = None,
    force_takeover: bool = False,
    takeover_reason: Optional[str] = None,
) -> Tuple[List[Tuple[str, Dict[str, Any], str, str]], str]:
    """Return lease and state events for an atomic review start.

    An active lease held by another actor is refused with LeaseError unless
    `force_takeover` is set, which requires a non-empty `takeover_reason` and
    records the seizure as a `lease-broken` event before acquiring.
    """
    if not actor_id.strip():
        raise ValueError("actor_id is required")
    if ttl_seconds <= 0:
        raise ValueError("ttl_seconds must be positive")
    current_time = now or datetime.now(timezone.utc)
    expires_at = format_utc_timestamp(current_time + timedelta(seconds=ttl_seconds))
    active = projection.active_lease
    seized = False
    if active and is_lease_active(active, current_time):
        if active.actor_id != actor_id:
            if not force_takeover:
                raise LeaseError(
                    f"Review lease is owned by {active.actor_id} until {active.expires_at}."
                )
            if not (takeover_reason or "").strip():
                raise ValueError("takeover_reason is required to force a lease takeover")
            seized = True
        else:
            if requested_lease_id and requested_lease_id != active.lease_id:
                raise LeaseError("Requested lease ID does not match the reviewer's active lease.")
            operations = [
                ("lease-renewed", {"expires_at": expires_at}, actor_role, actor_id)
            ]
            if projection.review_state == "review-requested":
                operations.append(("review-started", {}, actor_role, actor_id))
            return operations, active.lease_id

    lease_id = requested_lease_id or uuid.uuid4().hex
    operations = []
    if active:
        break_payload = {
            "lease_id": active.lease_id,
            "reason": "takeover" if seized else "expired",
            "replaced_by": lease_id,
        }
        if seized:
            break_payload["detail"] = takeover_reason
        operations.append(("lease-broken", break_payload, actor_role, actor_id))
    operations.append(("lease-acquired", {
        "lease_id": lease_id,
        "actor_role": actor_role,
        "actor_id": actor_id,
        "acquired_at": format_utc_timestamp(current_time),
        "expires_at": expires_at,
    }, actor_role, actor_id))
    if projection.review_state == "review-requested":
        operations.append(("review-started", {}, actor_role, actor_id))
    return operations, lease_id


def start_review(
    bead_id: str,
    actor_id: str,
    *,
    requested_lease_id: Optional[str] = None,
    ttl_seconds: int = 600,
    actor_role: str = "reviewer",
    base_dir: Optional[str] = None,
    force_takeover: bool = False,
    takeover_reason: Optional[str] = None,
) -> Tuple[EventLog, ReviewProjection]:
    """Atomically acquire or renew review ownership and start the review."""
    def build(projection):
        return build_start_review_operations(
            projection, actor_id, requested_lease_id=requested_lease_id,
            ttl_seconds=ttl_seconds, actor_role=actor_role,
            force_takeover=force_takeover, takeover_reason=takeover_reason,
        )

    return mutate_ledger_transaction(bead_id, build, base_dir=base_dir)


def build_resync_lease_operations(
    projection: ReviewProjection,
    actor_id: str,
    lease_id: str,
    *,
    now: Optional[datetime] = None,
) -> Tuple[List[Tuple[str, Dict[str, Any], str, str]], str]:
    """Return the event that re-points a lease at the ledger's current revision.

    `validate_lease_for_write` refuses any write once
    `projection.ledger_revision` has moved past the lease's recorded
    `current_ledger_revision`, and nothing else heals that drift: expiry can be
    waited out or taken over, a stale revision cannot. Applying the emitted
    `lease-resynced` event re-points the lease, so the holder can write again.

    Only the holder of the active lease may resync it: a different `actor_id`,
    or a `lease_id` that is not the active lease, raises LeaseError.
    """
    if not actor_id.strip():
        raise ValueError("actor_id is required")
    if not lease_id.strip():
        raise ValueError("lease_id is required")
    active = projection.active_lease
    if not active:
        raise LeaseError("No active lease exists on this ledger.")
    if active.lease_id != lease_id:
        raise LeaseError(
            f"Lease ID mismatch. Active: {active.lease_id}, Provided: {lease_id}"
        )
    if active.actor_id != actor_id:
        raise LeaseError(
            f"Lease {lease_id} is held by {active.actor_id}; only its holder may resync it."
        )
    current_time = now or datetime.now(timezone.utc)
    operations = [(
        "lease-resynced",
        {
            "lease_id": lease_id,
            "ledger_revision": projection.ledger_revision,
            "previous_ledger_revision": active.current_ledger_revision,
            "resynced_at": format_utc_timestamp(current_time),
        },
        active.actor_role,
        actor_id,
    )]
    return operations, lease_id


def resync_lease(
    bead_id: str,
    actor_id: str,
    lease_id: str,
    *,
    base_dir: Optional[str] = None,
) -> Tuple[EventLog, ReviewProjection]:
    """Atomically re-point the holder's lease at the ledger's current revision."""
    def build(projection):
        return build_resync_lease_operations(projection, actor_id, lease_id)

    return mutate_ledger_transaction(bead_id, build, base_dir=base_dir)
