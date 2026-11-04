# Case files per test case, readable format, recorded results

Epic: gin-workflow-qa-case-folders
Status: draft for user review.

## Goal and scope

Today a capability's test cases live in one file, `qa/cases/<capability>.md`, with the type in a `Type:` field and no place for a result (`plugins/gin-qa/src/scripts/gin_qa/cases.py:103-124`). Testers asked for one case per file, a format that reads well when rendered, a place to describe test data, and the latest result recorded in the case itself. After this change each case is its own file, `qa/cases/<capability>/TC-<CAP>-NNN-<slug>.<type>.md`; the file name sets the type; each case carries `Result`, `Run`, and `Bug` lines written only by `gin-qa cases result`; and `gin-qa e2e run` records every case it ran.

In scope:
- The per-case layout and a readable case format (bold field labels, bold section labels, a `Test data` section), with the flat `<capability>.md` file still parsed.
- `cases.py`: loader, `Case.type`, `next-id` across files and git history, `hash8` and export rules for the new parts.
- `gin-qa cases result` (the only write path for results) and `gin-qa cases split` (flat file to per-case files).
- `gin-qa e2e run` records the worst result per case.
- Templates `cases.md`, `guidelines.md`, and a new `qa-readme.md`; the `cases` and `e2e` skills and `explore-case.md`; `docs/guides/qa.md`, `docs/guides/customizing-templates.md`, `docs/reference/cli.md`; a version bump.

Out of scope: runners for non-e2e types; a manual-run skill (epic `gin-workflow-qa-manual-bugs`); the report (epic `gin-workflow-qa-report`, now an interactive HTML report), which reads the export fields this epic adds.

Decided with the user on 2026-11-04:
- One file per case, the type as the last name part before `.md` (`.e2e.md`, `.manual.md`, `.api.md`), not one file per type.
- Migration through a `split` command, not a silent dual layout.
- A result recorded without `--bug` keeps the existing `Bug` line.
- Field and section labels in bold; fields as `- ` list items so rendered Markdown keeps one field per line.
- A `Test data` section modelled on QFO-AT's scenarios: the data a case needs, described in words; credentials only as environment variable names.
- `e2e run` records results on every run; no `--no-record` flag (per-case files remove concurrent writes to one file).

## Requirements

### R1. Per-case layout

A capability's cases live in `<cases>/<capability>/`, where `<cases>` is the effective `qa.cases` folder. Each case is one file named `<TC-ID>[-<slug>].<type>.md`:

- `<TC-ID>` is `TC-<CAP>-NNN` and must equal the ID in the file's heading; `<CAP>` lower-cased must equal the folder name.
- `<slug>` is optional, `[a-z0-9]+(-[a-z0-9]+)*`, for readers only; renaming the case title does not require renaming the file.
- `<type>` matches `[a-z][a-z0-9-]*`. Any type is accepted; guidelines list the ones a team uses.

Example: `qa/cases/auth/TC-AUTH-001-sign-in.e2e.md`.

The file holds exactly one case whose heading is `# TC-<CAP>-NNN: <title>`. Other files in the folder (not ending in `.md`) are ignored.

The flat file `<cases>/<capability>.md` keeps working unchanged: `### ` blocks, type from its `Type:` field.

### R2. Case format

```markdown
# TC-AUTH-001: Sign in with a valid password

- **REQ:** REQ-AUTH-001@1a2b3c4d
- **Priority:** high
- **Result:** passed
- **Run:** qa/evidence/2026-11-04T10-00-00

**Preconditions:**
- user alice@example.com exists

**Test data:**
- Email: alice@example.com
- Password: environment variable `E2E_ALICE_PASSWORD`

**Steps:**
1. Open /login
2. Fill "Email" with the email from Test data

**Expected:**
- The dashboard is shown
```

- A field line is `Key: value`, optionally wrapped as `- **Key:** value`. Both forms are parsed in both layouts; a file may mix them.
- A section label is `Name:` or `**Name:**`. Sections, in this order: `Preconditions` (optional), `Test data` (optional), `Steps` (required, numbered), `Expected` (required). `Preconditions`, `Test data`, and `Expected` items are `- ` bullets.
- `Test data` describes the records and values the case needs: a literal value or a rule ("a unique 15-digit IMEI per run", "the first active brand"). Credentials appear only as environment variable names; the `cases` skill never writes a secret value.
- The parsed content does not depend on the form: a case rewritten from plain to bold labels has the same `hash8` and export.

### R3. Type and the `Case` model

`Case` gains `type: str` and `test_data: list[str]`.

- Per-case file: `type` comes from the file name. A `Type:` field there is a `check` finding: `<file>:<line>: <TC-ID>: Type comes from the file name; remove the Type: line`.
- Flat file: `type` is the `Type:` field lower-cased and stripped, or empty.
- `e2e.py` selects e2e cases by `case.type == "e2e"`; `as_dict` exports `type` from `case.type`.

