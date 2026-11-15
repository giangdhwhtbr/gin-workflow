# Quick in team mode

Epic: gin-workflow-quick-team
Kind: capability
Status: draft for user review.

## Goal and scope

In team mode (`project.team.enabled`), a `/gin:quick` change has no path to the protected base branch: quick commits on `quick/<slug>` and never pushes (`plugins/gin-workflow/src/references/stage-contract.md:34`, `docs/concepts/lifecycle.md:125`), no one approves it, QA does not know which cases cover it, and the PM cannot see quick runs because `quick.completed` lives only in the local `.agent-workflow/runtime/events.jsonl` (`lifecycle_cli.py:570-574`). Raised by PM-16, QA-18, BE-LEAD-17, and FE-LEAD-18 (`.planning/reviews/2026-11-07-process-review/synthesis.md`).

In scope:

- The team-mode end of `/gin:quick`: push, a pull request with covering cases and an approval reminder, a `[gin quick]` comment on an epic or milestone, and `gin team sync`.
- Covering QA cases by capability.
- `gin team pending` lists open pull requests of `quick/*` branches.
- `/gin:progress` and `/gin:milestone-close` read the `[gin quick]` comments.
- The stage contract, lifecycle concept page, team guide, and skills reference.

Out of scope:

- Solo mode, which keeps commit without push.
- Merging: the person who merges runs `gin team check --gate ship <pr-url>`, as for a track.
- A file-path lookup of QA cases in gin-qa.
- A bead per quick run, or quick runs in milestone capacity numbers.
- A quick change across two repositories (still two quick runs, or the full lifecycle).
- gin-console (it can read the comments through its bead comments API later).

Assumptions:

- `gin team check --gate ship <pr-url>` needs no epic (`team.py:466-`, `verify_gate`), so a quick pull request is checked like a track pull request.
- The team-mode end applies only when quick created `quick/<slug>` (started on `main`/`master`). A quick run on an existing feature branch commits there and does not push: its branch's own flow carries it.
- In a workspace, the pull request targets the child repository's default branch, as track pull requests do since `gin-workflow-ws-branch-model`.

Summary confirmed with the user on 2026-11-15: the roadmap goal stands; `gin-workflow-ws-branch-model` shipped (merge 3def56c2) with the rule that a child pull request targets the child's default branch; the ship check works without an epic; `quick/*` pull requests are invisible to `gin team pending`; gin-qa looks up cases only by capability or REQ; a bead under an epic would change its gates, so quick runs are recorded as comments.

Comments considered: 1, latest 2026-11-15T00:27:58Z

## Requirements

### Command

- `/gin:quick [--epic <id> | --milestone <id>]`. The option names where the `[gin quick]` comment goes. Without it, in team mode, the comment goes to the only milestone whose `status` is `active` in `gin milestone list --json`; with none or several, no comment is written and the report says so.
- `gin quick-check` and the steps before the commit do not change.

### Team-mode end

Applies when `project.team.enabled` is true and quick created `quick/<slug>`. It replaces "do not push":

1. Commit on `quick/<slug>`.
2. Propose the capabilities the change touches, from the changed files and the Capability Map of `13-CAPABILITIES.md` or the capability folders of `docs/specs/` when present; the member confirms or corrects them. With `gin-qa` on `PATH`, run `gin-qa cases export --format json` from the QA home and keep the `id` and `title` of each case whose `capability` is a confirmed capability (`gin-qa cases plan` lists missing and stale work, not covering cases). Without `gin-qa`, without a capability, or on a non-zero exit, the result is `no covering cases found` with the reason.
3. Push `quick/<slug>` to `origin`. The pre-push hook runs as configured.
4. Open the pull request with the `team.host` command of `team/references/hosts.md`; in a workspace child, against the child's default branch. The description, passed with the host CLI's body or description option (for example `--body` for `gh`, `--description` for `glab`), holds: the summary, the verify commands and their results, the covering cases (or `no covering cases found` and why), and the line `Needs ship approval: run gin team check --gate ship <pr-url> before merging.`
5. Write the `[gin quick]` comment (below) with `gin task comment <epic-or-milestone-id> "<text>"`.
6. `gin record quick-completed` with the pull request URL in `--evidence`.
7. With `team.beads_sync` set, `gin team sync`.

A failed push or pull request stops the run with the error; the commit stays on `quick/<slug>`, and nothing after the failed step is written. A failed comment is reported and the run continues.

