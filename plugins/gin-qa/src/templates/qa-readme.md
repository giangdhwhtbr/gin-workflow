# QA

This folder holds the test cases and end-to-end specs for this repository.

- `cases/`: one folder per capability, one file per test case.
- `e2e/`: Playwright specs, one per `e2e` case.
- `evidence/`: run folders written by `gin-qa e2e run`; git-ignored.
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
- `gin-qa e2e run` records the automated results.

## Commands

- `gin-qa cases next-id <capability>`: the next case ID.
- `gin-qa cases check`: finds problems in the case files.
- `gin-qa cases result <TC-ID> <status>`: records a result.
- `gin-qa cases split <capability>`: turns a flat `<capability>.md` file into case files.
- `gin-qa cases export --format json`: lists every case with its fields and result.
- `gin-qa e2e run [TC-ID|capability]`: runs the specs and records their results.
