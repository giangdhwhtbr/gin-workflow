---
name: finishing-a-development-branch
description: Best practices for merging work, cleaning up worktrees, and preparing the branch for final deployment/shipping.
---

# Finishing a Development Branch Skill

This skill explains how to cleanly finalize a branch, clean up temporary resources, and merge changes.

## Cleanup & Shippable State

1. Follow [docs/verification-and-handoff-workflow.md](file://../../../../docs/verification-and-handoff-workflow.md) before treating work as shippable.
2. **Review Diff**: Generate and inspect a clean diff of changes against the baseline branch when branch integration is in scope.
3. **Merge**: Merge the integration/development branch into the target deployment branch using the `merge-integration.sh "<track-branch>" "<integration-branch>"` script only when the active instructions authorize that workflow.
4. **Teardown**: Discover active track worktrees from the known execution context and `.planning/worktrees/`, then remove them using the `worktree-cleanup.sh "<track-id>"` script. Treat this discovery data as local cleanup metadata, not durable workflow state.
5. **Lifecycle Rule**: Branch and worktree cleanup do not replace Beads-based verification, handoff, or closure; they are implementation cleanup steps only.
