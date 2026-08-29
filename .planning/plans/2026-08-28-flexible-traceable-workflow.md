# Plan: Flexible-but-traceable workflow gating

## Objective

Every gate in the lifecycle stays in place and every bypass leaves an
auditable record, but no gate is a dead end any more. A trivial change can
reach `ship` without hand-editing state; a long-running worker does not
invalidate the approval that authorized it; and from any blocked state a
single command prints why the workflow is held and at least one concrete way
out.

The governing principle: **traceability is an append-only record of who
bypassed what and why — not the impossibility of bypassing.** The repository
currently conflates the two, so every gate is a concrete wall.

## Model Guidance
- `default_model_class`: `standard_impl`
- `phase_guidance`:
  - `plan`: `standard_impl`
  - `implement`: `standard_impl`
  - `verify`: `standard_impl`
  - `review`: `high_reasoning`
  - `docs`: `cheap_simple`
- `override_rule`: Use `high_reasoning` for Track 1 (waiver semantics), Track 3
  (approval validity model), and Track 5 (review-ledger recovery). Those three
  decide what "safe" means; the rest is mechanical once they are settled.

## Requirement Analysis

- Problem statement: the lifecycle enforces correctness by making every gate
  unpassable, which turns ordinary friction into hard stops.
  Five distinct blockers were confirmed in the code:

  1. **Linear 6-stage chain with no size discrimination.**
     `workflow_core/router.py:27` (`_STAGE_GATES`) forces
     `discuss → plan → orchestrate → execute → verify → ship` for every task.
     `_gate_complete()` (`router.py:344`) treats an absent gate as `False`,
     so a one-line typo fix must still traverse all six stages.
  2. **`blocked` is a terminal hold with no exit.**
     `router.py:299` routes `blocked`/`status == "blocked"` to
     `RouteDecision("progress", "hold", ...)`, but the `progress` skill is
     explicitly read-only and mutation-free
     (`plugins/gin-workflow/src/skills/progress/SKILL.md:29`). No `unblock`
     action exists anywhere. A disabled capability
     (`router.py:341`) holds identically and permanently.
  3. **Five-minute approval expiry, checked twice.**
     `_APPROVAL_FRESHNESS = timedelta(minutes=5)` (`router.py:47`) is applied
     to both the `ApprovalDecision` and its persisted `approval.recorded`
     audit event, and revalidated immediately before routing
     (`router.py:186-206`). With `routing.worker.timeout_seconds: 900`, an
     approval obtained before dispatch is structurally guaranteed to be stale
     when the result comes back. Four distinct failure statuses
     (`missing` / `invalid` / `mismatched` / `stale`, `router.py:107-165`) are
     all fatal and none carries a recovery hint.
     `_is_fresh()` also requires `age >= 0`, so any backwards clock skew fails.
  4. **Review-ledger recovery gaps.** `validate_lease_for_write`
     (`review_ledger/lease.py:44`) requires an exact `lease_id`, an unexpired
     lease, **and** `projection.ledger_revision == lease.current_ledger_revision`.
     Commit `a25e94c` taught `build_start_review_operations`
     (`review_ledger/cli.py:612`) to break and reacquire an *expired* lease,
     but nothing heals a **revision mismatch** or a lease actively held by
     another actor — both are still dead ends.
     `reconcile_transition_states` (`review_ledger/transitions.py`) raises
     `WorkflowIntegrityError` on any unmatched state pair.
     `bead_fsm.validate_bead_transition` raises on any pair absent from its
     table, and the table has no `review-requested → implementation-in-progress`
     edge, so a worker cannot withdraw work already submitted for review.
     `finding_fsm` reaches `human-waived` only from `human-decision-required`,
     and hard-codes a maximum of one clarification.
  5. **Hair-trigger routing knobs.**
     `.agent-workflow/generated/effective-config.yaml` sets
     `circuit_breaker.failure_threshold: 1` with `cooldown_seconds: 900`, so a
     single transient failure removes a provider for fifteen minutes.
     Combined with `codex` concurrency `1`, `queue.max_wait_seconds: 120`,
     `worker.max_retries: 1`, `review.require_independent: true` and
     `review.allow_self_review_fallback: false`, route exhaustion is easy to
     hit and terminates at `human_decision_required`.

  Compounding all five: `route_next_stage()` has **no caller anywhere in the
  repository outside tests**. `workflow_core/cli.py` rejects any `argv[0]`
  other than `"setup"` (`cli.py:59`). The router's `state` mapping is assembled
  ad hoc by whichever agent is reading the markdown skills, so there is no way
  to ask the system which gate is unmet and why.

