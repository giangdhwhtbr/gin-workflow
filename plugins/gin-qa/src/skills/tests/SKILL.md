---
name: tests
description: Write, run, and check automated tests for api, unit, integration, or other declared case types (not e2e) in the project's own test style, traced to the cases by the gin-qa CLI.
---

# Automated Tests

`/gin-qa:tests <capability> --type <type>` or `/gin-qa:tests <TC-ID>... --type <type>`. All commands are `gin-qa tests <command>`; exit 1 means findings to fix, exit 2 means wrong usage, a missing tool, or an invalid `## Automated types` section (which `check` lists as findings with exit 1).

1. Preconditions: `gin` and `gin-qa` are on `PATH` and `.agent-workflow/generated/effective-config.yaml` exists; otherwise stop and name what to install or run (`install.sh --plugin gin-qa`, `/setup`). For `e2e` use `/gin-qa:e2e`; `manual` cases have no tests.
2. Read the guidelines file (`plan --format json` names it under `guidelines`; `/gin-qa:cases` creates it). Its rules override everything below.
3. When its `## Automated types` section has no `### <type>`: find the project's test runner and where tests of this kind live (existing tests, `pyproject.toml`, `package.json`), propose the subsection to the user, and write it only after they confirm:
   ```markdown
   ### <type>
   - Tests: `<glob>`, `<glob>`
   - Run: `<runner> {files} <JUnit option>{junit}`
   ```
   The `Tests:` globs are relative to the repository root and may not be absolute or contain `..`. `{junit}` is required: it becomes the path of the JUnit XML file the runner must write (`pytest --junitxml={junit}`, `vitest run --reporter=junit --outputFile={junit}`). `{files}` is optional and a whole argument: it becomes the test files of the cases being run. The command runs from the repository root without a shell, and `{files}` paths are relative to that root. A runner option that changes folder (`uv run --directory`, `pnpm -C`) breaks `{files}`: point the runner at the project instead (`uv run --project backend pytest {files} --junitxml={junit}`) or leave `{files}` out. Then `check --type <type>` must show no declaration error.
4. `plan <capability> --type <type> --format json` gives the work: `missing`, `stale`, `orphan`. With TC-IDs, run `plan` for each one's capability (`TC-AUTH-004` is in `auth`) and keep only their rows.
5. `missing` and `stale`: take an existing test in the type's globs as the pattern (imports, fixtures, fakes, naming). For each case write, or update, a test that performs its steps with its test data and asserts its expected results:
   - its name contains the TC-ID (`test_tc_auth_004_locks_after_five_failures`, `it('TC-AUTH-004 locks the account')`): the JUnit name maps the result to the case;
   - a comment line right above it holds `TC: <TC-ID>@<hash8>` with the plan row's `hash8` (`# TC: TC-AUTH-004@1a2b3c4d`);
   - several cases may share a file, and a case may have several tests; its result is the worst of them.
   After updating a stale case's test, `pin <TC-ID>...`.
6. `orphan`: list the tests and ask the user whether to delete or keep each one. Never delete on your own.
7. `run --type <type> <capability|TC-ID...> --format json`. When a test you wrote fails, fix the test if it is wrong; if the product is wrong, keep the test and report the case as a product defect with the failing assertion. `blocked` means the test was skipped or did not run under a name holding the TC-ID: fix the name. Repeat until each case is `passed` or a reported defect.
8. `check --type <type>` must print `ok`, or list only findings outside this scope, which you report without fixing.
9. Bugs: list the cases reported as product defects and ask the user which ones to file. For each chosen case, ask for an external tracker reference as `/gin-qa:run` does (required when `## Bugs` in the guidelines says so), then run `gin-qa cases bug <TC-ID> --actual "<failing assertion>" --evidence "<JUnit file or test id from the run output>" [--external-ref "<ref>"] --run "<run folder>" --format json`. On exit 2 for the epic, offer the epics it lists, or `gin task list --type epic --json`, and run it again with `--discovered-from <bead>`. Report each bug as `<TC-ID> <bug>`, filed or kept open. Never file a bug the user did not choose.
10. Report the tests added and changed, the run folder, each case's result, the defects, and any guidelines change. Never edit `Result`, `Run`, or `Bug` lines yourself: `run` and `cases bug` write them. Do not commit; the user reviews and commits.
