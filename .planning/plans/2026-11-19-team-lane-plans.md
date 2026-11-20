# Plan: Team mode, the lead plans lanes and each member plans their own lane

Workflow: gin-workflow-g9az
Spec: `.planning/specs/2026-11-19-team-lane-plans-design.md`

## Objective

The lead's team plan declares lanes (owner, areas, repository, scope, acceptance criteria, contracts) and answers only the technical questions that cross areas; `gin team check-plan` accepts it without a track and `gin record plan-approved` accepts it while questions marked for a lane are open. The lead's orchestrate creates one lane bead per lane without tracks. The member who claims a lane bead writes the lane plan `<lead plan stem>.lane-<lane>.md`, answers the lane's questions, checks it with `gin team check-plan <lane plan>`, creates the lane's track beads and routes, and runs them on `feat/<topic>-<lane>` without the lead taking part before the lane's pull request. Plans without `## Lanes` and beads orchestrated before this change behave as before.

## Global Constraints

Copied from the spec (confirmed decisions, 2026-11-19):

- A lane plan is a file of its own next to the lead's plan: `<lead plan stem>.lane-<lane>.md`.
- At orchestrate the lead creates one lane bead per lane that has no track in the lead's plan; the member claims it, writes the lane plan, and creates the lane's track beads and routes.
- A technical question for one lane is written `- TQ-<n> (lane <name>): <question>` in the spec. `plan-approved` ignores such a question while it is open; the lane plan answers it with a `Decision:` line in the spec, on the lane branch.
- The lead's plan may mix declared lanes with tracks written in full (with `Lane:`); a lane with tracks in the lead's plan is planned by the lead, as today.

Copied from the spec (assumptions and out of scope):

- The lane bead stands for planning the lane. It closes when the lane plan is committed and the lane's track beads exist, not when the tracks close. `implementation_complete` stays unmet until the tracks close.
- `gin goal` covers tracks, not lane beads.
- The `## Lanes` format and the lane plan procedure are described in `skills/team/references/lanes.md`, not in `skills/plan/plan-schema.md`: the plan stage has 64 characters of budget left.
- Lane plans use the existing track schema of `skills/plan/plan-schema.md`, with track numbers unique within the lane plan file.
- Out of scope: approval of a lane plan before the lane's pull request, gin-console views of lanes, changes outside team mode, and splitting one lane between two members.

Added by this plan (test-enforced):

- `skills/team/SKILL.md` stays at or under 6,000 characters; each stage chain (`PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m workflow_core.budget --report`) stays at or under 12,000 (`tests/workflow_core/test_token_budget.py`). Measured before this change: team 5,884; plan 11,936; orchestrate 8,425; execute 11,816; ship 11,997. Measured with the exact wording of Track 6 (applied to a copy of `plugins/gin-workflow/src`): team 5,991; plan 11,981; orchestrate 8,485; execute 11,816; ship 11,997 (ship unchanged). Use the wording as written.
- `skills/team/references/lanes.md` is in no stage chain: `budget.stage_chain` follows only links of a stage skill and of skills it delegates to on a methodology line, and the stage skills name the `team` skill on their `project.team` line only. A plain-text `` `references/lanes.md` `` in `skills/plan/SKILL.md` or `skills/orchestrate/SKILL.md` resolves to no file (`budget._linked` tries `skills/<stage>/references/lanes.md` and `references/lanes.md`), so it adds only its own characters. Never write it as a Markdown link `[...](../team/references/lanes.md)`: that would add the whole file (7,983 characters) to the chain.
- Stage skills other than `team` contain no `` `bd `` token (`tests/test_no_direct_bd.py`) and exactly one line with `project.team` (`test_token_budget.py::test_team_guidance_loads_on_demand`).
- Tests that call `bd` live in classes with `@unittest.skipUnless(HAS_BD, "bd is not installed")`; no test calls the real `gh` (use `fake_cli` and `path_with`); the full suite passes with `bd` off `PATH`.
- `gin team` JSON output gains no field and loses none in this plan; no exact key-set test changes.

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
- Problem statement: in team mode the lead's `/plan` answers every technical question and writes every track's steps, also for areas the lead does not own. Since `gin-workflow-ifbt` a member's tracks form a lane with one branch, one worktree, and one pull request; the plan is still written by one person.
- Success criteria: US-1 to US-5 of the spec pass as tests or as skill text pinned by tests; the full suite passes, also with `bd` off `PATH`; `gin docs check` prints `ok` on the changed pages.
- Constraints: Global Constraints above.
- Non-goals: the out-of-scope list above.

Requirement map:

| Requirement | Track |
|---|---|
| R1 lane declarations | Track 1 (parser), Track 6 (format in `lanes.md`) |
| R2 plan check with lanes | Track 1 |
| R3 questions marked for a lane | Track 2 (parser, lint, `plan-approved`), Track 6 (the lead's plan stage leaves them open) |
| R4 `area_lead` areas | Track 2 |
| R5 lane beads | Track 3 (bead shape recognised by claim, ready, handoff, takeover), Track 6 (orchestrate creates them) |
| R6 topic and lane of a lane plan | Track 3 |
| R7 lane plan | Track 4 (`check-plan <lane plan>`), Track 6 (procedure) |
| R8 lane orchestrate | Track 6 (procedure); `gin routes resolve` already merges by `task_id` (`workflow_core/assignments.py:159-199`) |
| R9 dependencies on another lane | Track 5 (`team deps`, `team deps --bead`), Track 6 (placeholder creation) |
| R10 ship and complete | Track 5 (`team complete` test), Track 4 (open lane question refuses `check-plan`), Track 6 (ship runs it) |
| R11 goal | Track 5 |
| R12 documentation | Track 6 (skills), Track 7 (reference, guides, changelog) |
| US-1 | Track 1 (check-plan without tracks), Track 2 (`plan-approved`, `area_lead`) |
| US-2 | Track 3 (ready, claim), Track 4 (check-plan of a lane plan), Track 6 (lane orchestrate, no gate) |
| US-3 | Track 4 (open lane question), Track 5 (`team complete` with a lane plan), Track 6 (PR contents) |
| US-4 | Track 5 (`#lane-<name>` placeholders), Track 6 (dependencies of the lane's tracks) |
| US-5 | existing tests of every touched module, run in each track |

## Approach Options
### Option 1: Lane declarations in the lead plan, a lane plan file per lane, lane beads (confirmed at discuss)
- Summary: `## Lanes` declares each lane; a lane without tracks gets a lane bead `Plan: <lead plan>, Lane <name>`; its owner writes `<lead plan stem>.lane-<lane>.md`; every lane helper treats the lead plan and its lane plans as one plan (`team.lead_plan`).
- Pros: one epic, one spec, one `plan_approved` gate; claim, branch, worktree, complete, and deps reuse the lane code of `gin-workflow-ifbt`; plans without `## Lanes` take no new path.
- Cons: the lane plan is reviewed only in the lane's pull request.

### Option 2: Child epic per area with its own spec, plan, and gates
- Summary: the lead's epic holds the contracts; each area's epic is planned and approved on its own.
- Pros: each plan has its own gate.
- Cons: more specs, plans, and gates; gates are not recursive; rejected at discuss ("No child epics per area").

### Recommended Approach
- Selected option: Option 1.
- Rationale: confirmed by the user; it adds one Markdown section, one file name convention, and one bead description shape on top of the shipped lane code.

Decisions this plan makes where the spec leaves the choice open:

- `record plan-approved` reads the declared lanes from the plan file given as `--plan`, else `--evidence` when that is a file. With a PR URL as evidence and an open question marked for a lane, `--plan <path>` is required (`plan-approved refused: questions marked for a lane need the plan file as --plan or --evidence`). The check runs in every mode; lane-marked questions only appear in team plans.
- `gin team check-plan <lane plan>` finds the design doc through a `Spec: <design doc path>` line the lane plan must carry under its title, relative to the top of the git repository that holds the lane plan. This works for both layouts and needs no epic id.
- A lane plan is recognised by its file name only: `<stem>.lane-<lane>.md` with a name `team.valid_lane` accepts.
- The beads of a lane are keyed by (lead plan path, lane), where `team.lead_plan` maps a lane plan path to its lead plan path. This is the spec's "same topic and lane" with the plan's directory and date kept, so two plans of one topic in one epic never merge.
- A lane bead in a workspace also carries `Repo: <path>` when its declaration has `Repo:`, so its claim creates the worktree in the right child.
- A lane delivered in several pull requests: `team deps` records their merge commits on the placeholder separated by spaces, and `team deps --bead` requires each one.
- The lead plan's tracks in a declared lane are also checked to have an area of the lane (`Track <N>: area <area> is not an area of lane <lane>`), the same check the lane plan gets.
- `check-plan` refuses a lane plan for a lane that has tracks in the lead's plan (the lead plans it there).
- In a workspace, when the lane's `Repo:` is a child, the lane plan and the spec's decisions are committed on the parent's `feat/<topic>` (plans and specs live in the parent), not on the child's lane branch.
- `skills/ship/SKILL.md` is not changed: it has 3 characters of budget left and already defers team ship to the `team` skill, whose header sends the agent to `references/lanes.md`; the lane plan check at ship is in its `## Ship` section.

## Scope
- In scope: R1 to R12 and US-1 to US-5 of the spec.
- Out of scope: the spec's out-of-scope list; `gin team pending` rows for lane beads (a lane bead has no pull request before its tracks exist).

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Tracks 1 to 5 change team.py, team_beads.py, and their shared test files, each building on the helpers of the one before (plan_lanes, Question.lane, plan_lane/lead_plan, check_lane_plan); Track 6 rewrites skill text within character budgets measured over all skills; Track 7 documents the result. They run one after another on feat/team-lane-plans.
```

## Tasks

All paths are relative to the repository root. `S` stands for `plugins/gin-workflow/src/scripts/workflow_core`, `K` for `plugins/gin-workflow/src/skills`. Test helpers come from `tests/workflow_core/team_fixtures.py` (`make_team_repo`, `init_beads`, `git`, `write`, `fake_cli`, `calls`, `path_with`, `gh_pr`, `run_cli`, `run_cli_in_process`, `PLAN`, `TEAM`) and the local helpers of each test file (`bd`, `create`, `show`, `claim_meta` and the `LaneBeads` mixin in `test_team_beads.py`; `bd`, `create`, `show`, `merged_rule` in `test_team_complete.py`). The `PLAN` fixture is not changed by this plan, so the tests that build plans with `PLAN.replace(<multi-line block>, ...)` keep matching. New plan text for lanes lives in a constant `LANES` in `tests/workflow_core/test_team_gates.py` (Track 1).

In the team fixtures, `em@corp.com` (`be_dev`) may own `backend`, `chi@corp.com` (`fe_lead`, `fe_dev`) may own `frontend`, `binh@corp.com` (`be_lead`, `be_dev`) may own `backend` and leads it, and `plan_approved` is `area_lead`.

### Track 1: Lane declarations in the plan and `check-plan` (R1, R2)
- **Dependencies**: none
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team.py:219-365` (new `Lane`, `_LANES_HEADING`, `_LANE_HEADING`, `_LANE_META`, `plan_lanes`, `_lane_findings`, `_declaration_findings`, `_track_in_lane`; `check_plan`)
  - Test `tests/workflow_core/test_team_gates.py` (new constant `LANES`, `TestPlanChecks`)
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** one parser and a list of findings in one module, with every message fixed below; the existing track parser shows the pattern.
- **Interfaces produced**:
  - `team.Lane(name: str, owner: str, areas: tuple[str, ...], repo: str = "", depends: tuple[str, ...] = ())`, frozen dataclass.
  - `team.plan_lanes(path: Path, text: str | None = None) -> list[Lane]`: every `### Lane <name>` under `## Lanes`, duplicates kept, in file order.
  - `team._track_in_lane(track: Track, lane: Lane) -> list[str]` (Track 4 reuses it).
  - `team.check_plan(team, path, text=None)` keeps its signature; a plan with `## Lanes` needs no track.
- **Interfaces consumed**: `team.plan_tracks`, `team.valid_lane`, `team._FENCE`, `TeamConfig.member`, `TeamConfig.eligible`, `TeamConfig.areas`.
- **Findings** (exact texts; Track 7 quotes them):
  - `lane <name>: declared twice`
  - `lane <name>: invalid lane name`
  - `lane <name>: missing Area:` (only when `team.areas` is set, as for tracks)
  - `lane <name>: unknown area <area>`
  - `lane <name>: missing Owner:`
  - `lane <name>: owner <email> is not in team.members`
  - `lane <name>: owner <email> holds no role allowed in area <area>`
  - `lane <name>: Depends on lanes: <other> is not a declared lane`
  - `Track <N>: lane <lane> is not declared in ## Lanes`
  - `Track <N>: Owner: <email or -> is not the owner of lane <lane> (<lane owner>)`
  - `Track <N>: Repo: <path or .> is not the repository of lane <lane> (<lane repo or .>)`
  - `Track <N>: area <area> is not an area of lane <lane>`
