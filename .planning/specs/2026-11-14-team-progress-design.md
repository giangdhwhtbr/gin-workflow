# Progress views and usage totals for a team

Epic: gin-workflow-team-progress
Kind: capability
Status: draft for user review.

## Goal and scope

`/gin:progress` shows a team the milestone forecast, pending approvals, spec status, QA state, and grouping by area or repository, in text; `gin usage report` says when an epic's usage total is partial and why.

Problem (process review `.planning/reviews/2026-11-07-process-review/synthesis.md:147-157`): PM-11 (pending approvals per role and member), PM-14 (milestone schedule, warnings, and forecast with a plain-language summary), PM-15 (team usage totals), BA-16 (spec view per epic), QA-19 (QA state per epic), BE-LEAD-18 (grouping by area or repository, open track pull requests and their approvals), FE-LEAD-19 (an area filter and the epics waiting on another area). Checked on master `6839756c`:
- `plugins/gin-workflow/src/skills/progress/SKILL.md` (2,005 characters; the progress chain is 4,897 of 12,000) reports task status, prep tasks, review state, gates, waivers, unanswered `[gin question]` comments, and recent quick runs; it never calls `gin milestone`, and it shows no approvals, spec status per epic, QA state, or grouping.
- `gin milestone show <id> --json` already returns `deadline`, `finish`, `overflow_days`, `lanes`, and per epic `status`, `remaining_days`, `spec_confirmed`, `depends_on`, `external_depends_on`, and `warnings` (`late`, `spec_not_ready`, `spec_due`, `oversized`, `unestimated`, `external_blocker`, `after_integration`, `open_bugs`, `overflow`) (`workflow_core/milestone.py:293-363`); `gin milestone list --json` returns the project `forecast` (`milestone.py:372-451`).
- A gate's pull request is recorded only after the gate is proven (`team_beads.py:483-488`, `lifecycle_cli.py:221-231`); nothing stores an open pull request. Host adapters can look up a pull request only by branch name: `pr_for_branch(branch, cwd)` returns the newest pull request of any state (`hosts/base.py:34`), and `PrInfo` has no creation date (`team_host.py:23-33`). Only the spec pull request has a lookup command, `gin specs status --change` (`specs_trace.py:74-97`). `team.check_approval` (`team.py:465`) computes what a pull request still needs for a gate.
- Branch names: spec `spec/<topic>` (`spec/<epic>-<slug>` with the SDD layout), plan `plan/<topic>`, tracks `feat/<topic>-t<N>` with `<topic>` from the plan file name (`skills/team/SKILL.md:17,21,34`); track beads carry `Plan: <path>, Track <N>` and `Area:`/`Repo:` lines, and tracks carry `area:<name>` labels.
- QA data comes from gin-qa: `gin-qa cases plan --change <epic> --format json` gives `missing` and `stale` cases, `gin-qa cases export --format json` gives each case's `result` (`plugins/gin-qa/src/scripts/gin_qa/cli.py:111-129,191,252`; `cases.py:25,503-516`). Core files may not name gin-qa except `skills/qa-track/SKILL.md` (`tests/gin_qa/test_packaging.py:82-88`).
- `gin usage collect` overwrites a bead's `ai_usage` from the local logs only (`usage.py:~310-367`); `gin usage report` counts only top-level summaries in scope and lists `not_collected` beads (`usage.py:389-436`), so an epic summary hides a child's separately collected summary and a member's runs on another machine. Summaries carry no record identity, so they cannot be merged without double counting.
- gin-console already shows the forecast, the Gantt view, spec confirmation, usage tables, and team KPIs from stored data; it shows no pending approvals, QA state, or area grouping (`gin-console/frontend/src/features/{milestones,reports}/`).

In scope:
- Report sections in the progress skill, in text.
- A new `gin team pending` command.
- A `partial` marker in `gin usage report`.
- A QA state section in the `qa-track` skill.
- Docs.

Out of scope:
- The forecast computation (`gin-workflow-milestone-gates`).
- The age of a pull request (no creation date in `PrInfo`).
- Merging usage summaries collected on different machines.
- gin-console changes; the stored `ai_usage` format does not change.

Confirmed decisions (user, 2026-11-14): progress covers every section in text and gin-console stays the visual view; pending approvals come from a new command without pull request age; usage gets a `partial` marker with reasons instead of a merge; QA state goes through the `qa-track` skill.

