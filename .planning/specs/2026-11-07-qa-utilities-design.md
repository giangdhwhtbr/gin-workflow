# gin-qa utilities: move a flaky e2e case to manual, keep re-run evidence, and remove tester chores

Epic: gin-workflow-uj96
Status: draft for user review.

## Goal and scope

Testers do small file and shell chores around gin-qa by hand, one of them loses data, and there is no supported way to take a flaky e2e case off the pipeline:
- a failed manual re-run of a case whose bug is still open drops the actual result and evidence the tester gave (`bugs.py:101-105`); the `run` skill only warns about it;
- `gin-qa tests run` and `gin-qa report` write under the evidence folder, but only `gin-qa e2e init` git-ignores it (`e2e.py:173-178`);
- a case file is written by hand after `next-id`, then pinned;
- a report is zipped by hand (`skills/report/SKILL.md:13`);
- `gin-qa e2e init` prints the Playwright install steps instead of running them (`e2e.py:188-191`), and an older `evidence.ts` gets the `ariaSnapshot` block by hand (`skills/e2e/references/explore-case.md:31-46`);
- when an e2e test keeps failing or flaking on the pipeline, QA has no command to walk that case by hand instead, and the report does not show which cases left automation or why.

This spec adds:
- `gin-qa cases to-manual`, and a report section for moved cases;
- re-run evidence appended to the open bug by `gin-qa cases bug`;
- the evidence folder git-ignored by `tests run` and `report`;
- `gin-qa cases new`;
- `gin-qa report --zip`;
- `gin-qa e2e init --install`, and the `ariaSnapshot` merge.

Decisions confirmed with the user:
- All five items of the epic stay in scope, plus the move to manual.
- Moving a case deletes its spec: the pipeline stops running it at once, and git history keeps the file.
- The move is one command plus one field in the case, not a skill-only rule and not a separate history file.

Assumptions:
- QA decides when a case moves. gin-qa does not count failures, because pipeline history lives outside the repository.
- A moved case starts as `not run`: an e2e result is not a manual result.

Out of scope:
- Moving a case back to e2e with a command. The tester renames the file, removes the `Moved from e2e:` line, and runs `/gin-qa:e2e`.
- Moving a case of a type other than e2e.
- Copying `.claude/skills/<name>-qa/` to other harnesses.

## Requirements

### R1. `gin-qa cases to-manual`
Usage: `gin-qa cases to-manual <TC-ID> --reason <text> [--repository PATH] [--format text|json]`.
- Exit 2 and change nothing when:
  - the case does not exist, or its type is not `e2e`;
  - `--reason` is empty or holds a line break;
  - `manual` is not listed under `## Types` of the guidelines;
  - the case is in a flat `<cases>/<capability>.md` file (the message says to run `gin-qa cases split <capability>`).
- The command renames `<TC-ID>[-<slug>].e2e.md` to `<TC-ID>[-<slug>].manual.md`. The ID, `REQ:`, and `Bug:` stay.
- It writes `Moved from e2e: <YYYY-MM-DD>: <reason>` with today's UTC date, sets `Result: not run`, and removes `Run:`. `Result:` stays as a line because `cases check` refuses a `Bug:` without one (`cases.py:106-108`).
- It deletes `spec_path(eff, case)` (`e2e.py:52`). A missing spec is not an error; the output says so.
- `Moved from e2e` joins `KNOWN_FIELDS` (`cases.py:26`), so `hash8` does not change with it.
- It does not commit.
- Output: text prints the new case path, then the deleted spec or `no spec`; json prints `{"tc", "file", "spec"}` with `spec` null when there was none.

### R2. Report of moved cases
- `as_dict` (`cases.py:418`) gains `moved_from_e2e`: `{"date", "reason"}`, or null without the field.
- A `Moved from e2e:` value that is not `<YYYY-MM-DD>: <reason>` is a `gin-qa cases check` finding.
- `report.html` shows a section "Moved from e2e to manual" when at least one case in scope has the field: one row per case with the TC-ID, title, date, reason, and current result (`passed`, `failed`, `blocked`, or `not run`).
- Each such case carries a label in the main case list.
- `gin-qa report --format json` adds `moved`, the number of such cases.

