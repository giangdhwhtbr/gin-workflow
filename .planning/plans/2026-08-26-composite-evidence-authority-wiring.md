# Plan: CompositeEvidenceAuthority production wiring

## Objective

Every schema-2.3 project can complete the `verify` stage on any harness.
`ProviderRegistry.from_effective_config()` can obtain a real
`CompositeEvidenceAuthority` without every calling script hand-wiring four
resolvers, and that authority's cross-source identity checks are backed by
real durable state instead of only test fixtures.

## Model Guidance
- `default_model_class`: `standard_impl`
- `phase_guidance`:
  - `plan`: `standard_impl`
  - `implement`: `standard_impl`
  - `verify`: `standard_impl`
  - `review`: `high_reasoning`
  - `docs`: `cheap_simple`
- `override_rule`: Use `high_reasoning` for the review_ledger identity-threading track; execution boundaries there are the least settled part of this plan.

## Requirement Analysis

- Problem statement: `ProviderRegistry.from_effective_config()` (registry.py:176-182)
  requires a real `CompositeEvidenceAuthority` under `schema_version: '2.3'`, but
  the only place in the codebase that ever constructs one is test fixtures
  (`tests/workflow_core/test_end_to_end.py`, `tests/workflow_providers/test_registry.py`).
  No production code path builds one from real repository state, so `verify`
  is unconditionally blocked for every schema-2.3 project, on every harness.
  Reproduced live on qwikfone-rh6 under both Claude and Codex.
- Success criteria:
  - A production factory builds a real `CompositeEvidenceAuthority` from
    on-disk/durable state (no test-only fixtures required).
  - `ProviderRegistry.from_effective_config()` auto-constructs this authority
    when `evidence_authority` is not explicitly passed and `schema_version`
    is `2.3`, so individual skill-driven scripts don't need to hand-wire
    four resolvers themselves.
  - Worker test evidence, git checkpoint evidence, review-approval evidence,
    and verification evidence are each backed by real durable records that
    agree on the same `AcceptanceIdentity` for a given workflow attempt.
  - Existing test suite (347 tests as of commit 5c4e573) still passes; new
    tests cover the new production paths.
- Constraints:
  - `review_ledger/` (events.py, projections.py, bead_fsm.py, git_adapter.py)
    is a live, actively-used event-sourced system backing other in-progress
    beads (e.g. qwikfone). Changes there must be additive/backward-compatible
    with existing ledger files already on disk — do not break `review-ledger.py`
    subcommands or existing `.planning/<bead>/review.json` files.
  - Policy (`docs/context-and-evidence-policy.md`): worker/event payloads
    never carry credentials, full environment, command lines, or private
    reasoning. Only normalized fields (schema_version, tests, acceptance
    identities) may be persisted.
  - Do not change the portable worker-request/result contract fields already
    validated by `worker_dispatch.py` (`REQUIRED_RESULT_FIELDS`,
    `WorkerTestResult` schema) — only add persistence of data already present
    on those objects.
- Non-goals:
  - Not building a general-purpose new datastore; reuse `WorkflowEventStore`
    (events.jsonl) where the shape already fits, matching how `worker.*`
    routing events are already persisted.
  - Not redesigning `review_ledger`'s finding/dispute/deferral FSM — only
    adding identity fields to the checkpoint/approve path.
  - Not changing `ApprovalDecision`'s portable dataclass; only clarifying
    skill guidance for how an agent constructs one (docs-only track).

## Approach Options

### Option 1: Extend `WorkflowEventStore` for worker/verification, thread `AcceptanceIdentity` into `review_ledger` for checkpoint/review
- Summary: Persist worker results and verification records as new event
  types on the existing `events.jsonl` store (same mechanism already used
  for `worker.requested`/`worker.completed`/etc.). Add `AcceptanceIdentity`
  fields to `review_ledger`'s checkpoint/approve mutations so
  `checkpoint_resolver`/`review_resolver` can read the real ledger.
- Pros: Reuses existing, tested, atomic/idempotent infrastructure
  (`WorkflowEventStore`, `review_ledger` FSM) rather than inventing new
  storage. Keeps state ownership boundaries intact (events.jsonl owns
  runtime/orchestration facts; review_ledger owns review state) per the
  README's own ownership model.
