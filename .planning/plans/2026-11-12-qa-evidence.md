# Plan: Test evidence and defects from automated runs

Spec: .planning/specs/2026-11-12-qa-evidence-design.md
Epic: gin-workflow-qa-evidence
Workflow: gin-workflow-qa-evidence

## Objective

`gin-qa cases bug` files bugs for cases of any type and refuses to guess between several epics; `/gin-qa:e2e` and `/gin-qa:tests` offer it for product defects; `/gin-qa:report` and `docs/guides/qa.md` say how to publish the report zip from CI or by hand.

**Goal** (spec): run evidence outlives the tester's machine, automated e2e and API failures file bug beads, and a bug lands on the right epic.

**Architecture**: one code change in `plugins/gin-qa/src/scripts/gin_qa/bugs.py` (drop the manual-only guard; `epic_of` returns every distinct epic and `file_bug` refuses more than one), then skill and docs text. No new CLI flag, no host API, no CI file written by gin-qa.

**Tech Stack**: Python 3 standard library; unittest/pytest with the fake `gin` of `tests/gin_qa/test_cases_bug.py`; Markdown skills under the 6,000-character budget of `tests/gin_qa/test_packaging.py`.

**Global Constraints** (spec, verbatim):
- Out of scope: legacy parity (`gin-workflow-qa-parity`); the QA track and ship check (`gin-workflow-qa-lifecycle`, shipped); any code that uploads files or posts pull request comments; core gin-workflow skills (the core refers to gin-qa only from `qa-track`).
- The `several epics` refusal replaces the silent first-REQ choice; scripts that relied on it now need `--discovered-from`. The JSON output keys of `cases bug` do not change.
- No new dependency; skill files stay within the 6,000-character gin-qa budget (`tests/gin_qa/test_packaging.py`).
- The CI snippets are documentation: gin-qa writes no CI file.

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
- Problem statement: report zips stay on the tester's machine, automated failures cannot file bugs, and a case spanning several epics files against an arbitrary one.
- Success criteria: spec requirements 1–7 and US-1 to US-3; `python3 -m pytest -n auto` passes.
- Constraints: Global Constraints above.
- Non-goals: uploading or commenting through a host API; parity testing.

## Approach Options
### Option 1: docs and skill steps for publishing; widen `cases bug` (selected in `/discuss`)
- Summary: CI snippets plus a manual fallback; `cases bug` for every case type; exit 2 on several epics.
- Pros: no host dependency; reuses the `/gin-qa:run` choose-and-rerun pattern.
- Cons: publishing stays a manual or CI-configured step.

### Option 2: `gin-qa report --publish`
- Summary: upload the zip and post a comment through `gh`.
- Pros: one command.
- Cons: host-specific, needs write credentials and a new approval rule; rejected in `/discuss`.

### Recommended Approach
- Selected option: Option 1 (confirmed in `/discuss` on 2026-11-12).
- Rationale: smallest change that meets the goal.

## Scope
- In scope: spec requirements 1–7.
- Out of scope: see Global Constraints.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: the skills and docs describe the behaviour Track 1 ships; one lane.
```

## Tasks

`Q` is `plugins/gin-qa/src`. Run tests from the repository root.

### Track 1: `cases bug` for every case type, with no guess between epics
- **Dependencies**: none
- **Files**:
  - Modify `plugins/gin-qa/src/scripts/gin_qa/bugs.py:59-76,101-125` (`epic_of`, `file_bug`)
  - Test `tests/gin_qa/test_cases_bug.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** a bounded change to one module with the edge cases listed in the spec and an existing fake-`gin` test harness.
- **Interfaces**:
  - `bugs.epic_of(root: Path, eff: Effective, case: tc.Case) -> list[str]`: legacy (`Source:`) returns `[epic]` or `[]`; SDD returns the distinct epics of `case.reqs` in REQ order (`list(dict.fromkeys(...))`), possibly empty.
  - `bugs.file_bug(...)`: signature unchanged; no case-type check. When `discovered_from` is `None`: no epic → `QaError("no epic for <TC>; pass --discovered-from <bead>")` (unchanged); more than one → `QaError("several epics for <TC>: <a>, <b>; pass --discovered-from <bead>")`, before any `gin task` call and any case-file write. The open-bug re-run path stays before the epic lookup, as today.
