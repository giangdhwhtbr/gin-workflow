---
name: quick
description: Run a lightweight, single-track task with minimal ceremony.
---

# /quick Command

Execute a small, fast-turnaround task directly — no plan file, no multi-track orchestration. Accepts a short task description as args.

## Instructions

1. Take the task description from the command args.
2. Use the `executing-plans` skill (see [executing-plans/SKILL.md](file://../skills/executing-plans/SKILL.md)) to guide a single-track execution.
3. Keep ceremony minimal: implement the change, run the relevant checks, and report the result. Do not create a plan file or spawn an orchestrator.
