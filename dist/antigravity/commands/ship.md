---
name: ship
description: Complete and merge the development branch.
---

# /ship Command

Complete the development branch, merge into the main branch, and clean up temporary worktrees.

## Instructions

1. Use the `finishing-a-development-branch` skill.
2. Run the `merge-integration.sh "<track-branch>" "<integration-branch>"` script to merge the active development/track branch into the target integration/deployment branch (default is configured via `/orchestrate --integration-branch`).
3. Discover any active worktrees by reading `.planning/worktrees/` or checking `.planning/orchestration-state.json`.
4. Clean up all worktrees created for this plan by running the `worktree-cleanup.sh "<track-id>"` script for each active track.