### R3. Re-run evidence on an open bug
- When `gin-qa cases bug` keeps an open bug, it appends one line to the bead's notes with `gin task update <bug> --append-notes`: the UTC date, `Run:` when known, `Actual:`, and `Evidence:`, joined by `; `. The bead description is unchanged.
- The note holds no line break and no double quote, because a Windows `.cmd` shim cuts an argument at its first newline (`bugs.py:115`) and re-parses quotes; a double quote becomes a single quote.
- The notes are written before the case result. When the update fails, the command exits 2 and the case file is unchanged, so the tester can run it again.
- The json result gains `appended`: true when notes were written, false for a new bug.

### R4. Evidence folder ignored without e2e
- The `.gitignore` code of `e2e init` moves to one function in `e2e.py`, called by `e2e init`, `gin-qa tests run`, and `gin-qa report`.
- An existing entry is not written again.
- `report --out` with a folder outside the evidence folder does not touch `.gitignore`.

### R5. `gin-qa cases new`
Usage: `gin-qa cases new <capability> --type <type> --title <text> (--req <REQ-ID>... | --source <path>) [--repository PATH] [--format text|json]`.
- The SDD layout takes `--req` (repeatable); the legacy layout takes `--source`, because a legacy case needs `Source:` (`cli.py:136`). The other flag exits 2.
- Exit 2 and write nothing when the type is not listed under `## Types`, a REQ does not exist, the title is empty or holds a line break, or the capability has a flat cases file.
- The ID comes from `next_id` (`cases.py:230`); the file is `<cases>/<capability>/<TC-ID><_slug(title)>.<type>.md` (`cases.py:371`).
- The file holds the heading, the `REQ:` field pinned to the current hashes or the `Source:` field, `Priority: medium`, and the empty section headings of the `cases.md` template.
- `gin-qa cases check` may report the new case as incomplete until its steps and expected results are written.
- Output: text prints the path; json prints `{"tc", "file"}`.

### R6. `gin-qa report --zip`
- After the report folder is written, the command also writes `<folder>.zip` next to it, with the Python standard library. The folder stays.
- The archive holds `index.html` and every screenshot.
- Output adds `zip`, the path of the archive.
- A write failure exits 2 and leaves no partial archive.

### R7. `gin-qa e2e init --install`
- Without the flag, `e2e init` behaves as today.
- With it, the command installs `@playwright/test` and chromium and adds `"e2e": "playwright test"` to the `package.json` scripts when missing. Packages already installed are not installed again.
- The package manager comes from the lockfile: `pnpm-lock.yaml`, then `yarn.lock`, else npm.
- A failed install exits 2 and prints the error and the commands to run by hand.
- A repository without `package.json` exits 2 with a message saying so.

### R8. `ariaSnapshot` merge
- When `<e2e>/evidence.ts` exists without `ariaSnapshot`, `e2e init` inserts the snapshot block and the `snapshot` and `url` fields, only when the anchors of the template are found exactly.
- When an anchor is not found, the file is unchanged and the output points to the manual steps in `explore-case.md`.
- The merged file writes the same `result.json` shape as the template.

### R9. Skills and docs
- `cases` skill: uses `gin-qa cases new`; step 5 keeps the format rules.
- `run` skill: step 5 no longer says a kept bug misses the new result.
- `report` skill: step 4 uses `--zip`.
- `e2e` skill: uses `--install`, and names `gin-qa cases to-manual` for a case that keeps failing or flaking on the pipeline. `explore-case.md` says when the merge is automatic.
- `docs/guides/qa.md` and `qa.vi.md`: all commands above; the move to manual and how to go back; line 84 updated. `plugins/gin-qa/src/templates/qa-readme.md` line 7 updated. `docs/reference/cli.md`, or the gin-qa CLI reference it links to, lists the new commands and flags.

## User Stories

### US-1: QA moves a flaky e2e case to manual
As a QA, I want one command that moves a flaky e2e case to manual with a reason, so that the pipeline stops failing on it and the case is still tested.

