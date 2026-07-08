---
name: plan
description: Analyze requirements, compare implementation approaches, and write a project-committed implementation plan to `.planning/plans/`.
---

# /gin-workflow:plan Command

Analyze the request, relevant codebase context, and tradeoffs before writing a durable,
git-tracked plan to `.planning/plans/` using the `writing-plans` skill. This command
compares implementation approaches before it commits to a plan, then produces the
persistent file that `/gin-workflow:orchestrate` reads to create beads and parallel workers.

## Instructions

1. Inspect the relevant codebase context before drafting anything.
2. Clarify objectives, constraints, risks, and success criteria when they are unclear.
3. Compare 2-3 implementation approaches, explain tradeoffs, and recommend one.
4. Get user alignment on the selected approach before finalizing the plan.
5. Use the `writing-plans` skill to draft the approved plan per [plan-schema.md](file://../skills/writing-plans/plan-schema.md).
6. Save the resulting plan to `.planning/plans/<timestamp>-<description>.md`.
