# QA

This folder holds the test cases and end-to-end specs for this repository.

- `cases/`: one folder per capability, one file per test case.
- `e2e/`: Playwright specs, one per `e2e` case.
- `evidence/`: run folders written by `gin-qa e2e run` and `gin-qa tests run`; `gin-qa e2e init` git-ignores it (without e2e, add `qa/evidence/` to `.gitignore`).
- `guidelines.md`: the team rules for writing cases and specs.

## Case files

A case file is named `TC-<CAP>-NNN[-<slug>].<type>.md` and sits in `cases/<capability>/`.

- `TC-<CAP>-NNN` is the case ID; `<CAP>` is the capability in upper case.
- `<slug>` is optional and only helps readers; renaming the title does not require a new name.
- `<type>` is the test type, such as `e2e` or `manual`; the guidelines list the types in use.
- Each file holds one case. Get the next ID with `gin-qa cases next-id <capability>`.

## Case format

- Fields: `REQ`, `Priority`, any extra fields the guidelines name, and `Result`, `Run`, `Bug`.
- Sections, in this order: `Preconditions` (optional), `Test data` (optional), `Steps` (numbered), `Expected` (bullets).
- `Test data` lists the records and values the case needs, as a value or a rule.
- Credentials appear only as the name of an environment variable, never as a value.

## Results

- `Result` is one of `passed`, `failed`, `blocked`, `not run`.
- `Run` points to the evidence and `Bug` names the bug the result found.
- Change these lines only with `gin-qa cases result <TC-ID> <status> [--run <ref>] [--bug <id>|none]`.
- `gin-qa e2e run` and `gin-qa tests run` record the automated results.

## Process

- Cases: `/gin-qa:cases <capability>` writes the cases of a capability from its spec.
- Tests: `/gin-qa:e2e <capability>` builds the specs of `e2e` cases; `/gin-qa:tests <capability> --type <type>` builds the tests of each type under `Automated types` in the guidelines.
- Manual runs: `/gin-qa:run <capability>` walks the `manual` cases with a tester. When: not set yet.
- Bugs: each failed manual case becomes a bug bead linked to the case's epic. External reference: none.
- Report: `/gin-qa:report [capability]` writes an HTML report to zip and share. When and to whom: not set yet.

## Commands

- `gin-qa cases next-id <capability>`: the next case ID.
- `gin-qa cases check`: finds problems in the case files.
- `gin-qa cases result <TC-ID> <status>`: records a result.
- `gin-qa cases split <capability>`: turns a flat `<capability>.md` file into case files.
- `gin-qa cases export --format json`: lists every case with its fields and result.
- `gin-qa e2e run [TC-ID|capability]`: runs the specs and records their results.
- `gin-qa tests run --type <type> [TC-ID|capability]`: runs the tests of a type the guidelines declare under `Automated types` and records their results.