- Cons: The review_ledger identity threading is real design/implementation
  work against a live system; requires careful backward compatibility with
  existing ledger files.

### Option 2: Duplicate all four evidence sources into a single new bespoke evidence-authority store
- Summary: Build one new file format that mirrors everything (worker
  results, checkpoints, reviews, verification) independent of
  `events.jsonl` and `review_ledger`.
- Pros: Single format to design once.
- Cons: Creates two sources of truth for review/checkpoint state (the real
  `review_ledger` and this new mirror), which can silently drift and
  directly contradicts this repo's explicit state-ownership model
  (`docs/orchestration-state-model.md`). Rejected.

### Recommended Approach
- Selected option: Option 1.
- Reasoning: Reuses infrastructure already proven correct (atomic, locked,
  idempotent JSONL append for events; the FSM/event-sourcing already built
  for review_ledger) and preserves existing ownership boundaries instead of
  introducing a parallel, driftable copy of review/checkpoint state.

## Scope

- In scope:
  - Persisting `WorkerResult` (schema_version, tests, request/result
    `AcceptanceIdentity`) as a durable event at the existing
    `RoutedWorkerDispatcher._commit_result()` choke point.
  - A new `verification.recorded` event type + a small recording helper,
    analogous to the existing `_emit()` pattern.
  - Threading `AcceptanceIdentity` through `review_ledger`'s checkpoint and
    approve mutations so real ledger data satisfies `checkpoint_resolver`/
    `review_resolver`.
  - A production factory (`build_composite_evidence_authority(root,
    event_store)`) wiring all four resolvers to real state.
  - `ProviderRegistry.from_effective_config()` auto-constructing that
    authority under schema 2.3 when `evidence_authority` is not explicitly
    passed, while still honoring an explicit override (tests keep working
    unchanged).
  - Updating `verify/SKILL.md` and `approval-manager/SKILL.md` with concrete,
    harness-agnostic guidance for constructing `ApprovalDecision`.
- Out of scope:
  - Redesigning `review_ledger`'s finding lifecycle FSM.
  - Retrofitting historical/already-completed beads' evidence.
  - Any qwikfone-side changes; this plan is entirely within `gin-workflow`.

## Execution Strategy

```yaml
execution_strategy:
  mode: worker
  workers:
    mode: parallel
  rationale: Four tracks touch independent subsystems (routed dispatch, a new event type, review_ledger, and the registry factory); Tracks 1-3 have no file overlap and can run in parallel, with Track 4 depending on all three landing first.
```

## Tasks

### Track 1: Persist worker results as durable evidence
- **Dependencies**: none
- **Files**: `plugins/gin-workflow/src/scripts/workflow_providers/routed_worker.py`, `tests/workflow_providers/test_routed_worker.py`
- **Provider role**: `backend`
- **Reasoning**: `medium`
- **Acceptance criteria**: When a routed worker completes with `status == "completed"`, `schema_version == "2.3"`, and both `WorkerRequest.acceptance_identity` and `WorkerResult.acceptance_identity` set, `_commit_result()` appends one new idempotent `worker.result` event to the injected `WorkflowEventStore` containing `worker_id`, `status`, `schema_version`, `request_acceptance_identity`, `result_acceptance_identity`, `request_workspace_id`, and `tests` (only `WorkerTestResult`/auditable entries, via their existing `.to_dict()`). No event is emitted for failed/cancelled results or results without an acceptance identity. No credential/environment/command-line/private-reasoning fields are added to the payload. Existing 347-test suite still passes; new tests cover the emit-vs-skip conditions.
- **Estimated complexity**: medium

