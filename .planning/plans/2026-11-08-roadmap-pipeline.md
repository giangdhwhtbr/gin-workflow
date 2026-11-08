# Plan: Roadmap delivery pipeline: way of working, integration point, spec readiness warning

Spec: `.planning/specs/2026-11-08-roadmap-pipeline-design.md` (Epic: gin-workflow-roadmap-pipeline, confirmed 2026-11-08).

## Objective

`/gin:roadmap` proposes the team's way of working from `team.members` and the tech-doc set, sequences epics by spec readiness and real data needs, and writes `Spec ready by:` and an `Integration point:` block into every milestone; `gin milestone show` reports `spec_confirmed` per epic and warns `spec_not_ready` when an open epic sits in a kicked-off milestone without a confirmed spec. Older roadmap files and gin-console keep working.

## Architecture

- `plugins/gin-workflow/src/scripts/workflow_core/milestone.py` stays pure: `schedule`, `show_payload`, `list_payload` gain a `confirmed: frozenset[str] | None` parameter; rows gain `spec_confirmed`; the warning block gains `spec_not_ready`.
- `plugins/gin-workflow/src/scripts/workflow_core/milestone_cli.py` reads `.agent-workflow/runtime/events.jsonl` of the main checkout through `WorkflowEventStore` and passes the confirmed workflow ids down.
- `plugins/gin-workflow/src/skills/roadmap/references/way-of-working.md` holds the default pattern and the integration-point rule; `SKILL.md` points to it and stays under 12,000 characters.
- Template and docs follow.

## Tech Stack

Python 3 standard library, `unittest` run with `python3 -m pytest -n auto`; Beads `bd` 1.0.5 for the CLI tests (skipped when `bd` is missing); Markdown skill and docs.

## Global Constraints

Copied from the spec:

- "The integration point lives in the roadmap file only (user decision 2026-11-08); a milestone metadata date with an `after_integration` warning is a possible later epic."
- "Out of scope: Lanes, deadline, and forecast (shipped by `gin-workflow-57fw`). Starter-guide prompts and the brownfield guide (`gin-workflow-docs-refresh`). Integration date as milestone metadata and an `after_integration` schedule warning. Creating BA spec tasks or beads for the spec-ahead cadence; specs still come from `/discuss <epic>`. gin-console rendering of `spec_not_ready` and `spec_confirmed` (noted on `gin-console-cl0`)."
- "`SKILL.md`, under 12,000 characters, anchor phrases kept (`warn and leave its title, description, and dependencies unchanged`, `7. **Report**` with `[gin roadmap]`)."
- "read by the skill on demand (it is not part of the roadmap chain, so it has no budget; keep it under 6,000 characters)."
- "`schema` stays 1; `spec_confirmed` and `spec_not_ready` are additions."
- Repository rules: commit on `feat/roadmap-pipeline` only; `gin rules --files <paths>` before editing.

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

- Problem statement: the roadmap skill waits for the PM to describe how a multi-role team works, has no integration point per milestone, and nothing tells the PM that an epic entered a kicked-off milestone without a confirmed spec.
- Success criteria: spec US-1..US-5; template has the new section and lines; `SKILL.md` under 12,000 characters with the anchors; `show --json` rows carry `spec_confirmed`; `spec_not_ready` fires only for open epics in `scheduled`/`active` milestones without a `requirement.confirmed` event; unreadable event log degrades to a stderr warning and exit 0; docs updated; all tests pass.
- Constraints: Global Constraints above.
- Non-goals: see the out-of-scope list.

## Approach Options

### Option 1: Reference file plus a terse skill, confirmed ids passed into the pure scheduler
- Summary: the pattern text lives in `references/way-of-working.md`; `SKILL.md` adds short pointers inside existing steps (no renumbering); the CLI reads the event log once and passes a frozenset to `milestone.py`.
- Pros: keeps the skill under budget and the anchors intact; `milestone.py` stays pure and testable without files; one event-log read per command.
- Cons: the skill reads one more file on `/roadmap`.

### Option 2: Everything inline in `SKILL.md`, scheduler reads the event log itself
- Summary: write the pattern into the skill steps and let `milestone.py` open `events.jsonl`.
- Pros: one file to read for the skill.
- Cons: `SKILL.md` would pass 12,000 characters and renumber the anchored steps; `milestone.py` would lose its pure contract and its tests would need a filesystem.

