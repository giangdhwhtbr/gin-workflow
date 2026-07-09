# Agent Task Lifecycle

This document defines the canonical lifecycle for agent work in `gin-workflow`.

## Purpose

The lifecycle exists to make one thing unambiguous:

- Beads owns durable task state.
- Plan files own approved task decomposition.
- Worktrees, branches, and temporary orchestration artifacts are implementation details.

If any command, skill, or helper document conflicts with this document, this lifecycle spec wins.

State ownership within this lifecycle is defined in `docs/orchestration-state-model.md`.

## Lifecycle

The required lifecycle is:

1. Discover
2. Claim
3. Plan
4. Implement
5. Verify
6. Handoff
7. Close

Not every task needs every optional mechanism, but every task must pass through these phase boundaries in order.

## Phase Definitions

### 1. Discover

Goal:
Identify the next appropriate unit of work and recover the current project context.

Required actions:

- Run `bd prime` when Beads context is missing or stale.
- Use `bd ready`, `bd list --status=open`, or `bv --robot-triage` to identify candidate work.
- Read the selected issue before mutation.

Allowed artifacts:

- Beads issue metadata
- Existing plans in `.planning/plans/`
- Existing docs and code context

Source of truth:

- Beads for task availability and dependency state

Exit criteria:

- A specific bead has been selected for work.

### 2. Claim

Goal:
Atomically take responsibility for a bead before implementation starts.

Required actions:

- Claim the bead with `bd update <id> --claim` or the equivalent status mutation that establishes ownership.

Source of truth:

- Beads for ownership and in-progress state

Status transition:

- `open -> in_progress`

Exit criteria:

- The bead shows an active owner and in-progress status.

### 3. Plan

Goal:
Define or confirm the approved implementation shape before editing.

Required actions:

- For multi-step or ambiguous work, write or update a plan in `.planning/plans/`.
- Compare approaches and record the selected approach when the work is non-trivial.
- Ensure acceptance criteria and verification steps are explicit.

Allowed artifacts:

- `.planning/plans/*.md`
- Design or audit docs under `docs/`

Source of truth:

- Beads remains the source of truth for task status.
- Plan files are the source of truth for approved decomposition, file scope, and validation intent.

Exit criteria:

- The task has either:
  - an approved plan, or
  - a documented reason why a separate plan is unnecessary.

### 4. Implement

Goal:
Make the scoped changes needed to satisfy the bead.

Required actions:

- Read the bead and any relevant plan before editing.
- Keep changes within approved scope.
- If the task requires subagents or parallel tracks, create or coordinate child beads before dispatch.
- Use worktrees only when isolation is needed.

Allowed artifacts:

- Code and docs in scope
- Worktrees under `.planning/worktrees/` when explicitly used

Source of truth:

- Beads for task status, assignment, dependencies, and blockers
- Plan files for declared scope and track decomposition

Not allowed:

- Using `.planning/orchestration-state.json` or plan-file checkboxes as the authoritative execution state
- Treating worktree presence as proof of task progress

Blocked-work handling:

- If blocked by missing context, dependency, or external state, update the bead with the blocking reason instead of inventing local status files.
- Create follow-up beads for newly discovered durable work.
- Do not silently continue on out-of-scope work; either expand the plan intentionally or create follow-up work.

Exit criteria:

- The implementation is complete enough for verification, or the bead is explicitly marked blocked with a clear reason.

### 5. Verify

Goal:
Demonstrate that the work satisfies acceptance criteria and does not regress known behavior.

Required actions:

- Run the relevant tests, checks, or manual validation steps for the bead.
- Record failures honestly and fix them before claiming completion.

Source of truth:

- Verification evidence lives in command output and handoff notes.
- Beads remains the source of truth for whether the task is still active or ready to close.

Exit criteria:

- Verification passed, or the task remains in progress/blocked with failures documented.

### 6. Handoff

