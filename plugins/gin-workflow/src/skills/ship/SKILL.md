---
name: ship
description: Present integration options for completed work, run the approved one, and close out beads and ledgers.
---

## Before you start
1. If `.agent-workflow/generated/effective-config.yaml` does not exist in the main checkout (the parent of `git rev-parse --path-format=absolute --git-common-dir`; linked worktrees have none), stop: tell the user to run `/setup` once and do nothing else. (`capabilities: {}` is a valid config.)
2. Read [references/stage-contract.md](../../references/stage-contract.md) now: it defines the gate CLI, valid evidence, approval, and git rules this stage relies on.

# Ship

Check → detect workspace → present options → execute the choice → clean up → close out.

## Steps

1. Require `implementation_complete` and a terminal review state. Do not run tests: the `pre-commit`/`pre-push` git hooks and CI own that (run `gin-workflow hooks install` if `gin-workflow setup doctor` reports a hook missing). Run only these plain steps and stop on the first failure, reporting it to the user without retrying:
   - With `project.review_ledger` on, for each closed track bead of the epic: `python3 review-ledger.py validate --bead-id <id> --in-history` and `render --bead-id <id> --check`. Then `git log -m --name-only <newest approved commit>..HEAD` may touch only `.planning/specs/`, `.planning/reviews/`, and the SDD spec dirs; any other change after approval needs the last approved track reopened (`bd reopen`) and reviewed again.
   - With `project.layout: sdd`, lint, trace, and archive the change into the living spec, per the `gin-sdd` skill.
   With `project.team.enabled`, merging follows the host rules, Beads are synced, and a `team.approvals.ship` policy limits the options (the `gin-team` skill).
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
   - **Merge:** `cd "$MAIN_ROOT" && git checkout <base> && git pull --ff-only && git merge "$FEATURE_BRANCH"`; if the base cannot fast-forward (it diverged from its upstream), stop and ask instead of rebasing it. Then clean up (step 6) and `git branch -d "$FEATURE_BRANCH"`.
   - **PR:** (detached: `git checkout -b <branch>` first) `git push -u origin <branch>` then `gh pr create --fill`. Keep the worktree.
   - **Keep:** report the branch and worktree path. Keep the worktree.
   - **Discard:** list what will be deleted and require the typed word `discard`. Then `git reset --hard HEAD && git clean -fd`; for a named branch, clean up (step 6), then `cd "$MAIN_ROOT" && git checkout <base> && git branch -D "$FEATURE_BRANCH"`. A detached workspace is only reset; the harness owns its removal.
6. Cleanup (merge/discard only, when `IS_WORKTREE=yes`): from `MAIN_ROOT`, run `scripts/worktree-cleanup.sh <track-id>` (never from inside the worktree), before deleting the branch, then `git worktree prune`. Never use wildcards or unresolved paths; never remove harness-owned worktrees.
7. Close out: run `gin-workflow usage collect --bead <epic> --best-effort` before closing the parent bead and before any ledger cleanup; close the remaining beads with evidence (`bd close`); the parent bead closes only after a human-confirmed merge, and closing it is what marks `shipped`. A standalone bead (its own epic) is already closed: after the merge, `gin-workflow record shipped --workflow-id <bead> --evidence <merge commit> --actor <id>`. Once a bead is closed and merged, run `python3 review-ledger.py cleanup --bead-id <bead-id>` (or `--all-closed`). Reconcile knowledge per `gin-knowledge`. Branch or worktree cleanup never proves completion.
8. If this repository is itself a plugin/marketplace source installed elsewhere on this host (as `gin-workflow` is), refresh each platform's installed snapshot (see `docs/reference/troubleshooting.md`); harness caches do not pick up new commits.
9. Handoff: list `bd ready` tasks grouped by dependency readiness and non-overlapping file scope, mark which can run in parallel, and end with `Next commands:` (for example `/gin-workflow:execute <id-1> <id-2>`).

## Exit

Return `shipped`. Do not start another lifecycle stage.
