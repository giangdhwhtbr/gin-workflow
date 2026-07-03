---
name: executing-plans
description: Use this skill to run an approved plan inline in the current session, with manual checkpoints between task batches. For automated subagent-per-task execution with two-stage review, use :subagent-driven-development instead.
---

# Executing plans (inline)

Walk through a plan task-by-task in the current session. Read each task, follow the steps verbatim, run the verifications, mark progress, and stop the moment something blocks you.

This skill is the simpler of the two execution paths. It works even on platforms without subagent support and gives the user a chance to step in between batches.

**Announce at start:** "Using `:executing-plans` to run the plan inline."

**When to use this vs. `:subagent-driven-development`:**

| Situation | Choose |
|-----------|--------|
| Subagent dispatch unavailable on this platform | `:executing-plans` |
| User wants visible per-batch checkpoints | `:executing-plans` |
| Plan tasks are tightly interleaved (each one needs context from the last) | `:executing-plans` |
| Tasks are mostly independent and you want fast continuous execution | `:subagent-driven-development` |
| You want each task reviewed by a fresh agent before continuing | `:subagent-driven-development` |

If subagents are available, prefer the other path — quality is meaningfully higher because each task gets fresh context and two-stage review.

## The process

### 1. Load and read the plan critically

- Read the plan file in full (`.planning/plans/<filename>`).
- Look for blockers before starting: missing test commands, undefined symbols, references to files that don't exist, contradictions with the spec.
- If concerns surface, raise them with the user before touching code.
- If everything looks fine, create a TaskCreate task list mirroring the plan's task headings, set the first task to `in_progress`, and proceed.

### 2. Execute task-by-task

For each task in order:

1. Mark the task `in_progress`.
2. Follow each step exactly. The plan's steps are 2–5 minute actions written in order; do not skip ahead, do not improvise.
3. Run every verification step the plan specifies. If a "run the test" step is followed by an expected output, check that the actual output matches.
4. If a step shows code, write that code (do not paraphrase the implementation).
5. When the last step of the task completes, mark the task `completed`.

Move on to the next task without pausing for permission. The plan was already approved — execute it.

### 3. Stop when blocked

Stop and ask for help — do not guess — when:

- A step depends on something not present (missing file, missing dependency, undefined symbol).
- A verification fails repeatedly even after re-running the implementation step.
- A step's instructions are ambiguous in a way that would change the result.
- The plan asks for something that conflicts with what the codebase already does (and the spec didn't anticipate the conflict).

Surface the problem in plain language: what step you're on, what you tried, what the failure looked like. Don't guess and continue.

### 4. Hand off when all tasks are done

Once every task is marked `completed`:

- Announce: "All tasks done. Handing off to `:finishing-a-development-branch`."
- Invoke `:finishing-a-development-branch`. That skill runs the full test suite, presents merge / PR / cleanup options, and executes the user's choice.

## Returning to earlier steps

Re-run step 1 (load and review) when:

- The user updates the plan based on something you encountered.
- A blocker reveals that the plan's approach is wrong and needs replanning.

Don't try to power through a fundamentally wrong plan. Stop, surface, replan.

## Things to avoid

- **Don't start implementation on `main` / `master` without explicit user consent.** Use `:using-git-worktrees` first if no worktree exists.
- **Don't skip verification steps** — if the plan says "run the test and confirm it fails", run it. The plan-author put it there to catch mistakes.
- **Don't paraphrase the plan's code** — type the code as written. The plan went through review; your job is to execute it, not redesign it.
- **Don't continue past a blocker** — surface it and ask.

## Where this skill sits

| Aspect | Detail |
|--------|--------|
| Command entry | `/execute` (with mode flag for inline) |
| Direct skill call | `:executing-plans` |
| Reads | `.planning/plans/<filename>` |
| Writes | code, commits |
| Downstream | `:finishing-a-development-branch` after the last task |
| Alternative path | `:subagent-driven-development` for automated subagent-per-task execution |
| Required upstream | `:writing-plans` (produced the plan); optional `:using-git-worktrees` (isolated workspace) |
