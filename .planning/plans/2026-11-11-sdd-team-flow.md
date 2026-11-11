# Plan: SDD layout and change flow for a team workspace

Spec: .planning/specs/2026-11-11-sdd-team-flow-design.md
Epic: gin-workflow-sdd-team-flow
Workflow: gin-workflow-sdd-team-flow

## Objective

A `MODIFIED` or `REMOVED` block can target a requirement another open change adds, `specs trace` finds tests in every cloned workspace child, and the brownfield starter, the git agreement, the SDD and BA guides, and the `sdd` and gin-qa setup skills describe one team flow: SDD layout from setup, legacy capture before discuss, living specs for the new system only, asset folders with the spec pull request, and an archive row with the BA as reviewer.

**Goal** (spec): The brownfield starter sets the SDD layout with a capture step before discuss, and asset folders, in-flight requirement changes, `Source:` lines, spec checklists, cross-child `specs trace`, and the archive pull request follow one team flow.

**Architecture**: two code changes in `workflow_core`, then docs. `specs.py` gains one helper that lists the `ADDED` blocks of open change folders whose REQ is not living (`in_flight_blocks`); `lint_change`, `requirement_hash`, and `specs_archive.archive` use it. `specs_trace.trace` adds the cloned, workable children of `workspace.load(root)` to its file list, matching each child's tracked files against the parent's `test_globs` relative to the child and reporting them with the child's path in front; uncloned workable children go to a new `skipped` key. The docs tracks put each fact on one page (`sdd.md` for living specs, in-flight changes, and REQ-IDs; `git-flow.md` for branches, pull requests, and checklists) and link to it from the starter, the BA guide, roles, and workspace, with the Vietnamese translations kept in step.

**Tech Stack**: Python 3 standard library; unittest/pytest with `tests/workflow_core/specs_fixtures.py` and the `make_workspace` fixture of `tests/workflow_core/test_workspace.py`; Markdown docs checked by `gin docs check` and `mkdocs build --strict` in CI; skill budgets in `tests/workflow_core/test_token_budget.py` (6,000 characters for `sdd`) and `tests/gin_qa/test_packaging.py` (6,000 for each gin-qa skill).

**Global Constraints** (spec, verbatim):
- Lint, hash, and archive messages for living requirements are unchanged; only the message for a REQ that is neither living nor in flight changes (R6).
- `specs trace --format json` only adds `skipped`; gin-console does not read trace output.
- A project without `workspace.repos` traces exactly as today.
- A child whose `git ls-files` fails is listed in `skipped` instead of stopping the trace.
- Skill files stay within their character budgets (`tests/` budget tests).
- Out of scope: BA work during build, mockup tokens, and capture sign-off (`gin-workflow-ba-workspace`); Java globs in `DEFAULT_TEST_GLOBS`, the starter sets them in its config instead; `migrate-specs` for a project that is not rewritten: it keeps describing current behavior (`sdd.md:164`).

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
- Problem statement: the brownfield starter leaves the layout `legacy` and has no capture step; its text makes living specs describe legacy behavior; `specs lint` rejects a `MODIFIED` block on a requirement still in flight; `specs trace` sees only one repository; the git agreement contradicts the `sdd` skill on `Source:` lines and has no rule for asset folders or the archive.
- Success criteria: spec R1 to R12; US-1 to US-5 acceptance criteria as tests (code) or checked text (docs); existing tests pass; `gin docs check` clean on changed pages.
- Constraints: Global Constraints above.
- Non-goals: see Global Constraints.

## Approach Options
### Option 1: working `MODIFIED` block on an in-flight requirement (code)
- Summary: lint and hash accept a REQ `ADDED` in another open change; archive stops until that change is archived.
- Pros: the documented "new change folder with a `MODIFIED` block" flow works whether the requirement shipped or not; the approved change folder is never edited.
- Cons: three functions change; archive order becomes a rule.

### Option 2: re-review flow only (docs)
- Summary: amend the in-flight change folder and re-run spec review and the `requirement_confirmed` gate.
- Pros: no code.
- Cons: edits an approved spec without a gate of its own; rejected in `/discuss`.

