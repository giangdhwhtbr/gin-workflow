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
