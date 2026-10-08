# Plan: PM/BA roadmap, artifact templates, and brownfield onboarding

## Objective
A brownfield team goes from a documented as-is system to a confirmed roadmap of dependent Beads epics (`/roadmap`), picks epics per sprint (`sprint:<name>` label), deepens each with `/discuss <epic-id>`, and every PM/BA artifact comes from a project-overridable template. A walkthrough and an HTML onboarding deck explain the whole process per role.

Spec: `.planning/specs/2026-10-08-pm-ba-roadmap-templates-design.md` (workflow id `pm-ba-roadmap-templates`).

## Global Constraints (from the spec)
- Everything lives inside the `gin-workflow` plugin. No `gin-pm` plugin.
- Non-goals: sprints as objects with dates or capacity; an `artifacts.roadmap` config key; schema validation of template fields; a CLI checker for user stories; CODEOWNERS generation for the roadmap file; changes to `docs/interactive/`.
- `roadmap` is outside the lifecycle state machine and records no gate. Roadmap file: `.planning/roadmap.md` (legacy layout), `docs/roadmap.md` (SDD).
- Never write the roadmap file or Beads before the PM explicitly confirms. Never close or delete an epic. Sync is idempotent.
- Team mode: `team.approvals.roadmap` (role list) gates the roadmap PR through `gin-workflow team check <url> --gate roadmap`; without it, chat confirmation only. Not waivable.
- `/discuss <epic-id>` reuses the epic; without an id, behavior is unchanged.
- Repositories without a roadmap, and `team.approvals` without `roadmap`, behave exactly as today. New templates are additive; project overrides keep winning.
- The presentation covers team mode only (no solo mode) and is built last from verified behavior.

## Model Guidance
- `default_model_class`: `standard_impl`
- `phase_guidance`:
  - `implement`: `standard_impl`
  - `review`: `standard_impl`
  - `docs`: `standard_impl`
- `override_rule`: Track 4 (the `roadmap` skill) uses `high_reasoning`: its rules decide what is written to shared Beads.

## Requirement Analysis
- Problem statement: PM/BA work has no skill (epics and dependencies are created by hand), `/discuss` always creates a new epic, sprints are invisible to `progress`/`report`, legacy specs and user stories have no template, and there is no end-to-end brownfield guide per role.
- Success criteria: every spec requirement maps to a track below; unit tests, docs coverage, token budgets, and the install smoke test pass; a dry run of the walkthrough works in a scratch repository.
- Constraints: stage chains stay within 12 000 characters (`execute` is at 11 166 today), skill descriptions within 4 000 total (3 447 today); stage skills keep exactly one `project.team` line and at most two lines containing `sdd`; every skill appears in `docs/reference/skills.md`.
- Verified facts the plan relies on: `specs template <name>` works in every layout and prefers `.agent-workflow/templates/<name>` (`specs_cli.py:57`, `specs.py:94`); `team check URL --gate GATE` already verifies a PR without recording (`team_cli.py:26`); `bd create --id <prefix>-<anything>` accepts an explicit id with the database prefix (`bd config get issue_prefix`) and rejects another prefix; **`bd create --id` on an existing id replaces that bead and erases its description**, so existing epics are changed only with `bd update`; `bd list --all --json` rows carry `labels` and `parent`, and a child created under a labelled epic inherits its labels.

## Approach Options
### Option 1: Extend gin-workflow (skills, templates, two small code changes)
- Summary: new `roadmap` skill and templates; `team.py`/`schemas.py` accept a `roadmap` approval; `usage report --sprint`; lifecycle skills reuse epics.
- Pros: reuses templates, team checks, Beads; one install.
- Cons: touches several stage skills under tight budgets.

### Option 2: Separate `gin-pm` plugin
- Summary: roadmap skill and templates in a new plugin.
- Pros: isolates PM work.
- Cons: duplicates config, template, and team plumbing; no checker CLI yet to justify it.

### Recommended Approach
- Selected option: Option 1 (confirmed in discuss).
- Reasoning: smallest change that removes the manual steps.

## Scope
- In scope: spec Requirements 1–8.
- Out of scope: the spec's non-goals.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Seven tracks with a dependency chain; only three are independent, below the parallel-worker threshold.
```

## Tasks

### Track 1: Team-mode roadmap approval

**Metadata:**
- Dependencies: none
- Provider role: `backend`
- Reasoning: `medium`
- Model class: `standard_impl`
- Estimated complexity: low

**Files:**
- Modify: `plugins/gin-workflow/src/scripts/workflow_core/schemas.py` (`approvals.properties`, lines 42-50)
- Modify: `plugins/gin-workflow/src/scripts/workflow_core/team.py` (`GATES`, line 12; `resolve_artifact`, lines 292-304)
- Modify: `plugins/gin-workflow/src/skills/team-setup/SKILL.md` (Lead step 1)
- Modify: `docs/reference/config.md` (`### team`, line 122), `docs/guides/team.md` (line 12 and the example at lines 26-29), `docs/reference/cli.md` (`team` table, `check` row)
- Test: `tests/workflow_core/test_team_gates.py` (new class after `TestWaivers`)

