# Plan: Shared gate state and forecast fidelity

Spec: .planning/specs/2026-11-10-milestone-gates-design.md
Epic: gin-workflow-milestone-gates
Workflow: gin-workflow-milestone-gates

## Objective

`gin milestone` treats a spec as confirmed when the epic bead's shared `gates` hold it, warns `spec_due` before a planned milestone starts, `gin state` sees `orchestration_ready` recorded on another machine, and the milestone schedule and forecast place in-progress epics by remaining work and unestimated epics by an assumed median, with the deadline shown by `show`.

**Goal** (spec): `gin milestone` readiness and `orchestration_ready` read gate state from the epic bead, so every member's machine shows the same answer, and the milestone forecast counts the remaining work of in-progress epics and places unestimated ones.

**Architecture**: no new module. Shared readiness is computed in `milestone_cli.py` from the bead rows it already loads, reusing `team_beads.gates_of`; `milestone.py` stays pure and gains `remaining_days`, assumed days, and `spec_due`; `lifecycle_cli._share_gate` writes one more gate through `team_beads.write_gate`, and `gin state` merges it like the other shared gates.

**Tech Stack**: Python 3 standard library (`math`, `statistics`), unittest/pytest, the fake `bd` of `tests/workflow_core` helpers.

**Global Constraints** (spec, verbatim):
- R9. JSON stays `schema: 1`: keys are only added. Existing keys keep their names, types, and meanings, except that the planned dates now reflect R5 and R6.
- gin-console reads `schema: 1` and ignores unknown keys (`gin-console/backend/src/gin_console/milestones/models.py`); the gate values it reads from `gin state` stay strings.
- Out of scope: the capacity model, member availability, exit criteria, integration date, and split warnings (`gin-workflow-milestone-capacity`); progress views (`gin-workflow-team-progress`); sharing `implementation_complete` or waivers; gin-console changes.

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
- Problem statement: readiness and `orchestration_ready` are local to the machine that recorded them; the forecast ignores progress and unestimated epics; `show` hides the deadline.
- Success criteria: spec R1 to R9 and US-1 to US-4 acceptance criteria, each covered by a test named in its track.
- Constraints: Global Constraints above.
- Non-goals: capacity model, availability, exit criteria (epic `gin-workflow-milestone-capacity`).

## Approach Options
### Option 1: extend the existing modules
- Summary: readiness union in `milestone_cli._confirmed`, pure scheduling helpers in `milestone.py`, one more `write_gate` call in `_share_gate`.
- Pros: small diff; follows current patterns; each part testable alone; no extra `bd` call.
- Cons: readiness logic lives in two places (`gin state` and `gin milestone`).

### Option 2: a shared `gate_state.py`
- Summary: one module that both `gin state` and `gin milestone` call.
- Pros: one source of truth.
- Cons: refactors the `gin state` path gin-console depends on; out of the confirmed scope.

### Recommended Approach
- Selected option: Option 1 (confirmed in `/discuss` on 2026-11-10).
- Rationale: smallest change that meets R1 to R9 without touching the `gin state` contract beyond one merged gate.

## Scope
- In scope: R1 to R9.
- Out of scope: see Global Constraints.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: One lane; Track 3 edits the same files as Track 1, and Track 2 is small enough to run between them.
```

## Tasks

`S` below is `plugins/gin-workflow/src/scripts/workflow_core`.

### Track 1: Shared spec readiness and the spec_due warning
- **Dependencies**: none
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/milestone_cli.py:128-138` (`_confirmed` takes the loaded beads), `:335-353` (`_run` passes them)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/milestone.py:155-190` (`schedule`: `spec_due`)
  - Test `tests/workflow_core/test_milestone.py`
  - Test `tests/workflow_core/test_milestone_cli.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** bounded change in two known functions with exact rules from the spec.
