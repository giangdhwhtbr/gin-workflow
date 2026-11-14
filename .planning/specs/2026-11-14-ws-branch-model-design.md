# Branch, pull request, and review ledger model for workspace children

Epic: gin-workflow-ws-branch-model
Kind: capability
Status: draft for user review.

## Goal and scope

In team mode, a track pull request in a workspace child targets that child's default branch; `gin team claim` creates the member's track worktree in the right repository; `gin team takeover` fetches from the child; review ledgers of child tracks live in the parent; and `gin team complete <epic>` closes a multi-member epic once every pull request has merged.

Problem (process review `.planning/reviews/2026-11-07-process-review/synthesis.md:33-37`): BE-LEAD-4 (no pushed child branch, no worktree on claim, takeover fetches from the wrong repository), BE-LEAD-14 and FE-LEAD-14 (no base for a child track pull request, ship opens one pull request), BE-LEAD-15 (which branch tracks start from after the spec and plan pull requests merge), BE-LEAD-10 and FE-LEAD-16 (review ledgers committed in service repositories), PM-13 (nothing closes a multi-member epic). Checked on master `535a227e`:
- Orchestrate step 6 creates the child `feat/<topic>` from `origin/<default_branch>` and the track worktrees on the lead's machine and pushes nothing (`skills/orchestrate/SKILL.md:24`, `skills/worktrees/SKILL.md:36-42`). The team skill's orchestrate section names no branch or worktree (`skills/team/SKILL.md:24-26`).
- `gin team claim` writes the bead lease only (`workflow_core/team_beads.py:194`). `gin team takeover` fetches the handed-off branch and checks it out against the parent (`team_beads.py:378-`), so a branch that lives in a child fails with "does not exist locally or on origin" (`worktrees.py:59`). `handoff` already pushes from the track worktree, which is the child (`team_beads.py:314-`).
- `docs/guides/git-flow.md:56-57,79` name the branches but no base; in team mode a track pull request is approved by the `ship` roles (`git-flow.md` Pull requests table) and the team skill's ship section checks a child pull request from its track worktree (`skills/team/SKILL.md:42`); the plan skill commits the plan on the spec's `feat/<topic>` while team mode uses `plan/<topic>` (`skills/plan/SKILL.md:17`, `skills/team/SKILL.md:22`).
- `review_ledger/cli.py:40-53` puts the ledger under the current directory, so a review run in a child track worktree commits `.planning/reviews/<bead>/` into the service repository; `validate --in-history` searches the history of the current directory (`review-ledger.py:425-433`). `team_beads._ledger_ref` and `handoff` read `<worktree>/.planning/reviews/<bead>/review.json` (`team_beads.py:292`).
- Closing a multi-member epic is prose only: "the lead declares the feature complete once every track pull request has merged" (`docs/guides/team.md:105`, `skills/team/SKILL.md:42`).
- Budgets: the `team` skill is 5,995 of 6,000 characters (`tests/workflow_core/test_token_budget.py`); stage chains: plan 11,647, orchestrate 7,331, execute 11,805, ship 11,312, review 11,785 of 12,000.

In scope:
- The team-mode branch model for tracks and the parent integration branch.
- Worktree creation by `gin team claim`.
- `gin team takeover` in a child.
- The review ledger location in a workspace.
- `gin team complete`.
- The skill and docs changes.

Out of scope:
- Several pull request URLs in `record shipped` and `team deps` for children (`gin-workflow-ws-ship-records`).
- Read-only siblings and running services (`gin-workflow-ws-track-env`).
- `/gin:quick` in team mode (`gin-workflow-quick-team`).
- Solo mode (no `team:`), which keeps its local `feat/<topic>` merge.
- The ship gate check itself (`gin-workflow-ws-ship-gate`).

Confirmed decisions (user, 2026-11-14): the epic was split, and ship records, the track environment, and quick in team mode became their own roadmap epics; a child track pull request targets the child's default branch; `gin team claim` creates the track worktree; ledgers of child tracks live in the parent with the review refs in the child; a new `gin team complete <epic>` closes the epic.

