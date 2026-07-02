---
name: using-claude-draft
description: Draft-mode workflow — defer tool side-effects until the user approves the plan or diff, then execute.
---

# Using Draft Skill

This skill describes the approval-gated execution mode commonly called "draft mode": collect the work to be done into a reviewable plan or diff, defer all tool side-effects until the user approves, then execute the approved changes.

## Core Idea

In draft mode the assistant performs read-only investigation and produces a concrete proposal — a plan, a diff, or an ordered change list — without mutating the filesystem, running shell commands that change state, or otherwise taking side-effecting actions. The user reviews the proposal, requests adjustments or approves it, and only then does execution proceed.

This keeps potentially-destructive changes auditable and reversible up to the moment of approval, and it separates "what should happen" from "make it happen."

## What Counts as a Side Effect

Treat any action that changes state outside the conversation as a side effect to defer:

- File writes, edits, and deletions.
- Shell commands that mutate state (installs, builds, migrations, deploys, `git commit`/`push`, service restarts).
- Any tool call whose effect survives the session.

Read-only actions are always allowed during drafting: reading files, searching, listing, running queries, and any command whose only output is information.

## Workflow

1. **Draft**: Gather context with read-only tools. Produce a concrete proposal — for larger work, a plan following [writing-plans](file://../writing-plans/SKILL.md); for edits, a diff or an ordered list of changes with exact strings/paths.
2. **Review**: Present the proposal to the user. Do not take side-effecting actions while awaiting feedback.
3. **Revise** (as needed): Update the proposal in place based on feedback; still no side effects.
4. **Approve**: The user accepts the proposal.
5. **Execute**: Apply the approved changes — perform the writes, run the commands — and report what happened.

## Platform Behavior Notes

Draft mode is a workflow convention, not a single shared primitive. Behavior differs across platforms; flag platform-specific assumptions inline when describing the mode to users.

- On **Claude Code**, draft mode is typically entered via plan mode (`ExitPlanMode` is the gate that transitions from drafting to execution). Verify the current harness's exact entry/exit mechanism before relying on it.
- On **Antigravity**, the equivalent approval-gated mode may differ — confirm Antigravity's specific UI/command for deferring tool side-effects before assuming parity. Where a behavior below is Claude-specific, it is flagged inline.

## Rules

1. While drafting, do not call side-effecting tools. If a tool is ambiguous, treat it as side-effecting and defer it.
2. The proposal must be concrete enough to execute without further decisions: exact paths, exact replacement strings, exact commands. Vague proposals extend the loop and defeat the purpose.
3. Keep revisions in the proposal — do not partially execute, then revise. The state-changing phase begins only after explicit approval.
4. After approval, execute the approved set faithfully. If execution reveals the proposal was wrong, stop and re-draft rather than silently expanding scope.
5. If the task is purely informational (no changes intended), skip draft mode — there is nothing to gate.

## When to Use Draft Mode

- Multi-file edits or any change that is hard to undo after the fact.
- Changes to running infrastructure, config, or anything covered by repo rules (e.g. "do not modify the running server").
- When the user explicitly asks to plan first, review first, or see a diff before acting.
- On Claude Code, when plan mode is active — the harness enforces the gate. (Verify the Antigravity equivalent before assuming the same enforcement.)

## When to Skip Draft Mode

- Single-step, low-risk edits the user directly requested with full context.
- Pure read-only investigation (no side effects to defer in the first place).
- When the user has already approved a plan authored via [writing-plans](file://../writing-plans/SKILL.md) and asked for direct execution.