### Recommended Approach
- Selected option: Option 1 (confirmed in `/discuss` on 2026-11-11), with asset folders riding the spec pull request and living specs describing only the new system.
- Rationale: matches the epic's scope ("a working `MODIFIED` block") and keeps one flow for every requirement change after plan approval.

## Scope
- In scope: R1 to R12.
- Out of scope: see Global Constraints.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Tracks 1 and 2 both edit specs_cli.py and the specs table of cli.md, and the docs tracks describe the shipped behaviour of both; one lane avoids conflicts.
```

## Tasks

`S` is `plugins/gin-workflow/src/scripts/workflow_core`.

### Track 1: `MODIFIED` and `REMOVED` on a requirement another open change adds
- **Dependencies**: none
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs.py:388-396` (`_known_req_ids` uses the new `open_changes`), `:442-485` (`lint_change`), `:585-590` (`requirement_hash`), new `open_changes` and `in_flight_blocks` next to `_known_req_ids`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs_archive.py:54-65` (stop while the target change is open)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs_cli.py:148-151` (`hash` output names the change)
  - Modify `docs/reference/cli.md:137` (`hash` row)
  - Test `tests/workflow_core/test_specs.py`, `tests/workflow_core/test_specs_archive_trace.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** bounded change to three functions of one module with every case and message fixed by the spec.
- **Interfaces**:
  - `specs.open_changes(root: Path, cfg: Mapping[str, Any]) -> list[Path]`: sorted folders under `changes_dir(root, cfg)`, not `archive`, whose `change_file(change, "spec-delta")` exists (the loop `_known_req_ids` runs today).
  - `specs.in_flight_blocks(root: Path, cfg: Mapping[str, Any], *, exclude: Path | None = None) -> dict[str, list[tuple[Path, Block]]]`: for each open change other than `exclude`, its `ADDED` blocks whose id is not in `living_blocks(root, cfg)`, keyed by REQ id, in change order.
  - `specs.requirement_hash(root, cfg, req_id) -> tuple[Block, str, Path | None]`: the living block and `None` as today; else the single in-flight `ADDED` block and its change; two in-flight changes raise `SpecsError("<REQ> is added by <a> and <b>; renumber one")`; neither raises `SpecsError("<REQ> is not in the living spec or an open change")`. Callers that index `[1]` keep working.
  - `gin specs hash <REQ> --format json` → `{"id", "hash", "change": <change folder name> | null}`; text output stays `<!-- base: <hash> -->` on stdout and, for an in-flight REQ, adds `note: <REQ> is added by open change <name>; archive it first` on stderr.
  - Lint messages (`where` is `<delta path>:<line>` as today): `<REQ> is not in the living spec or an open change`; `<REQ> is added by <a> and <b>; renumber one`.
  - Archive message (`ArchiveConflict`, exit 1): `<REQ> is added by <change>; archive <change> first`.
- **Steps**:
  1. Failing tests in `tests/workflow_core/test_specs.py`, class `TestRepositoryCommands` (its `setUp` writes `AUTH_SPEC` and the activity diagram). Add a module constant `MODIFIED_003` built from `ADDED_BLOCK`:
     ```python
     MODIFIED_003 = ("### REQ-AUTH-003: Lock account after failed logins\n<!-- base: {base} -->\n"
                     "The system SHALL lock an account for 30 minutes after 5 failed logins.\n\n"
                     "#### Scenario: fifth failure locks\n- GIVEN a user with 4 failed logins\n"
                     "- WHEN the next login fails\n- THEN the account is locked\n")
     ```
     - `test_lint_accepts_modified_on_in_flight_req`: `make_change(self.root)` (name `ep-1-lockout`, adds REQ-AUTH-003); `block, base, source = specs.requirement_hash(self.root, self.cfg, "REQ-AUTH-003")`; assert `source.name == "ep-1-lockout"` and `base == specs.block_hash(ADDED_BLOCK)`; `second = make_change(self.root, "ep-2-longer", epic="ep-2", spec_delta=delta(modified=MODIFIED_003.format(base=base)))`; assert `specs.lint_change(self.root, self.cfg, second) == []`. Same for a `REMOVED` block with `Reason: dropped` → `[]`.
     - `test_lint_rejects_req_neither_living_nor_in_flight`: a change with `MODIFIED` `REQ-AUTH-999` (base `0`*64) → an error ending `REQ-AUTH-999 is not in the living spec or an open change`.
     - `test_req_added_by_two_open_changes`: `ep-1-lockout` and `ep-3-dup` both add REQ-AUTH-003; `requirement_hash` raises `SpecsError` with `REQ-AUTH-003 is added by ep-1-lockout and ep-3-dup; renumber one`; a third change modifying it gets the same text from lint.
     - `test_living_hash_unchanged`: `requirement_hash(..., "REQ-AUTH-002")` returns `source is None` and the same hash as `block_hash` of the living block.
     In `TestSpecsCli`, `test_hash_names_in_flight_change`: after `make_change`, `specs hash REQ-AUTH-003 --format json` prints `"change": "ep-1-lockout"`; the text form prints `<!-- base: ` on stdout and `note: REQ-AUTH-003 is added by open change ep-1-lockout; archive it first` on stderr.
  2. Failing test in `tests/workflow_core/test_specs_archive_trace.py`, class `TestArchive`: `test_modified_on_in_flight_req_waits_for_its_change` (import `MODIFIED_003` by defining the same constant locally): `first = make_change(self.root)`; base from `requirement_hash` of REQ-AUTH-003; `second = make_change(self.root, "ep-2-longer", epic="ep-2", spec_delta=delta(modified=MODIFIED_003.format(base=base)))`; `commit_all`; `archive(second)` raises `ArchiveConflict` whose `errors` contain `REQ-AUTH-003 is added by ep-1-lockout; archive ep-1-lockout first` and the living spec is unchanged; `archive(first, today=TODAY)`, `commit_all`, `archive(second, today=TODAY)` succeeds and `docs/specs/auth/spec.md` contains `30 minutes` and not `15 minutes`.
  3. Run `python3 -m pytest tests/workflow_core/test_specs.py tests/workflow_core/test_specs_archive_trace.py -q -n auto` → the new tests fail.
  4. `specs.py`: add `open_changes` and `in_flight_blocks`; make `_known_req_ids` loop over `open_changes`. In `lint_change`, compute `in_flight = in_flight_blocks(root, cfg, exclude=change)` once and replace the `if block.id not in living:` branch with:
     ```python
     if block.id not in living:
         added = in_flight.get(block.id, [])
         if not added:
             errors.append(f"{where}: {block.id} is not in the living spec or an open change")
         elif len(added) > 1:
             errors.append(f"{where}: {block.id} is added by {' and '.join(c.name for c, _ in added)}; renumber one")
     ```
     Change `requirement_hash` per the interface (living first, then `in_flight_blocks(root, cfg)`).
  5. `specs_archive.archive`: after the living-base loop, add
     ```python
     in_flight = in_flight_blocks(root, cfg, exclude=change)
     for block in blocks:
         added = in_flight.get(block.id, [])
         if block.section in ("MODIFIED", "REMOVED") and block.id not in living and len(added) == 1:
             name = added[0][0].name
             errors.append(f"{block.id} is added by {name}; archive {name} first")
     ```
  6. `specs_cli.py` `hash` branch: unpack three values, emit `{"id": block.id, "hash": digest, "change": source.name if source else None}`, and print the stderr note when `source` is set (text format only).
  7. `docs/reference/cli.md:137`: the `hash REQ-ID` row adds "; a requirement another open change adds gets that block's hash, and the JSON `change` names that change". Run `gin docs check docs/reference/cli.md` → no findings.
  8. Run step 3 → pass; `python3 -m pytest tests/workflow_core -q -n auto -k "specs"` → pass.
  9. Commit: `feat(specs): MODIFIED and REMOVED on a requirement another open change adds (gin-workflow-sdd-team-flow)`.
- **Acceptance criteria**: R6; US-3 criteria 1 to 5 as the tests above; existing specs tests pass unchanged.
- **Estimated complexity**: medium

### Track 2: `specs trace` across workspace children
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs_trace.py:12-16,34-58` (new `_child_tracked`; `trace` scans children)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs_cli.py:182-186` (text output lists skipped children)
  - Modify `docs/reference/cli.md:141` (`trace` row)
  - Test `tests/workflow_core/test_specs_archive_trace.py` (new class `TestTraceWorkspace`)
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** one function over the existing `workspace` and `test_files` helpers; the child rules (workable, cloned, failing `git ls-files`) are fixed by the spec.
- **Interfaces**:
  - `specs_trace._child_tracked(checkout: Path) -> list[str] | None`: `git ls-files` in `checkout`, `None` when it fails. The parent keeps `_tracked(root)` and its `rglob` fallback unchanged.
  - `trace(root, cfg, change) -> dict` adds `"skipped": list[str]` (child paths, manifest order). Candidates are the parent's tracked files filtered by `test_files(root, cfg, ...)`, plus, for each `repo` in `workspace.load(root).repos` with `repo.workable` and `space.present(repo)`, `f"{repo.path}/{p}"` for each `p` in `test_files(root, cfg, _child_tracked(space.checkout(repo)))`. A workable child that is not present, or whose `_child_tracked` returns `None`, goes to `skipped`. Frozen children and the Beads repository are neither scanned nor skipped. Without a workspace, `skipped` is `[]`.
  - Text output of `gin specs trace`: today's lines, then one `skipped: <path>` line per skipped child.
- **Steps**:
  1. Failing tests, class `TestTraceWorkspace` above the `__main__` guard of `tests/workflow_core/test_specs_archive_trace.py`. Fixture: `root = make_workspace(tmp)` (`from test_workspace import make_workspace`, as the file imports `specs_fixtures`); append `"artifacts:\n  layout: sdd\n"` to `root/.agent-workflow/config.yaml`; write `AUTH_SPEC`, the activity diagram, and `make_change(root)`; commit in the parent. In `root/services/api` write `tests/test_lock.py` containing `# REQ-AUTH-003` and commit there; create `root/legacy/portal` as a git repo with `tests/test_old.py` containing `# REQ-AUTH-003` (frozen; must not be scanned).
     - `test_child_tests_count_with_their_path`: `trace` → REQ-AUTH-003 `covered`, sources `["services/api/tests/test_lock.py"]`; `skipped == ["apps/web"]`.
     - `test_globs_match_relative_to_the_child`: with `test_globs: ["tests/**"]` in `cfg`, the child file still matches (the glob is applied to `tests/test_lock.py`, not `services/api/tests/test_lock.py`).
     - `test_failing_child_is_skipped`: patch `specs_trace._child_tracked` to return `None` → REQ-AUTH-003 `missing` and `skipped == ["services/api", "apps/web"]`, no exception.
     - `test_single_repository_adds_only_skipped`: in `TestTraceAndStatus.test_trace_finds_code_tags_and_tests_md_rows`, add `self.assertEqual([], result["skipped"])`.
     - CLI: `gin specs trace --change ep-1 --repository <root>` text output contains `skipped: apps/web`.
  2. Run `python3 -m pytest tests/workflow_core/test_specs_archive_trace.py -q` → the new tests fail.
  3. Implement per the interface in `specs_trace.py` (import `load` from `.workspace`; keep the `tests.md` rows as today); add the `skipped:` lines to the text output in `specs_cli.py`.
  4. `docs/reference/cli.md:141`: the `trace --change C` row adds "; in a workspace it also scans every cloned child that is neither frozen nor the Beads repository, names each source by its workspace path, and lists children it could not scan under `skipped`". Run `gin docs check docs/reference/cli.md` → no findings.
  5. Run step 2 → pass; `python3 -m pytest tests/workflow_core -q -n auto -k "specs or workspace"` → pass.
  6. Commit: `feat(specs): trace scans cloned workspace children and lists skipped ones (gin-workflow-sdd-team-flow)`.
