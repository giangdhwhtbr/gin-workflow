import json
import os
import sys
from datetime import datetime, timezone
from typing import Dict, Any, Tuple, Optional, List

from review_ledger.events import LedgerEvent, EventLog, WorkflowIntegrityError
from review_ledger.projections import ReviewProjection, FindingProjection
from review_ledger.finding_fsm import validate_finding_transition
from review_ledger.bead_fsm import validate_bead_transition
from review_ledger.lease import validate_lease_for_write, format_utc_timestamp
from review_ledger.renderer import render_review_markdown

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
    dir_path = os.path.join(base_dir, ".planning", bead_id)
    return (
        os.path.join(dir_path, "review.json"),
        os.path.join(dir_path, "review.md")
    )

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
    
    # Save review.json
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        
    # Render and save review.md
    md_content = render_review_markdown(proj, log)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

def mutate_ledger(
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
    if not bypass_lease and action not in ("lease-acquired", "lease-broken", "recovery-performed"):
        if proj.active_lease:
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
    state_map = {
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
        "shipping-completed": "closed"
    }
    if action in state_map:
        next_state = state_map[action]
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