### Recommended Approach
- Selected option: Option 1.
- Rationale: the budget and the test anchors force it, and it follows the `execute` skill's `references/` precedent and the `default_lanes`/`roadmap` parameters added by `gin-workflow-57fw`.

## Scope
- In scope: spec R1–R5 inside this repository.
- Out of scope: see Global Constraints.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Three small tracks; track 3 documents what tracks 1 and 2 build, and the full-suite evidence run after each track takes four minutes, so parallel workers would only add merge noise.
```

## Tasks

### Track 1: Spec readiness in `gin milestone`
- **Dependencies**: none
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/milestone.py:155-199` (`schedule`, `show_payload`) and `:254-283` (`list_payload`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/milestone_cli.py:1-20` (imports), `:120-135` (new `_confirmed` helper next to `_roadmap`), `:321-338` (`_run`)
  - Test `tests/workflow_core/test_milestone.py` (`test_req_011_show_payload_shape`, new `SpecReadinessTests`)
  - Test `tests/workflow_core/test_milestone_cli.py` (`test_req_011_show_exact_payload`, new tests)
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** bounded change with the exact code below; the only judgement is the degraded path on an unreadable log.
- **Acceptance criteria**: `test_milestone.py` and `test_milestone_cli.py` pass; `gin milestone show <id> --json` rows carry `spec_confirmed`; `spec_not_ready` appears only for open epics in `scheduled`/`active` milestones without a `requirement.confirmed` event; an unreadable `events.jsonl` prints one stderr warning and exits 0.
- **Estimated complexity**: medium

Interfaces produced:
- `schedule(milestone, beads, start, today, default_lanes: int = 1, confirmed: frozenset[str] | None = None) -> dict` (rows add `"spec_confirmed": bool | None`; warning `{"code": "spec_not_ready"}`)
- `show_payload(milestone, beads, start, today, default_lanes: int = 1, confirmed: frozenset[str] | None = None) -> dict`
- `list_payload(beads, today, include_closed, roadmap=None, default_lanes=1, confirmed: frozenset[str] | None = None) -> dict`
- `milestone_cli._confirmed(root: Path) -> frozenset[str] | None`

Steps:

1. Pure tests first. In `tests/workflow_core/test_milestone.py`, in `test_req_011_show_payload_shape`, add `"spec_confirmed": None,` to the epic row dict after `"estimate_days": 5,`. Add a class:
   ```python
   class SpecReadinessTests(unittest.TestCase):
       def rows_with(self, beads, confirmed, **kwargs):
           milestone_id = kwargs.pop("milestone_id", "m1")
           return rows(milestone.schedule(beads[milestone_id], beads, D("2026-11-02"), TODAY, 1, confirmed))

       def test_spec_confirmed_true_false_and_unknown(self):
           beads = world(milestone_bead(), bead("A", parent="m1", minutes=days(1)), bead("B", parent="m1", minutes=days(1)))
           found = self.rows_with(beads, frozenset({"A"}))
           self.assertEqual((True, False), (found["A"]["spec_confirmed"], found["B"]["spec_confirmed"]))
           self.assertIsNone(self.rows_with(beads, None)["A"]["spec_confirmed"])

       def test_spec_not_ready_only_after_kickoff(self):
           planned = world(milestone_bead(), bead("A", parent="m1", minutes=days(1)))
           self.assertNotIn({"code": "spec_not_ready"}, self.rows_with(planned, frozenset())["A"]["warnings"])
           scheduled = world(milestone_bead(kickoff="2026-11-09"), bead("A", parent="m1", minutes=days(1)))
           self.assertIn({"code": "spec_not_ready"}, self.rows_with(scheduled, frozenset())["A"]["warnings"])
           active = world(milestone_bead(start="2026-10-01", kickoff="2026-10-01"), bead("A", parent="m1", minutes=days(1)))
           self.assertIn({"code": "spec_not_ready"}, self.rows_with(active, frozenset())["A"]["warnings"])
           self.assertNotIn({"code": "spec_not_ready"}, self.rows_with(active, frozenset({"A"}))["A"]["warnings"])

       def test_closed_epic_and_unknown_log_never_warn(self):
           beads = world(milestone_bead(kickoff="2026-11-09"), bead("A", parent="m1", minutes=days(1), status="closed"),
                         bead("B", parent="m1", minutes=days(1)))
           found = self.rows_with(beads, frozenset())
           self.assertNotIn({"code": "spec_not_ready"}, found["A"]["warnings"])
           self.assertIn({"code": "spec_not_ready"}, found["B"]["warnings"])
           self.assertNotIn({"code": "spec_not_ready"}, self.rows_with(beads, None)["B"]["warnings"])

       def test_list_counts_spec_not_ready(self):
           beads = world(milestone_bead(kickoff="2026-11-09"), bead("A", parent="m1", minutes=days(1)))
           payload = milestone.list_payload(beads, TODAY, False, None, 1, frozenset())
           self.assertEqual(1, payload["milestones"][0]["warnings"])
           self.assertEqual(0, milestone.list_payload(beads, TODAY, False)["milestones"][0]["warnings"])
   ```
   Run `python3 -m pytest tests/workflow_core/test_milestone.py -q -p no:cacheprovider`: the new tests fail (`TypeError`), the shape test fails on the missing key.
2. In `milestone.py`:
   - `schedule` signature becomes `def schedule(milestone, beads, start, today, default_lanes: int = 1, confirmed: frozenset[str] | None = None) -> dict[str, Any]:`. After `active = status(milestone, today) == "active"` add `kicked_off = status(milestone, today) in ("scheduled", "active")`. In the warning block, after the `external_blocker` check, add:
     ```python
             if confirmed is not None and kicked_off and epic.get("status") != "closed" and epic_id not in confirmed:
                 warnings.append({"code": "spec_not_ready"})
     ```
     In the row dict add `"spec_confirmed": None if confirmed is None else epic_id in confirmed,` right after `"estimate_days": days,`.
   - `show_payload` gains `confirmed: frozenset[str] | None = None` after `default_lanes` and passes it as the last argument of `schedule(...)`.
   - `list_payload` gains `confirmed: frozenset[str] | None = None` after `default_lanes` and passes it to its `schedule(...)` call. `forecast` is untouched.
   Run the pure tests: pass.
3. CLI tests. In `tests/workflow_core/test_milestone_cli.py`, in `test_req_011_show_exact_payload`, add `"spec_confirmed": False,` after `"estimate_days": 3,` and after `"estimate_days": 2,` (the temp repo has no event log, so nothing is confirmed; t-m1 has no kickoff, so no warning changes). Add the import `from workflow_core.events import WorkflowEvent, WorkflowEventStore` next to the existing `from workflow_core import milestone_cli, team_beads` import, and these tests:
   ```python
   def events_path(self):
       path = self.root / ".agent-workflow/runtime/events.jsonl"
       path.parent.mkdir(parents=True, exist_ok=True)
       return path

   def confirm_spec(self, epic):
       WorkflowEventStore(self.events_path()).append(WorkflowEvent(
           event_id=f"evt-{epic}", event_type="requirement.confirmed", workflow_id=epic,
           timestamp="2026-10-20T00:00:00Z", payload={"evidence": f".planning/specs/{epic}.md"}, actor="t"))

   def test_spec_not_ready_after_kickoff_unless_confirmed(self):
       self.seed()
       self.confirm_spec("t-a")
       self.bd("update", "t-m1", "--set-metadata", "kickoff=2026-11-02")
       code, out, err = self.run_cli("show", "t-m1", "--json")
       self.assertEqual(0, code, err)
       rows = {row["id"]: row for row in json.loads(out)["epics"]}
       self.assertEqual((True, False), (rows["t-a"]["spec_confirmed"], rows["t-b"]["spec_confirmed"]))
       self.assertNotIn({"code": "spec_not_ready"}, rows["t-a"]["warnings"])
       self.assertIn({"code": "spec_not_ready"}, rows["t-b"]["warnings"])
       code, out, _ = self.run_cli("list", "--json")
       self.assertEqual(2, json.loads(out)["milestones"][0]["warnings"])

   def test_unreadable_event_log_degrades_with_a_warning(self):
       self.seed()
       self.events_path().write_text("{not json\n", encoding="utf-8")
       code, out, err = self.run_cli("show", "t-m1", "--json")
       self.assertEqual(0, code, err)
       self.assertIn("warning: event log unreadable:", err)
       self.assertIn("spec readiness unknown", err)
       self.assertTrue(all(row["spec_confirmed"] is None for row in json.loads(out)["epics"]))
   ```
   In the first test the `list` warning count is 2: t-b's existing `overflow` plus `spec_not_ready`. If `WorkflowEvent` requires another field, add it with a literal value and keep the asserts. Run `timeout 200 python3 -m pytest tests/workflow_core/test_milestone_cli.py -q -p no:cacheprovider -k "spec or exact"`: the new tests fail.
4. In `milestone_cli.py`, add the import `from .checkout import main_checkout` with the relative imports, and after `_roadmap`:
   ```python
   def _confirmed(root: Path) -> frozenset[str] | None:
       """Workflow ids with a `requirement.confirmed` event; None, with a stderr warning, when the log is unreadable."""
       from .events import EventPersistenceError, WorkflowEventStore

       path = main_checkout(root) / ".agent-workflow" / "runtime" / "events.jsonl"
       try:
           events = WorkflowEventStore(path).read_all()
       except (EventPersistenceError, OSError, ValueError) as error:
           print(f"warning: event log unreadable: {error}; spec readiness unknown", file=sys.stderr)
           return None
       return frozenset(event.workflow_id for event in events if event.event_type == "requirement.confirmed")
   ```
   In `_run`: for `list`, `payload = core.list_payload(_beads(root), _today(), args.all, roadmap, _default_lanes(config, roadmap), _confirmed(root))`; for `show`, pass `_confirmed(root)` as the last argument of `core.show_payload(...)`. `WorkflowEventStore.read_all` returns `[]` for a missing file (events.py:248-252), so a missing log means nothing is confirmed.
5. Run `timeout 400 python3 -m pytest tests/workflow_core/test_milestone_cli.py -q -p no:cacheprovider` in the background and `python3 -m pytest tests/workflow_core/test_milestone.py tests/workflow_core/test_roadmap_file.py -q -p no:cacheprovider`: all pass. Commit: `feat(milestone): spec_confirmed per epic and spec_not_ready after kickoff (gin-workflow-roadmap-pipeline)`.

### Track 2: Template, reference file, roadmap skill
- **Dependencies**: none
- **Files**:
  - Modify `plugins/gin-workflow/src/templates/roadmap.md:6-13,17-24,30-31`
  - Create `plugins/gin-workflow/src/skills/roadmap/references/way-of-working.md`
  - Modify `plugins/gin-workflow/src/skills/roadmap/SKILL.md:17-18,25-26,39`
  - Test `tests/workflow_core/test_specs.py:291` (template assertions)
  - Test `tests/workflow_core/test_token_budget.py` (new `test_roadmap_skill_within_12000`)
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** prose edits with a hard character budget and tested anchor lines; the reference text is given in full below but must be fitted and checked.
- **Acceptance criteria**: `gin specs template roadmap.md` prints `## Way of working`, `Spec ready by:`, `Integration point:`; `wc -c SKILL.md` under 12,000 and `wc -c references/way-of-working.md` under 6,000; `test_specs.py`, `test_epic_comments.py`, `test_skill_routing.py`, `test_token_budget.py` pass.
- **Estimated complexity**: medium

Steps:

1. Tests first. In `tests/workflow_core/test_specs.py`, after the `- Deadline:` assertion add:
   ```python
            self.assertIn("## Way of working", run_specs(root, "template", "roadmap.md").stdout)
            self.assertIn("Spec ready by:", run_specs(root, "template", "roadmap.md").stdout)
            self.assertIn("Integration point:", run_specs(root, "template", "roadmap.md").stdout)
   ```
   In `tests/workflow_core/test_token_budget.py`, in `TestBudgetLimits`, add:
   ```python
    def test_roadmap_skill_within_12000(self):
        skill = SRC / "skills/roadmap/SKILL.md"
        self.assertLessEqual(len(skill.read_text(encoding="utf-8")), 12_000)
        reference = SRC / "skills/roadmap/references/way-of-working.md"
        self.assertLessEqual(len(reference.read_text(encoding="utf-8")), 6_000)
   ```
   Run `python3 -m pytest tests/workflow_core/test_specs.py tests/workflow_core/test_token_budget.py -q -p no:cacheprovider -k "template or roadmap_skill"`: fails (template lines missing, reference file missing).
2. Template `plugins/gin-workflow/src/templates/roadmap.md`:
   - Header comment: after the `gin milestone list reads two Constraints lines ...` sentence add `## Way of working is written by a plain /roadmap from the skill's references/way-of-working.md and kept on re-runs; Spec ready by: and Integration point: are written by /roadmap --milestone. Older files without them stay valid.`
   - After the `- Deadline:` line and a blank line, before `## Strategy`, insert:
     ```
     ## Way of working

     - Foundation:
     - Spec cadence:
     - Build:
     - Integration:
     - Quality:
     - Load:

     ```
   - Right after `## Milestone: {{milestone_title}}` insert:
     ```
     Spec ready by: {{spec_ready_by}}
     Integration point: {{integration_date}}
     - Integrates:
     - Flags on:
     - E2E scope:
     - Exit criteria:
     ```
     followed by a blank line before `### {{epic_title}}`.
   Run the template test: passes.
3. Create `plugins/gin-workflow/src/skills/roadmap/references/way-of-working.md`:
   ```markdown
   # Way of working: default pattern for a multi-role team

   Read on `/roadmap`. Tailor each block to the team roles and the tech-doc set, present it with trade-offs, and write the confirmed text under `## Way of working` in the roadmap file. Keep a confirmed section on re-runs unless the PM asks for a change.

   ## Foundation
   First milestone, 2 weeks by default, shorter when the tech-doc set shows the pieces exist: CI/CD, environments, auth, feature flags, app shell, contract convention (OpenAPI first), and onboarding: each member sets up the environment, learns the tools and the gin skills (gin-workflow, gin-qa, gin-ba) on one small capability. Feature epics depend on the foundation epics they need.

   ## Spec cadence
   The BA confirms the specs of milestone N+1 during milestone N. `Spec ready by:` of a milestone is its kickoff date, else its start date. At kickoff, `gin milestone show <id>` warns `spec_not_ready` for an open epic without a confirmed spec; name those epics and the BA work due before kickoff.

   ## Build
   Contract first: the OpenAPI contract of a capability is agreed before BE and FE start, then both build in parallel. FE runs against mocks generated from the contract (MSW handlers from orval, for example); for a migration the first FE target is a 1-1 copy of the legacy UI. Sequence capabilities by spec readiness and by real API or data needs only; keep `Depends on:` minimal.

   ## Integration
   One feature flag per capability, controlled by the backend: `GET /api/feature-flags` lists them and the backend also guards the endpoints of an off feature. A gate handler per capability passes requests to the real API when its flag is on and falls through to the mock when off. The FE renders a `MOCK` watermark on a capability served by mocks (from the flags state, or an `X-Mock` header the mock handlers add) and removes it once the capability calls the real backend. Capabilities that share data (a cart referencing catalog ids) share a flag or integrate together. CI runs a contract-diff check; production builds carry no mocks. The integration point of a milestone is the working day at 75% of its working days from `start`, rounded down: the flags listed under `Flags on:` are turned on that day.

   ## Quality
   QA writes the E2E suite against the mocked UI during the build and reruns the same suite against the real API after the flip. QA closes each epic inside its own milestone; the days after the integration point are hardening days. `Exit criteria:` of a milestone: E2E green against the real API for every flag turned on, watermark gone, no open bug bead on the integrated epics.

   ## Load
   Team mode: group the roles of `team.members` (`.agent-workflow/config.yaml`) by the first token before `_` (`be_dev` and `be_lead` are BE; `fe_*` is FE; `qa` and `qe` are QA; `ba`, `sa`, `devops`, `pm` stand alone), print the grouping for the PM to correct, and bound each milestone by the scarcest group that the adopted epics need. Without team mode, bound by the lanes (`AI capacity:` or `--lanes`). Never ask the team composition.

   ## Milestone block
   ```
   Spec ready by: <kickoff, else start>
   Integration point: <date>
   - Integrates: <adopted epic ids>
   - Flags on: <one flag per capability, or one shared flag for capabilities that share data>
   - E2E scope: <the user flows those flags expose>
   - Exit criteria: <see Quality>
   ```
   ```
   Check `wc -c plugins/gin-workflow/src/skills/roadmap/references/way-of-working.md` is under 6,000 (expected about 3,400).
4. `SKILL.md` edits (apply exactly; keep every other character):
   - Line 17 (`--milestone` step 2) ends with `...gin milestone update <id> --lanes <n>\`.`; append: ` Bound adoption by the scarcest role group or the lanes, per the Load block of [way of working](references/way-of-working.md).`
   - Line 18 (adoption), replace `stop when the sum of estimates reaches the lanes times the working days` with `stop when the sum of estimates reaches the bound of step 2 (role group or lanes) times the working days`.
   - Line 19 (`--milestone` step 4), replace `the file groups epics under \`## Milestone: <title>\`, with \`Milestone: <id>\` and \`Estimate: <days>\` per epic.` with `the file groups epics under \`## Milestone: <title>\`, opened by \`Spec ready by:\` and the \`Integration point:\` block of the reference's Milestone block, with \`Milestone: <id>\` and \`Estimate: <days>\` per epic. Name each adopted epic whose \`spec_confirmed\` is false in \`gin milestone show <id> --json\`.`
   - Line 25 (Steps 2 Clarify): replace `business goals, milestones, team capacity, operating constraints (downtime, data migration), exclusions.` with `business goals, deadline, fixed constraints (downtime, data migration), non-goals, cutover. Never ask the team composition: team mode reads \`team.members\`, otherwise the lanes apply.`
   - Line 26 (Steps 3): replace the whole line with `3. **Propose 2–3 ways to split the work** (for example by bounded context, by risk, by business value) with trade-offs, sequenced by spec readiness and by real API or data needs only, with minimal dependencies and the foundation epics first when the project lacks CI/CD, environments, auth, flags, shell, or a contract convention; lead with your recommendation. Then propose the way of working from [way of working](references/way-of-working.md), tailored to the team and the tech-doc set, and revise until the PM confirms; on a re-run keep the confirmed \`## Way of working\` unless the PM asks for a change.`
   - Line 28 (Steps 5 Write): after `keeps \`Estimate:\`, and puts its epics under \`## Unassigned\`.` insert ` Step 5 writes the confirmed way of working under \`## Way of working\`.`
   - Line 39 (`7. **Report**`): after `unestimated count; overflow is reported, never blocks),` insert ` the \`spec_not_ready\` warnings of \`gin milestone show\` when the milestone has a kickoff,`.
   Run `wc -c plugins/gin-workflow/src/skills/roadmap/SKILL.md` (expected about 11,700; if over 12,000, shorten the new sentences, never the anchored lines) and `python3 -m pytest tests/workflow_core/test_specs.py tests/workflow_core/test_epic_comments.py tests/workflow_core/test_skill_routing.py tests/workflow_core/test_token_budget.py -q -p no:cacheprovider`: passes. Also `gin specs template roadmap.md | grep -c "Way of working"` prints 1.
5. Commit: `feat(roadmap): way of working reference, integration point and spec-ready lines, skill steps (gin-workflow-roadmap-pipeline)`.

### Track 3: Documentation
- **Dependencies**: Track 1, Track 2
- **Files**:
  - Modify `docs/reference/cli.md:211` (the `gin milestone` prose paragraph)
  - Modify `docs/guides/customizing-templates.md:127` and `docs/guides/customizing-templates.vi.md:127` (paragraph after the Deadline/AI capacity paragraph)
  - Modify `docs/reference/skills.md:49`, `docs/reference/skills.vi.md:49` (roadmap row)
  - Modify `docs/concepts/lifecycle.md:23`
- **Provider role**: `docs`
- **Model:** `haiku`
- **Effort:** `low`
- **Why:** exact sentences given below, inserted at named anchors; the Vietnamese mirrors translate the same sentences.
- **Acceptance criteria**: `gin docs check <file>` prints `ok` for each touched page; the sentences match the code of Track 1 and the skill of Track 2; full suite passes.
- **Estimated complexity**: low

Steps:

1. `docs/reference/cli.md`, in the paragraph starting `Dated milestones over roadmap epics`: in the `show` sentence replace `(\`overflow\`, \`late\`, \`unestimated\`, \`external_blocker\`)` with `(\`overflow\`, \`late\`, \`unestimated\`, \`external_blocker\`, \`spec_not_ready\`)`. After the sentence ending `set \`--lanes\` or the \`AI capacity:\` number to match the team.` insert: `Each epic row carries \`spec_confirmed\`: whether a \`requirement.confirmed\` event for the epic exists in \`.agent-workflow/runtime/events.jsonl\` of the main checkout. An open epic without one in a \`scheduled\` or \`active\` milestone gets \`spec_not_ready\`. An unreadable event log prints \`warning: event log unreadable: ...; spec readiness unknown\` on stderr, sets \`spec_confirmed\` to null, and the command still exits 0.` In the `--json` sentence, extend the additive keys list: `\`lanes\` (per milestone and on \`show\`), \`spec_confirmed\` (per epic on \`show\`), and \`forecast\` (...)`.
2. `docs/guides/customizing-templates.md`, after the paragraph at line 127, add: `The template's \`## Way of working\` section (Foundation, Spec cadence, Build, Integration, Quality, Load) is filled by a plain \`/gin:roadmap\` from the skill's \`references/way-of-working.md\` and kept on re-runs. Each \`## Milestone:\` block opens with \`Spec ready by:\` and an \`Integration point:\` block (Integrates, Flags on, E2E scope, Exit criteria) that \`/gin:roadmap --milestone\` writes. A roadmap without these lines stays valid.` Add the same paragraph in Vietnamese to `customizing-templates.vi.md` after its line 127 (code spans and file names verbatim).
3. `docs/reference/skills.md:49`: after `reconcile both on re-run;` insert `propose the team's way of working (foundation, spec-ahead cadence, flags and mocks, integration point, QA close) for the PM to confirm;` and after `plans a dated milestone with its own lanes` append `, spec deadline, and integration point`. Translate the same additions into the Vietnamese row of `skills.vi.md:49`.
4. `docs/concepts/lifecycle.md:23`: replace `It writes the project deadline and an estimate per epic and reports the forecast;` with `It proposes the way of working, writes the project deadline and an estimate per epic, and reports the forecast;` and replace `on its own lanes;` with `on its own lanes with a spec deadline and an integration point;`.
5. Run `gin docs check docs/reference/cli.md docs/guides/customizing-templates.md docs/guides/customizing-templates.vi.md docs/reference/skills.md docs/reference/skills.vi.md docs/concepts/lifecycle.md` (each `ok`) and `python3 -m pytest -n auto -q`. Commit: `docs(roadmap): way of working, integration point, spec_not_ready (gin-workflow-roadmap-pipeline)`.

## Integration
- **Branch**: `feat/roadmap-pipeline` (worktree `.claude/worktrees/feat-roadmap-pipeline`)
- **Merge strategy**: sequential

## Validation
- [ ] `python3 -m pytest -n auto` passes
- [ ] `gin specs template roadmap.md` prints `## Way of working`, `Spec ready by:`, `Integration point:`
- [ ] `wc -c plugins/gin-workflow/src/skills/roadmap/SKILL.md` under 12000; `references/way-of-working.md` under 6000
- [ ] `plugins/gin-workflow/src/scripts/gin milestone show gin-workflow-96sx --json` rows carry `spec_confirmed` (true for `gin-workflow-roadmap-pipeline` after this spec's gate) and exit 0
- [ ] Manual: corrupt a copy of `events.jsonl` in a scratch repo and see the stderr warning with exit 0

## Notes
- `Model:` and `Effort:` come from the main harness catalog (`haiku`, `sonnet`, `opus`; `low`..`max`) by the route rubric.
- Parent bead `gin-workflow-roadmap-pipeline` stays open until the user confirms the merge; track beads close when their tests and review pass.
- gin-console follow-up (label for `spec_not_ready`, `spec_confirmed` column) is a note for `gin-console-cl0`, added at ship.
