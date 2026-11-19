# Story points scored by AI, with velocity KPIs

Workflow: story-points
Kind: capability
Status: confirmed by the user on 2026-11-19.

## Goal and scope

Roadmap epics are estimated in working days today (`gin milestone estimate <epic> <days>`, stored as `estimated_minutes`, `plugins/gin-workflow/src/scripts/workflow_core/milestone_cli.py:335`). A day estimate mixes the size of the work with the team's pace, and the pace changes quickly when the team builds with AI agents, so estimates go stale and have to be redone. The team also works in Scrum terms and needs velocity KPIs for reporting.

This epic adds story points as the size measure of a roadmap epic. The AI scores them, the PM confirms or corrects them, and days are derived from points times a measured `days_per_point`, so the schedule follows the pace without re-estimating. Points are locked once a milestone kicks off, and three KPIs are reported per milestone.

In scope:

- Points on roadmap epics: storage, a `gin milestone points` command, a scoring guide shared by `/roadmap` and `/discuss <epic>`, and the lock at kick-start.
- `days_per_point`, measured or assumed, and the derived days used by the schedule, the forecast, and the warnings in `gin milestone show/list`.
- Velocity KPIs in `gin milestone show/list --json` and in `/milestone-close`.
- The `roadmap`, `discuss`, and `milestone-close` skills, the roadmap template, `docs/reference/cli.md`, and the changelog.

Out of scope:

- Points on tracks or tasks; only roadmap epics get points.
- KPIs per member or per lane.
- gin-console. It shows points and the KPIs in its own epic `gin-console-ulf` (export `story-points-kpi`), under the cross-repo epic `gin-harness-vhl`. Its Reports page reads `estimated_minutes` from bd (`gin-console/backend/src/gin_console/reports/models.py:75`); epics with points have none, so it must read `estimate_days` from `gin milestone ... --json` instead. This epic exports the capability `story-points`.

Assumptions:

- An epic without points keeps working with days as today; roadmap files and milestones written before this epic stay valid.
- Actual days of an epic are the working days, Monday to Friday, from `started_at` to `closed_at` (to today when open), as `/milestone-close` measures them today.
- The lanes of a milestone are not part of `days_per_point`: it measures the elapsed working days of one epic per point.

## Requirements

### R1: Points storage and `gin milestone points`

- An epic's points live in its bead metadata:
  - `points`: one of 1, 2, 3, 5, 8, 13, 21;
  - `points_reason`: one line naming the drivers used for the score;
  - `points_history`: a JSON list of `{from, to, at, actor, stage}`, appended on every change, in the way `milestone_moves` is kept (`milestone_cli.py:298`); a failed append warns and does not roll back.
- `gin milestone points <epic> <n> --reason "<text>" [--stage roadmap|discuss|close]` (default stage `roadmap`) sets the three keys and prints `points of <epic> set to <n>`.
- It refuses with a non-zero exit and writes nothing when:
  - `<n>` is not in the scale; the message lists the scale;
  - the bead is missing, is not an epic, or has no `roadmap` label;
  - the epic is closed;
  - the epic belongs to a milestone that has a `kickoff` and the stage is not `close`; the message says the points are locked since kick-start and names `/milestone-close`.
- An epic above 21 points gets no score; the scoring guide (R2) proposes a split instead.

### R2: AI scoring guide

- A reference file of the roadmap skill, `references/story-points.md`, read by `/roadmap` and `/discuss <epic>`, defines how the AI scores:
  - drivers: volume (screens, endpoints, and tables of `Legacy:`, or the user stories of the spec in `/discuss`), `Complexity:`, the unknowns of `Risks:`, and the number of outside dependencies;
  - anchors: when closed epics with points exist, the AI names one or two of them as the comparison (`same size as <epic> = 5`); without them it scores from the drivers only;
  - the score is the nearest scale value; above 21 it proposes a split;
  - the reason is one line in business words plus the counts, for example `12 screens, 31 endpoints, high: payment gateway`.
