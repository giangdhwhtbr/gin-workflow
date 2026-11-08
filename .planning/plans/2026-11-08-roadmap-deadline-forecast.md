# Plan: Roadmap deadline, lanes per milestone, forecast in `gin milestone list`

Spec: `.planning/specs/2026-11-08-roadmap-deadline-forecast-design.md` (Epic: gin-workflow-57fw, confirmed 2026-11-08).

## Objective

`gin milestone list` tells a PM when every open roadmap epic finishes against the project `Deadline:` written in the roadmap file, scheduling each open milestone on its own number of lanes and the unassigned pool on the project default. Milestone schedules become lane-bound. `/gin:roadmap` writes the deadline and estimates for the whole project and reports the forecast. gin-console keeps parsing the JSON (`schema: 1`, additive keys).

## Architecture

- `plugins/gin-workflow/src/scripts/workflow_core/milestone.py` stays pure (no clock, no `bd`, no files). It gains `Roadmap`, `lanes_of`, a greedy lane placer `_place` shared by `schedule` and the new `forecast`, and `lanes`/`forecast` keys in the payloads.
- New pure module `plugins/gin-workflow/src/scripts/workflow_core/roadmap_file.py` reads two bullet lines of the roadmap file into `milestone.Roadmap`.
- `plugins/gin-workflow/src/scripts/workflow_core/milestone_cli.py` resolves the default lanes (roadmap number, team member count, 1), parses `--lanes`, and prints the forecast line.
- Skill, template, and docs follow the CLI.

## Tech Stack

Python 3 standard library only (`re`, `dataclasses`, `datetime`), `unittest` tests run with `python3 -m pytest -n auto`. Beads `bd` 1.0.5 for the CLI tests (skipped when `bd` is missing).

## Global Constraints

Copied from the spec:

- "gin-console keeps reading the same JSON; the new keys are additive." "`schema` stays 1; no existing key changes meaning."
- "Out of scope: gin-console pages for the forecast. They follow as a cross-repo epic in `gin-harness` depending on `external:gin-workflow:milestone-forecast`. Lanes per area, or mapping epics to areas. Holidays, part-time capacity, or fractional lanes. The brownfield starter guide."
- "The reader never raises."
- "Cycles raise `CycleError` naming the loop, as today. Closed epics are still scheduled (they hold their dates and count in `finish`)."
- "A cycle or a reader error (R1) gives `error` set, the other fields filled as far as known, and `gin milestone list` still exits 0."
- Skill: "keeping its anchor phrases (`warn and leave its title, description, and dependencies unchanged`, `7. **Report**`) and under 12,000 characters".
- Repository rules: commit on `feat/roadmap-deadline-forecast` only; `gin rules --files <paths>` before editing.

## Route Rubric

- Choose the weakest model that can do the work.
- Raise the model for broad context or design judgement.
- Raise the effort for intrinsic difficulty: intricate logic, many edge cases, or long chains of steps.

| Kind of work | Model | Effort |
|---|---|---|
| Mechanical edits, documentation, boilerplate | `haiku` | `low` |
| Bounded implementation with a clear spec | `sonnet` | `medium` |
| Cross-module change, security, migration, concurrency | `opus` | `high` |

Unclear requirements never raise the model or effort.

## Requirement Analysis

- Problem statement: the scheduler lets independent epics run in parallel without limit and knows no project deadline; unassigned epics are only counted; AI capacity is free text the CLI cannot use.
- Success criteria: spec US-1..US-5; `gin milestone list` prints the forecast line and `--json` carries `forecast` and per-entry `lanes`; `gin milestone show` is lane-bound and prints `lanes`; `create`/`update` take `--lanes`; the roadmap template has `- Deadline:`; `/gin:roadmap` asks for the deadline, estimates every epic in the plain run, and reports the forecast; all tests pass.
- Constraints: Global Constraints above.
- Non-goals: console UI, areas, holidays, brownfield guide (owned by `gin-workflow-docs-refresh`).

## Approach Options

### Option 1: One placer, groups in sequence
- Summary: extract the greedy lane placer from `schedule`; `forecast` runs it per open milestone in `end` order, then on the pool, each group starting after the previous one's finish.
- Pros: one scheduling algorithm, lanes can differ per group without time-varying capacity, small code.
- Cons: a sprint epic blocked by a pool epic is not moved (already warned by `show`).

### Option 2: One global schedule with time-varying lanes
- Summary: schedule all open epics in one pass where the lane count changes at each milestone boundary.
- Pros: handles overlapping milestones.
- Cons: much more logic for a case the sprint model excludes; harder to explain in the forecast line.

### Recommended Approach
- Selected option: Option 1.
- Rationale: milestones are sprints and run in sequence (user decision 2026-11-08); one placer keeps `show` and `forecast` consistent.

## Scope
- In scope: R1–R9 of the spec inside this repository.
- Out of scope: see Global Constraints.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Tracks 2–4 edit the same two modules in dependency order; parallel workers would conflict on milestone.py and milestone_cli.py.
```

## Tasks

### Track 1: Roadmap file reader
- **Dependencies**: none
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/milestone.py:1-13` (add `Roadmap` dataclass after `Beads`)
  - Create `plugins/gin-workflow/src/scripts/workflow_core/roadmap_file.py`
  - Test `tests/workflow_core/test_roadmap_file.py`
- **Provider role**: `backend`
- **Model:** `haiku`
- **Effort:** `low`
- **Why:** two regexes and a dataclass with the full code given below; the test cases are enumerated.
- **Acceptance criteria**: `test_roadmap_file.py` passes; `read_roadmap` never raises.
- **Estimated complexity**: low

Steps:

1. In `milestone.py`, after `Beads = Mapping[str, Mapping[str, Any]]` add:
   ```python
   from dataclasses import dataclass  # with the other imports


   @dataclass(frozen=True)
   class Roadmap:
       """What `gin milestone list` reads from the roadmap file."""
       deadline: date | None = None
       lanes: int | None = None
       error: str | None = None
   ```
