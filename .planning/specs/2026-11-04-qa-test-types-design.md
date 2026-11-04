# gin-qa automated test types beyond e2e

Epic: gin-workflow-qa-test-types
Status: confirmed by the user on 2026-11-04.

## Goal and scope

Test cases of type `api`, `integration`, `unit`, or any other type a team automates get the same path e2e cases have: tests are planned from the cases, pinned to a case version, run, checked, and their results recorded in the case files.

Today only `.e2e.md` cases have tests (`plugins/gin-qa/src/scripts/gin_qa/e2e.py:43-45` selects `type == "e2e"`); gin-console's `api` cases are backend pytest tests with fakes and have no runner or skill.

In scope:
- An `## Automated types` section in `qa/guidelines.md` declaring, per type, the test globs and the run command.
- A new module `plugins/gin-qa/src/scripts/gin_qa/tests.py` and the CLI group `gin-qa tests {plan,pin,check,run}` wired in `cli.py`.
- The skill `/gin-qa:tests <capability> --type <type>`.
- `report.py`: a run folder of a non-e2e type is shown as a plain run reference.
- `templates/guidelines.md`, `templates/qa-readme.md`, `docs/guides/qa.md`, `docs/reference/cli.md`, `docs/reference/skills.md`, `docs/roles.md`; CLI `VERSION` 0.8 and plugin version 0.9.0.

Out of scope: Playwright and e2e specifics (`gin-qa e2e` is unchanged); performance or load tests; a new agent; selecting tests inside a file by name; declaring gin-console's `api` type (a follow-up in that repository).

## Requirements

Declaration
- `qa/guidelines.md` (the path from `qa.guidelines`) may hold a `## Automated types` section with one `### <type>` subsection per automated type. Each subsection has a `- Tests:` bullet with one or more backticked globs separated by commas, and a `- Run:` bullet with one backticked command:
  ```
  ## Automated types

  ### api
  - Tests: `backend/tests/**/test_*.py`
  - Run: `uv run --project backend pytest {files} --junitxml={junit}`
  ```
- `<type>` matches the case type pattern (`cases.TYPE`). `e2e` and `manual` cannot be declared. A type with no subsection is not automated, and its cases get no findings from `gin-qa tests`.
- Globs use `cases.glob_regex` and are relative to the repository root.
- The command must contain `{junit}`; `{files}` is optional. It is split with `shlex.split` and run without a shell, from the repository root. Each token equal to `{junit}` becomes the absolute path of the run's JUnit file. Each token equal to `{files}` becomes the selected test files, one argument per file. A placeholder inside a longer token (`--junitxml={junit}`) is replaced in place; `{files}` inside a longer token is a declaration error.
- Declaration errors (missing `Tests:` or `Run:`, no glob, no `{junit}`, a declared `e2e` or `manual`, a duplicate type, `{files}` inside a longer token) are findings of `tests check` and make every other `tests` command exit 2.

Link between case and test
- Marker: any line of a file matching the type's globs that contains `TC: <TC-ID>@<hash8>`, whatever comment syntax precedes it (`#`, `//`, `--`). One case may have markers in several files or several places; each marker counts.
- Test name: a JUnit `testcase` whose `name` or `classname` contains the TC-ID belongs to that case. Matching ignores case and treats `_` as `-`, so `test_tc_milestone_ui_021_open_milestone` belongs to `TC-MILESTONE-UI-021`.

`gin-qa tests plan [capability] [--type T]`
- Over the declared types (or only `T`), and the cases of `capability` when given, it returns:
  - `missing`: a case of the type with no marker in the type's test files;
  - `stale`: a marker whose hash8 differs from `cases.hash8` of its case, with file and line;
  - `orphan`: a marker naming a TC-ID that is not a case of that type (gone, or now another type), with file and line. A marker of a case of another declared type whose globs also cover the file belongs to that type and is not an orphan.
- `--format json` returns `{"types": {...}, "guidelines": <path>, "missing": [...], "stale": [...], "orphan": [...]}`; each row carries `tc`, `type`, `hash8`, and `case` (`cases.as_dict`) or `file` and `line`.

`gin-qa tests pin <TC-ID>...`
- Rewrites the hash8 of every marker of each case to its current hash8. A case with no marker, or that is not of a declared type, is an error, and nothing is written.

`gin-qa tests check [--type T]`
- Findings: declaration errors, then `missing`, `stale`, and `orphan` rows, each as `file:line: message` with the fix (`write the test with /gin-qa:tests <cap> --type <T>`, `update the test, then gin-qa tests pin <TC-ID>`).