- Success criteria:
  - A documentation-only or single-line fix travels from requirement to ship
    with no manual state editing and at most one human prompt.
  - An approval obtained before a 900-second worker dispatch is still valid
    when that worker returns, provided the approved scope has not changed.
  - Every gate bypass is recoverable from the event log: which gate, which
    class, who waived it, the stated reason, the scope it applied to, and the
    follow-up task opened for it.
  - From any blocked or held state, `gin-workflow state` prints the unmet gate
    and at least one concrete remedy, and `gin-workflow unblock` can act on it.
  - The existing test suites under `tests/workflow_core/`,
    `tests/review_ledger/`, and `tests/workflow_providers/` still pass.

- Constraints:
  - `WorkflowEventStore` (`workflow_core/events.py`) is append-only with
    deterministic `event_id` derived from
    `(event_type, workflow_id, task_id, payload, idempotency_key)`
    (`events.py:33-50`). New event types must fit that identity scheme
    unmodified. `WORKFLOW_EVENT_SCHEMA` (`schemas.py:114`) already accepts any
    non-empty `event_type`, so `gate.waived` needs no schema migration.
  - `APPROVAL_REQUEST_SCHEMA` (`schemas.py:172`) sets
    `additionalProperties: False`; adding `scope_hash` requires an explicit,
    optional property there.
  - `workflow_core/` must not import from `review_ledger/`. The scope hash is
    therefore passed into the router as an opaque string that it only compares
    for equality; producing it stays with the caller, which can use the
    existing `review_ledger/source_identity.py:compute_source_scope_hash` and
    `compute_source_tree_hash`.
  - `BUILT_IN_DEFAULTS["policy"]` is `{}` and `CONFIG_SCHEMA` types `policy` as
    a free-form object (`schemas.py:32`, `configuration.py:52`). New policy
    knobs therefore need no schema-version bump.
  - `review_ledger/` backs live ledgers on disk in `.planning/<bead>/`. All
    changes must be additive and must not break existing ledger files or the
    existing `review-ledger.py` subcommands.
  - Default behavior for a caller that supplies no new fields must be
    unchanged, so consuming repositories on older skills keep working.

- Non-goals:
  - Not removing any gate from `_STAGE_GATES`, and not weakening the
    approval requirement for `commit`, `push`, `upgrade`, or `data_move`.
  - Not introducing risk lanes/profiles. One mechanism (waiver) covers the
    "small change" case; a second classification axis would be redundant.
  - Not redesigning the finding/dispute/deferral FSM. CRITICAL findings remain
    non-deferrable.
  - Not changing Beads' ownership of durable task state, or the review
    ledger's ownership of findings and approval history.
  - Not touching worker dispatch, provider adapters, or native CLI probing
    beyond changing configuration values.

## Approach Options

### Option 1: Waivable gates with recorded justification (selected)
- Summary: keep every gate. Change `_gate_complete` from a boolean to a
  tri-state (`satisfied` / `waived` / `unmet`), where `waived` is backed by a
  persisted `gate.waived` event carrying gate, class, reason, scope hash,
  actor, and follow-up task id. Classify gates as *process* (agent may waive
  unilaterally), *safety* (human approval plus a mandatory follow-up task), or
  *non-waivable*. Replace wall-clock approval expiry with scope binding. Add a
  lifecycle CLI so held state is diagnosable and actionable.
- Pros: one mechanism covers all four reported pain points. The audit trail
  gets *stronger*, not weaker — today a bypass happens by an agent hand-editing
  a state dict and leaves no record at all; afterwards it is an event.
  Scope-bound approval is genuinely safer than a five-minute window, which
  today permits approving one thing and doing another four minutes later.
