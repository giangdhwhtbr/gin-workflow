---
name: gin-worktrees
description: Use before implementation to detect or create an isolated git worktree and verify a clean test baseline.
---

# Worktrees

Detect existing isolation first, then prefer the harness's native worktree tool, then fall back to git. Never fight the harness.

## 0. Detect
```bash
GIT_DIR=$(cd "$(git rev-parse --git-dir)" && pwd -P); GIT_COMMON=$(cd "$(git rev-parse --git-common-dir)" && pwd -P)
git rev-parse --show-superproject-working-tree   # prints a path => submodule, treat as a normal repo
```
- `GIT_DIR != GIT_COMMON` (not a submodule): already isolated. Report "Already in isolated workspace at `<path>` on branch `<name>`" (or "detached HEAD, externally managed") and skip to step 2. Never nest worktrees.
- Otherwise you are in a normal checkout. Isolation is the default; ask only if no preference is declared. Disabling isolation or working on the current branch needs explicit user approval, recorded before acting.

## 1. Create
1. **Native tool first.** If the harness provides a worktree tool, use it. `git worktree add` alongside one creates state the harness cannot manage.
2. **Git fallback** under `.planning/worktrees/<track-id>` (one explicit id, no wildcards or unresolved paths):
   - Verify the root is ignored: `git check-ignore -q .planning/worktrees`. If not, add it to `.gitignore` (commit it on the feature branch).
   - New branch: `scripts/worktree-create.sh <track-id> <branch> [base-ref]` (the script validates the id and path containment, and always creates the branch).
   - Existing branch: `git worktree add .planning/worktrees/<track-id> <branch>` (a branch can be checked out in only one worktree, so switch the main checkout away from it first).
   - Then work from inside the new directory. Paths and branch names are runtime metadata; Beads owns status.
3. If creation fails because of a sandbox or permission error, tell the user and, with approval, work in place.

## 2. Project setup
Install with the project's own tooling: `pnpm install` / `yarn install` / `npm ci` (lockfile-driven), `cargo build`, `pip install -r requirements.txt` or `poetry install`/`uv sync`, `go mod download`. Skip what does not apply.

## 3. Baseline
Run the project test command (configured `verify.commands` first). If it fails, report the failures and ask whether to proceed or investigate. If it passes, report: `Worktree ready at <path>; tests passing (<N>, 0 failures)`.

## Cleanup
Only after merge or a confirmed discard: from the main checkout (never from inside the worktree), run `scripts/worktree-cleanup.sh <track-id>`, then `git worktree prune`, then delete the branch. Keep the worktree for PR and keep-as-is outcomes.
