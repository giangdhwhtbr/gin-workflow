# Roadmap deadline and forecast: project deadline, lanes per milestone, forecast over every open epic

Epic: gin-workflow-57fw
Status: confirmed by the user on 2026-11-08.

## Goal and scope

Milestones are sprints, so a project-wide deadline cannot be one of them. This epic gives the roadmap a `Deadline:` line, turns "AI capacity" into a number of lanes the scheduler uses, lets each milestone carry its own lane count, and makes `gin milestone list` forecast when every open roadmap epic finishes against that deadline. gin-console keeps reading the same JSON; the new keys are additive.

The flow this serves, confirmed with the user on 2026-11-08:

1. `/gin:roadmap` for the whole project writes `Deadline:` and `AI capacity:` under `## Constraints` and an `Estimate:` for every epic (stored in Beads). Its report compares the forecast with the deadline.
2. `gin milestone create` (optionally `--lanes N`) and `/gin:roadmap --milestone <id>` pick ready epics into a sprint. The sprint's lanes may differ from the project capacity.
3. `gin milestone list` prints one forecast line over every open epic, assigned or not. Repeat per sprint; the forecast shrinks as sprints close.

A lane is one stream of work that runs one epic at a time. One person building with AI agents on one account is one lane; two members are two lanes.

Premise corrected during discovery: the current scheduler (`plugins/gin-workflow/src/scripts/workflow_core/milestone.py`, `schedule`) does not assume one sequential lane. Independent epics all start on the first working day, so it is optimistic without limit. Lanes fix that for milestone schedules as well as for the forecast; the user chose to apply them to both.

In scope: roadmap template line, roadmap-file reader, lanes on milestones, lane-bound scheduler, forecast in `gin milestone list`, `/gin:roadmap` changes, tests, docs in this repository.

Out of scope:
- gin-console pages for the forecast. They follow as a cross-repo epic in `gin-harness` depending on `external:gin-workflow:milestone-forecast` (see R9).
- Lanes per area, or mapping epics to areas. Nothing ties an epic to an area today.
- Holidays, part-time capacity, or fractional lanes.
- The brownfield starter guide. `gin-workflow-docs-refresh` carries that (note added on 2026-11-08): it describes the three-step flow above in `docs/starters/brownfield.md` and `brownfield.vi.md`.

Comments considered: 0. The epic has no roadmap entry.

## Requirements

### R1. Roadmap file lines and reader

- `plugins/gin-workflow/src/templates/roadmap.md` gets `- Deadline:` under `## Constraints`, after `- AI capacity:`. The header comment says both are read by `gin milestone list`: `Deadline:` as `YYYY-MM-DD`, `AI capacity:` by its leading whole number (the default lane count); the rest of the line stays free text.
- New pure module `plugins/gin-workflow/src/scripts/workflow_core/roadmap_file.py` with `read_roadmap(root, layout) -> Roadmap(deadline: date | None, lanes: int | None, error: str | None)`. The path is `team.ROADMAP[layout]` (`.planning/roadmap.md`, or `docs/roadmap.md` with `sdd`). It matches only two bullet lines anywhere in the file, first match wins: `^- Deadline:\s*(\S+)` and `^- AI capacity:\s*(\d+)`. A missing file or missing line gives `None`. A `Deadline:` value that is not an ISO date gives `deadline=None` and `error="Deadline: <value> is not a date (YYYY-MM-DD)"`. The reader never raises.

### R2. Lanes per milestone

- Milestone metadata gains `lanes`, a positive whole number, next to `start`, `end`, `kickoff`. `gin milestone create ... [--lanes N]` and `gin milestone update <id> [--lanes N]` write it; `--lanes 0`, a negative, or a non-integer fails with `lanes must be a positive whole number` (exit 1) before any write. Both go through `_guard` like the other writes.
- Effective lanes of a milestone, in order: its `lanes` metadata; the roadmap `AI capacity:` number; the number of `team.members` when team mode is on; 1.
- Default lanes of the project (for unassigned epics): the same chain without the first step.
- `show --json` and each `list --json` entry add `lanes`: the effective value. Text output of `show` appends `, lanes N` to its first line.

### R3. Lane-bound scheduler

`schedule(milestone, beads, start, today, lanes)` keeps its signature otherwise and its output shape. Algorithm, deterministic:

