# Plan: Milestone capacity model, exit criteria, and split warnings

Spec: .planning/specs/2026-11-10-milestone-capacity-design.md
Epic: gin-workflow-milestone-capacity
Workflow: gin-workflow-milestone-capacity

## Objective

Default lanes count building members; `--away` days off move the schedule on that member's lane; a milestone stores an integration date; `show` and `list` warn `after_integration`, `open_bugs`, and `oversized`; the roadmap skill acts on `oversized` and counts QA in Load.

**Goal** (spec): the roadmap bound and the `gin milestone` schedule use one capacity model: default lanes count only members who build, member days off reduce their lane, and QA counts in the Load bound. A milestone stores an integration date and warns when an epic will miss it or still has open bugs. An epic larger than its milestone is flagged.

**Architecture**: extend `milestone.py` (pure scheduling: lane days off in `_place`, new warnings, payload keys) and `milestone_cli.py` (building members, `update --away/--integration`, metadata warnings), following the pattern of `gin-workflow-milestone-gates`. Skill and docs text changes ride in the track that ships the behaviour they describe.

**Tech Stack**: Python 3 standard library, unittest/pytest, real `bd` in `MilestoneCliTests`/`MilestoneTeamTests` (skipped without `bd`).

**Global Constraints** (spec, verbatim):
- R9. JSON stays `schema: 1`; keys are only added.
- R8. `SKILL.md` stays within 12,000 characters.
- Out of scope: shared gate state and forecast fidelity; gin-qa case results as exit criteria (`gin-workflow-qa-lifecycle`); progress views (`gin-workflow-team-progress`); per-member AI quota; gin-console changes.
- Malformed `away` or `integration` metadata written outside the CLI is ignored for scheduling and warnings, with one stderr warning naming the milestone; the command exits 0.

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
- Problem statement: lanes default to every member; days off, integration date, and exit warnings have no home; oversized epics surface late.
- Success criteria: spec R1 to R9 and US-1 to US-4, each covered by a test named below.
- Constraints: Global Constraints above.
- Non-goals: see Global Constraints.

## Approach Options
### Option 1: extend milestone.py and milestone_cli.py
- Summary: per-lane days off as an optional argument of `_place`; warnings in `schedule`; CLI writes metadata through `bd update`.
- Pros: one place for scheduling; follows the shipped pattern; no schema change outside milestone metadata.
- Cons: `schedule` grows two optional parameters.

### Option 2: a `capacity.py` module
- Summary: lanes, days off, and Load in a new module.
- Pros: separate concern.
- Cons: no second user yet (YAGNI); confirmed against in `/discuss`.

### Recommended Approach
- Selected option: Option 1 (confirmed in `/discuss` on 2026-11-10).
- Rationale: smallest diff that meets R1 to R9.

