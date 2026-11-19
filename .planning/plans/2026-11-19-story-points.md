# Plan: Story points scored by AI, with velocity KPIs

Workflow: story-points
Spec: `.planning/specs/2026-11-19-story-points-design.md`

## Objective

Roadmap epics carry AI-scored story points (1, 2, 3, 5, 8, 13, 21). `gin milestone` derives working days from points times a measured `days_per_point` and schedules with them; points lock at kick-start, which snapshots the commitment; `gin milestone show/list --json` and `/milestone-close` report velocity, say/do, the days-per-point trend, and accuracy. `/roadmap` scores, `/discuss <epic>` re-scores, and gin-console (epic `gin-console-ulf`) reads the additive JSON.

## Global Constraints

Copied from the spec:

- Points live in epic bead metadata: `points` (scale 1, 2, 3, 5, 8, 13, 21), `points_reason`, `points_history` (`{from, to, at, actor, stage}` list, appended like `milestone_moves`; a failed append warns and does not roll back).
- `gin milestone points <epic> <n> --reason "<text>" [--stage roadmap|discuss|close]` refuses (non-zero exit, nothing written): off-scale `<n>`; missing bead, non-epic, no `roadmap` label; closed epic; epic in a milestone with a `kickoff` unless `--stage close`.
- `days_per_point`: the 10 most recently closed `roadmap` epics with `points`, `started_at`, `closed_at`: sum of actual days over sum of points, two decimals. Without them: `- Days per point: <n>` in `## Constraints` of the roadmap file, assumed; without that line 1, assumed.
- Days of an epic with points: `ceil(points * days_per_point)`, at least 1, computed on every run, never written to the bead. Without points: `estimated_minutes` as today. Every estimate use (placement, remaining days, forecast, warnings) uses these days.
- `gin milestone estimate` refuses an epic that has points, naming `gin milestone points`.
- `kickstart` writes `committed_points` and `planned_days_per_point`; a second kick-start overwrites both and warns.
- `velocity` block per milestone on `show` and `list`: `committed_points`, `completed_points`, `added_points`, `say_do`, `days_per_point`, `planned_days_per_point`, `accuracy`; epic rows add `points`, `points_reason`, `estimate_source`, `actual_days`, `actual_days_per_point`; top level adds `days_per_point {value, measured_epics, assumed}`. JSON changes are additive; `schema` stays 1.
- Actual days: working days, Monday to Friday, from `started_at` to `closed_at` (today when open).
- KPIs are team level only. Epics without points keep working as today. Points only on epics, not tracks.
- Out of scope: gin-console (`gin-console-ulf`), per-member KPIs, points on tracks.

## Route Rubric
- Choose the weakest model that can do the work.
- Raise the model for broad context or design judgement.
- Raise the effort for intrinsic difficulty: intricate logic, many edge cases, or long chains of steps.

| Kind of work | Model | Effort |
|---|---|---|
| Mechanical edits, documentation, boilerplate | weakest | `low` |
| Bounded implementation with a clear spec | middle | `medium` |
| Cross-module change, security, migration, concurrency | strongest | `high` |

Unclear requirements never raise the model or effort.

## Requirement Analysis
- Problem statement: day estimates mix size and pace; the pace moves with AI agents, so estimates go stale, and the team needs Scrum velocity KPIs.
- Success criteria: US-1..US-4 of the spec pass as tests; existing milestone tests stay green; skill size budgets hold.
- Constraints: the Global Constraints above; `skills/roadmap/SKILL.md` is at 11,983 of its 12,000-character cap and `milestone-plan.md` at 3,954 of 4,000 (`tests/workflow_core/test_token_budget.py:81`), the `discuss` stage chain at 11,337 of 12,000.
- Non-goals: gin-console, per-member KPIs, points on tracks.

## Approach Options
### Option 1: A `Pace` value threaded through the pure schedule functions
- Summary: `milestone.py` gains `Pace`, `points_of`, `epic_days`, `actual_days`, `measure_pace`, `velocity`; every `estimate_days(epic.get("estimated_minutes"))` call becomes `epic_days(epic, pace)`, with `pace: Pace = DEFAULT_PACE` as a keyword parameter on `remaining_days`, `_planned_days`, `schedule`, `show_payload`, `forecast`, `list_payload`. The CLI measures the pace once per run and passes it.
- Pros: one place decides days; old callers and tests keep their behaviour (default pace, no points); pure functions stay testable without bd.
- Cons: six signatures gain a keyword parameter.

### Option 2: Write derived days into `estimated_minutes` when points are set
- Summary: `gin milestone points` also writes `estimated_minutes`; the schedule is unchanged.
- Pros: almost no schedule code changes; gin-console Reports keeps reading `estimated_minutes`.
- Cons: days go stale when the pace changes, which defeats goal B of the spec; contradicts "never written to the bead".

### Recommended Approach
- Selected option: Option 1.
- Rationale: the spec requires days recomputed each run; a default `Pace` keeps every existing caller and test valid.

