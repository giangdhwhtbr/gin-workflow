---
name: finishing-a-development-branch
description: Self-contained — verify, present integration options, and execute delivery with provider-backed safety and durable audit evidence.
---

# Finishing a Development Branch

## Overview

Guide completion of development work by presenting clear options and handling chosen workflow safely through configured providers.

**Core principle:** Verify tests → Detect environment → Present options → Execute choice → Clean up.

## Required Inputs

- resolved `EffectiveConfig`
- `ArtifactRegistry`
- `ContextManifest(stage="ship")`
- native-harness `ApprovalDecision`

## The Process

### Step 1: Verify Tests and Readiness

**Before presenting options, you must ensure work is shippable:**

1. Follow the canonical verification and handoff workflow ([verification-and-handoff-workflow.md](file://../../references/verification-and-handoff-workflow.md)) before treating work as shippable.
2. Generate and inspect repository identity/diff evidence against the approved baseline when integration is in scope.

Verify tests pass using standard tools:

```bash
# Run project's test suite
npm test / cargo test / pytest / go test ./...
```

**If tests fail:**
```
Tests failing (<N> failures). Must fix before completing:

[Show failures]

Cannot proceed with merge/PR until tests pass.
```

Stop. Don't proceed to Step 2.

**If tests pass:** Continue to Step 2.

### Step 2: Detect Environment

**Determine workspace state before presenting options:**

```bash
GIT_DIR=$(cd "$(git rev-parse --git-dir)" 2>/dev/null && pwd -P)
GIT_COMMON=$(cd "$(git rev-parse --git-common-dir)" 2>/dev/null && pwd -P)
WORKTREE_PATH=$(git rev-parse --show-toplevel 2>/dev/null)
IS_WORKTREE=$( [ "$GIT_DIR" != "$GIT_COMMON" ] && echo "yes" || echo "no" )
```

**Save `IS_WORKTREE` and `WORKTREE_PATH` at Step 2 before any directory change.**

This determines which menu to show and how cleanup works:

| State | Menu | Cleanup |
|-------|------|---------|
| `GIT_DIR == GIT_COMMON` (normal repo) | Standard 4 options | No worktree to clean up |
| `GIT_DIR != GIT_COMMON`, named branch | Standard 4 options | Provenance-based (see Step 6) |
| `GIT_DIR != GIT_COMMON`, detached HEAD | Reduced 3 options (no merge) | No cleanup (externally managed) |

### Step 3: Determine Base Branch

1. Resolve the base branch from the approved plan artifact or evidence manifest (e.g. `base_branch: main`).
2. If unspecified in the plan, confirm with the user or check merge base:
   ```bash
   git merge-base HEAD main 2>/dev/null || git merge-base HEAD master 2>/dev/null
   ```

### Step 4: Present Options

**Normal repo and named-branch worktree — present exactly these 4 options:**

```
Implementation complete. What would you like to do?

1. Merge back to <base-branch> locally
2. Push and create a Pull Request
3. Keep the branch as-is (I'll handle it later)
4. Discard this work

Which option?
```

**Detached HEAD — present exactly these 3 options:**

```
Implementation complete. You're on a detached HEAD (externally managed workspace).

1. Push as new branch and create a Pull Request
2. Keep as-is (I'll handle it later)
3. Discard this work

Which option?
```

**Don't add explanation** - keep options concise.

### Step 5: Execute Choice

**Safety Rule:** Revalidate native-harness approval and persist durable audit evidence immediately before commit, push, merge, data movement, or protected cleanup. Use configured repository/workspace capabilities for authorized integration; never invoke adapter scripts directly.

**Preflight Cleanliness Check:**
- In feature workspace: inspect `git status --porcelain`. If uncommitted changes exist, request explicit user authorization to commit/checkpoint them first. Do not push or merge with uncommitted changes.
- In `MAIN_ROOT` (for local merge): inspect `git -C "$MAIN_ROOT" status --porcelain` before `checkout`/`pull`/`merge`. Ensure `MAIN_ROOT` is clean before performing integration operations.

**Option Mapping:**
- **Standard Menu (4 options):** Option 1 = Merge Locally, Option 2 = Push & Create PR, Option 3 = Keep As-Is, Option 4 = Discard.
- **Detached HEAD Menu (3 options):** Option 1 = Push as new branch & Create PR (runs Push & Create PR below), Option 2 = Keep As-Is, Option 3 = Discard.

#### Option 1: Merge Locally (Standard Menu only)

```bash
# Save feature branch name before switching directories
FEATURE_BRANCH=$(git rev-parse --abbrev-ref HEAD)
MAIN_ROOT=$(git -C "$(git rev-parse --git-common-dir)/.." rev-parse --show-toplevel)

# Ensure feature workspace and MAIN_ROOT are clean (with authorization)
cd "$MAIN_ROOT"

# Revalidate approval & persist evidence here
git checkout <base-branch>
git pull
git merge "$FEATURE_BRANCH"

# Verify tests on merged result
<test command>
```

Only after merge succeeds: Cleanup worktree via `WorkspaceProvider` (Step 6), then delete feature branch:
```bash
git branch -d "$FEATURE_BRANCH"
```

#### Option 2: Push and Create PR (Detached HEAD Option 1)

```bash
# Revalidate approval & persist evidence here

# On detached HEAD: prompt for branch name and create branch first: git checkout -b <feature-branch>
# Ensure all work is committed with authorization before push

# Push branch
git push -u origin <feature-branch>

# Create Pull Request using repository PR capability / CLI
gh pr create --fill
```

**Do NOT clean up worktree** — user needs it alive to iterate on PR feedback.

#### Option 3: Keep As-Is (Detached HEAD Option 2)

Report: "Keeping branch <name>. Worktree preserved at <path>."

**Don't cleanup worktree.**

#### Option 4: Discard (Detached HEAD Option 3)

**Confirm first (Standard Menu):**
```
This will permanently delete:
- Branch <name>
- All uncommitted commits/changes
- Worktree at <path>

Type 'discard' to confirm.
```

**Confirm first (Detached HEAD Menu):**
```
This will permanently reset:
- All working tree changes to HEAD in this workspace
(The externally managed workspace container is preserved by the harness)

Type 'discard' to confirm.
```

Wait for exact confirmation.

If confirmed:
```bash
# 1. Save workspace state BEFORE switching directory
IS_DETACHED=$( [ "$(git rev-parse --abbrev-ref HEAD)" = "HEAD" ] && echo "yes" || echo "no" )
FEATURE_BRANCH=$(git rev-parse --abbrev-ref HEAD)
MAIN_ROOT=$(git -C "$(git rev-parse --git-common-dir)/.." rev-parse --show-toplevel)

# 2. Reset/clean uncommitted changes in current workspace first
git reset --hard HEAD && git clean -fd

if [ "$IS_DETACHED" = "yes" ]; then
  # On detached HEAD: do not delete main branch. Delegate workspace cleanup to harness workspace-exit tool.
  echo "Detached HEAD workspace reset to clean state."
else
  # 3. For linked worktree: clean up workspace via WorkspaceProvider (Step 6) FIRST to release branch lock
  # 4. Then switch to MAIN_ROOT, checkout base branch, and delete feature branch
  cd "$MAIN_ROOT"
  git checkout <base-branch>
  git branch -D "$FEATURE_BRANCH"
fi
```

### Step 6: Cleanup Workspace

**Only runs for Options 1 and 4.** Options 2 and 3 always preserve the worktree.

Use the `IS_WORKTREE` and `WORKTREE_PATH` metadata captured during Step 2 (before directory switches).

**If `IS_WORKTREE == "no"`:** Normal repo, no worktree to clean up. Done.

**If `IS_WORKTREE == "yes"`:**
- For internally managed worktrees (recorded in workspace-provider records), resolve the `workspace_id` and invoke `WorkspaceProvider.cleanup(workspace_id, idempotency_key=...)`. Note: `WorkspaceProvider.cleanup` requires `workspace_id`, NOT a file path string.
- Perform `WorkspaceProvider` cleanup BEFORE deleting the feature branch (otherwise Git blocks branch deletion while worktree is active).
- Discover cleanup targets from bounded execution context and workspace-provider records.
- Reject wildcards, unresolved paths, and manual direct script execution.
- For externally managed / harness-owned worktrees (such as detached HEAD workspaces), do NOT delete or remove directly — leave the workspace in place or use the harness workspace-exit tool.

### Step 7: Final Task Tracking & Review Ledger Cleanup

Use task-tracking capabilities for durable handoff and closure. Branch or workspace cleanup never proves task completion.

Once the task bead is closed in task tracking and the branch is merged into the base branch, clean up its transient review ledger directory:

```bash
python3 review-ledger.py cleanup --bead-id <bead-id>
```

To clean up all stale review directories across the repository at once:

```bash
python3 review-ledger.py cleanup --all-closed
```

## Quick Reference

| Option | Merge | Push | Keep Worktree | Cleanup Branch |
|--------|-------|------|---------------|----------------|
| 1. Merge locally | yes | - | - | yes |
| 2. Create PR | - | yes | yes | - |
| 3. Keep as-is | - | - | yes | - |
| 4. Discard | - | - | - | yes (force) |

## Common Mistakes

**Skipping test verification**
- **Problem:** Merge broken code, create failing PR
- **Fix:** Always verify tests before offering options

**Open-ended questions**
- **Problem:** "What should I do next?" is ambiguous
- **Fix:** Present exactly 4 structured options (or 3 for detached HEAD)

**Cleaning up worktree for Option 2**
- **Problem:** Remove worktree user needs for PR iteration
- **Fix:** Only cleanup for Options 1 and 4

**Deleting branch before removing worktree**
- **Problem:** `git branch -d` fails because worktree still references the branch
- **Fix:** Merge first, remove worktree, then delete branch

**Running git worktree remove from inside the worktree**
- **Problem:** Command fails silently when CWD is inside the worktree being removed
- **Fix:** Always `cd` to main repo root before `git worktree remove`

**Wildcard cleanup**
- **Problem:** Deleting unexpected paths
- **Fix:** Reject wildcards and unresolved paths; discover targets strictly from context and provider records

**No confirmation for discard**
- **Problem:** Accidentally delete work
- **Fix:** Require typed "discard" confirmation

**Missing durable handoff**
- **Problem:** Closing branch without recording task status
- **Fix:** Always use task-tracking capabilities for closure

## Red Flags

**Never:**
- Proceed with failing tests
- Skip the canonical verification-and-handoff checklist
- Merge without verifying tests on result
- Delete work without confirmation
- Force-push without explicit request
- Remove a worktree before confirming merge success
- Execute integration or cleanup without revalidating approval and persisting evidence
- Invoke adapter scripts directly for integration/cleanup
- Run `git worktree remove` from inside the worktree
- Rely on branch closure as proof of task completion

**Always:**
- Generate/inspect evidence against the approved baseline
- Verify tests before offering options
- Detect environment before presenting menu
- Present exactly 4 options (or 3 for detached HEAD)
- Get typed confirmation for Option 4
- Revalidate approval before protected actions
- Clean up worktree for Options 1 & 4 only
- `cd` to main repo root before worktree removal
- Run `git worktree prune` after removal
- Use task-tracking to finalize closure