2. Write the failing test `tests/workflow_core/test_roadmap_file.py`:
   ```python
   from datetime import date
   from pathlib import Path
   import sys
   import tempfile
   import unittest

   SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
   sys.path.insert(0, str(SCRIPTS))

   from workflow_core.milestone import Roadmap  # noqa: E402
   from workflow_core.roadmap_file import read_roadmap  # noqa: E402

   HEAD = "# Roadmap: X\n\n## Constraints\n\n"


   class ReadRoadmapTests(unittest.TestCase):
       def write(self, root, body, layout="legacy"):
           path = root / (".planning/roadmap.md" if layout == "legacy" else "docs/roadmap.md")
           path.parent.mkdir(parents=True, exist_ok=True)
           path.write_text(HEAD + body, encoding="utf-8")

       def test_deadline_and_capacity_number(self):
           with tempfile.TemporaryDirectory() as tmp:
               root = Path(tmp)
               self.write(root, "- AI capacity: 2 people building with AI agents, 1 Claude Max account\n- Deadline: 2026-12-31\n")
               self.assertEqual(Roadmap(date(2026, 12, 31), 2, None), read_roadmap(root, "legacy"))

       def test_missing_file_and_missing_lines(self):
           with tempfile.TemporaryDirectory() as tmp:
               root = Path(tmp)
               self.assertEqual(Roadmap(), read_roadmap(root, "legacy"))
               self.write(root, "- AI capacity: one person\n- Deadline:\n")
               self.assertEqual(Roadmap(), read_roadmap(root, "legacy"))

       def test_zero_capacity_is_no_default(self):
           with tempfile.TemporaryDirectory() as tmp:
               root = Path(tmp)
               self.write(root, "- AI capacity: 0\n")
               self.assertEqual(Roadmap(), read_roadmap(root, "legacy"))

       def test_malformed_deadline_is_an_error_not_an_exception(self):
           with tempfile.TemporaryDirectory() as tmp:
               root = Path(tmp)
               self.write(root, "- Deadline: soon\n- AI capacity: 1\n")
               found = read_roadmap(root, "legacy")
               self.assertEqual((None, 1), (found.deadline, found.lanes))
               self.assertEqual("Deadline: soon is not a date (YYYY-MM-DD)", found.error)

       def test_sdd_layout_path(self):
           with tempfile.TemporaryDirectory() as tmp:
               root = Path(tmp)
               self.write(root, "- Deadline: 2027-01-15\n", layout="sdd")
               self.assertEqual(date(2027, 1, 15), read_roadmap(root, "sdd").deadline)
               self.assertIsNone(read_roadmap(root, "legacy").deadline)


   if __name__ == "__main__":
       unittest.main()
   ```
   Run `python3 -m pytest tests/workflow_core/test_roadmap_file.py -q`: fails with `ModuleNotFoundError`.
3. Create `roadmap_file.py`:
   ```python
   """Read the two roadmap lines `gin milestone list` uses: `- Deadline:` and the number that starts `- AI capacity:`."""

   from __future__ import annotations

   from pathlib import Path
   import re

   from .milestone import Roadmap, parse_date
   from .team import ROADMAP

   _DEADLINE = re.compile(r"^- Deadline:[ \t]*(\S+)", re.MULTILINE)
   _CAPACITY = re.compile(r"^- AI capacity:[ \t]*(\d+)", re.MULTILINE)


   def read_roadmap(root: Path, layout: str) -> Roadmap:
       """Never raises: a missing file or line gives None; a malformed deadline fills `error`."""
       path = Path(root) / ROADMAP.get(layout, ROADMAP["legacy"])
       if not path.is_file():
           return Roadmap()
       text = path.read_text(encoding="utf-8")
       capacity = _CAPACITY.search(text)
       lanes = int(capacity.group(1)) if capacity and int(capacity.group(1)) > 0 else None
       deadline = _DEADLINE.search(text)
       if deadline is None:
           return Roadmap(None, lanes, None)
       try:
           return Roadmap(parse_date(deadline.group(1)), lanes, None)
       except ValueError:
           return Roadmap(None, lanes, f"Deadline: {deadline.group(1)} is not a date (YYYY-MM-DD)")
   ```
   `team.ROADMAP` is `{"legacy": ".planning/roadmap.md", "sdd": "docs/roadmap.md"}` (`team.py:16`). If importing `team` pulls heavy imports at module load, copy the two-entry mapping into `roadmap_file.py` instead and say so in the commit message.
4. Run the test file: passes. Run `python3 -m pytest tests/workflow_core/test_milestone.py -q`: still passes. Commit: `feat(milestone): read Deadline and AI capacity from the roadmap file (gin-workflow-57fw)`.

