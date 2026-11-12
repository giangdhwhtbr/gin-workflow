# Test evidence and defects from automated runs

Epic: gin-workflow-qa-evidence
Status: draft for user review.

## Goal and scope

Run evidence outlives the tester's machine, automated e2e and API failures file bug beads, and a bug lands on the right epic.

In scope: the `/gin-qa:report`, `/gin-qa:e2e`, `/gin-qa:tests`, and `/gin-qa:run` skills; `gin-qa cases bug` (`plugins/gin-qa/src/scripts/gin_qa/bugs.py`); `docs/guides/qa.md`; tests under `tests/gin_qa/`.

Out of scope: legacy parity (`gin-workflow-qa-parity`); the QA track and ship check (`gin-workflow-qa-lifecycle`, shipped); any code that uploads files or posts pull request comments; core gin-workflow skills (the core refers to gin-qa only from `qa-track`).

Confirmed understanding (no epic comments): `gin-qa report --zip` already writes `<folder>.zip` under the gitignored `evidence/`; no code or CI template publishes it, and the approval comment is a documented team convention (`docs/guides/qa.md`, App pull request). `gin-qa cases bug` refuses every case type except `manual` (`bugs.py:104-105`), so `/gin-qa:e2e` and `/gin-qa:tests` stop at reporting a product defect. With REQs in several epics, `epic_of` silently takes the first REQ's epic (`bugs.py:76`).

Comments considered: 0

## Requirements

1. Publish: `/gin-qa:report` adds a step after `--zip`: print the zip path; with CI, put the URL of the CI artifact that holds the zip in the approval comment; without CI, attach the zip to a pull request comment by drag and drop and refer to that comment. No new CLI flag and no host API call.
2. `docs/guides/qa.md` gains a "Publish the evidence" section with two CI snippets that run `gin-qa e2e run` and `gin-qa report --zip` and keep the zip when the run fails: GitHub Actions (`actions/upload-artifact` with `if: always()`) and GitLab CI (`artifacts:` with `when: always`). The App pull request checklist says the approval comment carries the artifact URL (still a team convention).
3. `gin-qa cases bug` accepts a case of any type. Its behaviour is otherwise unchanged: an open `Bug:` bead gets a re-run note, else a new `bug` bead is created with `discovered-from:<epic>`, and the case records `failed` with the run and the bug through `record_result`.
4. `/gin-qa:e2e`: at the report step, list every `app_defect` case with its step, error, and screenshot paths, ask the user which ones to file, and for each chosen case run `gin-qa cases bug <TC-ID> --actual "<error>" --evidence "<screenshot>"... --run "<run folder>" --format json`. It never files a bug the user did not choose.
5. `/gin-qa:tests`: the same for each case whose test fails because the product is wrong, with the failing assertion as `--actual` and the test output path or test id as `--evidence`.
6. Several epics: `epic_of` collects the distinct epics of a case's REQs in REQ order. With more than one and no `--discovered-from`, `gin-qa cases bug` exits 2 with `several epics for <TC-ID>: <epic-a>, <epic-b>; pass --discovered-from <bead>` and creates nothing. One epic, or a legacy case with `Source:`, behaves as today.
7. `/gin-qa:run`, `/gin-qa:e2e`, and `/gin-qa:tests` handle that exit like `no epic`: show the listed epics (id and title from `gin task show`), plus any other bead id, and re-run with `--discovered-from <chosen>`.

## User Stories

### US-1: Evidence a reviewer can open
As a reviewer of an app pull request, I want the test report reachable from the approval comment, so that I can check the evidence without the tester's machine.

Acceptance criteria:
- `/gin-qa:report` tells the user how to publish the zip: the CI artifact URL, or a drag-and-drop attachment without CI.
- `docs/guides/qa.md` holds a GitHub Actions and a GitLab CI snippet that upload the report zip also when the tests fail.
- The App pull request checklist names the artifact URL in the approval comment.

### US-2: Bugs from automated failures
As a tester running automated e2e or API tests, I want to file a bug bead for a product defect from the run, so that the defect is tracked like one found in a manual run.

Acceptance criteria:
- `gin-qa cases bug` on an `e2e` case and on an `api` case creates a `bug` bead with `discovered-from:<epic>` and records `failed` with the run and the bug in the case file.
- A second `gin-qa cases bug` on the same case while its bug is open appends a re-run note and creates no bead.
- `/gin-qa:e2e` and `/gin-qa:tests` list the product defects and file bugs only for the cases the user chooses.

### US-3: The bug lands on the right epic
As a tester, I want to choose the epic when a case's REQs belong to several, so that the bug is not filed against an arbitrary one.

Acceptance criteria:
- `gin-qa cases bug` on a case whose REQs map to two epics exits 2, names both epics in REQ order, and creates no bead.
- With `--discovered-from <one of them>` it files the bug against that epic.
- A case whose REQs map to one epic files against it without a prompt.

## Errors and compatibility

- The `several epics` refusal replaces the silent first-REQ choice; scripts that relied on it now need `--discovered-from`. The JSON output keys of `cases bug` do not change.
- No new dependency; skill files stay within the 6,000-character gin-qa budget (`tests/gin_qa/test_packaging.py`).
- The CI snippets are documentation: gin-qa writes no CI file.

## Testing

- `tests/gin_qa/test_cases_bug.py`: replace `test_the_epic_comes_from_the_first_req_in_a_change` with a two-epic refusal test; add tests for an `e2e` and an `api` case filing a bug, the open-bug re-run note on an automated case, `--discovered-from` choosing one of two epics, and one epic filing without a prompt.
- `tests/gin_qa/test_packaging.py` passes (skill budgets and links).
- `gin docs check docs/guides/qa.md` passes.
- Full suite `python3 -m pytest -n auto` passes.

## Open Technical Questions