### The `[gin quick]` comment

```
[gin quick] <branch> <pr-url>
Summary: <one line>
Files: <count>
Author: <git email>
Cases: <case-id>, <case-id> | none
```

The labels are English and never translated.

### Pending approvals

- `gin team pending` adds a candidate for each remote `quick/*` head with an open pull request: gate `ship`, epic `null`, `approvals` and `missing` under the ship policy, as for a `feat/<topic>` row. Without a ship policy, quick rows show no `missing`.
- `--workflow-id` and `--milestone` filters leave quick rows out (they have no epic); the unfiltered list includes them.
- `docs/reference/cli.md` documents the `quick/*` rows.

### Readers

- `/gin:progress`, for the milestone in view: lists the `[gin quick]` comments of the milestone bead and of its epics (branch, pull request, author, date).
- `/gin:milestone-close`: the summary shows the number of quick runs of the milestone and its epics. The `[gin close]` format does not change.

### Documentation

- `stage-contract.md:34`: quick does not push, except in team mode on a `quick/<slug>` branch, where it pushes and opens a pull request.
- `docs/concepts/lifecycle.md` (the quick path), `docs/guides/team.md`, and the `quick` row of `docs/reference/skills.md` and `.vi.md` describe the team-mode end.

## User Stories

### US-1: Get a quick change reviewed and merged in a team
As a developer in team mode, I want `/gin:quick` to push my branch and open a pull request, so that a small change reaches the protected base branch through the team's approval.

Acceptance criteria:
- In team mode, after a quick run started on the base branch, `quick/<slug>` exists on `origin` and an open pull request targets the base branch (in a workspace child, the child's default branch).
- The pull request description has the summary, the verify results, the covering cases, and the ship approval line.
- In solo mode, quick still commits without pushing.
- A quick run on an existing feature branch commits there and does not push.

### US-2: Know which cases cover a quick change
As a QA member, I want the quick pull request to list the cases that cover the changed capability, so that I know what to re-run before I approve.

Acceptance criteria:
- The member confirms the capabilities before the cases are looked up.
- With gin-qa and a confirmed capability, the description lists the ids and titles of the cases of that capability from `gin-qa cases export`.
- Otherwise it says `no covering cases found` and why.

### US-3: See quick pull requests waiting for approval
As a lead, I want `gin team pending` to show open quick pull requests, so that they get approved like track pull requests.

Acceptance criteria:
- An open pull request of a `quick/*` branch appears with gate `ship`, no epic, and its approvals and missing roles.
- `gin team pending --workflow-id <epic>` and `--milestone <id>` do not list quick rows.

### US-4: See quick runs in progress and at the close
As a PM, I want quick runs recorded on the epic or milestone, so that progress and the milestone close show the work they took.

Acceptance criteria:
- After a team-mode quick run with an active milestone, the milestone bead has one `[gin quick]` comment in the format above.
- `--epic <id>` puts the comment on that epic instead.
- `/gin:progress --milestone <id>` lists the milestone's quick runs.
- `/gin:milestone-close` shows the number of quick runs.
- No bead is created, and the epic's gates and the milestone schedule do not change.

## Errors and compatibility

- Solo mode and quick runs on a feature branch behave as today.
- `gin-qa cases export` lists cases in every layout, so covering cases do not need `project.layout: sdd`.
- `gin team pending` JSON gains rows with `epic: null`; consumers that assumed an epic must accept null (gin-console does not read `team pending`; the team skill and `/progress` do).
- No new labels for beads; `[gin quick]` is a comment convention like `[gin retro]`.
- Budgets: the quick chain is 5,404 of 8,000 characters and the progress chain 6,944 of 12,000 (`tests/workflow_core/test_token_budget.py`); `team/SKILL.md` (5,984 of 6,000) is not changed.

## Testing

- Skill test on `skills/quick/SKILL.md`: the team-mode end, the `[gin quick]` first line and labels, the ship approval line, the capability confirmation before `gin-qa cases plan`, the solo and feature-branch exceptions, and `gin team sync`.
- `tests/workflow_core/test_team_pending.py` (or the existing team pending test file): a remote `quick/*` head with an open pull request gives a `ship` row with `epic` null and the ship policy's missing roles; filters leave it out; no row without an open pull request.
- Skill tests for `/progress` and `/milestone-close` reading `[gin quick]`.
- The stage contract sentence, docs tests, and the quick and progress chain budgets.

## Open Technical Questions