- The PM confirms or corrects each score. A corrected score gets the reason `PM: <reason or "corrected">`.
- `/roadmap` step 4 shows `Points: <n> (<reason>)` and `Estimate: <days>` (derived, R3) per epic; step 6 runs `gin milestone points` instead of `gin milestone estimate` for every epic whose points are new or changed in the run. On a re-run, Beads wins and a differing `Points:` line is reported, not written, unless the PM changed it in this run.
- `/discuss <epic>` re-scores the epic from its user stories after the spec is confirmed, shows old and new points with the reason, and runs `gin milestone points <epic> <n> --stage discuss` when the PM confirms a change. When the epic is locked (R1), it shows the score and says the change goes through `/milestone-close`.
- The size question of the Estimates block of `references/milestone-plan.md` (days for small, medium, large) is removed; that block describes points and `days_per_point` instead.

### R3: `days_per_point` and derived days

- `days_per_point` is computed by `gin milestone` from the 10 most recently closed `roadmap` epics that have `points`, `started_at`, and `closed_at`: the sum of their actual days over the sum of their points, two decimals.
- With no such epic, it is the number on the line `- Days per point: <n>` in `## Constraints` of the roadmap file, read like `Deadline:` (`milestone_cli.py:123`), and marked assumed; with no such line, 1, assumed. `/roadmap` asks the PM for this value once when nothing is measured; the question does not count against `project.max_questions`, and the answer is written with ` (assumed)` after the number.
- Days of an epic with `points`: `ceil(points * days_per_point)`, at least 1, computed on every run and never written to the bead. An epic without `points` uses `estimated_minutes` as today. `remaining_days` of an `in_progress` epic keeps its current rule on top of these days.
- Every place that uses an estimate (`_planned_days`, `remaining_days`, the `forecast`, and the `unestimated`, `oversized`, `overflow`, `late`, `after_integration` warnings) uses these days.
- `gin milestone estimate <epic> <days>` refuses an epic that has points, naming `gin milestone points`.
- JSON, additive only (`schema` unchanged):
  - per epic row of `show`: `points` (null without), `points_reason`, `estimate_source` (`points`, `days`, or `assumed` for the median an unestimated epic is given); `estimate_days` carries the derived days;
  - top level of `show` and of `list`: `days_per_point: {value, measured_epics, assumed}`.
- The text output of `gin milestone show` prints `<n>pt/<d>d` for an epic with points, and `gin milestone list` prints the `days_per_point` value, with `assumed` when it is.

### R4: Commitment snapshot at kick-start

