---
name: beads-status
description: Guidance for reporting execution status of tracked work items (beads) and tracks.
---

# Beads Status Skill

This skill renders a per-track status summary of the currently tracked work items. It reads state exclusively from the `bd` CLI — never parse `.planning/beads/` JSON files by hand.

## Execution Rules

1. **Gather state from the `bd` CLI** — run, in order, until you have enough context:
   - `bd list` — enumerate all known beads/tracks and their current status.
   - `bd ready` — list beads whose dependencies are satisfied and that are ready to start.
   - `bd status` — overall queue/progress summary (counts by state).
   - `bd show <id>` — for any specific track the user asks about, to get its full metadata (description, dependencies, assigned worker, acceptance criteria).
2. **Do not read `.planning/beads/` JSON directly.** The `bd` CLI is the source of truth; manual file parsing can drift out of sync with it. If `bd` is unavailable or errors, report that to the user rather than falling back to file parsing.
3. **Render a per-track summary** grouped by state:
   - **Pending** — not yet started (open, dependencies may be unresolved).
   - **Active** — in progress (`in_progress` / claimed by a worker).
   - **Complete** — closed/finished successfully.
   - **Failed** — closed but not passing acceptance, or marked blocked/failed.
   For each track show its id/title, current status, and (if relevant) the assigned worker or blocking dependency.
4. **Keep it read-only.** This skill only reports; it never mutates bead state. To change status, use the `bead-worker` or `executing-plans` skills.