## Scope
- In scope: R1 to R9.
- Out of scope: see Global Constraints.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Both tracks edit milestone.py, milestone_cli.py, and their tests; one lane.
```

## Tasks

`S` is `plugins/gin-workflow/src/scripts/workflow_core`. `TODAY` in `test_milestone.py` is Thursday 2026-10-29; `MilestoneCliTests.today` is the same date.

### Track 1: Building-member lanes and days off
- **Dependencies**: none
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/milestone.py:66-80` (day helpers), `:166-196` (`_place`), `:198-256` (`schedule`, `show_payload`), `:311-` (`list_payload`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/milestone_cli.py:32-68` (parser), `:141-148` (`_default_lanes`, new `_builders`), `/^def _update/` (`--away`), `/^def _run/` (pass builders)
  - Modify `docs/reference/cli.md:200-232` (`gin milestone` usage block, `update` row, one paragraph)
  - Test `tests/workflow_core/test_milestone.py`
  - Test `tests/workflow_core/test_milestone_cli.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `high`
- **Why:** scheduling with per-lane non-working days touches the greedy placer and its edge cases (weekends, lanes capped by epic count, anonymous lanes), plus a validated CLI write.
- **Interfaces**:
  - `milestone.is_building_role(role: str) -> bool`
  - `milestone.away_of(milestone: Mapping[str, Any]) -> dict[str, list[str]] | None` (None when the metadata is malformed; `{}` when absent)
  - `milestone._place(epics, first, lanes, days, off: Sequence[frozenset[date]] | None = None)`
  - `schedule(..., confirmed=None, builders: Sequence[str] = ())`, `show_payload(..., deadline=None, builders=())`, `list_payload(..., confirmed=None, builders=())`
  - `show` JSON adds `away`; milestone metadata `away` = JSON object `{member_email: ["YYYY-MM-DD..YYYY-MM-DD", ...]}`
  - `milestone_cli._builders(config) -> tuple[str, ...]` (member emails in `team.members` order with a building role)
- **Steps**:
  1. Failing tests in `tests/workflow_core/test_milestone.py`, new class `CapacityTests` placed above the `if __name__ == "__main__":` guard:
     ```python
     class CapacityTests(unittest.TestCase):
         def test_building_roles(self):
             self.assertEqual([True, True, True, True, True, False, False, False, False],
                              [milestone.is_building_role(r) for r in
                               ("dev", "be_dev", "fe_lead", "be_lead", "mobile_dev", "pm", "ba", "qe", "devops")])

         def test_away_skips_days_on_the_builders_lane(self):
             beads = world(milestone_bead(away='{"an@x.io": ["2026-11-03..2026-11-04"]}'),
                           bead("A", parent="m1", minutes=days(3)))
             result = milestone.schedule(beads["m1"], beads, D("2026-11-02"), TODAY, 1, None, ("an@x.io",))
             self.assertEqual(("2026-11-02", "2026-11-06"), span(rows(result)["A"]))  # Mon, then Thu, Fri

         def test_away_is_ignored_with_lanes_metadata(self):
             beads = world(milestone_bead(lanes="1", away='{"an@x.io": ["2026-11-03..2026-11-04"]}'),
                           bead("A", parent="m1", minutes=days(3)))
             result = milestone.schedule(beads["m1"], beads, D("2026-11-02"), TODAY, 1, None, ("an@x.io",))
             self.assertEqual(("2026-11-02", "2026-11-04"), span(rows(result)["A"]))

         def test_away_without_builders_is_ignored(self):
             beads = world(milestone_bead(away='{"an@x.io": ["2026-11-03"]}'), bead("A", parent="m1", minutes=days(2)))
             self.assertEqual(("2026-11-02", "2026-11-03"), span(rows(plan(beads))["A"]))

         def test_second_lane_belongs_to_the_second_builder(self):
             beads = world(milestone_bead(away='{"b@x.io": ["2026-11-02..2026-11-03"]}'),
                           bead("A", parent="m1", minutes=days(2)), bead("B", parent="m1", minutes=days(2)))
             result = milestone.schedule(beads["m1"], beads, D("2026-11-02"), TODAY, 2, None, ("a@x.io", "b@x.io"))
             self.assertEqual(("2026-11-02", "2026-11-03"), span(rows(result)["A"]))
             self.assertEqual(("2026-11-04", "2026-11-05"), span(rows(result)["B"]))

         def test_away_of_reads_json_and_rejects_garbage(self):
             self.assertEqual({}, milestone.away_of(milestone_bead()))
             self.assertEqual({"a@x.io": ["2026-11-03"]}, milestone.away_of(milestone_bead(away='{"a@x.io": ["2026-11-03"]}')))
             self.assertIsNone(milestone.away_of(milestone_bead(away="not json")))
             self.assertIsNone(milestone.away_of(milestone_bead(away='{"a@x.io": ["2026-13-40"]}')))

         def test_show_payload_lists_away(self):
             beads = world(milestone_bead(away='{"a@x.io": ["2026-11-03"]}'))
             payload = milestone.show_payload(beads["m1"], beads, None, TODAY)
             self.assertEqual({"a@x.io": ["2026-11-03"]}, payload["away"])
     ```
  2. Run `python3 -m pytest tests/workflow_core/test_milestone.py -k CapacityTests -q` → fails.
  3. In `milestone.py` (add `import json` and `from typing import Sequence` to the existing typing import):
     ```python
     _BUILDING = re.compile(r"dev|be_.+|fe_.+|.+_dev|.+_lead")


     def is_building_role(role: str) -> bool:
         return bool(_BUILDING.fullmatch(str(role)))


     def _ranges(spec: Any) -> frozenset[date]:
         """Dates of `["D", "D..D", ...]`; raises ValueError on a malformed entry or a reversed range."""
         if not isinstance(spec, list):
             raise ValueError("away ranges must be a list")
         found: set[date] = set()
         for item in spec:
             first, _, last = str(item).partition("..")
             begin, end = parse_date(first), parse_date(last or first)
             if begin > end:
                 raise ValueError(f"reversed range: {item}")
             found.update(begin + timedelta(days=n) for n in range((end - begin).days + 1))
         return frozenset(found)


     def away_of(milestone: Mapping[str, Any]) -> dict[str, list[str]] | None:
         """The milestone's `away` metadata as {member: [range, ...]}; {} when absent, None when malformed."""
         value = _meta(milestone).get("away")
         if value in (None, ""):
             return {}
         try:
             value = json.loads(value) if isinstance(value, str) else value
             if not isinstance(value, Mapping):
                 raise ValueError("away must be an object")
             for spec in value.values():
                 _ranges(spec)
         except ValueError:  # json.JSONDecodeError is a ValueError
             return None
         return {str(member): [str(item) for item in spec] for member, spec in value.items()}


     def _off(day: date, off: frozenset[date]) -> date:
         """The first working day on or after `day` that is not in `off`."""
         while day.weekday() >= 5 or day in off:
             day += timedelta(days=1)
         return day


     def _lane_off(milestone: Mapping[str, Any], builders: Sequence[str]) -> list[frozenset[date]] | None:
         """Days off per lane when lanes come from building members: lane n is builders[n]."""
         away = away_of(milestone)
         if not builders or str(_meta(milestone).get("lanes", "")) or not away:
             return None
         return [_ranges(away.get(member, [])) for member in builders]
     ```
     In `_place`, add the parameter `off: Sequence[frozenset[date]] | None = None` and replace the lane placement lines with:
     ```python
     lane = min(range(len(free)), key=lambda index: free[index])
     lane_off = off[lane] if off and lane < len(off) else frozenset()
     begin = _off(max(ready[epic_id], free[lane]), lane_off)
     end = begin
     for _ in range(length - 1):
         end = _off(end + timedelta(days=1), lane_off)
     planned[epic_id] = (begin, end)
     free[lane] = _off(end + timedelta(days=1), lane_off)
     ```
     In `schedule`, add the parameter `builders: Sequence[str] = ()` and pass `_lane_off(milestone, builders)` as `off` to `_place`. In `show_payload`, add `builders: Sequence[str] = ()`, pass it to `schedule`, and add `"away": away_of(milestone) or {}` after `"lanes"`. In `list_payload`, add `builders: Sequence[str] = ()` and pass it to `schedule`.
  4. Run step 2 → passes; run `python3 -m pytest tests/workflow_core/test_milestone.py -q` → passes. Update exact-payload expectations of `show_payload` (`test_req_011_show_payload_shape`) by adding `"away": {}`.
  5. Failing tests in `tests/workflow_core/test_milestone_cli.py`:
     - In `test_default_lanes_chain`, add a `pm@x.io: {roles: [pm]}` member to `team` and keep `2` as the expected default; add `self.assertEqual(("a@x.io", "b@x.io"), milestone_cli._builders(team))`.
     - In `test_req_011_show_exact_payload`, add `"away": {}` to the expected top level.
     - In `MilestoneTeamTests` (members from `team_fixtures.TEAM`; `an@corp.com` holds `ba`, which `TEAM_TEXT` permits to write milestones):
     ```python
     def test_away_writes_validates_and_removes(self):
         root = self.repo("ba", "an@corp.com")
         code, err = self.run_cli(root, "update", "t-m1", "--away", "binh@corp.com:2026-11-03..2026-11-04",
                                  "--away", "chi@corp.com:2026-11-02")
         self.assertEqual(0, code, err)
         away = json.loads(self.metadata(root, "t-m1")["away"])
         self.assertEqual({"binh@corp.com": ["2026-11-03..2026-11-04"], "chi@corp.com": ["2026-11-02..2026-11-02"]}, away)
         for bad in ("nobody@corp.com:2026-11-03", "binh@corp.com:2026-11-05..2026-11-03", "binh@corp.com:soon"):
             code, err = self.run_cli(root, "update", "t-m1", "--away", bad)
             self.assertEqual(1, code, bad)
         self.assertEqual(away, json.loads(self.metadata(root, "t-m1")["away"]))
         self.assertEqual(0, self.run_cli(root, "update", "t-m1", "--away", "chi@corp.com:none")[0])
         self.assertEqual({"binh@corp.com": ["2026-11-03..2026-11-04"]}, json.loads(self.metadata(root, "t-m1")["away"]))
     ```
     If `bd show --json` returns `away` already parsed, compare without `json.loads` (use `value if isinstance(value, dict) else json.loads(value)`).
  6. Run `python3 -m pytest tests/workflow_core/test_milestone_cli.py -q` → fails.
  7. In `milestone_cli.py`:
     ```python
     def _builders(config: Mapping[str, Any]) -> tuple[str, ...]:
         """Member emails, in `team.members` order, that hold a building role."""
         from . import team as team_core

         team = team_core.load_team(config)
         if team is None:
             return ()
         return tuple(email for email, member in team.members.items() if any(map(core.is_building_role, member.roles)))


     def _default_lanes(config: Mapping[str, Any], roadmap: core.Roadmap) -> int:
         """Roadmap `AI capacity:` number, else the building-member count, else 1."""
         return roadmap.lanes or len(_builders(config)) or 1
     ```
     Parser: on `update` add `item.add_argument("--away", action="append", default=[])`. Add:
     ```python
     def _away_change(config: Mapping[str, Any], current: Mapping[str, list[str]], values: Sequence[str]) -> dict[str, list[str]]:
         from . import team as team_core

         team = team_core.load_team(config)
         members = set(team.members) if team is not None else set()
         away = {member: list(spec) for member, spec in current.items()}
         for value in values:
             member, _, spec = value.partition(":")
             member = member.strip().lower()
             if member not in members:
                 raise MilestoneError(f"--away: {member or value} is not in team.members")
             if spec == "none":
                 away.pop(member, None)
                 continue
             first, _, last = spec.partition("..")
             begin, end = _date(first), _date(last or first)
             if begin > end:
                 raise MilestoneError(f"--away: {spec} ends before it starts")
             away.setdefault(member, []).append(f"{begin.isoformat()}..{end.isoformat()}")
         return away
     ```
     `_update` takes `config` (change the `WRITES` call site in `_write` to pass it, or read it with `_config(root)` inside `_update`; use whichever keeps the `WRITES` signature uniform: read `_config(root)` inside `_update`). Compute the change before any `bd` call so a refusal writes nothing:
     ```python
     if args.away:
         current = core.away_of(milestone) or {}
         away = _away_change(_config(root), current, args.away)
         argv += ["--set-metadata", f"away={json.dumps(away, sort_keys=True)}"] if away else ["--unset-metadata", "away"]
     ```
     (`milestone = _open(beads, args.id)`, reused for `core.period`.) In `_run`, compute `builders = () if roadmap.lanes else _builders(config)` and pass `builders=builders` to `core.list_payload` and `core.show_payload`.
  8. Run `python3 -m pytest tests/workflow_core/test_milestone.py tests/workflow_core/test_milestone_cli.py -q` → passes.
  9. Docs in `docs/reference/cli.md`: in the usage block change the `update` line to `gin milestone update ID [--title TITLE] [--start YYYY-MM-DD] [--end YYYY-MM-DD] [--lanes N] [--away MEMBER:FROM[..TO]|MEMBER:none]...`; in the `update` table row append "; `--away` records a member's days off (repeatable), `MEMBER:none` removes them"; and in the paragraph that explains a milestone's lanes, replace "else the number of `team.members`" with "else the number of `team.members` holding a building role (`dev`, `be_*`, `fe_*`, `*_dev`, `*_lead`)", then add: "When the lanes come from those members, lane n belongs to the n-th of them and the schedule skips their `away` days on that lane; lanes from `--lanes` or `AI capacity:` ignore `away`. `show` lists `away`." Run `gin docs check docs/reference/cli.md` → ok.
  10. Commit: `feat(milestone): building-member lanes and days off (gin-workflow-milestone-capacity)`.
- **Acceptance criteria**: R1, R2, R3, R9 (Track 1 part); US-1, US-2 pass as the tests above; existing milestone tests pass.
- **Estimated complexity**: medium

### Track 2: Integration date, exit warnings, oversized, and the roadmap skill
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/milestone.py` (`schedule` warnings, `show_payload` key, `metadata_problems`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/milestone_cli.py` (parser `--integration`, `_update`, `_show_text`, `_run` warnings)
  - Modify `plugins/gin-workflow/src/skills/roadmap/SKILL.md:17-18`
  - Modify `plugins/gin-workflow/src/skills/roadmap/references/way-of-working.md:21`
  - Modify `docs/reference/cli.md` (`gin milestone` section)
  - Test `tests/workflow_core/test_milestone.py`
  - Test `tests/workflow_core/test_milestone_cli.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** three independent warnings and one metadata key on the placer from Track 1, with exact rules; skill text edits under a character limit.
- **Interfaces**:
  - milestone metadata `integration` = `YYYY-MM-DD`; `show` JSON adds `integration` (date or null)
  - warnings `{"code": "after_integration"}`, `{"code": "open_bugs", "count": int}`, `{"code": "oversized", "days": int}`
  - `milestone.metadata_problems(milestone) -> list[str]` (names of malformed keys among `away`, `integration`)
- **Steps**:
  1. Failing tests in `tests/workflow_core/test_milestone.py`, new class `ExitWarningTests` above the `__main__` guard (extend the `bead` helper to accept `deps=()` of `(type, id)` pairs appended to `dependencies`, keeping `blocks` as is):
     ```python
     class ExitWarningTests(unittest.TestCase):
         def codes(self, beads, epic_id="A"):
             return rows(plan(beads))[epic_id]["warnings"]

         def test_after_integration(self):
             beads = world(milestone_bead(integration="2026-11-03"), bead("A", parent="m1", minutes=days(3)))
             self.assertIn({"code": "after_integration"}, self.codes(beads))
             beads = world(milestone_bead(integration="2026-11-04"), bead("A", parent="m1", minutes=days(3)))
             self.assertNotIn({"code": "after_integration"}, self.codes(beads))

         def test_open_bugs_counts_open_discovered_bugs(self):
             beads = world(milestone_bead(), bead("A", parent="m1", minutes=days(1)),
                           bead("b1", type="bug", deps=[("discovered-from", "A")]),
                           bead("b2", type="bug", deps=[("discovered-from", "A")]),
                           bead("b3", type="bug", status="closed", deps=[("discovered-from", "A")]))
             self.assertIn({"code": "open_bugs", "count": 2}, self.codes(beads))

         def test_oversized(self):
             beads = world(milestone_bead(start="2026-11-02", end="2026-11-06"), bead("A", parent="m1", minutes=days(7)))
             self.assertIn({"code": "oversized", "days": 2}, self.codes(beads))
             beads = world(milestone_bead(start="2026-11-02", end="2026-11-06"), bead("A", parent="m1", minutes=days(5)))
             self.assertNotIn("oversized", [w["code"] for w in self.codes(beads)])

         def test_malformed_integration_is_ignored_and_reported(self):
             beads = world(milestone_bead(integration="soon"), bead("A", parent="m1", minutes=days(3)))
             self.assertNotIn({"code": "after_integration"}, self.codes(beads))
             self.assertEqual(["integration"], milestone.metadata_problems(beads["m1"]))
             self.assertIsNone(milestone.show_payload(beads["m1"], beads, None, TODAY)["integration"])
     ```
  2. Run `python3 -m pytest tests/workflow_core/test_milestone.py -k ExitWarning -q` → fails.
  3. In `milestone.py`:
     ```python
     def _integration(milestone: Mapping[str, Any]) -> date | None:
         try:
             value = _meta(milestone).get("integration")
             return parse_date(value) if value else None
         except ValueError:
             return None


     def metadata_problems(milestone: Mapping[str, Any]) -> list[str]:
         meta = _meta(milestone)
         problems = []
         if meta.get("away") not in (None, "") and away_of(milestone) is None:
             problems.append("away")
         if meta.get("integration") and _integration(milestone) is None:
             problems.append("integration")
         return problems


     def _open_bugs(beads: Beads) -> dict[str, int]:
         counts: dict[str, int] = {}
         for bead in beads.values():
             if bead.get("issue_type") != "bug" or bead.get("status") == "closed":
                 continue
             for dep in bead.get("dependencies") or []:
                 if dep.get("type") == "discovered-from":
                     counts[str(dep.get("depends_on_id"))] = counts.get(str(dep.get("depends_on_id")), 0) + 1
         return counts
     ```
     In `schedule`, before the row loop: `integration = _integration(milestone)`, `bugs = _open_bugs(beads)`, `span_days = _workdays_before(start_day, end + timedelta(days=1))`. In the loop, after the existing warnings, with `still_open = epic.get("status") != "closed"`:
     ```python
     if integration and still_open and finish > integration:
         warnings.append({"code": "after_integration"})
     if bugs.get(epic_id):
         warnings.append({"code": "open_bugs", "count": bugs[epic_id]})
     if still_open and days_of[epic_id] is not None and days_of[epic_id] > span_days:
         warnings.append({"code": "oversized", "days": days_of[epic_id] - span_days})
     ```
     In `show_payload` add `"integration": i.isoformat() if (i := _integration(milestone)) else None` after `"away"`.
  4. Run step 2 → passes; update `test_req_011_show_payload_shape` with `"integration": None`; run `python3 -m pytest tests/workflow_core/test_milestone.py -q` → passes. If an existing test's milestone is shorter than one of its estimated epics, its warnings now include `oversized`; update that expectation and name the test in the commit message.
  5. Failing CLI tests in `tests/workflow_core/test_milestone_cli.py`: in `test_req_011_show_exact_payload` add `"integration": None`; and in `MilestoneTeamTests`:
     ```python
     def test_integration_writes_shows_and_clears(self):
         root = self.repo("ba", "an@corp.com")
         self.assertEqual(0, self.run_cli(root, "update", "t-m1", "--integration", "2026-11-03")[0])
         self.assertEqual("2026-11-03", self.metadata(root, "t-m1")["integration"])
         self.assertEqual(1, self.run_cli(root, "update", "t-m1", "--integration", "soon")[0])
         self.assertEqual(0, self.run_cli(root, "update", "t-m1", "--integration", "none")[0])
         self.assertNotIn("integration", self.metadata(root, "t-m1") or {})
     ```
     and in `ShowTextTests` a case that `_show_text` prints `integration: 2026-11-03` when the payload has it and no such line when it is null. In `MilestoneCliTests`, a case that `show` on a milestone with `--set-metadata integration=soon` (set through `self.bd`) exits 0 and prints `warning: t-m1: malformed integration metadata ignored` on stderr.
  6. Run `python3 -m pytest tests/workflow_core/test_milestone_cli.py -q` → fails.
  7. In `milestone_cli.py`: parser `update` adds `item.add_argument("--integration")`; in `_update`, before any `bd` call: `if args.integration == "none": argv += ["--unset-metadata", "integration"]` / `elif args.integration: argv += ["--set-metadata", f"integration={_date(args.integration).isoformat()}"]`. In `_show_text`, after the `deadline:` line: `if payload.get("integration"): lines.append(f"integration: {payload['integration']}")`. In `_run`, for `show` print `warning: {id}: malformed {key} metadata ignored` to stderr for each key of `core.metadata_problems(milestone)`; for `list`, do the same for every milestone bead listed.
  8. Run `python3 -m pytest tests/workflow_core/test_milestone.py tests/workflow_core/test_milestone_cli.py -q` → passes.
  9. Skill and docs:
     - `plugins/gin-workflow/src/skills/roadmap/SKILL.md` step 3: change "Name the epics left out and why (blocked, or over capacity)." to "Name the epics left out and why (blocked, or over capacity), and each adopted epic that `gin milestone show <id> --json` warns `oversized`, with a proposed split." In step 2, shorten "neither that size question nor an estimate revision counts against `project.max_questions`" to "neither counts against `project.max_questions`". Then `wc -c plugins/gin-workflow/src/skills/roadmap/SKILL.md` must print at most 12000; if not, shorten another sentence of step 2 or 3 without dropping a rule.
     - `references/way-of-working.md` Load block: after "an epic needs the groups its `Scope:` names", add "; QA (`qa`, `qe`) is needed by every epic whose `Scope:` names tests or cases".
     - `docs/reference/cli.md`: usage `update` line adds `[--integration YYYY-MM-DD|none]`; `update` row adds "; `--integration` stores or clears the integration date"; add to the warnings paragraph: "`after_integration` marks an open epic planned to end after the milestone's integration date. `open_bugs` counts open bug beads discovered from the epic. `oversized` marks an open epic whose planned days exceed the milestone's working days, with the excess in `days`. `show` adds `integration`. Malformed `away` or `integration` metadata is ignored with a warning on stderr."
     - Run `gin docs check docs/reference/cli.md` → ok.
  10. Run `python3 -m pytest -n auto -q` and read the summary line → passes.
  11. Commit: `feat(milestone): integration date, exit warnings, oversized epics (gin-workflow-milestone-capacity)`.
- **Acceptance criteria**: R4 to R9; US-3, US-4 pass as the tests above; `SKILL.md` at most 12,000 characters; JSON keys only added.
- **Estimated complexity**: medium

## Integration
- **Branch**: `feat/milestone-capacity`
- **Merge strategy**: sequential

## Validation
- [ ] `python3 -m pytest -n auto -q` passes (pre-push runs it).
- [ ] `gin docs check docs/reference/cli.md` reports no findings.
- [ ] `wc -c plugins/gin-workflow/src/skills/roadmap/SKILL.md` is at most 12000.
- [ ] `gin milestone show <id> --json` keeps `schema: 1` and every existing key.

## Notes
- `Model:` and `Effort:` are chosen from the main harness catalog using the route rubric.
- Omit `Effort:` when the catalog lists no efforts.
- Unclear requirements never raise the model or effort; ask the user or return to `discuss`.
- The user may override `Model:` and `Effort:` before plan approval.
- Provider roles describe responsibility rather than filename patterns.
- Deliverable merge-holds (e.g. "remain open until human-confirmed merge") apply exclusively to the Parent Bead. Individual track beads must close upon passing tests and code review to unblock downstream dependent tracks.
- Review lessons from `gin-workflow-milestone-gates`: new test classes go above the `__main__` guard, never between a decorator and its class, and never reuse an existing class name; check `--collect-only` counts.
- Member keys are the emails of `team.members` (the spec's "member name"); `--away` takes the email.