### R4. Loader and `check`

`load()` reads every flat `<cases>/*.md` and every `<cases>/*/*.md`. Besides the current findings, `check` reports:

- a file name in a capability folder that does not match R1;
- a TC-ID in the file name that differs from the heading, or a capability folder that differs from the ID's `<CAP>`;
- a per-case file holding no case, more than one case, or a heading that is not `# TC-…: <title>`;
- a capability that has both `<cases>/<capability>.md` and `<cases>/<capability>/`: `<cases>/<capability>.md: capability also has folder <cases>/<capability>/; run gin-qa cases split <capability>`;
- a `Type:` line in a per-case file (R3);
- a `Result:` value other than `passed`, `failed`, `blocked`, `not run`;
- a `Run:` or `Bug:` line without a `Result:` line.

Duplicate TC-IDs across all files stay a finding. The `test_globs` probe in `_check` covers the per-case files.

### R5. `next-id`

`gin-qa cases next-id <capability>` returns one more than the highest number for that capability found in:

- the flat file's current text and its git history (as today);
- the file names under `<cases>/<capability>/`;
- every file name that path ever held: `git log --format= --name-only -- <cases>/<capability>`.

So an ID is never reused after its file is deleted or after `split`.

### R6. Result fields

`Result`, `Run`, and `Bug` are the latest outcome of the case:

- `Result`: `passed | failed | blocked | not run`.
- `Run`: where the evidence is (an e2e run folder, or any reference a tester gives).
- `Bug`: the tracker ID of the bug the result found.

They are left out of `hash8` and out of export `fields`. Export gains top-level `result` (`not run` when the case has no `Result:` line), `run`, `bug` (empty strings when absent), and `test_data` (list). `hash8` includes `Test data:` and its items only when the section has items, so every existing case keeps its `hash8` and every e2e spec pin stays valid.

### R7. `gin-qa cases result`

`gin-qa cases result <TC-ID> <status> [--run REF] [--bug ID|none]` is the only command that writes these fields.

- Exit 2, writing nothing, when: the TC-ID does not exist; the status is not one of the four; a value contains a newline or control character; the case files have parse findings for that case.
- `Result` is set to the status. `Run` is set to `REF`, or its line removed when `--run` is absent. `Bug` changes only with `--bug`: set to `ID`, or removed with `--bug none`.
- Lines are kept in the order `Result`, `Run`, `Bug`, directly after the last other field line; existing result lines are replaced in place.
- New lines take the form of the case's other field lines: `- **Key:** value` when its last field line uses it, `Key: value` otherwise. `pin` likewise replaces only the value of the `REQ:` line and keeps its form.
- Works for flat and per-case files. Output: `TC-AUTH-001 passed` (text) or `{"tc", "result", "run", "bug", "file"}` (json).

### R8. `gin-qa cases split`

`gin-qa cases split <capability>` turns `<cases>/<capability>.md` into per-case files:

1. Parse the flat file. Refuse (exit 1, list every finding, write nothing) when: it has parse findings; any case lacks `Type:` or has a type not matching R1; the file holds anything other than its `# ` title line, blank lines, and case blocks (prose or `## ` sections would be lost); a target file already exists.
2. For each case, write `<cases>/<capability>/<TC-ID>-<slug>.<type>.md`, where `<slug>` is the title lower-cased, runs of non-`[a-z0-9]` replaced by `-`, trimmed, cut at 40 characters on a `-` boundary (no slug when empty). The content is the case block verbatim, with the heading `### ` turned into `# ` and the `Type:` line removed.
3. Delete the flat file. Output lists the files written.

Every split case keeps its `hash8`, so e2e specs stay pinned. `split` does not restyle labels; plain-label cases stay valid.

### R9. `gin-qa e2e run` records results

After Playwright exits, `run` calls the R7 writer once per case in the run, with `--run <run folder>`:

- The case's status is the worst over its result folders (one per Playwright project): `failed` over `blocked` over `passed`. A missing or invalid `result.json` counts as `blocked`. A case with no result folder at all is `blocked`.
- A recording error (e.g. the case was deleted mid-run) is added to the run's findings; it does not stop the other cases.
- The JSON output gains `recorded`: `[{"tc", "result"}]`.

The `/gin-qa:e2e` skill step 5 allows changes to the `Result`/`Run` lines of the cases in scope, besides their spec files.

### R10. Templates, skills, docs, version