- Cons: introduces a mechanism that can be over-used; requires care that
  safety waivers cannot be self-granted.

### Option 2: Risk lanes (express / standard / strict)
- Summary: classify each task into a lane; each lane declares which gates
  apply.
- Pros: makes the common "small change" path explicit and predictable.
- Cons: needs a second classification axis and a lane-assignment step that is
  itself a gate. Does not address blocked dead ends, approval staleness, or
  ledger recovery at all — those need Option 1's machinery regardless.
  Rejected as redundant: waiving the three process gates *is* the express lane.

### Option 3: Loosen configuration values only
- Summary: raise `failure_threshold`, `max_retries`, `max_wait_seconds`, and
  the approval TTL; enable `allow_self_review_fallback`.
- Pros: hours of work, near-zero risk, no new concepts.
- Cons: leaves the two structural dead ends untouched — `blocked` still has no
  exit and the six-stage chain still applies to a typo fix. Retained as
  Track 6 *inside* Option 1 rather than as an alternative to it.

### Recommended Approach
- Selected option: Option 1, with Option 3 folded in as Track 6.
- Reasoning: three of the five confirmed blockers are structural (no exit from
  `blocked`, mandatory six-stage traversal, ledger revision mismatch) and
  cannot be reached by tuning numbers. Option 1 is also the only option that
  *improves* auditability, because it converts today's undocumented manual
  state edits into recorded events.

## Scope

- In scope:
  - `plugins/gin-workflow/src/scripts/workflow_core/`: `waivers.py` (new),
    `router.py`, `approvals.py`, `schemas.py`, `configuration.py`, `cli.py`,
    `lifecycle_cli.py` (new).
  - `plugins/gin-workflow/src/scripts/review_ledger/`: `lease.py`,
    `transitions.py`, `bead_fsm.py`, `finding_fsm.py`, `cli.py`,
    and the `review-ledger.py` argument surface.
  - `.agent-workflow/config.yaml` and the regenerated
    `.agent-workflow/generated/effective-config.yaml`.
  - Skill and doc surfaces that describe gate behavior: `docs/agent-task-lifecycle.md`,
    `docs/orchestration-state-model.md`, `docs/verification-and-handoff-workflow.md`,
    `plugins/gin-workflow/src/skills/{workflow,progress,approval-manager,cross-agent-code-review}/SKILL.md`,
    `README.md`.
  - Tests under `tests/workflow_core/` and `tests/review_ledger/`.

- Out of scope:
  - `workflow_providers/` worker dispatch, registry, and native CLI probing.
  - Setup, migration, and bundle machinery (`setup_service.py`,
    `migrations.py`, `bundles.py`) — no schema-version bump is required.
  - Beads itself and the `bd` CLI.
  - The `install.sh` / `install.ps1` packaging path.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: >
    Tracks 1-4 and 6 all edit workflow_core/router.py, approvals.py, or
    configuration.py and must be serialized to avoid merge conflicts on the
    same functions. Only Track 5 (review_ledger) is genuinely independent,
    which is one parallelizable track, below the threshold for worker/parallel.