- **Acceptance criteria**: R8; US-4 criteria 1 to 4 as the tests above.
- **Estimated complexity**: medium

### Track 3: One team flow in the git agreement, SDD, BA, roles, and workspace docs, and the `sdd` skill
- **Dependencies**: Track 2
- **Files**:
  - Modify `docs/guides/sdd.md:3` (intro), `:56-90` (asset folders reach git with the spec), `:37-55` (REQ-IDs in a workspace), `:148-160` (stages table: spec review, ship), new section `## Living specs during a migration` and `## Changing a requirement after plan approval` before `## Migrating` (`:162`)
  - Modify `docs/guides/git-flow.md:46-60` (asset folders sentence after the branch table), `:72-77` (archive row), `:90-96` (checklist heading and `Source:` item), `:150-154` (link to the in-flight flow)
  - Modify `docs/guides/ba.md:70`, `:96-98` (asset folders; drop "the BA commits asset folders")
  - Modify `docs/roles.md:72` (in-flight requirement)
  - Modify `docs/guides/workspace.md:65-77` (REQ-IDs live in the parent), `:87` (Ship row: archive reviewer)
  - Modify the translations of each: `docs/guides/sdd.vi.md`, `docs/guides/git-flow.vi.md`, `docs/guides/ba.vi.md`, `docs/roles.vi.md`, `docs/guides/workspace.vi.md`
  - Modify `plugins/gin-workflow/src/skills/sdd/SKILL.md` (discuss step 3 trim, step 4, ship)
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** documentation of shipped behaviour across five pages and their translations, with one home per fact and a skill at 5,987 of 6,000 characters that needs trimming to fit.
- **Steps**:
  1. `sdd.md` (one home for these facts):
     - Intro (`:3`): keep "always describes current behavior" and add one sentence linking `#living-specs-during-a-migration` for a rewrite.
     - `## Living specs during a migration` (R3): during a rewrite, living specs describe the shipped new system; legacy behavior stays in `Kind: legacy` asset folders written by `/gin-ba:capture` or `gin specs assets add --legacy`; a requirement taken from legacy behavior names that folder in its `Source:` line; a project that is not rewritten seeds living specs from current behavior, as in Migrating.
     - In `## Images and mockups` (R5): a confirmed folder is not committed on its own branch; `/gin:discuss` commits it with the change folder that cites it on `spec/<epic>-<slug>`, so the spec approvers approve it; a confirmed folder no change cites stays uncommitted.
     - In `## Requirements` (R9): in a workspace, requirements and REQ-IDs live only in the parent's specs and children only reference them; `gin specs next-id` scans the tree, worktrees, and remote branches; `gin specs lint --against <base>` reports an `ADDED` id already used on the base, and `gin specs renumber` fixes it; the `sdd` skill runs that lint before the spec pull request and at ship.
     - `## Changing a requirement after plan approval` (R7): a new change folder with a `MODIFIED` (or `REMOVED`) block whose base comes from `gin specs hash <REQ>`, whether the requirement has shipped or another open change still adds it; the approved change folder is never edited; `gin specs archive` of the new change stops with `<REQ> is added by <change>; archive <change> first` until that change is archived.
     - Stages table: the `ship` row adds "The archive lands with the integration, and the BA reviews the living-spec diff ([pull requests](git-flow.md#pull-requests))."
  2. `git-flow.md` (one home for branches, pull requests, checklists):
     - After the branch table: "Asset folders have no branch of their own: a confirmed folder reaches the base with the spec pull request whose change folder cites it ([images and mockups](sdd.md#images-and-mockups))." (R5)
     - Pull request table, new row after Track (R12): `| Archive into the living spec | the integration of the epic: the feature branch merge, or the parent's pull request in a workspace | roles listed for `ship`; the BA reviews the living-spec diff | `ship` |`.
     - Checklist (R10): heading "The approver of a spec checks that:" and, before the list, "The BA uses it on spec pull requests other members author."; the `Source:` item (R11) reads "every requirement taken from an input has a `Source:` line that names it;".
     - `## Conflicts and changes after approval`: link the second sentence to `sdd.md#changing-a-requirement-after-plan-approval`.
  3. `ba.md`: `:70` replace "Review the folder and commit it yourself." with "Review the folder; `/gin:discuss` commits it with the change folder that cites it ([images and mockups](sdd.md#images-and-mockups))."; `:98` replace the bullet "The BA reviews and commits asset folders, because the skills never do." with "Confirmed asset folders reach the base with the spec pull request; see [images and mockups](sdd.md#images-and-mockups)."; `:97` links `sdd.md#changing-a-requirement-after-plan-approval` instead of restating the flow. Add a bullet: "Legacy behaviour stays in `Kind: legacy` folders; see [living specs during a migration](sdd.md#living-specs-during-a-migration)."
  4. `roles.md:72`: replace the SDD sentence with "With the SDD layout, see [changing a requirement after plan approval](guides/sdd.md#changing-a-requirement-after-plan-approval); `gin-qa cases plan` shows which test cases went stale."
  5. `workspace.md`: after "Specs and plans are committed to the parent." (`:77`) add "Requirements and their REQ-IDs live only in the parent's specs; children reference them in tests, and `gin specs trace` scans every cloned child ([REQ-IDs](sdd.md#requirements))."; the Ship row (`:87`) adds "; the parent's integration carries the archive into the living spec, and the BA reviews that diff".
  6. Translations: apply the same changes to each `.vi.md` sibling in Vietnamese, keeping code, paths, and commands verbatim, and give each new heading the English anchor in `{ #... }` form as the existing translations do (for example `## Đặc tả sống trong quá trình chuyển đổi { #living-specs-during-a-migration }`).
  7. `sdd/SKILL.md` (budget 6,000; now 5,987):
     - Step 3: delete " (numbers give reading order; an older unnumbered folder keeps its names)"; replace "copies the files (from anywhere) and writes `description.md` (`Kind:`, `Previous:`, `Confirmed: no`)" with "copies the files and writes `description.md`".
     - Step 4: "4. `specs lint --change <epic> --against <base>` must exit 0; a taken ID: `specs renumber`. An untracked cited file (ADR, mockup, asset folder): commit it with the change folder, lint again."
     - Ship: replace "A duplicate ID on the base: `specs renumber <old> <new> --change <epic>`, then rerun both." with "A duplicate ID on the base: `specs renumber`, then rerun both."; after "commit (`docs(specs): archive <epic>`)" add "; the BA reviews the living-spec diff in the integration".
     - `python3 -c "import pathlib;print(len(pathlib.Path('plugins/gin-workflow/src/skills/sdd/SKILL.md').read_text(encoding='utf-8')))"` → at most 6000.
  8. `gin docs check` on every changed page → no findings; `python3 -m pytest tests/workflow_core/test_token_budget.py tests/workflow_core/test_docs_coverage.py -q -n auto` → pass.
  9. Commit: `docs(sdd): one team flow for asset folders, in-flight changes, REQ-IDs, checklists, and the archive (gin-workflow-sdd-team-flow)`.
