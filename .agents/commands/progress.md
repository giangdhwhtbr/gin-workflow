---
name: progress
description: Report the status of tracked work items, active execution context, and next-task recommendations.
---

# /progress Command

Show the current status of tracked work items (beads), any active execution context, and recommended next tasks.

## Instructions

1. Use the `progress` skill (see [progress/SKILL.md](file://../skills/progress/SKILL.md)) to gather, format, and render status and recommendations.
2. The skill reads state exclusively from the `bd` CLI — do not parse local planning or runtime JSON manually.
3. Present a per-track summary (Pending / Active / Complete / Failed) so the user can see at a glance where work stands.
4. Include a "Next Task Recommendations" section showing the next logical tasks to execute, utilizing hierarchical dependency-aware logic.
5. Treat Beads as the authoritative source for task state, readiness, and dependency status.
6. Present any temporary worker or worktree metadata only as supplemental runtime context and label it as derived runtime metadata.
