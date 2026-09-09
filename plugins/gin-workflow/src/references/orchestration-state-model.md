# Orchestration State Model

This document defines the canonical ownership model for orchestration state in `gin-workflow`.

If any command, skill, or helper text conflicts with this document, this document wins.

## Purpose

The workflow must distinguish clearly between:

- durable task state
- durable planning input
- disposable runtime metadata

The system is correct only when each category has one owner.

`.agent-workflow/generated/effective-config.yaml` is the sole lifecycle configuration input. It resolves setup inputs and selects logical capabilities; it does not own task state, approved plan content, or runtime outcomes.

## Canonical Ownership

### Beads owns durable execution state

Beads is the source of truth for:

- task identity
- title and description
- priority
- status (`open`, `in_progress`, `closed`, blocked notes)
- claim and assignee state
- dependencies between tracks
- durable blockers
- durable follow-up work
- final completion state

This means an agent answering "what is active, blocked, ready, or complete?" starts with the task-tracking capability, not local runtime files.

### Plan files own approved decomposition

Plan files under `.planning/plans/` own:

- approved task and track breakdown
- declared file scope
- validation intent
- ordering rationale
- model guidance metadata

Plan files are durable project artifacts, but they are not the source of truth for runtime status transitions. For standalone or pre-existing beads where a separate plan was waived as unnecessary, the task description and acceptance criteria in Beads own declared file scope and validation intent.

### Review ledger owns findings and approval evidence

The review ledger owns findings history and triage status, lease/concurrency state,
active approval snapshots, and review verification evidence. It is the authoritative
audit log for review history; it does not own Beads task status or approved plan scope.

### Workflow event store owns audit records and gate waivers

The `WorkflowEventStore` owns append-only audit events, including recorded approvals
(`approval.recorded`), blocker clearing (`blocker.cleared`), and gate waivers
(`gate.waived`). `gate.waived` events record who bypassed a gate, which gate class applied,
the stated reason, scope hash, and optional follow-up task ID. Gate waivers allow stage
routing past unmet process or safety gates, but they are append-only audit records owned
by the event store; they never substitute for Beads task identity, priority, dependencies,
or closure status.


### Runtime metadata is local and disposable

Local orchestration metadata may exist for convenience, such as:

- track-id to bead-id mappings
- worker identifiers
- branch names
- worktree paths
- temporary execution caches

That metadata is allowed only if it is:

- reconstructible from Beads plus the approved plan, or
- safely disposable without losing durable workflow state

It must never become the authoritative answer for whether work is pending, active, blocked, or complete.

## Dependency Mapping

When a plan is decomposed into multiple tracks:

1. Create one durable task per durable track through the task-tracking capability.
2. Mirror plan dependencies through that capability.
3. Use durable task dependency state to decide readiness and blocking.

Plan order can guide creation, but readiness comes from Beads after dependencies are recorded.

## Parent Bead (Deliverable) vs Track Beads (Work Units)

When orchestrating a plan into Beads tasks, the workflow enforces a strict distinction between the parent deliverable and individual work units:

- **Parent Bead (Deliverable / Feature / Epic)**:
  - Represents the complete end-to-end feature or release deliverable.
  - Rules requiring human confirmation or release-level merge gates (e.g. "No commit/push authorized. Code tasks remain open until human-confirmed merge") belong exclusively to the Parent Bead.
  - The Parent Bead remains open until all tracks complete, integration/verification succeeds, and final human confirmation or merge takes place.

- **Track Beads (Work Units / Sub-beads)**:
  - Represent concrete technical execution units (e.g. T1, T2, T3).
  - The orchestrator MUST NEVER copy parent-level merge-hold rules or commit prohibitions into child track bead descriptions or acceptance criteria.
  - Acceptance criteria for track beads are strictly technical: code implemented within approved scope, tests passing, and code review approved.
  - When technical validation and code review pass, the track bead MUST be closed (`task.close` / `bd close`) to unlock downstream tracks in the Beads graph.
  - Closing a track bead does not require a git commit/push or merge of the overall deliverable.

## Progress And Status Reporting

### `/progress`

`/progress` is the consolidated, Beads-first execution and status summary.

It should report:

- bead status grouped by workflow state (Pending, Active, Complete, Failed)
- dependency-driven readiness and blocking relationships
- next-task recommendations (using hierarchical dependency-aware logic)
- optional/supplemental runtime context such as worker names or worktree paths (must be labeled as derived runtime metadata)

It must read durable state through the task-tracking capability and must not depend on local planning runtime JSON files.

## Operational Rules

- Never copy deliverable-level merge-hold rules ("remain open until human-confirmed merge") into child track beads.
- Never keep a completed track bead open waiting for parent deliverable merge when downstream tasks depend on it.
- Never describe `.planning/orchestration-state.json` as the durable task-state source.
- Never use plan checkboxes or worktree existence as proof of execution progress.
- Never allow a local runtime file to replace the task-tracking capability.
- If local runtime metadata becomes stale, repair or discard it; do not treat it as canonical.

## Acceptable Derived State

Examples of acceptable derived or session-local state:

- a temporary map from plan track labels to bead ids
- a cached list of active worker sessions
- worktree metadata used only for cleanup
- branch names used only for merge automation

Examples of unacceptable derived state:

- a local file marked "track complete" while the bead is still open
- a progress command that trusts a runtime cache over the task-tracking capability
- a cleanup step that infers task closure from worktree deletion

## Decision Table

| Question | Canonical source |
| --- | --- |
| What work exists? | Beads |
| What depends on what? | Beads |
| What is ready now? | Beads |
| What files are in scope for a track? | Plan file (or task metadata for standalone work) |
| What validation was intended? | Plan file (or task metadata for standalone work) |
| Which worktree path belongs to a track? | Derived runtime metadata |
| Which branch was used for a worker? | Derived runtime metadata |
| Who waived a gate and why? | Event store (`gate.waived` events) |
| Is the task complete? | Beads |


## Effective Configuration And Evidence

The effective configuration selects artifact names and capability providers only. Artifact resolution never moves or infers plans, Beads data, worktrees, knowledge stores, review ledgers, or evidence. Runtime manifests, events, worker results, and evidence indexes are supplemental records: they may support verification and audit, but never replace durable task state or approved plan scope. Acceptance identity and repository snapshots join those records without changing ownership. See [setup-system.md](setup-system.md), [capability-provider-contracts.md](capability-provider-contracts.md), and [context-and-evidence-policy.md](context-and-evidence-policy.md).

## Relationship To Other Docs

- `docs/agent-task-lifecycle.md` defines phase boundaries.
- This document defines state ownership inside those phases.
- `docs/verification-and-handoff-workflow.md` defines how verification, handoff, and closure update the durable state correctly.
