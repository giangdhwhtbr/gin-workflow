# Workflow Use Cases

Choose a guide by the shape of the work. These flows use lifecycle skills and
capability providers; they do not ask you to edit runtime caches or bypass a
configured provider.

## Prerequisites

- The plugin is installed for the active harness.
- Repository setup has created `.agent-workflow/generated/effective-config.yaml`.
- The requirement, repository location, and any safety constraints are known.
- For resumed work, durable task/config/evidence records are available; a
  worktree or branch alone is not progress evidence.

## Flow

| Situation | Guide | First action | Typical finish |
| :--- | :--- | :--- | :--- |
| Multi-track feature or migration | [Large task](large-task.md) | `$gin-workflow:discuss` | `$gin-workflow:ship` |
| Existing durable work | [Resume in progress](resume-in-progress.md) | `$gin-workflow:progress` | routed next stage |
| Small bounded defect | [Quick debug](quick-debug.md) | bounded discussion | focused verify/ship |

## State and evidence gates

The router selects one next lifecycle stage from durable gates. Beads owns task
status, dependencies, readiness, blockers, and closure; plans own approved scope;
the review ledger owns review findings and leases; evidence binds worker tests,
Git checkpoints, review approval, and verification to one acceptance identity.
A missing setup config, stale or mismatched identity, unavailable provider, lease
conflict, or missing approval holds progress.

## Realistic example

A team can use [Large task](large-task.md) to add a three-part export feature,
[Resume in progress](resume-in-progress.md) the next morning after a provider
outage, and [Quick debug](quick-debug.md) for a one-file regression discovered
while verifying that feature. Each guide preserves the same durable ownership.

## Common failures

Common stops include missing generated config, an unconfirmed requirement, a
plan/scope mismatch, provider capacity or health failure, stale review lease,
identity-bound evidence mismatch, and task-backend drift. None is repaired by
editing a cache or manually invoking a backend outside its capability contract.

## Safe recovery

Use the diagnostic returned by the owning skill, then re-enter through `setup`
(for missing/configuration issues), `progress` or `workflow` (for lifecycle
state), the review capability (for lease/review issues), or the evidence and
verification gates (for integrity issues). If scope changes, return to discuss
and plan; preserve the existing durable task and evidence history.
