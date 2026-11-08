# Team handoff: gin team handoff and takeover replace the manual chain

**Context**
Epic `gin-workflow-ht4l` (2026-11-07, shipped 2026-11-08). Handing a track over in team mode was a chain of commands run by hand (push the branch, commit the ledger, `team reassign`; fetch, `git worktree add`, `team claim`). A wrong order lost work: `reassign` before the push left commits behind, an uncommitted ledger did not travel, and `gin worktree create` could not check out an existing branch. The epic's other three subsystems (track beads from a plan, PR body, members) were split off at discuss and are not done.

**Decision/Solution**
- `gin team handoff <bead> (<email> | --release) [--worktree PATH]` (`workflow_core/team_beads.py` `handoff`): worktree at `.planning/worktrees/<bead>` or `--worktree`; refuses a dirty tree (tracked and untracked), a non-git worktree, and the `reassign` authority or target violations before any push; then `git push -u origin <branch>`, `push_review_ref` for the ledger's ref (`_ledger_ref`: `repositories[0].checkpoint_ref or review_ref`, default `refs/gin/review/<bead>`; a broken `review.json` stops here, after the branch push), metadata `handoff={branch, from, to, at}`, then `_write_reassign` or the release (`--assignee "" --status open --unset-metadata claim --add-label released`). Step failures are `SyncConflict` (exit 1); argument misuse is `TeamError` (exit 2).
- `gin team takeover <bead> [--branch NAME]` (`takeover`): main checkout only (`--git-dir` equals `--git-common-dir`); branch from `handoff.branch` or `--branch`; rejects a name starting with `-` or failing `git check-ref-format --branch` before any git call (a teammate with Beads write access could otherwise inject `--upload-pack=`); `git fetch origin <branch>`, `worktrees.checkout`, review ref fetched with `+ref:ref` only under `refs/gin/review/`, then `claim`. A failure after the worktree exists appends `worktree left at <path>; remove it with gin worktree cleanup <bead>`.
- Pool flag is the label `released`, not metadata: `bd ready --json` and `bd list --json` rows carry labels but no metadata. `team ready` lists a released bead for every member (`released: true` in the JSON row only); `claim` skips the area check for it and removes the label.
- `worktrees.checkout(repo, track_id, branch)` and `gin worktree checkout`: local branch, or `--track -b` from `origin/<branch>`; `ValueError` for an existing directory or unknown branch.
- `reassign`'s checks live in `_reassign_target` and its write in `_write_reassign`, shared with `handoff`.

**Consequences**
- The spec said `review-ledger.py push-refs`; the code calls `review_ledger.git_adapter.push_review_ref` directly because `push-refs` has no `--repository` and reads the ledger from the cwd. The import sits inside `handoff`.
- `handoff` metadata is written before the reassign or release; if that last `bd update` fails the bead keeps its assignee but carries the metadata. Re-running is safe (push is idempotent, metadata overwritten).
- `sync` runs twice in `takeover` with `beads_remote` (once in `takeover`, once in `claim`); the F-1 message of `takeover` says "from the handoff metadata" even when the name came from `--branch`.
- Tests (`tests/workflow_core/test_team_beads.py` `TestTeamHandoff`, 11 tests) use a bare `origin` created in `setUp` and `git remote set-url`; the second machine is simulated by `worktrees.cleanup` plus `git branch -D` in the same repo. `test_takeover_checks_out_the_handed_off_branch_and_claims` failed once under heavy load with the disk at 100% and never again.
- The team skill is at 5,843 of 6,000 characters.
- Not run: a real two-clone handoff with shared Beads (Dolt remote).

**References**
- `plugins/gin-workflow/src/scripts/workflow_core/{team_beads,team_cli,worktrees}.py`
- Tests: `tests/workflow_core/test_team_beads.py`, `tests/workflow_core/test_worktrees.py`
- Docs: `docs/reference/cli.md` (`gin team`, `gin worktree`), `docs/guides/team.md`, `docs/guides/team.vi.md`, `docs/guides/ai-strategy.md`, `plugins/gin-workflow/src/skills/team/SKILL.md`
- `.planning/specs/2026-11-07-team-handoff-design.md`, `.planning/plans/2026-11-07-team-handoff.md`
- Commits `8f54dae`, `e52fbad`, `cdc27c1`, `2fa8579`, `5e919b7`, `e7dc531`, `be787e5`, `648aa25`, `fa38281`
- Beads: `gin-workflow-ht4l`, `gin-workflow-ht4l.1` to `.5`
- Related: [review-ledger-cycle-limit](review-ledger-cycle-limit.md), [epic-comments](epic-comments.md)

**Scope**
Team mode track handoff and takeover, the `released` label, and `gin worktree checkout`.