**Interfaces:**
- `team.GATES: tuple[str, ...]` gains `"roadmap"`.
- `team.ROADMAP: dict[str, str] = {"legacy": ".planning/roadmap.md", "sdd": "docs/roadmap.md"}`
- `team.resolve_artifact(pr, root, "roadmap", selected) -> str` returns `ROADMAP[layout]` and ignores `selected`.
- CLI: `gin-workflow team check <url> --gate roadmap` (exit 0 ok, 1 rejected, 2 config or host error).

**Steps:**

1. In `tests/workflow_core/test_team_gates.py`, import `TEAM` from `team_fixtures` (extend the existing import line) and add after `class TestWaivers`:

```python
ROADMAP_TEAM = TEAM.format(host="github").replace(
    "    em@corp.com:", "    lan@corp.com: {roles: [pm], login: lan-pm}\n    em@corp.com:").replace(
    "    verification_passed: [qe]\n", "    verification_passed: [qe]\n    roadmap: [pm]\n")
ROADMAP_PATH = ".planning/roadmap.md"


class TestRoadmapApproval(GateCase):
    def setUp(self):
        super().setUp()
        self.root = make_team_repo(Path(self.tmp.name) / "roadmap-repo", team=ROADMAP_TEAM)

    def check(self):
        return run_cli(self.root, "team", "check", PR, "--gate", "roadmap", env=self.env)

    def test_pm_approval_of_a_merged_roadmap_pr_passes_without_recording(self):
        self.gh(gh_pr(author="binh-dev", files=[ROADMAP_PATH], reviews=[("lan-pm", "APPROVED", "c")]))
        result = self.check()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual([], self.events())

    def test_rejections(self):
        cases = [
            (gh_pr(author="binh-dev", files=[ROADMAP_PATH], reviews=[("an-ba", "APPROVED", "c")]),
             "missing approval from one of pm"),
            (gh_pr(author="lan-pm", files=[ROADMAP_PATH], reviews=[("lan-pm", "APPROVED", "c")]),
             "missing approval from one of pm"),
            (gh_pr(author="binh-dev", files=["README.md"], reviews=[("lan-pm", "APPROVED", "c")]),
             f"PR does not change {ROADMAP_PATH}"),
            (gh_pr(state="OPEN", author="binh-dev", files=[ROADMAP_PATH], reviews=[("lan-pm", "APPROVED", "c")]),
             "not merged"),
        ]
        for pr, reason in cases:
            with self.subTest(reason=reason):
                self.gh(pr)
                result = self.check()
                self.assertEqual(1, result.returncode, result.stderr)
                self.assertIn(reason, result.stdout)

    def test_sdd_layout_uses_docs_roadmap(self):
        root = make_team_repo(Path(self.tmp.name) / "sdd-repo", team=ROADMAP_TEAM,
                              extra="artifacts:\n  layout: sdd\n")
        self.gh(gh_pr(author="binh-dev", files=["docs/roadmap.md"], reviews=[("lan-pm", "APPROVED", "c")]))
        result = run_cli(root, "team", "check", PR, "--gate", "roadmap", env=self.env)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_roadmap_role_held_by_no_member_is_a_config_error(self):
        team = TEAM.format(host="github").replace("    verification_passed: [qe]\n",
                                                  "    verification_passed: [qe]\n    roadmap: [pm]\n")
        root = make_team_repo(Path(self.tmp.name) / "no-pm-repo", team=team)
        result = run_cli(root, "team", "check", PR, "--gate", "roadmap", env=self.env)
        self.assertEqual(2, result.returncode)
        self.assertIn("team.approvals.roadmap: role pm is held by no member", result.stderr)
```

2. Run: `PYTHONPATH=plugins/gin-workflow/src/scripts:tests python3 -m unittest tests.workflow_core.test_team_gates </dev/null` → the four new tests fail (schema rejects `roadmap`, and `--gate roadmap` is not a valid choice); the existing tests pass.

3. `schemas.py` `approvals.properties`: add `"roadmap": _ROLES,` after `"verification_passed": _ROLES,`. Keep `"additionalProperties": False`.

4. `team.py`:

```python
GATES = ("requirement_confirmed", "plan_approved", "verification_passed", "roadmap")
ROADMAP = {"legacy": ".planning/roadmap.md", "sdd": "docs/roadmap.md"}
```

and at the top of `resolve_artifact`, before `if selected:`, replace the function body start so it reads:

```python
def resolve_artifact(pr: Any, root: Path, gate: str, selected: str | None) -> str:
    """The spec, plan, or roadmap the gate approves: the selector, else the one candidate the PR changes."""
    from .specs import load_config, sdd_config

    cfg = sdd_config(load_config(Path(root)))
    if gate == "roadmap":
        return ROADMAP[cfg["layout"]]
    if selected:
        return selected
    kind, flag = ("spec", "--spec") if gate == "requirement_confirmed" else ("plan", "--plan")
    changes = str(cfg["changes"]).strip("/")
```

keeping the remaining lines (`candidates = ...` to the end) unchanged. `check_approval` needs no change: a `roadmap` PR takes the merged/artifact/approver branch.