Comments considered: 1, latest 2026-11-10T06:16:19Z
Confirmed summary (user, 2026-11-14): the goal and scope above; `gin-workflow-milestone-gates` shipped shared gate state and the forecast (`gin milestone show`), so this epic presents that data; since the roadmap entry, progress already reports prep tasks and unanswered questions, `/gin:report` exists, gin-console shows forecast and usage visually, and the progress chain has about 7,100 characters left.

## Requirements

R1. Milestone section. When the report has a milestone (`/gin:progress --milestone <id>`, else the milestone whose status is `active`, if exactly one), progress reads `gin milestone show <id> --json` and prints:
- two or three plain-language sentences for a non-technical reader (on track or how many working days late, what blocks it);
- the deadline, the forecast finish, the overflow days, and the lanes;
- one line per epic: id, title, status, `spec_confirmed`, remaining days, and its warnings.
Without a milestone, progress prints the project forecast line from `gin milestone list --json`. With the markdown backend (no milestone data), it says so in one sentence.

R2. Grouping and filters.
- With `team.areas`, tracks are grouped by their `area:` label; in a workspace, by the `Repo:` line of the track bead description.
- `/gin:progress --area <name>` or `--repo <path>` keeps only the matching tracks and their epics.
- An epic whose `depends_on` names an open epic whose tracks belong to another area is listed under "waiting on another area".

R3. Spec status per epic. Each epic line shows `spec_confirmed`, the open spec pull request from R4 when there is one, and, with the SDD layout, `gin specs status --change <epic>` and any confirmed asset folder that is not committed.

R4. `gin team pending [--workflow-id <epic> | --milestone <id>] [--format json]`:
- Team mode only; otherwise exit 2 with `team mode is off`.
- Candidate branches: the remote heads `spec/*` and `plan/*` (`git ls-remote --heads origin`); `feat/<topic>-t<N>` of each open track bead, `<topic>` from the plan file named on its `Plan:` line; and `feat/<topic>` when `team.approvals.ship` has roles.
- For each candidate, `pr_for_branch`; only `open` pull requests are kept.
- Gate from the branch: `spec/` is `requirement_confirmed`, `plan/` is `plan_approved`, `feat/<topic>` is `ship`, and `feat/<topic>-t<N>` is a track pull request with no gate.
- Epic: for a spec or plan pull request, the `Epic:` or `Workflow:` line of the spec or plan file it changes, read from that branch; for a track pull request, the track bead's epic.
- Missing roles: `team.check_approval` with the policy for the epic's kind, the author's approval excluded, and its sole-holder notes; a track pull request lists its approvers only.
- Rows: `gate`, `branch`, `url`, `author`, `epic`, `approvals` (logins), `missing` (the reasons `gin team check` gives for that pull request, which name the roles still missing; empty when the policy is met), `notes`, and `error` when one lookup failed. `--workflow-id` and `--milestone` keep the rows of those epics. The text form groups rows by gate.
- Exit 0 with rows (possibly none); exit 2 when the host CLI is missing or unavailable or `git ls-remote` fails, naming the cause.

R5. Pending approvals in progress. In team mode, progress runs `gin team pending` with the report's scope and lists each open gate pull request with its epic, author, approvals, and missing roles, then the open track pull requests. On exit 2 it prints `approvals unknown: <cause>`. Outside team mode it prints nothing for this section.

R6. QA state. A new `## QA state` section in `skills/qa-track/SKILL.md`: with gin-qa on PATH and `project.layout: sdd`, from the QA home, per epic of the report, `gin-qa cases plan --change <epic> --format json` gives the `missing` and `stale` counts and `gin-qa cases export --format json` the `failed` and `blocked` counts of the cases linked to the change's REQ-IDs; the latest run folder is shown only when a gin-qa command returns it. Without gin-qa, without the SDD layout, or on exit 2, progress prints `QA state skipped: <reason>`. The progress skill names the section with the same conditional wording ship uses for its QA check, so the qa-track skill stays out of the progress chain.

R7. Usage partial marker. `gin usage report` (JSON and text) adds `partial` (bool) and `partial_reasons` (list), true when any of these holds for the beads in scope:
- `children_not_merged`: an epic has a summary and a direct child has its own summary that the epic summary does not include;
- `not_collected`: a bead in scope has no `ai_usage`;
- `unattributed`: unattributed tokens are above 0;
- `log_sources`: a log source status is not a clean scan, or `skipped_lines` is above 0;
- `stale`: an epic's `collected_at` is older than the latest `closed_at` of its direct children;
- `unpriced`: a model has no price.
The text form prints `partial: <reasons>`. `/gin:report` shows it next to the totals. The stored `ai_usage` format does not change.

