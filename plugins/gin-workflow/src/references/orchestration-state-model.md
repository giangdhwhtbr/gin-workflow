# Orchestration State Model

This document defines the canonical ownership model for orchestration state in `gin-workflow`.

If any command, skill, or helper text conflicts with this document, this document wins.

## Purpose

The workflow must distinguish clearly between:

- durable task state
- durable planning input
- disposable runtime metadata

The system is correct only when each category has one owner.

The generated effective configuration is the sole lifecycle configuration input. It selects capabilities and artifacts; it does not replace Beads durable state, plan-owned scope, or runtime evidence.

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

Plan files are durable project artifacts, but they are not the source of truth for runtime status transitions.

### Review ledger owns findings and approval evidence

Review ledger under `.planning/<bead-id>/review.json` owns:
- findings history and triage statuses (disputed, deferred, fixed)
- lease status and concurrency control
- active approval snapshot and verification evidence

It is the authoritative log for audit history.

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
| What files are in scope for a track? | Plan file |
| What validation was intended? | Plan file |
| Which worktree path belongs to a track? | Derived runtime metadata |
| Which branch was used for a worker? | Derived runtime metadata |
| Is the task complete? | Beads |
| What findings exist and what are their statuses? | Review Ledger |
| Is there an active lease and who holds it? | Review Ledger |
| What is the approved source tree snapshot? | Review Ledger |

## Effective Configuration And Evidence

The effective configuration selects artifact names and capability providers only. Artifact resolution never moves or infers plans, Beads data, worktrees, knowledge stores, review ledgers, or evidence. Runtime manifests, events, worker results, and evidence indexes are supplemental records: they may support verification and audit, but never replace durable task state or approved plan scope. See [setup system](setup-system.md), [provider contracts](capability-provider-contracts.md), and [context and evidence policy](context-and-evidence-policy.md).

## Relationship To Other Docs

- [agent task lifecycle](agent-task-lifecycle.md) defines phase boundaries.
- This document defines state ownership inside those phases.
- `verification-and-handoff-workflow.md` defines how verification, handoff, and closure update the durable state correctly.