### Track 2: Lane-bound scheduler
- **Dependencies**: none
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/milestone.py:91-152` (`schedule`, `show_payload`; add `lanes_of`, `_check_cycles`, `_place`)
  - Test `tests/workflow_core/test_milestone.py` (`test_req_007_chain_and_parallel`, `test_req_011_show_payload_shape`, new `LaneTests`)
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `high`
- **Why:** intricate greedy placement with blockers, unestimated epics, ties, and cycle detection; the expected dates below must come out exactly.
- **Acceptance criteria**: every test in `test_milestone.py` passes; `test_req_007_chain_and_parallel` passes with `default_lanes=2` and the new one-lane test with the dates below.
- **Estimated complexity**: high

Interfaces produced:
- `lanes_of(milestone: Mapping, default_lanes: int) -> int`
- `_place(epics: Mapping[str, Mapping], first: date, lanes: int) -> dict[str, tuple[date, date]]` (raises `CycleError`)
- `schedule(milestone, beads, start, today, default_lanes: int = 1) -> dict` (same output keys as today)
- `show_payload(milestone, beads, start, today, default_lanes: int = 1) -> dict` (adds `"lanes": int`)

Steps:

1. Change the test helper and the parallel test in `test_milestone.py`:
   ```python
   def plan(beads, start="2026-11-02", today=TODAY, milestone_id="m1", lanes=1):
       return milestone.schedule(beads[milestone_id], beads, D(start), today, lanes)
   ```
   In `test_req_007_chain_and_parallel` call `plan(beads, lanes=2)` (expectations unchanged). In `test_req_011_show_payload_shape` add `"lanes": 1,` after `"today": "2026-10-29",`. Add a class:
   ```python
   class LaneTests(unittest.TestCase):
       def test_one_lane_runs_estimated_epics_in_sequence(self):
           beads = world(milestone_bead(), bead("A", parent="m1", minutes=days(3)),
                         bead("B", parent="m1", minutes=days(2), blocks=["A"]), bead("C", parent="m1", minutes=days(4)))
           result = plan(beads)
           found = rows(result)
           self.assertEqual(("2026-11-02", "2026-11-04"), span(found["A"]))
           self.assertEqual(("2026-11-05", "2026-11-10"), span(found["C"]))
           self.assertEqual(("2026-11-11", "2026-11-12"), span(found["B"]))
           self.assertEqual("2026-11-12", result["finish"])

       def test_two_lanes_split_three_equal_epics(self):
           beads = world(milestone_bead(), *(bead(name, parent="m1", minutes=days(2)) for name in "ABC"))
           found = rows(plan(beads, lanes=2))
           self.assertEqual(("2026-11-02", "2026-11-03"), span(found["A"]))
           self.assertEqual(("2026-11-02", "2026-11-03"), span(found["B"]))
           self.assertEqual(("2026-11-04", "2026-11-05"), span(found["C"]))

       def test_blocker_wins_over_a_free_lane(self):
           beads = world(milestone_bead(), bead("A", parent="m1", minutes=days(3)),
                         bead("B", parent="m1", minutes=days(1), blocks=["A"]))
           self.assertEqual(("2026-11-05", "2026-11-05"), span(rows(plan(beads, lanes=2))["B"]))

       def test_unestimated_epic_takes_no_lane(self):
           beads = world(milestone_bead(), bead("U", parent="m1"), bead("A", parent="m1", minutes=days(1)),
                         bead("B", parent="m1", minutes=days(1)))
           found = rows(plan(beads))
           self.assertEqual(("2026-11-02", "2026-11-02"), span(found["U"]))
           self.assertEqual(("2026-11-02", "2026-11-02"), span(found["A"]))
           self.assertEqual(("2026-11-03", "2026-11-03"), span(found["B"]))

       def test_lanes_of_metadata_then_default(self):
           self.assertEqual(2, milestone.lanes_of(milestone_bead(lanes=2), 1))
           self.assertEqual(2, milestone.lanes_of(milestone_bead(lanes="2"), 1))
           self.assertEqual(3, milestone.lanes_of(milestone_bead(), 3))
           self.assertEqual(3, milestone.lanes_of(milestone_bead(lanes="0"), 3))
           self.assertEqual(1, milestone.show_payload(world(milestone_bead())["m1"], world(milestone_bead()), None, TODAY)["lanes"])
   ```
   Run `python3 -m pytest tests/workflow_core/test_milestone.py -q`: the new tests and the two changed ones fail (`TypeError` on the extra argument).
2. In `milestone.py` replace `schedule` (lines 91–141) with:
   ```python
   def lanes_of(milestone: Mapping[str, Any], default_lanes: int) -> int:
       """The milestone's `lanes` metadata (int or digit string), else the default."""
       text = str(_meta(milestone).get("lanes", ""))
       return int(text) if re.fullmatch(r"[1-9][0-9]*", text) else default_lanes


   def _check_cycles(epics: Mapping[str, Mapping[str, Any]]) -> None:
       done: set[str] = set()

       def visit(epic_id: str, path: list[str]) -> None:
           if epic_id in done:
               return
           if epic_id in path:
               loop = path[path.index(epic_id):] + [epic_id]
               raise CycleError("dependency cycle: " + " -> ".join(loop))
           for dep in _blocks(epics[epic_id]):
               if dep in epics:
                   visit(dep, path + [epic_id])
           done.add(epic_id)

       for epic_id in sorted(epics):
           visit(epic_id, [])


   def _place(epics: Mapping[str, Mapping[str, Any]], first: date, lanes: int) -> dict[str, tuple[date, date]]:
       """Greedy placement on `lanes` lanes from the working day `first`: the ready epic with the earliest allowed
       start (ties by id) takes the lane that frees first. Unestimated epics take no lane and no days."""
       _check_cycles(epics)
       planned: dict[str, tuple[date, date]] = {}
       free = [first] * lanes
       while len(planned) < len(epics):
           ready: dict[str, date] = {}
           for epic_id, epic in epics.items():
               deps = [dep for dep in _blocks(epic) if dep in epics]
               if epic_id in planned or any(dep not in planned for dep in deps):
                   continue
               begin = first
               for dep in deps:
                   dep_start, dep_end = planned[dep]
                   estimated = estimate_days(epics[dep].get("estimated_minutes")) is not None
                   begin = max(begin, _workday(dep_end + timedelta(days=1)) if estimated else dep_start)
               ready[epic_id] = begin
           epic_id = min(ready, key=lambda item: (ready[item], item))
           days = estimate_days(epics[epic_id].get("estimated_minutes"))
           if days is None:
               planned[epic_id] = (ready[epic_id], ready[epic_id])
               continue
           lane = min(range(lanes), key=lambda index: free[index])
           begin = max(ready[epic_id], free[lane])
           end = _last_of(begin, days)
           planned[epic_id] = (begin, end)
           free[lane] = _workday(end + timedelta(days=1))
       return planned


   def schedule(milestone: Mapping[str, Any], beads: Beads, start: date, today: date,
                default_lanes: int = 1) -> dict[str, Any]:
       _, end = period(milestone)
       epics = {epic["id"]: epic for epic in epics_of(milestone["id"], beads)}
       planned = _place(epics, _workday(start), lanes_of(milestone, default_lanes))
       active = status(milestone, today) == "active"
       rows = []
       for epic_id in sorted(epics, key=lambda item: (planned[item][0], item)):
           ...  # lines 118–138 unchanged
       last = max((dates[1] for dates in planned.values()), default=None)
       return {"finish": last.isoformat() if last else None,
               "overflow_days": workdays_after(end, last) if last else 0, "epics": rows}
   ```
   The row loop (today's lines 117–138) is kept verbatim. In `show_payload` add the parameter `default_lanes: int = 1`, add `"lanes": lanes_of(milestone, default_lanes),` after `"today": today.isoformat(),`, and pass `default_lanes` to `schedule`.
3. Run `python3 -m pytest tests/workflow_core/test_milestone.py tests/workflow_core/test_milestone_cli.py -q`: `test_milestone.py` passes; in `test_milestone_cli.py` only `test_req_011_show_exact_payload` fails (new `lanes` key; Track 4 fixes it). Commit: `feat(milestone): lane-bound schedule with lanes per milestone (gin-workflow-57fw)`.

### Track 3: Forecast over every open epic
- **Dependencies**: Track 1, Track 2
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/milestone.py` (`list_payload`; add `forecast` before it)
  - Test `tests/workflow_core/test_milestone.py` (new `ForecastTests`, `test_req_011_list_payload_counts`)
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `high`
- **Why:** group sequencing with per-group lanes, several error paths, and exact dates.
- **Acceptance criteria**: `ForecastTests` pass; `list_payload` returns `forecast` and per-entry `lanes`; existing list tests pass.
- **Estimated complexity**: high

