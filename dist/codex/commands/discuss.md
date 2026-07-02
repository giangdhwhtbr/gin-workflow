---
name: discuss
description: Explore design options and trade-offs for a topic without committing to implementation.
---

# /discuss Command

Explore design options and trade-offs for a topic or question. Accepts a topic or question as args and produces a written summary convertible into a plan.

## Instructions

1. Use the `brainstorming` skill to structure the exploration of design options and trade-offs.
2. Pass the topic/question from args into the skill as the focus of the discussion.
3. Stay non-destructive: use read-only analysis tools and do not commit to implementation or make code changes.
4. Produce a written summary of options, pros/cons, and a recommended direction the user can feed into `/plan` via the `writing-plans` skill as the next step.