- **Acceptance criteria**: R5, R7, R9, R10, R11, R12, and R3's `sdd.md` part; US-2; US-3 criterion 6; US-4 criterion 5; US-5; budgets hold; docs check clean.
- **Estimated complexity**: medium

### Track 4: Brownfield starter in the SDD layout, and the gin-qa setup warning
- **Dependencies**: Track 3
- **Files**:
  - Modify `docs/starters/brownfield.md:62-79` (flow diagram: capture node), `:88-96` (setup answers and `artifacts` config), new section `## Capture and mockup (BA)` before `## Discuss an epic` (`:273`), `:288` (prompt link), `:296-306` (replace "Capture current behavior first")
  - Modify `docs/starters/brownfield.vi.md` (same changes)
  - Modify `plugins/gin-qa/src/skills/setup/SKILL.md:9` (step 1: layout warning)
  - Test `tests/gin_qa/test_packaging.py` (existing budget and link test; no new test)
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `low`
- **Why:** documentation edits on one page and its translation plus one skill sentence, all following Track 3's homes.
- **Steps**:
  1. Setup answers (`:92`): "Answer `stage: brownfield`, `shape: fullstack`, `workspace` for the repository layout, and `sdd` for the spec layout." Before `workspace:` in the config block, add:
     ```yaml
     artifacts:
       layout: sdd
       test_globs: ["**/src/test/**", "**/test_*.py", "**/*.test.*", "**/*.spec.*", "tests/**", "__tests__/**"]
     ```
     and one sentence: "The Maven test tree is added to the default globs so `gin specs trace` finds the services' tests."
  2. Flow diagram: insert `D --> CA["capture + mockup<br/>BA"] --> E` in place of `D --> E`.
  3. New `## Capture and mockup (BA)` before `## Discuss an epic`, in the page's Who/Where/Prompt/You get/Gate or approval/Common mistakes pattern: Who: BA; Where: the parent; Prompt: `/gin-ba:capture catalog --date <date>` naming the legacy screenshots of the catalog list and product detail, and `/gin-ba:mockup catalog` only when the new UI differs from the legacy one; You get: a dated `Kind: legacy` folder (and a mockup folder) under `docs/specs/catalog/assets/`; Gate or approval: none; the BA confirms each folder with `gin specs assets confirm catalog --date <date>`, and `/gin:discuss` cites only confirmed folders and commits them with the change folder; Common mistakes: committing an asset folder on its own branch, discussing before the folders are confirmed. Link [living specs during a migration](../guides/sdd.md#living-specs-during-a-migration) and [the BA guide](../guides/ba.md).
  4. Replace `### Capture current behavior first` (`:296-306`) with `### Legacy behavior and living specs`: living specs describe the new system; the epic's requirements cite the confirmed legacy folders with `Source:`; keep the REST contract paragraph; replace the example with a requirement of the new system that has a `Source:` line naming `docs/specs/auth/assets/<date>/legacy/description.md`. Update the prompt link at `:288` to the new anchor.
  5. `brownfield.vi.md`: same changes in Vietnamese, anchors `{ #capture-and-mockup-ba }` and `{ #legacy-behavior-and-living-specs }`.
  6. `plugins/gin-qa/src/skills/setup/SKILL.md` step 1: append "Then read `project.layout` from `gin state --format json`; when it is not `sdd`, warn that `gin-qa cases plan` then has no work list and `cases check` covers structure and IDs only, name `artifacts.layout: sdd` (`/gin:migrate-specs`) as the fix, and continue."
  7. `gin docs check docs/starters/brownfield.md docs/starters/brownfield.vi.md` → no findings; `python3 -m pytest tests/gin_qa/test_packaging.py tests/workflow_core/test_docs_coverage.py -q -n auto` → pass; `python3 -m pytest -n auto -q` → pass.
  8. Commit: `docs(starters): brownfield starts in the SDD layout with a capture step; gin-qa setup warns without it (gin-workflow-sdd-team-flow)`.
- **Acceptance criteria**: R1, R2, R3's starter part, R4; US-1.
- **Estimated complexity**: low

## Integration
- **Branch**: `feat/sdd-team-flow`
- **Merge strategy**: sequential

## Validation
- [ ] `python3 -m pytest -n auto -q` passes (pre-push runs it).
- [ ] `gin docs check` on the changed pages reports no findings.
- [ ] Manual: after `install.sh`, in a scratch SDD repository, `gin specs hash` of a REQ added by an open change prints the hash and the stderr note, and `gin specs archive` of the modifying change stops until the first is archived.

## Notes
- Omit `Effort:` when the catalog lists no efforts.
- The user may override `Model:` and `Effort:` before plan approval.
- Provider roles describe responsibility rather than filename patterns.
- Deliverable merge-holds (e.g. "remain open until human-confirmed merge") apply exclusively to the Parent Bead. Individual track beads must close upon passing tests and code review to unblock downstream dependent tracks.
- Test hygiene from earlier reviews: new classes above any `__main__` guard, never between a decorator and its class, no duplicate class names; check `--collect-only` counts.
- `docs/starters/brownfield.md` is also edited by `gin-workflow-qa-parity`, which runs after this epic.