Interfaces produced:
- `forecast(beads: Beads, today: date, roadmap: Roadmap, default_lanes: int) -> dict | None`
- `list_payload(beads, today, include_closed, roadmap: Roadmap | None = None, default_lanes: int = 1) -> dict` (adds `forecast`, per-entry `lanes`)

Steps:

1. Add tests (`TODAY` is Thursday 2026-10-29; `R = milestone.Roadmap`):
   ```python
   class ForecastTests(unittest.TestCase):
       def forecast(self, beads, roadmap=None, lanes=1):
           return milestone.forecast(beads, TODAY, roadmap or milestone.Roadmap(), lanes)

       def test_pool_only_with_spare_days(self):
           beads = world(bead("r1", labels=["roadmap"], minutes=days(2)), bead("r2", labels=["roadmap"], minutes=days(1)))
           found = self.forecast(beads, milestone.Roadmap(deadline=D("2026-11-06")))
           self.assertEqual({"deadline": "2026-11-06", "lanes": 1, "start": "2026-10-29", "finish": "2026-11-02",
                             "overflow_days": 0, "open_epics": 2, "unestimated": 0, "error": None}, found)

       def test_overflow_counts_working_days_after_the_deadline(self):
           beads = world(bead("r1", labels=["roadmap"], minutes=days(2)), bead("r2", labels=["roadmap"], minutes=days(1)))
           self.assertEqual(1, self.forecast(beads, milestone.Roadmap(deadline=D("2026-10-30")))["overflow_days"])

       def test_without_deadline(self):
           beads = world(bead("r1", labels=["roadmap"], minutes=days(1)))
           found = self.forecast(beads)
           self.assertEqual((None, 0, "2026-10-29"), (found["deadline"], found["overflow_days"], found["finish"]))

       def test_milestones_in_end_order_with_their_own_lanes_then_the_pool(self):
           beads = world(milestone_bead("m2", start="2026-11-09", end="2026-11-13", lanes=2),
                         milestone_bead("m1", start="2026-11-02", end="2026-11-06", lanes=1),
                         bead("A", parent="m1", minutes=days(2), labels=["roadmap"]),
                         bead("B", parent="m1", minutes=days(2), labels=["roadmap"]),
                         bead("C", parent="m2", minutes=days(3), labels=["roadmap"]),
                         bead("D", parent="m2", minutes=days(1), labels=["roadmap"]),
                         bead("r1", labels=["roadmap"], minutes=days(1)))
           found = self.forecast(beads, milestone.Roadmap(deadline=D("2026-11-13")))
           self.assertEqual(("2026-11-12", 0, 5), (found["finish"], found["overflow_days"], found["open_epics"]))

       def test_closed_epics_and_closed_milestones_are_left_out(self):
           beads = world(milestone_bead("m0", status="closed", start="2026-09-01", end="2026-09-30"),
                         bead("done", labels=["roadmap"], minutes=days(5), status="closed"),
                         bead("r1", labels=["roadmap"], minutes=days(1)))
           found = self.forecast(beads)
           self.assertEqual(("2026-10-29", 1), (found["finish"], found["open_epics"]))

       def test_pool_epic_blocked_by_a_sprint_epic_starts_after_it(self):
           beads = world(milestone_bead(lanes=1), bead("A", parent="m1", minutes=days(2), labels=["roadmap"]),
                         bead("r1", labels=["roadmap"], minutes=days(1), blocks=["A"]),
                         bead("r2", labels=["roadmap"], minutes=days(1)))
           self.assertEqual("2026-11-05", self.forecast(beads)["finish"])

       def test_cycle_sets_error(self):
           beads = world(bead("r1", labels=["roadmap"], blocks=["r2"]), bead("r2", labels=["roadmap"], blocks=["r1"]))
           found = self.forecast(beads)
           self.assertIn("dependency cycle", found["error"])
           self.assertIsNone(found["finish"])

       def test_reader_error_is_passed_through_with_the_dates(self):
           beads = world(bead("r1", labels=["roadmap"], minutes=days(1)))
           found = self.forecast(beads, milestone.Roadmap(error="Deadline: soon is not a date (YYYY-MM-DD)"))
           self.assertEqual(("Deadline: soon is not a date (YYYY-MM-DD)", "2026-10-29"), (found["error"], found["finish"]))

       def test_no_open_epic_gives_none(self):
           self.assertIsNone(self.forecast(world(bead("done", labels=["roadmap"], status="closed"))))
           self.assertIsNone(self.forecast(world(bead("t", type="task", labels=["roadmap"]))))

       def test_all_unestimated(self):
           beads = world(bead("r1", labels=["roadmap"]), bead("r2", labels=["roadmap"]))
           found = self.forecast(beads)
           self.assertEqual((None, 2, 2), (found["finish"], found["unestimated"], found["open_epics"]))

       def test_list_payload_carries_lanes_and_forecast(self):
           beads = world(milestone_bead(lanes=2), bead("A", parent="m1", minutes=days(1), labels=["roadmap"]))
           payload = milestone.list_payload(beads, TODAY, False, milestone.Roadmap(deadline=D("2026-11-30")), 1)
           self.assertEqual(2, payload["milestones"][0]["lanes"])
           self.assertEqual("2026-11-02", payload["forecast"]["finish"])
           self.assertIsNone(milestone.list_payload(world(milestone_bead()), TODAY, False)["forecast"])
   ```
   In `test_req_011_list_payload_counts` add `self.assertEqual(1, payload["milestones"][0]["lanes"])` and `self.assertEqual(3, payload["forecast"]["open_epics"])`. Run the file: the new tests fail with `AttributeError`.
