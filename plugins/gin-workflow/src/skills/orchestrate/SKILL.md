---
name: orchestrate
description: Mirror one approved plan into Beads tracks, resolve routes, and prepare an isolated workspace.
---

## Before you start
1. If `.agent-workflow/generated/effective-config.yaml` does not exist in the repository, stop: tell the user to run `/setup` once and do nothing else. (`capabilities: {}` is a valid config.)
2. Read [references/stage-contract.md](../../references/stage-contract.md) now: it defines the gate CLI, valid evidence, approval, and git rules this stage relies on.

# Orchestrate

Turn an approved plan into durable Beads state. Beads is the only source of status, ownership, readiness, dependencies, blockers, and closure; workspace and worker metadata are supplemental.

## Steps

1. Require `plan_approved` and read the plan from `.planning/plans/`.
2. Reject any implementation or review track without a provider role and reasoning; list every one.
3. Resolve routes for the whole batch before any durable write: build an `AssignmentRequest(task_id, provider_role, reasoning, main_harness, workflow_id)` per track and call `workflow_core.assignments.resolve_all_assignments(requests, config, local)` (`PYTHONPATH=<plugin>/scripts`; `config` is the generated effective config and `local` comes from `workflow_core.provider_config.load_provider_local_config(repo)`). If anything is unresolved, report all diagnostics and stop. Otherwise persist each preview with `write_assignment_manifest`. Concrete provider/model names never enter Beads or the plan.
4. Distinguish Parent Bead (Deliverable) vs Track Beads (Work Units):
   - **Parent Bead (Deliverable / Epic)**: the overall deliverable. Merge holds such as "remain open until human-confirmed merge" belong only here.
   - **Track Beads (Work Units)**: one per plan track (`bd create --parent <epic>`). Acceptance criteria are strictly technical (in-scope code, tests, review approval). Never copy parent merge holds into tracks.
5. Mirror dependencies with `bd dep add <blocked> <blocker>` and check `bd ready` / `bd show`. Each track closes after tests and review pass, which unblocks its dependents.
6. Isolate by default: create a worktree per the `gin-worktrees` skill under `.planning/worktrees/`. Disabling isolation or running on the current branch needs explicit approval, recorded first.
7. Production-impacting parallel work or an execution-strategy change needs explicit approval.
8. `gin-workflow record orchestration-ready --epic <parent-bead> --evidence "<bead-ids>; <worktree>; <branch>" --actor <id>`. The epic lets `gin-workflow state` derive `implementation_complete` once every track is closed.

## Exit

Return `orchestration_ready`. Do not begin execution.
