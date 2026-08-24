# Large Task: Multi-Track Change

Use this flow for a feature, migration, or other change whose work can be
split into dependent tracks and needs reviewable acceptance evidence.

## Prerequisites

- Setup is complete and the generated effective config is readable.
- The requirement has an owner available to confirm scope and trade-offs.
- Repository identity, expected source scope, and validation commands are known.
- The work can be decomposed into tracks with explicit dependencies.

## Flow

1. Run `$gin-workflow:discuss` and inspect the relevant code and constraints.
2. Summarize the requirement, risks, and acceptance criteria; wait for explicit
   confirmation.
3. Run `$gin-workflow:plan` to write the approved plan with file scope,
   validation intent, provider role, and reasoning tier.
4. Run `$gin-workflow:orchestrate` to create dependency-aware durable tasks and
   validate every assignment before task mutation.
5. Run `$gin-workflow:execute` for ready tracks. Workers receive bounded scope,
   context, and acceptance identity; route fallback preserves reasoning tier.
6. Request code review through the review capability. A reviewer uses the
   checkpoint/ref and active lease; findings are fixed or explicitly dispositioned.
7. Run `$gin-workflow:verify` against requirement, plan, tests, review approval,
   and authoritative evidence.
8. Run `$gin-workflow:ship` only after verification and handoff checks pass.

## State and evidence gates

Discussion must be confirmed before planning; plan approval precedes orchestration;
orchestration readiness precedes execution; all required tracks and dependencies
must be ready before their workers run. Acceptance records share one
`workflow_id`/`attempt_id`/`task_id` identity and repository snapshots with
non-empty scope/tree hashes, checkpoint SHA, and checkpoint ref. Review evidence
requires terminal approval and passed verification. Beads status, not a plan
checkbox or worktree, determines progress and closure.

## Realistic example

A product team adds CSV export in three tracks: (A) schema and permissions,
(B) streaming exporter depending on A, and (C) UI download flow depending on B.
The plan assigns `docs`/low to documentation, `backend`/medium to A and B, and
`frontend`/medium to C. Orchestration validates all assignments first. A worker
uses an explicit Codex model; a temporary Antigravity fallback records its
provider-default selection without claiming a concrete model. Review then checks
the checkpoint and tests for all three tracks before verification passes.

## Common failures

- Setup config is absent or has incompatible 2.3 channels: lifecycle routing holds.
- A track has unknown role/tier or missing local mapping: orchestration rejects
  the complete assignment set before creating partial execution state.
- A worker route is unavailable, or evidence has a cross-attempt identity:
  the task remains open and verification cannot pass.
- A reviewer has a live lease held by another actor, or the checkpoint scope
  changed: review waits or requires a fresh checkpoint and authorized recovery.

## Safe recovery

Use the owning skill's diagnostic. Run setup maintenance only through approved
`setup` actions; return to plan when scope changes; use progress/workflow to
select the next ready or blocked task; retry a provider through configured
same-tier fallback. For a stale lease, let the lease expire or use the review
capability's guarded takeover. Rebuild evidence from authoritative sources and
rerun focused tests. Never edit installed cache copies, write empty hashes, or
manually bypass task/provider capabilities.
