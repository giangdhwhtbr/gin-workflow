---
name: progress
description: Report execution status for all active beads.
---

# /progress Command

Show the current status of all tracked work items (beads) and the orchestrator's state.

## Instructions

1. Run `bd list` and `bd ready` to retrieve the latest status of all tasks.
2. If using `.planning/orchestration-state.json` for agent/worker tracking, map the workers to the active beads.
3. Format the progress as a clear table or graph, e.g.:
   - **Complete**: Track 1, Track 2
   - **Active**: Track 3 (Subagent: worker-3)
   - **Pending**: Track 4
4. Report any failures or blocks clearly based on the dependency graph.
