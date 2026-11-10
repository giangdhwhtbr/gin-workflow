# Shared gate state and forecast fidelity

Epic: gin-workflow-milestone-gates
Status: confirmed by the user on 2026-11-10.

## Goal and scope

`gin milestone` readiness and `orchestration_ready` read gate state from the epic bead, so every member's machine shows the same answer, and the milestone forecast counts the remaining work of in-progress epics and places unestimated ones.

The process review (`.planning/reviews/2026-11-07-process-review/synthesis.md`) found that a PM sees `spec_not_ready` for every spec a BA confirmed, because `gin milestone` reads only the local `events.jsonl` (`milestone_cli.py:128-138`; PM-5, BA-5); that `orchestration_ready` is local-only, so on a teammate's machine `gin state` routes back to orchestrate (`lifecycle_cli.py:87-88,426-428`; BE-LEAD-5); and that the forecast places an in-progress epic with its full estimate, drops unestimated epics from the finish, never shows the deadline in `show`, and leaves `late` undefined (`milestone.py:94-120,171-172,244-246`; PM-6).

In scope:
- A. Readiness from the shared `gates` metadata of the epic bead, with the local event log as the fallback; a `spec_due` warning for `planned` milestones.
- B. `orchestration_ready` shared through the epic bead in team mode.
- D. Remaining work for in-progress epics; a flagged default for unestimated epics; the deadline in `gin milestone show`; `late` and `spec_due` defined in the docs.

Out of scope:
- The capacity model, member availability, exit criteria, integration date, and split warnings: epic `gin-workflow-milestone-capacity`.
- Progress views: epic `gin-workflow-team-progress`.
- Sharing `implementation_complete` or waivers.
- gin-console changes; it ignores unknown keys.

Confirmed summary (user, 2026-11-10): the roadmap re-run split the original epic; this epic keeps A, B and D. Decisions: `orchestration_ready` is a `gates` entry written at record time, not inferred from labels; remaining work follows the share of open tracks; an unestimated epic takes the median estimate of the scheduled epics.

## Requirements

R1. `gin milestone list` and `show` treat an epic as spec-confirmed when its bead metadata has `gates.requirement_confirmed`, or when the main checkout's `events.jsonl` has a `requirement.confirmed` event whose workflow id is the epic id. The gate metadata comes from the epic rows `gin milestone` already loads; no extra `bd` call is made for it. `spec_confirmed` is null only when the event log is unreadable and no loaded epic has the gate.

R2. `gin milestone show` and `list` add the warning `spec_due` to an open epic without a confirmed spec in a `planned` milestone whose `start` is within 5 working days after today (today included). `spec_not_ready` keeps its current trigger (milestone `scheduled` or `active`). An epic never carries both.

R3. In team mode with the beads backend, `gin record orchestration-ready --epic <epic>` also writes `gates.orchestration_ready` with `actor`, `at`, and `epic` onto the epic bead through the existing `write_gate` path. It does not require a pull request URL.

R4. `gin state --format json` sets `gates.orchestration_ready` to `satisfied` when the shared gates of the epic hold `orchestration_ready`, as it already does for `requirement_confirmed` and `plan_approved`. Gate values stay the strings used today. Outside team mode nothing changes.

R5. The schedule places an `in_progress` epic with its remaining days instead of its estimate:
- with child tracks: `max(1, ceil(estimate_days * open_tracks / all_tracks))`, where open means not closed;
- without child tracks: `max(1, estimate_days - working days from started_at to today, excluding today)`, or the full estimate when `started_at` is missing.
An `open` epic keeps its full estimate. Each epic row adds `remaining_days` (integer, equal to `estimate_days` for an open epic, null when unestimated).

R6. An unestimated open or in-progress epic is placed with assumed days: the median of `estimate_days` over the estimated epics of the same schedule, rounded up, or 1 when no epic has an estimate. It keeps the `unestimated` warning; its row adds `assumed_days` (integer) and keeps `estimate_days` null. The forecast finish includes it. `forecast.unestimated` keeps counting these epics.

R7. `gin milestone show` adds `deadline` (the roadmap `Deadline:` date, or null) to its JSON, and its text output prints a `deadline:` line when set.

