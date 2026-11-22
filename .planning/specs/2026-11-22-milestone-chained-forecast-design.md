# Milestone chained forecast

Epic: gin-workflow-6yoq
Kind: capability
Status: draft for user review.

## Goal and scope

gin-console plans a project timeline (`gin-console-rm-project-timeline`, Milestones page, Timeline view) that puts every milestone and epic of a project on one time axis. It depends on `external:gin-workflow:milestone-chained-forecast`.

`gin milestone list --json` already chains the work: `forecast()` (`workflow_core/milestone.py:502-549`) places the open milestones in `end` order, each from `max(cursor, kickoff or start)` on its own lanes, then the open roadmap epics outside an open milestone on the default lanes, and moves the cursor to the working day after each group's last end. It returns only `finish` and `overflow_days`; the per-epic dates `_place()` computes are dropped, and `_place()` does not return the lane it picks. Stitching `gin milestone show` per milestone restarts each milestone at its own kickoff, so a late milestone does not push the next one, and epics outside a milestone get no dates.

This epic adds the chained dates to the `forecast` object, additively, from the same placement and warning rules.

Decided in discuss (2026-11-22):

- Only open epics labelled `roadmap` get chained dates: the set `forecast.finish`, `forecast.open_epics`, and `unassigned_epics` already count.
- The chained data lives in `forecast` as `forecast.milestones` and `forecast.epics`; the entries of the top-level `milestones` keep their meaning (each milestone's own schedule from its kickoff).
- The JSON contract is recorded in both `docs/reference/cli.md` and the gin-console contract `gin-harness/docs/changes/gin-harness-6s4-milestones/design.md`; the gin-harness change is committed only with the user's approval at ship.

In scope: the two new keys, the lane returned by `_place()`, the warning rules shared by `show` and the forecast, tests, and the two docs.

Out of scope:

- `lane` on `gin milestone show` rows.
- Text output of `gin milestone list` and `show`.
- Honouring `blocks` dependencies between groups in the schedule (today they only warn).
- gin-console parsing and drawing the timeline.

Assumptions:

- Chained dates are a forecast of the remaining work: they start from today and place open epics only, so they differ from `show` dates of an active milestone, which places closed epics from the kickoff.
- `lane` counts from 1 within the lanes of the epic's group; with lanes from building members, lane n is the n-th member, as in `show`.

## Requirements

1. `_place()` returns `(start, end, lane)` per epic. `lane` is the 1-based index of the lane the epic takes; it is null for an epic placed without days. `schedule()` and `forecast()` read the new shape; the output of `gin milestone show` does not change.
2. The epic warnings of `schedule()` (`milestone.py:405-425`) move into one helper used by `schedule()` and `forecast()`. It takes the epic, its planned end, the group it was placed in, and the milestone context (`end`, `integration`, status, working days of the period, spec readiness), which is absent for the group outside milestones. Without a milestone context it reports only `unestimated`, `external_blocker`, and `open_bugs`.
3. `forecast()` takes `confirmed` (the set `list_payload()` already receives) and adds `forecast.milestones`: one entry per open milestone in chain order (`end`, then `id`), each `{id, start, finish, overflow_days}`:
   - `start`: the working day its group was placed from, `max(cursor, kickoff or start)`.
   - `finish`: the latest `planned_end` of its epics.
   - `overflow_days`: working days after the milestone's `end` up to and including `finish`.
   - `start` and `finish` are null and `overflow_days` is 0 when the milestone has no open roadmap epic, or when `forecast.error` stopped the chain at or before it.
4. `forecast()` adds `forecast.epics`: one row per open roadmap epic it placed, ordered by `planned_start`, then `id`, each `{id, title, status, milestone, lane, planned_start, planned_end, remaining_days, estimate_source, warnings}`:
   - `milestone`: the id of the open milestone the epic was placed in; null for the group outside milestones, which includes epics under a closed milestone.
   - `remaining_days` and `estimate_source` (`points`, `days`, `assumed`) as on `show` rows.
   - `warnings`: objects with the codes and fields of `show` (`overflow` with `days`, `late`, `unestimated`, `external_blocker`, `spec_due`, `spec_not_ready`, `after_integration`, `open_bugs` with `count`, `oversized` with `days`), computed against the chained dates; `external_blocker` counts a `blocks` dependency on any bead outside the epic's group that is not closed.
5. Existing keys of `forecast`, of the top-level `milestones` entries, and of the payload keep their names and values; `schema` stays 1. `forecast.finish` equals the latest `planned_end` in `forecast.epics`, and `forecast.open_epics` equals its length when no error stopped the chain.
6. `docs/reference/cli.md` (the `gin milestone` section) describes `forecast.milestones` and `forecast.epics`. The JSON contract in `gin-harness/docs/changes/gin-harness-6s4-milestones/design.md` gains a row per new key and the note that gin-workflow-6yoq added them; a gin-workflow before it omits them.

## User Stories

### US-1: One chained timeline
As a PM, I want every open roadmap epic of my project to have chained planned dates, so that the gin-console timeline shows milestones and the epics outside them on one time axis.

Acceptance criteria:
- `gin milestone list --all --json` lists every open roadmap epic in `forecast.epics` with `planned_start`, `planned_end`, `lane`, and `milestone`.
- An open roadmap epic without a milestone parent appears with `milestone: null`, placed after the last open milestone, on the default lanes.
- An open roadmap epic under a closed milestone appears with `milestone: null`.
- Two independent epics of a milestone with 2 lanes share a `planned_start` and take lanes 1 and 2.

### US-2: Late milestones push the next
As a PM, I want a milestone forecast to finish late to push the next milestone's epics, so that the timeline shows the real knock-on delay.

Acceptance criteria:
- When a milestone's epics end 2 working days after its `end`, its `forecast.milestones` entry has `overflow_days: 2`, and its epics carry the `overflow` warning with `days`.
- The next milestone's `start` and the `planned_start` of its first epic are the working day after the late milestone's `finish`.
- A milestone with no open roadmap epic is listed with null `start` and `finish` and does not move the cursor.

### US-3: A stable contract for gin-console
As a gin-console developer, I want the new fields added without changing existing ones, so that the current parser keeps working and the timeline reads one documented contract.

Acceptance criteria:
- The keys and values of the existing `forecast` object and of each top-level `milestones` entry are the same as before for the same Beads data.
- `gin milestone show` output is unchanged for the same Beads data.
- `docs/reference/cli.md` and the gin-harness contract list every new key.

## Errors and compatibility

| Condition | Result |
|---|---|
| Dependency cycle or bad milestone metadata in the group of milestone k | `forecast.error` as today; groups placed before k keep their epic rows and milestone dates; milestones from k on have null `start` and `finish` and no epic rows; exit 0 |
| Malformed roadmap `Deadline:` | `forecast.error` as today; the chain is placed in full |
| Open milestone with no open roadmap epic, with or without `start`/`end` metadata | Listed in `forecast.milestones` with null `start` and `finish`, `overflow_days` 0 |
| Unreadable event log | `confirmed` is null; no `spec_due` or `spec_not_ready`, as on `show` |
| Malformed `away` or `integration` metadata | Ignored with the existing stderr warning |
| No open roadmap epic | `forecast` is null, as today |

Compatibility: only keys are added. gin-console's pydantic models ignore unknown keys, so its current parser keeps working. In the forecast a group holds only the open roadmap epics, so a `blocks` dependency on an open epic of the same milestone that lacks the `roadmap` label shows as `external_blocker` there, while `show` lists it in `depends_on`.

## Testing

Unit tests in `tests/workflow_core/test_milestone.py` call `forecast()` and `list_payload()` with a fixed today; CLI tests in `tests/workflow_core/test_milestone_cli.py` run `gin milestone list --all --json` on a temporary Beads database.

- Spillover: milestone m1 on 1 lane ends 2 working days late; `overflow_days`, the `overflow` warning, and m2's `start` and first `planned_start` match US-2.
- Outside milestones: an unparented roadmap epic and one under a closed milestone get dates after the last milestone, `milestone: null`, and lanes from the default lanes.
- Lanes: two independent epics on a 2-lane milestone take lanes 1 and 2 on the same day.
- Consistency: `forecast.finish` equals the latest `planned_end`; `open_epics` equals the row count; the existing keys of `forecast` and of the `milestones` entries are unchanged.
- Error mid-chain: a cycle in m2 keeps m1's rows and dates, gives m2 null dates and no rows, and names the cycle in `error`.
- Empty milestone: listed with null dates and `overflow_days` 0.
- Warnings: `overflow` from chained dates; `external_blocker` across groups; no milestone-only warning on epics outside milestones; `spec_not_ready` for an unconfirmed epic of an active milestone.
- `show`: the existing `schedule()` and `show` tests pass unchanged after the helper split and the `_place()` change.
- CLI: the JSON has `forecast.milestones` and `forecast.epics` with every key and `schema: 1`.

## Open Technical Questions