- `templates/cases.md`: one per-case file in the R2 form.
- `templates/qa-readme.md` (new): the `qa/` tree, the file naming rule, the field and section meanings, the result values, and the commands (`next-id`, `check`, `result`, `split`, `export`, `e2e run`). The `cases` skill writes it as `README.md` next to the guidelines file when that file does not exist, as it does for `guidelines.md`.
- `templates/guidelines.md`: the type line names file suffixes (`.e2e.md` for cases a browser test can run, `.manual.md` otherwise); the test data line says shared accounts and records go here, case-specific data in the case's `Test data`.
- `skills/cases/SKILL.md`: the per-case layout and format, `Test data` rules, `split` for an existing flat file, `result` as the only way to change result lines.
- `skills/e2e/SKILL.md` and `references/explore-case.md`: `Test data` items are built in the spec (or a fixture) before step 1; step 5 per R9; runs record results.
- `docs/guides/qa.md`, `docs/guides/customizing-templates.md`, `docs/reference/cli.md`: layout, format, `result`, `split`, recording.
- gin-qa `0.6.0` → `0.7.0` (`plugin.meta.json`, both `plugin.json`), launcher `VERSION` `0.5` → `0.6`, per `docs/contributing.md` Release step 1.

## User Stories

### US-1: One file per test case
As a tester, I want each test case in its own file named by ID and type, so that reviews, history, and recorded results touch only that case.

Acceptance criteria:
- `qa/cases/auth/TC-AUTH-001-sign-in.e2e.md` is loaded with type `e2e` and appears in `cases export`.
- A per-case file whose name ID differs from its heading is a `check` finding.
- `next-id auth` never returns the ID of a deleted case file.

### US-2: Readable case format with test data
As a tester, I want bold field and section labels and a `Test data` section, so that a rendered case is easy to read and states the data it needs.

Acceptance criteria:
- A case in the R2 form parses with its fields, test data, steps, and expected items.
- The same case in plain labels has the same `hash8` and export.
- A case without `Test data` keeps the `hash8` it had before this change.

### US-3: Record a result
As a tester, I want one command that records a case's result, run, and bug, so that the case file always shows its latest outcome in a fixed form.

Acceptance criteria:
- `cases result TC-AUTH-001 failed --run R --bug B` adds `Result`, `Run`, `Bug` lines after the last field, in the case's label form.
- A later `cases result TC-AUTH-001 passed` replaces `Result`, removes `Run`, and keeps `Bug`.
- An unknown status or a multi-line value exits 2 and leaves the file unchanged.

### US-4: Move a flat file to per-case files
As a tester with an existing `<capability>.md`, I want `cases split`, so that I adopt the new layout without retyping cases or breaking e2e pins.

Acceptance criteria:
- `split milestone-ui` on a valid flat file writes one file per case, deletes the flat file, and `check` passes.
- Every split case has the same `hash8` as before.
- A case without `Type:`, extra prose, or an existing target file makes `split` exit 1 and write nothing.

### US-5: e2e runs record their outcome
As a tester, I want `gin-qa e2e run` to record each case's result, so that the case files reflect the last automated run without manual copying.

Acceptance criteria:
- A run where one Playwright project fails a case records `failed` with `Run` set to the run folder.
- A case without `result.json` is recorded `blocked`.
- The JSON output lists `recorded` per case.

## Errors and compatibility

- Flat files keep parsing, and `Type:`-based selection keeps working for them; nothing forces a migration. A capability in both layouts is a `check` finding, not a load error, so other capabilities keep working.
- `hash8` is unchanged for every existing case (R2, R6), so no e2e spec becomes stale from this release.
- `cases export` keeps its existing keys; `result`, `run`, `bug`, `test_data` are added. Consumers that ignore unknown keys are unaffected.
- `e2e run` now edits committed case files (`Result`/`Run` lines). Exploration runs record too; the last run wins, and `/gin-qa:e2e` ends with the official run, so the committed result is that run's.
- `cases result` and `split` write files only after every check passes; a failed command leaves the tree unchanged.

## Testing

CLI-level tests under `tests/gin_qa/`, using temporary repositories as the existing tests do:

- Loader: per-case files (bold and plain labels), flat files, mixed repository; `type` from file name and from `Type:`; `test_data` parsed and exported.
- `check`: each new finding in R4.
- `hash8`: plain vs bold form equal; no `Test data` keeps the old value; `Result`/`Run`/`Bug` do not change it.
- `next-id`: across per-case files, a deleted file in git history, and the flat file.
- `result`: add, replace, remove `Run`, keep and remove `Bug`, form follows the case, flat-file case, each exit-2 case leaving the file unchanged.
- `pin`: keeps the bold form of the `REQ` line.
- `split`: success with `hash8` preserved and `Type:` removed; each refusal writes nothing.
- `e2e run` with the existing fake `npx`: worst result across two projects, missing `result.json` gives `blocked`, `recorded` in the output.
- Existing smoke and docs-coverage tests updated for the new commands and version.
