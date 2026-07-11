---
name: progress
description: Guidance for reporting execution status of tracked work items (beads), tracks, and next-task recommendations.
---

# Progress Skill

This skill renders a per-track status summary and next-task recommendations of the currently tracked work items. It reads state exclusively from the `bd` CLI and follows [orchestration-state-model.md](file://../../references/orchestration-state-model.md) — never parse local planning or runtime JSON files by hand.

## Execution Rules

1. **Gather state from the `bd` CLI** — run, in order, until you have enough context:
   - `bd list --all` — enumerate all known beads/tracks (including closed ones) and their current status.
   - `bd ready` — list beads whose dependencies are satisfied and that are ready to start.
   - `bd status` — overall queue/progress summary (counts by state).
   - `bd show <id>` — for any specific track the user asks about or to investigate dependencies.
2. **Do not read local planning or runtime JSON directly.** The `bd` CLI is the source of truth.
3. **Render a per-track summary** grouped by state:
   - **Pending** — not yet started (open, dependencies may be unresolved).
   - **Active** — in progress (`in_progress` / claimed by a worker).
   - **Complete** — closed/finished successfully.
   - **Failed** — closed but not passing acceptance, or marked blocked/failed.
   For each track show its id/title, current status, and (if relevant) the assigned worker or blocking dependency.
4. **Output Next-Task Recommendations**:
   Analyze the gathered Bead states to provide a "Next Task Recommendations" section:
   - **Check Active Tasks & Dependencies first**: Look for any tasks in `in_progress` status.
     - For each active task, check if it has unresolved child issues or dependencies.
     - If it does, and any of those child/dependency issues are in `open` state and are ready to work (appear in `bd ready`), recommend them first to progress the active parent task.
       - *Format*: `[Ready Child] <child_id>: <title> (required to progress active parent <parent_id>)`
     - If the active task has no unresolved dependencies/children, recommend continuing work on it.
       - *Format*: `[Active] <id>: <title> (Continue current work)`
   - **Check Unclaimed Ready Tasks**: If there are no active tasks, or after listing active tasks/dependencies:
     - List the top `ready` tasks (from `bd ready`) that are not already claimed or in progress, sorted by priority (P0 to P4).
       - *Format*: `[Ready] <id>: <title> (Priority: <priority>)`
   - **Check Blocked Tasks / Root Blockers**: If all open tasks are blocked (no active or ready tasks):
     - Trace the blocker chain to identify root blockers (tasks that block others but are themselves waiting on completed/closed tasks or are the root of a block).
       - *Format*: `[Root Blocker] <id>: <title> (unblocks <dependent_id>)`
   - **No Tasks / Empty Queue**: If all tasks are completed:
     - Output a clear message suggesting the next workflow step (e.g., run `/plan` to define new work, or ship the current branch).
5. **Keep runtime context supplemental.** If worker names, branch names, or worktree paths are shown, label them as derived runtime metadata rather than authoritative task state.
6. **Keep it read-only.** This skill only reports; it never mutates bead state.
