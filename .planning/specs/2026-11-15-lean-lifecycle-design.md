# Lean lifecycle: the host owns CI and approvals, tests run once, the ledger is optional

Epic: gin-workflow-ws-ship-records
Kind: capability
Status: draft for user review.

## Goal and scope

gin prefers the tools a project already has. A merged pull request counts as approved when the team says the host enforces approvals; the full test suite runs once per epic (or on the host) instead of before every review; the skills run no review ledger when it is off and follow `project.review` and `project.worktree`; `gin record shipped` takes one pull request per repository; and `gin team deps` finds the pull requests of a workspace child.

Problem. The gate inventory of this discuss (36 items) and two measured epics show where the time goes, and it is not in recording the five gates:
- `gin-workflow-ws-branch-model` (4 tracks) ran the full suite 14 times, about 94 minutes: before each review request, again after each fix cycle, at the merge, and at the push. `gin evidence run` is the pre-push hook's own run (`workflow_core/verification.py:72-80`, `hooks.py:166-205`), and the review skill asks for it before every review request (`skills/review/SKILL.md:15`). The worktrees skill adds a baseline run per worktree (`skills/worktrees/SKILL.md` "Baseline").
- Nothing reads the host's CI: no code or skill names `statusCheckRollup`, `gh pr checks`, or a commit status.
- This repository has `project.review_ledger: false` (the `standard` preset, `workflow_core/project.py:13-17`), yet the execute and review skills run the ledger commands for every track, because their text never reads that setting (`skills/execute/SKILL.md:42-44`, `skills/review/SKILL.md:14-27`). `project.review` and `project.worktree` are parsed (`project.py:69-70`) and no skill reads them.
- In team mode `gin record` and `gin team check` re-check on the host what branch protection already enforces: who approved, on which commit (`workflow_core/team.py:465-540`). A gate either has a role policy or needs no pull request at all (`needs_pr`, `team.py:585-588`).
- The workflow skill says `gin state` applies the approval TTL (`skills/workflow/SKILL.md:15`); `gin state` never does.
- `gin record shipped` accepts one pull request URL (`team.py:647-663`), so a standalone bead that changes the parent and a child cannot prove both; the workspace guide's `"<repo>:<sha>; ..."` form is unchecked. `gin team deps` searches merged pull requests in the parent only and `deps --bead` checks ancestry in the current repository (`workflow_core/team_beads.py:579-626`), so a blocking track in a child is never found.

In scope:
- A `host` value for `team.approvals.<gate>`.
- Several pull request URLs in `gin record shipped`.
- `gin team deps` for workspace children.
- A `verify.run_at` setting for where the full suite runs, followed by the hooks and the skills.
- Skills that run no ledger command when the ledger is off and that follow `project.review` and `project.worktree`.
- Docs that match the code.

Out of scope:
- Configuring branch protection through a host API; the lead enables it by hand, as today.
- Reading CI status from the host.
- One review per epic instead of one per track.
- Removing the role policies of `team.approvals`.
- Read-only siblings and running services (`gin-workflow-ws-track-env`); `/gin:quick` in team mode (`gin-workflow-quick-team`).
- `gin team complete`, which keeps checking only that pull requests merged.

Confirmed decisions (user, 2026-11-15): the host-trust mode and the whole simplification go into this one epic, renamed; existing tools come first (host CI, branch protection) and gin never demands in-session work they already do; `push` is the default for where the suite runs at `easy` and `standard` rigor; `host` is a new approval value that `/gin:team-setup` proposes for new teams, and role policies keep working; `gin team complete` gets no approval check.

Comments considered: 1, latest 2026-11-15T00:28:01Z
Confirmed summary (user, 2026-11-15): the goal and scope above; the `[gin ship]` comment says `gin-workflow-ws-branch-model` shipped, so an epic with tracks now closes through `gin team complete` and several URLs in `record shipped` matter only for a standalone bead that spans repositories; `gin team deps` is still broken for children; the epic id stays `gin-workflow-ws-ship-records` and its title changed.

## Requirements

R1. `team.approvals.<gate>: host`. The value `host` is accepted for `requirement_confirmed` (also per kind in a kind map), `plan_approved`, `ship`, and `roadmap`, next to a role list, an `{all, any}` policy, and `area_lead`. With `host`:
- the gate needs pull request proof (`gin record <gate> --evidence <url>`), as a gate with roles does;
- the pull request must be merged and belong to the parent repository or a `workspace.repos` entry; gin checks no approver, no author, and no head commit;
- `gin team check --gate <gate> <url>` before a merge checks the repository only and prints that the host enforces approvals;
- `gin team pending` lists such a pull request with an empty `missing` and the note `approvals: host`;
- the gate has no approver roles: any member may waive it, CODEOWNERS gets no spec-approver owners from it, and `team init` does not warn that it has no role policy.

