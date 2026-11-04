# gin-qa interactive HTML report

Epic: gin-workflow-qa-report
Status: confirmed by the user on 2026-11-04.

## Goal and scope

QA needs one report they can open offline and send to someone else: counts per capability, type, priority, and result with charts, and a filterable case list where each case shows its test data, steps, latest result, run evidence, and bug.

`gin-qa report [capability]` writes a report folder: an `index.html` with its CSS, JS, and data inlined (no CDN, no network), plus copies of the e2e screenshots the report shows. Zipping that one folder is all it takes to share the report.

In scope:
- `gin-qa report [capability] [--out DIR] [--format text|json]` in `plugins/gin-qa/src/scripts/gin_qa/` (new `report.py`, wired in `cli.py`).
- The page template `plugins/gin-qa/src/templates/report.html`: inline CSS and vanilla JS, bar charts built from HTML buttons and CSS, no third-party code.
- The skill `/gin-qa:report [capability]`.
- `docs/guides/qa.md` and `docs/reference/cli.md`.

Out of scope: xlsx output (dropped on 2026-11-04 in favour of HTML); trend history across runs; publishing or uploading the report; runners for non-e2e types; embedding screenshots as base64; ARIA snapshots in the report; a project-overridable report template.

## Requirements

Data
- The report covers every case `tc.load` returns, or only the cases of `capability` when given. Each case carries the fields of `gin-qa cases export` (`cases.as_dict`).
- For each distinct `Run` value among the cases, the report reads that run once with `e2e.export`, and attaches to each case the results of its own `Run`: one entry per Playwright project, each with its status, error, and steps (number, title, status, URL, error, screenshot).
- A case whose `Run` is empty, or names something outside the evidence folder (a manual run reference such as `sprint-12 sheet`), shows its result and `Run` with no evidence and no note. A case whose `Run` folder is missing or unreadable shows its result and the note `evidence not found: <run>`; the rest of the report is still written.

Output
- Default location: `<evidence root>/report-<UTC stamp>/` (`qa/evidence/report-2026-11-04T08-00-00/` with default config), the stamp format `e2e run` uses, with a `-2`, `-3`, ... suffix when the folder exists. `qa/evidence/` is already git-ignored by `gin-qa e2e init`, so reports stay out of git.
- `--out DIR` writes to `DIR` instead; `DIR` must not exist or must be empty.
- The folder holds `index.html` and, for each screenshot a shown step references, a copy at `<run folder name>/<path relative to the run folder>`. `index.html` refers to images by those relative paths only. Nothing outside the folder is referenced.
- The command prints the path of `index.html` (`--format json`: `{"report": <path>, "cases": <n>, "screenshots": <n>, "missing_evidence": [<run>, ...]}`).

Page
- Header: generation time (UTC), scope (all or the capability), total cases.
- Four bar charts: cases per capability, type, priority, and result. Clicking a bar filters the case table by that value; clicking it again clears the filter.
- Case table: ID, title, capability, type, priority, result, bug; a search box over ID and title; one select per chart dimension; a count of shown cases.
- Case detail, opened by clicking a row: REQs or Source, other fields, preconditions, test data, steps, expected, result, run, bug, and per Playwright project the run steps with status, URL, error, and a screenshot thumbnail that opens the full image.
- Works offline from a `file://` URL in current Chromium, Firefox, and Safari.

Safety
- Case data is embedded as JSON in `<script type="application/json">` with every `<` written as `<`, so no case text can close the script element.
- The page sets text with `textContent` and builds elements with DOM calls; case data never reaches `innerHTML`.
- Only screenshots that `e2e.export` resolved inside the run folder are copied.

## User Stories

### US-1: Share a report as one folder
As a QA engineer, I want `gin-qa report` to write a folder with the page and its screenshots, so that I can zip it and send it to someone who has no access to the repository.

Acceptance criteria:
- `gin-qa report` writes `qa/evidence/report-<stamp>/index.html` and prints its path.
- Every screenshot the page references exists inside the report folder.
- Moving the report folder elsewhere and opening `index.html` shows the same page with all images.
- `--out DIR` with a non-empty `DIR` exits 2 and writes nothing.

### US-2: See the overall status at a glance
As a QA lead, I want charts of cases per capability, type, priority, and result, so that I see coverage and failures without reading every case.

Acceptance criteria:
- The four charts count every case in scope once per dimension.
- Clicking a bar narrows the case table to that value; clicking it again restores the table.

### US-3: Find and inspect one case
As a QA engineer, I want to search and filter cases and open one to see its data, steps, result, and per-step screenshots, so that I can check why it failed.

Acceptance criteria:
- Search by ID or title and the dimension selects combine to narrow the table.
- The detail view shows test data, steps, expected, result, run, and bug of the case.
- For an e2e case with run evidence, the detail view shows each step's status, URL, error, and screenshot for each Playwright project.
- A case whose run folder is gone shows `evidence not found: <run>` instead of steps.

### US-4: Report on one capability
As a QA engineer, I want `gin-qa report <capability>`, so that I can send a report on the feature under test only.

Acceptance criteria:
- Only cases of that capability appear in the charts, table, and copied screenshots.
- An unknown capability, or a repository with no test cases, exits 2 with an error and writes nothing.

### US-5: Run it from the agent
As a gin-qa user, I want `/gin-qa:report [capability]`, so that the agent writes the report and tells me where it is.

Acceptance criteria:
- The skill runs `gin-qa report` with the capability given and reports the `index.html` path and any runs with missing evidence.

## Errors and compatibility

- Exit codes follow the existing gin-qa contract: 0 written, 2 usage or environment error (unknown capability, no cases, non-empty `--out`, unreadable template). The report itself has no findings, so it never exits 1.
- A missing or invalid run folder is not an error: it is listed in `missing_evidence` and shown on the page.
- No new Python or JavaScript dependency. `cases export` and `e2e export` output stays unchanged, so gin-console is not affected.
- `gin-qa` `VERSION` gets a minor bump; `usage` in `cli.py` lists `report`.

## Testing

`tests/gin_qa/test_report.py`, on a fixture repository with cases in two capabilities and an evidence run folder holding `result.json` and screenshots:
- the report folder and `index.html` are written and the printed path matches;
- the embedded JSON parses and holds every case in scope, with results attached from each case's own `Run`;
- every image path in the data is relative and resolves inside the report folder;
- a case title containing `</script>` stays inside the JSON (`<`);
- a capability filter limits cases and copied screenshots;
- a case whose `Run` folder is missing is listed in `missing_evidence` and the report is still written;
- unknown capability, no cases, and non-empty `--out` exit 2 and write nothing;
- the template holds the data placeholder exactly once.

The page's JS (charts, filters, detail view) is checked by opening a generated report in a browser from a `file://` URL before the epic ships.
