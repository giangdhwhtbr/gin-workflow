---
name: requesting-code-review
description: Extends superpowers:requesting-code-review with code-reviewer subagent integration, expected structured findings, and completion rules.
---

# Requesting Code Review Skill

This skill extends `superpowers:requesting-code-review` for the `gin-workflow` plugin.

## Base Skill

When `superpowers:requesting-code-review` is available, use it first as the base contract. Then apply the Gin Workflow overlay below.

If `superpowers:requesting-code-review` is unavailable, continue with this skill's self-contained rules and say that the Superpowers base skill could not be loaded.

## Gin Workflow Overlay

Gin Workflow keeps the Superpowers standards, with these plugin-specific overrides:

1. **When to Request a Review**:
   Dispatch the `code-reviewer` agent before resolving a plan, after substantial non-trivial changes, or on user request.
2. **Context Delivery**:
   Invoke the `code-reviewer` subagent (defined in `agents/code-reviewer.md`) and provide:
   - **The diff** — `git diff <merge-base>...HEAD`.
   - **The plan** — plan path/summary.
   - **Acceptance criteria** — specific criteria to check.
   - **In-scope files** — files declared in plan.
   - **Known constraints** — any specific codebase constraints.
3. **Execution**:
   Use `invoke_subagent` (on Antigravity CLI) or the Agent tool (on Claude Code) as described in `dispatching-parallel-agents`.
4. **Expected Structured Output**:
   The `code-reviewer` agent returns ranked findings containing: Severity, Summary, Failure scenario, Location, and Verdict.
5. **Post-Review Process**:
   Pass findings to the `receiving-code-review` skill.
