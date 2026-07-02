---
name: plan
description: Write a project-committed implementation plan to `.planning/plans/` for use by `/orchestrate`. Distinct from the native session-local planning mode.
---

# /gin-workflow:plan Command

Writes a durable, git-tracked plan to `.planning/plans/` using the `writing-plans` skill.
This is **not** the same as the native Antigravity session planning mode — it produces a
persistent file that `/gin-workflow:orchestrate` reads to create beads and parallel workers.

## Instructions

1. Use the `writing-plans` skill to draft a plan per [plan-schema.md](file://../skills/writing-plans/plan-schema.md).
2. Ask the user for details if objectives, scope, or tasks are ambiguous.
3. Save the resulting plan to `.planning/plans/<timestamp>-<description>.md`.