- `gin milestone kickstart <id>` also writes `committed_points` (the sum of the points of the milestone's open epics) and `planned_days_per_point` (the current `days_per_point`) to the milestone metadata.
- A second kick-start of the same milestone overwrites both and prints a warning that the commitment changed.

### R5: Velocity KPIs

- Each milestone in `gin milestone show --json` and `gin milestone list --json` gets a `velocity` block:
  - `committed_points`: from the snapshot; null before kick-start;
  - `completed_points`: the sum of the points of the milestone's closed epics;
  - `added_points`: the points of the epics moved into the milestone after its kickoff, from their `milestone_moves`;
  - `say_do`: `completed_points / committed_points`, two decimals; null without a snapshot or when `committed_points` is 0;
  - `days_per_point`: the actual days over the points of the milestone's closed epics with points; null with none;
  - `planned_days_per_point`: from the snapshot; null before kick-start;
  - `accuracy`: `planned_days_per_point / days_per_point`, two decimals; 1.00 is on plan, below 1 took longer; null when either is null.
- Each epic row of `show --json` gets `actual_days` (null when not started) and `actual_days_per_point` (null without points or actual days).
- `gin milestone list --json` lists closed milestones with their `velocity` when called with `--all`, so the trend of `days_per_point` across milestones can be drawn without recomputing it.

### R6: `/milestone-close`

- The Summary shows per epic its points next to `estimate_days` and the actual days.
- Metrics add `velocity <completed>/<committed>` (`n/a` without a snapshot), `say_do`, `days_per_point`, and `accuracy`, taken from the `velocity` block; `estimate_accuracy` stays for epics without points. All stay team level, never per member.
- The `estimate` decision becomes, for an epic with points, a points correction run with `gin milestone points <epic> <n> --stage close --reason "<text>"`; for an epic without points it stays a day estimate.
- The `Metrics:` line of the close comment and the manager wording list the new metrics.

## User Stories

### US-1: AI scores the roadmap in points
As a PM, I want the AI to score each roadmap epic in story points with a reason, so that I only confirm or correct a relative size instead of guessing days.

Acceptance criteria:
- `/roadmap` shows `Points: <n> (<reason>)` and a derived `Estimate: <days>` for every epic, and the reason names at least one driver of the scoring guide.
- After confirmation, `gin task show <epic> --json` has `points`, `points_reason`, and a `points_history` entry with stage `roadmap`.
- An epic the AI sizes above 21 is shown with a proposed split and no points.
- `gin milestone points <epic> 4 --reason x` exits non-zero and names the scale.

### US-2: The schedule follows the measured pace
As a PM, I want days derived from points and the measured pace, so that the forecast follows the team's speed without re-estimating.

Acceptance criteria:
- With closed epics of 5 points over 10 actual days and 5 points over 5 actual days, `days_per_point.value` is 1.5 and an open 8-point epic has `estimate_days` 12 and `estimate_source` `points`.
- With no closed epic with points and `- Days per point: 2 (assumed)` in the roadmap file, `days_per_point` is `{value: 2, measured_epics: 0, assumed: true}`.
- Closing one more epic with points changes `estimate_days` of open epics on the next `gin milestone show`, with no write to their beads.
- `gin milestone estimate <epic> 5` on an epic with points exits non-zero and names `gin milestone points`.
- An epic without points keeps its `estimated_minutes` days and `estimate_source` `days`.

### US-3: Points are locked at kick-start
As a manager, I want the commitment fixed when a milestone starts, so that velocity and say/do are honest.

Acceptance criteria:
- `gin milestone kickstart <id>` writes `committed_points` and `planned_days_per_point` to the milestone metadata.
- After kick-start, `gin milestone points <epic> 8` on an epic of that milestone exits non-zero and names `/milestone-close`; with `--stage close` it succeeds and appends a history entry with stage `close`.
- `/discuss <epic>` on a locked epic shows its score and does not change it.

### US-4: Velocity KPIs for reporting
As a manager, I want velocity, say/do, the pace trend, and the estimate accuracy per milestone, so that I can report delivery KPIs.

Acceptance criteria:
- A milestone committed at 20 points with 15 points closed and one 3-point epic moved in after kickoff shows `committed_points` 20, `completed_points` 15, `added_points` 3, `say_do` 0.75.
- `gin milestone list --all --json` returns a `velocity` block for each milestone, closed ones included.
- A milestone with no kick-start shows `committed_points`, `say_do`, `planned_days_per_point`, and `accuracy` as null.
- `/milestone-close` prints `velocity`, `say_do`, `days_per_point`, and `accuracy` on its `Metrics:` line.

## Errors and compatibility

- All JSON changes are additive and `schema` stays the same, so the current gin-console keeps working; it shows derived days through `estimate_days` already, and misses only the days of epics with points on its Reports page until `gin-console-ulf` ships.
- Malformed `points` or `points_history` metadata is ignored with the warning `malformed <key> metadata ignored`, like other milestone metadata (`milestone_cli.py:161`); the epic then counts as without points.
- A milestone kicked off before this epic has no snapshot: its KPIs that need it are null.
- `gin milestone points` with the markdown task backend refuses with the same message `gin milestone` gives today for that backend.

## Testing

- `tests/workflow_core/test_milestone.py`: `days_per_point` from the 10 most recent closed epics, assumed from the roadmap line and the default 1; derived days in placement, forecast, and each warning; mixed epics with and without points; `velocity` block values including nulls and `added_points` from `milestone_moves`; `actual_days` and `actual_days_per_point`.
- CLI tests: `points` scale, non-epic, closed, locked, and `--stage close`; `estimate` refused on an epic with points; `kickstart` snapshot and the overwrite warning; text output `<n>pt/<d>d` and `days_per_point` in `list`.
- Skill and docs invariants the suite enforces (`docs/contributing.md`) kept green for the changed skills, the new reference file, and `docs/reference/cli.md`.

## Open Technical Questions