R2. `/gin:team-setup` proposes `host` for the four gates and still tells the lead to protect the base branch (a pull request with an approval, code-owner review, and required status checks where the host has CI). A team that names roles keeps today's checks.

R3. `gin record shipped` takes `--evidence` more than once in team mode with a ship policy: one pull request URL per repository. Each URL is checked as a single one is today (merged, repository known, and the role policy when the gate has roles). Two URLs of one repository, or one failing URL, refuse the whole command with the reasons per URL and record nothing. One `--evidence` behaves as today.

R4. The shipped proof on the bead keeps `pr_url` and `merge_commit` of the first URL and gains `pull_requests`: a list of `{pr_url, merge_commit, repository}`, one per URL. The `delivery.shipped` event's `evidence` is the URLs joined by `, `.

R5. `gin team deps` finds a blocking track's pull request in its repository: the `Repo:` of track `<N>` in the plan file the placeholder names (`external: <plan>#<N>`), else the parent. It searches merged pull requests with that repository's checkout as the working directory. A child that is not cloned leaves the placeholder waiting with `gin workspace clone <path>`. Closing a placeholder stores `repo` next to `merge_commit`.

R6. `gin team deps --bead <bead>`: when the placeholder's `repo` is the repository of the current directory (or it has none), the merge commit must be an ancestor of HEAD, as today. Otherwise the merge commit must be on `origin/<default_branch>` in that repository's checkout; when it is missing there, the message names `git -C <path> fetch origin`.

R7. `verify.run_at`: `track`, `push`, or `host`. Without the key, the rigor preset decides: `easy` and `standard` give `push`, `strict` gives `track`. `gin state --format json` shows the value as `project.run_at`. A config without the key stays valid.

R8. Hooks follow `verify.run_at`. With `track` and `push` the pre-push hook runs the suite as today and skips a tree that already has a passing record. With `host` the pre-push hook runs no command, prints that the host CI runs the tests, and exits 0; `gin hooks status` counts that as ok. The pre-commit hook (lint, typecheck) is unchanged in every mode.

R9. Skills follow `project.run_at`:
- `track`: as today (`gin evidence run` before each review request, a baseline run in a new worktree).
- `push` and `host`: no `gin evidence run` before a review request and no baseline run; the developer and the reviewer run the tests of what the track changed.
- Ship with `push`: `gin evidence run` once on the integrated feature branch before the merge or the pull request push; a failure stops ship before any merge and is reported. Ship with `host` runs no tests.
- `/gin:quick`: `push` scopes tests to the changed files at every rigor; `host` runs lint and typecheck only; `track` is unchanged.

R10. `/gin:setup` asks whether the host runs CI on pull requests and writes `verify.run_at: host` on yes. `gin setup doctor` reports the value in use.

R11. With `project.review_ledger: false`, the execute, review, and ship skills run no `review-ledger.py` command and write nothing under `.planning/reviews/`. The reviewer still reviews the track's diff and returns a verdict and findings in its report; the implementer fixes them and asks again, at most `project.max_cycles` times, then asks the user. The track's close reason names the reviewer, the cycle count, and the finding count. With `project.review_ledger: true` the ledger procedure is today's, moved to `skills/review/ledger.md`, which the review skill names and only then reads.

R12. `project.review: self_check` (the `easy` preset): no reviewer subagent; the implementer re-reads the diff for debug leftovers, secrets, and test coverage, as `/gin:quick` does. `independent` is today's review.

R13. `project.worktree`: `always` gives each track a worktree (today); `parallel` (the `standard` preset) gives tracks worktrees only when the plan's execution strategy runs them in parallel, and otherwise tracks commit one after another on `feat/<topic>`; `never` creates none. In team mode `gin team claim` creates the track worktree as today.

R14. Docs and skill text match the code: the workflow skill and `docs/concepts/lifecycle.md` no longer say `gin state` applies the approval TTL; `docs/reference/config.md` (`verify.run_at`, `team.approvals: host`), `docs/reference/cli.md` (`record shipped`, `team deps`, `team check`), `docs/concepts/lifecycle.md` and `docs/concepts/providers.md` (evidence policy), `docs/guides/team.md`, `git-flow.md`, `workspace.md`, `docs/starters/brownfield.md`, and their `.vi.md` pages.

