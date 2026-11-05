# Plan: Capability placement for requirements and assets

Epic: gin-workflow-7xy4
Spec: `.planning/specs/2026-11-05-ba-capability-placement-design.md`

## Objective
With the SDD layout, every epic names its capabilities from the roadmap on, discuss presents a capabilities table (capability, requirement groups, asset paths) that the user confirms before any `REQ-<CAP>-<NNN>` exists, and one documented rule says where a feature's UI requirements and its assets go. Skill text, templates, docs, and tests only; no code or config change.

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
- Problem statement: `gin-sdd` discuss step 2 calls `specs next-id <cap>` without presenting the capability; no stage proposes a capability list; nothing says where UI requirements or input assets belong. gin-console ended with the Reports UI in `ui` and its mockup in `reports/assets/`.
- Success criteria: `roadmap.md` and `epic.md` templates print `Capabilities:`; `/roadmap` step 4 names it per epic; `gin-sdd` discuss presents a capabilities table before `specs new`, states the `ui` rule, and records capability, REQ-IDs, and asset paths in `## Capabilities Affected`; `docs/guides/sdd.md` (en, vi) and `docs/reference/skills.md` (en, vi) describe both; budgets hold.
- Constraints (Global Constraints, from the spec): SDD layout only; no CLI command or config key; `skills/gin-*/SKILL.md` within 6,000 characters (`gin-sdd` is 3,428); `discuss` within the 12,000-character stage budget (8,411 today); `specs archive` keeps maintaining `docs/specs/README.md` (`specs_archive.py:87-91`); names match `[a-z][a-z0-9-]*`.
- Non-goals: diagrams in specs (`gin-workflow-ycg8`), SRS export (`gin-workflow-bel0`), a lint for the placement rule, changes to `/migrate-specs` or the legacy layout, the gin-console follow-up.

## Approach Options
### Option 1: Skill text and templates (recommended)
- Summary: add the `Capabilities:` field to the roadmap skill and templates, the capabilities step and the rule to `gin-sdd` discuss, and describe both in the docs; assert the text in tests.
- Pros: matches how the SDD stages are specified today (skill text asserted by tests); no new surface; the README index is already code-maintained.
- Cons: the rule is a convention, not enforced by `specs lint`.

### Option 2: Config key `artifacts.ui_capability` plus a lint rule
- Summary: store the rule in config and make `specs lint --change` reject UI requirements outside the configured capability.
- Pros: enforced.
- Cons: lint cannot tell a UI requirement from an API one without tagging every block; schema, setup, docs, and tests change for a rule the user has already fixed as the default. Rejected at discuss.

### Recommended Approach
- Selected option: Option 1.
- Rationale: the user confirmed a fixed default rule with a README override; the gap is that no stage presents the choice, which text fixes.

