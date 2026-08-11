---
name: writing-plans
description: Extends superpowers:writing-plans with Gin Workflow plan schema, confirmation gating, Beads-ready tracks, and model guidance metadata.
---

# Writing Plans Skill

This skill extends `superpowers:writing-plans` for the `gin-workflow` plugin.

## Base Skill

When `superpowers:writing-plans` is available, use it first as the base planning contract. Then apply the Gin Workflow overlay below.

If `superpowers:writing-plans` is unavailable, continue with this skill's self-contained rules and say that the Superpowers base skill could not be loaded.

## Gin Workflow Overlay

Gin Workflow keeps the Superpowers planning standard, with these plugin-specific overrides:

1. Use this skill only after the requirement discovery phase has ended with explicit user confirmation of the summarized understanding.
2. Save plans in `.planning/plans/`, not `docs/superpowers/plans/`.
3. Follow the format defined in [plan-schema.md](file://plan-schema.md) when writing or modifying a plan.
4. Break work into Beads-ready tracks with explicit dependencies.
5. Include goals and scope, technical approach, required changes, implementation steps, testing strategy, and risks or mitigations.
6. Include `Model Guidance` metadata using the abstract classes `high_reasoning`, `standard_impl`, and `cheap_simple`.
7. Treat `standard_impl` as the implicit default when no model class is specified.
8. Declare `execution_strategy` exactly as specified in [plan-schema.md](file://plan-schema.md). Strategy selection and later changes follow the canonical [agent task lifecycle reference](../../references/agent-task-lifecycle.md).

## Execution Rules

1. Confirm that discovery ended with explicit user approval of the summarized understanding.
2. If objectives, constraints, non-goals, or success criteria are still unclear, stop and return to discovery.
3. Convert the confirmed requirement into a plan with concrete file mapping, right-sized tasks, explicit validation, and realistic sequencing.
4. Structure the plan so it can be turned directly into Beads tasks during orchestration.
5. Apply the Gin Workflow overlay for plan location, schema, Beads-ready track structure, validation, and model guidance.

## Planning Standard

Every plan should answer these questions before the task list begins:

1. What problem is being solved, and what is out of scope?
2. What constraints or risks materially affect implementation?
3. Which approach was selected, and why was it chosen?
4. What files, systems, or behaviors must change?
5. How will the user know the work is complete?
6. Which model class guidance, if any, needs to be recorded for phases or tracks?
