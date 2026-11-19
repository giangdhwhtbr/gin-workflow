# Story points: AI-scored size, days from the measured pace, velocity KPIs

**Context**
Epic `gin-workflow-y7d6` (2026-11-19). Roadmap epics were estimated in working days (`estimated_minutes`), which mixes size with pace; with AI agents the pace moves, so day estimates went stale. The team works in Scrum terms and needs velocity KPIs, shown on gin-console by `gin-console-ulf` under the cross-repo epic `gin-harness-vhl` (export `story-points`).

**Decision/Solution**
- Points live in epic bead metadata: `points` (scale `POINT_SCALE` 1, 2, 3, 5, 8, 13, 21), `points_reason`, `points_history` (`{from, to, stage, at, actor}`, appended like `milestone_moves`; bd returns it as a string or a list). Written only by `gin milestone points EPIC N --reason TEXT [--stage roadmap|discuss|close]`, which refuses off-scale or non-ASCII digits, an empty reason, a non-`roadmap` epic, a closed epic, and an epic whose milestone has `kickoff` unless `--stage close`, all before any bd write.
- Days are derived, never stored: `epic_days(epic, pace)` is `ceil(round(points * pace.value, 6))`, at least 1, else the old `estimated_minutes`. A `Pace` (`value`, `measured_epics`, `assumed`) is threaded as keyword `pace=DEFAULT_PACE` through `remaining_days`, `_planned_days`, `schedule`, `show_payload`, `forecast`, `list_payload`, so callers and epics without points behave as before.
- `measure_pace(beads, assumed, today)`: the 10 (`MEASURED_EPICS`) most recently closed `roadmap` epics with points and actual days, sum of working days `started_at`..`closed_at` (both included, at least 1) over sum of points; else the roadmap line `- Days per point: <n>` (read by `roadmap_file.py` into `Roadmap.days_per_point`), else 1, assumed.
- `gin milestone estimate` refuses an epic with points. `kickstart` writes `committed_points` (open epics' points) and `planned_days_per_point`, and warns only when a re-kick-start changes the commitment.
- `velocity(milestone, beads, today)`: `committed_points`, `completed_points` (closed epics with points), `added_points` (latest `milestone_moves` entry into the milestone dated after `kickoff`), `say_do`, `days_per_point` (closed epics with points and actual days), `planned_days_per_point`, `accuracy` = planned over measured. Nulls instead of division by zero; malformed snapshot keys are reported by `metadata_problems`.
- JSON is additive, `schema` stays 1: top-level `days_per_point`, per-milestone `velocity`, epic rows `points`, `points_reason`, `estimate_source` (`points`|`days`|`assumed`, null for a closed epic with neither), `actual_days`, `actual_days_per_point`.
- Skills: `roadmap/references/story-points.md` holds the scoring guide (drivers, anchors, split above 21, `PM:` reason on a correction, write, re-score, lock). `/roadmap` writes `Points:` and `Estimate:` per epic and calls `gin milestone points`; `/discuss <epic>` re-scores after `requirement-confirmed` with `--stage discuss`; `/milestone-close` reports `velocity`, `say_do`, `days_per_point`, `accuracy` and corrects points with `--stage close`.

**Consequences**
- Size caps after this epic: roadmap `SKILL.md` 11,796 of 12,000, `milestone-plan.md` 3,540 of 4,000, `story-points.md` 2,315 of 4,000, discuss chain 11,442 of 12,000. `discuss` names `../roadmap/references/story-points.md` as inline code, not a markdown link, so `budget.stage_chain` does not load it.
- An additive JSON key breaks the exact-payload tests in `test_milestone.py` (`PayloadTests`) and `test_milestone_cli.py` (`test_req_011_*_exact_payload`); the track that adds keys must own both files (see [milestone-lanes-and-forecast](milestone-lanes-and-forecast.md)).
- `str.isdigit()` accepts characters such as `²` that `int()` rejects; metadata and CLI input parse digits with `isascii() and isdigit()`.
- gin-console's Reports page reads `estimated_minutes` from bd; epics with points have none until `gin-console-ulf` switches to `estimate_days` from `gin milestone --json`. The gin-console contract doc in gin-harness is updated there.

**References**
- `plugins/gin-workflow/src/scripts/workflow_core/{milestone,roadmap_file,milestone_cli}.py`; tests `tests/workflow_core/test_{milestone,roadmap_file,milestone_cli}.py`
- `plugins/gin-workflow/src/skills/roadmap/{SKILL.md,references/story-points.md,references/milestone-plan.md}`, `skills/discuss/SKILL.md`, `skills/milestone-close/SKILL.md`, `templates/roadmap.md`; `docs/reference/cli.md`
- `.planning/specs/2026-11-19-story-points-design.md`, `.planning/plans/2026-11-19-story-points.md`
- Commits `f89bfaac`, `bacd118e`, `3e1623a5`, `07ed97b3`, `5803fa48`, `06814c12`
- Beads: `gin-workflow-y7d6`, `.1` to `.3`; `gin-console-ulf`, `gin-harness-vhl`

**Scope**
Roadmap epic estimates, `gin milestone` scheduling and KPIs, and the roadmap, discuss, and milestone-close skills with the Beads task backend.
