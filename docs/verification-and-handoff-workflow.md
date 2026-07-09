# Verification And Handoff Workflow

This document defines the canonical close-out workflow for agent tasks in `gin-workflow`.

It is subordinate to explicit user or orchestrator instructions, but otherwise it is the authoritative operational checklist for verification, handoff, and task closure.

## Goals

- require relevant quality gates when files changed
- keep Beads as the durable source of task outcome
- make handoff non-interactive and reviewable
- preserve the repository's conservative no-commit/no-push default

## When This Workflow Applies

Use this workflow whenever an agent is preparing to claim work is complete, fixed, verified, or ready for handoff.

It applies to:

- code changes
- documentation changes
- workflow/spec changes
- multi-step implementation tasks

## Canonical Close-Out Sequence

The required sequence is:

1. Run relevant quality gates
2. Record Beads notes, blockers, and follow-up work
3. Run `git status`
4. Prepare handoff summary
5. Close the bead only if acceptance criteria and handoff evidence are complete

## Step 1: Run Relevant Quality Gates

If files changed, run the relevant validation for the task.

Examples:

- build or compile commands
- type checks
- unit or integration tests
- linting
- manual verification steps from the plan
- doc-specific review when the task is documentation only

Rules:

- run what is relevant, not a fake universal checklist
- if validation is intentionally not run, say so explicitly in the handoff
- if validation fails, do not claim the task is complete

## Step 2: Record Beads Notes, Blockers, And Follow-Up Work

Before ending the session, ensure Beads reflects the durable state of the task without closing it early.

Required behavior:

- update notes with what changed and what was verified
- record blockers if work cannot complete
- create follow-up beads for remaining durable work

Do not run `bd close` in this step. Final closure belongs to Step 5, after verification, `git status`, and the handoff summary are complete.

Source of truth:

- Beads owns task status, blockers, and closure

## Step 3: Run `git status`

`git status` is mandatory before handoff.

Purpose:

- confirm the actual changed files
- catch unexpected edits
- report whether the worktree is clean or still contains local changes

Rules:

- report changed files in the handoff
- do not hide unrelated modifications if they affect the current result

## Step 4: Prepare Handoff Summary

The handoff must be explicit and non-interactive.

Required handoff contents:

- what changed
- which files changed
- what validation was run
- what validation was not run
- any blocked items or residual risks
- the bead status at handoff time
- proposed next commands when useful

Recommended phrasing:

- changed files
- validation
- beads status
- remaining risks
- next commands

## Step 5: Close The Bead

Close the bead only when:

- the acceptance criteria are satisfied
- relevant verification is complete
- follow-up work has been captured separately
- Beads notes reflect the outcome
- `git status` has been reviewed
- the handoff is complete

If any of those are false:

- leave the bead in progress, or
- update it with a blocker and follow-up state

## Platform-Aware Guidance

This repo supports multiple agent platforms, but the close-out policy is shared.

Shared requirements:

- non-interactive commands only
- Beads-first status updates
- conservative git policy by default

Platform-specific mechanics may differ, but they must not change the required close-out sequence.

## Commit And Push Policy

Default policy:

- do not commit unless explicitly requested or otherwise authorized by current instructions
- do not push unless explicitly requested or otherwise authorized by current instructions

Completion and handoff do not imply commit or push authority.

## Minimal Handoff Template

Use this shape when ending work:

```md
Changed:
- ...

Validation:
- Ran: ...
- Not run: ...

Beads:
- Updated: ...
- Closed: yes|no

Risks / Blockers:
- ...

Next commands:
- ...
```

## Relationship To Other Workflow Docs

- `docs/agent-task-lifecycle.md` defines the phase model
- this document defines the concrete close-out checklist for the `Verify`, `Handoff`, and `Close` phases
- `verification-before-completion` and `finishing-a-development-branch` should defer to this workflow rather than redefine it independently
