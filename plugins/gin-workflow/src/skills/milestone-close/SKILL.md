---
name: milestone-close
description: Close a milestone in one guided run. Summarise it, move open epics to the next milestone with reasons, record the result, apply actions.
---

# Milestone close

On `/milestone-close` only. Outside the lifecycle: it records no gate. One question per message. Write nothing until the person running the close confirms the table.

## Before you start
1. If `.agent-workflow/generated/effective-config.yaml` does not exist in the main checkout (the parent of `git rev-parse --path-format=absolute --git-common-dir`), stop: tell the user to run `/setup` once and do nothing else.
2. Milestones need the Beads task backend. With another backend, say so in one sentence and stop.
3. Read `gin state --format json`. In team mode, when `project.team.permissions.milestone` lists roles and none is in `project.team.me.roles`, or `project.team.me` is null, stop and name the roles (`team.permissions.milestone`). With `team.beads_sync` set in `.agent-workflow/config.yaml` of the main checkout, run `gin team sync` first.

## Milestone
With an id, use it. Otherwise use the only milestone whose `status` is `active` in `gin milestone list --json`; with none or several, list the open milestones (id, title, period, status) and ask which one. Run `gin milestone show <id> --json`; on a non-zero exit report its message and stop. When its `status` is `closed`, write nothing and say so. Before its `end`, say the close is early and ask whether to continue.

## Summary
Show, without writing:
- Delivered: the closed epics of the milestone.
- Open epics with `remaining_days`, and per epic the `count` of its `open_bugs` warning (0 without one).
- Per epic, `estimate_days` against the working days, Monday to Friday, from `started_at` to `closed_at` of `gin task show <epic> --json` (to today when open; `not started` without `started_at`).
- Cost and rework (reopens, bugs found later, review cycles) from `gin usage report --milestone <id> --format json`; on a non-zero exit, report it and continue without them.
- The milestone's `Outcome:` and `Demo:` from the roadmap file (`.planning/roadmap.md`, or `docs/roadmap.md` with `project.layout: sdd`); propose `reached`, `partial`, or `missed` for each with a one-line note, or `not planned` when the file or the line is missing.
- Retros: the newest `[gin retro]` comment per member from `gin task comments <id> --json`; with none, say `no retros`. Retros are optional.

## Metrics
Team level only, never per member. Compute from the data of the summary:
- `completion`: closed epics over all epics of the milestone at the start of this run, as `<closed>/<total>`.
- `estimate_accuracy`: the sum of `estimate_days` over the sum of actual working days, over the closed epics that have both; two decimals; 1.00 is on estimate, below 1 took longer; `n/a` without such an epic.
- `capacity_used`: the sum of `estimate_days` of the closed epics over `lanes` times the working days, Monday to Friday, from `start` to `end`, both ends included, no `away` days subtracted (`gin milestone show <id> --json`); two decimals; `n/a` without `lanes` or estimates.
- `cost_per_epic`: `totals.cost` of the usage report over the closed epics, in USD with two decimals, followed by ` partial` when the report's `partial` is true; `totals.cost` covers every epic of the milestone, open ones included; `n/a` when the report failed, `totals.cost` is null, or no epic closed.
- `rework`: the sum of `quality.reopens` and `quality.bugs` over the report's `beads` entries whose `parent` is not the `bead` of another entry, because an epic's `quality` already includes its children; `n/a` when the report failed.

Compare with the most recently closed milestone: in `gin milestone list --all --json`, the closed milestone with the latest `end` before this milestone's `start`; read the `Metrics:` line of its newest `[gin close]` comment and show the change of each metric. Without such a milestone, comment, or `Metrics:` line, say `no earlier metrics`.

## Next milestone
The next milestone is the open milestone in `gin milestone list --json` with the earliest `start` after this milestone's `start`. With none, propose a new one starting the first working day after this milestone's `end`, with the same number of working days, and ask the PM for its title; it is created in Write, after confirmation.