R8. `docs/reference/cli.md` (the `gin milestone` section) defines `late`, `spec_due`, `remaining_days`, `assumed_days`, and the `deadline` key, and states that spec readiness reads the shared gates in team mode. `docs/concepts/state-model.md` states that `orchestration_ready` is shared through the epic bead in team mode.

R9. JSON stays `schema: 1`: keys are only added. Existing keys keep their names, types, and meanings, except that the planned dates now reflect R5 and R6.

## User Stories

### US-1: Same readiness on every machine
As a PM, I want `gin milestone show` to see the specs a BA confirmed on another machine, so that I do not chase specs that are already confirmed.

Acceptance criteria:
- An epic with `gates.requirement_confirmed` in its bead metadata and no local event shows `spec_confirmed: true` and no `spec_not_ready`.
- An epic with only a local `requirement.confirmed` event still shows `spec_confirmed: true`.
- With an unreadable event log and no shared gate, `spec_confirmed` is null and the stderr warning is printed, as today.

### US-2: Warning before a planned milestone starts
As a BA, I want a warning for unconfirmed specs of a milestone that starts soon, so that specs are ready before kickoff.

Acceptance criteria:
- An open epic without a confirmed spec in a `planned` milestone starting within 5 working days gets `spec_due`.
- The same epic in a `planned` milestone starting later gets no `spec_due`.
- An epic in a `scheduled` or `active` milestone gets `spec_not_ready`, never `spec_due`.

### US-3: A teammate continues an orchestrated epic
As a developer on a team, I want `gin state` on my machine to show `orchestration_ready` once the lead orchestrated the epic, so that execute is not routed back to orchestrate.

Acceptance criteria:
- After `record orchestration-ready --epic` in team mode, the epic bead's `gates` metadata holds `orchestration_ready` with `actor`, `at`, and `epic`.
- On a machine with no local `orchestration.ready` event, `gin state --format json --workflow-id <epic>` shows `orchestration_ready: satisfied` when the shared gate exists.
- Outside team mode, `record orchestration-ready` writes no bead metadata.

### US-4: A forecast that reflects progress
As a PM, I want in-progress epics scheduled by their remaining work and unestimated epics counted, so that the forecast finish is neither too late nor falsely early.

Acceptance criteria:
- An in-progress epic with estimate 4 and 1 of 4 tracks closed is placed for 3 days and shows `remaining_days: 3`.
- An in-progress epic without tracks, estimate 3, started 2 working days ago, is placed for 1 day.
- An unestimated epic next to epics estimated 1, 2, and 4 is placed for 2 days with `assumed_days: 2` and the `unestimated` warning, and the forecast finish includes it.
- `gin milestone show --json` has `deadline` equal to the roadmap `Deadline:`, and the text output prints it.

## Errors and compatibility

- An unreadable event log: R1 uses the shared gates alone and prints the existing stderr warning; the command exits 0.
- A bead row with malformed `gates` metadata (not an object): it is treated as having no shared gate; no error.
- `write_gate` failure during `record orchestration-ready`: reported like the existing gate-sharing failures; the local event stays recorded.
- A track list that cannot be read for an in-progress epic: the full estimate is used, as today.
- gin-console reads `schema: 1` and ignores unknown keys (`gin-console/backend/src/gin_console/milestones/models.py`); the gate values it reads from `gin state` stay strings.

## Testing

- `tests/workflow_core/test_milestone.py`: R2, R5, R6 (remaining days with and without tracks, assumed days, forecast finish), R1 merge of shared and local readiness.
- `tests/workflow_core/test_milestone_cli.py`: `deadline` in `show` JSON and text; `spec_confirmed` from bead metadata; exact-payload tests updated in the same track.
- `tests/workflow_core/test_team_gates.py`: R3 writes `orchestration_ready` in team mode and not outside it.
- `tests/workflow_core/test_lifecycle_cli.py`: R4 merges the shared `orchestration_ready` into `gin state`.
- `gin docs check` for R8.

## Open Technical Questions

## Assumptions

- `spec_due` uses a fixed window of 5 working days; making it configurable belongs to `gin-workflow-milestone-capacity` if needed.
- The branch `feat/milestone-gates` starts from `roadmap/process-review`, so the confirmed roadmap merges to master with this epic.
- `started_at` is present on epic rows loaded by `gin milestone`; when it is not, R5 uses the full estimate.