5. Run step 2 again → `OK`. (The role check is `validate_team`, `team.py:89-97`, which iterates every `approvals` key; `configuration.py:221` raises it and `team_cli.main` turns it into exit 2 on stderr.)

6. `team-setup/SKILL.md` Lead step 1: after "`verification_passed` roles," insert "`roadmap` roles (who approves the `/roadmap` PR)," so the approvals list reads "approvals (`requirement_confirmed` roles, `plan_approved: area_lead` or roles, `verification_passed` roles, `roadmap` roles (who approves the `/roadmap` PR), `[]` for none)".

7. Docs:
   - `docs/reference/config.md` line 122: replace "`approvals` (per gate: a role list or `area_lead`)" with "`approvals` (per gate: a role list or `area_lead`; `roadmap` takes a role list and gates the `/roadmap` pull request)".
   - `docs/guides/team.md` line 12: replace "which roles approve `requirement_confirmed` and `verification_passed`," with "which roles approve `requirement_confirmed`, `verification_passed`, and the `/roadmap` pull request (`roadmap`),"; in the example `approvals:` block add `    roadmap: [pm]` after `verification_passed: [qe]` and a member line `    lan@example.com: {roles: [pm], login: lan-pm}` under `members:`.
   - `docs/reference/cli.md` `team` table, `check` row purpose: "Check that a pull request of this repository changes the gate's artifact and satisfies its approvals; `--gate roadmap` checks the roadmap file without recording anything".

8. Run: `PYTHONPATH=plugins/gin-workflow/src/scripts:tests python3 -m unittest tests.workflow_core.test_team_gates tests.workflow_core.test_schema_2_7 tests.workflow_core.test_docs_coverage </dev/null` → `OK`.

9. Commit: `feat(team): gate the roadmap pull request with team.approvals.roadmap`.

**Acceptance criteria:**
- The four new tests pass and the existing team gate and schema tests still pass.
- `gin-workflow record` still accepts only lifecycle gates.
- Independent review approves.

### Track 2: `usage report --sprint`

**Metadata:**
- Dependencies: none
- Provider role: `backend`
- Reasoning: `low`
- Model class: `cheap_simple`
- Estimated complexity: low

**Files:**
- Modify: `plugins/gin-workflow/src/scripts/workflow_core/usage.py` (`report`, lines 281-292)
- Modify: `plugins/gin-workflow/src/scripts/workflow_core/usage_cli.py` (`report` scope group, lines 32-35; `main`, the `usage.report(...)` call)
- Modify: `plugins/gin-workflow/src/skills/report/SKILL.md` (step 1)
- Modify: `docs/reference/cli.md` (`## \`gin-workflow usage\`` synopsis and paragraph)
- Test: `tests/workflow_core/test_usage.py` (`ReportTests`), `tests/workflow_core/test_usage_cli.py`

**Interfaces:**
- `usage.report(repo: Path, *, bead: str | None = None, epic: str | None = None, since: date | None = None, sprint: str | None = None) -> dict[str, Any]`
- CLI: `gin-workflow usage report --sprint NAME`, mutually exclusive with `--bead`, `--epic`, `--since`.

**Steps:**

1. In `ReportTests` (`tests/workflow_core/test_usage.py`), add:

```python
    def test_sprint_report_covers_labelled_epics_and_their_tracks(self):
        rows = self.rows()
        rows[0]["labels"] = ["roadmap", "sprint:s1"]
        rows.append({"id": "ep2", "title": "Next", "issue_type": "epic", "status": "open",
                     "labels": ["sprint:s2"]})
        self.rules[0]["stdout"] = rows
        fake_cli(self.bin, "bd", self.rules)
        out = usage.report(self.repo, sprint="s1")
        self.assertEqual(["ep1", "ep1.1"], [row["bead"] for row in out["beads"]])
        self.assertEqual(["ep1.2"], out["not_collected"])
        self.assertEqual(3.0, out["totals"]["cost"])
        self.assertEqual([], usage.report(self.repo, sprint="none")["beads"])
```

2. In `tests/workflow_core/test_usage_cli.py` `test_report_scope_flags_are_exclusive_and_since_is_a_date`, add:

```python
        done = run_cli(self.repo, "usage", "report", "--sprint", "s1", "--epic", "e1", env=self.env)
        self.assertEqual(done.returncode, 2)
```

3. Run: `PYTHONPATH=plugins/gin-workflow/src/scripts:tests python3 -m unittest tests.workflow_core.test_usage tests.workflow_core.test_usage_cli </dev/null` → `report() got an unexpected keyword argument 'sprint'`, and the CLI test fails (`--sprint` unknown exits 2 for the wrong reason; it passes only after step 5, so check the stderr says `not allowed with argument`).

4. `usage.py` `report`: add `sprint: str | None = None` to the signature and, after the `elif epic:` branch:

```python
    elif sprint:
        epics = {row["id"] for row in rows if row.get("issue_type") == "epic"
                 and f"sprint:{sprint}" in (row.get("labels") or ())}
        selected = [row for row in rows if row.get("id") in epics or row.get("parent") in epics]
```

