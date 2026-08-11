# Capability Provider Contracts

The effective configuration selects provider-neutral capabilities. Lifecycle skills use these contracts rather than provider-specific commands:

- task tracking: durable task identity, dependencies, readiness, ownership, blockers, and closure
- workspace: isolation preparation and cleanup metadata
- worker dispatch: dispatch, cancel, status, and normalized result collection
- knowledge: search and proposal submission; workers do not make permanent knowledge writes
- review: request, terminal review state, and findings
- evidence: record/query an evidence index and evaluate required acceptance evidence
- notifications: optional delivery only

Every provider exposes health and capability metadata. Providers may be unavailable; callers use the configured fallback where one is defined. Beads remains the durable task-tracking provider in this repository, while plan files own approved decomposition and runtime artifacts remain supplemental.

Provider selection does not authorize a lifecycle transition. Approval, context, artifact, and evidence guards still apply. See [orchestration-state-model.md](orchestration-state-model.md) and [context-and-evidence-policy.md](context-and-evidence-policy.md).