```

## Tasks

### Track 1: Gate waiver primitives
- **Dependencies**: none
- **Files**:
  - Create `plugins/gin-workflow/src/scripts/workflow_core/waivers.py`
  - Create `tests/workflow_core/test_waivers.py`
- **Provider role**: `backend`
- **Reasoning**: `high`
- **Detail**:
  Define the vocabulary the rest of the plan depends on, with no router
  changes yet.

  - `GateClass(str, Enum)`: `PROCESS`, `SAFETY`.
  - Module constants:
    - `PROCESS_GATES = frozenset({"requirement_confirmed", "plan_approved", "orchestration_ready"})`
    - `SAFETY_GATES = frozenset({"verification_passed", "review_approved"})`
      Note: `review_approved` is deliberately **not** a router gate — see
      `docs/agent-task-lifecycle.md` "Code Review", which states the router
      exposes no `review_approved` gate. It appears here only so that waiving
      independent review is classified, approved, and recorded through the same
      machinery. Do not add it to `_STAGE_GATES`; Verification consumes it.
    - `NON_WAIVABLE_GATES = frozenset({"implementation_complete", "shipped"})`
    - `WAIVER_EVENT_TYPE = "gate.waived"`
  - `classify_gate(gate: str) -> GateClass` raises `ValueError` for a gate in
    `NON_WAIVABLE_GATES` or unknown to all three sets. `implementation_complete`
    is a statement of fact, not ceremony, and `shipped` is terminal; neither is
    meaningfully waivable.
  - `@dataclass(frozen=True) class GateWaiver` with fields
    `gate: str`, `gate_class: GateClass`, `reason: str`, `scope_hash: str`,
    `waived_by: str`, `follow_up_task_id: str | None = None`.
    `__post_init__` rejects an empty `reason`, an empty `scope_hash`, an empty
    `waived_by`, and — for `GateClass.SAFETY` — a missing or empty
    `follow_up_task_id`. It also calls `classify_gate` and rejects a
    `gate_class` that disagrees with the classification.
  - `build_waiver_event(waiver, *, workflow_id, task_id=None) -> WorkflowEvent`
    returns `WorkflowEvent.create(event_type=WAIVER_EVENT_TYPE, ...)` with the
    waiver's `to_dict()` as payload and `actor=waiver.waived_by`.
  - `collect_waivers(store: WorkflowEventStore, *, workflow_id: str, scope_hash: str) -> dict[str, GateWaiver]`
    reads the persisted stream, keeps only `gate.waived` events whose
    `workflow_id` and payload `scope_hash` both match, revalidates each through
    `WorkflowEvent.from_mapping(event.to_dict())` exactly as
    `router._revalidate_audit_event` does, and returns the newest valid waiver
    per gate. Malformed events are skipped, never fatal.
- **Acceptance criteria**:
  - A safety waiver without `follow_up_task_id` raises `ValueError`.
  - A waiver naming `implementation_complete` or `shipped` raises `ValueError`.
  - `collect_waivers` ignores waivers recorded under a different `scope_hash`.
  - `collect_waivers` ignores a corrupted event line without raising.
  - `build_waiver_event` produces an event that `WorkflowEventStore.append`
    accepts and `read_all` returns unchanged.
- **Estimated complexity**: medium

### Track 2: Tri-state gates and remedies in the router
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/router.py`
  - Modify `tests/workflow_core/test_router.py`
- **Provider role**: `backend`
- **Reasoning**: `high`
- **Detail**:
  - Add `remedies: tuple[str, ...] = ()` to `RouteDecision`. Assert in
    `__post_init__` that `decision == "hold"` implies `remedies` is non-empty —
    a hold with no stated way out is the defect this track exists to remove.
  - Replace `_gate_complete(state, gate) -> bool` with
    `_gate_status(state, gate, waivers) -> str` returning
    `"satisfied"` / `"waived"` / `"unmet"`. It keeps the existing strict
    `type(value) is not bool` check for a present gate value, consults
    `waivers` only when the gate value is absent or `False`, and never treats
    a gate in `NON_WAIVABLE_GATES` as waived.
  - In `route_next_stage`, read waivers once via
    `collect_waivers(state["audit_event_store"], workflow_id=..., scope_hash=state.get("scope_hash", ""))`
    when an event store is present; otherwise use an empty mapping so callers
    that pass no store behave exactly as today.
  - Evidence strings gain the waived form:
    `f"{gate}=waived({waiver.reason})"` alongside the existing
    `f"{gate}=false"`, so the returned evidence still narrates the real path.
  - Every existing `hold` return grows remedies:
    - blocked: `("unblock --clear-blocker", f"unblock --gate <gate> --reason <why>")`
    - guard failure: one remedy naming the failing action, e.g.
      `f"re-request approval for {action}"` for `approval:*=missing|stale`, and
      `f"re-record audit event for {action}"` for `audit:*=missing|invalid`.
    - capability disabled: `(f"enable capabilities.{stage} in effective-config.yaml", f"waive {gate} with a recorded reason")`.
