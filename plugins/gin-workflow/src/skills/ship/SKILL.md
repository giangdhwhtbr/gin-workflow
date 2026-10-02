---
name: ship
description: Present integration options for verified work, run the approved one, and close out beads and ledgers.
---

Follow [references/stage-contract.md](../../references/stage-contract.md) (the plugin's shared stage contract).

# Ship

Verify → detect workspace → present options → execute the choice → clean up → close out.

## Steps

1. Require `verification_passed` and a terminal review state. Re-run the project test command; if it fails, show the failures and stop.
2. Detect the workspace before changing directory and save the results:
   ```bash
   GIT_DIR=$(cd "$(git rev-parse --git-dir)" && pwd -P); GIT_COMMON=$(cd "$(git rev-parse --git-common-dir)" && pwd -P)
   WORKTREE_PATH=$(git rev-parse --show-toplevel); IS_WORKTREE=$([ "$GIT_DIR" != "$GIT_COMMON" ] && echo yes || echo no)
   MAIN_ROOT=$(git -C "$GIT_COMMON/.." rev-parse --show-toplevel); FEATURE_BRANCH=$(git rev-parse --abbrev-ref HEAD)
   ```
3. Base branch: from the plan, else `git merge-base HEAD main || git merge-base HEAD master`, else ask.
4. Present exactly these options, without extra explanation:
   - Named branch: `1. Merge back to <base> locally` · `2. Push and create a Pull Request` · `3. Keep the branch as-is` · `4. Discard this work`
   - Detached HEAD (externally managed): `1. Push as new branch and create a PR` · `2. Keep as-is` · `3. Discard`
5. Before creating a PR, merging, force-pushing, or cleanup: get explicit approval for that action, and confirm `git status --porcelain` is clean in both the worktree and `MAIN_ROOT` (ask to commit uncommitted work first). Never force-push unless asked.
   - **Merge:** `cd "$MAIN_ROOT" && git checkout <base> && git pull && git merge "$FEATURE_BRANCH"`, re-run the tests on the merged result, then clean up (step 6) and `git branch -d "$FEATURE_BRANCH"`.
   - **PR:** (detached: `git checkout -b <branch>` first) `git push -u origin <branch>` then `gh pr create --fill`. Keep the worktree.
   - **Keep:** report the branch and worktree path. Keep the worktree.
   - **Discard:** list what will be deleted and require the typed word `discard`. Then `git reset --hard HEAD && git clean -fd`; for a named branch, clean up (step 6), then `cd "$MAIN_ROOT" && git checkout <base> && git branch -D "$FEATURE_BRANCH"`. A detached workspace is only reset; the harness owns its removal.
6. Cleanup (merge/discard only, when `IS_WORKTREE=yes`): from `MAIN_ROOT`, run `scripts/worktree-cleanup.sh <track-id>` (never from inside the worktree), before deleting the branch, then `git worktree prune`. Never use wildcards or unresolved paths; never remove harness-owned worktrees.
7. Close out: close the remaining beads with evidence (`bd close`); the parent bead closes only after a human-confirmed merge, and closing it is what marks `shipped`. Once a bead is closed and merged, run `python3 review-ledger.py cleanup --bead-id <bead-id>` (or `--all-closed`). Reconcile knowledge per `gin-knowledge`. Branch or worktree cleanup never proves completion.
8. If this repository is itself a plugin/marketplace source installed elsewhere on this host (as `gin-workflow` is), refresh each platform's installed snapshot (see the README Troubleshooting entry); harness caches do not pick up new commits.
9. Handoff: list `bd ready` tasks grouped by dependency readiness and non-overlapping file scope, mark which can run in parallel, and end with `Next commands:` (for example `/gin-workflow:execute <id-1> <id-2>`).

## Exit

Return `shipped`. Do not start another lifecycle stage.
