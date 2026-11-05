# Plan: Spec assets: dated iteration folders and legacy capture

Epic: gin-workflow-spec-iterations
Spec: .planning/specs/2026-11-05-spec-iterations-design.md

## Objective
With the SDD layout, each batch of a capability's inputs lives in `docs/specs/<capability>/assets/<YYYY-MM-DD>/` with a `description.md` started from `gin-workflow specs template iteration.md`; screenshots of an existing feature go under `legacy/`; `specs lint` (living and `--change`) reports a dated folder without `description.md`; `gin-sdd` and the guides state the convention.

Architecture: one new template file, one new function `lint_iterations` in `workflow_core/specs.py` appended to `lint_living` and `lint_change`, skill text in `gin-sdd`, and docs. No new command, config key, or event.

Tech stack: Python 3 standard library (`re`, `pathlib`), `unittest` tests run by `python3 -m pytest -n auto`.

Global Constraints (from the spec):
- SDD layout only; `specs` commands already exit 2 with the legacy layout.
- A flat file under `assets/` and a folder not named by an ISO date are not checked.
- A project with no dated folders sees no change in lint results.
- No `specs assets new` command; the skill creates the folder with `mkdir` plus `specs template iteration.md`.
- `skills/gin-*/SKILL.md` stay within 6,000 characters (`tests/workflow_core/test_token_budget.py:162`).

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
- Problem statement: `docs/specs/<cap>/assets/` is flat; new customer inputs mix with old ones, nothing records their source or date, and legacy screenshots have no place or description.
- Success criteria: the user stories US-1..US-3 of the spec; `specs lint` exits 1 naming a dated folder without `description.md`; full suite green.
- Constraints: see Global Constraints.
- Non-goals: a CLI that creates the folder; mockup generation and legacy description from images (`gin-workflow-ba-plugin`); moving existing flat assets; assets in change folders; the legacy layout.

## Approach Options
### Option 1: Convention, template, and lint (chosen in discuss)
- Summary: template `iteration.md`, `lint_iterations` in `specs.py`, skill and guide text.
- Pros: about 15 lines of Python; reuses `specs_dir`, `shown`, `template_text`.
- Cons: the agent creates the folder by hand.

### Option 2: Option 1 plus `specs assets new`
- Summary: a command that creates the folder and `description.md`.
- Pros: one call for the future `gin-ba` skills.
- Cons: about 40 more lines and tests for a `mkdir` plus `specs template`.

### Recommended Approach
- Selected option: Option 1.
- Rationale: chosen by the user in discuss on 2026-11-05 (bead notes of `gin-workflow-spec-iterations`).

## Scope
- In scope: R1–R4 of the spec.
- Out of scope: everything listed under the spec's "Out of scope".

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Two small tracks; Track 2 names the template and lint behavior that Track 1 ships, so they run one after the other on the feature branch.
```

## Tasks
### Track 1: Template `iteration.md` and the dated-folder lint check
- **Dependencies**: none
- **Files**:
  - Create `plugins/gin-workflow/src/templates/iteration.md`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs.py:280-331` (add `_ISO_DATE` and `lint_iterations`; append it in `lint_living` and `lint_change`)
  - Test `tests/workflow_core/test_specs.py:61-120,222-235` (new test in `TestRepositoryCommands`; template assertions in `test_pm_and_ba_templates_ship_and_can_be_overridden`)
  - Modify `docs/reference/cli.md:132` (`lint` row names the dated-folder check)
  - Modify `docs/guides/customizing-templates.md:27-40` (template list and table row)
  - Modify `docs/guides/customizing-templates.vi.md` (same list and row, Vietnamese)
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** bounded change to one module with the exact function, messages, and tests given below; the edge cases (non-date folders, capability without `spec.md`) are listed.
- **Interfaces**:
  - Produces `workflow_core.specs.lint_iterations(root: Path, cfg: Mapping[str, Any]) -> list[str]`, findings shaped `"<specs>/<cap>/assets/<YYYY-MM-DD>: missing description.md (gin-workflow specs template iteration.md)"`, sorted by path.
  - Produces template name `iteration.md` for `gin-workflow specs template`.
  - Consumes `specs_dir(root, cfg)` (`specs.py:213`) and `shown(root, path)` (`specs.py:260`).
