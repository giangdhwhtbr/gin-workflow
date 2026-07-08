---
name: writing-plans
description: Guidance on how to analyze requirements, compare approaches, and write execution-ready plans before coding.
---

# Writing Plans Skill

This skill defines how to turn a request into a clear, high-quality, execution-ready plan for the `gin-workflow` plugin.

## Execution Rules

1. Inspect the relevant codebase context before drafting the plan.
2. Clarify ambiguous objectives, constraints, non-goals, and success criteria before locking the plan.
3. Propose 2-3 approaches with tradeoffs, recommend one, and only then finalize the plan.
4. Always follow the format defined in [plan-schema.md](file://plan-schema.md) when writing or modifying a plan.
5. Save plans in the `.planning/plans/` directory with a timestamped or semantic filename (e.g. `.planning/plans/2026-06-28-init-auth.md`).
6. Ensure tasks are broken down into discrete tracks that can run independently or specify dependencies explicitly.
7. Define clear, testable acceptance criteria for each track.
8. Document verification steps in the `Validation` section.

## Planning Standard

Every plan should answer these questions before the task list begins:

1. What problem is being solved, and what is out of scope?
2. What constraints or risks materially affect implementation?
3. Which approach was selected, and why was it chosen over alternatives?
4. How will the user know the work is complete?
