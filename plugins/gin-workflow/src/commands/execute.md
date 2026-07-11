---
name: execute
description: Implement approved work from the plan through Beads-backed worker execution.
---

# /execute Command

Execute approved work from an existing plan through Beads-backed worker execution.

## Instructions

1. Use the `executing-plans` skill to guide the implementation.
2. Select a target plan from `.planning/plans/` or follow a specified task list derived from the approved plan.
3. Treat the plan as scope and validation input while Beads tracks durable execution progress.
4. Execute work through `bead-worker` behavior for each implementation track.
5. If implementation discovers requirement ambiguity, missing information, or blockers that need product clarification, return to `/discuss` instead of making assumptions.
6. Verify each step as you complete it.
