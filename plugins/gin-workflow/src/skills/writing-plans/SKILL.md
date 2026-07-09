---
name: writing-plans
description: Extends superpowers:writing-plans with Gin Workflow plan schema, Beads-ready tracks, and model guidance metadata.
---

# Writing Plans Skill

This skill extends `superpowers:writing-plans` for the `gin-workflow` plugin.

## Base Skill

When `superpowers:writing-plans` is available, use it first as the base planning contract. Then apply the Gin Workflow overlay below.

If `superpowers:writing-plans` is unavailable, continue with this skill's self-contained rules and say that the Superpowers base skill could not be loaded.

## Gin Workflow Overlay

Gin Workflow keeps the Superpowers planning standard, with these plugin-specific overrides:

1. Save plans in `.planning/plans/`, not `docs/superpowers/plans/`.
2. Follow the format defined in [plan-schema.md](file://plan-schema.md) when writing or modifying a plan.
3. Break work into Beads-ready tracks with explicit dependencies.
4. Include `Model Guidance` metadata using the abstract classes `high_reasoning`, `standard_impl`, and `cheap_simple`.
5. Treat `standard_impl` as the implicit default when no model class is specified.
6. Default `plan` work to `standard_impl`; escalate planning to `high_reasoning` only when the planning step still has major unresolved tradeoffs, sequencing risk, or unclear execution boundaries.

## Execution Rules

1. Inspect the relevant codebase context before drafting the plan.
2. Clarify ambiguous objectives, constraints, non-goals, and success criteria before locking the plan.
3. Propose 2-3 approaches with tradeoffs, recommend one, and only then finalize the plan.
4. Apply the Superpowers task-quality rules for file mapping, right-sized tasks, concrete steps, and self-review.
5. Apply the Gin Workflow overlay for plan location, schema, Beads-ready track structure, validation, and model guidance.

## Planning Standard

Every plan should answer these questions before the task list begins:

1. What problem is being solved, and what is out of scope?
2. What constraints or risks materially affect implementation?
3. Which approach was selected, and why was it chosen over alternatives?
4. How will the user know the work is complete?
5. Which model class guidance, if any, needs to be recorded for phases or tracks?