- **Acceptance criteria**:
  - A state with `plan_approved` absent but a valid persisted process waiver
    routes past `plan` to `orchestrate`, with `plan_approved=waived(...)` in
    the evidence.
  - A waiver for `implementation_complete` does not let routing pass that gate.
  - A safety waiver for `verification_passed` recorded without an approval is
    ignored (Track 3 supplies the approval check; here it is enough that the
    gate class is carried through).
  - Every `hold` decision returns at least one remedy.
  - Calling `route_next_stage` with no `audit_event_store` and no waivers
    produces byte-identical decisions to the pre-change implementation for all
    existing `tests/workflow_core/test_router.py` cases.
- **Estimated complexity**: high

### Track 3: Scope-bound approval validity
- **Dependencies**: Track 2
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/approvals.py`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/schemas.py`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/router.py`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/configuration.py`
  - Modify `tests/workflow_core/test_router.py`
- **Provider role**: `backend`
- **Reasoning**: `high`
- **Detail**:
  - `ApprovalRequest` gains `scope_hash: str = ""`. `to_dict()` emits it.
    `APPROVAL_REQUEST_SCHEMA` gains `"scope_hash": {"type": "string"}` as an
    optional property, so existing persisted requests stay valid.
  - Replace the module constant `_APPROVAL_FRESHNESS` with a policy lookup:
    `_approval_ttl(config) -> timedelta`, reading
    `config["policy"]["approval"]["ttl_seconds"]` and defaulting to `86400`.
    Add `_CLOCK_SKEW_TOLERANCE = timedelta(seconds=60)`.
  - `_is_fresh(timestamp, now, ttl)` becomes
    `-_CLOCK_SKEW_TOLERANCE <= (now - timestamp) <= ttl`, so a modest backwards
    clock skew no longer reads as a forged future timestamp.
  - Add `_scope_matches(request, state) -> bool`: when
    `policy.approval.bind_to_scope` is true (default) and both
    `request.scope_hash` and `state["scope_hash"]` are non-empty, they must be
    equal. An empty hash on either side means "not scope-bound" and falls back
    to TTL alone, preserving current behavior for callers that supply nothing.
  - `_guard_evidence` emits `approval:{key}=scope_changed` and holds when the
    scope hash differs. `authorize_protected_action` raises
    `PermissionError("approval scope has changed")` in the same case.
  - `_audit_status` uses the same TTL and skew tolerance.
  - `BUILT_IN_DEFAULTS["policy"]` becomes
    `{"approval": {"ttl_seconds": 86400, "bind_to_scope": True}}`.
- **Acceptance criteria**:
  - An approval decided 15 minutes ago against an unchanged scope hash is
    accepted; today it is rejected as stale.
  - The same approval against a changed scope hash is rejected, and the
    router evidence reads `approval:<action>=scope_changed`.
  - An approval decided 25 hours ago is rejected as stale even with a matching
    scope hash.
  - A decision timestamped 30 seconds in the future is accepted; one
    timestamped 10 minutes in the future is rejected.
  - Existing approval tests that supply no `scope_hash` still pass unchanged.
- **Estimated complexity**: high