Comments considered: 1, latest 2026-11-10T15:48:14Z
Confirmed summary (user, 2026-11-14): the goal and scope above; the `[gin ship]` comment of `gin-workflow-ws-ship-gate` says the ship gate now accepts child pull requests and handed BE-LEAD-13 and BE-LEAD-16 to this epic, which now go to `gin-workflow-ws-ship-records`; every finding of the epic still holds on master.

## Requirements

R1. Track branches in team mode. A track's branch `feat/<topic>-t<N>` starts from `origin/<default_branch>` of the track's repository: the child named by the bead's `Repo:` line, else the parent. Its pull request targets that default branch and is approved by the `team.approvals.ship` roles. `<default_branch>` is `workspace.repos[].default_branch` for a child; for the parent, the branch `git symbolic-ref refs/remotes/origin/HEAD` names, else `main`.

R2. Orchestrate in team mode. Orchestrate creates no child `feat/<topic>` and no worktree for another member's track. In a workspace it creates the parent's `feat/<topic>` from `origin/<default_branch>` of the parent and pushes it; this branch holds the epic's review ledgers and knowledge records. Tracks start from the default branch after the spec and plan pull requests merge; the plan and orchestrate skills say so.

R3. `gin team claim <bead>` creates the track worktree after the lease:
- `<topic>` and `<N>` come from the bead's `Plan: <path>, Track <N>` line (`<topic>` as `team_pending.topic_of` derives it), the repository from its `Repo:` line;
- it runs `git -C <repo> fetch origin <default_branch>`, creates `feat/<topic>-t<N>` from `origin/<default_branch>`, and adds the worktree at `.planning/worktrees/<bead>` of the parent (the existing `gin worktree create [--repository <repo>]` layout);
- an existing worktree for the bead is kept; claiming one's own bead again renews the lease;
- a child that is not cloned refuses before the lease with `gin workspace clone <path>` and exit 1;
- a fetch or worktree failure after the lease keeps the lease, reports the error, and exits 1; running `gin team claim` again retries;
- a bead without a `Plan:` line gets the lease only, as today.

R4. `gin team takeover <bead>` reads the bead's `Repo:` and fetches the handed-off branch and the review ref from that child's `origin`, then checks the worktree out in the child; a child that is not cloned exits 1 with `gin workspace clone <path>`. In a workspace, `handoff` also pushes the parent's `feat/<topic>` when it has ledger commits that are not pushed, and `takeover` pulls it first.

R5. Review ledger location. When `review-ledger.py` runs in a workspace child's track worktree `<P>/.planning/worktrees/<bead>` or in a child checkout, the ledger directory is `<P>/.planning/reviews/<bead>/`, `<P>` being the parent checkout that holds the worktree. The reviewed repository stays the child: checkpoint commits and `refs/gin/review/<bead>` live there and `push-refs` pushes them to the child's `origin`. The ledger records the worktree path for checkpoints and the child checkout path for history checks. Outside a workspace nothing changes. When no parent is found, the current directory is used, as today.

R6. `validate --in-history`, run from the parent, finds each child track's approved source in the history of its child checkout, also after the track worktree has been removed.

R7. Ledger sharing in team mode with a workspace: the ledger lives on the parent's `feat/<topic>`. Each ledger session (implementer or reviewer) starts with `git pull --rebase` on that branch and ends with a commit of `.planning/reviews/<bead>/` and a push; the review and team skills say so. Ship opens the parent's `feat/<topic>` pull request.

R8. `gin team complete <epic> [--format json]`:
- team mode only, else exit 2 with `team mode is off`; the git email's member must hold a role that leads an area (`team.areas[*].lead`), else exit 2;
- checks that every child bead of the epic not labelled `prep` is closed; that for each track bead the newest pull request of `feat/<topic>-t<N>` in its repository is `merged`; and, in a workspace, that the parent's `feat/<topic>` pull request is `merged` when that branch exists on the parent's `origin`;
- when every check passes it closes the epic bead with a reason that lists the merged pull request URLs (which marks `shipped`) and prints the next step (`gin team sync` when `team.beads_sync` is set);
- otherwise it lists each missing item, closes nothing, and exits 1;
- a host failure exits 2 with the cause.

