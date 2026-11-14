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

1. Require `implementation_complete` and a terminal review state. Run `gin hooks status` (in a workspace, `gin hooks status --all-repos`); on exit 1, warn the user which hook is not `ok`, or that `verify_commands` is empty, so checks did not run before integration (`gin hooks install`, in a workspace `gin hooks install --all-repos`, fixes a missing hook), and continue: it never stops ship. List each entry of `review_waivers` from `gin state --format json --workflow-id <id>` to the user as a track closed without review, with its reason and actor. When `team.members` in `.agent-workflow/config.yaml` has a member with the role `ba` and `gin task comments <epic> --json` has no `[gin accept]` comment, warn `no BA acceptance ([gin accept]) on <epic>` and continue; skip this check with the markdown backend. Do not run tests: the `pre-commit`/`pre-push` git hooks and CI own that. Run only these plain steps and stop on the first failure, reporting it to the user without retrying:
   - With `project.review_ledger` on, for each closed track bead of the epic not listed in `review_waivers` and not labelled `prep`: `python3 review-ledger.py validate --bead-id <id> --in-history` and `render --bead-id <id> --check`. The newest approved commit is the one `validate --in-history` prints for the newest track; after a squash merge, it is the squash commit. Then `git log -m --name-only <newest approved commit>..HEAD` may touch only `.planning/specs/`, `.planning/reviews/`, `.planning/knowledge/`, and the SDD spec dirs; any other change after approval needs the last approved track reopened (`gin task reopen`) and reviewed again. Tell the user each closed `prep` bead of the epic (id, title, close reason) as closed without review.
   - With `project.layout: sdd`, lint, trace, and archive the change into the living spec, per the `sdd` skill.
   - Run the acceptance-case check in the `qa-track` skill (Ship check): missing or stale cases stop ship; without it, say the QA check was skipped.
   With `project.team.enabled`, merging follows the host rules, Beads are synced, and a `team.approvals.ship` policy limits the options (the `team` skill).
   Then reconcile knowledge per `learn` and commit the records on the feature branch, before the options.
2. Detect the workspace before changing directory and save the results:
   ```bash
   GIT_DIR=$(cd "$(git rev-parse --git-dir)" && pwd -P); GIT_COMMON=$(cd "$(git rev-parse --git-common-dir)" && pwd -P)
   WORKTREE_PATH=$(git rev-parse --show-toplevel); IS_WORKTREE=$([ "$GIT_DIR" != "$GIT_COMMON" ] && echo yes || echo no)
   MAIN_ROOT=$(git -C "$GIT_COMMON/.." rev-parse --show-toplevel); FEATURE_BRANCH=$(git rev-parse --abbrev-ref HEAD)
   ```
3. Base branch: from the plan, else `git merge-base HEAD main || git merge-base HEAD master`, else ask. Workspace: one integration item per `Repo:` with tracks, then the parent (spec, plan, docs).
4. Present exactly these options, without extra explanation:
   - Named branch: `1. Merge back to <base> locally` · `2. Push and create a Pull Request` · `3. Keep the branch as-is` · `4. Discard this work`
   - Detached HEAD (externally managed): `1. Push as new branch and create a PR` · `2. Keep as-is` · `3. Discard`
5. Before creating a PR, merging, force-pushing, or cleanup: get approval (stage-contract Approvals), and confirm `git status --porcelain` is clean in both the worktree and `MAIN_ROOT` (ask to commit uncommitted work first). Never force-push unless asked.
   - **Merge:** `cd "$MAIN_ROOT" && git checkout <base> && git pull --ff-only`; if the base cannot fast-forward (it diverged from its upstream), stop and ask instead of rebasing it. Then, on the feature branch, run `gin usage collect --bead <epic> --best-effort` and `python3 review-ledger.py cleanup --bead-id <id>` for each closed track bead (a standalone bead is its own track; skip beads not closed and `prep` beads), and commit the deletion there so it lands with the merge (if the merge is then abandoned, `git revert` that commit). Then `git merge "$FEATURE_BRANCH"` from `MAIN_ROOT`, clean up (step 6) and `git branch -d "$FEATURE_BRANCH"`. Report any `remote_error` in the cleanup output. Workspace: `MAIN_ROOT` is the child checkout `<parent>/<repo>`; merge its track branches into the child's `feat/<topic>`, then `feat/<topic>` into `<default_branch>`, one repository at a time; the parent last.
   - **PR:** (detached: `git checkout -b <branch>` first) `git push -u origin <branch>` then open the PR: with team mode the `team.host` command from the `team` skill's references/hosts.md, else `gh pr create --fill`. Keep the worktree.
   - **Keep:** report the branch and worktree path. Keep the worktree.
   - **Discard:** list what will be deleted and require the typed word `discard`. Then `git reset --hard HEAD && git clean -fd`; for a named branch, clean up (step 6), then `cd "$MAIN_ROOT" && git checkout <base> && git branch -D "$FEATURE_BRANCH"`. A detached workspace is only reset; the harness owns its removal.
6. Cleanup (merge/discard only, when `IS_WORKTREE=yes`): from `MAIN_ROOT`, run `gin worktree cleanup <track-id>` (never from inside the worktree), before deleting the branch, then `git worktree prune`. In a workspace: `gin worktree cleanup --repository <repo> <track-id>` from the parent. Never use wildcards or unresolved paths; never remove harness-owned worktrees.
7. Close out: run `gin usage collect --bead <epic> --best-effort` before closing the parent bead, unless the merge already ran it; close the remaining beads with evidence (`gin task close`); before closing the parent bead, tell the user each open `prep` bead and close it with `--reason "not needed: <epic> shipped"`, because bd refuses to close an epic with an open child; the parent bead closes only after a human-confirmed merge, and closing it is what marks `shipped`. Then, also for a standalone bead, run `gin task show <epic> --json --include-dependents`; for each dependent with `issue_type: epic` and status `open` or `in_progress` (the list also holds the epic's own tracks and bugs: skip them), run `gin task comment <dependent> "[gin ship] <epic-id> <title> shipped (merge <sha>). Spec: <design doc>. Its outcome may change what this epic needs; the next /discuss <dependent> reads this comment."` with `<sha>` the merge commit and `<design doc>` the `evidence` of the epic's latest `requirement.confirmed` event in `.agent-workflow/runtime/events.jsonl` of the main checkout (`none` without one). A failed comment never blocks the close: report it. With the markdown task backend there are no comments: say so in one sentence. A standalone bead (its own epic) is already closed: after the merge, `gin record shipped --workflow-id <bead> --evidence <merge commit> --actor <id>` (workspace: `--evidence "<repo>:<merge commit>; ...; parent:<merge commit>"`; team mode with a `ship` policy: `--evidence <pr-url>`, actor from the git email). Show each entry of `warnings` from `gin state --format json --workflow-id <id>` to the user. Branch or worktree cleanup never proves completion.
8. If this repository is itself a plugin/marketplace source installed elsewhere on this host (as the gin-workflow repository is), refresh each platform's installed snapshot (see `docs/reference/troubleshooting.md`); harness caches do not pick up new commits.
9. Handoff: list `gin task ready --exclude-label prep` tasks grouped by dependency readiness and non-overlapping file scope, mark which can run in parallel, then the dependent epics that received a `[gin ship]` comment, and end with `Next commands:` (for example `/gin:execute <id-1> <id-2>`).

## Exit

Return `shipped`. Do not start another lifecycle stage.
