---
name: worktrees
description: Use before implementation to detect or create an isolated git worktree and, when tests run per track, verify a clean test baseline.
---

# Worktrees

Detect existing isolation first, then prefer the harness's native worktree tool, then fall back to git. Never fight the harness.

## 0. Detect
```bash
GIT_DIR=$(cd "$(git rev-parse --git-dir)" && pwd -P); GIT_COMMON=$(cd "$(git rev-parse --git-common-dir)" && pwd -P)
git rev-parse --show-superproject-working-tree   # prints a path => submodule, treat as a normal repo
```
- `GIT_DIR != GIT_COMMON` (not a submodule): already isolated. Report "Already in isolated workspace at `<path>` on branch `<name>`" (or "detached HEAD, externally managed") and skip to step 2. Never nest worktrees.
- Otherwise you are in a normal checkout. Create a worktree when `project.worktree` asks for one (the `execute` skill); skipping it needs approval (stage-contract Approvals).

## 1. Create
1. **Native tool first.** If the harness provides a worktree tool, use it. `git worktree add` alongside one creates state the harness cannot manage.
2. **Git fallback** under `.planning/worktrees/<track-id>` (one explicit id, no wildcards or unresolved paths):
   - Verify the root is ignored: `git check-ignore -q .planning/worktrees`. If not, add it to `.gitignore` (commit it on the feature branch).
   - New branch: `gin worktree create <track-id> <branch> [base-ref]` (it validates the id and path containment, and always creates the branch). `base-ref` defaults to the current branch.
   - Existing branch: `git worktree add .planning/worktrees/<track-id> <branch>` (a branch can be checked out in only one worktree, so switch the main checkout away from it first).
   - Then work from inside the new directory. Paths and branch names are runtime metadata; Beads owns status.
3. If creation fails because of a sandbox or permission error, tell the user and work in place only with approval (stage-contract Approvals).

## 2. Project setup
Install with the project's own tooling: `pnpm install` / `yarn install` / `npm ci` (lockfile-driven), `cargo build`, `pip install -r requirements.txt` or `poetry install`/`uv sync`, `go mod download`. Skip what does not apply.

## 3. Baseline
With `push` or `host` as `project.run_at`, skip the baseline and report `Worktree ready at <path>`. With `project.run_at: track`, run the project test command. In a workspace child it is `workspace.current.checks.test` from `gin state --format json`; when that is missing, report that the entry has no test check and ask, and never run the parent's commands, which belong to another repository. Outside a workspace child it is the configured `verify.commands`. If it fails, report the failures and ask whether to proceed or investigate. If it passes, report: `Worktree ready at <path>; tests passing (<N>, 0 failures)`.

## Cleanup
Only after merge or a confirmed discard: from the main checkout (never from inside the worktree), run `gin worktree cleanup <track-id>`, then `git worktree prune`, then delete the branch. Keep the worktree for PR and keep-as-is outcomes.

## 3. Workspace
When `gin state --format json` reports `workspace.current_repo`, the worktree is one child repository and the project root is the parent:
- Strip the `<repo>/` prefix from the plan's `Files:`; paths in the worktree are repo-relative.
- Read `references/shape-<shape>.md` for `workspace.current.shape` (`backend`, `frontend`); `library` and `qa` have none.
- Commit in this worktree only (push only in team mode, stage-contract Git); the spec and plan live in the parent and are read, never edited, by a track.
- `gin` commands from inside the worktree resolve the parent: `gin task`, `gin state`, `gin review` need no `--repository`.
- Cleanup from the parent: `gin worktree cleanup --repository <repo> <track-id>`.

A track with `Reads:` (plan track or bead description): before the developer starts, take each named repository's row from `gin workspace status --json`. If it is not `present`, stop with `gin workspace clone <path>`. Give the developer its `checkout`, `branch`, and `commit` as read-only context. Never switch or pull that checkout.