5. `usage_cli.py`: add `scope.add_argument("--sprint")` after `--since`, and pass `sprint=args.sprint` to `usage.report(...)`.

6. Run step 3 again → `OK`; add an assertion in the CLI test that `"not allowed with argument"` is in `done.stderr`.

7. `report/SKILL.md` step 1: after "an epic and its tracks (`--epic <id>`)," insert "a sprint's epics and their tracks (`--sprint <name>`, epics labelled `sprint:<name>`),".

8. `docs/reference/cli.md`: synopsis becomes `gin-workflow usage report [--bead ID | --epic ID | --sprint NAME | --since YYYY-MM-DD]`; append to the paragraph: "`--sprint NAME` covers the epics labelled `sprint:NAME` and their tracks."

9. Run: `PYTHONPATH=plugins/gin-workflow/src/scripts:tests python3 -m unittest tests.workflow_core.test_usage tests.workflow_core.test_usage_cli tests.workflow_core.test_docs_coverage </dev/null` → `OK`.

10. Commit: `feat(usage): report a sprint's epics with --sprint`.

**Acceptance criteria:**
- Sprint report covers only epics with the exact `sprint:<name>` label and their child tracks; scope flags stay exclusive.
- Independent review approves.

### Track 3: PM/BA templates and the template rule

**Metadata:**
- Dependencies: none
- Provider role: `docs`
- Reasoning: `low`
- Model class: `cheap_simple`
- Estimated complexity: low

**Files:**
- Create: `plugins/gin-workflow/src/templates/roadmap.md`, `epic.md`, `user-story.md`, `design-spec.md`
- Modify: `plugins/gin-workflow/src/templates/proposal.md`
- Modify: `plugins/gin-workflow/src/references/stage-contract.md` (`## Context`)
- Test: `tests/workflow_core/test_specs.py` (`TestSpecsCli`)

**Interfaces:**
- Template names `roadmap.md`, `epic.md`, `user-story.md`, `design-spec.md`, fetched with `gin-workflow specs template <name>`; placeholders use `{{key}}` as rendered by `specs.render`.

**Steps:**

1. In `TestSpecsCli` add:

```python
    def test_pm_and_ba_templates_ship_and_can_be_overridden(self):
        with tempfile.TemporaryDirectory() as directory:
            root = make_repo(Path(directory), layout="legacy")
            for name in ("roadmap.md", "epic.md", "user-story.md", "design-spec.md"):
                with self.subTest(name=name):
                    self.assertEqual(0, run_specs(root, "template", name).returncode)
            self.assertIn("## User Stories", run_specs(root, "template", "design-spec.md").stdout)
            self.assertIn("## User Stories", run_specs(root, "template", "proposal.md").stdout)
            self.assertIn("Depends on:", run_specs(root, "template", "roadmap.md").stdout)
            write(root, ".agent-workflow/templates/user-story.md", "### Story {{n}}\n")
            self.assertEqual("### Story {{n}}\n", run_specs(root, "template", "user-story.md").stdout)
```

2. Run: `PYTHONPATH=plugins/gin-workflow/src/scripts:tests python3 -m unittest tests.workflow_core.test_specs </dev/null` → the new test fails with `unknown template: roadmap.md`.

3. Create `templates/roadmap.md`:

~~~markdown
# Roadmap: {{title}}

Date: {{date}}
Source: {{source}}