- **Steps**:
  1. In `tests/workflow_core/test_team_gates.py`, add after `SPEC_PATH`:
     ```python
     LANES = """# Plan: Login

     ## Lanes

     ### Lane api
     - **Owner**: em@corp.com
     - **Area**: backend
     - **Scope**: the login API
     - **Acceptance criteria**: POST /login answers 200 or 401
     - **Contracts**: produces `POST /login`

     ### Lane web
     - **Owner**: chi@corp.com
     - **Area**: frontend
     - **Scope**: the login form
     - **Acceptance criteria**: the form posts to /login
     - **Contracts**: consumes `POST /login`
     - **Depends on lanes**: api

     ## Contracts

     - `POST /login`: request `{"email": str, "password": str}`; 200 `{"session": str}`; 401.

     ## Tasks

     ## Integration
     - Branch: feat/login
     """


     def lanes_plan(*blocks: str) -> str:
         """A plan whose `## Lanes` holds `blocks` and that has no track."""
         return "# Plan\n\n## Lanes\n\n" + "\n".join(blocks) + "\n## Tasks\n"


     MIXED = LANES.replace("## Tasks\n\n", PLAN[PLAN.index("## Tasks"):PLAN.index("## Integration")])
     ```
     Import `plan_lanes` next to `plan_tracks` in the `from workflow_core.team import (...)` block.
  2. Write failing tests in `TestPlanChecks`:
     ```python
     def test_plan_lanes_reads_the_declarations(self):
         path = write(self.root, PLAN_PATH, LANES)
         self.assertEqual([("api", "em@corp.com", ("backend",), "", ()),
                           ("web", "chi@corp.com", ("frontend",), "", ("api",))],
                          [(lane.name, lane.owner, lane.areas, lane.repo, lane.depends) for lane in plan_lanes(path)])
         plain = lanes_plan("### Lane `api`\n- Owner: `em@corp.com`\n- Area: backend\n- Area: frontend\n"
                            "- Repo: services/api\n- Depends on lanes: web, `qa`\n")
         self.assertEqual([("api", "em@corp.com", ("backend", "frontend"), "services/api", ("web", "qa"))],
                          [(lane.name, lane.owner, lane.areas, lane.repo, lane.depends)
                           for lane in plan_lanes(write(self.root, PLAN_PATH, plain))])
         fenced = "```markdown\n## Lanes\n\n### Lane x\n- Owner: em@corp.com\n```\n"
         self.assertEqual([], plan_lanes(write(self.root, PLAN_PATH, PLAN + fenced)))
         self.assertEqual([], plan_lanes(write(self.root, PLAN_PATH, PLAN)))

     def test_a_plan_with_lanes_and_no_track_passes(self):
         path = write(self.root, PLAN_PATH, LANES)
         self.assertEqual([], plan_tracks(path))
         self.assertEqual([], check_plan(self.team, path))
         result = run_cli(self.root, "team", "check-plan", str(path))
         self.assertEqual((0, "ok"), (result.returncode, result.stdout.strip()), result.stderr)
         self.assertEqual([f"{path}: no '### Track N:' sections"],
                          check_plan(self.team, write(self.root, PLAN_PATH, "# Plan\n\n## Lanes\n\n## Tasks\n")))

     def test_lane_declaration_findings(self):
         good = "### Lane api\n- Owner: em@corp.com\n- Area: backend\n"
         cases = [
             (lanes_plan("### Lane api\n- Area: backend\n"), "lane api: missing Owner:"),
             (lanes_plan("### Lane API\n- Owner: em@corp.com\n- Area: backend\n"), "lane API: invalid lane name"),
             (lanes_plan("### Lane t3\n- Owner: em@corp.com\n- Area: backend\n"), "lane t3: invalid lane name"),
             (lanes_plan(good, good), "lane api: declared twice"),
             (lanes_plan("### Lane api\n- Owner: chi@corp.com\n- Area: backend\n"),
              "lane api: owner chi@corp.com holds no role allowed in area backend"),
             (lanes_plan("### Lane api\n- Owner: zed@corp.com\n- Area: backend\n"),
              "lane api: owner zed@corp.com is not in team.members"),
             (lanes_plan("### Lane api\n- Owner: em@corp.com\n- Area: nowhere\n"), "lane api: unknown area nowhere"),
             (lanes_plan("### Lane api\n- Owner: em@corp.com\n"), "lane api: missing Area:"),
             (lanes_plan(good + "- Depends on lanes: web\n"), "lane api: Depends on lanes: web is not a declared lane"),
         ]
         for text, finding in cases:
             with self.subTest(finding):
                 self.assertEqual([finding], check_plan(self.team, write(self.root, PLAN_PATH, text)))

     def test_tracks_are_checked_against_their_declared_lane(self):
         self.assertEqual([], check_plan(self.team, write(self.root, PLAN_PATH, MIXED)))
         cases = [
             (MIXED.replace("- Lane: api", "- Lane: ops"), "Track 1: lane ops is not declared in ## Lanes"),
             (MIXED.replace("- Owner: em@corp.com\n- Lane: api", "- Owner: binh@corp.com\n- Lane: api"),
              "Track 1: Owner: binh@corp.com is not the owner of lane api (em@corp.com)"),
             (MIXED.replace("- Lane: api\n", "- Lane: api\n- Repo: services/a\n"),
              "Track 1: Repo: services/a is not the repository of lane api (.)"),
         ]
         for text, finding in cases:
             with self.subTest(finding):
                 self.assertEqual([finding], check_plan(self.team, write(self.root, PLAN_PATH, text)))
         other_area = MIXED.replace("### Lane api\n- **Owner**: em@corp.com\n- **Area**: backend",
                                    "### Lane api\n- **Owner**: em@corp.com\n- **Area**: frontend")
         self.assertIn("Track 1: area backend is not an area of lane api",
                       check_plan(self.team, write(self.root, PLAN_PATH, other_area)))

     def test_a_plan_without_lanes_is_checked_as_before(self):
         self.assertEqual([], check_plan(self.team, write(self.root, PLAN_PATH, PLAN)))
         self.assertIn("Track 1: missing Lane:",
                       check_plan(self.team, write(self.root, PLAN_PATH, PLAN.replace("- Lane: api\n", ""))))
     ```
  3. Run `timeout 300 python3 -m pytest tests/workflow_core/test_team_gates.py -q -k "Lane or lane or without_lanes"`: the new tests fail (`ImportError: cannot import name 'plan_lanes'`).
  4. In `S/team.py`, after `class Track` (line 228), add:
     ```python
     @dataclass(frozen=True)
     class Lane:
         """A `### Lane <name>` declaration under a plan's `## Lanes`."""
         name: str
         owner: str
         areas: tuple[str, ...]
         repo: str = ""
         depends: tuple[str, ...] = ()
     ```
     After `_IMPLICIT_LANE` (line 239), add:
     ```python
     _LANES_HEADING = "## Lanes"
     _LANE_HEADING = re.compile(r"^### Lane\s+`?([^`\s]+)`?\s*$")
     _LANE_META = re.compile(r"^-\s*(?:\*\*)?(Owner|Area|Repo|Depends on lanes)(?:\*\*)?:(?:\*\*)?\s*(.*?)\s*$")
     ```
     After `plan_tracks` (line 314), add:
     ```python
     def plan_lanes(path: Path, text: str | None = None) -> list[Lane]:
         """`### Lane <name>` declarations under `## Lanes` with their `Owner:`, `Area:` lines, `Repo:`, and
         `Depends on lanes:`; other lines of a declaration (Scope, Acceptance criteria, Contracts) are not read, and
         fenced code is skipped. Empty for a plan without `## Lanes`. `text` is the plan's content when it is not
         read from `path`."""
         lanes: list[Lane] = []
         current: dict[str, Any] | None = None
         inside = False
         fence = ""

         def close() -> None:
             if current is not None:
                 lanes.append(Lane(current["name"], current["owner"], tuple(dict.fromkeys(current["areas"])),
                                   current["repo"], tuple(current["depends"])))

         for line in (Path(path).read_text(encoding="utf-8") if text is None else text).splitlines():
             opener = _FENCE.match(line)
             if fence:
                 fence = "" if line.strip() == fence else fence
                 continue
             if opener:
                 fence = opener.group(1)
                 continue
             if line.startswith("## "):
                 close()
                 current, inside = None, line.strip() == _LANES_HEADING
                 continue
             if not inside:
                 continue
             if line.startswith("### "):
                 close()
                 heading = _LANE_HEADING.match(line)
                 current = None if heading is None else {"name": heading.group(1), "owner": "", "areas": [],
                                                         "repo": "", "depends": []}
                 continue
             meta = _LANE_META.match(line.strip()) if current is not None else None
             if meta is None:
                 continue
             key, value = meta.group(1), meta.group(2)
             if key == "Depends on lanes":
                 current["depends"] += [item.strip().strip("`") for item in value.split(",") if item.strip().strip("`")]
             elif key == "Area":
                 current["areas"].append(value.strip("`"))
             else:
                 current[key.lower()] = value.strip("`")
         close()
         return lanes
     ```
  5. In `check_plan` (line 317), replace the first three statements:
     ```python
     errors: list[str] = []
     tracks = plan_tracks(path, text)
     if not tracks:
         return [f"{path}: no '### Track N:' sections"]
     ```
     with:
     ```python
     errors: list[str] = []
     body = Path(path).read_text(encoding="utf-8") if text is None else text
     tracks = plan_tracks(path, body)
     lanes = plan_lanes(path, body)
     if not tracks and not lanes:
         return [f"{path}: no '### Track N:' sections"]
     ```
     and insert `errors += _lane_findings(team, lanes, tracks)` right before `listed: dict[str, list[int]] = {}`. After `check_plan`, add:
     ```python
     def _lane_findings(team: TeamConfig, lanes: Sequence[Lane], tracks: Sequence[Track]) -> list[str]:
         """Findings of a plan's `## Lanes`: each declaration, then each track against the lane its `Lane:` names.
         A track without a valid `Lane:` is reported by `check_plan` already."""
         if not lanes:
             return []
         errors: list[str] = []
         declared: dict[str, Lane] = {}
         for lane in lanes:
             if lane.name in declared:
                 errors.append(f"lane {lane.name}: declared twice")
                 continue
             declared[lane.name] = lane
             if not valid_lane(lane.name):
                 errors.append(f"lane {lane.name}: invalid lane name")
             errors += _declaration_findings(team, lane)
         for lane in declared.values():
             errors += [f"lane {lane.name}: Depends on lanes: {name} is not a declared lane"
                        for name in lane.depends if name not in declared]
         for track in tracks:
             if not track.lane or not valid_lane(track.lane):
                 continue
             lane = declared.get(track.lane)
             if lane is None:
                 errors.append(f"Track {track.number}: lane {track.lane} is not declared in ## Lanes")
             else:
                 errors += _track_in_lane(track, lane)
         return errors


     def _declaration_findings(team: TeamConfig, lane: Lane) -> list[str]:
         label = f"lane {lane.name}"
         errors: list[str] = []
         if team.areas and not lane.areas:
             errors.append(f"{label}: missing Area:")
         errors += [f"{label}: unknown area {name}" for name in lane.areas if team.areas and name not in team.areas]
         if not lane.owner:
             return errors + [f"{label}: missing Owner:"]
         member = team.member(lane.owner)
         if member is None:
             return errors + [f"{label}: owner {lane.owner} is not in team.members"]
         return errors + [f"{label}: owner {lane.owner} holds no role allowed in area {name}" for name in lane.areas
                          if name in team.areas and not team.eligible(member, team.areas[name])]


     def _track_in_lane(track: Track, lane: Lane) -> list[str]:
         """A track of a declared lane has the lane's owner and repository and one of its areas."""
         label = f"Track {track.number}"
         errors: list[str] = []
         if lane.owner and track.owner.lower() != lane.owner.lower():
             errors.append(f"{label}: Owner: {track.owner or '-'} is not the owner of lane {lane.name} ({lane.owner})")
         if (track.repo or ".") != (lane.repo or "."):
             errors.append(f"{label}: Repo: {track.repo or '.'} is not the repository of lane {lane.name} "
                           f"({lane.repo or '.'})")
         if track.area and lane.areas and track.area not in lane.areas:
             errors.append(f"{label}: area {track.area} is not an area of lane {lane.name}")
         return errors
     ```
  6. Run `timeout 300 python3 -m pytest tests/workflow_core/test_team_gates.py -q`: passes. Then `timeout 600 python3 -m pytest -n auto tests/workflow_core/test_team_pending.py tests/workflow_core/test_team_init.py tests/workflow_core/test_specs_technical_questions.py -q`: passes.
  7. Commit: `feat(team): plans declare lanes; check-plan checks them (<bead>)`.
- **Acceptance criteria**: R1 and R2; US-1 first criterion; every finding above prints exactly as listed; `test_team_gates.py` passes unchanged otherwise.
- **Estimated complexity**: medium

### Track 2: Questions marked for a lane, `plan-approved`, and `area_lead` areas (R3, R4)
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs.py:146-192` (`_TQ`, `Question`, `technical_questions`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/lifecycle_cli.py:273-331` (`_open_questions`, new `_lane_question_refusal`, the `plan-approved` block of `_record_command`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team.py:543-556` (`check_approval`: the plan block and the `area_lead` area set)
  - Test `tests/workflow_core/test_specs_technical_questions.py` (`TestParse`, `TestLint`, new `TestPlanApprovedLaneQuestions`)
  - Test `tests/workflow_core/test_team_gates.py` (`TestRecordGitHub`)
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** a regex group and a dataclass field, one refusal branch in `record`, and one set union; three modules but each change is a few lines with fixed messages.
- **Interfaces produced**:
  - `specs.Question(id: str, line: int, decision: str, lane: str = "")`; `technical_questions` fills `lane` from `- TQ-<n> (lane <name>): ...`.
  - `lifecycle_cli._open_questions(repo_path: Path, workflow_id: str) -> list[tuple[str, str]]`: `(label, lane)`, `label` as before (`<path>:<line>: TQ-<n>`), `lane` `""` when unmarked.
  - `lifecycle_cli._lane_question_refusal(plan: Path | None, marked: Sequence[tuple[str, str]]) -> str | None`.
  - Refusal messages (exact first lines; each then lists `<path>:<line>: TQ-<n> (lane <name>)` per question):
    - `plan-approved refused: questions marked for a lane need the plan file as --plan or --evidence`
    - `plan-approved refused: questions marked for a lane the plan does not declare`
- **Interfaces consumed**: `team.plan_lanes` (Track 1), `lifecycle_cli._plan_path`.
- **Steps**:
  1. Write failing tests in `tests/workflow_core/test_specs_technical_questions.py`:
     - `TestParse`:
       ```python
       def test_a_question_marked_for_a_lane_records_the_lane(self):
           found, errors = self.parse(spec("- TQ-4 (lane be): Which cache?\n  Decision: redis.\n- TQ-5: Which queue?\n"))
           self.assertEqual([], errors)
           self.assertEqual([("TQ-4", 12, "be", "redis."), ("TQ-5", 14, "", "")],
                            [(q.id, q.line, q.lane, q.decision) for q in found])
           found, errors = self.parse(spec("- TQ-6 (lane BE): x\n"))
           self.assertEqual([], found)
           self.assertIn(":12: not a question", errors[0])
       ```
     - `TestLint`:
       ```python
       def test_a_question_marked_for_a_lane_passes_lint(self):
           self.assertEqual([], specs.lint_design_spec(write(self.root, "lane.md", spec("- TQ-4 (lane be): a\n"))))
       ```
     - A new class after `TestPlanApprovedCheck`:
       ```python
       class TestPlanApprovedLaneQuestions(_Repo):
           """R3: an open question marked for a lane the plan declares does not refuse plan-approved."""

           PLAN = "# Plan\n\n## Lanes\n\n### Lane be\n- Owner: em@corp.com\n- Area: backend\n\n## Tasks\n"

           def setUp(self):
               super().setUp()
               write(self.root, "plan.md", self.PLAN)

           def record(self, questions: str, *extra: str, evidence: str = "plan.md"):
               write(self.root, SPEC_PATH, spec(questions))
               err = io.StringIO()
               with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                   code = cli_main(["record", "plan-approved", "--repository", str(self.root), "--evidence", evidence,
                                    "--actor", "user", "--workflow-id", "ep-1", *extra])
               return code, err.getvalue()

           gate = TestPlanApprovedCheck.gate

           def test_an_open_question_of_a_declared_lane_records_the_gate(self):
               self.assertEqual(0, self.record("- TQ-4 (lane be): Which cache?\n")[0])
               self.assertEqual("satisfied", self.gate())

           def test_an_open_question_without_a_lane_still_refuses(self):
               code, err = self.record("- TQ-4 (lane be): Which cache?\n- TQ-5: Which queue?\n")
               self.assertEqual(1, code)
               self.assertIn(f"plan-approved refused: open technical questions\n{SPEC_PATH}:13: TQ-5", err)
               self.assertNotIn("TQ-4", err)
               self.assertEqual("unmet", self.gate())

           def test_a_lane_the_plan_does_not_declare_refuses(self):
               code, err = self.record("- TQ-4 (lane ops): Which cache?\n")
               self.assertEqual(1, code)
               self.assertIn("plan-approved refused: questions marked for a lane the plan does not declare\n"
                             f"{SPEC_PATH}:12: TQ-4 (lane ops)", err)

           def test_without_a_plan_file_the_lane_cannot_be_checked(self):
               code, err = self.record("- TQ-4 (lane be): Which cache?\n", evidence="pr-123")
               self.assertEqual(1, code)
               self.assertIn("plan-approved refused: questions marked for a lane need the plan file as --plan or "
                             f"--evidence\n{SPEC_PATH}:12: TQ-4 (lane be)", err)
               self.assertEqual(0, self.record("- TQ-4 (lane be): Which cache?\n", "--plan", "plan.md",
                                               evidence="pr-123")[0])
       ```
  2. Write failing tests in `TestRecordGitHub` (`tests/workflow_core/test_team_gates.py`):
     ```python
     def test_plan_approved_needs_the_lead_of_each_declared_lane_area(self):
         write(self.root, PLAN_PATH, LANES)
         self.gh(gh_pr(files=[PLAN_PATH], reviews=[("binh-dev", "APPROVED", "c")]))
         result = self.record("plan-approved")
         self.assertEqual(1, result.returncode)
         self.assertIn("missing approval from fe_lead for area frontend", result.stderr)
         self.gh(gh_pr(files=[PLAN_PATH], reviews=[("binh-dev", "APPROVED", "c"), ("chi-fe", "APPROVED", "c")]))
         self.assertEqual(0, self.record("plan-approved").returncode)

     def test_plan_approved_with_an_open_lane_question_needs_the_plan_file(self):
         write(self.root, PLAN_PATH, LANES)
         questions = "# Login\n\nEpic: w\n\n## Open Technical Questions\n\n- TQ-4 (lane api): Which cache?\n"
         write(self.root, SPEC_PATH, questions)
         self.gh(gh_pr(files=[PLAN_PATH], reviews=[("binh-dev", "APPROVED", "c"), ("chi-fe", "APPROVED", "c")]))
         result = self.record("plan-approved")
         self.assertEqual(1, result.returncode)
         self.assertIn("questions marked for a lane need the plan file as --plan or --evidence", result.stderr)
         self.assertEqual([], calls(self.bin))
         write(self.root, SPEC_PATH, questions + "- TQ-5: Which queue?\n")
         result = self.record("plan-approved", PR, "--plan", PLAN_PATH)
         self.assertEqual(1, result.returncode)
         self.assertIn("plan-approved refused: open technical questions", result.stderr)
         write(self.root, SPEC_PATH, questions)
         result = self.record("plan-approved", PR, "--plan", PLAN_PATH)
         self.assertEqual(0, result.returncode, result.stderr)
     ```
  3. Run `timeout 300 python3 -m pytest tests/workflow_core/test_specs_technical_questions.py tests/workflow_core/test_team_gates.py -q`: the new tests fail.
  4. In `S/specs.py`:
     - Line 147: `_TQ = re.compile(r"^- (TQ-\d+)(?: \(lane ([a-z0-9][a-z0-9-]*)\))?: \S")`.
     - `Question` (line 154): add the last field `lane: str = ""` after `decision: str`.
     - Line 182: `questions.append(Question(question.group(1), number, "", question.group(2) or ""))`.
     - Docstring of `technical_questions`: `"""Questions under `## Open Technical Questions` (an empty decision is open; `- TQ-<n> (lane <name>):` records the lane) and the section's format errors."""`. The format error text `not a question (- TQ-<n>: <question>) or its Decision: line` stays as it is (pinned by `TestChangeLint`).
  5. In `S/lifecycle_cli.py`:
     - `_open_questions` (line 273): docstring `"""(`<path>:<line>: TQ-<n>`, lane) for each open technical question in the workflow's design doc; the lane is "" for a question not marked `(lane <name>)`."""`, return annotation `list[tuple[str, str]]`, and the last line:
       ```python
       return [(f"{shown(repo_path, design)}:{item.line}: {item.id}", item.lane)
               for item in questions if not item.decision]
       ```
       The two early `return []` stay.
     - After `_plan_path` (line 295), add:
       ```python
       def _lane_question_refusal(plan: Path | None, marked: Sequence[tuple[str, str]]) -> str | None:
           """Why plan-approved refuses open questions marked for a lane: no plan file to read its `## Lanes` from,
           or a lane the plan does not declare; None when the plan declares every lane."""
           from .team import plan_lanes

           if plan is None:
               return ("plan-approved refused: questions marked for a lane need the plan file as --plan or --evidence\n"
                       + "\n".join(f"{label} (lane {lane})" for label, lane in marked))
           declared = {lane.name for lane in plan_lanes(plan)}
           undeclared = [f"{label} (lane {lane})" for label, lane in marked if lane not in declared]
           if undeclared:
               return "plan-approved refused: questions marked for a lane the plan does not declare\n" + "\n".join(undeclared)
           return None
       ```
     - In `_record_command`, replace
       ```python
       if open_questions:
           return {"status": "rejected", "message": "plan-approved refused: open technical questions\n"
                   + "\n".join(open_questions)}, 1
       ```
       with
       ```python
       unmarked = [label for label, lane in open_questions if not lane]
       if unmarked:
           return {"status": "rejected", "message": "plan-approved refused: open technical questions\n"
                   + "\n".join(unmarked)}, 1
       marked = [(label, lane) for label, lane in open_questions if lane]
       if marked:
           root = Path(args.repository).resolve()
           refusal = _lane_question_refusal(_plan_path(root, args.plan) or _plan_path(root, evidence), marked)
           if refusal:
               return {"status": "rejected", "message": refusal}, 1
       ```
  6. In `S/team.py` `check_approval`:
     - After `tracks: list[Track] = []` (line 543) add `lanes: list[Lane] = []`; after `tracks = plan_tracks(plan, artifact_text)` (line 548) add `lanes = plan_lanes(plan, artifact_text)`.
     - Line 556 becomes
       ```python
       areas = {track.area for track in tracks if track.area} | {name for lane in lanes for name in lane.areas}
       for name in sorted(areas):
       ```
       and the docstring of `check_approval` adds: "Under `area_lead` the areas are those of the plan's tracks and of its declared lanes."
  7. Run `timeout 300 python3 -m pytest tests/workflow_core/test_specs_technical_questions.py tests/workflow_core/test_team_gates.py -q`: passes. Then `timeout 900 python3 -m pytest -n auto tests/workflow_core/ -q -k "lifecycle or specs or record or plan"`: passes.
  8. Commit: `feat(team): questions marked for a lane; plan-approved and area_lead read the declared lanes (<bead>)`.
- **Acceptance criteria**: R3 and R4; US-1 second and third criteria; an unmarked open question refuses exactly as before (`TestPlanApprovedCheck` unchanged and passing).
- **Estimated complexity**: medium

### Track 3: Topic, lane beads, and the beads of a lane across plan files (R5 bead shape, R6)
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team.py:242-245` (new `_LANE_PLAN`, `plan_lane`, `lead_plan` after `valid_lane`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team_pending.py:11-57` (import, new `_LANE_BEAD`, `lane_bead`; `topic_of`, `lane_branch`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team_beads.py:17-18` (imports), `:218-261` (`track_of`, `_lane`, new `_is_lane_bead`, `lane_of`, `lane_beads`), `:433` (`claim`: `delivered`)
  - Test `tests/workflow_core/test_team_pending.py` (`TestTopicOf`, `TestTrackRows`)
  - Test `tests/workflow_core/test_team_beads.py` (`LaneBeads` helpers, new `TestTeamLaneBeadClaim`)
- **Provider role**: `backend`
- **Model:** `opus`
- **Effort:** `high`
- **Why:** the lane identity every team command builds on (claim, handoff, takeover, reassign, ready, pending, complete) changes to span several plan files and a bead that is no track, with leases, worktrees, the merged-branch restart, and beads made before lanes all to keep working.
- **Interfaces produced**:
  - `team.plan_lane(path: str | Path) -> tuple[str, str] | None`: `(lead plan path, lane)` of `<stem>.lane-<lane>.md` with a valid lane name; None otherwise.
  - `team.lead_plan(path: str | Path) -> str`: the lead plan path of a lane plan path, else `str(path)`.
  - `team_pending.lane_bead(description: str) -> tuple[str, str] | None`: `(plan path, lane)` of a lane bead (`Plan: <path>, Lane <name>`).
  - `team_pending.topic_of(plan_path: str) -> str`: drops `.lane-<lane>` before the date.
  - `team_pending.lane_branch(description: str) -> str | None`: also for a lane bead.
  - `team_beads._lane(issue) -> tuple[str, int, str, bool] | None`: `(lead plan path, 0, lane, True)` for a lane bead.
  - `team_beads._is_lane_bead(issue: Mapping[str, Any]) -> bool`.
  - `team_beads.track_of(issue)`: `(topic, 0, repo)` for a lane bead.
  - `team_beads.lane_beads(root, issue)`: the epic's children with the same `(lead_plan(plan), lane)`.
  - `LaneBeads.LANE_PLAN`, `LaneBeads.lane_bead(lane="be", holder="binh@corp.com") -> str`, `LaneBeads.lane_track(number, lane="be") -> str` in `test_team_beads.py` (Track 5 uses them).
- **Interfaces consumed**: `team.valid_lane`, `team_pending.track_lane`, `team_beads._lane_targets`, `_lane_key`, `track_worktree`, `claim`, `ready`.
- **Steps**:
  1. Write failing tests in `tests/workflow_core/test_team_pending.py`. Add `from workflow_core.team import lead_plan, plan_lane` to the imports, then in `TestTopicOf`:
     ```python
     def test_a_lane_plan_has_the_topic_of_its_lead_plan(self):
         self.assertEqual("shop", team_pending.topic_of(".planning/plans/2026-11-19-shop.lane-be.md"))
         self.assertEqual("shop.lane-t3", team_pending.topic_of(".planning/plans/2026-11-19-shop.lane-t3.md"))
         self.assertEqual((".planning/plans/2026-11-19-shop.md", "qa-e2e"),
                          plan_lane(".planning/plans/2026-11-19-shop.lane-qa-e2e.md"))
         self.assertIsNone(plan_lane(".planning/plans/2026-11-19-shop.md"))
         self.assertEqual("docs/changes/c/04-plan.md", lead_plan("docs/changes/c/04-plan.lane-be.md"))
         self.assertEqual("p.md", lead_plan("p.md"))

     def test_a_lane_bead_and_its_branch(self):
         lane = "Lane be: the API\n\nPlan: .planning/plans/2026-11-19-shop.md, Lane be\nLane: be\n"
         self.assertEqual((".planning/plans/2026-11-19-shop.md", "be"), team_pending.lane_bead(lane))
         self.assertEqual("feat/shop-be", team_pending.lane_branch(lane))
         self.assertEqual("feat/shop-be", team_pending.lane_branch(
             "Plan: .planning/plans/2026-11-19-shop.lane-be.md, Track 2\nLane: be\n"))
         self.assertIsNone(team_pending.lane_bead("Plan: p.md, Track 1\nLane: be\n"))
         self.assertIsNone(team_pending.track_lane(lane))
     ```
     and in `TestTrackRows`:
     ```python
     def test_a_lane_plan_track_is_on_the_lead_topic_branch_and_a_lane_bead_has_no_row(self):
         lane_plan = PLAN_PATH.replace(".md", ".lane-web.md")
         self.bd({**TRACK, "id": "e-1.4", "description": f"Plan: {lane_plan}, Track 1\nLane: web\n"},
                 {**TRACK, "id": "e-1.5", "description": f"Plan: {PLAN_PATH}, Lane web\nLane: web\n"})
         self.gh(("feat/login-web", gh_pr(PR_TRACK, state="OPEN", author="em-dev", files=["web/login.tsx"])))
         self.assertEqual([("feat/login-web", None, "e-1")],
                          [(row["branch"], row["gate"], row["epic"]) for row in self.pending()])
     ```
  2. Write failing tests in `tests/workflow_core/test_team_beads.py`. Add `calls` to the `from team_fixtures import ...` line. In `LaneBeads`, add after `URL`:
     ```python
     LANE_PLAN = ".planning/plans/2026-11-19-shop.lane-be.md"
     ```
     and after `track`:
     ```python
     def lane_bead(self, lane: str = "be", holder: str = "binh@corp.com") -> str:
         text = f"Plan: {self.PLAN}, Lane {lane}\nLane: {lane}"
         bead = json.loads(bd(self.root, "create", f"Lane {lane}: the shop API", "--parent", self.epic, "-l",
                              f"lane:{lane},area:backend", "--description", text, "--json"))["id"]
         if holder:
             bd(self.root, "update", bead, "--assignee", holder)
         return bead

     def lane_track(self, number: int, lane: str = "be") -> str:
         text = f"Plan: {self.PLAN.replace('.md', f'.lane-{lane}.md')}, Track {number}\nLane: {lane}"
         return json.loads(bd(self.root, "create", f"Lane track {number}", "--parent", self.epic, "-l",
                              "area:backend", "--description", text, "--json"))["id"]
     ```
     Then a new class after `TestTeamLaneClaim`:
     ```python
     @unittest.skipUnless(HAS_BD, "bd is not installed")
     class TestTeamLaneBeadClaim(LaneBeads, unittest.TestCase):
         """R5, R6, US-2: a lane bead and the tracks of its lane plan are one lane of the lead plan."""

         def test_ready_lists_the_lane_bead_on_the_lane_branch(self):
             lane = self.lane_bead()
             rows = {row["id"]: row for row in json.loads(run_cli(self.root, "team", "ready", "--format", "json").stdout)["ready"]}
             self.assertEqual(("be", "feat/shop-be"), (rows[lane]["lane"], rows[lane]["branch"]))

         def test_claiming_a_lane_bead_gives_the_lane_worktree(self):
             lane = self.lane_bead()
             claimed = self.claim(lane)
             self.assertEqual(0, claimed.returncode, claimed.stdout + claimed.stderr)
             data = json.loads(claimed.stdout)
             self.assertEqual(("be", [lane], "feat/shop-be", True),
                              (data["lane"], data["beads"], data["branch"], data["created"]))
             self.assertTrue(data["worktree"].endswith(f".planning/worktrees/{self.epic}-be"), data["worktree"])
             self.assertEqual("in_progress", show(self.root, lane)["status"])

         def test_claiming_a_lane_bead_takes_the_open_tracks_of_its_lane_plan(self):
             lane, t1, t2 = self.lane_bead(), self.lane_track(1), self.lane_track(2)
             other = self.track(3, "fe", "frontend")
             data = json.loads(self.claim(lane).stdout)
             self.assertEqual([lane, t1, t2], data["beads"])
             self.assertEqual("binh@corp.com", show(self.root, t2)["assignee"])
             self.assertFalse(show(self.root, other).get("assignee"))

         def test_a_lead_plan_track_and_a_lane_plan_track_share_the_lane(self):
             lead, planned = self.track(1), self.lane_track(1)
             data = json.loads(self.claim(lead).stdout)
             self.assertEqual(([lead, planned], "feat/shop-be"), (data["beads"], data["branch"]))

         def test_a_foreign_lease_on_the_lane_bead_refuses_with_the_lane_message(self):
             lane = self.lane_bead(holder="")
             bd(self.root, "update", lane, "--claim", actor="em@corp.com")
             claim_meta(self.root, lane, "em@corp.com", "2999-01-01T00:00:00Z")
             track = self.lane_track(1)
             refused = self.claim(track)
             self.assertEqual(1, refused.returncode, refused.stdout + refused.stderr)
             self.assertIn(f"lane be is claimed by em@corp.com until 2999-01-01T00:00:00Z ({lane})", refused.stdout)

         def test_a_closed_lane_bead_does_not_count_as_a_delivered_track(self):
             lane = self.lane_bead()
             bd(self.root, "close", lane)
             t1, t2 = self.lane_track(1), self.lane_track(2)
             self.assertEqual(0, self.claim(t1, []).returncode)
             claimed = self.claim(t2, [])
             self.assertEqual(0, claimed.returncode, claimed.stdout + claimed.stderr)
             self.assertNotIn("note", json.loads(claimed.stdout))
             self.assertEqual([], calls(self.bin))
     ```
  3. Run `timeout 300 python3 -m pytest tests/workflow_core/test_team_pending.py -q` and `timeout 900 python3 -m pytest -n auto tests/workflow_core/test_team_beads.py -q -k LaneBead`: the new tests fail.
  4. In `S/team.py`, after `valid_lane` (line 244):
     ```python
     _LANE_PLAN = re.compile(r"^(.*)\.lane-([a-z0-9][a-z0-9-]*)\.md$")


     def plan_lane(path: str | Path) -> tuple[str, str] | None:
         """(lead plan path, lane) of a lane plan path `<lead plan stem>.lane-<lane>.md`; None for any other path."""
         found = _LANE_PLAN.match(str(path))
         return (f"{found[1]}.md", found[2]) if found and valid_lane(found[2]) else None


     def lead_plan(path: str | Path) -> str:
         """The lead plan path of a lane plan path; any other plan path as given."""
         found = plan_lane(path)
         return found[0] if found else str(path)
     ```
  5. In `S/team_pending.py`:
     - Line 11: `from .team import TeamConfig, TeamError, lead_plan`.
     - After `_LANE_LINE` (line 15): `_LANE_BEAD = re.compile(r"^Plan:\s*`?([^`,\n]+?)`?,\s*Lane\s+`?([a-z0-9][a-z0-9-]*)`?\s*$", re.MULTILINE)`.
     - `topic_of` (line 38):
       ```python
       def topic_of(plan_path: str) -> str:
           """The plan file stem without a leading `YYYY-MM-DD-`; a lane plan `<stem>.lane-<lane>.md` has the topic of
           its lead plan."""
           return re.sub(r"^\d{4}-\d{2}-\d{2}-", "", Path(lead_plan(plan_path)).stem)
       ```
     - After `track_lane`:
       ```python
       def lane_bead(description: str) -> tuple[str, str] | None:
           """(plan path, lane) of a lane bead description (`Plan: <path>, Lane <name>`): the bead that stands for
           planning a lane the plan declares without tracks; None for any other bead."""
           found = _LANE_BEAD.search(description)
           return (found[1], found[2]) if found else None
       ```
     - `lane_branch` (line 54):
       ```python
       def lane_branch(description: str) -> str | None:
           """`feat/<topic>-<lane>` of a track bead or a lane bead description; None for any other bead."""
           found = track_lane(description)
           if found is not None:
               return f"feat/{topic_of(found[0])}-{found[2]}"
           planned = lane_bead(description)
           return None if planned is None else f"feat/{topic_of(planned[0])}-{planned[1]}"
       ```
  6. In `S/team_beads.py`:
     - Line 17: `from .team import Area, Member, TeamConfig, TeamError, lead_plan, plan_tracks`.
     - Line 18: `from .team_pending import lane_bead, lane_branch, topic_of, track_lane` (`_TRACK_LINE` is no longer used here).
     - Replace `track_of` and `_lane` (lines 218-229) with:
       ```python
       def track_of(issue: Mapping[str, Any]) -> tuple[str, int, str | None] | None:
           """(topic, track number, `Repo:` path or None) of a track bead (`Plan: <path>, Track <N>`) or of a lane bead
           (`Plan: <path>, Lane <name>`, track number 0); None for any other bead."""
           found = _lane(issue)
           if found is None:
               return None
           repo = _REPO_LINE.search(str(issue.get("description") or ""))
           return topic_of(found[0]), found[1], repo[1] if repo else None


       def _lane(issue: Mapping[str, Any]) -> tuple[str, int, str, bool] | None:
           """(plan path, track number, lane, named) of a track bead, or (plan path, 0, lane, True) of a lane bead."""
           body = str(issue.get("description") or "")
           found = track_lane(body)
           if found is not None:
               return found
           planned = lane_bead(body)
           return None if planned is None else (planned[0], 0, planned[1], True)


       def _is_lane_bead(issue: Mapping[str, Any]) -> bool:
           return lane_bead(str(issue.get("description") or "")) is not None
       ```
     - `lane_of` docstring: `"""The lane of a track bead or a lane bead: its `Lane:` line, else the implicit `t<N>`; None for any other bead."""`.
     - `lane_beads` (line 238):
       ```python
       def lane_beads(root: Path, issue: Mapping[str, Any]) -> list[dict[str, Any]]:
           """The beads of `issue`'s lane, any status: the children of its epic with the same lead plan (the plan, or
           any of its lane plans `<stem>.lane-<lane>.md`) and the same lane, the lane bead included. Just `issue` for a
           bead that is no track or has no parent."""
           own, epic = _lane(issue), issue.get("parent")
           if own is None or not epic:
               return [dict(issue)]
           key = (lead_plan(own[0]), own[2])
           rows = [row for row in _bd_json(root, ["list", "--parent", str(epic), "--all", "--limit", "0"])
                   if (found := _lane(row)) is not None and (lead_plan(found[0]), found[2]) == key]
           return rows if any(row["id"] == issue["id"] for row in rows) else [dict(issue), *rows]
       ```
     - `claim`, line 433: `delivered = any(row.get("status") == "closed" and not _is_lane_bead(row) for row in lane)` (a closed lane bead means the lane was planned, not that a pull request merged).
  7. Run `timeout 300 python3 -m pytest tests/workflow_core/test_team_pending.py -q` and `timeout 1200 python3 -m pytest -n auto tests/workflow_core/test_team_beads.py tests/workflow_core/test_team_complete.py tests/workflow_core/test_goal.py -q`: passes, including every `TestTeamLaneClaim`, `TestTeamLaneHandoff`, and `TestTeamClaimWorktree` test (beads without `Lane:` and beads of plans without lane plans behave as before, US-5).
  8. Commit: `feat(team): lane beads and lane plan tracks share the lane of their lead plan (<bead>)`.
- **Acceptance criteria**: R6; R5's bead shape is read by claim, ready, handoff, takeover, and reassign; US-2 first criterion; the refusal for a lane held by another member is the existing `lane <name> is claimed by <email> until <expires_at> (<bead>)`.
- **Estimated complexity**: high

### Track 4: `check-plan` of a lane plan (R7, R10 ship refusal)
- **Dependencies**: Track 1, Track 2, Track 3
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team.py` (new `_SPEC_LINE`, `_git_top`, `check_lane_plan` after `_track_in_lane`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team_cli.py:210-215` (`check-plan` picks the lane plan check)
  - Test `tests/workflow_core/test_team_gates.py` (new class `TestLanePlanChecks`)
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** one function composed of `check_plan`, `plan_lanes`, `_track_in_lane`, and `technical_questions`, plus a two-line dispatch; the findings are fixed below.
- **Interfaces produced**:
  - `team.check_lane_plan(team: TeamConfig, path: Path, root: Path) -> list[str]`.
  - Findings (exact texts): `<path>: lead plan <lead> not found`; `<path>: lane <lane> is not declared in <lead>`; `<path>: lane <lane> has tracks in <lead>; the lead plans it there`; `Track <N>: lane <other> is not lane <lane>`; the findings of `check_plan` and `_track_in_lane` (Track 1); `<path>: missing Spec: <design doc path> line`; `<path>: Spec: <spec> is not a file`; `<spec>:<line>: TQ-<n> (lane <lane>) has no Decision:`.
- **Interfaces consumed**: `team.plan_lane`, `team.plan_lanes`, `team.plan_tracks`, `team.check_plan`, `team._track_in_lane`, `specs.technical_questions` and `Question.lane` (Track 2).
- **Steps**:
  1. Write failing tests: a new class at the end of `tests/workflow_core/test_team_gates.py` (no `bd`, no host):
     ````python
     LANE_PATH = ".planning/plans/2026-10-03-login.lane-api.md"
     LANE_PLAN = """# Plan: Login API

     Spec: .planning/specs/2026-10-03-login-design.md

     ## Tasks

     ### Track 1: API
     - **Area**: backend
     - **Owner**: em@corp.com
     - **Lane**: api
     - **Files**:
       - Create `services/auth/login.py`
       - Test `tests/services/test_login.py`

     ### Track 2: Session
     - **Area**: backend
     - **Owner**: em@corp.com
     - **Lane**: api
     - **Files**:
       - Create `services/auth/session.py`

     ## Integration
     """
     QUESTIONS = "# Login\n\nEpic: w\n\n## Open Technical Questions\n\n- TQ-4 (lane api): Which cache?\n"


     class TestLanePlanChecks(unittest.TestCase):
         """R7, R10, US-2, US-3: a lane plan is checked against its lane's declaration and its lane's questions."""

         def setUp(self):
             self.tmp = tempfile.TemporaryDirectory()
             self.addCleanup(self.tmp.cleanup)
             self.root = make_team_repo(Path(self.tmp.name) / "repo")
             self.team = load_team(yaml.safe_load((self.root / ".agent-workflow/config.yaml").read_text()))
             self.lead = write(self.root, PLAN_PATH, LANES)
             write(self.root, SPEC_PATH, QUESTIONS + "  Decision: redis.\n- TQ-5 (lane web): Which store?\n")

         def check(self, text: str = LANE_PLAN, relative: str = LANE_PATH) -> list[str]:
             return check_lane_plan(self.team, write(self.root, relative, text), self.root)

         def test_a_lane_plan_that_follows_its_lane_passes(self):
             self.assertEqual([], self.check())
             result = run_cli(self.root, "team", "check-plan", LANE_PATH, "--format", "json")
             self.assertEqual(0, result.returncode, result.stdout + result.stderr)

         def test_another_lane_another_owner_or_a_file_outside_the_area_fails(self):
             second = LANE_PLAN.index("### Track 2")
             head, tail = LANE_PLAN[:second], LANE_PLAN[second:]
             cases = [
                 (head + tail.replace("- **Lane**: api", "- **Lane**: web"), ["Track 2: lane web is not lane api"]),
                 (head + tail.replace("- **Owner**: em@corp.com", "- **Owner**: binh@corp.com"),
                  ["lane api: tracks 1 and 2 have different owners",
                   "Track 2: Owner: binh@corp.com is not the owner of lane api (em@corp.com)"]),
                 (head + tail.replace("`services/auth/session.py`", "`web/session.tsx`"),
                  ["Track 2: web/session.tsx is outside area backend"]),
             ]
             for text, findings in cases:
                 with self.subTest(findings[-1]):
                     self.assertEqual(findings, self.check(text))
             result = run_cli(self.root, "team", "check-plan", LANE_PATH)
             self.assertEqual(1, result.returncode)
             self.assertIn("Track 2: web/session.tsx is outside area backend", result.stdout)

         def test_a_track_in_another_area_of_the_team_is_reported(self):
             second = LANE_PLAN.index("### Track 2")
             text = LANE_PLAN[:second] + LANE_PLAN[second:].replace("- **Area**: backend", "- **Area**: frontend")
             self.assertIn("Track 2: area frontend is not an area of lane api", self.check(text))

         def test_the_lead_plan_must_declare_the_lane_without_tracks(self):
             ops = self.check(relative=".planning/plans/2026-10-03-login.lane-ops.md")
             self.assertEqual([f"{self.root / '.planning/plans/2026-10-03-login.lane-ops.md'}: lane ops is not declared in "
                               f"{self.lead}"], ops)
             write(self.root, PLAN_PATH, MIXED)
             self.assertEqual([f"{self.root / LANE_PATH}: lane api has tracks in {self.lead}; the lead plans it there"],
                              self.check())
             self.lead.unlink()
             self.assertEqual([f"{self.root / LANE_PATH}: lead plan {self.lead} not found"], self.check())

         def test_an_open_question_of_the_lane_fails_and_others_are_ignored(self):
             write(self.root, SPEC_PATH, QUESTIONS + "- TQ-5 (lane web): Which store?\n- TQ-6: Which queue?\n")
             self.assertEqual([f"{SPEC_PATH}:7: TQ-4 (lane api) has no Decision:"], self.check())
             result = run_cli(self.root, "team", "check-plan", LANE_PATH)
             self.assertEqual(1, result.returncode)

         def test_the_lane_plan_names_its_design_doc(self):
             path = self.root / LANE_PATH
             self.assertEqual([f"{path}: missing Spec: <design doc path> line"],
                              self.check(LANE_PLAN.replace(f"Spec: {SPEC_PATH}\n", "")))
             self.assertEqual([f"{path}: Spec: .planning/specs/nope.md is not a file"],
                              self.check(LANE_PLAN.replace(SPEC_PATH, ".planning/specs/nope.md")))
     ````
     Import `check_lane_plan` in the `from workflow_core.team import (...)` block. `run_cli` here is `run_cli_in_process`, which runs from `self.root`, so the relative `LANE_PATH` resolves there.
  2. Run `timeout 300 python3 -m pytest tests/workflow_core/test_team_gates.py -q -k LanePlanChecks`: the tests fail (`ImportError`).
  3. In `S/team.py`, after `_track_in_lane`:
     ```python
     _SPEC_LINE = re.compile(r"^Spec:\s*`?([^`\s]+)`?\s*$", re.MULTILINE)


     def _git_top(directory: Path) -> Path | None:
         done = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=directory, text=True, capture_output=True,
                               check=False)
         top = done.stdout.strip()
         return Path(top) if done.returncode == 0 and top else None


     def check_lane_plan(team: TeamConfig, path: Path, root: Path) -> list[str]:
         """Findings of a lane plan `<lead plan stem>.lane-<lane>.md`. The lead plan beside it must declare the lane
         and have no track of it; then the checks of `check_plan`, each track against the lane's declaration, and
         each question of the design doc that its `Spec:` line names, marked `(lane <lane>)`, without a `Decision:`.
         `Spec:` is relative to the top of the git repository that holds the lane plan, else to `root`."""
         from .specs import technical_questions

         found = plan_lane(path)
         if found is None:
             raise TeamError(f"{path} is not a lane plan (<lead plan stem>.lane-<lane>.md)")
         lead, name = found
         if not Path(lead).is_file():
             return [f"{path}: lead plan {lead} not found"]
         lane = next((item for item in plan_lanes(Path(lead)) if item.name == name), None)
         if lane is None:
             return [f"{path}: lane {name} is not declared in {lead}"]
         if any(track.lane == name for track in plan_tracks(Path(lead))):
             return [f"{path}: lane {name} has tracks in {lead}; the lead plans it there"]
         text = Path(path).read_text(encoding="utf-8")
         errors = check_plan(team, path, text)
         for track in plan_tracks(path, text):
             if track.lane and track.lane != name:
                 errors.append(f"Track {track.number}: lane {track.lane} is not lane {name}")
             elif track.lane:
                 errors += _track_in_lane(track, lane)
         spec = _SPEC_LINE.search(text)
         if spec is None:
             return errors + [f"{path}: missing Spec: <design doc path> line"]
         design = Path(spec[1])
         if not design.is_absolute():
             design = (_git_top(Path(path).resolve().parent) or Path(root)) / design
         if not design.is_file():
             return errors + [f"{path}: Spec: {spec[1]} is not a file"]
         questions, _ = technical_questions(design, spec[1])
         return errors + [f"{spec[1]}:{item.line}: {item.id} (lane {name}) has no Decision:"
                          for item in questions if item.lane == name and not item.decision]
     ```
  4. In `S/team_cli.py` line 211, replace `findings = team_core.check_plan(team, args.plan)` with:
     ```python
     findings = (team_core.check_lane_plan(team, args.plan, root) if team_core.plan_lane(args.plan)
                 else team_core.check_plan(team, args.plan))
     ```
     The workspace `check_plan_repos` lines after it stay and apply to a lane plan too.
  5. Run `timeout 300 python3 -m pytest tests/workflow_core/test_team_gates.py -q`: passes.
  6. Commit: `feat(team): check-plan checks a lane plan against its lane and its questions (<bead>)`.
- **Acceptance criteria**: R7's check; US-2 second criterion; R10's "ship of a lane refuses while a question marked for the lane has no decision" is `check-plan <lane plan>` exiting 1 (ship runs it, Track 6); a plan that is no lane plan is checked by `check_plan` as before.
- **Estimated complexity**: medium

### Track 5: Lane placeholders in `team deps`, goal over lane beads, complete with a lane plan (R9, R10, R11)
- **Dependencies**: Track 3
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team_beads.py:20` (`_EXTERNAL`), `:747-777` (`deps`, new `_lane_delivered`), `:805-830` (`deps_for`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/goal.py:19-62` (`goal_text`)
  - Test `tests/workflow_core/test_team_beads.py` (new `TestTeamDepsLane`)
  - Test `tests/workflow_core/test_goal.py` (`TestGoalTeam`)
  - Test `tests/workflow_core/test_team_complete.py` (`TestTeamComplete`)
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `high`
- **Why:** bounded changes to two modules with a clear spec, but the placeholder logic has several waiting states, several pull requests per lane, and merge commits checked in other repositories.
- **Interfaces produced**:
  - `team_beads._EXTERNAL = re.compile(r"^external: (\S+)#(\d+|lane-[a-z0-9][a-z0-9-]*)$")`.
  - `team_beads._lane_delivered(root: Path, team: TeamConfig, plan: str, lane: str, beads: Sequence[Mapping[str, Any]]) -> tuple[list[Any], str | None]`: the merged pull requests that list every track of the lane (empty while one is not listed) and the `repo` metadata; raises `SyncConflict` with the waiting reason `lane <lane> of <plan> has no bead`, `lane <lane> has open beads: <ids>`, or `lane <lane> has no track bead yet`.
  - `team deps` records `merge_commit` as the delivering pull requests' merge commits joined by one space, `closed[].pr` as their URLs joined by `, `, and the close reason `<urls> merged (<commits>)` (unchanged for one pull request).
  - `team deps --bead` requires every commit of `merge_commit`.
  - `goal.goal_text(...)` signature unchanged; a lane bead is no track, and with `member` it prints one `No goal: lane <name> has no tracks yet; run /plan for it.` line per lane when the member's only open beads in the epic are lane beads.
- **Interfaces consumed**: `team.lead_plan`, `team_pending.lane_bead`, `team_beads._lane`, `_is_lane_bead`, `track_of`, `_track_repo`, `_delivers`, `team_host.merged_with_text`, `LaneBeads.lane_bead`, `LaneBeads.lane_track` (Track 3).
- **Steps**:
  1. Write failing tests in `tests/workflow_core/test_team_beads.py`, a new class after `TestTeamLaneBeadClaim`:
     ```python
     @unittest.skipUnless(HAS_BD, "bd is not installed")
     class TestTeamDepsLane(LaneBeads, unittest.TestCase):
         """R9, US-4: `external: <plan>#lane-<name>` closes once lane <name> has no open bead and every track merged."""

         def deps(self, *prs: tuple[str, str, str]) -> dict:
             fake_cli(self.bin, "gh", [{"argv": ["pr", "list"], "stdout": [
                 {"url": url, "mergeCommit": {"oid": commit}, "body": f"Plan: {self.LANE_PLAN}\nTracks: {tracks}\n"}
                 for url, commit, tracks in prs]}])
             result = run_cli(self.root, "team", "deps", "--format", "json", env=path_with(self.bin))
             self.assertEqual(0, result.returncode, result.stdout + result.stderr)
             return json.loads(result.stdout)

         def planned_lane(self, *open_tracks: int) -> tuple[str, str]:
             """A closed lane bead, tracks 1 and 2 of the lane plan (closed unless listed), and the placeholder."""
             lane = self.lane_bead()
             bd(self.root, "close", lane)
             for number in (1, 2):
                 track = self.lane_track(number)
                 if number not in open_tracks:
                     bd(self.root, "close", track)
             return lane, create(self.root, f"external: {self.PLAN}#lane-be")

         def test_a_merged_lane_closes_its_placeholder(self):
             _lane, ext = self.planned_lane()
             payload = self.deps((self.URL, "abc", "1, 2"))
             self.assertEqual([{"id": ext, "pr": self.URL}], payload["closed"])
             self.assertEqual(("closed", "abc"), (show(self.root, ext)["status"], show(self.root, ext)["metadata"]["merge_commit"]))

         def test_a_lane_merged_in_two_pull_requests_records_both_commits(self):
             _lane, ext = self.planned_lane()
             second = "https://github.com/org/app/pull/10"
             payload = self.deps((self.URL, "abc", "1"), (second, "def", "2"))
             self.assertEqual([{"id": ext, "pr": f"{self.URL}, {second}"}], payload["closed"])
             self.assertEqual("abc def", show(self.root, ext)["metadata"]["merge_commit"])

         def test_an_open_track_or_lane_bead_keeps_it_waiting_with_a_reason(self):
             _lane, ext = self.planned_lane(2)
             payload = self.deps((self.URL, "abc", "1, 2"))
             self.assertEqual([ext], payload["waiting"])
             self.assertTrue(payload["reasons"][ext].startswith("lane be has open beads: "), payload["reasons"])
             self.assertEqual("open", show(self.root, ext)["status"])

         def test_a_lane_not_planned_yet_waits(self):
             lane = self.lane_bead()
             ext = create(self.root, f"external: {self.PLAN}#lane-be")
             self.assertEqual(f"lane be has open beads: {lane}", self.deps()["reasons"][ext])
             bd(self.root, "close", lane)
             self.assertEqual("lane be has no track bead yet", self.deps()["reasons"][ext])
             other = create(self.root, f"external: {self.PLAN}#lane-ops")
             self.assertEqual(f"lane ops of {self.PLAN} has no bead", self.deps()["reasons"][other])

         def test_a_track_no_merged_pull_request_lists_waits_without_a_reason(self):
             _lane, ext = self.planned_lane()
             payload = self.deps((self.URL, "abc", "1"))
             self.assertEqual([ext], payload["waiting"])
             self.assertNotIn(ext, payload["reasons"])

         def test_the_bead_check_needs_every_recorded_commit(self):
             git(self.root, "commit", "-q", "--allow-empty", "-m", "one")
             first = git(self.root, "rev-parse", "HEAD").strip()
             git(self.root, "commit", "-q", "--allow-empty", "-m", "two")
             second = git(self.root, "rev-parse", "HEAD").strip()
             work = create(self.root, "work", "area:backend")
             ext = create(self.root, f"external: {self.PLAN}#lane-be")
             bd(self.root, "update", ext, "--set-metadata", f"merge_commit={first} {second}")
             bd(self.root, "close", ext)
             bd(self.root, "dep", "add", work, ext)
             result = run_cli(self.root, "team", "deps", "--bead", work, "--format", "json")
             self.assertEqual(0, result.returncode, result.stdout + result.stderr)
             self.assertEqual([ext], json.loads(result.stdout)["ok"])
             git(self.root, "checkout", "-q", "--detach", first)
             result = run_cli(self.root, "team", "deps", "--bead", work)
             self.assertEqual(1, result.returncode)
             self.assertIn(second, result.stdout)
     ```
     The existing `test_deps_closes_placeholders_whose_track_merged` and the `#<N>` tests of `TestTeamBeadsLocal` and `TestTeamDepsWorkspaceChild` stay unchanged and must pass (R9 third bullet).
  2. Write failing tests in `tests/workflow_core/test_goal.py`, in `TestGoalTeam`:
     ```python
     def lane_bead(self, bead: str, name: str, assignee: str = "a@corp.com"):
         return track(bead, assignee=assignee, title=f"Lane {name}: scope",
                      description=f"Plan: p.md, Lane {name}\nLane: {name}")

     def test_only_lane_beads_left_say_to_plan_each_lane(self):
         text = goal_text("epic", [self.lane_bead("e.1", "be"), self.lane_bead("e.2", "fe"), track("e.3", "closed")],
                          "wf", False, member=self.ME)
         self.assertEqual("No goal: lane be has no tracks yet; run /plan for it.\n"
                          "No goal: lane fe has no tracks yet; run /plan for it.", text)
         self.assertEqual("No goal: lane fe has no tracks yet; run /plan for it.",
                          goal_text("epic", [self.lane_bead("e.1", "be"), self.lane_bead("e.2", "fe")], "wf", False,
                                    member=self.ME, lane="fe"))

     def test_a_lane_bead_is_never_a_track_of_the_goal(self):
         tracks = [self.lane_bead("e.1", "be"), track("e.2", assignee=self.ME, description=lane_desc("fe", 2))]
         text = goal_text("epic", tracks, "wf", False, member=self.ME)
         self.assertTrue(text.startswith("/goal tracks e.2 of epic epic"), text)
         self.assertNotIn("e.1", text)

     def test_another_members_lane_bead_gives_the_usual_line(self):
         self.assertEqual("No goal: a@corp.com has no open track in epic epic.",
                          goal_text("epic", [self.lane_bead("e.1", "be", "b@corp.com")], "wf", False, member=self.ME))
     ```
  3. Write failing tests in `tests/workflow_core/test_team_complete.py`, in `TestTeamComplete`:
     ```python
     LANE_PLAN = LOGIN_PLAN.replace(".md", ".lane-be.md")

     def lane_with_track(self, close_lane: bool = True) -> tuple[str, str]:
         lane = create(self.root, "Lane be: login API", parent=self.epic,
                       description=f"Plan: {LOGIN_PLAN}, Lane be\nLane: be")
         track = create(self.root, "Lane track 1", parent=self.epic,
                        description=f"Plan: {self.LANE_PLAN}, Track 1\nLane: be")
         bd(self.root, "close", track)
         if close_lane:
             bd(self.root, "close", lane)
         return lane, track

     def test_a_lane_plan_track_is_delivered_by_a_pull_request_naming_the_lane_plan(self):
         self.lane_with_track()
         self.gh({"argv": ["pr", "list", "--state", "merged"], "stdout": [
             {"url": "https://github.com/org/app/pull/1", "mergeCommit": {"oid": "m" * 40},
              "body": f"Plan: {LOGIN_PLAN}\nTracks: 1, 2\n"},
             {"url": "https://github.com/org/app/pull/3", "mergeCommit": {"oid": "m" * 40},
              "body": f"Plan: {self.LANE_PLAN}\nTracks: 1\n"}]})
         result = run_cli(self.root, "team", "complete", self.epic, env=self.env)
         self.assertEqual(0, result.returncode, result.stdout + result.stderr)
         self.assertIn("merged https://github.com/org/app/pull/3", result.stdout)

     def test_a_lane_plan_track_no_pull_request_lists_keeps_the_epic_open(self):
         _lane, track = self.lane_with_track()
         self.gh(merged_rule("https://github.com/org/app/pull/1", "1, 2"))
         result = run_cli(self.root, "team", "complete", self.epic, env=self.env)
         self.assertEqual(1, result.returncode)
         self.assertIn(f"missing {track} ({self.LANE_PLAN}#1): no merged pull request lists it", result.stdout)

     def test_an_open_lane_bead_keeps_the_epic_open(self):
         lane, _track = self.lane_with_track(close_lane=False)
         self.gh({"argv": ["pr", "list", "--state", "merged"], "stdout": [
             {"url": "https://github.com/org/app/pull/1", "mergeCommit": {"oid": "m" * 40},
              "body": f"Plan: {LOGIN_PLAN}\nTracks: 1, 2\n"},
             {"url": "https://github.com/org/app/pull/3", "mergeCommit": {"oid": "m" * 40},
              "body": f"Plan: {self.LANE_PLAN}\nTracks: 1\n"}]})
         result = run_cli(self.root, "team", "complete", self.epic, env=self.env)
         self.assertEqual(1, result.returncode)
         self.assertIn(f"missing {lane} is open", result.stdout)
     ```
     Only the goal test needs no code change to fail first; the complete tests pass once Track 3's `topic_of` is in (they prove R10's first bullet and US-3 and stay as regression tests).
  4. Run `timeout 1200 python3 -m pytest -n auto tests/workflow_core/test_team_beads.py tests/workflow_core/test_goal.py tests/workflow_core/test_team_complete.py -q -k "DepsLane or GoalTeam or lane"`: the deps and goal tests fail.
  5. In `S/team_beads.py`:
     - Line 20: `_EXTERNAL = re.compile(r"^external: (\S+)#(\d+|lane-[a-z0-9][a-z0-9-]*)$")`.
     - Replace the body of `deps` (lines 747-777) with:
       ```python
       def deps(root: Path, team: TeamConfig) -> dict[str, Any]:
           """Close each open `external: <plan>#<N>` placeholder whose track a merged pull request lists, and each
           `external: <plan>#lane-<name>` placeholder whose lane has no open bead and whose every track merged."""
           from .team_host import merged_with_text

           closed, waiting, unresolved, reasons = [], [], [], {}
           beads: list[dict[str, Any]] | None = None  # every bead, read once for the first lane placeholder
           for issue in _bd_json(root, ["list", "--status", "open"]):
               match = _EXTERNAL.match(issue.get("title", ""))
               if not match:
                   continue
               plan, target = match.group(1), match.group(2)
               try:
                   if target.startswith("lane-"):
                       if beads is None:
                           beads = _bd_json(root, ["list", "--all", "--limit", "0"])
                       prs, repo = _lane_delivered(root, team, plan, target.removeprefix("lane-"), beads)
                   else:
                       repo_dir, repo = _blocking_repo(root, plan, int(target))
                       found = next((pr for pr in merged_with_text(team.host, plan, repo_dir)
                                     if _delivers(pr.body, plan, int(target))), None)
                       prs = [found] if found else []
               except SyncConflict as error:
                   waiting.append(issue["id"])
                   reasons[issue["id"]] = str(error)
                   continue
               if not prs:
                   waiting.append(issue["id"])
                   continue
               without = [pr.url for pr in prs if not pr.merge_commit]
               if without:
                   unresolved.append({"id": issue["id"], "pr": without[0]})
                   continue
               urls = ", ".join(pr.url for pr in prs)
               commits = " ".join(dict.fromkeys(pr.merge_commit for pr in prs))
               noted = _bd(root, ["update", issue["id"], "--set-metadata", f"merge_commit={commits}"]
                           + (["--set-metadata", f"repo={repo}"] if repo else []))
               if noted.returncode != 0:
                   raise TeamError(f"bd update {issue['id']} failed: {noted.stderr.strip()}")
               done = _bd(root, ["close", issue["id"], "--reason", f"{urls} merged ({commits})"])
               if done.returncode != 0:
                   raise TeamError(f"bd close {issue['id']} failed: {done.stderr.strip()}")
               closed.append({"id": issue["id"], "pr": urls})
           return {"closed": closed, "waiting": waiting, "unresolved": unresolved, "reasons": reasons}


       def _lane_delivered(root: Path, team: TeamConfig, plan: str, lane: str,
                           beads: Sequence[Mapping[str, Any]]) -> tuple[list[Any], str | None]:
           """The merged pull requests that list every track of `lane` of the lead plan `plan`, in any of its lane
           plans (empty while a track is not listed), and the `repo` the placeholder records (`.` for the parent of a
           workspace, None outside one). Raises SyncConflict while the lane has no bead, an open bead, or no track."""
           from .team_host import merged_with_text

           rows = [row for row in beads
                   if (found := _lane(row)) is not None and (lead_plan(found[0]), found[2]) == (plan, lane)]
           if not rows:
               raise SyncConflict(f"lane {lane} of {plan} has no bead")
           still_open = [str(row["id"]) for row in rows if row.get("status") != "closed"]
           if still_open:
               raise SyncConflict(f"lane {lane} has open beads: {', '.join(still_open)}")
           tracks = sorted((row for row in rows if not _is_lane_bead(row)), key=lambda row: _lane(row)[1])
           if not tracks:
               raise SyncConflict(f"lane {lane} has no track bead yet")
           repo = (track_of(tracks[0])[2] or ".") if workspace.locate(root).workspace is not None else None
           repo_dir = _track_repo(root, None if repo in (None, ".") else repo)[0]
           merged: dict[str, list[Any]] = {}
           prs: list[Any] = []
           for row in tracks:
               path, number = _lane(row)[0], _lane(row)[1]
               if path not in merged:
                   merged[path] = merged_with_text(team.host, path, repo_dir)
               found = next((pr for pr in merged[path] if _delivers(pr.body, path, number)), None)
               if found is None:
                   return [], repo
               if all(pr.url != found.url for pr in prs):
                   prs.append(found)
           return prs, repo
       ```
     - In `deps_for` (line 816 on), replace `commit = str(metadata.get("merge_commit", ""))` with `commits = str(metadata.get("merge_commit", "")).split()`, `elif not commit:` with `elif not commits:`, and the `try` block with:
       ```python
       try:
           reason = next((found for commit in commits
                          if (found := _reach_reason(root, here, metadata.get("repo") or None, commit, cwd))), "")
       except SyncConflict as error:
           reason = str(error)
       ```
       Docstring: `"""The bead's `external:` placeholders: ok only when closed with each recorded merge commit in this workspace."""`.
  6. In `S/goal.py`:
     - Line 19: `from .team_pending import lane_bead, track_lane`.
     - At the start of `goal_text`, before `found = {...}` (line 36):
       ```python
       planning = {track["id"]: (found_lane[1], track) for track in tracks if track.get("status") != "closed"
                   and (found_lane := lane_bead(str(track.get("description") or ""))) is not None}
       ```
       and add `and track["id"] not in planning` to the condition of `found`.
     - Replace `mine` and `covered` (lines 52-58) with:
       ```python
       def mine(track: dict[str, Any], name: str | None) -> bool:
           assignee = (track.get("assignee") or "").lower()
           return (lane is None or name == lane) and (assignee == member or (lane is not None and not assignee))

       def lane_name(track: dict[str, Any]) -> str | None:
           found_lane = track_lane(str(track.get("description") or ""))
           return found_lane[2] if found_lane else None

       covered = open_tracks if member is None else {bead: t for bead, t in open_tracks.items() if mine(t, lane_name(t))}
       ```
     - Right after `runnable = ...` (line 60), before `if not open_tracks:`:
       ```python
       to_plan = [name for name, track in planning.values() if member is not None and mine(track, name)]
       if member is not None and not covered and to_plan:
           return "\n".join(f"No goal: lane {name} has no tracks yet; run /plan for it." for name in dict.fromkeys(to_plan))
       ```
     - Docstring of `goal_text` adds: "A lane bead (`Plan: <path>, Lane <name>`) is never a track; when the member's only open beads are lane beads, one line per lane says to plan it."
  7. Run `timeout 1200 python3 -m pytest -n auto tests/workflow_core/test_team_beads.py tests/workflow_core/test_goal.py tests/workflow_core/test_team_complete.py -q`: passes.
  8. Commit: `feat(team): deps closes lane placeholders; goal names the lanes left to plan (<bead>)`.