## Spillover
Every open epic moves to the next milestone. For each one:
1. Reason. Quote the retro line (`Slowed us:` or `Went well:`) that names the epic id or title, marked `retro`. Without one, ask the person running the close for the reason, one epic per message, marked `asked`.
2. Decision. Propose one: keep as is; re-estimate with new remaining days; split, done later with `/roadmap` or `/discuss <epic>`; or remove a named blocker.

When the moved epics take the next milestone over its capacity (the bound of the Load block of the roadmap skill's way of working), still move them; report the overflow in working days and propose what to do.

## Actions
From the summary, the retros, and the spillover, propose actions, each with a kind:
- `way_of_working`: the exact new text of a line in `## Way of working` of the roadmap file.
- `estimate`: an epic and its new days.
- `lesson`: a topic and a summary for a knowledge record.
- `remember`: a short fact every session needs; propose it, and keep it only when the PM chooses it.

## Confirm
Present one table: delivered epics; each spillover epic with its target milestone, reason (retro|asked), and decision; the `Outcome:` and `Demo:` results; the metrics and their change; the actions. Revise it until the person running the close confirms.

## Write
In this order, after confirmation. A failing step stops the run; report what was written. A re-run continues: moved epics are no longer in the milestone, and a closed milestone is refused, so after a stop past step 5 finish the rest by hand from the report.
1. When proposed, `gin milestone create "<title>" --start <date> --end <date>`; it prints the new id.
2. `gin milestone move <epic>... --to <next-id>` for the spillover epics.
3. `gin milestone estimate <epic> <days>` for each `estimate` action.
4. `gin task comment <milestone-id> "<text>"` with this text:
   ```
   [gin close] <milestone-id>
   Delivered: <epic-id>, <epic-id>
   Spillover: <epic-id> -> <milestone-id>; reason (retro|asked): <text>; decision: <text>
   Outcome: reached|partial|missed|not planned; <note>
   Demo: reached|partial|missed|not planned; <note>
   Retros: <count>
   Metrics: completion <closed>/<total>; estimate_accuracy <n.nn|n/a>; capacity_used <n.nn|n/a>; cost_per_epic <n.nn[ partial]|n/a>; rework <n|n/a>
   Action: way_of_working|estimate|lesson|remember; <text>
   ```
   `Delivered:` is `none` when no epic closed. One `Spillover:` line per moved epic and one `Action:` line per action; none when there are none. Replace line breaks inside a value with `; `. Never translate the labels: gin-console and later runs parse them.
5. `gin milestone close <milestone-id> --reason "Delivered <n> of <m> epics; <k> moved to <next-id>"`.
6. On branch `milestone-close/<milestone-id>` of the main checkout's repository: in the roadmap file, write the milestone's `Result:` block and apply each `way_of_working` action to `## Way of working`; write or update each `lesson` as `.planning/knowledge/<topic>.md` following the Reconcile steps of the `learn` skill (search first, update instead of duplicating); commit. When `team.approvals.roadmap` in `.agent-workflow/config.yaml` lists roles, push and open the pull request as `/roadmap` step 5 does. Without a roadmap file, skip `Result:` and the way-of-working actions and say so; still write the lessons. The `Result:` block, in business words and without file paths:
   ```
   Result: closed <YYYY-MM-DD>; delivered <n> of <m> epics; <k> moved to <next milestone title>
   - Outcome: <reached|partial|missed|not planned>; <note>
   - Demo: <reached|partial|missed|not planned>; <note>
   - Metrics: <closed> of <total> epics done (<percent>%); estimates <accuracy as percent> accurate; <capacity_used as percent> of capacity used; <cost> USD per epic; <rework> reworks
   - Spillover: <epic title>: <reason>; <decision>
   - Actions: <one line per action>
   ```
7. `gin task remember "<fact>"` for each `remember` action the PM chose.
8. With `team.beads_sync` set, `gin team sync`.

## Report
The closed milestone, the metrics with their change, the next milestone and its load, each moved epic with its decision, the actions applied, the branch and commit (and pull request), and anything skipped. Next steps: `/progress --milestone <next-id>`, and `/roadmap` or `/discuss <epic>` for each epic to split.
