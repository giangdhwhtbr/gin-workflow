---
name: discuss
description: Start requirement discovery and discussion before planning or task creation.
---

# Discuss Skill

This is the primary user-facing entry point for new requirements in `gin-workflow`.

Use this skill to explore a requirement deeply, ask clarifying questions, identify risks and constraints, challenge assumptions, and align on understanding before any plan or Beads task is created.

## Delegation

- Use `discovering-work` as the underlying workflow contract.
- Treat `/discuss` as an optional command alias only on hosts that surface plugin commands.

## Usage Standard

1. Explore the relevant project context.
2. Ask clarifying questions until the requirement is fully understood.
3. Identify ambiguity, missing information, edge cases, risks, dependencies, and constraints.
4. Suggest improvements, alternatives, and stronger approaches when appropriate.
5. Summarize the final understanding and wait for explicit user confirmation.
6. Do not create plans or Beads tasks during this phase.
7. After user confirmation, transition to `plan`.