- **Acceptance criteria**: R9 (code part), R10 first bullet, R11; US-3 second criterion; US-4 second criterion; every existing `deps`, `deps --bead`, `complete`, and `goal` test passes unchanged (US-5).
- **Estimated complexity**: high

### Track 6: Skills: lane declarations, lane plans, lane orchestrate, lane ship (R1, R3, R5, R7, R8, R9, R10, R12 skills)
- **Dependencies**: Track 1, Track 2, Track 3, Track 4, Track 5
- **Files**:
  - Modify `plugins/gin-workflow/src/skills/team/references/lanes.md` (whole file below)
  - Modify `plugins/gin-workflow/src/skills/team/SKILL.md:23` (`## plan` paragraph)
  - Modify `plugins/gin-workflow/src/skills/plan/SKILL.md:21` (the `project.team` line of step 5)
  - Modify `plugins/gin-workflow/src/skills/orchestrate/SKILL.md:17` (the `project.team` line of step 1)
  - Test `tests/workflow_core/test_skill_routing.py` (`test_team_branch_model_is_in_the_skills`)
  - Test `tests/workflow_core/test_token_budget.py` (`test_team_guidance_loads_on_demand`)
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** the wording is given below and was measured against the character budgets; the work is exact replacement plus the tests that pin skill text.
- **Budget** (measured on a copy of `plugins/gin-workflow/src` with exactly these edits): team `SKILL.md` 5,884 to 5,991 (limit 6,000); plan chain 11,936 to 11,981; orchestrate chain 8,425 to 8,485; execute 11,816 and ship 11,997 unchanged (limit 12,000). `lanes.md` grows from 3,512 to 7,983 characters and is in no stage chain. `skills/ship/SKILL.md` is not changed: it has 3 characters left, and its `project.team` line already defers to the `team` skill, whose header links `lanes.md`, whose `## Ship` now starts with the lane plan check.
- **Steps**:
  1. Update the pinned tests first.
     - In `tests/workflow_core/test_skill_routing.py`, `test_team_branch_model_is_in_the_skills`: extend the `for needle in (...)` tuple over `lanes` with `"## Lanes"`, `"### Lane <name>"`, `"- TQ-<n> (lane <name>): <question>"`, `"Plan: <plan path>, Lane <name>"`, `"<lead plan stem>.lane-<lane>.md"`, `"Spec: <design doc path>"`, `"gin team check-plan <lane plan>"`, `"external: <plan path>#lane-<name>"`, `"gin routes resolve"`, `"Plan: <lane plan path>, Track <N>"`; and after the loop add:
       ```python
       self.assertIn("leave `(lane <name>)` questions to them", read("skills/team/SKILL.md"))
       for stage in ("plan", "orchestrate"):
           with self.subTest(pointer=stage):
               self.assertIn("`references/lanes.md`", read(f"skills/{stage}/SKILL.md"))
       ```
     - In `tests/workflow_core/test_token_budget.py`, `test_team_guidance_loads_on_demand`: after `team_skill = ...` add `lanes = (SRC / "skills/team/references/lanes.md").resolve()` and inside the loop, after the `assertNotIn(team_skill, ...)`, add `self.assertNotIn(lanes, stage_chain(SRC, stage))`.
     Run `timeout 300 python3 -m pytest tests/workflow_core/test_skill_routing.py tests/workflow_core/test_token_budget.py -q`: the routing test fails; the budget test passes.
  2. Replace the whole of `K/team/references/lanes.md` with:
     ````markdown
     # Lanes

     Read this in team mode. A lane is the tracks of one plan that one member does in one repository. It has one branch `feat/<topic>-<lane>` (`<topic>` is the plan file name without its date and without `.lane-<lane>`), one worktree `.planning/worktrees/<epic>-<lane>`, and one pull request. A track bead without a `Lane:` line was orchestrated before lanes: it is its own lane `t<N>` and keeps `feat/<topic>-t<N>` and `.planning/worktrees/<bead>`. The lead's plan may declare a lane and leave its tracks to the lane's owner, who writes them in a lane plan.

     ## Plan

     - Every track's Metadata has `- **Lane**: <name>`: lowercase letters, digits, and `-`, never `t<digits>`. The area name is the usual choice. The tracks of a lane share `Owner:` and `Repo:`; a lane may span areas its owner may own.
     - Add `## Contracts` before `## Tasks`, with one entry per interface that a track of one lane produces and a track of another lane consumes. An HTTP endpoint lists method, path, request, response, and error codes; anything else lists its exact names and types. The consuming track names the entry in its Interfaces and does not depend on the producing track.
     - A track depends on a track of another lane only when it needs that lane's merged code, such as an end-to-end QA track.
     - A contract entry changed after approval goes through a new plan PR.
     - To leave a lane's tracks to its owner, add `## Lanes` before `## Contracts`, with one `### Lane <name>` per lane:
       ```markdown
       ### Lane be
       - **Owner**: em@corp.com
       - **Area**: backend
       - **Repo**: services/api
       - **Scope**: the login API and its tests
       - **Acceptance criteria**: POST /login answers 200 with a session and 401 on a wrong password
       - **Contracts**: produces `POST /login`
       - **Depends on lanes**: fe
       ```
       Repeat `Area:` per area; `Repo:` only in a workspace; `Depends on lanes:` only when the lane's tracks need another lane's merged code. A track whose `Lane:` names a declared lane has that lane's owner and repository, and the lead plans that lane here. A declared lane without tracks is planned by its owner (Lane plan). A plan with `## Lanes` needs no track.
     - Answer only the technical questions that concern more than one area. Write a question for one lane as `- TQ-<n> (lane <name>): <question>` and leave it open for the lane's owner. `gin record plan-approved` accepts it open when the plan declares the lane, so pass `--plan <path>` with the PR URL; it refuses a question marked for a lane the plan does not declare. With `area_lead`, the lead of each declared lane's area approves the plan PR.

     ## Orchestrate

     - Each track bead gets the label `lane:<lane>` and the line `Lane: <lane>` in its description, after the `Plan:` line.
     - A dependency inside a lane is `gin task dep add <blocked> <blocker>`. For a dependency on a track of another lane, create a bead titled `external: <plan path>#<N>` and make it block the dependent track, with and without `team.beads_sync`. `gin team deps` closes it when a merged PR lists that track.
     - For each declared lane without tracks, create one lane bead under the epic, titled `Lane <name>: <scope>`, with the labels `lane:<name>` and `area:<area>` per area, `--assignee <owner>`, and the description lines `Plan: <plan path>, Lane <name>` and `Lane: <name>` (in a workspace also `Repo: <path>`). It is not a track: it gets no `track:` label and no route.
     - For each name in a lane's `Depends on lanes:`, create one bead titled `external: <plan path>#lane-<name>`, once per named lane. The dependent lane's tracks will depend on it. `gin team deps` closes it when lane `<name>` has no open bead and merged PRs list every track of it.

     ## Lane plan

     - `gin team ready` lists your lane bead. `gin team claim <bead>` claims it with every open track of the lane and creates the lane's worktree. Run `/plan` for the lane in that worktree: record no gate and ask no other member.
     - Write the lane plan next to the lead's plan as `<lead plan stem>.lane-<lane>.md`, with `Spec: <design doc path>` under its title and tracks in the schema of the `plan` skill, numbered from 1. Every track has the lane's `Lane:`, `Owner:`, and `Repo:`, one of its areas as `Area:`, and files inside that area; it uses only the `## Contracts` entries the lane's `Contracts:` names.
     - Ask the user about each `- TQ-<n> (lane <lane>):` question of the design doc as the plan stage does, and write `Decision: <answer>` under it. Leave every other question alone.
     - `gin team check-plan <lane plan>` must exit 0: it checks each track against the lane's declaration in the lead's plan and reports each question marked for the lane without a decision. Then commit the lane plan and the design doc on the lane branch; when the lane's `Repo:` is a workspace child, on the parent's `feat/<topic>` instead. The lead reviews them with the lane's PR.

     ## Lane orchestrate

     - Run `/orchestrate` for the lane plan in the lane worktree. While `gin team check-plan <lane plan>` exits 1, create nothing.
     - Read the epic's children with `gin task list --parent <epic> --all --json`. For each track of the lane plan that has no bead with the line `Plan: <lane plan path>, Track <N>`, create one under the epic with that line and `Lane: <lane>` (in a workspace also `Repo:` and `Reads:`), the labels `track:<N>`, `area:<area>`, and `lane:<lane>`, and `--assignee <owner>`. Add the dependencies between them with `gin task dep add`, and make each track depend on every `external: <lead plan path>#lane-<name>` bead of the lane's `Depends on lanes:`.
     - Write the routes of these tracks only and run `gin routes resolve --workflow-id <epic id> --tracks <file> --json`; it merges them into the workflow's assignment manifest.
     - When every track has its bead, close the lane bead with `gin task close <lane bead> --reason "planned in <lane plan path>: <track bead ids>"`. Record no gate. After a failure, run it again: it creates only the missing beads.

     ## Execute

     - `gin team claim <bead>` claims every open track of the bead's lane and creates or reuses the lane's worktree. It refuses when another member holds an unexpired lease on any of them. Claim again at the start of each track: it renews the lease and marks that track in progress.
     - Run the lane's tracks in dependency order in that worktree. The reviewed diff of a track runs from the lane branch's head when the track started to the track's last commit. After the track closes, `git push -u origin feat/<topic>-<lane>` and go on to the next one.
     - `gin goal --workflow-id <id>` covers the tracks assigned to you; `--lane <name>` picks one lane and also covers its unassigned tracks. It leaves out tracks that need a human or wait for another lane to merge.
     - When the lane's PR has merged and tracks remain, the next `gin team claim` starts the branch again from the default branch. If the host kept the merged branch, delete it on origin before the next push. If the claim reports commits made after the merged PR, merge `origin/<default>` into the branch. Never force-push.

     ## Ship

     - With a lane plan, `gin team check-plan <lane plan>` must exit 0 before the PR: ship stops while a question marked for the lane has no `Decision:`.
     - Deliver the closed tracks of the lane that no merged PR lists yet; each needs its review approved or waived. Open tracks stay for a later PR of the same lane.
     - Fill the generated PR template: `Plan:` with the plan path (the lane plan path for its tracks), `Tracks:` with every delivered track number (`gin team deps` and `gin team complete` read both), `Beads:`, and one line per track under `## Tracks`.
     - A fix the PR reviewer asks for is committed on the lane branch and pushed. With `project.review_ledger: true`, first reopen the last approved track and have it reviewed again.
     - After the merge, when the lane has no open track, run `gin worktree cleanup <epic>-<lane>` from the main checkout (in a workspace, `gin worktree cleanup --repository <repo> <epic>-<lane>` from the parent).
     ````
  3. `K/team/SKILL.md`, one replacement in the `## plan` paragraph (the old text occurs once):
     - Old: ``` `team check-plan <plan>` must exit 0 before asking for approval.```
     - New: ``` `team check-plan <plan>` must exit 0 before asking for approval. A plan may declare lanes their owners plan; leave `(lane <name>)` questions to them (references/lanes.md).```
  4. `K/plan/SKILL.md`, two replacements on the `project.team` line of step 5 (each old text occurs once):
     - Old: ``tracks add `Area:`/`Lane:`/`Owner:`, the plan`` New: ``tracks add `Area:`/`Lane:`/`Owner:` or lanes are declared, the plan``
     - Old: ``after it merges (the `team` skill).`` New: ``after it merges (the `team` skill, `references/lanes.md`).``
  5. `K/orchestrate/SKILL.md`, one replacement (occurs once):
     - Old: ``With `project.team.enabled`, label, assign, link, and sync track beads per the `team` skill.``
     - New: ``With `project.team.enabled`, label, assign, link, and sync track beads per the `team` skill; lane beads and lane plans follow its `references/lanes.md`.``
  6. Measure: `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m workflow_core.budget --report` shows plan 11,981, orchestrate 8,485, execute 11,816, ship 11,997; `wc -m plugins/gin-workflow/src/skills/team/SKILL.md` shows 5991. Run `timeout 600 python3 -m pytest -n auto tests/workflow_core/test_skill_routing.py tests/workflow_core/test_token_budget.py tests/test_no_direct_bd.py tests/workflow_core/test_role_aware_skills.py -q`: passes.
  7. Commit: `docs(team): lane declarations, lane plans, and lane orchestrate in the skills (<bead>)`.
