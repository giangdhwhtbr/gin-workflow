# Capability Provider Contracts

The effective configuration selects provider-neutral capabilities. Lifecycle skills use these contracts rather than provider-specific commands:

- task tracking: durable task identity, dependencies, readiness, ownership, blockers, and closure
- workspace: isolation preparation and cleanup metadata
- worker dispatch: resolve role/reasoning, recheck provider/model circuit health and capacity, then dispatch, cancel, report status, and collect normalized results
- knowledge: search and proposal submission; workers do not make permanent knowledge writes
- review: request, terminal review state, and findings
- evidence: record/query an evidence index and evaluate required acceptance evidence
- notifications: optional delivery only

Every provider exposes health and capability metadata. Native worker providers are injected from gitignored machine-local configuration; the registry never derives executables or concrete models from portable `EffectiveConfig`. Providers may be unavailable; callers use only ordered same-reasoning fallbacks. Actual route aliases, circuit state, and assignment previews are runtime evidence. Beads remains the durable task-tracking provider in this repository, while plan files own approved decomposition and runtime artifacts remain supplemental.

Worker infrastructure failures are classified. Quota, rate limit, authentication, service, timeout, and crash failures affect the provider/model circuit. Task, test, review, invalid-result, and capacity failures do not. Review dispatch follows the same router, with independent-provider and maximum-cycle policy enforced before task closure.

Provider selection does not authorize a lifecycle transition. Approval, context, artifact, and evidence guards still apply. See [orchestration-state-model.md](orchestration-state-model.md) and [context-and-evidence-policy.md](context-and-evidence-policy.md).

## Integrity-bound contracts

Acceptance evidence is bound to an `AcceptanceIdentity` containing `workflow_id`,
`attempt_id`, `task_id`, and one or more `RepositorySnapshot` values. Every snapshot
requires a repository id, source-scope hash, source-tree hash, checkpoint SHA, and
checkpoint ref; exact identity mismatches fail closed. The implementation is in
`workflow_core/identity.py` and is covered by `tests/workflow_core/test_identity.py`.

The review ledger creates a source checkpoint with a temporary Git index, computes
source-scope and tree hashes, and updates only the dedicated review ref. It verifies
that HEAD, branch, real index, and working-tree status are unchanged. Review start
acquires or renews one active lease atomically; a live lease conflicts across actors,
an expired lease can be replaced, and writes require the active lease id, expiry,
and ledger revision to match. See `review_ledger/git_adapter.py`,
`review_ledger/cli.py`, `review_ledger/lease.py`, and their tests.

The evidence provider derives authoritative records from independent worker, Git,
review, and verification resolvers. Worker request/result identities must match;
repository records must match resolved Git snapshots; review evidence requires a
terminal approval plus a passed verification event. Invalid, stale, cross-attempt,
or non-authoritative records are rejected before completeness can pass. See
`workflow_providers/evidence.py` and `tests/workflow_providers/test_evidence.py`.

Task tracking is capability-driven. Before durable task mutation the provider
probes the configured `bd` or `br` executable, command capabilities, backend
identity, and health. `br` data movement (`flush`, `pull`, or `merge`) requires a
matching mode/backend approval and a persisted fresh `DATA_MOVE` authorization;
dry-run previews do not mutate. Use the task-tracking capability through the
workflow skills, never a manual provider bypass. See `workflow_providers/task_tracking.py`.
