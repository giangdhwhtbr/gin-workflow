---
name: progress
description: Report Beads task status, blockers, open waivers, and next ready work without mutating anything.
---

## Before you start
1. If `.agent-workflow/generated/effective-config.yaml` does not exist in the main checkout (the parent of `git rev-parse --path-format=absolute --git-common-dir`; linked worktrees have none), stop: tell the user to run `/setup` once and do nothing else. (`capabilities: {}` is a valid config.)
2. Read [references/stage-contract.md](../../references/stage-contract.md) now: it defines the gate CLI, valid evidence, approval, and git rules this stage relies on.

# Progress

Read-only status report.

1. Query Beads: `gin task list --status open,in_progress`, `gin task ready --exclude-label prep`, `gin task blocked`, and `gin task show <id>` for requested tasks. For a milestone: `gin task list --parent <milestone-id> --all --json` gives the epics; `gin task list --parent <epic> --all --json` gives each one's tracks. Children labelled `prep` are prep tasks: report them apart from the tracks, with assignee and status.
   - Milestone: with `--milestone <id>`, else the single milestone whose `status` is `active` in `gin milestone list --json`, run `gin milestone show <id> --json`. Start with two or three plain-language sentences: on track, or how many working days late (`overflow_days`), and what blocks it. Then show `deadline`, `finish`, `overflow_days`, `lanes`, and one line per epic with `status`, `spec_confirmed`, `remaining_days`, and `warnings`. With no or several active milestones and no `--milestone`, show the `forecast` line of `gin milestone list --json` and say why. On the markdown backend, or when a command exits non-zero, say milestone data is unavailable and give the error.
   - Grouping: group tracks by their `area:` label when `team.areas` is set, and in a workspace by the `Repo:` line of the track description. `--area <name>` or `--repo <path>` keeps only the matching tracks and their epics. List epics whose `depends_on` names an open epic of another area under "waiting on another area".
   - Approvals, in team mode only: run `gin team pending --format json` with the report's scope (`--workflow-id <id>` or `--milestone <id>`). List gate pull requests first (gate, epic, author, approvals, `missing`), then track pull requests. A row with `error` is shown as unknown with its error. Any non-zero exit, or every row with `error`, prints `approvals unknown: <cause>`.
   - Spec: per epic, show `spec_confirmed` (unknown when null), its open spec pull request, and with `project.layout: sdd` the output of `gin specs status --change <epic>` and any confirmed asset folder not committed. The spec pull request is the `gin team pending` row with gate `requirement_confirmed` for that epic; outside team mode, none is shown. If `gin specs status` fails, say spec status is unavailable for that epic.
   - QA state: run the QA state check of the `qa-track` skill when it applies; without it, say the QA state was skipped.
1a. Milestone: with `--milestone <id>`, else the single `active` milestone, run `gin milestone show <id> --json`. Start with two or three plain-language sentences: on track, or how many working days late (`overflow_days`), and what blocks it. Then show `deadline`, `finish`, `overflow_days`, `lanes`, and one line per epic with `status`, `spec_confirmed`, `remaining_days`, and `warnings`. Without a milestone, show the `forecast` line of `gin milestone list --json`. On the markdown backend, or when the command fails, say milestone data is unavailable and give the error.
1b. Group tracks by their `area:` label when `team.areas` is set, and in a workspace by the `Repo:` line of the track description. `--area <name>` or `--repo <path>` keeps only the matching tracks and their epics. List epics whose `depends_on` names an open epic of another area under "waiting on another area".
1c. Spec: per epic, show `spec_confirmed` (unknown when null), its open spec pull request from step 1d, and with `project.layout: sdd` the output of `gin specs status --change <epic>` and any confirmed asset folder not committed. If `gin specs status` fails, say spec status is unavailable for that epic.
1d. Approvals, in team mode only: run `gin team pending --format json` with the report's scope (`--workflow-id <id>` or `--milestone <id>`). List gate pull requests first (gate, epic, author, approvals, `missing`), then track pull requests. A row with `error` is shown as unknown with its error. Exit 2, or every row with `error`, prints `approvals unknown: <cause>`.
1e. QA state: run the QA state check of the `qa-track` skill when it applies; without it, say the QA state was skipped.
2. Group as Pending, Active, Complete, and Failed. Recommend active dependencies first, then ready work by priority, then root blockers.
3. Add review status (`python3 review-ledger.py status --bead-id <id>`) and gate state (`gin state --format json`) when relevant, and recent `/quick` runs (`recent_quick` in `gin state`).
4. Report open gate waivers (gates shown as `waived(<reason>)` by `gin state`) and check their follow-up tasks with `gin task show`, so waivers do not become a habit.
5. With Beads, for each open epic in the report, list each `[gin question] <track>:` comment (`gin task comments <epic> --json`) that has no newer `[gin answer] <track>:` comment, with its date and text, as open questions for the BA. The markdown backend has no comments.
6. Label worker and worktree details as derived runtime metadata, never authoritative state.
7. Return the report. Never mutate state or chain into another stage.
