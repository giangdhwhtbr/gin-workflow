---
name: finishing-a-development-branch
description: Best practices for merging work, cleaning up worktrees, and preparing the branch for final deployment/shipping.
---

# Finishing a Development Branch Skill

This skill explains how to cleanly finalize a branch, clean up temporary resources, and merge changes.

## Cleanup & Shippable State

1. **Staged Changes**: Ensure no untracked or uncommitted files remain in the worktree.
2. **Review Diff**: Generate and inspect a clean diff of changes against the baseline branch.
3. **Merge**: Merge the integration/development branch into the target deployment branch using the `merge-integration.sh "<track-branch>" "<integration-branch>"` script.
4. **Teardown**: Discover active track worktrees from the known execution context and `.planning/worktrees/`, then remove them using the `worktree-cleanup.sh "<track-id>"` script.
5. **Lifecycle Rule**: Branch and worktree cleanup do not replace Beads-based handoff and closure; they are implementation cleanup steps only.
