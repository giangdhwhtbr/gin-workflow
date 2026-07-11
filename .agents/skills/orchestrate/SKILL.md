---
name: orchestrate
description: After plan approval, automatically create and wire Beads tasks from the plan for execution.
---

# Orchestrate Skill

This is the primary user-facing orchestration skill for `gin-workflow`.

Use it after the plan is approved to translate the plan into durable Beads execution state. The agent should create tasks, define dependencies, and prepare execution without requiring the user to run manual `bd` commands.

## Delegation

- Use `bead-orchestrator` as the underlying orchestration contract.
- Treat `/orchestrate` as an optional command alias only on hosts that surface plugin commands.

## Usage Standard

1. Treat the approved plan as the source for task creation, dependency mapping, scope, and validation intent.
2. Automatically create and connect the necessary Beads tasks from the plan.
3. Keep Beads as the durable source of truth for execution status, readiness, blockers, and closure.
4. Prepare the work so execution can begin with `execute`.
