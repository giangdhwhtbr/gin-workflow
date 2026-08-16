---
name: worker-dispatch
description: Dispatch bounded implementation work through configured native workers with safe sequential fallback.
---

# Worker Dispatch Skill

Dispatch one approved, dependency-ready task through the configured worker capability.

## Required inputs

- resolved `EffectiveConfig`
- an approved plan whose `execution_strategy` contains `mode`, `workers.mode`, and `rationale`
- one generated `ContextManifest(stage="execute")`
- one task identity, retry identity, provider role and reasoning tier, isolation policy, approved scope, and expected result contract

## Dispatch rules

1. Validate the bounded manifest before dispatch. Fail with `context_unavailable` when required context cannot be loaded; never transfer the parent transcript, provider model names, secrets, or private reasoning.
2. Select direct execution for sequential work, one-agent work, work with three or fewer tasks, or work without an explicit worker condition. Select worker execution only for parallelizable work with more than three tasks, long-running work, specialized work, or independent review.
3. Re-resolve the approved provider role and reasoning through local mappings at dispatch time. Recheck circuit, native health, and capacity before selecting a candidate; preview manifests are not execution guarantees.
4. Preserve the ordered preferred/fallback policy and never downgrade the requested reasoning tier. Record the actual provider/model alias and whether fallback was used in runtime events only.
5. Use the configured provider-neutral adapter. Native adapters bridge only to harness worker support and delegate coding workflow to `subagent-driven-development`; this wrapper does not restate implementation, TDD, debugging, planning, or review methodology.
6. When a circuit is open, native support is unhealthy, or capacity times out, record `worker.unavailable` before trying the next same-tier candidate. Do not start cloud SDK clients or daemon processes.
7. Enforce configured concurrency, an isolated workspace per worker, and one task claim per worker. Capacity saturation follows queue policy and never changes circuit health. Reuse the retry identity so repeated dispatch or collection is idempotent.
8. If every route is unavailable, return `worker_routes_unavailable` and leave durable task closure to the lifecycle coordinator.
9. Validate the normalized result before accepting completion. Preserve completed results during retry, timeout, or partial failure and never redispatch a completed task.

Read [worker lifecycle](references/worker-lifecycle.md), [delegation policy](references/delegation-policy.md), and [result contract](references/result-contract.md) before dispatch.