### Track 4: `gin-workflow state` and `gin-workflow unblock`
- **Dependencies**: Track 2, Track 3
- **Files**:
  - Create `plugins/gin-workflow/src/scripts/workflow_core/lifecycle_cli.py`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/cli.py`
  - Create `tests/workflow_core/test_lifecycle_cli.py`
- **Provider role**: `backend`
- **Reasoning**: `medium`
- **Detail**:
  This is the first real caller of `route_next_stage` outside tests, and the
  answer to "I am stuck and cannot tell why".

  - `cli.py:main` currently errors unless `argv[0] == "setup"`. Extend the
    dispatch to accept `state` and `unblock`, delegating to
    `lifecycle_cli.main(argv)`, and keep the existing usage error for anything
    else.
  - `gin-workflow state [--repository PATH] [--format text|json]`:
    loads the effective config, builds router state from the durable
    task-tracking and evidence sources, calls `route_next_stage` once, and
    prints a per-gate table of `satisfied` / `waived(reason)` / `unmet`, the
    selected stage, the decision, the evidence tuple, and the remedies.
    Read-only; exit code `0` when routing, `1` when holding.
  - `gin-workflow unblock --gate GATE --reason TEXT --actor ID [--follow-up TASK_ID] [--repository PATH]`:
    builds a `GateWaiver`, refuses a safety gate without `--follow-up`,
    refuses a non-waivable gate, appends the `gate.waived` event through
    `WorkflowEventStore`, and prints the resulting event id.
  - `gin-workflow unblock --clear-blocker --reason TEXT --actor ID`:
    records a `blocker.cleared` event so the blocked hold can be lifted with
    the same audit properties as a waiver.
- **Acceptance criteria**:
  - `state` on a repository with an unmet `plan_approved` prints that gate as
    `unmet` and lists at least one remedy, exit code `1`.
  - `state --format json` emits a parseable object with `stage`, `decision`,
    `gates`, `evidence`, and `remedies` keys.
  - `unblock --gate verification_passed` without `--follow-up` exits non-zero
    with a message naming the missing follow-up task.
  - `unblock --gate implementation_complete` exits non-zero.
  - After a successful `unblock --gate plan_approved`, a subsequent `state`
    reports that gate as `waived` and routes to the next stage.
  - `gin-workflow setup ...` and `gin-workflow --version` behave exactly as
    before.
- **Estimated complexity**: high

### Track 5: Review-ledger recovery paths
- **Dependencies**: none
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/review_ledger/lease.py`
  - Modify `plugins/gin-workflow/src/scripts/review_ledger/cli.py`
  - Modify `plugins/gin-workflow/src/scripts/review_ledger/transitions.py`
  - Modify `plugins/gin-workflow/src/scripts/review_ledger/bead_fsm.py`
  - Modify `plugins/gin-workflow/src/scripts/review_ledger/finding_fsm.py`
  - Modify `plugins/gin-workflow/src/scripts/review-ledger.py`
  - Modify `tests/review_ledger/test_lease.py`, `test_bead_fsm.py`,
    `test_finding_fsm.py`, `test_transitions.py`, `test_cli.py`
- **Provider role**: `backend`
- **Reasoning**: `high`
- **Detail**:
  - **Revision-mismatch recovery.** CORRECTION (2026-08-28, found during
    execution): the premise below is wrong. `ReviewProjection.apply_event`
    ends with an unconditional
    `self.active_lease.current_ledger_revision = self.ledger_revision`
    (`review_ledger/projections.py:413-414`), and `load_ledger` always rebuilds
    by replay, so the revision check in `validate_lease_for_write` is
    unreachable for any disk-loaded ledger. Verified by forging drift into a
    copy of a real ledger: replay erased it and the write was allowed. The
    recovery command was still built and tested, but it has no production
    trigger until `gin-workflow-0qh` decides whether the check should be made
    load-bearing or removed. Do not cite revision drift as a live dead end.

    `validate_lease_for_write` keeps failing
    closed, but add `build_resync_lease_operations(projection, actor_id, lease_id, *, now)`
    in `cli.py` and a `resync-lease` subcommand. It emits a `lease-resynced`
    event that re-points `current_ledger_revision` at
    `projection.ledger_revision` for the lease's own holder only. A holder
    mismatch is still an error. This is the gap `a25e94c` left: expiry is
    healed, revision drift is not.
  - **Takeover.** `start-review` gains `--force-takeover --reason TEXT`. When
    an active lease is held by a different actor, this emits
    `lease-broken {"lease_id": ..., "reason": "takeover", "detail": <reason>, "replaced_by": ...}`
    before acquiring. Without the flag, the existing `LeaseError` is unchanged.
  - **Reconciliation.** `reconcile_transition_states` gains a third return
    value `"replay_ledger"` for the Beads-ahead case (Beads status maps to a
    ledger state further along than the ledger records, and a matching pending
    transition exists in reverse). `WorkflowIntegrityError` remains for
    genuinely unmatched pairs, but its message gains the concrete remedy
    (`resync-lease`, or the specific replay direction).
  - **Bead FSM.** Add the two missing edges:
    `("review-requested", "implementation-in-progress"): {"worker"}` so a
    worker can withdraw work already submitted, and
    `("review-in-progress", "review-requested"): {"reviewer"}` so a reviewer
    can hand a review back without a finding.
  - **Finding FSM.** Add `("open", "human-waived"): {"human"}` so a human can
    waive a finding without first routing it through
    `human-decision-required`. Make the clarification cap a parameter
    `max_clarifications: int = 1` on `validate_finding_transition` rather than
    a literal. CRITICAL findings remain non-deferrable — unchanged.
