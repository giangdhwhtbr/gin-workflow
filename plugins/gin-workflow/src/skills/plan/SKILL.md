---
name: plan
description: After requirement confirmation, create a durable implementation plan.
---

# Plan Skill

This is the primary user-facing planning skill for `gin-workflow`.

Use it only after the requirement discovery phase has ended with an explicit user confirmation of the summarized understanding.

## Delegation

- Use `writing-plans` as the underlying planning contract.
- Treat `/plan` as an optional command alias only on hosts that surface plugin commands.

## Usage Standard

1. Confirm that the user explicitly approved the summarized understanding.
2. If understanding is not yet confirmed, return to `discuss`.
3. Run the `context-retrieval` skill to query Obsidian and retrieve related user stories, decisions, and indexes before writing the plan.
4. Turn the confirmed understanding into a durable implementation plan in `.planning/plans/`.
5. Include goals and scope, technical approach, required changes, implementation steps, testing strategy, and risks or mitigations.
6. After writing the plan, use `telegram-notify` to send a `plan_ready` notification (two-way). If the user replies via Telegram, use their response as approval or revision feedback. On timeout, save state and exit gracefully.
7. After the plan is approved, transition to `orchestrate`.