R8. Unchanged. Progress keeps its current sections (task status, prep tasks, review state, gates, waivers, unanswered questions, recent quick runs), stays read-only, and never chains into another stage.

R9. Docs. `docs/reference/cli.md` (`gin team pending`, the `partial` fields of `gin usage report`), `docs/guides/usage-report.md` and its `.vi.md` (partial totals), `docs/guides/team.md` and `.vi.md` (pending approvals), `docs/reference/skills.md` and `.vi.md` (the progress row if its description changes), and `docs/concepts/lifecycle.md` where it describes progress.

## User Stories

### US-1: The PM reads the sprint in one place
As a PM, I want `/gin:progress --milestone <id>` to tell me in plain words whether the sprint is on track and which epics are late or lack a confirmed spec, so that I can report to stakeholders without opening the console.

Acceptance criteria:
- The report starts with two or three plain-language sentences, then the deadline, the forecast finish, and the overflow days from `gin milestone show`.
- Each epic line shows its status, `spec_confirmed`, remaining days, and warnings.

### US-2: Leads see who must approve what
As a lead in team mode, I want the open gate pull requests with the roles still missing, so that the right person approves next.

Acceptance criteria:
- `gin team pending --format json` lists an open `spec/` pull request as `requirement_confirmed` with its epic, author, approvals, and missing roles computed by the epic kind's policy.
- An open `plan/` pull request is listed as `plan_approved`; an open track pull request lists its approvers and no gate.
- A missing host CLI gives exit 2 naming it, and progress prints `approvals unknown: <cause>`.
- Outside team mode, `gin team pending` exits 2 with `team mode is off`.

### US-3: Area and repository views
As an area lead, I want my area's tracks and the epics waiting on another area, so that I see my work and my dependencies.

Acceptance criteria:
- `/gin:progress --area backend` keeps only tracks labelled `area:backend` and their epics.
- An epic that depends on an open epic of another area is listed under "waiting on another area".

### US-4: QA and spec state per epic
As a BA or QA, I want each epic's spec state and QA counts, so that I know what to write or test next.

Acceptance criteria:
- With the SDD layout and gin-qa, each epic shows its missing, stale, failed, and blocked case counts.
- Without gin-qa, progress prints `QA state skipped: <reason>`.
- Each epic shows `spec_confirmed` and its open spec pull request when there is one.

### US-5: Usage totals say when they are partial
As a PM, I want the usage report to say when a total misses runs, so that I do not report a low number as the team's cost.

Acceptance criteria:
- An epic with a summary and a child with its own summary reports `partial: true` with `children_not_merged`.
- A report with no reason reports `partial: false`.
- The stored `ai_usage` of a bead is unchanged after `gin usage report`.

## Errors and compatibility

- Solo projects: progress prints no approvals section; everything else works from the Beads backend; with the markdown backend, the milestone and QA sections say they are unavailable in one sentence each.
- Host failures never stop progress; they become `approvals unknown: <cause>`.
- `gin team pending` makes one `git ls-remote` and one host call per candidate branch; on Gitea, `pr_for_branch` scans the newest 500 pull requests.
- `gin usage report` JSON gains two keys; consumers that ignore unknown keys (gin-console) are unaffected.
- No gin-qa text outside `skills/qa-track/SKILL.md`.

## Testing

- `tests/workflow_core/test_team_*.py` (new cases with the host fakes in `fake_cli`): candidate branches from remote heads and track beads; gate from the branch; epic from the spec or plan file; missing roles by kind; track pull requests; filters; team mode off; host missing; one failed lookup.
- `tests/workflow_core/test_usage.py` / `test_usage_cli.py`: each partial reason and the no-reason case; stored `ai_usage` unchanged.
- `tests/workflow_core/test_skill_routing.py`: the new progress lines (milestone, grouping, approvals, QA state, unchanged sections) and the qa-track `## QA state` section; `tests/gin_qa/test_packaging.py` still passes.
- `tests/workflow_core/test_token_budget.py`: the progress chain stays within 12,000 and qa-track within 6,000.
- `gin docs check` on changed pages; full suite `python3 -m pytest -n auto`.

## Open Technical Questions