- **Interfaces**:
  - `milestone_cli._confirmed(root: Path, beads: Mapping[str, Mapping[str, Any]]) -> frozenset[str] | None`
  - `milestone.SPEC_DUE_DAYS = 5`
  - `schedule(...)` unchanged signature; adds warning `{"code": "spec_due"}`.
- **Steps**:
  1. Failing tests in `tests/workflow_core/test_milestone.py`, new class `SpecReadinessTests`:
     ```python
     class SpecReadinessTests(unittest.TestCase):
         def codes(self, result, epic_id):
             return [w["code"] for w in rows(result)[epic_id]["warnings"]]

         def test_spec_due_for_planned_milestone_starting_within_five_working_days(self):
             beads = world(milestone_bead(start="2026-11-04", end="2026-11-20"), bead("A", parent="m1", minutes=days(1)))
             result = milestone.schedule(beads["m1"], beads, D("2026-11-04"), TODAY, 1, frozenset())
             self.assertIn("spec_due", self.codes(result, "A"))
             self.assertNotIn("spec_not_ready", self.codes(result, "A"))

         def test_no_spec_due_when_the_planned_milestone_starts_later(self):
             beads = world(milestone_bead(start="2026-11-09", end="2026-11-20"), bead("A", parent="m1", minutes=days(1)))
             result = milestone.schedule(beads["m1"], beads, D("2026-11-09"), TODAY, 1, frozenset())
             self.assertNotIn("spec_due", self.codes(result, "A"))

         def test_no_spec_due_when_confirmed_or_closed(self):
             beads = world(milestone_bead(start="2026-11-02", end="2026-11-20"), bead("A", parent="m1", minutes=days(1)),
                           bead("B", parent="m1", minutes=days(1), status="closed"))
             result = milestone.schedule(beads["m1"], beads, D("2026-11-02"), TODAY, 1, frozenset({"A"}))
             self.assertNotIn("spec_due", self.codes(result, "A"))
             self.assertNotIn("spec_due", self.codes(result, "B"))

         def test_kicked_off_milestone_warns_spec_not_ready_never_spec_due(self):
             beads = world(milestone_bead(start="2026-11-02", end="2026-11-20", kickoff="2026-10-28"),
                           bead("A", parent="m1", minutes=days(1)))
             result = milestone.schedule(beads["m1"], beads, D("2026-11-02"), TODAY, 1, frozenset())
             self.assertEqual(["spec_not_ready"], [c for c in self.codes(result, "A") if c.startswith("spec_")])
     ```
     (`TODAY` is Thursday 2026-10-29; five working days with today included end Wednesday 2026-11-04.)
  2. Run `python3 -m pytest tests/workflow_core/test_milestone.py -k SpecReadiness -q` → fails (no `spec_due`).
  3. In `milestone.py` add `SPEC_DUE_DAYS = 5` under `WORKDAY_MINUTES`. In `schedule`, change the first line `_, end = period(milestone)` to `start_day, end = period(milestone)`, and after `kicked_off` add:
     ```python
     due = status(milestone, today) == "planned" and start_day <= _last_of(_workday(today), SPEC_DUE_DAYS)
     ```
     and replace the `spec_not_ready` block with:
     ```python
     if confirmed is not None and epic.get("status") != "closed" and epic_id not in confirmed:
         if kicked_off:
             warnings.append({"code": "spec_not_ready"})
         elif due:
             warnings.append({"code": "spec_due"})
     ```
  4. Run the step 2 command → passes; run `python3 -m pytest tests/workflow_core/test_milestone.py -q` → passes.
  5. Failing tests in `tests/workflow_core/test_milestone_cli.py` next to `test_spec_not_ready_after_kickoff_unless_confirmed`, using the class's existing `seed`, `bd`, `confirm_spec`, `events_path`, and `run_cli` helpers:
     ```python
     def test_shared_gate_confirms_the_spec(self):
         self.seed()
         self.bd("update", "t-a", "--set-metadata",
                 'gates={"requirement_confirmed": {"actor": "ba@corp.com", "at": "2026-10-20T00:00:00Z"}}')
         self.bd("update", "t-m1", "--set-metadata", "kickoff=2026-11-02")
         code, out, err = self.run_cli("show", "t-m1", "--json")
         self.assertEqual(0, code, err)
         rows = {row["id"]: row for row in json.loads(out)["epics"]}
         self.assertEqual((True, False), (rows["t-a"]["spec_confirmed"], rows["t-b"]["spec_confirmed"]))
         self.assertNotIn({"code": "spec_not_ready"}, rows["t-a"]["warnings"])

     def test_unreadable_log_still_uses_shared_gates(self):
         self.seed()
         self.bd("update", "t-a", "--set-metadata", 'gates={"requirement_confirmed": {"actor": "x", "at": "y"}}')
         self.events_path().write_text("{not json\n", encoding="utf-8")
         code, out, err = self.run_cli("show", "t-m1", "--json")
         self.assertIn("warning: event log unreadable:", err)
         rows = {row["id"]: row for row in json.loads(out)["epics"]}
         self.assertEqual((True, False), (rows["t-a"]["spec_confirmed"], rows["t-b"]["spec_confirmed"]))
     ```
     If the class's `bd` helper cannot set a JSON metadata value with `--set-metadata gates=...`, set it the way `seed` sets milestone metadata (`--metadata '{...}'` at create) and note the helper used in the commit message.
  6. Run `python3 -m pytest tests/workflow_core/test_milestone_cli.py -q` → the two new tests fail.
  7. In `milestone_cli.py` replace `_confirmed` with:
     ```python
     def _confirmed(root: Path, beads: Mapping[str, Mapping[str, Any]]) -> frozenset[str] | None:
         """Epic ids with a confirmed spec: `gates.requirement_confirmed` in the bead metadata, or a local
         `requirement.confirmed` event. None, with a stderr warning, when the log is unreadable and no bead has the gate."""
         from .events import EventPersistenceError, WorkflowEventStore
         from .team_beads import gates_of

         shared = {bead_id for bead_id, row in beads.items() if "requirement_confirmed" in gates_of(row)}
         path = main_checkout(root) / ".agent-workflow" / "runtime" / "events.jsonl"
         try:
             events = WorkflowEventStore(path).read_all()
         except (EventPersistenceError, OSError, ValueError) as error:
             print(f"warning: event log unreadable: {error}; spec readiness unknown", file=sys.stderr)
             return frozenset(shared) if shared else None
         return frozenset(shared | {event.workflow_id for event in events if event.event_type == "requirement.confirmed"})
     ```
     In `_run`, load beads once per command and pass them: `beads = _beads(root)` before `core.list_payload(beads, ...)` with `_confirmed(root, beads)`; in `show` pass `_confirmed(root, beads)`.
  8. Run `python3 -m pytest tests/workflow_core/test_milestone.py tests/workflow_core/test_milestone_cli.py -q` → passes.
  9. Commit: `feat(milestone): shared spec readiness and spec_due (gin-workflow-milestone-gates)`.