- Each lane has a next-free working day, initially `_workday(start)`.
- Repeatedly take, among epics whose in-milestone blockers are all placed, the one with the earliest allowed start (blockers' end + 1 working day; an unestimated blocker only pushes to its start, as today), ties by id. Place it on the lane that is free earliest; `planned_start = max(allowed start, lane free day)`; `planned_end = _last_of(planned_start, days)`; the lane becomes free the next working day.
- An unestimated epic takes no lane and no days: `(begin, begin)` with the `unestimated` warning, as today.
- Cycles raise `CycleError` naming the loop, as today. Closed epics are still scheduled (they hold their dates and count in `finish`).
- Warnings, `finish`, `overflow_days`, and the row fields are unchanged.

With `lanes=1` every estimated epic of a milestone runs in sequence; with `lanes >= number of independent epics` the result equals today's.

### R4. Forecast

New pure function `forecast(beads, today, roadmap, lanes_of, default_lanes) -> dict | None` in `milestone.py`, called by `list_payload`:

- Input set: every bead with `issue_type == "epic"`, label `roadmap`, status not `closed`. Nothing when the set is empty (`forecast` is `null`).
- Groups: open milestones (status not `closed`) in order of `end` then id, each with its effective lanes, then the unassigned pool with the default lanes. Within a group, only its open epics are scheduled, by R3, from `max(today, kickoff or start of the milestone, the working day after the previous group's finish)`; the pool starts the working day after the last milestone's finish, or today when there is none. A blocker placed in an earlier group pushes the blocked epic's start, as an in-group blocker would. A blocker in a later group does not move dates (`milestone show` already warns `external_blocker` for that case). Open epics in progress keep their full estimate; the roadmap skill may lower it to the remaining days.
- Output: `{"deadline": iso | None, "lanes": default_lanes, "start": today, "finish": iso | None, "overflow_days": int, "open_epics": int, "unestimated": int, "error": str | None}`. `overflow_days` is `workdays_after(deadline, finish)`, 0 without a deadline or when on time. `finish` is `None` only when every open epic is unestimated.
- A cycle or a reader error (R1) gives `error` set, the other fields filled as far as known, and `gin milestone list` still exits 0. Milestone entries keep reporting their own `error` as today.

### R5. `gin milestone list` output

- JSON: top-level `forecast` (R4) and per-entry `lanes` (R2). `schema` stays 1; no existing key changes meaning.
- Text: after `unassigned roadmap epics: N`, one line when `forecast` is not null:
  - with a deadline: `forecast: finish 2026-12-20, deadline 2026-12-31, 8 working days spare, lanes 1, 3 open epics, 1 unestimated` (or `overflow 5 working days` in place of the spare part; `on the deadline` when equal);
  - without: `forecast: finish 2026-12-20, no deadline, lanes 1, 3 open epics`;
  - the `, N unestimated` part only when N > 0; `error: ...` replaces the dates on error.
  Spare days are computed in the text layer with `workdays_after(finish, deadline)`; the JSON carries `finish` and `deadline`.

### R6. `/gin:roadmap` skill

`plugins/gin-workflow/src/skills/roadmap/SKILL.md`, keeping its anchor phrases (`warn and leave its title, description, and dependencies unchanged`, `7. **Report**`) and under 12,000 characters (the roadmap's own limit for stage skills; `budget.STAGES` does not list `roadmap`, so no test enforces it):

- Clarify step: with the AI capacity question, ask for the project deadline (a date, or none). When the file already has a `Deadline:` line, show it for confirmation like `AI capacity:`. Step 5 writes `- Deadline: YYYY-MM-DD` (or leaves the line empty) and keeps `AI capacity:` starting with the number of lanes.
- Plain `/roadmap` proposes an `Estimate:` for every epic with the method `--milestone` uses today (measured pace, else small/medium/large sizes marked `(assumed)`), writes the lines under `## Unassigned`, and in step 6 sets them with `gin milestone estimate <epic> <days>`. Beads wins on a re-run.
- `--milestone <id>`: ask the sprint's lanes with the roadmap number as the default; set it with `gin milestone update <id> --lanes N` in step 6 when it differs from the stored value.
- Step 7 Report: run `gin milestone list --json` and report the `forecast` line in words: finish, deadline, spare or overflow working days, unestimated count. Overflow never blocks. The skill does no date arithmetic itself.

### R7. Documentation

- `docs/reference/cli.md`, `## gin milestone`: `--lanes` on `create` and `update`, the effective-lanes chain, the forecast line, the JSON additions (`forecast`, `lanes`), the lane-bound schedule, and the exit code of a bad `--lanes`.
- `docs/guides/customizing-templates.md`, roadmap template section: the `Deadline:` and `AI capacity:` lines and what reads them.
- `docs/reference/skills.md` roadmap row and `docs/concepts/lifecycle.md` sentence on `/roadmap`: estimates and the forecast in the plain run, lanes in `--milestone`. Vietnamese mirrors that exist for the touched pages get the same change.

### R8. Behaviour change to announce

With lanes applied to milestone schedules, an existing milestone whose epics ran in parallel now shows later planned dates and may gain `overflow` warnings at the default of 1 lane. The cli.md section and the ship notes say so; the remedy is `gin milestone update <id> --lanes N` or the `AI capacity:` number.

### R9. Capability for gin-console

- The plan labels this epic `export:milestone-forecast`; ship turns it into `provides:milestone-forecast`.
- The JSON contract for the console is R4 and R5 of this spec. The record in `gin-harness/docs/changes/gin-harness-6s4-milestones/design.md` ("only ever added to") is updated by the follow-up cross-repo epic in `gin-harness` ("Console shows the roadmap forecast", `external:gin-workflow:milestone-forecast`), together with `MilestoneList`/`MilestoneEntry` in `gin-console/backend/src/gin_console/milestones/models.py` and the UI. Pydantic models there ignore unknown keys, so the console keeps working before that epic.

## User Stories

### US-1: Set a project deadline in the roadmap
As a PM, I want a `Deadline:` line in the roadmap constraints, so that the whole project has a date that is not a sprint.

Acceptance criteria:
- `gin specs template roadmap.md` prints `- Deadline:` under `## Constraints`.
- `/gin:roadmap` asks for the deadline next to AI capacity and writes the line; an existing line is shown for confirmation.
- `gin milestone list --json` reports that date in `forecast.deadline`; a malformed date appears in `forecast.error` and the command exits 0.

### US-2: Roadmap the whole project with estimates and a forecast
As a PM, I want the plain `/gin:roadmap` run to estimate every epic and compare the total with the deadline, so that I know before the first sprint whether the plan fits.

Acceptance criteria:
- The plain run writes `Estimate:` per epic under `## Unassigned` and sets them with `gin milestone estimate`.
- Its report states finish, deadline, and spare or overflow working days from `gin milestone list --json`, and continues when over.
- A re-run keeps Beads estimates and reports differences without writing.

### US-3: Plan a sprint with its own capacity
As a PM, I want each milestone to have its own lane count, so that a sprint with two members is scheduled differently from a solo sprint.

Acceptance criteria:
- `gin milestone create --lanes 2` and `gin milestone update <id> --lanes 2` store the value; `--lanes 0` fails with `lanes must be a positive whole number` and writes nothing.
- `gin milestone show <id>` schedules at most that many estimated epics at once; without the metadata the roadmap number, then the team member count, then 1 applies.
- `show --json` and `list --json` entries carry `lanes`.

### US-4: Read the forecast
As a PM or a gin-console reader, I want `gin milestone list` to say when every open epic finishes against the deadline, so that I see the project's position without summing estimates by hand.

Acceptance criteria:
- Text output ends with the forecast line of R5 when at least one roadmap epic is open, and omits it otherwise.
- `forecast.finish` covers open epics of every open milestone in sequence and the unassigned pool after them, with blockers from earlier groups respected.
- `forecast.open_epics` and `forecast.unestimated` count the scheduled set; `overflow_days` counts working days after the deadline.
- Every pre-existing JSON key keeps its name and meaning; `schema` stays 1.

### US-5: Existing schedules stay readable after the change
As a PM with a running milestone, I want to understand why its dates moved, so that I can set the right lane count.

Acceptance criteria:
- cli.md explains the lane-bound schedule and the default of 1 lane.
- `gin milestone show` prints the effective lanes on its first line.

## Errors and compatibility

| Case | Behaviour |
|---|---|
| `--lanes` not a positive whole number | `lanes must be a positive whole number`, exit 1, nothing written |
| `Deadline:` not `YYYY-MM-DD` | `forecast.error`, `forecast.deadline` null, exit 0 |
| Roadmap file missing | no deadline, default lanes from team or 1, exit 0 |
| Dependency cycle among open epics | `forecast.error` names the loop; milestone entries unchanged; exit 0 (`show` still exits 1 as today) |
| No open roadmap epic | `forecast` null, no text line |
| Every open epic unestimated | `forecast.finish` null, `unestimated` = `open_epics`, text says `finish unknown` |

Compatibility: `schema` stays 1; `forecast` and `lanes` are additions. gin-console (`milestones/source.py`, `models.py`) refuses only `schema != 1` and its Pydantic models ignore extra keys, so it keeps working until the follow-up epic reads the new fields. Older roadmap files without the new lines stay valid. The existing exact-payload tests change because the payload grows.

## Testing

- `tests/workflow_core/test_roadmap_file.py` (new): deadline parsed; AI capacity leading number parsed, free text after it ignored; missing file and missing lines; malformed deadline gives `error`; `sdd` layout path.
- `tests/workflow_core/test_milestone.py`: `test_req_007_chain_and_parallel` gains an explicit `lanes` argument and keeps its expectations with enough lanes; new cases: one lane serialises independent epics in id order; two lanes split three equal epics into two rounds; a blocker wins over a free lane; unestimated epics take no lane; forecast with a deadline (spare and overflow), without a deadline, with two milestones in sequence using different lanes, with the unassigned pool after them, with a pool epic blocked by a sprint epic, with a cycle, with no open epic, with every epic unestimated; effective-lanes chain (metadata, roadmap number, team members, 1).
- `tests/workflow_core/test_milestone_cli.py`: `test_req_011_show_exact_payload` and `test_req_011_list_exact_payload` updated for `lanes` and `forecast`; `create --lanes` and `update --lanes` write metadata; a bad `--lanes` exits 1 before `bd`; `test_list_text_output` covers the forecast line with and without a deadline.
- `tests/workflow_core/test_specs.py`: the rendered roadmap template contains `- Deadline:`.
- `tests/workflow_core/test_token_budget.py` and `test_epic_comments.py` keep passing (skill size and anchor phrases).
- Full suite: `python3 -m pytest -n auto`.

## Open Technical Questions
