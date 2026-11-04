# Test case guidelines

Rules for writing test cases in this repository. `/gin-qa:cases` reads this file first; its rules override the skill's defaults. `/gin-qa:setup` fills in the `Language:` line and the `Types`, `Automated types`, `Manual runs`, and `Bugs` sections from an interview. Edit freely.

- Language: not set yet (the language test cases are written in).
- One user action per step.
- Type: the file suffix of a case (`.e2e.md`, `.manual.md`), one of the types under `## Types`.
- `Priority: high | medium | low`.
- Extra fields this team uses (kept and exported as-is): none yet.

## Types

The case types this repository uses. `gin-qa cases check` reports a case whose type is not listed here.

- `e2e`: cases a browser test can run (`/gin-qa:e2e`).
- `manual`: cases a tester walks through (`/gin-qa:run`).

## E2E specs (`/gin-qa:e2e`)

- Playwright: `@playwright/test` 1.49 or later (the evidence fixture records ARIA snapshots).
- Locators: prefer `getByRole` with the accessible name; use `getByTestId` only when no stable name exists.
- Sign-in: none yet (describe how specs sign in, e.g. a `storageState` file or a sign-in step).
- Test data: none yet (shared users and records specs may rely on; data one case needs goes in its `Test data` section).

## Automated types

Case types other than e2e whose tests `gin-qa tests` plans and runs (`/gin-qa:tests`). One `### <type>` per type; `Tests:` globs are relative to the repository root, never absolute or containing `..`; `{junit}` is the JUnit XML file the command writes, `{files}` (optional) the test files of the cases run. For example:

    ### api
    - Tests: `backend/tests/**/test_*.py`
    - Run: `pytest {files} --junitxml={junit}`

None yet.

## Manual runs

How `/gin-qa:run` names and schedules manual runs.

- Run reference: `manual <YYYY-MM-DD>` (the date is the run's UTC date).
- When: not set yet (for example, before each release).

## Bugs

- Tracker: Beads. `gin-qa cases bug` files each failed manual case as a bug bead linked to the case's epic.
- External reference: none (`optional`, or `required` with an optional pattern as a regular expression, such as ``required, pattern `PROJ-\d+` ``; `/gin-qa:run` then asks for it on each failure).
