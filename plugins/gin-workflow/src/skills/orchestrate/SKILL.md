---
name: orchestrate
description: Mirror one approved plan into Beads tracks, resolve routes, and prepare an isolated workspace.
---

## Before you start
1. If `.agent-workflow/generated/effective-config.yaml` does not exist in the main checkout (the parent of `git rev-parse --path-format=absolute --git-common-dir`; linked worktrees have none), stop: tell the user to run `/setup` once and do nothing else. (`capabilities: {}` is a valid config.)
2. Read [references/stage-contract.md](../../references/stage-contract.md) now: it defines the gate CLI, valid evidence, approval, and git rules this stage relies on.

# Orchestrate

Turn an approved plan into durable Beads state. Beads is the only source of status, ownership, readiness, dependencies, blockers, and closure; workspace and worker metadata are supplemental.

## Steps

1. Require `plan_approved` and read the plan from `.planning/plans/`. When the spec names `Epic: <id>` (a roadmap epic), use it as the parent of the tracks and create no other epic. With `project.layout: sdd`, read `<change>/plan.md`, reuse the epic, and label tracks per the `gin-sdd` skill.
   With `project.team.enabled`, label, assign, and sync track beads per the `gin-team` skill.
2. Reject any implementation or review track without a provider role, model, and effort (effort when catalog has efforts); list every one.
3. Distinguish Parent Bead (Deliverable) vs Track Beads (Work Units), and create the track beads now; their ids key the routes in step 4:
   - **Parent Bead (Deliverable / Epic)**: the overall deliverable. Merge holds such as "remain open until human-confirmed merge" belong only here.
   - **Track Beads (Work Units)**: one per plan track (`gin-workflow task create --parent <epic>`). Acceptance criteria are strictly technical (in-scope code, tests, review approval). Never copy parent merge holds into tracks. A track whose plan entry has a `Human gate:` line gets `--labels human-gate`.
4. Write the tracks as a JSON list of `{"task_id", "provider_role", "model", "effort"}`, with `task_id` the track bead id created in step 3, to `.agent-workflow/runtime/routes-<workflow>.json` and run `gin-workflow routes resolve --workflow-id <workflow> --tracks <file> --json`. Exit 2 lists every diagnostic; report them all and stop (after fixing the configuration, run it again; the beads stay). It writes the assignment manifest only when every track resolves. Concrete provider/model names never enter Beads or the plan.
5. Mirror dependencies with `gin-workflow task dep add <blocked> <blocker>` and check `gin-workflow task ready` / `gin-workflow task show`. Each track closes after tests and review pass, which unblocks its dependents.
6. Isolate by default: create a worktree per the `gin-worktrees` skill under `.planning/worktrees/`. Disabling isolation or running on the current branch needs explicit approval, recorded first.
7. Production-impacting parallel work or an execution-strategy change needs explicit approval.
8. `gin-workflow record orchestration-ready --workflow-id <id> --epic <parent-bead> --evidence "<bead-ids>; <worktree>; <branch>" --actor <id>`. The epic lets `gin-workflow state` derive `implementation_complete` once every track is closed.

## Exit

Return `orchestration_ready`. Do not begin execution.

End with `Next commands:`, the ready tracks (`/gin-workflow:execute <id>`), and what `gin-workflow goal --workflow-id <workflow>` prints, verbatim: a Claude Code `/goal` (suggest auto mode) over only the tracks the agent can finish unattended, or why there is none.