- **Steps**:
  1. Failing test. In `tests/workflow_core/test_specs.py`, class `TestRepositoryCommands`, after `test_lint_change_flags_cited_paths_git_does_not_track`, add:
     ```python
     def test_lint_flags_dated_asset_folder_without_description(self):
         write(self.root, "docs/specs/auth/assets/2026-05-11/legacy/login.png", "png")
         write(self.root, "docs/specs/reports/assets/2026-12-01/filter.png", "png")  # capability without spec.md
         write(self.root, "docs/specs/auth/assets/mockup/index.html", "<html>")
         write(self.root, "docs/specs/auth/assets/login-form.png", "png")
         write(self.root, "docs/specs/auth/assets/110526/shot.png", "png")
         expected = [
             "docs/specs/auth/assets/2026-05-11: missing description.md (gin-workflow specs template iteration.md)",
             "docs/specs/reports/assets/2026-12-01: missing description.md (gin-workflow specs template iteration.md)"]
         self.assertEqual(expected, specs.lint_living(self.root, self.cfg))
         self.assertEqual(expected, specs.lint_change(self.root, self.cfg, make_change(self.root)))
         result = run_specs(self.root, "lint")
         self.assertEqual(1, result.returncode)
         self.assertIn(expected[0], result.stdout)
         write(self.root, "docs/specs/auth/assets/2026-05-11/description.md", "# Auth: 2026-05-11\n")
         write(self.root, "docs/specs/reports/assets/2026-12-01/description.md", "# Reports: 2026-12-01\n")
         self.assertEqual([], specs.lint_living(self.root, self.cfg))
         self.assertEqual([], specs.lint_change(self.root, self.cfg, make_change(self.root)))
     ```
     In `TestSpecsCli.test_pm_and_ba_templates_ship_and_can_be_overridden`, add `"iteration.md"` to the name tuple, and after the `epic.md` assertion:
     ```python
     iteration = run_specs(root, "template", "iteration.md").stdout
     for needle in ("Kind:", "Source:", "Previous: none", "## Summary", "## Changes", "## Files"):
         with self.subTest(needle=needle):
             self.assertIn(needle, iteration)
     ```
  2. Run `python3 -m pytest tests/workflow_core/test_specs.py -k "dated_asset or templates_ship" -q`: expect 2 failures: `lint_living` returns `[]` instead of the two findings, and `specs template iteration.md` exits 2 with `unknown template: iteration.md`.
  3. Create `plugins/gin-workflow/src/templates/iteration.md`:
     ```markdown
     # {{capability}}: {{date}}

     <!-- description.md of one dated asset folder, docs/specs/<capability>/assets/<YYYY-MM-DD>/, named by the day
          the inputs arrived. Kind: new (first requirements), change (the customer's changes after an earlier folder),
          or legacy (screenshots of an existing feature, kept under legacy/). A new batch of inputs gets a new folder;
          never edit an older one. -->

     Kind:
     Source:
     Previous: none

     ## Summary

     ## Changes

     ## Files
     ```
  4. In `plugins/gin-workflow/src/scripts/workflow_core/specs.py`, before `def lint_living`, add:
     ```python
     _ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


     def lint_iterations(root: Path, cfg: Mapping[str, Any]) -> list[str]:
         """Every dated asset folder `<specs>/<cap>/assets/<YYYY-MM-DD>/` has a `description.md`."""
         return [f"{shown(root, folder)}: missing description.md (gin-workflow specs template iteration.md)"
                 for folder in sorted(specs_dir(root, cfg).glob("*/assets/*"))
                 if folder.is_dir() and _ISO_DATE.match(folder.name) and not (folder / "description.md").is_file()]
     ```
     `Path.glob` on a missing directory yields nothing, so no `is_dir` guard is needed. Change the last line of `lint_living` to `return errors + lint_iterations(root, cfg)` and the last line of `lint_change` to `return errors + _untracked_citations(root, change) + lint_iterations(root, cfg)`.
  5. Run the command of step 2: expect 2 passed. Run `python3 -m pytest tests/workflow_core/test_specs.py tests/workflow_core/test_specs_archive_trace.py -q`: expect all passed.
  6. Docs:
     - `docs/reference/cli.md:132`, in the `lint` row, after "but git neither tracks nor ignores" insert: `, and each dated asset folder `<specs>/<cap>/assets/<YYYY-MM-DD>/` without a `description.md``.
     - `docs/guides/customizing-templates.md:27`, add `` `iteration.md` `` after `` `specs-README.md` `` in the "Specs, stories, and roadmap" list; after the `specs-README.md` table row add `| Asset folder description (SDD layout) | `/gin-workflow:discuss` | `.agent-workflow/templates/iteration.md` |`.
     - `docs/guides/customizing-templates.vi.md`: the same list entry, and after the `specs-README.md` row `| Mô tả thư mục asset (layout SDD) | `/gin-workflow:discuss` | `.agent-workflow/templates/iteration.md` |`.
     - Run `gin-workflow docs check docs/reference/cli.md docs/guides/customizing-templates.md docs/guides/customizing-templates.vi.md`: expect exit 0.
  7. Commit: `feat(specs): dated asset folders need a description.md (gin-workflow-spec-iterations)`.