2. Add `forecast` above `list_payload`:
   ```python
   def _open_roadmap_epics(beads: Beads) -> dict[str, Mapping[str, Any]]:
       return {bead["id"]: bead for bead in beads.values()
               if bead.get("issue_type") == "epic" and "roadmap" in (bead.get("labels") or [])
               and bead.get("status") != "closed"}


   def forecast(beads: Beads, today: date, roadmap: Roadmap, default_lanes: int) -> dict[str, Any] | None:
       """When every open roadmap epic finishes: open milestones in `end` order on their own lanes, one after
       another, then the unassigned pool on `default_lanes`. None when no roadmap epic is open."""
       epics = _open_roadmap_epics(beads)
       if not epics:
           return None
       result: dict[str, Any] = {
           "deadline": roadmap.deadline.isoformat() if roadmap.deadline else None, "lanes": default_lanes,
           "start": today.isoformat(), "finish": None, "overflow_days": 0, "open_epics": len(epics),
           "unestimated": sum(estimate_days(epic.get("estimated_minutes")) is None for epic in epics.values()),
           "error": roadmap.error}
       milestones = sorted((bead for bead in beads.values()
                            if bead.get("issue_type") == "milestone" and bead.get("status") != "closed"),
                           key=lambda bead: (str(_meta(bead).get("end", "")), bead["id"]))
       groups: list[tuple[Mapping[str, Any] | None, dict[str, Mapping[str, Any]]]] = [
           (m, {k: v for k, v in epics.items() if v.get("parent") == m["id"]}) for m in milestones]
       owned = {k for _, group in groups for k in group}
       groups.append((None, {k: v for k, v in epics.items() if k not in owned}))
       cursor, ends = _workday(today), []
       try:
           for milestone, group in groups:
               if milestone is None:
                   first, lanes = cursor, default_lanes
               else:
                   begin, _ = period(milestone)
                   meta = _meta(milestone)
                   first = max(cursor, parse_date(meta["kickoff"]) if meta.get("kickoff") else begin)
                   lanes = lanes_of(milestone, default_lanes)
               planned = _place(group, _workday(first), lanes)
               group_ends = [planned[k][1] for k, v in group.items() if estimate_days(v.get("estimated_minutes")) is not None]
               if group_ends:
                   ends.append(max(group_ends))
                   cursor = _workday(max(group_ends) + timedelta(days=1))
       except ValueError as error:  # CycleError and bad milestone metadata
           result["error"] = str(error)
           return result
       if ends:
           finish = max(ends)
           result["finish"] = finish.isoformat()
           if roadmap.deadline:
               result["overflow_days"] = workdays_after(roadmap.deadline, finish)
       return result
   ```
   In `list_payload`: signature `list_payload(beads: Beads, today: date, include_closed: bool, roadmap: Roadmap | None = None, default_lanes: int = 1)`; first line `roadmap = roadmap or Roadmap()`; in `entry` add `"lanes": lanes_of(milestone, default_lanes),` after `"kickoff"`; pass `default_lanes` to `schedule`; return `{"schema": SCHEMA, "milestones": entries, "unassigned_epics": unassigned, "today": today.isoformat(), "forecast": forecast(beads, today, roadmap, default_lanes)}`.
   Expected dates in the sequence test: m1 (lanes 1) A 11-02..11-03, B 11-04..11-05; m2 starts max(11-06, 11-09) = 11-09 with 2 lanes: C 11-09..11-11, D 11-09; pool r1 on 11-12.
3. Run `python3 -m pytest tests/workflow_core/test_milestone.py -q`: passes. Commit: `feat(milestone): forecast every open roadmap epic against the deadline (gin-workflow-57fw)`.

### Track 4: CLI: `--lanes`, default lanes, forecast line
- **Dependencies**: Track 3
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/milestone_cli.py:31-64` (parser), `:112-130` (text), `:145-160` (create, update), `:268-281` (`_run`)
  - Test `tests/workflow_core/test_milestone_cli.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** bounded wiring with exact strings given; the CLI tests need `bd` and a roadmap file in the temp repo.
