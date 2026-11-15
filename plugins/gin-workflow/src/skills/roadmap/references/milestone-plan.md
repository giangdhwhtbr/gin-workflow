# Milestone plan: allocation in one run

Read on a plain `/roadmap` (no `--milestone`). With `--milestone`, read only the Estimates block.

## Estimates
List the closed `roadmap` epics with `gin task list --label roadmap --type epic --status closed --json`. Measure each from the `timestamp` of its earliest `requirement.confirmed` event (`workflow_id` is the epic) in `.agent-workflow/runtime/events.jsonl` of the main checkout to its `closed_at`. Without that event, start from the earliest `created_at` of its tracks (`gin task list --parent <epic> --all --json`); skip an epic with neither. Round each span up to whole working days, at least 1. When that list is empty (no measured pace), ask the PM for one day value per size, small, medium and large, assign one size per epic, and mark each `Estimate:` line `(assumed)` in the roadmap file. Otherwise never ask the PM for estimates; neither the size question nor an estimate revision counts against `project.max_questions`. Revise them on request.

## Plan
In step 2, ask once for the milestone plan: none; the open milestones of `gin milestone list --json`; or a list from the PM with a title, a start, and an end per milestone. The question does not count against `project.max_questions`. With none, only the Estimates block applies.

## Allocation
In step 4, present one table with, per milestone: its period, its capacity (the bound of the Load block of [way of working](way-of-working.md)), `Outcome:`, `Demo:`, its epics with their estimates, and the sum of those estimates.

Candidates follow the adoption rule of `--milestone` step 3: `open` or `in_progress` `roadmap` epics with no `parent`, plus the epics this run creates, never a closed one; an `in_progress` epic counts its remaining working days.

Fill the milestones in `end` order by dependency layer:
- Epics with no open blocker go first.
- An epic never goes into a milestone that ends before the milestone of an epic it depends on.
- Foundation epics go into the first milestone; those over its capacity go first into the next one.
- Stop filling a milestone when the sum of its estimates reaches its capacity.

When the PM states the demo of a milestone first, the epics that demo needs go into that milestone or an earlier one; name each one that does not fit. An epic that fits no milestone stays under `## Unassigned` with the reason (blocked, or over capacity). When the last milestone with epics ends after `Deadline:`, name the overflow in working days.

## Write
In step 5, after the PM confirms and before the file is written, run the team permission check of `--milestone` step 1, then `gin milestone create "<title>" --start <date> --end <date>` for each milestone of the plan whose title `gin milestone list --json` lacks; it prints the new id. A failure stops before the file is written; report it as in `--milestone` step 5. A created milestone holds no epic until step 6, so a rejected roadmap PR leaves only empty milestones, which the next run reuses by title. Step 5 then writes each milestone block as `--milestone` step 4 describes.

In step 6, after the sync, and after the roadmap PR merges when `team.approvals.roadmap` has a policy, run per milestone `gin milestone move <epic>... --to <id>` for its epics that have no milestone in Beads, then `gin milestone estimate <epic> <days>` under the estimates rule of step 6. Failures follow `--milestone` step 5.

The adopted-epic rule of step 6 covers only epics that existed before this run: an epic the sync creates in this run gets its title, description, and `Depends on:` dependencies, and an existing `open` epic the plan allocates keeps its bead unchanged, as with `--milestone`.

## Re-run
Beads wins for membership and estimates. Compare each milestone's `gin milestone show <id> --json` with the file and report each difference without writing Beads. Propose an allocation only for the candidates of the Allocation block. `/roadmap --milestone <id>` changes one milestone later.
