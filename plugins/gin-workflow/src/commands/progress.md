---
name: progress
description: Report execution status for all active beads.
---

# /progress Command

Show the current status of tracked work items and any active execution context.

## Instructions

1. Run `bd list` and `bd ready` to retrieve the latest status of all tasks.
2. Treat Beads as the authoritative source for task state.
3. If temporary worker or worktree metadata exists, present it only as supplemental runtime context and not as a competing status source.
4. Format the progress as a clear table or graph, e.g.:
   - **Complete**: Track 1, Track 2
   - **Active**: Track 3 (Subagent: worker-3)
   - **Pending**: Track 4
5. Report any failures or blocks clearly based on the dependency graph.