## Scope
- In scope: `skills/roadmap/SKILL.md` steps 4 and 6; templates `roadmap.md`, `epic.md`; `skills/gin-sdd/SKILL.md` discuss section; `docs/guides/sdd.md`, `docs/guides/sdd.vi.md`, `docs/reference/skills.md`, `docs/reference/skills.vi.md`; tests in `tests/workflow_core/test_specs.py` and `tests/workflow_core/test_skill_routing.py`.
- Out of scope: everything under Non-goals; `dist/` (rebuilt by `install.sh`, untracked).

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Both tracks edit tests/workflow_core/test_skill_routing.py and share the docs style checks; one at a time avoids a merge of the same test file.
```

## Tasks
### Track 1: Roadmap names each epic's capabilities
- **Dependencies**: none
- **Files**:
  - Modify `plugins/gin-workflow/src/skills/roadmap/SKILL.md:27` (step 4 field list) and `:29-33` (step 6 description note)
  - Modify `plugins/gin-workflow/src/templates/roadmap.md:34-35` (add `Capabilities:` after `Scope:`)
  - Modify `plugins/gin-workflow/src/templates/epic.md:5` (add `Capabilities: {{capabilities}}` after `Out of scope:`)
  - Modify `docs/reference/skills.md:49`, `docs/reference/skills.vi.md:49` (roadmap row)
  - Test `tests/workflow_core/test_specs.py:231` (template assertions)
  - Test `tests/workflow_core/test_skill_routing.py` (new test)
- **Provider role**: `docs`
- **Model:** `haiku`
- **Effort:** `low`
- **Why:** mechanical insertions of given text into skill, templates, and docs; the plan gives the exact wording and the tests.
- **Acceptance criteria**:
  - `gin-workflow specs template roadmap.md` and `gin-workflow specs template epic.md` print a `Capabilities:` line.
  - `skills/roadmap/SKILL.md` step 4 lists `Capabilities:` with its sources and the `(new)` marker, and omits it for the legacy layout.
  - `docs/reference/skills.md` and `skills.vi.md` roadmap rows name `Capabilities:`.
  - `python3 -m pytest -q tests/workflow_core/test_specs.py tests/workflow_core/test_skill_routing.py tests/workflow_core/test_token_budget.py` passes; `gin-workflow docs check docs/reference/skills.md docs/reference/skills.vi.md` prints `ok` twice.
- **Estimated complexity**: low

Steps:
1. Failing tests. In `tests/workflow_core/test_specs.py` after line 231 (`self.assertIn("Depends on:", ...)`), add:
   ```python
            self.assertIn("Capabilities:", run_specs(root, "template", "roadmap.md").stdout)
            self.assertIn("Capabilities: {{capabilities}}", run_specs(root, "template", "epic.md").stdout)
   ```
   In `tests/workflow_core/test_skill_routing.py`, after `test_discuss_and_plan_use_confirmed_glossary_terms`, add:
   ```python
    def test_roadmap_names_capabilities_per_epic(self):
        text = (SRC / "skills/roadmap/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("`Capabilities:`", text)
        self.assertIn("`(new)`", text)
        self.assertIn("02-FEATURES.md", text)
        self.assertLess(text.index("`Capabilities:`"), text.index("5. **Write**"))
   ```
   Run `python3 -m pytest -q tests/workflow_core/test_specs.py tests/workflow_core/test_skill_routing.py -k "templates or capabilities"`: 2 failed.
2. Templates. `plugins/gin-workflow/src/templates/roadmap.md`: after the line `Scope:` (line 34) insert `Capabilities:`. `plugins/gin-workflow/src/templates/epic.md`: after `Out of scope: {{out_of_scope}}` insert `Capabilities: {{capabilities}}`.
3. Roadmap skill step 4 (line 27). Replace `` `Scope:`, `Out of scope:`, `Depends on:` (epic ids), `` with:
   ```
   `Scope:`, `Out of scope:`, `Capabilities:` (with `project.layout: sdd`: the capabilities its requirements go to, as `[a-z][a-z0-9-]*` names taken from `docs/specs/README.md`, else from the Feature Catalog of `02-FEATURES.md`, else from the brief; a name without a folder under `artifacts.specs` is marked `(new)`; omitted with the legacy layout), `Depends on:` (epic ids),
   ```
   Step 6, the bullet `the description comes from `gin-workflow specs template epic.md`;` becomes `the description comes from `gin-workflow specs template epic.md`, `Capabilities:` copied from the file;`.
4. Docs. `docs/reference/skills.md:49`: after `reconcile both on re-run;` insert ` with the SDD layout each epic carries `Capabilities:`;`. `docs/reference/skills.vi.md:49`: after `đối chiếu cả hai khi chạy lại;` insert ` với layout SDD mỗi epic mang dòng `Capabilities:`;`.
5. Run the tests of step 1 (pass), then `python3 -m pytest -q tests/workflow_core/test_specs.py tests/workflow_core/test_skill_routing.py tests/workflow_core/test_token_budget.py` (all pass) and `gin-workflow docs check docs/reference/skills.md docs/reference/skills.vi.md` (`ok`). Commit: `feat(roadmap): name each epic's capabilities (gin-workflow-7xy4)`.

### Track 2: Discuss confirms capabilities before REQ-IDs
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-workflow/src/skills/gin-sdd/SKILL.md:10-16` (discuss section: new step 1, old steps renumbered 2-5, proposal and asset rules in the new step 3)
  - Modify `docs/guides/sdd.md:54-58` (Images and mockups: placement rule) and `:66` (discuss row)
  - Modify `docs/guides/sdd.vi.md:54-58` and `:66` (same, in Vietnamese)
  - Test `tests/workflow_core/test_skill_routing.py` (new test)
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** the new step must stay precise and within the 6,000-character `gin-*` budget while renumbering the discuss steps; wording judgement beyond a mechanical insert, with a clear spec.
- **Acceptance criteria**:
  - `gin-sdd` discuss presents a *Capabilities affected* table in the confirmed design before `specs new`, states the `ui` rule and the README override, normalizes names, prefers an existing capability over a near-duplicate `(new)` name, and warns that a change after `specs next-id` means renumbering.
  - `gin-sdd` discuss says `## Capabilities Affected` lists each capability with its REQ-IDs and asset paths, that an asset elsewhere in the repository is `git mv`ed into `<specs>/<cap>/assets/`, and that an asset outside the repository is not copied.
  - `docs/guides/sdd.md` and `sdd.vi.md` state the rule in Images and mockups and the table in the `discuss` row.
  - `len(SKILL.md) <= 6000`; `python3 -m pytest -q tests/workflow_core/test_skill_routing.py tests/workflow_core/test_token_budget.py tests/workflow_core/test_docs_coverage.py` passes; `gin-workflow docs check docs/guides/sdd.md docs/guides/sdd.vi.md` prints `ok` twice.
- **Estimated complexity**: low

Steps:
1. Failing test. In `tests/workflow_core/test_skill_routing.py`, after `test_roadmap_names_capabilities_per_epic`, add:
   ```python
    def test_sdd_discuss_confirms_capabilities_before_ids(self):
        text = (SRC / "skills/gin-sdd/SKILL.md").read_text(encoding="utf-8")
        discuss = text[text.index("## discuss"):text.index("## plan")]
        for needle in ("Capabilities affected", "`ui` holds only", "`(new)`", "renumbering",
                       "## Capabilities Affected", "`git mv`", "README.md"):
            with self.subTest(needle=needle):
                self.assertIn(needle, discuss)
        self.assertLess(discuss.index("Capabilities affected"), discuss.index("`specs new <slug> --epic <epic>`"))
        self.assertLessEqual(len(text), 6_000)
   ```
   Run `python3 -m pytest -q tests/workflow_core/test_skill_routing.py -k capabilities_before_ids`: 1 failed.
2. `plugins/gin-workflow/src/skills/gin-sdd/SKILL.md`, discuss section. Insert a new step 1 before the current step 1 and renumber the current steps 1-4 to 2-5:
   ```
   1. In the design the user confirms, present a *Capabilities affected* table: per requirement group, the capability (an existing folder under `artifacts.specs`, or `(new)`), what goes there, and its assets as `<specs>/<cap>/assets/<file>`. Sources, in order: the epic's `Capabilities:` line, `<specs>/README.md`, the tech-doc `02-FEATURES.md`; ask only when all are missing. Rule: a feature's requirements, its UI included, go to the feature's capability; `ui` holds only design system, layout, navigation, and shared components; a rule written in `<specs>/README.md` overrides this. Normalize names to `[a-z][a-z0-9-]*`; when a `(new)` name nearly matches an existing capability (`report`, `reports`), use the existing one and say so. Say that changing a capability after `specs next-id` means renumbering, which breaks test names and archived citations.
   ```
   In the renumbered step 3 (old step 2), after `each with `REQ:`.` insert: `` `## Capabilities Affected` lists each capability with its REQ-IDs and asset paths; `git mv` an asset placed elsewhere in the repository into `<specs>/<cap>/assets/`; an asset outside the repository is not copied: ask the user to put it there first. ``
3. `docs/guides/sdd.md`, section `## Images and mockups` (line 54): before the paragraph `As a team convention, keep screenshots...` insert:
   ```
   A feature's requirements, its UI included, live in the feature's capability (`reports`, not `ui`). A `ui` capability holds only what spans pages: design system, layout, navigation, shared components. A project that wants another rule writes it in `docs/specs/README.md`, and discuss follows the README.
   ```
   Line 66, `discuss` row: after `Creates the epic,` insert ` after you confirm the capabilities table (capability, requirement groups, asset paths) in the design,`.
   `docs/guides/sdd.vi.md`: same section, insert before the paragraph starting `Như một quy ước của nhóm,`:
   ```
   Requirements của một feature, kể cả UI của nó, nằm trong capability của feature đó (`reports`, không phải `ui`). Capability `ui` chỉ giữ những gì dùng chung cho nhiều trang: design system, layout, navigation, component dùng chung. Project muốn quy tắc khác thì ghi vào `docs/specs/README.md`, và discuss theo README.
   ```
   Row 66: after `Tạo epic,` insert ` sau khi bạn xác nhận bảng capability (capability, nhóm requirement, đường dẫn asset) trong design,`.
4. Run the test of step 1 (pass), then `python3 -m pytest -q tests/workflow_core/test_skill_routing.py tests/workflow_core/test_token_budget.py tests/workflow_core/test_docs_coverage.py` (all pass) and `gin-workflow docs check docs/guides/sdd.md docs/guides/sdd.vi.md` (`ok`). Commit: `feat(sdd): confirm capabilities and asset paths before REQ-IDs (gin-workflow-7xy4)`.

## Integration
- **Branch**: `feat/ba-capability-placement` (worktree `.claude/worktrees/ba-capability-placement`)
- **Merge strategy**: sequential

## Validation
- [ ] `python3 -m pytest -n auto` passes (pre-push hook)
- [ ] `gin-workflow docs check` prints `ok` for the four docs pages
- [ ] `gin-workflow specs template roadmap.md` and `epic.md` show `Capabilities:`
- [ ] `wc -c plugins/gin-workflow/src/skills/gin-sdd/SKILL.md` ≤ 6000

## Notes
- Track beads: Track 2 reuses `gin-workflow-7xy4.1` (orchestrate updates its title and description to this track); Track 1 is a new child of `gin-workflow-7xy4`.
- The spec and this plan are committed together at plan approval on `feat/ba-capability-placement`.
- `dist/` needs no step: `install.sh` rebuilds it at ship.