R9. Skills and docs.
- `docs/guides/git-flow.md`: the base of each branch kind, and the parent's `feat/<topic>` in a workspace.
- The `team` skill: orchestrate, execute (claim creates the worktree), review (ledger sharing), ship (the parent pull request, then `gin team complete`); the skill is at 5,995 of 6,000 characters, so the workspace rules go into a reference file the skill names (for example `skills/team/references/workspace.md`).
- The orchestrate skill step 6 and the plan skill (one sentence each for team mode).
- `docs/guides/team.md`, `docs/guides/workspace.md`, `docs/starters/brownfield.md` and their `.vi.md` pages, `docs/reference/cli.md` (`team claim`, `team takeover`, `team complete`), `docs/concepts/state-model.md` (ledger location).

## User Stories

### US-1: A member starts a track with one command
As a backend engineer in team mode, I want `gin team claim <bead>` to give me the track worktree in my service repository, so that I start work without asking the lead.

Acceptance criteria:
- After `gin team claim <bead>` for a bead with `Repo: services/order-api` and `Plan: .planning/plans/2026-11-14-x.md, Track 2`, `.planning/worktrees/<bead>` is a worktree of `services/order-api` on `feat/x-t2`, branched from `origin/main` of that child.
- Running the claim again keeps the worktree and the lease.
- With `services/order-api` not cloned, the claim exits 1, prints `gin workspace clone services/order-api`, and writes no lease.

### US-2: Takeover works in a child
As a member taking over a handed-off track, I want `gin team takeover` to fetch the branch from the child, so that I continue where the other member stopped.

Acceptance criteria:
- After a handoff that pushed `feat/x-t2` to the child's `origin`, `gin team takeover <bead>` checks it out at `.planning/worktrees/<bead>` in the child.

### US-3: Ledgers stay out of service repositories
As a service owner, I want review ledgers out of my repository, so that its default branch carries only service code.

Acceptance criteria:
- A review run in a child track worktree writes `<P>/.planning/reviews/<bead>/review.json`, and the child worktree has no `.planning/reviews/`.
- `validate --in-history` from the parent passes for an approved child track, also after its worktree is removed.

### US-4: The lead closes the epic
As a lead, I want one command that closes the epic once every track pull request has merged, so that nothing ships half done.

Acceptance criteria:
- With every track closed and every track pull request merged, `gin team complete <epic>` closes the epic and lists the pull request URLs.
- With one track pull request still open, it exits 1, names that pull request, and leaves the epic open.
- A member who leads no area gets exit 2.

## Errors and compatibility

- Solo mode and single-repository team projects keep their flow; the only change for a single-repository team is that `team claim` also creates the track worktree.
- `team claim` without a `Plan:` line behaves as today.
- `review-ledger.py` outside a workspace keeps the current directory as the ledger root; existing ledgers stay readable.
- `gin team complete` never closes the epic when a check fails or the host is unavailable.
- The JSON of existing commands only gains keys.

## Testing

- `tests/workflow_core/test_team_beads.py` (or a new `test_team_claim_worktree.py`): claim creates the worktree in a child from local bare remotes, is idempotent, refuses an uncloned child without a lease, keeps the lease on a fetch failure, and leaves a bead without `Plan:` as today; takeover fetches from the child.
- `tests/review_ledger/`: the ledger root from a child track worktree and from a child checkout; `validate --in-history` from the parent with and without the worktree; outside a workspace unchanged.
- `tests/workflow_core/test_team_complete.py` (new) with the `fake_cli` host fakes: every check passing, an open track pull request, an open track bead, a member without a lead role, team mode off, a host failure.
- `tests/workflow_core/test_skill_routing.py` and `test_token_budget.py`: the skill text and budgets; `gin docs check` on changed pages; full suite `python3 -m pytest -n auto`.

## Open Technical Questions
