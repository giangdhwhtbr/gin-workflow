---
name: using-git-worktrees
description: Extends superpowers:using-git-worktrees with directory layout constraints (.planning/worktrees/) and PreToolUse safety-check hook.
---

# Using Git Worktrees Skill

This skill extends `superpowers:using-git-worktrees` for the `gin-workflow` plugin.

## Base Skill

When `superpowers:using-git-worktrees` is available, use it first as the base contract. Then apply the Gin Workflow overlay below.

If `superpowers:using-git-worktrees` is unavailable, continue with this skill's self-contained rules and say that the Superpowers base skill could not be loaded.

## Gin Workflow Overlay

Gin Workflow keeps the Superpowers standards, with these plugin-specific overrides:

1. **Safety First**:
   - Only execute worktree creation and teardown commands via approved scripts (`worktree-create.sh`, `worktree-cleanup.sh`).
   - Do not allow hallucinated paths or wildcards in worktree commands.
2. **Worktree Layout**:
   - Create worktrees under `.planning/worktrees/<track-id>/`.
   - Ensure the worktree is checked out to a unique branch specific to the track.
3. **Constraint Hook**:
   - The safety-check script (`safety-check.sh`) must run in `PreToolUse` to ensure all filesystem modifications and shell executions are restricted to the designated worktree path.
