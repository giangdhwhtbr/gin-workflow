---
name: orchestrate
description: After plan approval, automatically create and wire Beads tasks from the plan for execution.
---

# /orchestrate Command

After the plan is approved, use this command to translate the plan into durable Beads
execution state. The agent should create the required tasks, break down work into actionable
beads, define dependencies, and prepare execution without requiring the user to run manual
`bd` commands.

State ownership is defined in [orchestration-state-model.md](file://../references/orchestration-state-model.md).

## Usage

```bash
/orchestrate [--plan <path>] [--worktree|--no-worktree] [--max-tracks <N>] [--integration-branch <name>] [--inject-agents-md]
```

## Instructions

1. Use the `bead-orchestrator` skill to coordinate and manage execution.
2. Treat the approved plan as the input for task creation, dependency mapping, scope, and validation intent.
3. Automatically create and connect the necessary Beads tasks from the plan.
4. Keep Beads as the durable source of truth for track status, ownership, dependencies, readiness, blockers, and closure.
5. Prepare the work so execution can begin with `bead-worker` or `/execute`.
6. Do not require the user to manually run `bd create`, `bd dep add`, or claim commands as part of normal workflow.
