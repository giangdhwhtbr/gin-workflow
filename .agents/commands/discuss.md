---
name: discuss
description: Start requirement discovery and discussion before planning or task creation.
---

# /discuss Command

Start the requirement discovery and discussion phase for `gin-workflow`.

Use this command when you have a new requirement and want the agent to explore it deeply,
ask clarifying questions, identify risks and constraints, challenge assumptions, suggest
alternatives, and continue the discussion until the requirement is fully understood.

This command should use the `discovering-work` skill.

## Usage

```bash
/discuss [topic or requirement]
```

## Instructions

1. Use the `discovering-work` skill as the primary workflow for this command.
2. Explore the relevant project context before proposing solutions.
3. Ask clarifying questions and continue discussion until the requirement is fully understood.
4. Identify ambiguity, missing information, edge cases, risks, dependencies, and constraints.
5. Suggest improvements, alternatives, and stronger approaches when appropriate.
6. Summarize the final understanding and wait for explicit user confirmation.
7. Do not create plans or Beads tasks during this phase.
8. After user confirmation, transition to `/plan`.
