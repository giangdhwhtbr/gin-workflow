# Milestone capacity model, exit criteria, and split warnings

Epic: gin-workflow-milestone-capacity
Status: confirmed by the user on 2026-11-10.

## Goal and scope

The roadmap bound and the `gin milestone` schedule use one capacity model: default lanes count only members who build, member days off reduce their lane, and QA counts in the Load bound. A milestone stores an integration date and warns when an epic will miss it or still has open bugs. An epic larger than its milestone is flagged.

The process review (`.planning/reviews/2026-11-07-process-review/synthesis.md`) found that default lanes count every member, the PM and BA included (`milestone_cli.py:141-148`; PM-4); that member availability has no home (PM-17); that the integration date and exit criteria live only in the roadmap file, so nothing warns when they fail (PM-12, QA-15); that QA is not part of the Load bound (QA-15); and that an epic larger than its milestone is found only after the fact (PM-18).

In scope:
- C. Default lanes from building members; member days off on the milestone; QA in the roadmap Load bound.
- E. An integration date on the milestone; `after_integration` and `open_bugs` warnings.
- F. An `oversized` warning, and the roadmap skill acting on it when adopting epics.

Out of scope:
- Shared gate state and forecast fidelity (shipped in `gin-workflow-milestone-gates`).
- gin-qa case results as exit criteria (`gin-workflow-qa-lifecycle`).
- Progress views (`gin-workflow-team-progress`).
- Per-member AI quota.
- gin-console changes; it ignores unknown keys.

Confirmed summary (user, 2026-11-10): the epic keeps parts C, E and F from the roadmap re-run. `gin-workflow-milestone-gates` shipped (merge 1b67778): `_place` takes the `days` mapping from `_planned_days`, which this epic builds on, and `SPEC_DUE_DAYS` stays fixed at 5. Decisions: default lanes count members with a building role; days off are milestone metadata set with `--away`; integration date and exit-criteria warnings live on the milestone bead.

Comments considered: 1, latest 2026-11-10T06:16:18Z

## Requirements

R1. Without milestone `lanes` metadata and without an `AI capacity:` number, the default lanes equal the number of `team.members` that hold at least one building role: a role equal to `dev`, or starting with `be_` or `fe_`, or ending with `_dev` or `_lead`. With no such member, or outside team mode, the default is 1. Lanes from `lanes` metadata or `AI capacity:` are unchanged.

R2. `gin milestone update <id> --away <member>:<YYYY-MM-DD>..<YYYY-MM-DD>` (repeatable; one date alone means one day) adds a days-off range to the milestone's `away` metadata, keyed by member name. `--away <member>:none` removes that member's ranges. A malformed value, a `from` after `to`, or a member not in `team.members` is refused with exit 1 and nothing is written. The command follows the existing milestone write path (role check, pull and push).

R3. When the lanes come from R1 (building members), lane n belongs to the n-th building member in `team.members` order, and the schedule skips that member's `away` days on that lane, as it skips weekends. When the lanes come from `lanes` metadata or `AI capacity:`, `away` is not applied to dates. `show` adds `away` (the stored ranges, `{}` when none) in both cases.

R4. `gin milestone update <id> --integration <YYYY-MM-DD|none>` stores or clears the milestone's `integration` metadata. `show` adds `integration` (date or null) and prints an `integration:` line when set.

R5. With an `integration` date, `show` and `list` add the warning `after_integration` to an open epic whose planned end is after that date.

R6. `show` and `list` add the warning `{"code": "open_bugs", "count": N}` to an epic of the milestone when N bug beads that are not closed have a `discovered-from` dependency on it. The beads come from the rows `gin milestone` already loads.

R7. `show` and `list` add the warning `{"code": "oversized", "days": D}` to an open epic whose planned days (remaining or assumed, as placed) exceed the working days of the milestone, `start` to `end` inclusive; D is the excess.

R8. The roadmap skill's milestone adoption names each `oversized` epic and proposes splitting it, and the Load block of `references/way-of-working.md` counts QA (`qa`, `qe`) as a group needed by every epic whose `Scope:` names tests or cases. `SKILL.md` stays within 12,000 characters.

R9. `docs/reference/cli.md` documents `--away`, `--integration`, the keys `away` and `integration`, the warnings `after_integration`, `open_bugs`, `oversized`, and the building-member default. JSON stays `schema: 1`; keys are only added.

## User Stories

### US-1: Lanes that count builders
As a PM on a team, I want the default lanes to count only members who build, so that the schedule is not twice as optimistic as the team.

Acceptance criteria:
- A team of `pm`, `ba`, `be_lead`, `be_dev`, `fe_dev`, `qe` without `lanes` or `AI capacity:` gets 3 default lanes.
- A milestone with `lanes` metadata keeps its value.
- Outside team mode the default stays 1.

### US-2: Days off move the plan
As a PM, I want to record a builder's days off on the milestone, so that their lane does not schedule work on those days.

Acceptance criteria:
- `--away an:2026-11-04..2026-11-05` stores the range; `show` lists it under `away`.
- With lanes from building members, an epic on that member's lane skips those two days and ends two working days later.
- An unknown member, a malformed date, or a reversed range exits 1 and writes nothing.
- `--away an:none` removes the member's ranges.

### US-3: Integration date and exit warnings
As a PM, I want the milestone to know its integration date and warn about epics that will miss it or still have bugs, so that I see exit-criteria risk before the date.

Acceptance criteria:
- `--integration 2026-11-12` stores the date; `show` prints `integration: 2026-11-12`.
- An open epic planned to end after the integration date gets `after_integration`.
- An epic with two open bug beads discovered from it gets `{"code": "open_bugs", "count": 2}`; closed bugs are not counted.
- `--integration none` clears the date and the warning.

### US-4: An epic larger than its milestone
As a PM, I want an epic that cannot fit in its milestone flagged, so that I split it before kickoff.

Acceptance criteria:
- An open epic placed for 7 days in a 5-working-day milestone gets `{"code": "oversized", "days": 2}`.
- `/gin:roadmap --milestone` names that epic and proposes a split.

## Errors and compatibility

- Malformed `away` or `integration` metadata written outside the CLI is ignored for scheduling and warnings, with one stderr warning naming the milestone; the command exits 0.
- A member listed in `away` who left `team.members` is ignored for dates and still shown under `away`.
- `--away` and `--integration` on a closed milestone are refused, like other `update` changes.
- gin-console reads `schema: 1` and ignores unknown keys; warning codes are free text there.

## Testing

- `tests/workflow_core/test_milestone.py`: building-member lanes (R1), days off on a member lane and their absence on anonymous lanes (R3), `after_integration` (R5), `open_bugs` (R6), `oversized` (R7).
- `tests/workflow_core/test_milestone_cli.py`: `--away` and `--integration` writes, refusals, and the `show` keys and text lines (R2, R4); exact-payload tests updated in the same track.
- Existing roadmap skill budget or text tests, if any, for R8; `gin docs check` for R9.

## Open Technical Questions

## Assumptions

- A building role is `dev`, `be_*`, `fe_*`, `*_dev`, or `*_lead`; `pm`, `ba`, `qa`, `qe`, `sa`, and `devops` alone do not build. A project that disagrees sets `lanes` or `AI capacity:`.
- Lane-to-member mapping follows `team.members` order; it is a scheduling approximation, not an assignment of epics to people.
- A bug bead counts for R6 when its `issue_type` is `bug`, it is not closed, and one of its dependencies has `type: discovered-from` pointing at the epic.
- `SPEC_DUE_DAYS` stays fixed at 5.