## Scope
- In scope: `milestone.py`, `roadmap_file.py`, `milestone_cli.py` and their tests; the `roadmap` skill (SKILL.md, new `references/story-points.md`, `references/milestone-plan.md`), `discuss` and `milestone-close` skills, the roadmap template; `docs/reference/cli.md`, `docs/reference/skills.md`, `docs/reference/skills.vi.md`, `docs/concepts/lifecycle.md`, `docs/starters/brownfield.md`, `docs/starters/brownfield.vi.md`; budget and routing tests.
- Out of scope: gin-console; the gin-console contract doc in gin-harness (`gin-harness/docs/changes/gin-harness-6s4-milestones/design.md`), updated by `gin-console-ulf`; `docs/changelog.md`, written at release time (`chore(release)` commits), not per feature.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Track 2 calls the functions Track 1 adds and Track 3 documents the commands Track 2 adds; one session, solo work.
```

## Tasks

### Track 1: Points, pace, derived days, and velocity in the schedule core
- **Dependencies**: none
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/milestone.py:15-30` (constants, `Roadmap.days_per_point`, `Pace`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/milestone.py:63-66` (add `points_of`, `points_problem`, `epic_days`, `actual_days`, `measure_pace` after `estimate_days`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/milestone.py:121-129` (`metadata_problems` checks the snapshot keys)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/milestone.py:183-210` (`remaining_days`, `_planned_days` take `pace`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/milestone.py:293-363` (`schedule` and `show_payload`: pace, new row fields, `velocity`, `days_per_point`; add `velocity` and `_moved_in_after` before `show_payload`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/milestone.py:372-452` (`forecast` and `list_payload` take `pace`; `list_payload` adds `velocity` per entry and `days_per_point`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/roadmap_file.py:1-32` (read `- Days per point:`)
  - Test `tests/workflow_core/test_milestone.py`
  - Test `tests/workflow_core/test_roadmap_file.py`
- **Interfaces** (produced):
  - `milestone.POINT_SCALE: tuple[int, ...] = (1, 2, 3, 5, 8, 13, 21)`, `milestone.MEASURED_EPICS = 10`
  - `milestone.Roadmap(deadline, lanes, error, days_per_point: float | None = None)`
  - `milestone.Pace(value: float = 1.0, measured_epics: int = 0, assumed: bool = True)` with `as_json() -> dict`; `milestone.DEFAULT_PACE = Pace()`
  - `milestone.points_of(bead) -> int | None`, `milestone.points_problem(bead) -> bool`
  - `milestone.epic_days(epic, pace: Pace = DEFAULT_PACE) -> int | None`
  - `milestone.actual_days(bead, today: date) -> int | None`
  - `milestone.measure_pace(beads, assumed: float | None, today: date) -> Pace`
  - `milestone.velocity(milestone, beads, today: date) -> dict[str, Any]`
  - keyword `pace: Pace = DEFAULT_PACE` on `remaining_days`, `_planned_days`, `schedule`, `show_payload`, `forecast`, `list_payload`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `high`
- **Why:** bounded to one module with a precise spec, but the derived days feed placement, remaining days, the forecast, and six warnings, and the KPIs have many null and edge cases.
- **Acceptance criteria**: US-2 and US-4 value checks of the spec pass as unit tests; `python3 -m pytest tests/workflow_core/test_milestone.py tests/workflow_core/test_roadmap_file.py -q` passes with every existing test unchanged.
- **Estimated complexity**: medium

Steps:

1. Write the failing tests. In `tests/workflow_core/test_milestone.py`, extend the `bead()` helper (line 15) with `closed_at=None` and set it like `started_at`:

   ```python
   def bead(id, *, type="epic", status="open", parent=None, minutes=None, blocks=(), labels=(), meta=None, title="",
            started_at=None, deps=(), closed_at=None):
       ...
       if started_at:
           item["started_at"] = started_at
       if closed_at:
           item["closed_at"] = closed_at
       return item
   ```

   Append a new class at the end of the file:

   ```python
   def done(id, points, started, closed, parent=None):
       return bead(id, status="closed", parent=parent, labels=["roadmap"], meta={"points": points},
                   started_at=f"{started}T09:00:00Z", closed_at=f"{closed}T17:00:00Z")


   class PointsTests(unittest.TestCase):
       def test_points_of_accepts_the_scale_only(self):
           for value, expected in ((5, 5), ("8", 8), (4, None), ("x", None), (True, None), (None, None), (34, None)):
               with self.subTest(value=value):
                   self.assertEqual(expected, milestone.points_of(bead("E", meta={"points": value})))
           self.assertTrue(milestone.points_problem(bead("E", meta={"points": "4"})))
           self.assertFalse(milestone.points_problem(bead("E")))

       def test_actual_days_counts_working_days_both_ends(self):
           # Mon 2026-11-02 .. Fri 2026-11-13 = 10 working days
           self.assertEqual(10, milestone.actual_days(done("A", 5, "2026-11-02", "2026-11-13"), TODAY))
           self.assertEqual(1, milestone.actual_days(done("A", 5, "2026-11-07", "2026-11-07"), TODAY))
           self.assertIsNone(milestone.actual_days(bead("A"), TODAY))
           running = bead("A", status="in_progress", started_at="2026-10-26T09:00:00Z")
           self.assertEqual(4, milestone.actual_days(running, TODAY))  # Mon 10-26 .. Thu 10-29

       def test_us2_pace_measured_from_closed_epics(self):
           beads = world(done("A", 5, "2026-11-02", "2026-11-13"), done("B", 5, "2026-11-16", "2026-11-20"),
                         bead("C", labels=["roadmap"], meta={"points": 8}))
           pace = milestone.measure_pace(beads, None, TODAY)
           self.assertEqual(milestone.Pace(1.5, 2, False), pace)
           self.assertEqual(12, milestone.epic_days(beads["C"], pace))

       def test_pace_uses_the_ten_latest_closed_epics(self):
           old = [done(f"O{n}", 1, "2026-01-05", "2026-01-16") for n in range(5)]  # 10 days per point
           new = [done(f"N{n}", 1, "2026-10-05", "2026-10-05") for n in range(10)]  # 1 day per point
           self.assertEqual(milestone.Pace(1.0, 10, False), milestone.measure_pace(world(*old, *new), None, TODAY))

       def test_us2_pace_assumed_from_the_roadmap_then_one(self):
           beads = world(bead("C", labels=["roadmap"], meta={"points": 8}))
           self.assertEqual(milestone.Pace(2.0, 0, True), milestone.measure_pace(beads, 2.0, TODAY))
           self.assertEqual(milestone.DEFAULT_PACE, milestone.measure_pace(beads, None, TODAY))
           self.assertEqual({"value": 2.0, "measured_epics": 0, "assumed": True},
                            milestone.Pace(2.0, 0, True).as_json())

       def test_epic_days_rounds_up_and_falls_back_to_minutes(self):
           self.assertEqual(4, milestone.epic_days(bead("E", meta={"points": 3}), milestone.Pace(1.33, 3, False)))
           self.assertEqual(1, milestone.epic_days(bead("E", meta={"points": 1}), milestone.Pace(0.2, 3, False)))
           self.assertEqual(2, milestone.epic_days(bead("E", minutes=days(2)), milestone.Pace(5.0, 3, False)))
           self.assertIsNone(milestone.epic_days(bead("E")))

       def test_us2_schedule_uses_derived_days_and_reports_the_source(self):
           pace = milestone.Pace(1.5, 2, False)
           beads = world(milestone_bead(), bead("P", parent="m1", meta={"points": 8, "points_reason": "12 screens"}),
                         bead("D", parent="m1", minutes=days(2)), bead("U", parent="m1"))
           found = rows(milestone.schedule(beads["m1"], beads, D("2026-11-02"), TODAY, 1, pace=pace))
           self.assertEqual((12, "points", 8, "12 screens"), (found["P"]["estimate_days"], found["P"]["estimate_source"],
                                                            found["P"]["points"], found["P"]["points_reason"]))
           self.assertEqual(("days", None), (found["D"]["estimate_source"], found["D"]["points"]))
           self.assertEqual("assumed", found["U"]["estimate_source"])
           self.assertEqual(12, found["P"]["remaining_days"])

       def test_derived_days_drive_oversized_and_the_forecast(self):
           pace = milestone.Pace(3.0, 1, False)
           beads = world(milestone_bead(end="2026-11-13"), bead("P", parent="m1", labels=["roadmap"], meta={"points": 5}))
           row = rows(milestone.schedule(beads["m1"], beads, D("2026-11-02"), TODAY, 1, pace=pace))["P"]
           self.assertIn({"code": "oversized", "days": 5}, row["warnings"])
           result = milestone.forecast(beads, TODAY, milestone.Roadmap(), 1, pace=pace)
           self.assertEqual(0, result["unestimated"])
           self.assertEqual("2026-11-20", result["finish"])  # 15 working days from Mon 11-02

       def test_actual_days_per_point_on_rows(self):
           beads = world(milestone_bead(), done("A", 5, "2026-11-02", "2026-11-13", parent="m1"),
                         bead("B", parent="m1", minutes=days(1)))
           found = rows(milestone.schedule(beads["m1"], beads, D("2026-11-02"), TODAY, 1))
           self.assertEqual((10, 2.0), (found["A"]["actual_days"], found["A"]["actual_days_per_point"]))
           self.assertEqual((None, None), (found["B"]["actual_days"], found["B"]["actual_days_per_point"]))


   class VelocityTests(unittest.TestCase):
       def moved(self, at):
           return json.dumps([{"from": None, "to": "m1", "at": at, "actor": "a"}])

       def test_us4_committed_completed_added_and_say_do(self):
           m1 = milestone_bead(kickoff="2026-11-02", committed_points="20", planned_days_per_point="1.5")
           beads = world(m1, done("A", 8, "2026-11-02", "2026-11-11", parent="m1"),
                         done("B", 5, "2026-11-02", "2026-11-06", parent="m1"),
                         bead("C", status="closed", parent="m1", meta={"points": 2, "milestone_moves": self.moved("2026-11-01T10:00:00Z")}),
                         bead("D", parent="m1", meta={"points": 3, "milestone_moves": self.moved("2026-11-05T10:00:00Z")}),
                         bead("E", parent="m1", meta={"points": 5}))
           v = milestone.velocity(beads["m1"], beads, TODAY)
           self.assertEqual({"committed_points": 20, "completed_points": 15, "added_points": 3, "say_do": 0.75,
                             "days_per_point": 1.0, "planned_days_per_point": 1.5, "accuracy": 1.5}, v)

       def test_us4_nulls_before_kick_start(self):
           beads = world(milestone_bead(), bead("E", parent="m1", meta={"points": 5}))
           self.assertEqual({"committed_points": None, "completed_points": 0, "added_points": 0, "say_do": None,
                             "days_per_point": None, "planned_days_per_point": None, "accuracy": None},
                            milestone.velocity(beads["m1"], beads, TODAY))

       def test_zero_commitment_gives_no_say_do(self):
           beads = world(milestone_bead(kickoff="2026-11-02", committed_points=0))
           self.assertIsNone(milestone.velocity(beads["m1"], beads, TODAY)["say_do"])

       def test_us4_show_and_list_carry_velocity_and_pace(self):
           pace = milestone.Pace(1.5, 2, False)
           beads = world(milestone_bead(), milestone_bead("m0", start="2026-10-01", end="2026-10-30", status="closed"),
                         bead("E", parent="m1", meta={"points": 5}))
           shown = milestone.show_payload(beads["m1"], beads, None, TODAY, pace=pace)
           self.assertEqual(pace.as_json(), shown["days_per_point"])
           self.assertEqual(0, shown["velocity"]["completed_points"])
           listed = milestone.list_payload(beads, TODAY, True, pace=pace)
           self.assertEqual(pace.as_json(), listed["days_per_point"])
           self.assertEqual({"m0", "m1"}, {entry["id"] for entry in listed["milestones"] if "velocity" in entry})

       def test_malformed_snapshot_is_a_metadata_problem(self):
           m1 = milestone_bead(committed_points="many", planned_days_per_point="1.5")
           self.assertEqual(["committed_points"], milestone.metadata_problems(m1))
   ```

   Add `import json` at the top of the test file. The numbers in `test_us4_committed_completed_added_and_say_do`: A takes 8 working days (Mon 11-02..Wed 11-11), B 5 (11-02..11-06); C is closed without `started_at`, so it counts in `completed_points` (8 + 5 + 2 = 15) but not in `days_per_point` = (8 + 5) days / (8 + 5) points = 1.0, and `accuracy` = 1.5 / 1.0; D, moved in on 11-05 after the 11-02 kickoff, adds 3; C, moved in before it, adds nothing.

   In `tests/workflow_core/test_roadmap_file.py`, add to the existing test class:

   ```python
   def test_days_per_point_line(self):
       with tempfile.TemporaryDirectory() as tmp:
           root = Path(tmp)
           self.write(root, "- AI capacity: 2\n- Days per point: 1.5 (assumed)\n")
           self.assertEqual(1.5, read_roadmap(root, "legacy").days_per_point)
           self.write(root, "- Days per point: none\n")
           self.assertIsNone(read_roadmap(root, "legacy").days_per_point)
           self.write(root, "- Days per point: 0\n")
           self.assertIsNone(read_roadmap(root, "legacy").days_per_point)
   ```

   (Use the file's existing `self.write(root, text, layout="legacy")` helper and imports; add `tempfile`/`Path` imports only if missing.)

2. Run: `python3 -m pytest tests/workflow_core/test_milestone.py tests/workflow_core/test_roadmap_file.py -q`. Expected: the new tests fail with `AttributeError` (no `points_of`, `Pace`, ...); existing tests pass.

3. Implement in `milestone.py`. After `SPEC_DUE_DAYS = 5`:

   ```python
   POINT_SCALE = (1, 2, 3, 5, 8, 13, 21)
   MEASURED_EPICS = 10
   ```

   Extend `Roadmap` with a last field `days_per_point: float | None = None` (docstring: "What `gin milestone` reads from the roadmap file."). After `Roadmap` add:

   ```python
   @dataclass(frozen=True)
   class Pace:
       """Working days per story point: measured from closed epics, else assumed (roadmap line, else 1)."""
       value: float = 1.0
       measured_epics: int = 0
       assumed: bool = True

       def as_json(self) -> dict[str, Any]:
           return {"value": self.value, "measured_epics": self.measured_epics, "assumed": self.assumed}


   DEFAULT_PACE = Pace()
   ```

   After `estimate_days` add (they use `_workdays_before`, defined later in the module; that is fine at call time):

   ```python
   def points_of(bead: Mapping[str, Any]) -> int | None:
       """The bead's `points` metadata (int or digit string) when it is on the scale, else None."""
       value = _meta(bead).get("points")
       if isinstance(value, bool) or value is None:
           return None
       text = str(value).strip()
       return int(text) if text.isdigit() and int(text) in POINT_SCALE else None


   def points_problem(bead: Mapping[str, Any]) -> bool:
       """`points` metadata is present but not on the scale; it is ignored."""
       return _meta(bead).get("points") not in (None, "") and points_of(bead) is None


   def _day(value: Any) -> date | None:
       try:
           return parse_date(str(value or "")[:10])
       except ValueError:
           return None


   def actual_days(bead: Mapping[str, Any], today: date) -> int | None:
       """Working days from `started_at` to `closed_at` (today while open), both included, at least 1;
       None when not started or closed without `closed_at`."""
       begun = _day(bead.get("started_at"))
       ended = _day(bead.get("closed_at")) if bead.get("status") == "closed" else today
       if begun is None or ended is None:
           return None
       return max(1, _workdays_before(begun, ended + timedelta(days=1)))


   def measure_pace(beads: Beads, assumed: float | None, today: date) -> Pace:
       """Days per point over the MEASURED_EPICS most recently closed roadmap epics with points and actual days;
       else `assumed` (the roadmap's `Days per point:`), else 1."""
       closed = [bead for bead in beads.values()
                 if bead.get("issue_type") == "epic" and "roadmap" in (bead.get("labels") or [])
                 and bead.get("status") == "closed" and points_of(bead) is not None
                 and actual_days(bead, today) is not None]
       closed.sort(key=lambda bead: (str(bead.get("closed_at")), bead["id"]), reverse=True)
       closed = closed[:MEASURED_EPICS]
       if closed:
           days = sum(actual_days(bead, today) or 0 for bead in closed)
           return Pace(round(days / sum(points_of(bead) or 0 for bead in closed), 2), len(closed), False)
       return Pace(float(assumed), 0, True) if assumed else DEFAULT_PACE


   def epic_days(epic: Mapping[str, Any], pace: Pace = DEFAULT_PACE) -> int | None:
       """Planned days: points times the pace, rounded up, at least 1; else the day estimate; else None."""
       points = points_of(epic)
       if points is not None:
           return max(1, math.ceil(round(points * pace.value, 6)))
       return estimate_days(epic.get("estimated_minutes"))
   ```

   `metadata_problems`: after the `integration` check add

   ```python
       if meta.get("committed_points") not in (None, "") and _count(meta.get("committed_points")) is None:
           problems.append("committed_points")
       if meta.get("planned_days_per_point") not in (None, "") and _rate(meta.get("planned_days_per_point")) is None:
           problems.append("planned_days_per_point")
   ```

   with these helpers next to `_integration`:

   ```python
   def _count(value: Any) -> int | None:
       text = str(value).strip() if value is not None and not isinstance(value, bool) else ""
       return int(text) if text.isdigit() else None


   def _rate(value: Any) -> float | None:
       try:
           number = float(str(value)) if value is not None and not isinstance(value, bool) else None
       except ValueError:
           return None
       return number if number is not None and math.isfinite(number) and number > 0 else None
   ```

   Update the docstring of `metadata_problems` to name all four keys.

   `remaining_days(epic, beads, today, pace: Pace = DEFAULT_PACE)`: replace `days = estimate_days(epic.get("estimated_minutes"))` with `days = epic_days(epic, pace)`.

   `_planned_days(epics, beads, today, pace: Pace = DEFAULT_PACE)`: in `known`, replace `estimate_days(epic.get("estimated_minutes"))` with `epic_days(epic, pace)`; call `remaining_days(epic, beads, today, pace)`.

   `schedule(..., builders=(), pace: Pace = DEFAULT_PACE)`: `days_of = _planned_days(epics, beads, today, pace)`; in the row loop `days = epic_days(epic, pace)` and `points = points_of(epic)`, `actual = actual_days(epic, today)`; the row gets `"remaining_days": remaining_days(epic, beads, today, pace)` and, after `"estimate_days": days,`:

   ```python
               "points": points, "points_reason": _meta(epic).get("points_reason") if points is not None else None,
               "estimate_source": "points" if points is not None else "days" if days is not None
                                  else "assumed" if days_of[epic_id] is not None else None,
               "actual_days": actual,
               "actual_days_per_point": round(actual / points, 2) if actual is not None and points else None,
   ```

   Before `show_payload` add:

   ```python
   def _moved_in_after(epic: Mapping[str, Any], milestone_id: str, kickoff: date) -> bool:
       """The epic's latest move into `milestone_id` (its `milestone_moves`) is dated after `kickoff`."""
       stored = _meta(epic).get("milestone_moves")
       try:
           moves = json.loads(stored) if isinstance(stored, str) else list(stored or [])
       except (ValueError, TypeError):
           return False
       into = [move for move in moves if isinstance(move, Mapping) and move.get("to") == milestone_id]
       when = _day(into[-1].get("at")) if into else None
       return when is not None and when > kickoff


   def velocity(milestone: Mapping[str, Any], beads: Beads, today: date) -> dict[str, Any]:
       """KPIs of one milestone: the kick-start snapshot against its closed epics with points."""
       meta = _meta(milestone)
       epics = epics_of(milestone["id"], beads)
       committed = _count(meta.get("committed_points"))
       planned = _rate(meta.get("planned_days_per_point"))
       closed = [epic for epic in epics if epic.get("status") == "closed" and points_of(epic) is not None]
       completed = sum(points_of(epic) or 0 for epic in closed)
       measured = [(points_of(epic) or 0, days) for epic in closed if (days := actual_days(epic, today)) is not None]
       pace = round(sum(d for _, d in measured) / sum(p for p, _ in measured), 2) if measured else None
       kickoff = _day(meta.get("kickoff"))
       added = sum(points_of(epic) or 0 for epic in epics
                   if kickoff is not None and _moved_in_after(epic, milestone["id"], kickoff))
       return {"committed_points": committed, "completed_points": completed, "added_points": added,
               "say_do": round(completed / committed, 2) if committed else None,
               "days_per_point": pace, "planned_days_per_point": planned,
               "accuracy": round(planned / pace, 2) if planned and pace else None}
   ```

   `show_payload(..., builders=(), pace: Pace = DEFAULT_PACE)`: add `"days_per_point": pace.as_json(), "velocity": velocity(milestone, beads, today),` before the `**schedule(...)` spread, and pass `pace=pace` to `schedule`.

   `forecast(..., builders=(), pace: Pace = DEFAULT_PACE)`: `"unestimated": sum(epic_days(epic, pace) is None for epic in epics.values())`; `days_of = _planned_days(group, beads, today, pace)`.

   `list_payload(..., builders=(), pace: Pace = DEFAULT_PACE)`: each `entry` gets `"velocity": velocity(milestone, beads, today)` (computed outside the `try`, it needs no period); `schedule(..., builders, pace=pace)`; the result gets `"days_per_point": pace.as_json()` and `forecast(..., builders, pace=pace)`.

   In `roadmap_file.py`: update the module docstring to "Read the roadmap lines `gin milestone` uses: `- Deadline:`, the number that starts `- AI capacity:`, and `- Days per point:`."; add `_PACE = re.compile(r"^- Days per point:[ \t]*(\d+(?:\.\d+)?)", re.MULTILINE)`; compute `pace_match = _PACE.search(text)` and `days_per_point = float(pace_match.group(1)) if pace_match and float(pace_match.group(1)) > 0 else None` after `lanes`, and pass `days_per_point=days_per_point` to each of the three `Roadmap(...)` returns that follow.

4. Run: `python3 -m pytest tests/workflow_core/test_milestone.py tests/workflow_core/test_roadmap_file.py -q`. Expected: all pass.

5. Commit: `git add -A plugins/gin-workflow/src/scripts/workflow_core/milestone.py plugins/gin-workflow/src/scripts/workflow_core/roadmap_file.py tests/workflow_core/test_milestone.py tests/workflow_core/test_roadmap_file.py && git commit -m "feat(milestone): story points, measured days per point, and velocity KPIs in the schedule (story-points)"` with the attribution trailer.

### Track 2: `gin milestone points`, the kick-start snapshot, and the CLI output
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/milestone_cli.py:30-69` (`points` subparser)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/milestone_cli.py:161-217` (malformed `points` warning, `_list_text`, `_show_text`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/milestone_cli.py:290-357` (`_kickstart` snapshot, `_points`, `_trace_points`, `_estimate` refusal, `WRITES`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/milestone_cli.py:395-416` (`_run` measures the pace and passes it)
  - Modify `docs/reference/cli.md:220-246` (usage line, JSON keys, `points` row, `estimate` and `kickstart` rows)
  - Test `tests/workflow_core/test_milestone_cli.py`
- **Interfaces**:
  - Consumed: Track 1's `POINT_SCALE`, `points_of`, `points_problem`, `measure_pace`, `epics_of`, `Pace`, the `pace=` keyword, `Roadmap.days_per_point`.
  - Produced: `gin milestone points EPIC N --reason TEXT [--stage roadmap|discuss|close]` printing `points of <epic> set to <n>`; `milestone_cli._pace(root, config, beads) -> core.Pace`; `milestone_cli._trace_points(root, bead, epic, to: int, stage: str, actor: str) -> None`.
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** bounded CLI work following the existing `move`/`estimate` patterns with exact refusal rules from the spec.
- **Acceptance criteria**: US-1 (scale refusal, metadata and history), US-2 (`estimate` refused), US-3 (snapshot, lock, `--stage close`) of the spec pass; `python3 -m pytest tests/workflow_core/test_milestone_cli.py tests/workflow_core/test_docs_coverage.py -q` passes.
- **Estimated complexity**: medium

Steps:

1. Write the failing tests in `tests/workflow_core/test_milestone_cli.py`, class `MilestoneCliTests` (helpers: `seed_writes()` at :279 creates milestones `t-m1` (2026-11-02..11-30), `t-m2`, `t-mc` and epics `t-a` under `t-m1`, `t-ac` under `t-mc`, without labels; `refused(*argv)` at :295 asserts exit 1 with the Dolt store unchanged and returns stderr; `show(id)` returns the bd row). `t-a` has no `roadmap` label, so each new test below starts with `self.seed_writes()` followed by `self.bd("update", "t-a", "--add-label", "roadmap")`; that line is left out of the code below for brevity and must be written in every new test. Replace `test_req_003_kickstart`'s exact-metadata assertion (line ~391) with key checks, and add:

   ```python
   def metadata(self, bead_id):
       return self.show(bead_id).get("metadata") or {}

   def test_us1_points_write_reason_and_history(self):
       self.seed_writes()
       code, out, err = self.run_cli("points", "t-a", "5", "--reason", "12 screens, high: payments")
       self.assertEqual(0, code, err)
       self.assertIn("points of t-a set to 5", out)
       meta = self.metadata("t-a")
       self.assertEqual("5", str(meta["points"]))
       self.assertEqual("12 screens, high: payments", meta["points_reason"])
       history = meta["points_history"]
       history = json.loads(history) if isinstance(history, str) else history
       self.assertEqual([None, 5, "roadmap"], [history[0]["from"], history[0]["to"], history[0]["stage"]])
       self.assertEqual(0, self.run_cli("points", "t-a", "8", "--reason", "x", "--stage", "discuss")[0])
       history = self.metadata("t-a")["points_history"]
       history = json.loads(history) if isinstance(history, str) else history
       self.assertEqual([5, 8, "discuss"], [history[1]["from"], history[1]["to"], history[1]["stage"]])

   def test_us1_points_refusals_write_nothing(self):
       self.seed_writes()
       for bad in ("4", "0", "34", "x"):
           with self.subTest(bad=bad):
               self.assertIn("1, 2, 3, 5, 8, 13, 21", self.refused("points", "t-a", bad, "--reason", "x"))
       self.refused("points", "t-m1", "5", "--reason", "x")
       self.refused("points", "t-missing", "5", "--reason", "x")
       self.bd("close", "t-a")
       self.refused("points", "t-a", "5", "--reason", "x")
       self.assertNotIn("points", self.metadata("t-a"))

   def test_us3_points_locked_after_kick_start(self):
       self.seed_writes()
       self.assertEqual(0, self.run_cli("points", "t-a", "5", "--reason", "x")[0])
       self.assertEqual(0, self.run_cli("kickstart", "t-m1", "--date", "2026-11-02")[0])
       meta = self.metadata("t-m1")
       self.assertEqual("5", str(meta["committed_points"]))
       self.assertEqual("1.0", str(float(meta["planned_days_per_point"])))
       self.assertIn("/milestone-close", self.refused("points", "t-a", "8", "--reason", "x"))
       code, _, err = self.run_cli("points", "t-a", "8", "--reason", "slipped", "--stage", "close")
       self.assertEqual(0, code, err)
       code, _, err = self.run_cli("kickstart", "t-m1", "--date", "2026-11-03")
       self.assertEqual(0, code)
       self.assertIn("commitment changed from 5 to 8 points", err)
       self.assertEqual("8", str(self.metadata("t-m1")["committed_points"]))

   def test_us2_estimate_refused_once_points_exist(self):
       self.seed_writes()
       self.assertEqual(0, self.run_cli("points", "t-a", "3", "--reason", "x")[0])
       self.assertIn("gin milestone points", self.refused("estimate", "t-a", "5"))

   def test_show_and_list_report_points_and_pace(self):
       self.seed_writes()
       self.assertEqual(0, self.run_cli("points", "t-a", "3", "--reason", "x")[0])
       shown = json.loads(self.run_cli("show", "t-m1", "--json")[1])
       row = next(row for row in shown["epics"] if row["id"] == "t-a")
       self.assertEqual((3, 3, "points"), (row["points"], row["estimate_days"], row["estimate_source"]))
       self.assertEqual({"value": 1.0, "measured_epics": 0, "assumed": True}, shown["days_per_point"])
       self.assertIn("velocity", shown)
       self.assertIn("3pt/3d", self.run_cli("show", "t-m1")[1])
       self.assertIn("days per point: 1.0 (assumed)", self.run_cli("list")[1])
   ```

   In `test_req_003_kickstart`, replace the `assertEqual({"start": ..., "kickoff": "2026-10-29"}, ...)` line with:

   ```python
           meta = self.show("t-m1")["metadata"]
           self.assertEqual(("2026-11-02", "2026-11-30", "2026-10-29"), (meta["start"], meta["end"], meta["kickoff"]))
           self.assertEqual("0", str(meta["committed_points"]))
   ```

   (`self.refused` returns stderr and asserts a non-zero exit with nothing written; check its definition and adapt if it returns something else.) In `ShowTextTests`, add:

   ```python
   def test_points_print_with_days(self):
       out = self.text(self.milestone(), self.item("p", metadata={"points": 5}))
       self.assertIn("p 2026-11-02..2026-11-06 5pt/5d", out)
   ```

2. Run: `python3 -m pytest tests/workflow_core/test_milestone_cli.py -q`. Expected: the new tests fail (`invalid choice: 'points'`, missing keys); the rest pass.

3. Implement in `milestone_cli.py`:

   Parser, after the `estimate` subparser:

   ```python
       item = sub.add_parser("points", parents=[common])
       item.add_argument("epic")
       item.add_argument("n")
       item.add_argument("--reason", required=True)
       item.add_argument("--stage", choices=("roadmap", "discuss", "close"), default="roadmap")
   ```

   Pace helper next to `_default_lanes`:

   ```python
   def _pace(root: Path, config: dict[str, Any], beads: Mapping[str, Mapping[str, Any]]) -> core.Pace:
       return core.measure_pace(beads, _roadmap(root, config).days_per_point, _today())
   ```

   `_warn_malformed_metadata`: also warn for open epics labelled `roadmap`:

   ```python
           if (milestone.get("issue_type") == "epic" and milestone.get("status") != "closed"
                   and "roadmap" in (milestone.get("labels") or []) and core.points_problem(milestone)):
               print(f"warning: {milestone['id']}: malformed points metadata ignored", file=sys.stderr)
   ```

   (rename the loop variable to `bead` and update the docstring to "...open milestone key ... and each open roadmap epic's `points`"). In `_run`'s `show` branch pass `list(beads.values())` instead of `[_milestone(beads, args.id)]` so epics are checked too; keep the `_milestone(beads, args.id)` call for its not-found error.

   `_list_text`: before the forecast line:

   ```python
       pace = payload.get("days_per_point")
       if pace:
           source = "assumed" if pace["assumed"] else f"measured over {pace['measured_epics']} epics"
           lines.append(f"days per point: {pace['value']} ({source})")
   ```

   `_show_text`: inside the row loop, before the `if row["estimate_days"] is not None:` branch:

   ```python
           if row.get("points") is not None:
               days = f"{row['points']}pt/{row['estimate_days']}d"
           elif row["estimate_days"] is not None:
   ```

   `_kickstart`:

   ```python
   def _kickstart(root: Path, args: argparse.Namespace, beads: dict[str, dict[str, Any]], actor: str) -> tuple[str, str]:
       milestone = _open(beads, args.id)
       day = _date(args.date) if args.date else _today()
       pace = _pace(root, _config(root), beads)
       committed = sum(core.points_of(epic) or 0 for epic in core.epics_of(args.id, beads) if epic.get("status") != "closed")
       meta = milestone.get("metadata") if isinstance(milestone.get("metadata"), Mapping) else {}
       if meta.get("committed_points") not in (None, ""):
           print(f"warning: {args.id}: commitment changed from {meta['committed_points']} to {committed} points",
                 file=sys.stderr)
       _bd(root, ["update", args.id, "--set-metadata", f"kickoff={day.isoformat()}",
                  "--set-metadata", f"committed_points={committed}",
                  "--set-metadata", f"planned_days_per_point={pace.value}"], actor)
       return f"kickoff of {args.id} set to {day.isoformat()}, {committed} points committed", "kickoff"
   ```

   `_trace_points` (same pattern as `_trace_move`):

   ```python
   def _trace_points(root: Path, bead: Mapping[str, Any], epic: str, to: int, stage: str, actor: str) -> None:
       """Append {from, to, at, actor, stage} to the epic's `points_history`; a failure warns, never rolls back."""
       try:
           metadata = bead.get("metadata")
           stored = metadata.get("points_history") if isinstance(metadata, Mapping) else None
           history = json.loads(stored) if isinstance(stored, str) else list(stored or [])
           history.append({"from": core.points_of(bead), "to": to, "stage": stage,
                           "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "actor": actor or "unknown"})
           _bd(root, ["update", epic, "--set-metadata", f"points_history={json.dumps(history)}"], actor)
       except (MilestoneError, ValueError, TypeError, AttributeError) as error:
           print(f"warning: points of {epic} set but points_history not recorded: {error}", file=sys.stderr)
   ```

   `_points`:

   ```python
   def _points(root: Path, args: argparse.Namespace, beads: dict[str, dict[str, Any]], actor: str) -> tuple[str, str]:
       if not args.n.isdigit() or int(args.n) not in core.POINT_SCALE:
           raise MilestoneError("points must be one of " + ", ".join(map(str, core.POINT_SCALE)))
       bead = beads.get(args.epic)
       if bead is None:
           raise MilestoneError(f"{args.epic} not found")
       if bead.get("issue_type") != "epic" or "roadmap" not in (bead.get("labels") or []):
           raise MilestoneError(f"{args.epic} is not a roadmap epic")
       if bead.get("status") == "closed":
           raise MilestoneError(f"{args.epic} is closed")
       parent = beads.get(bead.get("parent") or "") or {}
       meta = parent.get("metadata") if isinstance(parent.get("metadata"), Mapping) else {}
       if parent.get("issue_type") == "milestone" and meta.get("kickoff") and args.stage != "close":
           raise MilestoneError(f"points of {args.epic} are locked since the kick-start of {parent['id']}; "
                                "change them through /milestone-close")
       _bd(root, ["update", args.epic, "--set-metadata", f"points={int(args.n)}",
                  "--set-metadata", f"points_reason={args.reason}"], actor)
       _trace_points(root, bead, args.epic, int(args.n), args.stage, actor)
       return f"points of {args.epic} set to {int(args.n)}", "points"
   ```

   `_estimate`: after the `issue_type` check add

   ```python
       if core.points_of(bead) is not None:
           raise MilestoneError(f"{args.epic} has story points; change them with gin milestone points")
   ```

   `WRITES`: add `"points": _points`.

   `_run`: in `list`, compute `pace = _pace(root, config, beads)` after `beads` and pass `pace=pace` to `core.list_payload`; in `show`, the same with `core.show_payload(..., pace=pace)` (keyword, after the positional `builders` argument).

   In `docs/reference/cli.md`:
   - usage block: add `gin milestone points EPIC N --reason TEXT [--stage roadmap|discuss|close]` after the `estimate` line;
   - in the paragraph that lists the additive `--json` keys, add: `days_per_point` (`value`, `measured_epics`, `assumed`; on `list` and `show`), `velocity` per milestone (`committed_points`, `completed_points`, `added_points`, `say_do`, `days_per_point`, `planned_days_per_point`, `accuracy`), and per epic on `show` `points`, `points_reason`, `estimate_source` (`points`, `days`, `assumed`), `actual_days`, `actual_days_per_point`;
   - at the start of the `estimate_days` paragraph, add: "An epic with story points is planned for `ceil(points × days_per_point)` working days, at least 1, recomputed on every run. `days_per_point` is the actual working days over the points of the 10 most recently closed `roadmap` epics with points (from `started_at` to `closed_at`, both included); without them it is the number on the roadmap's `- Days per point:` line, else 1, and `assumed` is true. `list` prints it on a `days per point:` line; `show` prints `<points>pt/<days>d` for such an epic. A malformed `points` value is ignored with a warning on stderr.";
   - after that paragraph add: "`velocity` compares the kick-start snapshot with the milestone's closed epics with points: `say_do` is completed over committed points, null before kick-start or with 0 committed; `added_points` counts epics moved in after the kickoff date (from `milestone_moves`); `days_per_point` is measured over the milestone's closed epics with points; `accuracy` is `planned_days_per_point` over it (1.00 on plan, below 1 slower). `list --all` returns it for closed milestones too.";
   - table: `kickstart` row: append "; also stores `committed_points` (the points of its open epics) and `planned_days_per_point`, and warns when a second kick-start changes the commitment"; `estimate` row: append "; refused for an epic with story points"; new row after it: `| \`points\` | Set a roadmap epic's story points (1, 2, 3, 5, 8, 13, 21) with a one-line reason; appends \`{from, to, at, actor, stage}\` to \`points_history\`. Refuses an off-scale value, a non-epic or an epic without the \`roadmap\` label, a closed epic, and an epic of a kicked-off milestone unless \`--stage close\` |`.

4. Run: `python3 -m pytest tests/workflow_core/test_milestone_cli.py tests/workflow_core/test_milestone.py tests/workflow_core/test_docs_coverage.py -q`. Expected: all pass.

5. Commit: `git add -A plugins/gin-workflow/src/scripts/workflow_core/milestone_cli.py tests/workflow_core/test_milestone_cli.py docs/reference/cli.md && git commit -m "feat(milestone): gin milestone points, the kick-start commitment, and points in show and list (story-points)"` with the attribution trailer.

### Track 3: AI scoring in the roadmap, discuss, and milestone-close skills
- **Dependencies**: Track 2
- **Files**:
  - Create `plugins/gin-workflow/src/skills/roadmap/references/story-points.md`
  - Modify `plugins/gin-workflow/src/skills/roadmap/SKILL.md:17,21-22,31,36` (`--milestone` steps 2, 5, 6; Steps 4 and 6)
  - Modify `plugins/gin-workflow/src/skills/roadmap/references/milestone-plan.md:5-6,23` (Estimates block; Write block step 6 command)
  - Modify `plugins/gin-workflow/src/skills/discuss/SKILL.md` (step 8 Record)
  - Modify `plugins/gin-workflow/src/skills/milestone-close/SKILL.md` (Summary, Metrics, Spillover, Actions, Write steps 3, 4, 6)
  - Modify `plugins/gin-workflow/src/templates/roadmap.md:12-13,29-30` (comment and `- Days per point:` line)
  - Modify `docs/reference/skills.md:50,53` and `docs/reference/skills.vi.md` (same rows)
  - Modify `docs/concepts/lifecycle.md:23`
  - Modify `docs/starters/brownfield.md:225-227,269` and `docs/starters/brownfield.vi.md` (same passages)
  - Test `tests/workflow_core/test_token_budget.py:81-89`
  - Test `tests/workflow_core/test_skill_routing.py:67-103,233-250`
- **Interfaces**: consumed: `gin milestone points EPIC N --reason TEXT [--stage roadmap|discuss|close]`, `days_per_point` and `velocity` in `gin milestone show/list --json`, the roadmap line `- Days per point: <n> (assumed)`.
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** skill instructions that agents execute, written against tight character caps (roadmap SKILL.md 11,983/12,000, milestone-plan.md 3,954/4,000, discuss chain 11,337/12,000); wording needs judgement, not only edits.
- **Acceptance criteria**: `python3 -m pytest tests/workflow_core/test_token_budget.py tests/workflow_core/test_skill_routing.py tests/workflow_core/test_docs_coverage.py tests/test_no_direct_bd.py -q` passes; every scoring rule of spec R2 and every `/milestone-close` change of R6 is in the skill text.
- **Estimated complexity**: medium

Steps:

1. Update the tests first.
   - `test_token_budget.py:86`: `for name in ("manager-view.md", "milestone-plan.md", "story-points.md"):` (cap 4,000 each).
   - `test_skill_routing.py`, `test_roadmap_manager_view_and_milestone_plan`: in the `plan` needles replace `"gin milestone estimate"` with `"gin milestone points"`; in the `write` order checks replace `"gin milestone estimate"` with `"gin milestone points"`; replace the `estimates` needles with `("[story points](story-points.md)", "`(assumed)`", "- Days per point:")`; add after them:

     ```python
             points = (roadmap / "references/story-points.md").read_text(encoding="utf-8")
             for needle in ("1, 2, 3, 5, 8, 13, 21", "`Legacy:`", "`Complexity:`", "`Risks:`", "propose a split",
                            "PM: ", "gin milestone points", "--stage discuss", "/milestone-close"):
                 with self.subTest(needle=needle):
                     self.assertIn(needle, points)
             present = text[text.index("4. **Present the roadmap**"):text.index("5. **Write**")]
             self.assertIn("[story points](references/story-points.md)", present)
     ```
   - `test_milestone_close_moves_spillover_and_records_the_result`: add needles `"--stage close"`, `"say_do"`, `"days_per_point"`, `"velocity <completed>/<committed>"`; replace the `keys` tuple with `("completion", "estimate_accuracy", "capacity_used", "cost_per_epic", "rework", "velocity", "say_do", "days_per_point", "; accuracy")` (`"; accuracy"` so the search skips `estimate_accuracy`).
   - Add a test in the same class:

     ```python
     def test_discuss_rescores_a_roadmap_epic(self):
         text = (SRC / "skills/discuss/SKILL.md").read_text(encoding="utf-8")
         for needle in ("../roadmap/references/story-points.md", "Re-score", "--stage discuss"):
             with self.subTest(needle=needle):
                 self.assertIn(needle, text)
     ```

2. Run: `python3 -m pytest tests/workflow_core/test_token_budget.py tests/workflow_core/test_skill_routing.py -q`. Expected: the changed tests fail (missing file and needles).

3. Create `plugins/gin-workflow/src/skills/roadmap/references/story-points.md` (under 4,000 characters):

   ```markdown
   # Story points: how the AI scores an epic

   Read on `/roadmap` (step 4 and `--milestone` step 2) and on `/discuss <epic>` for a roadmap epic.

   ## Scale
   Points measure size relative to other epics, never time: 1, 2, 3, 5, 8, 13, 21. Days come from `gin milestone show` or `list`: points times `days_per_point`, rounded up.

   ## Score
   1. Drivers, read from the epic: volume (screens, endpoints, and tables of `Legacy:` in `/roadmap`; the user stories and their acceptance criteria of the confirmed spec in `/discuss`), `Complexity:`, the unknowns of `Risks:`, and the outside dependencies (`Depends on:` and external services).
   2. Anchors: from `gin task list --label roadmap --type epic --status closed --json`, pick one or two closed epics with `points` of similar drivers and compare (`same size as <epic> = 5`). Without them, score from the drivers only.
   3. Take the nearest scale value. Above 21, propose a split into epics of 21 or less instead of a score.
   4. Reason: one line, business words plus the counts, for example `12 screens, 31 endpoints, high: payment gateway`.

   Show `Points: <n> (<reason>)` with the derived `Estimate: <days>` per epic. The PM confirms or corrects each; a corrected score gets the reason `PM: <the PM's reason, else corrected>`. Scores and corrections do not count against `project.max_questions`.

   ## Write
   `gin milestone points <epic> <n> --reason "<reason>"` for each epic whose points are missing in Beads or changed in this run; on a re-run Beads wins and a differing `Points:` line is reported, not written. An epic that keeps only a day estimate is valid input; propose a score for it.

   ## Re-score in /discuss
   After `requirement-confirmed` is recorded for a roadmap epic, score it again from its user stories. Show the old and new points with the reason. When they differ and the PM confirms, run `gin milestone points <epic> <n> --stage discuss --reason "<reason>"`. When the command refuses because the milestone has kicked off, show the score and say the change goes through `/milestone-close`.

   ## Lock
   Points lock when the epic's milestone kicks off: `gin milestone kickstart` stores the committed points and the pace for the velocity KPIs. After that only a `/milestone-close` `estimate` action changes them, with `--stage close`.
   ```

4. Edit `roadmap/SKILL.md` (keep it at or under 12,000 characters; check with `wc -m`):
   - `--milestone` step 2: replace "propose `Estimate: <working days>` for every epic of the milestone, from the measured pace and the AI capacity, per the Estimates block" with "score `Points:` for every epic of the milestone per the Estimates block".
   - `--milestone` step 3: "The PM may add or drop epics and change estimates." → "The PM may add or drop epics and change points."
   - `--milestone` step 5: "and estimates with `gin milestone estimate <epic> <days>`" → "and points with `gin milestone points`"; "When a `gin milestone move` or `estimate` call exits non-zero" → "When a `gin milestone move` or `points` call exits non-zero".
   - `--milestone` step 6: "Beads wins for membership and estimates" → "Beads wins for membership and points"; the example "E1 estimate: file 5, Beads 8" → "E1 points: file 5, Beads 8".
   - Steps 4: "Every run proposes `Estimate: <working days>` per epic (`--milestone` step 2)." → "Every run scores `Points:` and shows the derived `Estimate:` per [story points](references/story-points.md)."
   - Steps 6, the `estimates:` bullet → "   - points: per the Write block of [story points](references/story-points.md);"
   If the file is still over 12,000 characters, shorten wording inside the lines changed above only.

5. Edit `references/milestone-plan.md` (at or under 4,000 characters):
   - Replace the whole `## Estimates` body with:

     ```markdown
     Score points per [story points](story-points.md); `Estimate:` is the days `gin milestone show` derives from them. When `days_per_point` in `gin milestone list --json` has `measured_epics` 0, ask the PM once for the working days of one point (default 1; not counted against `project.max_questions`), write `- Days per point: <n> (assumed)` under `## Constraints`, and mark each `Estimate:` line `(assumed)`.
     ```
   - Write block, step 6 sentence: "then `gin milestone estimate <epic> <days>` under the estimates rule of step 6" → "then `gin milestone points` under the points rule of step 6".
   - Re-run block: "Beads wins for membership and estimates" → "Beads wins for membership and points".

6. Edit `discuss/SKILL.md`, step 8 Record: append one sentence: "For a roadmap epic, then Re-score its points per `../roadmap/references/story-points.md` (`--stage discuss`)." Write the path as inline code, not a markdown link, so the discuss stage budget does not load the file (`budget.py` `_LINK`; the `_REFERENCE` match resolves to no file under `skills/discuss/` or `src/references/`). Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -c "from pathlib import Path; from workflow_core.budget import stage_chars; print(stage_chars(Path('plugins/gin-workflow/src'), 'discuss'))"`; expected under 12,000.

7. Edit `milestone-close/SKILL.md`:
   - Summary bullet "Per epic, `estimate_days` against the working days ..." → start with "Per epic, its `points` (when set), `estimate_days` against the working days ...".
   - Metrics: `estimate_accuracy` bullet: "over the closed epics that have both" → "over the closed epics without points that have both". Add after the `rework` bullet:
     "- `velocity`, `say_do`, `days_per_point`, `accuracy`: from the `velocity` block of `gin milestone show <id> --json`; `velocity` as `<completed_points>/<committed_points>`; each `n/a` when null."
   - Spillover decision: "re-estimate with new remaining days" → "re-estimate (new points for an epic with points, else new remaining days)".
   - Actions: "- `estimate`: an epic and its new days." → "- `estimate`: an epic and its new points, or its new days when it has no points."
   - Write step 3: "`gin milestone estimate <epic> <days>` for each `estimate` action." → "`gin milestone points <epic> <n> --stage close --reason \"<text>\"` for each `estimate` action on an epic with points, else `gin milestone estimate <epic> <days>`."
   - Write step 4 `Metrics:` line: append `; velocity <completed>/<committed>|n/a; say_do <n.nn|n/a>; days_per_point <n.nn|n/a>; accuracy <n.nn|n/a>`.
   - Write step 6 `- Metrics:` line: append `; <completed> of <committed> points (say/do <percent>%); <days_per_point> days per point`.

8. Edit `templates/roadmap.md`: in the comment, "The milestone headings and the Milestone: and Estimate: lines" → "The milestone headings and the Milestone:, Points: and Estimate: lines"; "gin milestone list reads two Constraints lines: Deadline: ... and the whole number that starts AI capacity: (...)." → append "; it also reads Days per point: (working days per story point, used until closed epics give a measured value)". Under `## Constraints`, add `- Days per point:` after `- Deadline:`.

9. Docs:
   - `docs/reference/skills.md:50` roadmap row: "with a project deadline and an estimate per epic" → "with a project deadline and story points per epic, scored by the AI and converted to working days from the measured pace"; `:53` milestone-close row: add "velocity, say/do, days per point" to its metrics list. Mirror both in `docs/reference/skills.vi.md` (Vietnamese, same rows).
   - `docs/concepts/lifecycle.md:23`: "an estimate per epic" → "story points per epic (days follow from the measured pace)"; add "`/discuss <epic>` re-scores a roadmap epic's points once its spec is confirmed."
   - `docs/starters/brownfield.md:227` and `:269`: name `Points:` next to `Estimate:` and the `- Days per point:` Constraints line; `:269` "each with an `Estimate:` in working days" → "each with `Points:` and the `Estimate:` in working days derived from them". Mirror in `brownfield.vi.md`.

10. Run: `python3 -m pytest tests/workflow_core/test_token_budget.py tests/workflow_core/test_skill_routing.py tests/workflow_core/test_docs_coverage.py tests/test_no_direct_bd.py -q`. Expected: all pass. Then `wc -m plugins/gin-workflow/src/skills/roadmap/SKILL.md plugins/gin-workflow/src/skills/roadmap/references/*.md` shows SKILL.md ≤ 12,000 and each reference ≤ 4,000 (way-of-working ≤ 6,000).

11. Commit: `git add -A plugins/gin-workflow/src/skills plugins/gin-workflow/src/templates/roadmap.md docs tests/workflow_core/test_token_budget.py tests/workflow_core/test_skill_routing.py && git commit -m "feat(roadmap): AI-scored story points in roadmap, discuss, and milestone-close (story-points)"` with the attribution trailer.

## Integration
- **Branch**: `feat/story-points`
- **Merge strategy**: sequential

## Validation
- [ ] `python3 -m pytest tests/workflow_core/test_milestone.py tests/workflow_core/test_milestone_cli.py tests/workflow_core/test_roadmap_file.py tests/workflow_core/test_token_budget.py tests/workflow_core/test_skill_routing.py tests/workflow_core/test_docs_coverage.py tests/test_no_direct_bd.py -q` passes.
- [ ] The full suite runs once at the pre-push hook when the epic ships.
- [ ] Manual: in a scratch repo with `providers.task_tracking: beads`, create a `roadmap` epic, `gin milestone points <epic> 5 --reason x`, `gin milestone show <m> --json` shows `points: 5`, `estimate_source: points`, `days_per_point`; after `kickstart`, `points` refuses without `--stage close`.

## Notes
- Parent Bead: the gin-workflow epic carries `export:story-points` (Beads copies a parent's labels to its children; the track beads inherit it harmlessly). It remains open until the human-confirmed merge; then `gin task close` it and `bd -C gin-workflow ship story-points` so `gin-console-ulf` and `gin-harness-vhl` see the capability. Track beads close after tests and review pass.
- Deviation from the spec's scope list: `docs/changelog.md` is written at release time in this repository, so no entry is added here.
- `estimate_source` is null for a closed epic without points or an estimate (it takes no days), in addition to the three values in the spec.
- The user may override `Model:` and `Effort:` before plan approval.