- **Acceptance criteria**: US-3 of the spec; the template part of US-1 (`specs template iteration.md` prints `Kind:`, `Source:`, `Previous:`, `## Summary`, `## Changes`, `## Files`).
- **Estimated complexity**: low

### Track 2: `gin-sdd` discuss and the SDD guide state the convention
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-workflow/src/skills/gin-sdd/SKILL.md:11,13` (discuss steps 1 and 3)
  - Test `tests/workflow_core/test_skill_routing.py:67-75` (needles in `test_sdd_discuss_confirms_capabilities_before_ids`)
  - Modify `docs/guides/sdd.md:52-60` (template list, "Images and mockups")
  - Modify `docs/guides/sdd.vi.md:52-60` (same, Vietnamese)
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `low`
- **Why:** text edits with the exact wording given; `sonnet` rather than `haiku` because the skill sits close to its 6,000-character budget and the Vietnamese guide must match the English one.
- **Interfaces**: consumes the template name `iteration.md` and the lint message of Track 1.
- **Steps**:
  1. Failing test. In `test_sdd_discuss_confirms_capabilities_before_ids`, add to the needle tuple: `"<specs>/<cap>/assets/<YYYY-MM-DD>/<file>"`, `"`specs template iteration.md`"`, `"`legacy/`"`, `"never edit an older dated folder"`.
  2. Run `python3 -m pytest tests/workflow_core/test_skill_routing.py -k capabilities_before_ids -q`: expect 1 failure.
  3. `plugins/gin-workflow/src/skills/gin-sdd/SKILL.md`:
     - Step 1: replace `its assets as `<specs>/<cap>/assets/<file>`` with `its assets as `<specs>/<cap>/assets/<YYYY-MM-DD>/<file>``.
     - Step 3: after "an asset outside the repository is not copied: ask the user to put it there first." insert: `Each batch of inputs gets a new dated folder `assets/<YYYY-MM-DD>/` (the day it arrived) with `description.md` from `specs template iteration.md` (`Kind:` `new`, `change`, or `legacy`); screenshots of an existing feature go under its `legacy/`; never edit an older dated folder.`
  4. Run the command of step 2: expect 1 passed. Run `python3 -m pytest tests/workflow_core/test_token_budget.py -q`: expect all passed (`gin-sdd` within 6,000 characters).
  5. `docs/guides/sdd.md`:
     - Line 52: add `` `iteration.md` `` to the template list.
     - Replace the paragraph starting "As a team convention, keep screenshots" (line 58) with:
       ````markdown
       Keep screenshots, mockups and diagrams for a capability in `docs/specs/<capability>/assets/`, one dated folder per batch of inputs, with file names that say the screen and state:

       ```text
       docs/specs/reports/assets/
         2026-05-11/          # first requirements
           description.md     # Kind: new
           report-list.png
           mockup/
         2026-12-01/          # the customer's changes
           description.md     # Kind: change, Previous: assets/2026-05-11/
           report-filter.png
       ```

       Name the folder by the ISO date the inputs arrived. A new batch of requirements, changes, or designs gets a new folder; an older folder is never edited, so the folders record the history of the capability's inputs. On a legacy project without design specs, put screenshots of the existing feature under `<date>/legacy/` and describe how it behaves today in that folder's `description.md` with `Kind: legacy`. Start every `description.md` from `gin-workflow specs template iteration.md`. `specs lint` reports a dated folder without `description.md`; flat files under `assets/` and folders not named by an ISO date stay valid and are not checked.
       ````
     - Line 60: replace `(`assets/login-form.png`)` with `(`assets/2026-05-11/report-list.png`)`.
  6. `docs/guides/sdd.vi.md`, the same three edits:
     - Line 52: add `` `iteration.md` `` to the template list.
     - Replace the paragraph starting "Như một quy ước của nhóm" (line 58) with the same `text` tree (comments translated: `# requirements đầu tiên`, `# thay đổi của khách`) and:
       `Đặt tên thư mục theo ngày ISO nhận đầu vào. Một đợt requirements, thay đổi hay thiết kế mới thì vào một thư mục mới; thư mục cũ không bao giờ bị sửa, nên các thư mục ghi lại lịch sử đầu vào của capability. Với project legacy không có design spec, đặt screenshot của feature hiện có trong `<date>/legacy/` và mô tả hành vi hiện tại của nó trong `description.md` của thư mục đó với `Kind: legacy`. Mọi `description.md` bắt đầu từ `gin-workflow specs template iteration.md`. `specs lint` báo thư mục có tên ngày mà thiếu `description.md`; file phẳng trong `assets/` và thư mục không mang tên ngày ISO vẫn hợp lệ và không bị kiểm tra.`
       preceded by `Giữ screenshot, mockup và sơ đồ của một capability trong `docs/specs/<capability>/assets/`, mỗi đợt đầu vào một thư mục theo ngày, với tên file nói rõ màn hình và trạng thái:`.
     - Line 60: `(`assets/login-form.png`)` → `(`assets/2026-05-11/report-list.png`)`.
  7. Run `gin-workflow docs check docs/guides/sdd.md docs/guides/sdd.vi.md`: expect exit 0.
  8. Commit: `docs(sdd): dated asset folders and legacy capture in gin-sdd and the guide (gin-workflow-spec-iterations)`.
- **Acceptance criteria**: US-1 (skill text) and US-2 of the spec; `test_skill_routing.py` and `test_token_budget.py` pass.
- **Estimated complexity**: low

## Integration
- **Branch**: `feat/spec-iterations`
- **Merge strategy**: sequential

## Validation
- [ ] `python3 -m pytest -n auto` passes (pre-push hook).
- [ ] `gin-workflow docs check` exits 0 on the five changed docs pages.
- [ ] Manual: in a scratch SDD repo, `mkdir -p docs/specs/reports/assets/2026-05-11 && gin-workflow specs lint` exits 1 naming the folder; `gin-workflow specs template iteration.md > docs/specs/reports/assets/2026-05-11/description.md && gin-workflow specs lint` prints `ok` (lint reads the disk, so an empty dated folder is enough to trigger the finding).

## Notes
- `Model:` and `Effort:` are chosen from the main harness catalog (`haiku`, `sonnet`, `opus`; efforts `low`..`max`).
- The user may override `Model:` and `Effort:` before plan approval.
- The Parent Bead `gin-workflow-spec-iterations` stays open until the human-confirmed merge; track beads close after tests and review pass.