<!-- Written by /roadmap after the PM confirms it. One "### " block per epic; an epic id never changes once written.
     Depends on: epic ids from this file. Evidence: the tech-doc file and section (for example
     ARCHITECTURE.md#Request flow) or the product brief. The dependency graph stays acyclic. -->

## Goals

## Constraints

## Strategy

## Order

```mermaid
flowchart LR
```

## Epics

### {{epic_title}}
Epic: {{epic_id}}
Goal:
Scope:
Out of scope:
Depends on:
Evidence:
Risks:
~~~

4. Create `templates/epic.md`:

```markdown
<!-- Description of a roadmap epic in Beads; /discuss <epic-id> starts from it. -->
{{goal}}

Scope: {{scope}}
Out of scope: {{out_of_scope}}
Evidence: {{evidence}}
Roadmap: {{roadmap}}
```

5. Create `templates/user-story.md`:

```markdown
<!-- One block per story under "## User Stories". REQ: the REQ-IDs that deliver the story
     (SDD layout only; drop the line otherwise). One observable outcome per acceptance bullet. -->
### US-{{n}}: {{title}}
As a {{role}}, I want {{goal}}, so that {{benefit}}.
REQ: {{reqs}}

Acceptance criteria:
-
```

6. Create `templates/design-spec.md`:

```markdown
# {{title}}

Epic: {{epic}}
Status: draft for user review.

<!-- Written by /discuss with the legacy layout. Drop the Epic line when there is none.
     User Stories come from `gin-workflow specs template user-story.md`. -->

## Goal and scope

## Requirements

## User Stories

## Errors and compatibility

## Testing
```

7. `templates/proposal.md`: insert `## User Stories` (followed by a blank line) between `## What Changes` and `## Capabilities Affected`.

8. `stage-contract.md` `## Context`: append the sentence "Build an artifact from `gin-workflow specs template <name>` when one exists; never invent its structure."

9. Run step 2 again plus `tests.workflow_core.test_token_budget` → `OK`.

10. Commit: `feat(templates): roadmap, epic, user story, and design spec templates`.

**Acceptance criteria:**
- The four templates ship, `proposal.md` has `## User Stories`, overrides win, and every stage chain stays within budget.
- Independent review approves.

### Track 4: `roadmap` skill

**Metadata:**
- Dependencies: Track 1, Track 3
- Provider role: `general`
- Reasoning: `high`
- Model class: `high_reasoning`
- Estimated complexity: medium

**Files:**
- Create: `plugins/gin-workflow/src/skills/roadmap/SKILL.md`
- Modify: `docs/reference/skills.md` (the table with `team-setup` … `tech-doc`, after the `tech-doc` row)
- Modify: `tests/install_smoke_test.sh` (after the `tech-doc` assertions, lines 142 and 177-179)

**Interfaces:**
- Skill `gin-workflow:roadmap`; consumes `team check --gate roadmap` (Track 1) and the `roadmap.md`/`epic.md` templates (Track 3).

**Steps:**

1. `tests/install_smoke_test.sh`: after `assert_exists "plugins/gin-workflow/dist/claude-code/skills/tech-doc/SKILL.md"` add `assert_exists "plugins/gin-workflow/dist/claude-code/skills/roadmap/SKILL.md"`; after the `tech-doc` `assert_contains` lines add:

```bash
assert_contains "plugins/gin-workflow/dist/claude-code/skills/roadmap/SKILL.md" "every file of the tech-doc folder"
assert_contains "plugins/gin-workflow/dist/claude-code/skills/roadmap/SKILL.md" "never close or delete"
assert_contains "plugins/gin-workflow/dist/claude-code/skills/roadmap/SKILL.md" "Never \`bd create --id\` an existing id"
```

2. Run: `bash tests/install_smoke_test.sh </dev/null` → fails on the missing `roadmap/SKILL.md`; `test_docs_coverage` still passes (the skill does not exist yet).

3. Create `skills/roadmap/SKILL.md`:

~~~markdown
---
name: roadmap
description: Turn the tech-doc set or a product brief into a confirmed roadmap file and dependent Beads epics; reconcile both on re-run.
---

# Roadmap

On `/roadmap` only. Outside the lifecycle: it records no gate. One question per message. Never write the roadmap file or touch Beads before the PM explicitly confirms the roadmap.

## Before you start
1. If `.agent-workflow/generated/effective-config.yaml` does not exist in the main checkout (the parent of `git rev-parse --path-format=absolute --git-common-dir`), stop: tell the user to run `/setup` once and do nothing else.
2. `gin-workflow state --format json` gives `project.stage` and `project.layout`. The roadmap file is `.planning/roadmap.md`, or `docs/roadmap.md` with `project.layout: sdd`.
3. `brownfield` or `legacy` needs the tech-doc folder (`.planning/codebase/`, or `artifacts.codebase`, default `docs/codebase/`, with the SDD layout); if it is missing, stop and recommend `/tech-doc`. `greenfield` needs a product brief: ask for a path or the text.

## Steps
1. **Read** every file of the tech-doc folder, subsystem subfolders included, yourself (no subagent summaries: epic dependencies come from reading across files), or the product brief; then living specs (or `.planning/specs/`), the roadmap file if it exists, and `bd list --label roadmap --all --json`. With `.codegraph/`, check load-bearing claims with `codegraph explore`.
2. **Clarify** with the PM: business goals, milestones, team capacity, operating constraints (downtime, data migration), exclusions.
3. **Propose 2–3 ways to split the work** (for example by bounded context, by risk, by business value) with trade-offs; lead with your recommendation.
4. **Present the roadmap**. Each epic: title, `Epic: <id>`, `Goal:`, `Scope:`, `Out of scope:`, `Depends on:` (epic ids), `Evidence:` (tech-doc file and section, or the brief), `Risks:`. A new id is `<prefix>-rm-<slug>` (`bd config get issue_prefix`; slug of lowercase letters, digits, and hyphens) and never changes once written. Check that dependencies are acyclic. On a re-run, present only what differs from the file and Beads. Revise until the PM explicitly confirms.
5. **Write** the file from `gin-workflow specs template roadmap.md` on branch `roadmap/<topic>` and commit. When `team.approvals.roadmap` in `.agent-workflow/config.yaml` lists roles: push, ask approval, open the pull request, and return `awaiting_roadmap_review`. On the next run, `gin-workflow team check <pr-url> --gate roadmap`: exit 0 continues with the merged file; exit 1 shows the reasons and stops. Never work around a rejection.
6. **Sync Beads** for each epic in the file, after `bd show <id> --json`:
   - missing: `bd create --id <id> --type epic --labels roadmap -d "<description>" "<title>"`;
   - existing: `bd update <id> --title "<title>" -d "<description>"`. Never `bd create --id` an existing id: it replaces the bead and erases its description;
   - the description comes from `gin-workflow specs template epic.md`;
   - dependencies: `bd dep add <epic> <dependency>` for each `Depends on:` id; `bd dep remove <epic> <dependency>` for a roadmap dependency the file no longer lists (`bd dep list <epic> --json`);
   - an epic that is `in_progress` or closed: warn and leave its title, description, and dependencies unchanged;
   - an epic labelled `roadmap` that the file no longer lists: report it and ask; never close or delete an epic;
   - a failing `bd` call: stop and report which epics were synced; a re-run continues from there.
7. **Sprint** (when asked): `bd update <epic> --add-label sprint:<name>` for each chosen epic.
8. **Report**: the roadmap path, epics created and updated, dependency changes, `bd ready` epics, and the next step `/discuss <epic-id>`.
~~~

4. `docs/reference/skills.md`: after the `tech-doc` row add `| \`roadmap\` | Turn the tech-doc set or a product brief into a confirmed roadmap and dependent Beads epics; reconcile both on re-run |`.

5. Run: `./install.sh --platform all </dev/null`, then `bash tests/install_smoke_test.sh </dev/null` → exit 0; `PYTHONPATH=plugins/gin-workflow/src/scripts:tests python3 -m unittest tests.workflow_core.test_docs_coverage tests.workflow_core.test_token_budget tests.workflow_providers.test_harness_packaging </dev/null` → `OK` (descriptions stay under 4 000).

6. Manual check in a scratch repository (`mktemp -d`, `git init`, `bd init --prefix demo`): `bd create --id demo-rm-billing --type epic --labels roadmap -d "d" "Billing"`, then `bd update demo-rm-billing --title "Billing v2" -d "d2"`, `bd show demo-rm-billing --json` keeps the `roadmap` label and shows `d2`; `bd dep add`/`bd dep remove` between two such epics round-trips. Record the commands and output in the bead notes.

7. Commit: `feat(roadmap): add the roadmap skill for PM epics and dependencies`.

**Acceptance criteria:**
- The skill matches spec Requirement 1; smoke, docs-coverage, budget, and packaging checks pass; the manual Beads round-trip behaves as written.
- Independent review approves.

### Track 5: Epic reuse, user stories, and sprints in lifecycle skills

**Metadata:**
- Dependencies: Track 2, Track 3
- Provider role: `general`
- Reasoning: `medium`
- Model class: `standard_impl`
- Estimated complexity: medium

**Files:**
- Modify: `plugins/gin-workflow/src/skills/discuss/SKILL.md` (intro paragraph, steps 5-6)
- Modify: `plugins/gin-workflow/src/skills/gin-sdd/SKILL.md` (`## discuss` steps 1-2)
- Modify: `plugins/gin-workflow/src/skills/orchestrate/SKILL.md` (step 1)
- Modify: `plugins/gin-workflow/src/skills/execute/SKILL.md` (`## 1. Select and review` step 1)
- Modify: `plugins/gin-workflow/src/skills/progress/SKILL.md` (step 1)
- Modify: `tests/install_smoke_test.sh`

**Interfaces:**
- `/discuss <epic-id>`; spec header `Epic: <id>` (legacy layout) read by `orchestrate`.

**Steps:**

1. `tests/install_smoke_test.sh`, after the Track 4 assertions:

```bash
assert_contains "plugins/gin-workflow/dist/claude-code/skills/discuss/SKILL.md" "/discuss <epic-id>"
assert_contains "plugins/gin-workflow/dist/claude-code/skills/orchestrate/SKILL.md" "create no other epic"
assert_contains "plugins/gin-workflow/dist/claude-code/skills/execute/SKILL.md" "labelled \`roadmap\`"
assert_contains "plugins/gin-workflow/dist/claude-code/skills/progress/SKILL.md" "sprint:<name>"
```

Run `./install.sh --platform all </dev/null && bash tests/install_smoke_test.sh </dev/null` → fails on the first new assertion.

2. `discuss/SKILL.md`, after the paragraph ending "never ask them to run `bd` during discovery.", add:

```markdown
**Roadmap epic:** `/discuss <epic-id>` starts from `bd show <id> --json` and its roadmap entry. Stop if the id is missing, not an epic, or closed; warn if its dependencies are still open. Pass `--workflow-id <epic-id>` to every `state` and `record` call and never create another epic.
```

3. `discuss/SKILL.md` step 5: replace "Write the spec to `.planning/specs/YYYY-MM-DD-<topic>-design.md`." with "Write the spec to `.planning/specs/YYYY-MM-DD-<topic>-design.md` from `gin-workflow specs template design-spec.md` (`Epic: <id>` for a roadmap epic), with user stories from `specs template user-story.md`." Do not add a line containing `sdd` or `project.team`.

4. `discuss/SKILL.md` step 6: append "Every user story has acceptance criteria and, with REQ-IDs, at least one `REQ:`; every new REQ has a story or a stated technical reason."

5. `gin-sdd/SKILL.md` `## discuss` step 1: replace "After the user confirms the design: `bd create --type epic --title "<title>"` →" with "After the user confirms the design: `bd create --type epic --title "<title>"` (a roadmap epic is reused as is) →". Step 2: after "Write `proposal.md`, `spec-delta.md`, and `design.md` in that folder." insert " `proposal.md` lists `## User Stories` from `specs template user-story.md`, each with `REQ:`."

6. `orchestrate/SKILL.md` step 1: after "read the plan from `.planning/plans/`." insert " When the spec names `Epic: <id>` (a roadmap epic), use it as the parent and create no other epic."

7. `execute/SKILL.md` step 1: append " A bead labelled `roadmap` is an epic awaiting `/discuss <epic-id>`: never record it as its own epic."

8. `progress/SKILL.md` step 1: append " For a sprint: `bd list --label sprint:<name> --all --json`, grouped by epic."

9. Run: `./install.sh --platform all </dev/null && bash tests/install_smoke_test.sh </dev/null` → exit 0; `PYTHONPATH=plugins/gin-workflow/src/scripts:tests python3 -m unittest tests.workflow_core.test_token_budget tests.workflow_providers.test_harness_packaging </dev/null` → `OK` (`execute` chain under 12 000; `test_sdd_guidance_loads_on_demand` and `test_team_guidance_loads_on_demand` unchanged).

10. Commit: `feat(lifecycle): reuse roadmap epics in discuss and orchestrate, sprint progress`.

**Acceptance criteria:**
- Spec Requirements 3, 4, and the `progress` part of 5 are reflected in the skills; budgets and smoke tests pass.
- Independent review approves.

### Track 6: Brownfield walkthrough and starter docs

**Metadata:**
- Dependencies: Track 4, Track 5
- Provider role: `docs`
- Reasoning: `medium`
- Model class: `standard_impl`
- Estimated complexity: medium

**Files:**
- Create: `docs/starters/brownfield-walkthrough.md`
- Modify: `docs/starters/team-roles.md` (matrix in section 1; new PM section before `## 2. The BA`; Next Steps)
- Modify: `docs/starters/brownfield-modernize.md` (section 2 end; `## 7. Next Steps`), `docs/starters/greenfield.md` (`## 5. Next Steps`), `README.md` (Starters row)

**Steps:**

1. Write `docs/starters/brownfield-walkthrough.md` with these sections, in order:
   - `# Brownfield Walkthrough: From Legacy Code to Sprint Delivery` and a two-sentence intro.
   - `## The scenario`: a legacy PHP ordering system (orders, payments, inventory) being modernized; team PM Lan (`pm`), BA An (`ba`), Tech Lead Binh (`be_lead`), Dev Em (`be_dev`), QE Chi (`qe`); the `team:` YAML with these members, areas `legacy_core` (`legacy/**`) and `modern_api` (`src/**`, `tests/**`), and approvals `requirement_confirmed: [ba]`, `plan_approved: area_lead`, `verification_passed: [qe]`, `roadmap: [pm]`.
   - `## The flow at a glance`: a Mermaid `flowchart LR` setup → tech-doc → roadmap → sprint label → discuss → plan → orchestrate → cases → execute → e2e → verify → ship → progress/report, with the role on each node.
   - One `##` section per stage, each with **Who**, **Prompt** (fenced, copyable), **You get** (files, beads, PRs), **Gate or approval**, **Common mistakes**. Stages and prompts:
     1. Setup (Tech Lead): `/gin-workflow:setup` then `/gin-workflow:team-setup`.
     2. Survey (Tech Lead): `/gin-workflow:tech-doc whole repository`.
     3. Roadmap (PM): `/gin-workflow:roadmap Goal: move payments and inventory out of the monolith within two quarters without downtime.` → `.planning/roadmap.md`, PR approved by `pm`, epics `<prefix>-rm-*` with dependencies.
     4. Sprint planning (PM): `/gin-workflow:roadmap Label demo-rm-payments and demo-rm-orders-api for sprint 2026-s1.`
     5. Discuss (BA): `/gin-workflow:discuss demo-rm-payments` → spec with user stories, spec PR approved by `ba`.
     6. Plan and orchestrate (Tech Lead): `/gin-workflow:plan`, `/gin-workflow:orchestrate`.
     7. Test cases (QE): `/gin-qa:cases payments`.
     8. Execute (Dev): `gin-workflow team ready`, `gin-workflow team claim <bead>`, `/gin-workflow:execute`.
     9. E2E and verify (QE): `/gin-qa:e2e payments`, approve the PR, `/gin-workflow:verify`.
     10. Ship and sprint review (Tech Lead, PM): `/gin-workflow:ship`, `/gin-workflow:progress sprint 2026-s1`, `/gin-workflow:report --sprint 2026-s1`.
   - `## Customizing outputs`: the template table (roadmap, epic, user story, design spec, proposal) with `.agent-workflow/templates/<name>` overrides, a full example override of `user-story.md` (adds a `Priority:` line and Vietnamese headings), and the QE `qa/guidelines.md` example (language, extra fields).
   - `## Solo variant`: the same flow for one person: no `team-setup`, no PRs for gates (chat confirmation), `bd ready` instead of `team ready`.
2. `team-roles.md`: add a **PM** row first in the matrix (`/roadmap`, `/progress`, `/report`; `.planning/roadmap.md` or `docs/roadmap.md`; `roadmap/<topic>`; roadmap approval), retitle to "Team Roles Guide: PM, BA, Dev & Tester", add `## 2. The PM (Product Manager) Workflow` (roadmap, sprint labels, sprint report) and renumber later sections; link the walkthrough in Next Steps.
3. `brownfield-modernize.md`: at the end of section 2 add "Next, turn the baseline into a roadmap of epics with `/gin-workflow:roadmap` (see the [Brownfield Walkthrough](brownfield-walkthrough.md))."; add the walkthrough to Next Steps. `greenfield.md` Next Steps: "**Planning several epics?** Start from a product brief with `/gin-workflow:roadmap`." `README.md` Starters row: add `[brownfield walkthrough](docs/starters/brownfield-walkthrough.md)`.
4. Dry run in a scratch repository (`mktemp -d`; `git init`; `bd init --prefix demo`; copy a minimal `.planning/codebase/` with `OVERVIEW.md`, `ARCHITECTURE.md`, `CONCERNS.md`; `/gin-workflow:setup`): run the roadmap stage prompt and `/gin-workflow:discuss <epic-id>` far enough to confirm the epic is reused (no new epic in `bd list --type epic`). Fix any walkthrough step that does not match what happened; record the result in the bead notes.
5. Run: `PYTHONPATH=plugins/gin-workflow/src/scripts:tests python3 -m unittest tests.workflow_core.test_docs_coverage tests.workflow_providers.test_harness_packaging </dev/null` → `OK` (links resolve, Mermaid typed).
6. Commit: `docs(starters): brownfield walkthrough with prompts per role`.

**Acceptance criteria:**
- Every stage has a copyable prompt and matches the dry run; docs checks pass.
- Independent review approves.

### Track 7: Onboarding presentation

**Metadata:**
- Dependencies: Track 6
- Provider role: `frontend`
- Reasoning: `medium`
- Model class: `standard_impl`
- Estimated complexity: medium

**Files:**
- Create: `docs/presentations/brownfield-onboarding.html`
- Modify: `docs/starters/brownfield-walkthrough.md` (link to the deck in the intro)

**Steps:**

1. Ask the user the slide language (Vietnamese or English) before writing.
2. Build one self-contained HTML file (inline CSS, JS, and SVG; no network requests), keyboard and click navigation, a slide counter, readable at phone width, light and dark themes via CSS custom properties. Content comes only from the walkthrough and the merged skills; team mode only, no solo slides. Slides:
   1. Title.
   2. Why gin-workflow: the problems it removes (unclear requirements, unreviewed AI code, lost traceability, invisible cost).
   3. Lifecycle at a glance: SVG diagram tech-doc → roadmap → discuss → plan → orchestrate → execute → verify → ship.
   4. Advantages, one card each with its mechanism: evidence-backed gates, role-based PR approvals, story → REQ → test case → test traceability, isolated worktrees, independent review, sprint cost and quality reports, overridable templates.
   5. Team map: SVG swimlanes PM, BA, Tech Lead, Dev, QE across the stages, with the gate each approves.
   6–10. One slide per role (PM, BA, Tech Lead, Dev, QE): commands, one example prompt, outputs, owned gate.
   11. A sprint in practice: roadmap epic → sprint label → discuss → tracks → ship → sprint report.
   12. Customizing outputs: `.agent-workflow/templates/` overrides for roadmap, epic, user story, design spec; `qa/guidelines.md` for QE; one before/after example.
   13. Day-one checklist for a new brownfield project.
3. Open it in a browser (the `run` skill or a local file URL) and check every slide at desktop and phone width in both themes.
4. Publish it as a private artifact (load the `artifact-design` skill first) and give the user the link; commit only the HTML file.
5. Run: `PYTHONPATH=plugins/gin-workflow/src/scripts:tests python3 -m unittest tests.workflow_core.test_docs_coverage </dev/null` → `OK`.
6. Commit: `docs(presentations): brownfield onboarding deck`.

**Acceptance criteria:**
- Every slide is backed by a merged feature; diagrams read in both themes; no external requests; the user has the artifact link.
- Independent review approves.

## Integration
- **Branch**: `feat/pm-ba-roadmap-templates`
- **Merge strategy**: sequential

## Validation
- [ ] `PYTHONPATH=plugins/gin-workflow/src/scripts timeout 600 python3 -m unittest tests/test_all.py </dev/null` → `OK (skipped=3)` (baseline on master: `OK (skipped=3)`)
- [ ] `bash tests/install_smoke_test.sh </dev/null` → exit 0
- [ ] Manual: Track 4 Beads round-trip and Track 6 dry run recorded in bead notes
- [ ] Manual: `gin-workflow team check <url> --gate roadmap` on a test repository rejects a PR without `pm` approval

## Notes
- Model guidance is planning metadata, not Beads state. Concrete providers and models are resolved at orchestration.
- The parent bead stays open until the human-confirmed merge; track beads close after tests and review pass.
- Tracks 1, 2, and 3 are independent and may run in any order; Track 4 needs 1 and 3, Track 5 needs 2 and 3, Track 6 needs 4 and 5, Track 7 needs 6.
- Track 2 changes code, so its review runs at `medium` whatever tier it declares.