Acceptance criteria:
- `gin-qa cases to-manual TC-X-001 --reason "flaky on CI"` renames the case to `.manual.md`, writes the `Moved from e2e:` line, sets `Result: not run`, removes `Run:`, and deletes the spec.
- After it, `gin-qa cases check` and `gin-qa e2e check` report nothing about that case, also when the case keeps a `Bug:` line.
- `/gin-qa:run` lists the case as a manual case and records its result.
- A case of another type, an empty reason, or a missing `manual` type exits 2 and changes nothing.

### US-2: The report shows what left automation
As a QA lead, I want the report to show which cases moved from e2e to manual, why, and their status, so that I can see what automation no longer covers.

Acceptance criteria:
- A moved case appears in the section "Moved from e2e to manual" with its date, reason, and current result.
- After the tester records `passed`, the section shows `passed`.
- A report with no moved case has no such section.

### US-3: A re-run keeps its evidence
As a tester, I want a repeated failure added to the bug that is still open, so that the new result and evidence are not lost.

Acceptance criteria:
- A failed re-run of a case with an open bug appends the actual result and evidence to the bead's notes.
- A failed notes update exits 2 and leaves the case file unchanged.

### US-4: Evidence stays out of git without e2e
As a tester on a repository with no e2e cases, I want the evidence folder ignored, so that I do not commit run output by accident.

Acceptance criteria:
- `gin-qa tests run` adds `/qa/evidence/` to `.gitignore`, once.
- `gin-qa report` does the same for a report under the evidence folder.

### US-5: A new case starts correct
As a tester, I want a command that creates a case file, so that its name, ID, and pin are right from the start.

Acceptance criteria:
- `gin-qa cases new orders --type manual --title "Cancel an order" --req REQ-ORDERS-001` creates a correctly named, pinned file with the next ID.
- An unknown type or REQ exits 2 and writes nothing.

### US-6: A report is ready to share
As a tester, I want a zip of the report, so that I can send it without packing the right folder by hand.

Acceptance criteria:
- `gin-qa report --zip` writes `<folder>.zip` with `index.html` and the screenshots, and prints its path.

### US-7: e2e setup runs in one step
As a tester, I want `e2e init` to install what it needs, so that I do not copy commands, and an older fixture gets step snapshots safely.

Acceptance criteria:
- `gin-qa e2e init --install` installs with the manager of the lockfile and adds the `e2e` script.
- `gin-qa e2e init` without the flag installs nothing.
- An older `evidence.ts` matching the template anchors gets the snapshot block; any other one stays unchanged and the output names the manual steps.

## Errors and compatibility
- Usage and validation errors exit 2 with a message on stderr, like the other `gin-qa` commands; `cases check` findings exit 1.
- `to-manual` validates everything before it writes. It writes the case first and deletes the spec last, so a failed delete leaves a spec that `e2e check` reports as an orphan.
- Existing case files stay valid; a missing `Moved from e2e:` line means the case never moved.
- `hash8` values do not change.
- The new json keys are additions; existing keys keep their meaning.
- `e2e init` can now change an older `evidence.ts`. It does so only on an exact anchor match.

## Testing
- `tests/gin_qa/test_cases_cli.py`: `to-manual` success, each refusal with nothing changed, a missing spec, an unchanged `hash8`, a malformed `Moved from e2e:` value in `cases check`, and `cases new` success and refusals.
- `tests/gin_qa/test_e2e_cli.py`: `e2e check` clean after a move, `--install` with a fake package manager for each lockfile, a failed install, no `package.json`, the merge with and without anchors, and the shared `.gitignore` function.
- `tests/gin_qa/test_cases_bug.py`: notes appended on a kept bug, a failed notes update with the case unchanged, and `appended` in the output.
- `tests/gin_qa/test_report.py`: the moved section with and without moved cases, the current result in it, `--zip` contents, and `.gitignore` with and without `--out`.
- `tests/gin_qa/test_tests_cli.py`: `tests run` adds the ignore entry once.
- `tests/gin_qa/test_packaging.py` and the docs tests, for changed skills and templates.

## Open Technical Questions