- **Acceptance criteria**: `test_milestone_cli.py` passes; `gin milestone list` on this repo prints a `forecast:` line and exits 0.
- **Estimated complexity**: medium

Interfaces consumed: `core.forecast`, `core.lanes_of`, `core.Roadmap`, `roadmap_file.read_roadmap`, `specs.sdd_config`, `team.load_team`.

Steps:

1. Tests. Update the two exact payloads: in `test_req_011_show_exact_payload` add `"lanes": 1,` after `"today": "2026-10-29",`; in `test_req_011_list_exact_payload` add `"forecast": None,` after `"unassigned_epics": 0,` and `"lanes": 1,` after `"kickoff": None,` (t-a and t-b carry no `roadmap` label, so the forecast is null). Add:
   ```python
   def write_roadmap(self, body):
       path = self.root / ".planning/roadmap.md"
       path.parent.mkdir(parents=True, exist_ok=True)
       path.write_text("# Roadmap: T\n\n## Constraints\n\n" + body, encoding="utf-8")

   def test_lanes_on_create_and_update(self):
       code, out, err = self.run_cli("create", "M1", "--start", "2026-11-02", "--end", "2026-12-18", "--lanes", "2")
       self.assertEqual(0, code, err)
       self.assertEqual({"start": "2026-11-02", "end": "2026-12-18", "lanes": 2}, self.show(out.strip())["metadata"])
       self.assertEqual(2, json.loads(self.run_cli("show", out.strip(), "--json")[1])["lanes"])
       self.assertEqual(0, self.run_cli("update", out.strip(), "--lanes", "3")[0])
       self.assertEqual("3", str(self.show(out.strip())["metadata"]["lanes"]))
       self.assertEqual(3, json.loads(self.run_cli("show", out.strip(), "--json")[1])["lanes"])

   def test_bad_lanes_is_refused_before_any_write(self):
       for value in ("0", "-1", "two"):
           err = self.refused("create", "M1", "--start", "2026-11-02", "--end", "2026-12-18", "--lanes", value)
           self.assertIn("lanes must be a positive whole number", err)

   def test_list_forecast_line_uses_roadmap_lanes_and_deadline(self):
       self.seed()
       self.bd("create", "R1", "--id", "t-r1", "--type", "epic", "--labels", "roadmap", "--estimate", "480")
       self.bd("update", "t-a", "--add-label", "roadmap")
       self.bd("update", "t-b", "--add-label", "roadmap")
       self.write_roadmap("- AI capacity: 2 accounts\n- Deadline: 2026-11-13\n")
       code, out, err = self.run_cli("list")
       self.assertEqual(0, code, err)
       self.assertIn("forecast: finish 2026-11-09, deadline 2026-11-13, 4 working days spare, lanes 2, 3 open epics", out)
       payload = json.loads(self.run_cli("list", "--json")[1])
       self.assertEqual(2, payload["milestones"][0]["lanes"])
       self.assertEqual("2026-11-09", payload["forecast"]["finish"])

   def test_list_forecast_without_deadline_and_with_a_bad_one(self):
       self.bd("create", "R1", "--id", "t-r1", "--type", "epic", "--labels", "roadmap")
       code, out, _ = self.run_cli("list")
       self.assertEqual(0, code)
       self.assertIn("forecast: finish unknown, no deadline, lanes 1, 1 open epics, 1 unestimated", out)
       self.write_roadmap("- Deadline: soon\n")
       code, out, _ = self.run_cli("list")
       self.assertEqual(0, code)
       self.assertIn("forecast: error: Deadline: soon is not a date (YYYY-MM-DD), lanes 1, 1 open epics, 1 unestimated", out)

   def test_default_lanes_chain(self):
       from workflow_core.milestone import Roadmap
       team = {"team": {"members": {"a@x.io": {"roles": ["dev"], "login": "a"}, "b@x.io": {"roles": ["dev"], "login": "b"}}}}
       self.assertEqual(4, milestone_cli._default_lanes(team, Roadmap(lanes=4)))
       self.assertEqual(2, milestone_cli._default_lanes(team, Roadmap()))
       self.assertEqual(1, milestone_cli._default_lanes({}, Roadmap()))
   ```
   If `load_team` needs more keys than `members` to return a config, give the test dict the minimal extra keys it asks for and keep the asserted values. Dates: t-a 3d and t-b 2d (blocked) on 2 lanes from 11-02 give 11-02..11-04 and 11-05..11-06; the pool epic R1 (1d) follows on 11-09; spare to 11-13 is 4 working days. Run the file: the new tests fail.