- **Acceptance criteria**: R1, R2; US-1 and US-2 acceptance criteria pass as the tests above; the existing `test_spec_not_ready_after_kickoff_unless_confirmed` and `test_unreadable_event_log_degrades_with_a_warning` still pass.
- **Estimated complexity**: low

### Track 2: Share orchestration_ready through the epic bead
- **Dependencies**: none
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/lifecycle_cli.py:200-225` (`_share_gate` writes the gate), `:425-428` (`gin state` merges it)
  - Modify `docs/concepts/state-model.md:34` (one sentence)
  - Test `tests/workflow_core/test_team_gates.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** two small edits on an existing path with fake-`bd` tests already in place.
- **Interfaces**: epic bead metadata `gates.orchestration_ready = {"actor": str, "at": str, "epic": str}`; `gin state` gate `orchestration_ready` stays a `satisfied`/`unmet` string.
- **Steps**:
  1. Failing tests in `tests/workflow_core/test_team_gates.py`, class that holds `test_orchestration_ready_seeds_the_epic_and_labels_it`:
     ```python
     def test_orchestration_ready_writes_its_own_gate(self):
         self.bd({"e-2": {"id": "e-2", "issue_type": "epic", "status": "open", "metadata": {}}})
         ready = run_cli(self.root, "record", "orchestration-ready", "--evidence", "w", "--workflow-id", "w",
                         "--epic", "e-2", env=self.env)
         self.assertEqual(0, ready.returncode, ready.stderr)
         writes = [json.loads(u[4].removeprefix("gates=")) for u in self.bd_updates()
                   if u[2] == "e-2" and u[3] == "--set-metadata"]
         gate = writes[-1]["orchestration_ready"]
         self.assertEqual("e-2", gate["epic"])
         self.assertRegex(gate["at"], r"^\d{4}-\d{2}-\d{2}T")
         self.assertTrue(gate["actor"])

     def test_state_reads_orchestration_ready_from_the_epic_bead(self):
         gate = {"actor": "binh@corp.com", "at": "2026-11-01T00:00:00Z", "epic": "e-1"}
         self.bd({"e-1": {"id": "e-1", "issue_type": "epic", "status": "open",
                          "metadata": {"gates": json.dumps({"orchestration_ready": gate})}}})
         state = json.loads(run_cli(self.root, "state", "--workflow-id", "e-1", "--format", "json", env=self.env).stdout)
         self.assertEqual("satisfied", state["gates"]["orchestration_ready"])
     ```
     `test_solo_mode_never_writes_gates` already covers "outside team mode nothing is written"; add to it a `record orchestration-ready --epic e-9` call before the `state` call and keep its `self.assertEqual([], self.bd_updates())` assertion after it.
  2. Run `python3 -m pytest tests/workflow_core/test_team_gates.py -q -k "orchestration_ready or solo_mode"` → the two new tests fail.
  3. In `_share_gate`, inside `if args.gate == "orchestration-ready":`, after the `for prior in ...` loop and before labelling, add:
     ```python
     write_gate(repo_path, epic, "orchestration_ready", {"actor": actor, "at": utc_now(), "epic": epic}, actor=actor)
     ```
     In the `gin state` merge, change `for gate in ("requirement_confirmed", "plan_approved"):` to `for gate in ("requirement_confirmed", "plan_approved", "orchestration_ready"):`.
  4. Run the step 2 command → passes; run `python3 -m pytest tests/workflow_core/test_team_gates.py tests/workflow_core/test_lifecycle_cli.py -q` → passes.
  5. In `docs/concepts/state-model.md:34` change "`record orchestration-ready --epic` copies the proofs recorded before that epic existed and adds that label." to "`record orchestration-ready --epic` copies the proofs recorded before that epic existed, writes its own `orchestration_ready` entry (`actor`, `at`, `epic`), and adds that label." and change "treats `requirement_confirmed` and `plan_approved` as satisfied" to "treats `requirement_confirmed`, `plan_approved`, and `orchestration_ready` as satisfied". Run `gin docs check docs/concepts/state-model.md` → no findings.
  6. Commit: `feat(state): share orchestration_ready through the epic bead (gin-workflow-milestone-gates)`.
