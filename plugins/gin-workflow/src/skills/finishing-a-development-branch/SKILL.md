---
name: finishing-a-development-branch
description: Extends superpowers:finishing-a-development-branch with teardown safety and bundled verification-and-handoff workflow integration.
---

# Finishing a Development Branch Skill

This skill extends `superpowers:finishing-a-development-branch` for the `gin-workflow` plugin.

## Base Skill

When `superpowers:finishing-a-development-branch` is available, use it first as the base contract. Then apply the Gin Workflow overlay below.

If `superpowers:finishing-a-development-branch` is unavailable, continue with this skill's self-contained rules and say that the Superpowers base skill could not be loaded.

## Gin Workflow Overlay

Gin Workflow keeps the Superpowers standards, with these plugin-specific overrides:

1. Follow [verification-and-handoff-workflow.md](file://../../references/verification-and-handoff-workflow.md) before treating work as shippable.
2. **Review Diff**: Generate and inspect a clean diff of changes against the baseline branch when branch integration is in scope.
3. **Merge**: Merge the integration/development branch into the target deployment branch using the `merge-integration.sh "<track-branch>" "<integration-branch>"` script only when the active instructions authorize that workflow.
4. **Teardown**: Discover active track worktrees from the known execution context and `.planning/worktrees/`, then remove them using the `worktree-cleanup.sh "<track-id>"` script. Treat this discovery data as local cleanup metadata, not durable workflow state.
5. **Lifecycle Rule**: Branch and worktree cleanup do not replace Beads-based verification, handoff, or closure; they are implementation cleanup steps only.
