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
- any waived gates, including stated reasons and follow-up task IDs
- any blocked items or residual risks
- the bead status at handoff time
- proposed next commands when useful

Recommended phrasing:

- changed files
- validation
- waived gates (with reasons and follow-up task IDs)
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

Track Bead vs Deliverable Bead Closure:

- **Track Beads (Work Units)**: When technical acceptance criteria, tests, and code review pass, close the track bead (`task.close` / `bd close`) immediately to unblock downstream dependent tracks in the Beads graph. Closing a track bead does NOT require git commit/push, PR creation, or base-branch merge.
- **Parent Bead (Deliverable)**: Only the parent deliverable bead remains open until full integration, verification, and human-confirmed merge occur.

If any required close-out conditions are false:

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

- commit and push freely on a feature branch or isolated worktree branch, including the commits created by `review-ledger.py checkpoint`
- never commit directly to `main`/`master` (or the configured base branch)
- creating a Pull Request, merging into the base branch, and force-pushing require explicit user approval

Completion and handoff do not imply PR or merge authority.

### Handoff Before PR or Merge Approval

When a worker completes technical implementation and verification for a track bead, it commits and pushes the feature branch, closes the track bead in Beads (to unblock downstream tracks), and then:

1. **Strict Prohibition on "Waiting for PR Merge"**:
   Agents are strictly forbidden from reporting, claiming, or recording a state of "waiting for PR merge" ("chờ PR merge", "awaiting PR merge") when no Pull Request exists with a verifiable PR link. Never fabricate or assume PR status without an actual PR link.

2. **Mandatory User Decision Menu**:
   The worker MUST stop at handoff and present exactly two explicit options to the user:
   - **Option 1**: Request approval to create a PR from the pushed feature branch (`Xin lệnh tạo PR từ nhánh feature đã push`).
   - **Option 2**: Keep the pushed feature branch and proceed to the next track using the generated artifacts (`Giữ nhánh feature đã push và tiếp tục chuyển sang track tiếp theo sử dụng artifact vừa sinh`).

## Minimal Handoff Template

Use this shape when ending work:

```md
Changed:
- ...

Validation:
- Ran: ...
- Not run: ...

Waived gates:
- None (or e.g. verification_passed - reason: ... [follow-up task: gin-workflow-xyz])

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

## Integrity checks before closure

For acceptance-sensitive work, the handoff names the workflow/attempt/task
identity and the repository snapshot evidence used by tests, review, and
verification. Checkpoint evidence must include non-empty scope/tree hashes and a
checkpoint ref; review evidence must be terminal approval followed by passed
verification. The evidence capability rejects stale, cross-attempt, or
non-authoritative records.

Durable task mutation is capability-owned. Run the relevant `progress` or
`workflow` route and task-tracking preflight before mutation; do not infer closure
from a deleted worktree, a plan checkbox, a cache file, or an empty hash. Protected
data movement requires its matching approval and audit event.
