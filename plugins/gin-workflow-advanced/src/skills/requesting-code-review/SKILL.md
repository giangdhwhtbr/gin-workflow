---
name: requesting-code-review
description: Use this skill to dispatch a code reviewer (subagent or the bundled code-reviewer agent) to evaluate completed work against its plan and quality standards before issues compound. Required after each task in subagent-driven execution and before merging significant changes.
---

# Requesting code review

Send the work to a reviewer with exactly the context they need — and only that context. The reviewer should not inherit your session's history; they should receive the diff, the plan or requirements, and a clear ask. This keeps the review focused on the code rather than your reasoning, and frees your own context for the next step.

The bundled `code-reviewer` agent at `agents/code-reviewer.md` is the default reviewer. If your platform supports the Task tool, dispatch `code-reviewer` directly. Otherwise, use the prompt template at `code-reviewer.md` next to this file with a general-purpose subagent.

## When to request a review

| Situation | Required? |
|-----------|-----------|
| After each task in `:subagent-driven-development` | Yes |
| After a major feature is complete | Yes |
| Before merging to the main branch | Yes |
| When stuck and a fresh perspective would help | Optional |
| Before starting a refactor (baseline check) | Optional |
| After fixing a complex bug | Optional |

## How to dispatch

### 1. Capture the git range

```bash
BASE_SHA=$(git rev-parse HEAD~1)   # or origin/main, or the commit before your task started
HEAD_SHA=$(git rev-parse HEAD)
```

### 2. Decide which reviewer to use

- **`code-reviewer` agent (bundled)** — preferred when your platform supports Task dispatch with `subagent_type: code-reviewer`. The agent already knows the review protocol; you just supply the parameters.
- **General-purpose subagent with the prompt template** — when the bundled agent isn't available. Use the template at `code-reviewer.md` next to this file and substitute the placeholders.

### 3. Provide exactly four parameters

| Placeholder | Meaning |
|-------------|---------|
| `DESCRIPTION` | One- or two-sentence summary of what you built |
| `PLAN_OR_REQUIREMENTS` | Path to the plan file or task text the work was supposed to fulfill |
| `BASE_SHA` | Commit SHA before the work started |
| `HEAD_SHA` | Commit SHA at the end of the work |

The reviewer reads the diff between `BASE_SHA` and `HEAD_SHA` directly; do not paste the diff into the prompt.

### 4. Act on the response

The reviewer returns Strengths, Issues categorized by severity (Critical / Important / Minor), Recommendations, and an Assessment.

- **Critical** — fix before doing anything else.
- **Important** — fix before proceeding to the next task or merging.
- **Minor** — note them; fix if time permits.
- **Recommendations** — advisory; consider but don't block.

If the reviewer is wrong, push back with technical reasoning. See `:receiving-code-review` for the discipline of evaluating feedback.

## Worked example

Just finished Task 2 ("Add verification function"). Now request a review before continuing.

```
BASE_SHA=$(git log --oneline | grep "Task 1" | head -1 | awk '{print $1}')
HEAD_SHA=$(git rev-parse HEAD)

[Dispatch code-reviewer agent with:]
  DESCRIPTION: Added verifyIndex() and repairIndex() with four issue types.
  PLAN_OR_REQUIREMENTS: Task 2 from .planning/plans/2026-05-06-deployment.md
  BASE_SHA: a7981ec
  HEAD_SHA: 3df7661

[Reviewer returns:]
  Strengths: clean separation, real (non-mock) tests
  Issues:
    Important — missing progress indicators for long operations
    Minor — magic number 100 for the reporting interval
  Assessment: ready after the Important issue is addressed.

[Apply the Important fix; re-run tests; proceed to Task 3.]
```

## Workflow integration

| Caller | Cadence |
|--------|---------|
| `:subagent-driven-development` | After each task; the spec reviewer runs first, then this skill runs the code-quality reviewer |
| `:executing-plans` | After each task or at natural checkpoints |
| `/ship` | Before opening a PR or merging |
| ad hoc | Whenever you want a second opinion |

## Things to avoid

- **Skipping review because "the change is small".** Small changes hide in plain sight; a reviewer often catches what familiarity makes invisible.
- **Ignoring Critical or Important issues.** The categories exist for a reason. Pushing back is fine; ignoring isn't.
- **Arguing with the reviewer reflexively.** Read the issue, check the code, decide. If the reviewer is wrong, push back with the specific evidence (test output, file/line that contradicts the claim).
- **Asking for review after the change is already merged.** Review's value is highest before integration.

## When to push back on review feedback

Push back when:

- The suggestion would break existing functionality (and you can show the test or behavior that proves it).
- The reviewer is missing context you have (e.g., a constraint that's documented elsewhere).
- The suggestion violates YAGNI (the feature isn't actually used).
- The reviewer's preference is plausible but not better — taste, not correctness.

How to push back, in this order:

1. State the reviewer's concern in your own words to confirm you understood it.
2. Provide the specific evidence (file/line, test output, doc reference).
3. Propose what you'll do instead, or ask the reviewer to confirm before you change.

If the disagreement is about architecture, escalate to the user rather than arguing it out with the reviewer.

## Where this skill sits

| Aspect | Detail |
|--------|--------|
| Direct skill call | `:requesting-code-review` |
| Default reviewer | `code-reviewer` agent at `agents/code-reviewer.md` |
| Prompt template | `code-reviewer.md` next to this file (used when the agent isn't available) |
| Used by | `:subagent-driven-development` (per-task quality review), `:executing-plans` (checkpoint review), `/ship` (pre-merge review) |
| Hands off to | `:receiving-code-review` for evaluating the reviewer's output |
