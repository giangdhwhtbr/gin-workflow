---
name: requesting-code-review
description: How and when to dispatch the code-reviewer specialist agent to review a change, and the structured output to expect.
---

# Requesting Code Review Skill

This skill defines when to request a code review, what context to provide to the reviewer, and the structured findings you should get back. It works with the existing `code-reviewer` agent definition and is the quality gate called before finishing a development branch.

## When to Request a Review

Dispatch the code-reviewer agent at these points:

1. **Before resolving a plan**: Once implementation is complete and verification (verification-before-completion) has passed, request a review of the full diff against the plan's acceptance criteria.
2. **After a non-trivial change**: Any change that touches shared modules, introduces new control flow, or alters data handling deserves a review even if it is not yet complete.
3. **On request**: When the orchestrator or user explicitly asks for a review of a branch or diff.

Do not request a review for trivial changes (typo fixes, comment-only edits, frontmatter updates) where the verification-before-completion gate already covers correctness.

## How to Dispatch the Code-Reviewer Agent

Invoke the existing `code-reviewer` agent (see `agent-plugin/src/agents/code-reviewer.md`) as a subagent. Provide it with the following context — it cannot infer missing context:

1. **The diff**: The exact diff to review, scoped to the change under review. For a branch, diff against the merge base (`git diff <merge-base>...HEAD`), not the working tree.
2. **The plan**: The plan file path or a summary of the plan being implemented, so the reviewer can judge whether the change matches intent — not just whether the code runs.
3. **Acceptance criteria**: The specific acceptance criteria from the plan. The reviewer confirms each criterion is met by the diff, not just that the code is well-formed.
4. **In-scope files**: The list of files the track declared as in scope, so the reviewer can flag out-of-scope edits.
5. **Known constraints**: Any non-obvious constraints the reviewer should respect (performance budgets, compatibility targets, conventions to follow). State these explicitly; do not assume the reviewer shares the plan's context.

## Invocation

On Claude Code, spawn the `code-reviewer` agent via the Agent tool with the above context embedded in the prompt. On Antigravity CLI, use `invoke_subagent` with the same prompt. See the dispatching-parallel-agents skill for the mechanics of spawning a subagent; the review is typically a single subagent, not a parallel fan-out.

## Expected Structured Output

The code-reviewer agent returns findings as a ranked list. Each finding contains:

- **Severity**: ranked most-severe first (e.g. `critical` / `high` / `medium` / `low`, or the agent's own severity scale). The most actionable and dangerous findings come first.
- **Summary**: A one-sentence statement of the defect.
- **Failure scenario**: A concrete input or state that triggers the wrong output or crash — not a vague concern. If no concrete scenario exists, the finding should be downranked or omitted.
- **Location**: The file and line(s) the finding anchors to.
- **Verdict** (when a verify pass ran): `CONFIRMED` (the failure reproduces) or `PLAUSIBLE` (the finding stands on inspection but was not reproduced).

If no findings survive verification, the reviewer returns an empty list. Treat an empty list as a green light, not as a skipped check.

## After the Review

Hand the returned findings to the receiving-code-review skill for triage. Do not attempt to fix findings inline during the review dispatch — collect the full list first, then triage as a separate step. Once findings are resolved and re-verified, proceed to finishing-a-development-branch.