2. Implement in `milestone_cli.py`:
   - Parser: add `item.add_argument("--lanes")` to `create` and `update`.
   - Helpers after `_date`:
     ```python
     def _lanes(text: str) -> int:
         if not re.fullmatch(r"[1-9][0-9]*", text):
             raise MilestoneError("lanes must be a positive whole number")
         return int(text)


     def _roadmap(root: Path, config: dict[str, Any]) -> core.Roadmap:
         from .roadmap_file import read_roadmap
         from .specs import sdd_config

         return read_roadmap(root, sdd_config(config)["layout"])


     def _default_lanes(config: Mapping[str, Any], roadmap: core.Roadmap) -> int:
         """Roadmap `AI capacity:` number, else the team member count, else 1."""
         from . import team as team_core

         if roadmap.lanes:
             return roadmap.lanes
         team = team_core.load_team(config)
         return len(team.members) if team is not None and team.members else 1
     ```
   - `_create`: build `meta = {"start": ..., "end": ...}` as a dict, `if args.lanes: meta["lanes"] = _lanes(args.lanes)` before the `_bd` call, then `json.dumps(meta)`.
   - `_update`: `argv += ["--set-metadata", f"lanes={_lanes(args.lanes)}"] if args.lanes else []` before `_bd`, with `_lanes` evaluated before any write (it raises first).
   - `_show_text`: first line ends with `..., schedule from {schedule_start}{preview}, lanes {payload['lanes']}`.
   - Forecast text:
     ```python
     def _forecast_text(forecast: dict[str, Any]) -> str:
         if forecast["error"]:
             head = f"forecast: error: {forecast['error']}"
         else:
             head = f"forecast: finish {forecast['finish'] or 'unknown'}"
             if not forecast["deadline"]:
                 head += ", no deadline"
             elif forecast["finish"] is None:
                 head += f", deadline {forecast['deadline']}"
             elif forecast["overflow_days"]:
                 head += f", deadline {forecast['deadline']}, overflow {forecast['overflow_days']} working days"
             else:
                 spare = core.workdays_after(date.fromisoformat(forecast["finish"]), date.fromisoformat(forecast["deadline"]))
                 head += f", deadline {forecast['deadline']}, " + (f"{spare} working days spare" if spare else "on the deadline")
         tail = f", lanes {forecast['lanes']}, {forecast['open_epics']} open epics"
         if forecast["unestimated"]:
             tail += f", {forecast['unestimated']} unestimated"
         return head + tail
     ```
     In `_list_text`, after the `unassigned roadmap epics` line: `if payload["forecast"]: lines.append(_forecast_text(payload["forecast"]))`.
   - `_run`: for `list`, `roadmap = _roadmap(root, config)`; `payload = core.list_payload(_beads(root), _today(), args.all, roadmap, _default_lanes(config, roadmap))`. For `show`, `payload = core.show_payload(_milestone(beads, args.id), beads, start, _today(), _default_lanes(config, _roadmap(root, config)))`.
3. Run `python3 -m pytest tests/workflow_core/test_milestone_cli.py tests/workflow_core/test_milestone.py -q`: passes. Run `gin milestone list` in the worktree: the last line starts with `forecast:` and the exit code is 0 (this repo has no `Deadline:` line, so it says `no deadline`). Commit: `feat(milestone): --lanes, default lanes from the roadmap or team, forecast line (gin-workflow-57fw)`.

### Track 5: Template, roadmap skill, docs
- **Dependencies**: Track 4
- **Files**:
  - Modify `plugins/gin-workflow/src/templates/roadmap.md:9-17`
  - Modify `plugins/gin-workflow/src/skills/roadmap/SKILL.md:17-20,25,27-30,36`
  - Modify `docs/reference/cli.md:198-226`
  - Modify `docs/guides/customizing-templates.md:49-52`, `docs/guides/customizing-templates.vi.md` (same section)
  - Modify `docs/reference/skills.md:49`, `docs/reference/skills.vi.md` (roadmap row)
  - Modify `docs/concepts/lifecycle.md:23`
  - Test `tests/workflow_core/test_specs.py:290` (template assertion), `tests/workflow_core/test_token_budget.py`, `tests/workflow_core/test_epic_comments.py` (anchors, unchanged)
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** the skill text must stay compact and keep two tested anchor phrases while changing five numbered steps; the Vietnamese mirrors need a faithful translation.
- **Acceptance criteria**: `gin specs template roadmap.md` prints `- Deadline:`; `wc -c plugins/gin-workflow/src/skills/roadmap/SKILL.md` < 12000; `test_specs.py`, `test_epic_comments.py`, `test_skill_routing.py`, `test_token_budget.py` pass; `mkdocs build --strict` passes if mkdocs is installed (skip otherwise and say so).
- **Estimated complexity**: medium

Steps:

1. Test first: in `test_specs.py` after the `Depends on:` assertion add `self.assertIn("- Deadline:", run_specs(root, "template", "roadmap.md").stdout)`. Run `python3 -m pytest tests/workflow_core/test_specs.py -q -k template`: fails.
2. Template `roadmap.md`: under `## Constraints` make the lines
   ```
   - AI capacity:
   - Deadline:
   ```
   and add to the header comment, after "A plain /roadmap omits them and lists its epics under Unassigned.": `gin milestone list reads two Constraints lines: Deadline: (YYYY-MM-DD, the project deadline) and the whole number that starts AI capacity: (the default lanes: streams of work that run one epic at a time).` Run the test: passes.
3. Skill `SKILL.md`, exact edits (keep everything else):
   - Line 17 (`--milestone` step 2), append: ` Also ask the sprint's lanes (streams of work that each run one epic at a time), default the number that starts the \`AI capacity:\` line; step 6 writes a different value with \`gin milestone update <id> --lanes <n>\`.`
   - Line 18, replace `stop when the sum of estimates reaches the working days (Monday to Friday) between \`start\` and \`end\` of \`gin milestone show <id> --json\`` with `stop when the sum of estimates reaches the lanes times the working days (Monday to Friday) between \`start\` and \`end\` of \`gin milestone show <id> --json\``.
   - Line 20, after `estimates with \`gin milestone estimate <epic> <days>\`.` insert ` Set the lanes with \`gin milestone update <id> --lanes <n>\` when they differ from \`lanes\` in \`gin milestone show <id> --json\`.`
   - Line 25 (Steps 2), after `Step 5 writes the answer on that line.` insert ` Also ask for the project deadline (a date, or none); when \`## Constraints\` has a \`Deadline:\` line, show it for confirmation instead. Step 5 writes \`- Deadline: YYYY-MM-DD\` (or leaves it empty) and starts \`AI capacity:\` with the number of lanes; \`gin milestone list\` reads both.`
   - Line 27 (Steps 4), after `\`Risks:\`.` insert ` Every run proposes \`Estimate: <working days>\` per epic by the method of \`--milestone\` step 2.`
   - Line 28 (Steps 5), replace `A plain \`/roadmap\` omits the milestone heading and the \`Milestone:\` and \`Estimate:\` lines, and puts its epics under \`## Unassigned\`.` with `A plain \`/roadmap\` omits the milestone heading and the \`Milestone:\` lines, keeps \`Estimate:\`, and puts its epics under \`## Unassigned\`.`
   - Steps 6, add a bullet before `- an epic labelled \`roadmap\` that the file no longer lists`: `- estimates: \`gin milestone estimate <epic> <days>\` for an epic whose \`estimated_minutes\` in Beads is empty, or whose value the PM changed in this run; otherwise Beads wins and a differing \`Estimate:\` line is reported ("E1 estimate: file 5, Beads 8"), not written;`
   - Line 36 (`7. **Report**`), after `\`gin task ready\` epics,` insert ` the forecast from \`gin milestone list --json\` (\`forecast\`: finish, deadline, spare or overflow working days, unestimated count; overflow is reported, never blocks),`. The line keeps `[gin roadmap]`.
   Run `wc -c plugins/gin-workflow/src/skills/roadmap/SKILL.md` (expect about 10,900, under 12,000) and `python3 -m pytest tests/workflow_core/test_epic_comments.py tests/workflow_core/test_skill_routing.py tests/workflow_core/test_token_budget.py -q`: passes.