- **Acceptance criteria**: R3, R4, R8 (state-model part); US-3 acceptance criteria pass; existing tests in both files pass.
- **Estimated complexity**: low

### Track 3: Remaining work, assumed days, and the deadline in show
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/milestone.py:124-203` (`_place`, `schedule`, `show_payload`), `:212-255` (`forecast`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/milestone_cli.py:183-194` (`_show_text`), `:343-350` (`_run` passes the deadline)
  - Modify `docs/reference/cli.md:213-230` (new paragraph after the `list`/`show` paragraph)
  - Test `tests/workflow_core/test_milestone.py`
  - Test `tests/workflow_core/test_milestone_cli.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `high`
- **Why:** one module, but scheduling logic with several edge cases (tracks or not, weekends, closed and unestimated epics, dependency placement) and exact-payload tests to update.
- **Interfaces**:
  - `milestone.remaining_days(epic: Mapping[str, Any], beads: Beads, today: date) -> int | None`
  - `milestone._planned_days(epics: Mapping[str, Mapping[str, Any]], beads: Beads, today: date) -> dict[str, int | None]`
  - `milestone._place(epics, first, lanes, days: Mapping[str, int | None])`
  - `milestone.show_payload(..., deadline: date | None = None)` adds key `deadline`
  - epic rows add `remaining_days: int | None` and `assumed_days: int | None`
- **Steps**:
  1. Failing tests in `tests/workflow_core/test_milestone.py`, new class `PlannedDaysTests` (extend the `bead` helper with `started_at=None` that sets `"started_at"` when given):
     ```python
     class PlannedDaysTests(unittest.TestCase):
         def test_in_progress_with_tracks_uses_the_open_share(self):
             beads = world(milestone_bead(), bead("A", parent="m1", minutes=days(4), status="in_progress"),
                           *[bead(f"A.{n}", type="task", parent="A", status="closed" if n == 1 else "open") for n in (1, 2, 3, 4)])
             row = rows(plan(beads))["A"]
             self.assertEqual((3, 4), (row["remaining_days"], row["estimate_days"]))
             self.assertEqual(("2026-11-02", "2026-11-04"), span(row))

         def test_in_progress_without_tracks_subtracts_elapsed_working_days(self):
             beads = world(milestone_bead(), bead("A", parent="m1", minutes=days(3), status="in_progress",
                                                  started_at="2026-10-27T09:00:00Z"))
             self.assertEqual(1, rows(plan(beads))["A"]["remaining_days"])  # Tue 27 and Wed 28 elapsed

         def test_open_epic_keeps_its_estimate(self):
             beads = world(milestone_bead(), bead("A", parent="m1", minutes=days(2)))
             self.assertEqual(2, rows(plan(beads))["A"]["remaining_days"])

         def test_unestimated_epic_takes_the_median(self):
             beads = world(milestone_bead(), bead("A", parent="m1", minutes=days(1)), bead("B", parent="m1", minutes=days(2)),
                           bead("C", parent="m1", minutes=days(4)), bead("U", parent="m1"))
             row = rows(plan(beads))["U"]
             self.assertEqual((None, 2, None), (row["estimate_days"], row["assumed_days"], row["remaining_days"]))
             self.assertIn({"code": "unestimated"}, row["warnings"])
             self.assertEqual("2026-11-12", plan(beads)["finish"])  # 1+2+4+2 = 9 working days from Mon 2 Nov

         def test_all_unestimated_assume_one_day(self):
             beads = world(milestone_bead(), bead("U", parent="m1"))
             self.assertEqual(1, rows(plan(beads))["U"]["assumed_days"])

         def test_forecast_finish_counts_unestimated_epics(self):
             beads = world(bead("r1", labels=["roadmap"], minutes=days(2)), bead("r2", labels=["roadmap"]))
             found = milestone.forecast(beads, TODAY, milestone.Roadmap(), 1)
             self.assertEqual(("2026-11-03", 1), (found["finish"], found["unestimated"]))  # Thu 29 .. Tue 3: 2 + 2 days
     ```
  2. Run `python3 -m pytest tests/workflow_core/test_milestone.py -k PlannedDays -q` → fails.
  3. In `milestone.py` (add `import statistics`), add after `workdays_after`:
     ```python
     def _workdays_before(begin: date, end: date) -> int:
         """Working days from `begin` up to, not including, `end`."""
         count, day = 0, begin
         while day < end:
             count += day.weekday() < 5
             day += timedelta(days=1)
         return count


     def remaining_days(epic: Mapping[str, Any], beads: Beads, today: date) -> int | None:
         """Days left: the estimate for a not-started epic; for an in-progress one, the share of open child tracks,
         else the estimate minus the working days since `started_at`. At least 1; None when unestimated."""
         days = estimate_days(epic.get("estimated_minutes"))
         if days is None or epic.get("status") != "in_progress":
             return days
         tracks = [bead for bead in beads.values() if bead.get("parent") == epic["id"] and bead.get("issue_type") != "epic"]
         if tracks:
             still_open = sum(track.get("status") != "closed" for track in tracks)
             return max(1, math.ceil(days * still_open / len(tracks)))
         try:
             begun = parse_date(str(epic.get("started_at") or "")[:10])
         except ValueError:
             return days
         return max(1, days - _workdays_before(begun, today))


     def _planned_days(epics: Mapping[str, Mapping[str, Any]], beads: Beads, today: date) -> dict[str, int | None]:
         """Days each epic takes in the schedule: remaining days, else for an open unestimated epic the median
         estimate of the group rounded up (1 when none is estimated); a closed unestimated epic takes none."""
         known = [d for epic in epics.values() if (d := estimate_days(epic.get("estimated_minutes"))) is not None]
         assumed = math.ceil(statistics.median(known)) if known else 1
         planned: dict[str, int | None] = {}
         for epic_id, epic in epics.items():
             days = remaining_days(epic, beads, today)
             planned[epic_id] = assumed if days is None and epic.get("status") != "closed" else days
         return planned
     ```
     Change `_place(epics, first, lanes)` to `_place(epics, first, lanes, days)`: use `days[dep] is not None` for `estimated` and `days[epic_id]` for the placed length; update its docstring to "Epics whose days are None take no lane and no days."
     In `schedule`: `days_of = _planned_days(epics, beads, today)`; `planned = _place(epics, _workday(start), lanes_of(milestone, default_lanes), days_of)`; per row keep `days = estimate_days(...)` for `estimate_days` and the `unestimated` warning, and add `"remaining_days": remaining_days(epic, beads, today)` and `"assumed_days": days_of[epic_id] if days is None else None` after `"estimate_days"`.
     In `forecast`: `planned = _place(group, _workday(first), lanes, days_of := _planned_days(group, beads, today))` and `group_ends = [planned[k][1] for k in group if days_of[k] is not None]`.
  4. Run step 2 → passes. Run `python3 -m pytest tests/workflow_core/test_milestone.py -q`; update the existing tests whose expectation R6 changes, and only those: `test_req_007_unestimated_dependency`, `test_req_008_unestimated`, `test_unestimated_epic_takes_no_lane`, and any `ForecastTests` case with an unestimated open epic. Each now expects the unestimated open epic to take the assumed days; rename `test_unestimated_epic_takes_no_lane` to `test_unestimated_epic_takes_the_assumed_days`. Keep a test that a closed unestimated epic takes no lane. Run again → passes.
  5. Failing tests in `tests/workflow_core/test_milestone_cli.py`: in `test_req_011_show_exact_payload` add `"deadline": None` to the top level and `"remaining_days": 3, "assumed_days": None` / `"remaining_days": 2, "assumed_days": None` to the two rows; add:
     ```python
     def test_show_prints_the_roadmap_deadline(self):
         self.seed()
         roadmap = self.root / ".planning/roadmap.md"
         roadmap.parent.mkdir(parents=True, exist_ok=True)
         roadmap.write_text("# Roadmap: x\n\n## Constraints\n\n- Deadline: 2026-11-13\n", encoding="utf-8")
         code, out, err = self.run_cli("show", "t-m1", "--json")
         self.assertEqual("2026-11-13", json.loads(out)["deadline"])
         code, out, err = self.run_cli("show", "t-m1")
         self.assertIn("deadline: 2026-11-13", out)
     ```
     (if the class's root uses the SDD layout, write the file at `docs/roadmap.md` instead, matching `_roadmap`.)
  6. Run `python3 -m pytest tests/workflow_core/test_milestone_cli.py -q` → fails.
  7. `show_payload(..., confirmed=None, deadline: date | None = None)` adds `"deadline": deadline.isoformat() if deadline else None` after `"lanes"`. In `_run`'s `show` branch: `roadmap = _roadmap(root, config)` and pass `_default_lanes(config, roadmap)`, `_confirmed(root, beads)`, `roadmap.deadline`. In `_show_text`, after the header line: `if payload.get("deadline"): lines.append(f"deadline: {payload['deadline']}")`; in each epic line use `row['estimate_days']` when set, else `f"{row['assumed_days']}d?"` for an assumed length (keep `-` when both are None).
  8. Run `python3 -m pytest tests/workflow_core/test_milestone.py tests/workflow_core/test_milestone_cli.py -q` → passes.
  9. Docs: in `docs/reference/cli.md`, after the paragraph that starts "Dated milestones over roadmap epics", add:
     ```markdown
     Each epic row of `show` carries `estimate_days`, `remaining_days`, and `assumed_days`. An in-progress epic is placed for its remaining days: the estimate times the share of its open child tracks, rounded up, or without tracks the estimate minus the working days since it started; at least 1. An open epic without an estimate is placed for the median estimate of its group, rounded up, or 1 day, shown in `assumed_days` with the `unestimated` warning. `late` means an open epic of an active milestone whose planned end is before today. `spec_due` marks an open epic without a confirmed spec in a planned milestone that starts within 5 working days, today included; `spec_not_ready` replaces it once the milestone is kicked off. A spec counts as confirmed when the epic bead's `gates` metadata holds `requirement_confirmed` or the local event log has the event. `show` also reports `deadline` from the roadmap's `Deadline:` line.
     ```
     Run `gin docs check docs/reference/cli.md` → no findings (split a sentence over 35 words if reported).
  10. Run `python3 -m pytest -n auto -q` → passes.
  11. Commit: `feat(milestone): remaining work, assumed days, deadline in show (gin-workflow-milestone-gates)`.
- **Acceptance criteria**: R5, R6, R7, R8 (cli.md part), R9; US-4 acceptance criteria pass as the tests above; JSON keys are only added.
- **Estimated complexity**: medium

## Integration
- **Branch**: `feat/milestone-gates`
- **Merge strategy**: sequential

## Validation
- [ ] `python3 -m pytest -n auto -q` passes (pre-push runs it).
- [ ] `gin docs check docs/reference/cli.md docs/concepts/state-model.md` reports no findings.
- [ ] `gin milestone list --json` and `gin milestone show <id> --json` keep `schema: 1` and every existing key.
- [ ] Manual: after `install.sh`, `gin milestone list` on this repository prints a forecast that counts every open roadmap epic.

## Notes
- `Model:` and `Effort:` are chosen from the main harness catalog using the route rubric.
- Omit `Effort:` when the catalog lists no efforts.
- Unclear requirements never raise the model or effort; ask the user or return to `discuss`.
- The user may override `Model:` and `Effort:` before plan approval.
- Provider roles describe responsibility rather than filename patterns.
- Deliverable merge-holds (e.g. "remain open until human-confirmed merge") apply exclusively to the Parent Bead. Individual track beads must close upon passing tests and code review to unblock downstream dependent tracks.
- Exact-payload CLI tests change in the same track as the payload (`.planning/knowledge/milestone-lanes-and-forecast.md`).
- `feat/milestone-gates` carries the roadmap commits of `roadmap/process-review`; they merge to master with this epic.