R15. Unchanged: `strict` rigor keeps the per-track suite, the ledger, and a worktree per track; a project with `project.review_ledger: true` runs the same ledger commands as today; role policies in `team.approvals` are checked as today.

## User Stories

### US-1: The host enforces approvals
As a lead, I want gin to accept a merged pull request as approved, so that an approval given on the host or in person never blocks a gate.

Acceptance criteria:
- With `team.approvals.ship: host`, `gin record shipped --evidence <merged PR URL>` succeeds for a pull request nobody approved on the host.
- With the same config, an unmerged pull request is refused with one reason.
- `gin team pending` shows that pull request with the note `approvals: host` and nothing missing.
- A team with `team.approvals.ship: [be_lead]` still gets "missing approval" for an unapproved pull request.

### US-2: One shipped record for several repositories
As a developer who ships a standalone change across the parent and a child, I want to name both pull requests, so that the record proves the whole change.

Acceptance criteria:
- `gin record shipped --evidence <parent PR> --evidence <child PR>` records `pull_requests` with two entries and keeps `pr_url` of the first.
- Two URLs of the same repository are refused and nothing is recorded.

### US-3: Dependencies across repositories
As a member whose track waits for another member's track in a child, I want `gin team deps` to find that pull request, so that my track unblocks when it merges.

Acceptance criteria:
- With plan track 2 on `Repo: services/order-api` and its pull request merged there, `gin team deps` closes the placeholder `external: <plan>#2` and stores `repo: services/order-api`.
- With that child not cloned, the placeholder stays waiting and the output names `gin workspace clone services/order-api`.
- `gin team deps --bead <bead>` from a track in another repository passes when the merge commit is on `origin/main` of `services/order-api`.

### US-4: The suite runs once
As a maintainer, I want the full suite to run once per epic, so that a four-track epic does not spend an hour and a half on repeated runs.

Acceptance criteria:
- A `standard` project without `verify.run_at` reports `project.run_at: push`; a `strict` one reports `track`.
- With `push`, the execute and review skills ask for no `gin evidence run` per track, and ship asks for one before the merge.
- With `host`, `gin hooks run pre-push` runs no test command and exits 0.

### US-5: No ledger when it is off
As a maintainer of a project with `project.review_ledger: false`, I want reviews without ledger commands, so that a review is one reviewer run and a line in the bead.

Acceptance criteria:
- The review skill names `ledger.md` only for `project.review_ledger: true`, and its own text has no `init`, `checkpoint`, or `transition-requested` command.
- The execute skill asks for `push-refs` only with the ledger on.

### US-6: Rigor decides how much process a project gets
As a solo developer on `easy` rigor, I want no worktree, a self check, and tests at push, so that small work ships fast.

Acceptance criteria:
- The execute and orchestrate skills create track worktrees only for `project.worktree: always`, or `parallel` with a parallel execution strategy.
- The review skill does a self check for `project.review: self_check`.

## Errors and compatibility

- Existing configs stay valid: no key is removed, and `verify.run_at` and `host` are additions. The default behaviour changes for `easy` and `standard` projects (the suite at push instead of per track); `verify.run_at: track` restores it.
- `gin state --format json` gains `project.run_at`; the shipped proof gains `pull_requests`; `gin team pending` rows gain a note. Nothing is renamed or removed (gin-console reads only derived gates).
- With `host` approvals, a pull request merged without review passes; that is the host's branch protection to prevent.
- With `push`, a regression outside a track's own tests shows at ship, not after the track; with `host`, gin never sees test results.
- A failed `gin evidence run` at ship stops before any merge.
- `gin team deps` with a plan file that is missing in the checkout reports the placeholder as waiting with "pull the merged plan".

## Testing

- `tests/workflow_core/test_team_gates.py`: `host` for each gate (record, check, pending, waiver, kind map), role policies unchanged; `record shipped` with two URLs, a duplicate repository, one unmerged URL, and the proof shape.
- `tests/workflow_core/test_team_beads.py`: `deps` for a child (merged, not cloned, plan missing), `deps --bead` same repository and other repository.
- `tests/workflow_core/test_hooks.py`, `test_project_settings.py`, `test_lifecycle_cli.py`: `run_at` defaults by rigor, the explicit key, the pre-push hook with `host`, record reuse with `push`, `quick-check` output.
- `tests/workflow_core/test_skill_routing.py` and `test_token_budget.py`: the skill text per mode, the ledger reference, and the stage budgets (execute 11,914 and review 11,954 of 12,000 today).
- `gin docs check` on changed pages; the full suite once at ship.

## Open Technical Questions