`gin-qa tests run --type T [TC-ID|capability ...]`
- Selection: all cases of `T` that have a marker, or those named by TC-ID or capability. A TC-ID that is not a `T` case with a marker, or a capability with no such case, exits 2.
- `{files}` becomes the files holding markers of the selected cases, sorted and deduplicated. Without `{files}` in the command, the whole command runs and results are recorded only for the selected cases.
- Evidence: a new folder `<evidence root>/<UTC stamp>-<T>/` (the stamp and `-2` suffix rule of `e2e run`), holding `run.json` (`type`, `started`, `command` as run, `cases` selected, `exit`) and `junit.xml` (the `{junit}` path).
- The JUnit file is read with `xml.etree.ElementTree`, `testsuites` or a single `testsuite` at the root. For each `testcase`: a `failure` or `error` child gives `failed`, a `skipped` child gives `blocked`, otherwise `passed`. A case takes the worst of its test cases (`failed`, then `blocked`, then `passed`).
- A selected case with no matching test case is recorded `blocked` with the finding `<TC-ID>: no test named after it ran`. When `junit.xml` is missing or unreadable, every selected case is recorded `blocked` with one finding naming the file.
- Each selected case gets `cases.record_result(..., status, run=<folder>)`; a write error is a finding and the other cases are still recorded.
- Output: `--format json` `{"run": <folder>, "exit": <code>, "findings": [...], "recorded": [{"tc", "result"}]}`; text lists findings, `<TC-ID> <result>` lines, and `run: <folder>`. The command's output goes to stderr. Exit: the command's non-zero exit, else 1 when there are findings, else 0. A command that cannot start (not found) exits 2.

Report
- `gin-qa report` treats a `Run` folder whose `run.json` has a `type` key as a plain run reference: the case shows its result and `Run` with no evidence and no `evidence not found` note.

Skill `/gin-qa:tests <capability> --type <T>`
- Reads `qa/guidelines.md`. When `T` is not declared, it finds the project's test runner and an existing test folder, proposes the `### <T>` subsection, and writes it after the user confirms.
- Runs `gin-qa tests plan <capability> --type <T>`. For each missing or stale case it takes an existing test in the type's globs as the pattern (imports, fixtures, fakes), writes or updates one test per case named after the TC-ID with the marker line, then `gin-qa tests pin`.
- Runs `gin-qa tests run --type <T> <capability>` and `gin-qa tests check --type <T>`, fixes the tests it wrote until both are clean or a failure is a product bug, and reports results per case.
- It never edits case files directly; results are written only by `tests run`.

## User Stories

### US-1: Declare an automated type
As a QA lead, I want to declare in `qa/guidelines.md` where a type's tests live and how they run, so that gin-qa can plan and run them with the project's own runner.

Acceptance criteria:
- A `### api` subsection with `Tests:` and `Run:` makes `api` cases appear in `gin-qa tests plan`.
- A subsection without `{junit}` in `Run:`, or a declared `e2e`, is a `gin-qa tests check` finding and makes `gin-qa tests run` exit 2.
- A type without a subsection produces no `gin-qa tests` findings.

### US-2: See which tests to write or update
As a developer, I want `gin-qa tests plan` to list cases without a test, tests pinned to an old case version, and tests of removed cases, so that I know what to change.

Acceptance criteria:
- An `api` case with no `TC:` marker in the type's files is listed as `missing`.
- After the case text changes, its marker is listed as `stale` with file and line; `gin-qa tests pin <TC-ID>` clears it.
- A marker naming a deleted case, or a case now of another type, is listed as `orphan`.
- `gin-qa tests check` reports the same rows as findings and exits 1, or prints `ok` and exits 0.

### US-3: Run the tests and record results
As a QA engineer, I want `gin-qa tests run --type api [capability]` to run the declared command and write each case's result, so that case files show the latest automated result.

Acceptance criteria:
- A passing, a failing, and a skipped test named after three cases record `passed`, `failed`, and `blocked`, each with `Run` set to the run folder.
- A case with two tests, one failing, records `failed`.
- A selected case whose test did not run records `blocked` with a finding.
- With `{files}` in the command, only the files holding markers of the selected cases are passed to it.
- The run folder holds `run.json` and `junit.xml`; the exit code is the command's, or 1 on findings.

### US-4: Have the agent write the tests
As a developer, I want `/gin-qa:tests <capability> --type <T>`, so that missing tests are written in the project's own style and run.

Acceptance criteria:
- The skill writes tests that follow an existing test in the type's globs, each with a `TC:` marker and a name containing the TC-ID.
- At the end `gin-qa tests check --type <T>` is clean, and the per-case results come from `gin-qa tests run`.

### US-5: Report shows non-e2e results
As a QA lead, I want the report to show results of `api` runs without false warnings, so that the report stays accurate as more types are automated.

Acceptance criteria:
- A case whose `Run` is a `tests run` folder shows its result and `Run` and no `evidence not found` note, and the folder is not listed in `missing_evidence`.

## Errors and compatibility

- Exit codes follow the gin-qa convention: 0 ok, 1 findings, 2 usage or environment error.
- `gin-qa e2e`, `gin-qa cases`, and existing case files are unchanged. A `guidelines.md` without `## Automated types` keeps working; `tests plan` returns nothing.
- The run command comes from a file in the repository, with the same trust as a `package.json` script; it runs without a shell, so no shell expansion of case or path text happens.
- `junit.xml` is parsed with the standard library only; no new dependency.
- Windows: no shell, paths passed as arguments, `{junit}` as an absolute path.

## Testing

- pytest in `tests/gin_qa/test_tests_cli.py`, with the fixtures of `tests/gin_qa/qa_fixtures.py`:
  - the declaration parser: valid section, each declaration error, no section;
  - `plan`, `pin`, `check`: missing, stale, orphan, multiple markers for one case, capability and `--type` filters;
  - `run` with a fake command (a Python script) that writes a JUnit file: passed, failed, error, skipped, two tests for one case, no matching test, no JUnit file, `{files}` expansion, command not found;
  - `report` with a case whose `Run` is a `tests run` folder (`tests/gin_qa/test_report.py`).
- `python3 -m pytest -n auto` passes.
