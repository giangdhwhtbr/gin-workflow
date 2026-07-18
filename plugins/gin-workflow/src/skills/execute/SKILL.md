---
name: execute
description: Implement approved work from the plan through Beads-backed worker execution.
---

# Execute Skill

This is the primary user-facing implementation skill for `gin-workflow`.

Use it to execute approved work from a plan through Beads-backed worker behavior.

## Delegation

- Use `executing-plans` as the primary implementation contract.
- Use `bead-worker` behavior for each implementation track.
- Treat `/execute` as an optional command alias only on hosts that surface plugin commands.

## Usage Standard

1. Select a target plan or approved task list derived from the plan.
2. Treat the plan as scope and validation input while Beads tracks durable execution progress.
3. Implement each bead according to scope, run local validation as work progresses, and use the `knowledge-capture` skill to record notable codebase discoveries and decisions.
4. If implementation reveals ambiguity, missing information, or blockers that require product clarification, use `telegram-notify` to send a `work_blocked` notification, then return to `discuss` instead of making assumptions.
5. After implementation is complete, transition to `verify`.
