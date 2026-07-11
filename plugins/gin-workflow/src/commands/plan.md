---
name: plan
description: After requirement confirmation, create a project-committed implementation plan in `.planning/plans/`.
---

# /gin-workflow:plan Command

Use this command only after the requirement discovery and discussion phase has ended with an
explicit user confirmation of the summarized understanding.

Turn that confirmed understanding into a durable, git-tracked plan in `.planning/plans/`
using the `writing-plans` skill. If scope, tradeoffs, risks, or success criteria are still
unresolved, return to `/discuss` first.

## Instructions

1. Confirm that the user has explicitly approved the summarized understanding.
2. If understanding is not yet confirmed, stop and return to `/discuss`.
3. Convert the confirmed understanding into a concrete implementation shape, file scope, task decomposition, testing strategy, and risk mitigation plan.
4. Keep the plan aligned with any user-approved decisions from the discovery phase.
5. Use the `writing-plans` skill to draft the approved plan per [plan-schema.md](file://../skills/writing-plans/plan-schema.md).
6. Save the resulting plan to `.planning/plans/<timestamp>-<description>.md`.
7. Record `Model Guidance` metadata in the plan using abstract model classes only.
8. Assume `standard_impl` unless a phase or track clearly justifies `high_reasoning` or `cheap_simple`.
9. After the plan is approved, transition to `/orchestrate` so the agent can create and wire the Beads tasks automatically.
