---
name: ship
description: Complete and merge the development branch.
---

# /ship Command

Complete the development branch, merge into the main branch, and clean up temporary worktrees.

## Instructions

1. Use the `finishing-a-development-branch` skill.
2. Follow [docs/verification-and-handoff-workflow.md](file://../../../../docs/verification-and-handoff-workflow.md) before treating the task as complete.
3. Run the `merge-integration.sh "<track-branch>" "<integration-branch>"` script only when branch integration is actually in scope and current instructions authorize it.
4. Discover active worktrees from the known plan/run context and the `.planning/worktrees/` directory when worktree isolation was used.
5. Treat worktrees as implementation artifacts only; Beads remains the source of truth for whether work is still active or complete.
6. Clean up all worktrees created for this plan by running the `worktree-cleanup.sh "<track-id>"` script for each active track.