- **Steps**:
  1. Failing tests in `tests/gin_qa/test_cases_bug.py` (reuse `BugCase`, `case_file`, the `answers.json` fake; use `make_change` twice, or the fixture's way of giving a REQ a change with an epic, so two REQs belong to changes with epics `ep-1` and `ep-2`; read `qa_fixtures.make_change` for the epic argument):
     - In `TestSdd`, replace `test_the_epic_comes_from_the_first_req_in_a_change` with `test_one_epic_files_without_a_choice` (REQ-AUTH-001 living, REQ-AUTH-003 in `ep-1`: files against `ep-1`, as the old test asserted) and add `test_several_epics_exit_2_until_one_is_chosen`: the case's REQs map to `ep-1` and `ep-2`; `cases bug` exits 2, stderr contains `several epics for TC-AUTH-001: ep-1, ep-2`, no `task create` call is logged, and the case file is unchanged; then with `--discovered-from ep-2` it exits 0 and `--deps` is `discovered-from:ep-2`.
     - Add `test_an_e2e_case_files_a_bug_and_records_it` and `test_an_api_case_files_a_bug_and_records_it` (legacy `Source:` case files named `.e2e.md` and with `Type: api` as the case format requires; read how `test_cases_cli.py` writes an api case): exit 0, one `task create` with `-t bug` and `discovered-from:<spec epic>`, and the case file has `Result: failed`, the `Run`, and the `Bug`.
     - Add `test_a_re_run_of_an_e2e_case_appends_to_its_open_bug`: an e2e case whose `Bug:` is an open bead; `created` is false, `appended` is true, no `task create`.
     Run `python3 -m pytest tests/gin_qa/test_cases_bug.py -q` → the new tests fail.
  2. `bugs.py`: delete the `case.type != "manual"` check; change `epic_of` per Interfaces (update its docstring: "every epic of the case's REQs"); in `file_bug` replace `epic = discovered_from or epic_of(...)` and the `None` check with:
     ```python
     if discovered_from:
         epic = discovered_from
     else:
         epics = epic_of(root, eff, case)
         if not epics:
             raise QaError(f"no epic for {case_id}; pass --discovered-from <bead>")
         if len(epics) > 1:
             raise QaError(f"several epics for {case_id}: {', '.join(epics)}; pass --discovered-from <bead>")
         epic = epics[0]
     ```
     Update the `file_bug` docstring ("on a case" instead of "on a manual case") and the module docstring of the test file.
  3. `grep -rn "epic_of" plugins tests` and adapt any other caller to the list return.
  4. `python3 -m pytest tests/gin_qa -q -n auto` → pass.
  5. Commit: `feat(gin-qa): cases bug for every case type; refuse to guess between epics (gin-workflow-qa-evidence)`.
- **Acceptance criteria**: spec requirements 3 and 6; US-2 bullets 1–2; US-3.
- **Estimated complexity**: low

### Track 2: skills and guide: publish the report, offer bugs from automated runs
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-qa/src/skills/report/SKILL.md:13` (publish step)
  - Modify `plugins/gin-qa/src/skills/e2e/SKILL.md:18` (offer bugs for `app_defect`)
  - Modify `plugins/gin-qa/src/skills/tests/SKILL.md:26,28` (offer bugs for product defects)
  - Modify `plugins/gin-qa/src/skills/run/SKILL.md:17` (several epics)
  - Modify `docs/guides/qa.md:137-146,205-210` (publish section, CI snippets, App pull request line, `cases bug` scope)
  - Modify `docs/reference/cli.md` (`gin-qa cases bug`: any case type, several-epics exit 2; added in review, user approval 2026-11-12)
  - Test `tests/gin_qa/test_packaging.py` (unchanged; must pass)
- **Provider role**: `docs`
- **Model:** `haiku`
- **Effort:** `low`
- **Why:** text edits with the exact wording below, guarded by the packaging budget test and `gin docs check`.
- **Steps**:
  1. `report/SKILL.md` step 4: append "Publish it where the reviewer can open it: with CI, the job that runs the tests uploads the zip as an artifact (`docs/guides/qa.md`, Publish the evidence) and the approval comment gives the artifact URL; without CI, attach the zip to a pull request comment and give that comment's link."
  2. `run/SKILL.md` step 4, the `cases bug` exit-2 bullet: make it read "`cases bug` exits 2 with `no epic for <TC-ID>`, `several epics for <TC-ID>: ...`, or `no such bead`: offer the epics it lists (id and title from `gin task show`), or else those of `gin task list --type epic --json`, plus another bead id. Run `cases bug` again with `--discovered-from <bead>`." Keep the rest of the bullet.
  3. `e2e/SKILL.md`: after step 7, insert step 8 and renumber the rest: "8. Bugs: list the `app_defect` cases and ask the user which ones to file. For each chosen case, ask for an external tracker reference as `/gin-qa:run` does (required when `## Bugs` in the guidelines says so), then run `gin-qa cases bug <TC-ID> --actual "<step>: <error>" --evidence "<screenshot>" [--external-ref "<ref>"] --run "<run folder>" --format json`. On exit 2 for the epic, offer the epics it lists, or `gin task list --type epic --json`, and run it again with `--discovered-from <bead>`. Report each bug as `<TC-ID> <bug>`, filed or kept open. Never file a bug the user did not choose."; in step 5 allow the `Bug` line to change too ("the `Result`, `Run`, and `Bug` lines").
  4. `tests/SKILL.md`: after step 7, insert step 8 with the same text, where `--actual` is "<failing assertion>" and `--evidence` is the JUnit file or test id from the `run` output, and the defects are the cases reported as product defects; renumber; in the last step change "Never edit `Result`, `Run`, or `Bug` lines yourself: `run` writes them." to "Never edit `Result`, `Run`, or `Bug` lines yourself: `run` and `cases bug` write them."
  5. `docs/guides/qa.md`:
     - In "Report", after the list, add a subsection `### Publish the evidence`: the report zip is the evidence a reviewer opens; with CI, upload it as an artifact also when the tests fail, and give the artifact URL in the approval comment; without CI, attach the zip to a pull request comment. Then two fenced snippets:
       ```yaml
       # GitHub Actions: steps of the job that runs the e2e tests
       - run: gin-qa e2e run
       - if: always()
         run: gin-qa report --zip --out qa/evidence/report
       - if: always()
         uses: actions/upload-artifact@v4
         with:
           name: qa-report
           path: qa/evidence/report.zip
       ```
       ```yaml
       # GitLab CI
       e2e:
         script:
           - gin-qa e2e run
         after_script:
           - gin-qa report --zip --out qa/evidence/report
         artifacts:
           when: always
           paths:
             - qa/evidence/report.zip
       ```
       Add one sentence: the paths assume the QA home `qa`; use your QA home's `evidence/` folder. Check `--out` and the zip name against `plugins/gin-qa/src/scripts/gin_qa/report.py` (`_target`, `_archive`) and fix the snippets if they differ.
     - In "Manual runs", "End-to-end specs", or the `cases bug` description (find where `gin-qa cases bug` is documented): `cases bug` files a bug for a case of any type; when the case's REQs belong to several epics it exits 2 and names them, and `--discovered-from` picks one.
     - In "End-to-end specs" and "Other automated tests": one sentence each that the skill offers `gin-qa cases bug` for each product defect the user chooses.
     - "App pull request": "The approval comment gives the URL of the report artifact, or the pull request comment with the report zip (a team convention)."
  6. `python3 -m pytest tests/gin_qa/test_packaging.py tests/workflow_core/test_docs_coverage.py -q` → pass; `gin docs check docs/guides/qa.md` → ok; `python3 -m pytest -n auto` → pass.
  7. Commit: `docs(gin-qa): publish the report; offer bugs from automated runs (gin-workflow-qa-evidence)`.
- **Acceptance criteria**: spec requirements 1, 2, 4, 5, 7; US-1; US-2 bullet 3.
- **Estimated complexity**: low

## Integration
- **Branch**: `feat/qa-evidence`
- **Merge strategy**: sequential

## Validation
- [ ] `python3 -m pytest -n auto` passes
- [ ] `gin docs check docs/guides/qa.md` prints ok
- [ ] Each gin-qa `SKILL.md` stays under 6,000 characters

## Notes
- The user may override `Model:` and `Effort:` before plan approval.
- Deliverable merge-holds apply only to the Parent Bead; track beads close once tests and review pass.
