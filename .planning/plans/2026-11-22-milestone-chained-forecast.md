# Plan: Milestone chained forecast

Epic: gin-workflow-6yoq
Spec: `.planning/specs/2026-11-22-milestone-chained-forecast-design.md`

## Objective

`gin milestone list --json` returns, inside `forecast`, the chained dates of every open milestone (`forecast.milestones`) and of every open roadmap epic (`forecast.epics`), computed by the scheduler that already produces `forecast.finish`, with the warning rules of `gin milestone show`. Existing keys keep their names and values; `gin milestone show` output does not change.

**Goal:** gin-console's project timeline (`gin-console-rm-project-timeline`) reads one chained forecast for all milestones and the epics outside them.

**Architecture:** all logic stays in `plugins/gin-workflow/src/scripts/workflow_core/milestone.py` (pure functions over `bd list --json` rows). Track 1 moves the per-epic warning and estimate-source rules of `schedule()` into shared helpers without changing output. Track 2 makes `_place()` return the lane, has `forecast()` keep the per-epic placement it already computes, and documents the contract.

**Tech Stack:** Python 3 standard library, `unittest` run by pytest.

**Global Constraints** (from the spec):

- Only open epics labelled `roadmap` get chained dates: the set `forecast.finish`, `forecast.open_epics`, and `unassigned_epics` already count.
- The chained data lives in `forecast` as `forecast.milestones` and `forecast.epics`; the entries of the top-level `milestones` keep their meaning (each milestone's own schedule from its kickoff).
- The JSON contract is recorded in both `docs/reference/cli.md` and the gin-console contract `gin-harness/docs/changes/gin-harness-6s4-milestones/design.md`; the gin-harness change is committed only with the user's approval at ship.
- Existing keys of `forecast`, of the top-level `milestones` entries, and of the payload keep their names and values; `schema` stays 1. `forecast.finish` equals the latest `planned_end` in `forecast.epics`, and `forecast.open_epics` equals its length when no error stopped the chain.

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
- Problem statement: `forecast()` (`milestone.py:502-549`) chains milestones and the pool of epics outside them but drops the per-epic dates `_place()` computes, and `_place()` does not return the lane. gin-console cannot draw one chained timeline from `show`, which restarts every milestone at its kickoff.
- Success criteria: the spec's acceptance criteria for US-1, US-2, US-3; the tests of Track 2 pass; the existing tests of `tests/workflow_core/test_milestone.py` and `test_milestone_cli.py` pass, with one assertion of `test_pool_only_with_spare_days` narrowed to the old keys.
- Constraints: see Global Constraints; the rules `test-behavior` (test through `forecast()`, `list_payload()`, and the CLI, not private helpers) and `reuse-existing`.
- Non-goals: `lane` on `show` rows; text output of `list` and `show`; honouring `blocks` dependencies between groups when placing; gin-console parsing.

## Approach Options
### Option 1: Extend `forecast()` and share the warning rules
- Summary: `_place()` returns the lane; `forecast()` builds a row per placed epic and the chained dates per milestone; the warning rules of `schedule()` move into a helper both call.
- Pros: the same epic set and cursor as `forecast.finish`, so totals and rows always agree; small diff in one module.
- Cons: `_place()` changes its return shape (two internal callers).

### Option 2: Call `schedule()` per milestone from the cursor
- Summary: reuse `schedule()` rows with `start=cursor`.
- Pros: more reuse of the row building.
- Cons: `schedule()` places closed epics and epics without the `roadmap` label, so its dates disagree with `forecast.finish` in the same output.

### Recommended Approach
- Selected option: Option 1.
- Rationale: chosen in discuss; it keeps one epic set and one cursor for totals and rows.

## Scope
- In scope: `_place()` lane, shared warning and estimate-source helpers, `forecast.milestones`, `forecast.epics`, `confirmed` passed to `forecast()`, tests, `docs/reference/cli.md`, the gin-harness contract table.
- Out of scope: the non-goals above.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Both tracks edit milestone.py and Track 2 builds on the helpers of Track 1.
```

## Tasks
### Track 1: Share the epic warning rules between show and the forecast
- **Dependencies**: none
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/milestone.py:383-444` (add `_Window`, `_window()`, `_estimate_source()`, `_epic_warnings()` above `schedule()`; `schedule()` calls them)
  - Test `tests/workflow_core/test_milestone.py` (unchanged; it pins the `show` output)
  - Test `tests/workflow_core/test_milestone_cli.py` (unchanged)
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** a behaviour-preserving extraction with the exact code given; the existing schedule, spec-readiness, spec-due, exit-warning and CLI exact-payload tests catch any drift.
- **Interfaces**:
  - Produces `_Window` (frozen dataclass: `end: date`, `active: bool`, `kicked_off: bool`, `spec_due: bool`, `integration: date | None`, `working_days: int`).
  - Produces `_window(milestone: Mapping[str, Any], today: date) -> _Window` (raises `ValueError` from `period()` on missing or bad dates).
  - Produces `_estimate_source(epic: Mapping[str, Any], planned_days: int | None, pace: Pace) -> str | None`.
  - Produces `_epic_warnings(epic: Mapping[str, Any], finish: date, group: Mapping[str, Any], beads: Beads, window: _Window | None, today: date, planned_days: int | None, bugs: Mapping[str, int], confirmed: frozenset[str] | None, pace: Pace) -> list[dict[str, Any]]`.
- **Steps**:
  1. Run `timeout 600 python3 -m pytest tests/workflow_core/test_milestone.py tests/workflow_core/test_milestone_cli.py -q` and note the pass count (all pass).
  2. In `milestone.py`, directly above `def schedule(`, add:
     ```python
     @dataclass(frozen=True)
     class _Window:
         """What the warnings of an epic need from its milestone."""
         end: date
         active: bool
         kicked_off: bool
         spec_due: bool
         integration: date | None
         working_days: int


     def _window(milestone: Mapping[str, Any], today: date) -> _Window:
         begin, end = period(milestone)
         state = status(milestone, today)
         return _Window(end=end, active=state == "active", kicked_off=state in ("scheduled", "active"),
                        spec_due=state == "planned" and begin <= _last_of(_workday(today), SPEC_DUE_DAYS),
                        integration=_integration(milestone),
                        working_days=_workdays_before(begin, end + timedelta(days=1)))


     def _estimate_source(epic: Mapping[str, Any], planned_days: int | None, pace: Pace) -> str | None:
         if points_of(epic) is not None:
             return "points"
         if epic_days(epic, pace) is not None:
             return "days"
         return "assumed" if planned_days is not None else None


     def _epic_warnings(epic: Mapping[str, Any], finish: date, group: Mapping[str, Any], beads: Beads,
                        window: _Window | None, today: date, planned_days: int | None, bugs: Mapping[str, int],
                        confirmed: frozenset[str] | None, pace: Pace) -> list[dict[str, Any]]:
         """Warnings of one placed epic, in `show` order. Without a milestone `window` only `unestimated`,
         `external_blocker`, and `open_bugs` apply."""
         still_open = epic.get("status") != "closed"
         warnings: list[dict[str, Any]] = []
         if window is not None and (overflow := workdays_after(window.end, finish)):
             warnings.append({"code": "overflow", "days": overflow})
         if window is not None and window.active and still_open and finish < today:
             warnings.append({"code": "late"})
         if epic_days(epic, pace) is None:
             warnings.append({"code": "unestimated"})
         if any(beads[dep].get("status") != "closed" for dep in _blocks(epic) if dep not in group and dep in beads):
             warnings.append({"code": "external_blocker"})
         if window is not None and confirmed is not None and still_open and epic["id"] not in confirmed:
             if window.kicked_off:
                 warnings.append({"code": "spec_not_ready"})
             elif window.spec_due:
                 warnings.append({"code": "spec_due"})
         if window is not None and window.integration and still_open and finish > window.integration:
             warnings.append({"code": "after_integration"})
         if bugs.get(epic["id"]):
             warnings.append({"code": "open_bugs", "count": bugs[epic["id"]]})
         if window is not None and still_open and planned_days is not None and planned_days > window.working_days:
             warnings.append({"code": "oversized", "days": planned_days - window.working_days})
         return warnings
     ```
  3. Rewrite the body of `schedule()` to use them; keep `period()` first so a milestone without dates still fails before a cycle check:
     ```python
         _, end = period(milestone)
         epics = {epic["id"]: epic for epic in epics_of(milestone["id"], beads)}
         days_of = _planned_days(epics, beads, today, pace)
         planned = _place(epics, _workday(start), lanes_of(milestone, default_lanes), days_of,
                          _lane_off(milestone, builders))
         window = _window(milestone, today)
         bugs = _open_bugs(beads)
         rows = []
         for epic_id in sorted(epics, key=lambda item: (planned[item][0], item)):
             epic = epics[epic_id]
             begin, finish = planned[epic_id]
             days = epic_days(epic, pace)
             points = points_of(epic)
             actual = actual_days(epic, today)
             outside = [beads[dep] for dep in _blocks(epic) if dep not in epics and dep in beads]
             rows.append({
                 "id": epic_id, "title": epic.get("title", ""), "status": epic.get("status"), "estimate_days": days,
                 "points": points, "points_reason": _meta(epic).get("points_reason") if points is not None else None,
                 "estimate_source": _estimate_source(epic, days_of[epic_id], pace),
                 "actual_days": actual,
                 "actual_days_per_point": round(actual / points, 2) if actual is not None and points else None,
                 "remaining_days": remaining_days(epic, beads, today, pace),
                 "assumed_days": days_of[epic_id] if days is None else None,
                 "spec_confirmed": None if confirmed is None else epic_id in confirmed,
                 "planned_start": begin.isoformat(), "planned_end": finish.isoformat(),
                 "depends_on": sorted(dep for dep in _blocks(epic) if dep in epics),
                 "external_depends_on": [{"id": bead["id"], "milestone": _milestone_of(bead, beads)}
                                         for bead in sorted(outside, key=lambda bead: bead["id"])],
                 "warnings": _epic_warnings(epic, finish, epics, beads, window, today, days_of[epic_id], bugs,
                                            confirmed, pace),
             })
         last = max((dates[1] for dates in planned.values()), default=None)
         return {"finish": last.isoformat() if last else None,
                 "overflow_days": workdays_after(end, last) if last else 0, "epics": rows}
     ```
  4. Run the command of step 1: the same pass count, no failure.
  5. Commit on `feat/milestone-chained-forecast`: `refactor(milestone): share epic warnings between show and the forecast (gin-workflow-6yoq)`. No push.
- **Acceptance criteria**: the tests of step 1 pass unchanged; `schedule()` has no inline warning or estimate-source logic left; no other function changes.
- **Estimated complexity**: low

### Track 2: Chained forecast rows in gin milestone list
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/milestone.py:342-380` (`_place()` returns the lane), `:383-444` (`schedule()` unpacks three values), `:502-549` (`forecast()` builds `milestones` and `epics`, takes `confirmed`), `:583` (`list_payload()` passes `confirmed`). Line numbers are before Track 1; Track 1 shifts them down.
  - Test `tests/workflow_core/test_milestone.py:313-419` (`ForecastTests.test_pool_only_with_spare_days` narrowed; new class `ChainedForecastTests` after `ForecastTests`)
  - Test `tests/workflow_core/test_milestone_cli.py:331-342` (`test_list_forecast_line_uses_roadmap_lanes_and_deadline` gains the chained assertions)
  - Modify `docs/reference/cli.md:230` (one sentence appended to the `gin milestone` paragraph)
  - Modify `/home/gin/gin-fam/gin-harness/docs/changes/gin-harness-6s4-milestones/design.md:105-107` (contract rows and the version note; outside this repository, left uncommitted)
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** bounded change in one module with exact code and expected dates; the edge cases (error mid-chain, empty milestone, closed milestone, lanes) are listed as tests.
- **Interfaces**:
  - Consumes `_Window`, `_window()`, `_estimate_source()`, `_epic_warnings()` from Track 1.
  - Changes `_place(...) -> dict[str, tuple[date, date, int | None]]`: `(start, end, lane)`, `lane` from 1, None for an epic without days.
  - Changes `forecast(beads, today, roadmap, default_lanes, builders=(), pace=DEFAULT_PACE, confirmed: frozenset[str] | None = None)`.
  - Produces JSON `forecast.milestones: [{id, start, finish, overflow_days}]` and `forecast.epics: [{id, title, status, milestone, lane, planned_start, planned_end, remaining_days, estimate_source, warnings}]`.
- **Steps**:
  1. Failing tests in `tests/workflow_core/test_milestone.py`:
     - In `ForecastTests.test_pool_only_with_spare_days`, replace the single `assertEqual` with:
       ```python
               self.assertEqual({"deadline": "2026-11-06", "lanes": 1, "start": "2026-10-29", "finish": "2026-11-02",
                                 "overflow_days": 0, "open_epics": 2, "unestimated": 0, "error": None},
                                {key: value for key, value in found.items() if key not in ("milestones", "epics")})
               self.assertEqual({"deadline", "lanes", "start", "finish", "overflow_days", "open_epics", "unestimated",
                                 "error", "milestones", "epics"}, set(found))
       ```
     - After the `ForecastTests` class, add:
       ```python
       def chained(beads, roadmap=None, lanes=1, confirmed=None):
           return milestone.forecast(beads, TODAY, roadmap or milestone.Roadmap(), lanes, confirmed=confirmed)


       class ChainedForecastTests(unittest.TestCase):
           def test_us2_late_milestone_pushes_the_next(self):
               beads = world(milestone_bead("m1", start="2026-11-02", end="2026-11-04", lanes=1),
                             milestone_bead("m2", start="2026-11-05", end="2026-11-20", lanes=1),
                             bead("A", parent="m1", labels=["roadmap"], minutes=days(5)),
                             bead("C", parent="m2", labels=["roadmap"], minutes=days(1)))
               found = chained(beads)
               self.assertEqual([{"id": "m1", "start": "2026-11-02", "finish": "2026-11-06", "overflow_days": 2},
                                 {"id": "m2", "start": "2026-11-09", "finish": "2026-11-09", "overflow_days": 0}],
                                found["milestones"])
               epics = rows(found)
               self.assertIn({"code": "overflow", "days": 2}, epics["A"]["warnings"])
               self.assertEqual(("2026-11-09", "2026-11-09"), span(epics["C"]))

           def test_us1_epics_outside_milestones_follow_the_last_milestone(self):
               beads = world(milestone_bead("m0", status="closed", start="2026-09-01", end="2026-09-30"),
                             milestone_bead("m1", start="2026-11-02", end="2026-11-20", lanes=1),
                             bead("A", parent="m1", labels=["roadmap"], minutes=days(1)),
                             bead("P", labels=["roadmap"], minutes=days(2)),
                             bead("Q", parent="m0", labels=["roadmap"], minutes=days(1)))
               result = chained(beads)
               found = rows(result)
               self.assertEqual(["m1"], [entry["id"] for entry in result["milestones"]])
               self.assertEqual(("m1", 1, "2026-11-02", "2026-11-02"),
                                (found["A"]["milestone"], found["A"]["lane"], *span(found["A"])))
               self.assertEqual((None, 1, "2026-11-03", "2026-11-04"),
                                (found["P"]["milestone"], found["P"]["lane"], *span(found["P"])))
               self.assertEqual((None, 1, "2026-11-05", "2026-11-05"),
                                (found["Q"]["milestone"], found["Q"]["lane"], *span(found["Q"])))

           def test_us1_independent_epics_take_separate_lanes(self):
               beads = world(milestone_bead("m1", lanes=2),
                             bead("A", parent="m1", labels=["roadmap"], minutes=days(1)),
                             bead("B", parent="m1", labels=["roadmap"], minutes=days(1)))
               found = rows(chained(beads))
               self.assertEqual({"A": (1, "2026-11-02"), "B": (2, "2026-11-02")},
                                {key: (row["lane"], row["planned_start"]) for key, row in found.items()})

           def test_us3_rows_match_the_totals_and_carry_every_key(self):
               beads = world(milestone_bead("m1", lanes=1),
                             bead("A", parent="m1", labels=["roadmap"], minutes=days(2)),
                             bead("U", parent="m1", labels=["roadmap"]),
                             bead("P", labels=["roadmap"], meta={"points": 3}))
               found = chained(beads)
               self.assertEqual("2026-11-10", found["finish"])
               self.assertEqual(found["finish"], max(row["planned_end"] for row in found["epics"]))
               self.assertEqual(found["open_epics"], len(found["epics"]))
               self.assertEqual(["A", "U", "P"], [row["id"] for row in found["epics"]])
               self.assertEqual({"id", "title", "status", "milestone", "lane", "planned_start", "planned_end",
                                 "remaining_days", "estimate_source", "warnings"}, set(found["epics"][0]))
               self.assertEqual({"A": "days", "U": "assumed", "P": "points"},
                                {row["id"]: row["estimate_source"] for row in found["epics"]})

           def test_us3_list_payload_keeps_its_keys(self):
               beads = world(milestone_bead(lanes=1), bead("A", parent="m1", labels=["roadmap"], minutes=days(1)))
               payload = milestone.list_payload(beads, TODAY, False, milestone.Roadmap(), 1)
               self.assertEqual({"schema", "milestones", "unassigned_epics", "today", "days_per_point", "forecast"},
                                set(payload))
               self.assertEqual({"id", "title", "status", "start", "end", "kickoff", "lanes", "finish", "epics",
                                 "warnings", "error", "velocity"}, set(payload["milestones"][0]))
               self.assertEqual(["A"], [row["id"] for row in payload["forecast"]["epics"]])

           def test_error_mid_chain_keeps_the_groups_placed_before_it(self):
               beads = world(milestone_bead("m1", start="2026-11-02", end="2026-11-06", lanes=1),
                             milestone_bead("m2", start="2026-11-09", end="2026-11-13"),
                             bead("A", parent="m1", labels=["roadmap"], minutes=days(2)),
                             bead("C", parent="m2", labels=["roadmap"], blocks=["D"]),
                             bead("D", parent="m2", labels=["roadmap"], blocks=["C"]))
               found = chained(beads)
               self.assertIn("dependency cycle", found["error"])
               self.assertEqual([{"id": "m1", "start": "2026-11-02", "finish": "2026-11-03", "overflow_days": 0},
                                 {"id": "m2", "start": None, "finish": None, "overflow_days": 0}], found["milestones"])
               self.assertEqual(["A"], [row["id"] for row in found["epics"]])

           def test_milestone_without_open_roadmap_epics_has_no_dates(self):
               beads = world(milestone_bead("m1"), bead("m2", type="milestone"),
                             bead("r1", labels=["roadmap"], minutes=days(1)))
               found = chained(beads)
               self.assertEqual([{"id": "m2", "start": None, "finish": None, "overflow_days": 0},
                                 {"id": "m1", "start": None, "finish": None, "overflow_days": 0}], found["milestones"])
               self.assertEqual(("2026-10-29", "2026-10-29"), span(rows(found)["r1"]))

           def test_warnings_follow_show_rules_on_chained_dates(self):
               beads = world(milestone_bead("m1", start="2026-11-02", end="2026-11-20", lanes=1),
                             bead("A", parent="m1", labels=["roadmap"], minutes=days(1), blocks=["P"]),
                             bead("P", labels=["roadmap"], minutes=days(30)))
               found = rows(chained(beads, confirmed=frozenset()))
               self.assertIn({"code": "external_blocker"}, found["A"]["warnings"])
               self.assertEqual([], found["P"]["warnings"])

           def test_spec_not_ready_in_an_active_milestone(self):
               beads = world(milestone_bead("m1", start="2026-10-01", end="2026-11-30", kickoff="2026-10-01"),
                             bead("A", parent="m1", labels=["roadmap"], minutes=days(1)))
               self.assertIn({"code": "spec_not_ready"}, rows(chained(beads, confirmed=frozenset()))["A"]["warnings"])
               self.assertNotIn({"code": "spec_not_ready"},
                                rows(chained(beads, confirmed=frozenset({"A"})))["A"]["warnings"])
               payload = milestone.list_payload(beads, TODAY, False, None, 1, frozenset())
               self.assertIn({"code": "spec_not_ready"}, payload["forecast"]["epics"][0]["warnings"])
       ```
       Expected dates use today 2026-10-29 (Thursday) and 1 day per point: in `test_us3_rows_match_the_totals_and_carry_every_key`, A runs 11-02..11-03, U takes the median 2 days 11-04..11-05, and P (3 points) runs 11-06..11-10.
  2. Failing CLI assertions: in `tests/workflow_core/test_milestone_cli.py`, at the end of `test_list_forecast_line_uses_roadmap_lanes_and_deadline`, add:
     ```python
             self.assertEqual([{"id": "t-m1", "start": "2026-11-02", "finish": "2026-11-06", "overflow_days": 2}],
                              payload["forecast"]["milestones"])
             chained = {row["id"]: row for row in payload["forecast"]["epics"]}
             self.assertEqual({"t-a": ("t-m1", 1, "2026-11-02", "2026-11-04"),
                               "t-b": ("t-m1", 2, "2026-11-05", "2026-11-06"),
                               "t-r1": (None, 1, "2026-11-09", "2026-11-09")},
                              {key: (row["milestone"], row["lane"], row["planned_start"], row["planned_end"])
                               for key, row in chained.items()})
             self.assertIn({"code": "overflow", "days": 2}, chained["t-b"]["warnings"])
     ```
     (2 lanes from `AI capacity: 2`; t-b waits for t-a and takes lane 2, the lane that freed first.)
  3. Run `timeout 600 python3 -m pytest tests/workflow_core/test_milestone.py tests/workflow_core/test_milestone_cli.py -q`: the new tests fail (`KeyError: 'milestones'`, `TypeError` for `confirmed`).
  4. `_place()` in `milestone.py`:
     - Return annotation `-> dict[str, tuple[date, date, int | None]]`; append to the docstring: `Returns (start, end, lane) per epic; lane counts from 1 and is None for an epic without days.`
     - `planned: dict[str, tuple[date, date, int | None]] = {}`
     - `dep_start, dep_end, _ = planned[dep]`
     - `planned[epic_id] = (ready[epic_id], ready[epic_id], None)`
     - `planned[epic_id] = (begin, end, lane + 1)`
     In `schedule()`: `begin, finish, _ = planned[epic_id]`.
  5. Replace `forecast()` with:
     ```python
     def forecast(beads: Beads, today: date, roadmap: Roadmap, default_lanes: int,
                  builders: Sequence[str] = (), pace: Pace = DEFAULT_PACE,
                  confirmed: frozenset[str] | None = None) -> dict[str, Any] | None:
         """When every open roadmap epic finishes: open milestones in `end` order on their own lanes, one after
         another, then the unassigned pool on `default_lanes`. `milestones` holds the chained dates of each open
         milestone and `epics` a row per placed epic. None when no roadmap epic is open. On a cycle or bad
         milestone metadata, `error` is set and `finish`, `milestones`, and `epics` cover only the groups placed
         before it."""
         epics = _open_roadmap_epics(beads)
         if not epics:
             return None
         milestones = sorted((bead for bead in beads.values()
                              if bead.get("issue_type") == "milestone" and bead.get("status") != "closed"),
                             key=lambda bead: (str(_meta(bead).get("end", "")), bead["id"]))
         result: dict[str, Any] = {
             "deadline": roadmap.deadline.isoformat() if roadmap.deadline else None, "lanes": default_lanes,
             "start": today.isoformat(), "finish": None, "overflow_days": 0, "open_epics": len(epics),
             "unestimated": sum(epic_days(epic, pace) is None for epic in epics.values()),
             "error": roadmap.error,
             "milestones": [{"id": m["id"], "start": None, "finish": None, "overflow_days": 0} for m in milestones],
             "epics": []}
         chained = {entry["id"]: entry for entry in result["milestones"]}
         groups: list[tuple[Mapping[str, Any] | None, dict[str, Mapping[str, Any]]]] = [
             (m, {k: v for k, v in epics.items() if v.get("parent") == m["id"]}) for m in milestones]
         owned = {k for _, group in groups for k in group}
         groups.append((None, {k: v for k, v in epics.items() if k not in owned}))
         bugs = _open_bugs(beads)
         cursor, ends = _workday(today), []
         try:
             for milestone, group in groups:
                 if not group:
                     continue
                 off, window = None, None
                 if milestone is None:
                     first, lanes = cursor, default_lanes
                 else:
                     begin, end = period(milestone)
                     meta = _meta(milestone)
                     first = max(cursor, parse_date(meta["kickoff"]) if meta.get("kickoff") else begin)
                     lanes = lanes_of(milestone, default_lanes)
                     off = _lane_off(milestone, builders)
                     window = _window(milestone, today)
                 days_of = _planned_days(group, beads, today, pace)
                 planned = _place(group, _workday(first), lanes, days_of, off)
                 for epic_id, epic in group.items():
                     placed_start, placed_end, lane = planned[epic_id]
                     result["epics"].append({
                         "id": epic_id, "title": epic.get("title", ""), "status": epic.get("status"),
                         "milestone": milestone["id"] if milestone is not None else None, "lane": lane,
                         "planned_start": placed_start.isoformat(), "planned_end": placed_end.isoformat(),
                         "remaining_days": remaining_days(epic, beads, today, pace),
                         "estimate_source": _estimate_source(epic, days_of[epic_id], pace),
                         "warnings": _epic_warnings(epic, placed_end, group, beads, window, today, days_of[epic_id],
                                                    bugs, confirmed, pace)})
                 group_ends = [planned[k][1] for k in group if days_of[k] is not None]
                 if group_ends:
                     ends.append(max(group_ends))
                     cursor = _workday(max(group_ends) + timedelta(days=1))
                     if milestone is not None:
                         chained[milestone["id"]].update(start=_workday(first).isoformat(),
                                                         finish=max(group_ends).isoformat(),
                                                         overflow_days=workdays_after(end, max(group_ends)))
         except ValueError as error:  # CycleError and bad milestone metadata
             result["error"] = str(error)
         result["epics"].sort(key=lambda row: (row["planned_start"], row["id"]))
         if ends:
             finish = max(ends)
             result["finish"] = finish.isoformat()
             if roadmap.deadline:
                 result["overflow_days"] = workdays_after(roadmap.deadline, finish)
         return result
     ```
  6. In `list_payload()`, the last line passes `confirmed`: `"forecast": forecast(beads, today, roadmap, default_lanes, builders, pace=pace, confirmed=confirmed)}`.
  7. Run the command of step 3: every test passes.
  8. Docs:
     - `docs/reference/cli.md:230`: append to the end of the paragraph (after `` `actual_days_per_point`. ``):
       `` `forecast` also adds `milestones`, each open milestone in chain order with `id`, `start` (the working day its group is placed from), `finish`, and `overflow_days`, with null dates when it has no open roadmap epic or `error` stopped the chain before it, and `epics`, each placed open roadmap epic with `id`, `title`, `status`, `milestone` (null outside an open milestone), `lane` (from 1), `planned_start`, `planned_end`, `remaining_days`, `estimate_source`, and `warnings` computed with the `show` rules on these chained dates; outside a milestone only `unestimated`, `external_blocker`, and `open_bugs` apply. ``
     - `/home/gin/gin-fam/gin-harness/docs/changes/gin-harness-6s4-milestones/design.md`: after the `forecast.error` row (`:105`), add:
       ```markdown
       | `forecast.milestones` | each open milestone in chain order (`end`, then `id`): `{id, start, finish, overflow_days}` |
       | `forecast.milestones[].start` | working day its group is placed from: the later of the cursor (today, then the working day after the previous group's last `planned_end`) and its `kickoff`, else `start`; `null` when it has no open roadmap epic or `error` stopped the chain at or before it |
       | `forecast.milestones[].finish` | latest `planned_end` of its rows in `forecast.epics`; `null` when `start` is |
       | `forecast.milestones[].overflow_days` | working days after the milestone's `end` up to and including `finish`; 0 when `finish` is `null` |
       | `forecast.epics` | one row per placed open roadmap epic, ordered by `planned_start`, then `id`; with an `error`, only the groups placed before it |
       | `forecast.epics[].milestone` | id of the open milestone the epic is placed in; `null` outside an open milestone (including epics under a closed one) |
       | `forecast.epics[].lane` | the lane the epic takes, from 1, within its milestone's lanes or `forecast.lanes` |
       | `forecast.epics[].planned_start`, `planned_end` | chained dates from today; a milestone that finishes late pushes the next |
       | `forecast.epics[].id`, `title`, `status`, `remaining_days`, `estimate_source` | as on `show` epic rows |
       | `forecast.epics[].warnings` | `show` warning objects computed on the chained dates; outside a milestone only `unestimated`, `external_blocker`, and `open_bugs`; `external_blocker` counts an open `blocks` dependency outside the epic's group, which holds only open roadmap epics |
       ```
       and after the line `` `lanes` and `forecast` were added by milestone-forecast ... `` (`:107`) add the line:
       `` `forecast.milestones` and `forecast.epics` were added by milestone-chained-forecast (gin-workflow-6yoq, 2026-11-22); a gin-workflow before it omits them. ``
       Do not commit in gin-harness; ship commits it with the user's approval.
  9. Commit in this repository on `feat/milestone-chained-forecast`: `feat(milestone): chained per-epic forecast in milestone list (gin-workflow-6yoq)`. No push.
- **Acceptance criteria**: the spec's US-1, US-2, and US-3 criteria hold through the tests of steps 1 and 2; the command of step 3 passes in full; `git -C /home/gin/gin-fam/gin-harness diff --stat` shows only the contract file changed.
- **Estimated complexity**: medium

## Integration
- **Branch**: `feat/milestone-chained-forecast`
- **Merge strategy**: sequential

## Validation
- [ ] `timeout 600 python3 -m pytest tests/workflow_core/test_milestone.py tests/workflow_core/test_milestone_cli.py -q` passes after each track.
- [ ] The full suite runs once in the pre-push hook at ship.
- [ ] Manual: in a project with milestones and roadmap epics (gin-console), `gin milestone list --all --json | python3 -c "import json,sys; f=json.load(sys.stdin)['forecast']; print(f['finish'], max(r['planned_end'] for r in f['epics']), len(f['epics']), f['open_epics'])"` prints equal finish dates and equal counts, after `./install.sh`.

## Notes
- The user may override `Model:` and `Effort:` before plan approval.
- The Parent Bead (gin-workflow-6yoq) stays open until the human-confirmed merge; track beads close after tests and review pass.
- gin-console reads the new keys only after `gin-workflow/install.sh` runs again on its machine.