- **Acceptance criteria**:
  - A ledger whose `ledger_revision` has advanced past the lease's recorded
    revision can be written again after `resync-lease`, by the lease holder.
  - `resync-lease` by a non-holder raises `LeaseError`.
  - `start-review --force-takeover` against another actor's active lease
    succeeds and records `lease-broken` with `reason: takeover`; without the
    flag it still raises `LeaseError`.
  - `reconcile_transition_states` returns `replay_ledger` for the Beads-ahead
    case instead of raising.
  - A worker can move `review-requested → implementation-in-progress`.
  - A human can move a finding `open → human-waived`.
  - A CRITICAL finding still cannot reach any deferred state.
- **Estimated complexity**: high

### Track 6: Routing and policy defaults
- **Dependencies**: Track 3
- **Files**:
  - Modify `.agent-workflow/config.yaml`
  - Regenerate `.agent-workflow/generated/effective-config.yaml`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/configuration.py`
  - Modify `tests/workflow_core/test_configuration.py`,
    `tests/workflow_core/test_config_examples.py`
- **Provider role**: `backend`
- **Reasoning**: `low`
- **Detail**:
  - `routing.circuit_breaker.failure_threshold`: `1` → `3`. One transient
    failure should not remove a provider for 900 seconds.
  - `routing.queue.max_wait_seconds`: `120` → `600`, so a queued job outlives
    one in-flight 900-second worker on a concurrency-1 provider.
  - `routing.worker.max_retries`: `1` → `2`.
  - `routing.review.require_independent` stays `true` and
    `allow_self_review_fallback` stays `false`. Route exhaustion keeps
    producing `human_decision_required`, but the message now names the
    Track 4 remedy: waive `review_approved` as a safety gate, which requires
    human approval and a follow-up task.
  - Confirm `policy.approval` defaults from Track 3 land in the regenerated
    effective config.
- **Acceptance criteria**:
  - Regenerated `effective-config.yaml` carries the new values and still
    validates against `CONFIG_SCHEMA`.
  - `tests/workflow_core/test_config_examples.py` passes against the new
    defaults.
- **Estimated complexity**: low

### Track 7: Documentation and skill surfaces
- **Dependencies**: Track 1, Track 2, Track 3, Track 4, Track 5, Track 6
- **Files**:
  - Modify `docs/agent-task-lifecycle.md`
  - Modify `docs/orchestration-state-model.md`
  - Modify `docs/verification-and-handoff-workflow.md`
  - Modify `plugins/gin-workflow/src/skills/workflow/SKILL.md`
  - Modify `plugins/gin-workflow/src/skills/progress/SKILL.md`
  - Modify `plugins/gin-workflow/src/skills/approval-manager/SKILL.md`
  - Modify `plugins/gin-workflow/src/skills/cross-agent-code-review/SKILL.md`
  - Modify `README.md`
- **Provider role**: `docs`
- **Reasoning**: `medium`
- **Detail**:
  - `agent-task-lifecycle.md` "Gates and evidence" gains the gate
    classification table and the rule that a hold always carries a remedy.
  - `orchestration-state-model.md` records that `gate.waived` events are
    durable audit records owned by the event store, and never substitutes for
    Beads status.
  - `verification-and-handoff-workflow.md` requires the handoff summary to
    list any waived gate and its follow-up task id.
  - `approval-manager/SKILL.md` replaces "decisions more than five minutes
    old" with the scope-bound rule and the configurable TTL.
  - `progress/SKILL.md` adds reporting of open waivers and their unclosed
    follow-up tasks — the mitigation that keeps waivers from becoming a habit.
  - `workflow/SKILL.md` documents `gin-workflow state` as the diagnostic entry
    point and drops the "five-minute freshness" wording.
  - `cross-agent-code-review/SKILL.md` documents `resync-lease` and
    `--force-takeover`.
  - `README.md` Troubleshooting gains an entry for diagnosing a held workflow.
- **Acceptance criteria**:
  - No document still states a five-minute approval window.
  - Every new CLI verb and ledger subcommand is documented where an agent
    following the skills would find it.
- **Estimated complexity**: medium

## Integration
- **Branch**: `integration/flexible-traceable-workflow`
- **Merge strategy**: sequential

## Validation

Baseline as of this plan (commit `bb93284`): `python3 -m unittest tests.test_all`
runs 402 tests with 6 pre-existing failures, all of them the same stale
packaging-version assertion in
`tests/workflow_providers/test_harness_packaging.py:143`
(`'1.1.0' != '1.1.1'`, tracked as bead `gin-workflow-3hs`). Those 6 are
unrelated to this plan and must neither be fixed here nor grow.

- [ ] `python3 -m unittest tests.test_all` passes with no failures other than
      those 6 known packaging-version failures, and the total test count has
      grown by the new tests below.
- [ ] New tests exist for: safety-waiver rejection without follow-up,
      non-waivable gate rejection, scope-changed approval rejection,
      long-TTL approval acceptance, hold-without-remedy assertion,
      `resync-lease` holder check, and forced lease takeover.
- [ ] Manual: on a scratch bead, drive a documentation-only change from
      requirement to ship using waivers for the three process gates, and
      confirm the event log contains one `gate.waived` per waived gate with
      reason, actor, and scope hash.
- [ ] Manual: obtain an approval, sleep past 15 minutes, and confirm it is
      still accepted against an unchanged scope and rejected after the scope
      changes.
- [ ] Manual: `gin-workflow state` on a deliberately blocked workflow prints
      the blocker and a remedy, and `gin-workflow unblock` clears it.
- [ ] `git status` reviewed before handoff.

## Risks and Mitigations

- **Waivers become routine and quality drops.** Mitigated by Track 7's
  `/progress` reporting of open waivers with unclosed follow-up tasks, and by
  requiring human approval plus a follow-up task for every safety waiver.
  Worth revisiting after a few weeks of real use: if process waivers are
  issued on nearly every task, the correct fix is to change the default gates,
  not to keep waiving them.
- **`scope_hash` semantics are the load-bearing assumption of Track 3.** If it
  is computed too broadly, unrelated edits invalidate approvals and the old
  friction returns in a new shape; too narrowly, an approval survives a change
  it should not have. Track 3 keeps the router agnostic (equality only) so the
  definition can be tuned in the caller without touching gating logic. Any
  caller supplying an empty hash falls back to TTL-only behavior.
- **Track 5 touches a live event-sourced system with ledgers already on disk.**
  All changes are additive event types and additional FSM edges; no existing
  event type, projection field, or subcommand changes meaning. Existing ledger
  files must be readable before and after — assert this explicitly in
  `tests/review_ledger/test_cli.py`.
- **Track 2 and Track 3 both rewrite the same router functions.** Serialized by
  the declared dependency; do not run them in parallel.
- **Behavioral drift for consuming repositories.** Every new field defaults to
  the current behavior (`scope_hash=""`, no waivers, no event store → identical
  routing), so a repository on older skills is unaffected until it opts in.

## Notes
- Model guidance is planning metadata, not Beads state.
- No schema-version bump is required: `WORKFLOW_EVENT_SCHEMA` already accepts
  arbitrary event types and `policy` is a free-form object.
- Tracks 1-4 and 6 form one dependency chain; Track 5 may start at any time;
  Track 7 closes out.