### Track 2: Verification record store
- **Dependencies**: none
- **Files**: `plugins/gin-workflow/src/scripts/workflow_providers/evidence.py` (or a new sibling module if cleaner), `tests/workflow_providers/test_evidence.py`
- **Provider role**: `backend`
- **Reasoning**: `medium`
- **Acceptance criteria**: A new `verification.recorded` event type can be durably appended (idempotent, via `WorkflowEventStore`) carrying `task_id`, `verification_event_id`, `review_event_id`, `acceptance_identity`, and `status`. A small helper function exists for callers (the `verify` skill's driving script) to record one. Tests cover round-trip record/read and duplicate/idempotency behavior.
- **Estimated complexity**: medium

### Track 3: Thread AcceptanceIdentity into review_ledger checkpoint/approve
- **Dependencies**: none
- **Files**: `plugins/gin-workflow/src/scripts/review_ledger/events.py`, `plugins/gin-workflow/src/scripts/review_ledger/projections.py`, `plugins/gin-workflow/src/scripts/review_ledger/bead_fsm.py`, `plugins/gin-workflow/src/scripts/review_ledger/cli.py`, `plugins/gin-workflow/src/scripts/review-ledger.py`, `tests/review_ledger/`
- **Provider role**: `backend`
- **Reasoning**: `high`
- **Acceptance criteria**: `checkpoint`/`approve` ledger mutations can carry an `AcceptanceIdentity` (workflow_id/attempt_id) alongside the existing repository_id/checkpoint_sha/source_scope_hash fields, without breaking any existing `review-ledger.py` subcommand or any ledger file already on disk (additive schema change; identity fields optional/absent on old records). `load_ledger`/projections expose enough to build the `checkpoint_resolver`/`review_resolver` payload shapes `CompositeEvidenceAuthority._checkpoint()`/`_review()` require (evidence.py:152-251). Existing `tests/review_ledger/` suite still passes; new tests cover identity-bearing checkpoints/approvals.
- **Estimated complexity**: high

### Track 4: Production factory + registry auto-wiring + skill docs
- **Dependencies**: Track 1, Track 2, Track 3
- **Files**: `plugins/gin-workflow/src/scripts/workflow_providers/registry.py`, new `plugins/gin-workflow/src/scripts/workflow_providers/evidence_authority.py`, `plugins/gin-workflow/src/skills/verify/SKILL.md`, `plugins/gin-workflow/src/skills/approval-manager/SKILL.md`, `tests/workflow_providers/test_registry.py`
- **Provider role**: `backend`
- **Reasoning**: `medium`
- **Acceptance criteria**: `build_composite_evidence_authority(root, event_store)` wires all four resolvers (worker/checkpoint/review/verification) to the real stores from Tracks 1-3. `ProviderRegistry.from_effective_config()` calls it automatically when `schema_version == '2.3'` and no explicit `evidence_authority` is passed; an explicit override (as tests already do) still takes precedence, so the existing test suite's construction pattern is unaffected. `verify/SKILL.md` and `approval-manager/SKILL.md` document concretely how an agent (any harness) constructs and records an `ApprovalDecision`. A live re-run of `verify` against a real schema-2.3 project (e.g. qwikfone-rh6, once unblocked) no longer raises "schema 2.3 evidence authority must be a CompositeEvidenceAuthority".
- **Estimated complexity**: medium

## Integration
- **Branch**: `integration/gin-workflow-8wf-evidence-authority`
- **Merge strategy**: parallel-then-merge

## Validation
- [ ] Full suite (`python3 -m unittest tests.test_all -v`) passes, 0 regressions against the pre-change baseline (347 tests)
- [ ] New tests added for Tracks 1-4 pass
- [ ] `review-ledger.py` CLI still works against a pre-existing (unmodified-format) `.planning/<bead>/review.json`
- [ ] Manual: run `verify` against qwikfone-rh6 (or an equivalent schema-2.3 fixture project) and confirm the `CompositeEvidenceAuthority` error no longer occurs

## Notes
- Model guidance is planning metadata, not Beads state.
- Track 3 is the highest-risk/highest-complexity track; if it proves larger
  than expected during execution, split it into its own follow-up plan
  rather than expanding scope here.
- Root-cause investigation and options were already discussed with and
  confirmed by the user (2026-08-26): "Full production wiring" was chosen
  over a minimal qwikfone-only unblock or relaxing the schema-2.3 check, and
  "track as a proper bead/plan" was chosen over ad hoc inline implementation
  once the review_ledger identity-threading scope became clear. Tracked as
  bead `gin-workflow-8wf`.