4. `docs/reference/cli.md`, `## gin milestone`:
   - Synopsis: `gin milestone create TITLE --start YYYY-MM-DD --end YYYY-MM-DD [--lanes N]` and `gin milestone update ID [--title TITLE] [--start YYYY-MM-DD] [--end YYYY-MM-DD] [--lanes N]`.
   - Prose, after the sentence on `list`: `It ends with a forecast line when any \`roadmap\` epic is open: when every open epic finishes against the roadmap's \`Deadline:\`, with the spare or overflow working days, the default lanes, and the open and unestimated counts. Open milestones are scheduled one after another in \`end\` order, each on its own lanes, then the unassigned epics on the default lanes.`
   - After the sentence on `show`: `Schedules are lane-bound: a lane runs one epic at a time, so with one lane estimated epics run in sequence and independent epics only overlap with two or more lanes. A milestone's lanes come from its \`lanes\` metadata, else the whole number that starts the \`AI capacity:\` line of the roadmap file, else the number of \`team.members\`, else 1. A milestone planned before lanes existed now shows later dates and may gain \`overflow\` warnings; set \`--lanes\` or the \`AI capacity:\` number to match the team.`
   - JSON sentence: `\`--json\` prints \`schema: 1\` with the additive keys \`lanes\` (per milestone) and \`forecast\` (\`deadline\`, \`lanes\`, \`start\`, \`finish\`, \`overflow_days\`, \`open_epics\`, \`unestimated\`, \`error\`; null without an open roadmap epic); fields are defined in the gin-console contract (...) and only ever added to.`
   - Table: `create` row adds `; \`--lanes N\` stores the lane count`; `update` row becomes `Change the title, either date, or the lanes of an open milestone`.
   - Exit codes: add `a \`--lanes\` that is not a positive whole number` to the exit 1 list; add after the exit codes: `A malformed \`Deadline:\` line or a dependency cycle among open epics is reported in \`forecast.error\`; \`list\` still exits 0.`
5. `docs/guides/customizing-templates.md`, end of `## Spec, story, and roadmap templates`: add a paragraph: `The roadmap template's \`## Constraints\` has two lines that \`gin milestone list\` reads: \`- Deadline: YYYY-MM-DD\` (the project deadline the forecast is measured against) and \`- AI capacity: <n> ...\`, whose leading whole number is the default number of lanes. Keep both bullets when you override the template; free text after the number is ignored.` Mirror it in `customizing-templates.vi.md` in Vietnamese.
6. `docs/reference/skills.md:49`: row text becomes `Turn the tech-doc set or a product brief into a confirmed roadmap and dependent Beads epics with a project deadline and an estimate per epic; reconcile both on re-run; reports the \`gin milestone list\` forecast; with the SDD layout each epic carries \`Capabilities:\`; \`--milestone <id>\` plans a dated milestone with its own lanes`. Same row in `skills.vi.md` in Vietnamese. `docs/concepts/lifecycle.md:23`: replace `With \`--milestone <id>\` it plans a dated milestone over those epics;` with `It writes the project deadline and an estimate per epic and reports the forecast; with \`--milestone <id>\` it plans a dated milestone over those epics on its own lanes;`.
7. Run `python3 -m pytest -n auto -q` (full suite) and, when available, `mkdocs build --strict`. Commit: `docs(milestone): Deadline line, lanes, forecast in template, roadmap skill, and reference (gin-workflow-57fw)`.

## Integration
- **Branch**: `feat/roadmap-deadline-forecast` (worktree `.claude/worktrees/feat-roadmap-deadline-forecast`)
- **Merge strategy**: sequential

## Validation
- [ ] `python3 -m pytest -n auto` passes
- [ ] `gin milestone list` and `gin milestone list --json` on this repository exit 0, print `forecast:` and `"forecast"`, `schema` 1
- [ ] `gin milestone show gin-workflow-96sx` prints `lanes 1` and sequential dates
- [ ] `gin specs template roadmap.md` prints `- Deadline:`
- [ ] `wc -c plugins/gin-workflow/src/skills/roadmap/SKILL.md` under 12000
- [ ] Manual: write `- Deadline: 2026-12-31` into `.planning/roadmap.md` in the worktree, run `gin milestone list`, see the deadline comparison, then revert the file

## Notes
- `Model:` and `Effort:` come from the main harness catalog (`haiku`, `sonnet`, `opus`; `low`..`max`) by the route rubric.
- Parent bead `gin-workflow-57fw` stays open until the user confirms the merge; track beads close when their tests and review pass.
- Plan label for the parent: `export:milestone-forecast` (spec R9); the gin-console follow-up is a `gin-harness` epic, not a track here.
