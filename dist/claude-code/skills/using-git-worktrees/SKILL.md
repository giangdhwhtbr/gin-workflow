---
name: using-git-worktrees
description: Guidelines for managing Git worktrees safely to isolate parallel track development.
---

# Using Git Worktrees Skill

This skill explains how to isolate concurrent worker tracks using Git worktrees.

## Execution Rules

1. **Safety First**:
   - Only execute worktree creation and teardown commands via approved scripts (`worktree-create.sh`, `worktree-cleanup.sh`).
   - Do not allow hallucinated paths or wildcards in worktree commands.
2. **Worktree Layout**:
   - Create worktrees under `.planning/worktrees/<track-id>/`.
   - Ensure the worktree is checked out to a unique branch specific to the track.
3. **Constraint Hook**:
   - The safety-check script (`safety-check.sh`) must run in `PreToolUse` to ensure all filesystem modifications and shell executions are restricted to the designated worktree path.