Goal:
Leave a durable, reviewable summary of what changed and what remains.

Required actions:

- Summarize changes, verification, and any follow-up work.
- Run `git status`.
- If code or docs changed, report the changed files and validation status.
- If more work is needed, create or update beads before ending the session.

Session-close behavior:

- Follow the repo session-close protocol from `AGENTS.md`.
- Do not commit or push unless explicitly authorized by the active instructions or the user.
- Closing the bead happens after the work and handoff evidence are complete.

Source of truth:

- Beads for issue outcome
- Git working tree for file-change state

Exit criteria:

- Another agent or human can understand current status without reconstructing hidden context.

### 7. Close

Goal:
Mark the bead complete only after implementation, verification, and handoff are done.

Required actions:

- Close the bead with `bd close <id>` once acceptance criteria are met.

Status transition:

- `in_progress -> closed`

Source of truth:

- Beads for final completion state

Exit criteria:

- The bead is closed and any remaining work has been captured separately.

## Ownership Model

### Beads owns

- task identity
- priority
- dependencies
- claim/assignee state
- in-progress versus closed state
- blocked reasons and follow-up work
- final closure

### Plan files own

- approved approach
- task decomposition
- declared file scope
- validation intent
- model guidance metadata

### Worktrees and runtime artifacts own

- temporary isolation details only

They must be reconstructible or disposable. They are not authoritative workflow state.

See `docs/orchestration-state-model.md` for the detailed ownership rules and reporting expectations.

## Required Commands By Phase

| Phase | Primary commands |
| --- | --- |
| Discover | `bd prime`, `bd ready`, `bd list --status=open`, `bv --robot-triage`, `bd show <id>` |
| Claim | `bd update <id> --claim` |
| Plan | `/plan`, plan authoring in `.planning/plans/`, `bd show <id>` |
| Implement | task-specific edit/test commands, optional worktree scripts, optional subagent dispatch |
| Verify | `/verify`, project-specific test/build/typecheck commands |
| Handoff | `git status`, `bd update <id> --notes ...`, optional follow-up `bd create ...` |
| Close | `bd close <id>` |

## Subagents

Subagents are optional and should be introduced during Implement, not as a parallel status system.

Rules:

- Parent coordination still lives in Beads.
- If work is split into durable tracks, represent that split in beads.
- Temporary worker identity can appear in notes or disposable runtime state, but bead status remains authoritative.

## Persistent Memory

Use `bd remember` for durable project memory that should survive sessions and handoffs.

Do not use:

- ad hoc memory files
- plan files as a memory log
- runtime JSON as a substitute for durable knowledge

## Model Guidance

Model selection guidance belongs in plan metadata, not in Beads state.

Rules:

- Use abstract classes only: `high_reasoning`, `standard_impl`, `cheap_simple`
- Assume `standard_impl` when no class is specified
- Prefer `high_reasoning` for brainstorming, design, and review
- Default planning to `standard_impl` once the design is settled
- Escalate planning to `high_reasoning` only when sequencing, dependency resolution, or execution boundaries remain materially unclear
- Treat model guidance as advisory planning context, not as workflow status or hard enforcement

## Blocked Work

A blocked task must be visible in Beads.

Required behavior:

- record the blocker in bead notes or status metadata
- create dependency or follow-up beads when the blocker is durable
- stop claiming forward progress until the blocker is resolved

## Session Close Checklist

Before ending a work session:

1. Create follow-up beads for remaining durable work.
2. Run relevant quality gates when files changed.
3. Run `git status`.
4. Summarize changes, verification, and remaining risks.
5. Close the bead only if the acceptance criteria are actually complete.

## Implications For Workflow Docs

Any command or skill should follow these rules:

- never describe `.planning/orchestration-state.json` as the durable task state source
- never allow plan files to replace Beads for task status transitions
- describe worktrees as optional isolation, not status authority
- treat handoff and closure as Beads-first lifecycle steps