- **Acceptance criteria**: R12's skill part; R5, R7, R8, R9, R10 procedures are in `lanes.md`; the budgets above hold; stage skills keep one `project.team` line and no `` `bd `` token.
- **Estimated complexity**: medium

### Track 7: Reference, guides, and changelog (R12)
- **Dependencies**: Track 6
- **Files**:
  - Modify `docs/reference/cli.md:85` (`record plan-approved`), `:150` (`specs lint`), `:204` (`team check-plan`), `:205` (`team pending`), `:206` (`team ready`), `:207` (`team claim`), `:211` (`team deps`), `:212` (`team complete`), `:360` (`gin goal`)
  - Modify `docs/guides/team.md:96-97,105`
  - Modify `docs/guides/team.vi.md:96-97,105`
  - Modify `docs/changelog.md:7-25` (`## Unreleased`)
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** the insertions are given at anchors that occur once, but each statement must be checked against the code of Tracks 1 to 5 and the Vietnamese page must say what its source says; docs tracks of the previous epic needed review fixes at this route.
- **Steps**: each step inserts text right after the quoted anchor (the anchor stays); every anchor occurs exactly once in its file.
  1. `docs/reference/cli.md`:
     - After ``line under `## Open Technical Questions` without an indented `Decision:` line.`` insert `` An open question marked `- TQ-<n> (lane <name>):` does not refuse it when the plan declares that lane under `## Lanes`; the plan is read from `--plan`, else from `--evidence` when that is a file. Without one it is refused with `questions marked for a lane need the plan file as --plan or --evidence`, and a lane the plan does not declare with `questions marked for a lane the plan does not declare`.``
     - Replace ``(`- TQ-<n>: <question>` lines, unique ids,`` with ``(`- TQ-<n>: <question>` or `- TQ-<n> (lane <name>): <question>` lines, unique ids,``.
     - After ``Track <N>: invalid lane <name>`, `lane <name>: tracks <A> and <B> have different owners`, and `lane <name>: tracks <A> and <B> are in different repositories`.`` insert `` A plan with `## Lanes` needs no track. Each `### Lane <name>` declaration is checked (`lane <name>: missing Owner:`, `invalid lane name`, `declared twice`, `missing Area:`, `unknown area <area>`, `owner <email> is not in team.members`, `owner <email> holds no role allowed in area <area>`, `Depends on lanes: <other> is not a declared lane`), and each track against the lane its `Lane:` names (`Track <N>: lane <lane> is not declared in ## Lanes`, `Owner: <email> is not the owner of lane <lane> (<owner>)`, `Repo: <path> is not the repository of lane <lane> (<repo>)`, `area <area> is not an area of lane <lane>`). A lane plan `<plan stem>.lane-<lane>.md` is checked against its lane's declaration in the plan beside it: `<path>: lead plan <lead> not found`, `<path>: lane <lane> is not declared in <lead>`, `<path>: lane <lane> has tracks in <lead>; the lead plans it there`, `Track <N>: lane <other> is not lane <lane>`, the track findings above, `<path>: missing Spec: <design doc path> line`, `<path>: Spec: <spec> is not a file`, and `<spec>:<line>: TQ-<n> (lane <lane>) has no Decision:` for each open question of the design doc its `Spec:` line names (relative to the top of its git repository) that is marked for the lane.``
     - Replace ``on the `Plan:` line of a track bead, without its date.`` with ``on the `Plan:` line of a track bead, without its date and without `.lane-<lane>`.`` (in the `pending` row).
     - After ``` `lane` is `t<N>` for a bead without a `Lane:` line.``` insert `` A lane bead (`Plan: <plan>, Lane <name>`) is listed with its lane and branch.``
     - After ``with worktree `.planning/worktrees/<bead>` on `feat/<topic>-t<N>`.`` insert `` A lane bead (`Plan: <plan>, Lane <name>`, made by orchestrate for a lane the plan declares without tracks) claims its lane in the same way. The beads of a lane are the epic's children whose plan is the plan or one of its lane plans `<plan stem>.lane-<lane>.md`, with the same lane.``
     - After ``a placeholder with no recorded `repo` is checked against `HEAD` of the current repository`` (end of the `deps` row, before ` |`) insert ``. A placeholder `external: <plan>#lane-<name>` closes when every bead of lane `<name>` of that plan, its lane bead included, is closed and merged PRs list every track of the lane, whichever lane plan names it; it waits with a reason while the lane has no bead, an open bead, or no track bead. It records the merge commit of each of those PRs, separated by spaces, and `--bead` requires each one``.
     - After ``its `Tracks:` line holds the track number.`` insert `` A track of a lane plan is listed by a PR whose `Plan:` line names the lane plan.``
     - After ``waits on a human or on another lane to merge: <beads>.` `` (the closing backtick of that sentence) insert `` A lane bead is no track: when your only open beads in the epic are lane beads, it prints `No goal: lane <name> has no tracks yet; run /plan for it.` for each.``
  2. `docs/guides/team.md`:
     - After ``the filled `03-design.md` sections.`` (end of the `plan` row, before ` |`) insert `` A plan may instead declare lanes under `## Lanes` (owner, areas, repository, scope, acceptance criteria, the contracts each lane produces or consumes, `Depends on lanes:`) and leave their tracks to each owner: `team check-plan` then passes without a track, and with `area_lead` the lead of each declared lane's area approves. The lead answers only the questions that cross areas; a question for one lane is written `- TQ-<n> (lane <name>): <question>`, stays open, and `record plan-approved --plan <path>` accepts it when the plan declares that lane.``
     - After ``and `team claim` creates the worktree.`` (end of the `orchestrate` row) insert `` A declared lane without tracks gets one lane bead `Lane <name>: <scope>` with the line `Plan: <plan>, Lane <name>`, assigned to its owner, and each lane in its `Depends on lanes:` gets an `external: <plan>#lane-<name>` placeholder.``
     - After ``Contracts are approved with the plan ([command](../reference/cli.md#gin-goal)).`` insert a blank line and the paragraph: ``The owner of a lane bead claims it with `gin team claim <bead>` and, in the lane worktree, runs `/plan` for the lane: it writes the lane plan `<plan stem>.lane-<lane>.md` beside the lead's plan, with the lane's tracks and a `Decision:` under each question marked for the lane. `gin team check-plan <lane plan>` checks the lane plan against the lane's declaration and its questions; no gate is recorded, and the lead reviews the lane plan with the lane's pull request. `/orchestrate` for the lane plan then creates the lane's track beads and routes and closes the lane bead. Ship of the lane runs the same check again. Until the lane has tracks, `gin goal` prints `No goal: lane <name> has no tracks yet; run /plan for it.` ([command](../reference/cli.md#gin-team)).``
  3. `docs/guides/team.vi.md`:
     - After ``các phần đã điền của `03-design.md`.`` insert `` Plan cũng có thể khai báo các lane trong `## Lanes` (owner, area, repository, phạm vi, tiêu chí chấp nhận, các contract mà lane tạo ra hoặc dùng, `Depends on lanes:`) và để owner của từng lane viết track của lane đó: khi đó `team check-plan` pass mà không cần track nào, và với `area_lead`, lead của area của từng lane đã khai báo phải duyệt. Lead chỉ trả lời các câu hỏi liên quan tới nhiều area; câu hỏi cho một lane được viết `- TQ-<n> (lane <name>): <question>`, vẫn để mở, và `record plan-approved --plan <path>` chấp nhận nó khi plan khai báo lane đó.``
     - After ``và `team claim` tạo worktree.`` insert `` Mỗi lane đã khai báo mà chưa có track nhận một lane bead `Lane <name>: <scope>` với dòng `Plan: <plan>, Lane <name>`, gán cho owner của lane, và mỗi lane trong `Depends on lanes:` của nó nhận một placeholder `external: <plan>#lane-<name>`.``
     - After ``Contract được duyệt cùng plan ([lệnh](../reference/cli.md#gin-goal)).`` insert a blank line and the paragraph: ``Owner của một lane bead claim nó bằng `gin team claim <bead>` và, trong worktree của lane, chạy `/plan` cho lane: lệnh viết lane plan `<plan stem>.lane-<lane>.md` cạnh plan của lead, gồm các track của lane và một dòng `Decision:` dưới mỗi câu hỏi được đánh dấu cho lane. `gin team check-plan <lane plan>` kiểm tra lane plan theo khai báo của lane và các câu hỏi của nó; không gate nào được ghi, và lead review lane plan cùng pull request của lane. Sau đó `/orchestrate` cho lane plan tạo các track bead và route của lane rồi đóng lane bead. Ship của lane chạy lại cùng phép kiểm tra đó. Khi lane chưa có track, `gin goal` in `No goal: lane <name> has no tracks yet; run /plan for it.` ([lệnh](../reference/cli.md#gin-team)).``
  4. `docs/changelog.md`, under `## Unreleased`:
     - Replace ``instead of a pull request per track.`` (end of the intro sentence) with ``instead of a pull request per track. A team plan may also declare lanes and leave each lane's tracks to its owner, who writes them in a lane plan.``
     - After the `### Added` bullet ``- `gin team ready` rows carry `lane` and `branch`, and the text groups rows under their branch.`` insert:
       ```markdown
       - A team plan may declare lanes under `## Lanes` and leave each lane's tracks to its owner, who writes them in a lane plan `<plan stem>.lane-<lane>.md` with no approval gate. `gin team check-plan` checks the declarations and the lane plan.
       - A technical question for one lane is written `- TQ-<n> (lane <name>): <question>`. `gin record plan-approved` accepts it open when the plan declares the lane, and `gin team check-plan <lane plan>` fails until the lane plan answers it.
       - `gin team deps` closes `external: <plan>#lane-<name>` placeholders once every track of that lane has merged.
       - `gin goal` prints `No goal: lane <name> has no tracks yet; run /plan for it.` when your only open beads are lane beads.
       ```
     - After the `### Changed` bullet ``- `gin team pending` lists one branch per lane with an open track. `gin team deps` and `gin team complete` read the `Tracks:` line of merged pull requests.`` insert:
       ```markdown
       - `gin team claim`, `ready`, `pending`, and `complete` treat a lane bead and the tracks of a lane plan as part of the lane of their lead plan; `<topic>` leaves out `.lane-<lane>`.
       - With `plan_approved: area_lead`, the lead of each declared lane's area approves the plan.
       ```
  5. Run `python3 plugins/gin-workflow/src/scripts/gin docs check docs/reference/cli.md docs/guides/team.md docs/guides/team.vi.md docs/changelog.md`: prints `ok`. Run `timeout 600 python3 -m pytest -n auto tests/workflow_core/test_docs_coverage.py tests/workflow_core/test_docs_check.py -q`: passes.
  6. Commit: `docs(team): lanes planned by their owners in the reference, guides, and changelog (<bead>)`.
- **Acceptance criteria**: R12's documentation part; `gin docs check` prints `ok` on the four pages; the finding and message texts quoted match Tracks 1, 2, 4, and 5 exactly.
- **Estimated complexity**: low

## Integration
- **Branch**: feat/team-lane-plans
- **Merge strategy**: sequential

## Validation
- [ ] `timeout 1800 python3 -m pytest -n auto -q` passes.
- [ ] With `bd` off `PATH`: `BD=$(dirname "$(command -v bd)"); NP=$(echo "$PATH" | tr ':' '\n' | grep -vx "$BD" | paste -sd:); PATH="$NP" timeout 1800 python3 -m pytest -n auto -q` passes (every new class that calls `bd` has the `HAS_BD` guard). `gh` lives in the same directory as `bd` here, so this run also proves no test needs the real `gh`.
- [ ] `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m workflow_core.budget --report` shows every stage at or under 12,000 (plan 11,981, orchestrate 8,485, execute 11,816, ship 11,997), and `wc -m plugins/gin-workflow/src/skills/team/SKILL.md` is at or under 6,000 (5,991).
- [ ] `python3 plugins/gin-workflow/src/scripts/gin docs check docs/reference/cli.md docs/guides/team.md docs/guides/team.vi.md docs/changelog.md` prints `ok`.
- [ ] Manual: in a scratch team repository, write a lead plan with `## Lanes` and no track and run `gin team check-plan` (exit 0); write `<stem>.lane-<lane>.md` with a track in another lane and run `gin team check-plan <lane plan>` (exit 1, `Track <N>: lane <other> is not lane <lane>`).

## Notes
- Parent Bead: `gin-workflow-g9az`. Merge holds apply only to it; each track bead closes when its tests and review pass, which unblocks the next track.
- `<bead>` in each commit message is that track's bead id.
- `<topic>` in the plan text and skills means the plan file name without its date (and without `.lane-<lane>` for a lane plan).
- After ship, reinstall with `./install.sh --platform all` so the installed `gin` and skills carry the change.
- The `PLAN` fixture of `team_fixtures.py` is not changed; new lane plans are built from `LANES`, `MIXED`, and `LANE_PLAN` in the test files, so no existing `PLAN.replace(...)` stops matching.
