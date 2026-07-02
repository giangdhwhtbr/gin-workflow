---
name: beads-status
description: Report the status of tracked work items and execution tracks.
---

# /beads-status Command

Show the current status of tracked work items (beads) and execution tracks.

## Instructions

1. Use the `beads-status` skill (see [beads-status/SKILL.md](file://../skills/beads-status/SKILL.md)) to gather and render status.
2. The skill reads state exclusively from the `bd` CLI — do not parse `.planning/beads/` JSON manually.
3. Present a per-track summary (pending / active / complete / failed) so the user can see at a glance where work stands.
