# Legacy parity testing

Epic: gin-workflow-qa-parity
Status: draft for user review.

## Goal and scope

Parity tests have one owner, a case field for the legacy reference, and a stated build to run against.

In scope: a `Legacy:` case field in gin-qa (`plugins/gin-qa/src/scripts/gin_qa/cases.py`); a `gin specs assets list` command in gin-workflow (`workflow_core/specs_assets.py`, `specs_cli.py`); the `/gin-qa:cases` skill; `docs/starters/brownfield.md` and `brownfield.vi.md`; `docs/roles.md`; `docs/guides/qa.md` and `qa.vi.md`; `docs/reference/cli.md`; `plugins/gin-qa/src/templates/cases.md`; tests.

Out of scope: the SDD capture step in the starter (`gin-workflow-sdd-team-flow`, shipped); a command that records legacy payloads; accepting payload files in `gin specs assets add --legacy`.

Confirmed understanding (no epic comments): case files accept any free field, and free fields feed `hash8` while `Source`, `Priority`, and `Moved from e2e` do not (`cases.py:29,269-276`). `/gin-ba:capture` writes legacy folders `<specs>/<cap>/assets/<date>/` with a `description.md` (`Kind: legacy`, `Confirmed: <date>` once the BA confirms, `### <Screen>` under `## As-is behaviour`) and images under `legacy/`; `--legacy` accepts images only, and no command lists the folders. `/gin-qa:cases` reads no assets. The brownfield starter gives parity tests to the API developer (track 2) and API tests to QA (track 6), and names no build. `gin-workflow-sdd-team-flow`, which also edits the starter, shipped on 2026-11-11.

Comments considered: 0

## Requirements

1. `Legacy:` case field: optional, one line, one or more comma-separated references. Each reference is a relative path, optionally followed by `#<screen>`. It is a known field: it does not change `hash8`. `gin-qa cases check` reports an empty value and a reference that is absolute or contains `..`. `gin-qa cases export` rows gain `legacy`, a list of the references (empty without the field).
2. `gin specs assets list <cap> [--format text|json]` lists the dated asset folders of a capability, oldest first. Each JSON row is `{"date", "kind", "confirmed", "path", "screens"}`: `kind` from the `Kind:` line (`null` without one), `confirmed` the confirmed date or `null`, `path` the `description.md` path relative to the project root, `screens` the `### ` headings under `## As-is behaviour`. It resolves the project root like `gin specs reqs` (workspace parent included). An unknown capability exits 2 as `assets add` does; a capability without assets prints an empty list and exits 0.
3. `/gin-qa:cases`, when it writes cases for a capability, runs `gin specs assets list <cap> --format json`, reads each folder with `kind: legacy` and a `confirmed` date (screens, fields, rules), writes cases for the legacy behaviour it shows, and sets `Legacy:` to `<path>#<screen>`. Unconfirmed legacy folders are skipped and named in the report. Recorded payloads live in the QA home under `legacy/<capability>/`; an `api` case that compares against one also lists that file in `Legacy:`.
4. Brownfield starter (`brownfield.md` and `brownfield.vi.md` together): the QA owner (Chi) owns parity tests, written as `api` cases with `Legacy:` and run with `/gin-qa:tests --type api` from `qa/`; the API developer's track (Em) covers the service and facade with unit and integration tests in its `verify.checks`. The starter states the build: the new service built from the pull request branch, run in CI or locally, compared with payloads recorded once from the legacy system on staging and committed under `qa/legacy/catalog/`. The sentence that parity scripts run in the `pre-push` hook is removed.
5. `docs/roles.md` (Tests) adds that parity tests against the legacy system belong to the tester (a team convention).
6. Docs: `docs/guides/qa.md` and `qa.vi.md` describe `Legacy:`; `docs/reference/cli.md` documents `gin specs assets list` and the `legacy` export key; `plugins/gin-qa/src/templates/cases.md` shows the optional field.

## User Stories

### US-1: A case names the legacy behaviour it checks
As a tester, I want a `Legacy:` field on a case, so that a reviewer can open the confirmed screen or recorded payload the case compares against.

Acceptance criteria:
- A case with `Legacy: docs/specs/catalog/assets/2026-10-01/description.md#Product list, qa/legacy/catalog/list.json` passes `gin-qa cases check`, and its export row has both references under `legacy`.
- Adding, changing, or removing `Legacy:` leaves the case's `hash8` unchanged.
- `Legacy:` with an empty value, an absolute path, or a `..` segment is a `cases check` finding.

### US-2: Cases from confirmed legacy captures
As a tester, I want `/gin-qa:cases` to read the BA's confirmed legacy captures, so that the cases cover the behaviour the new system must keep.

Acceptance criteria:
- `gin specs assets list catalog --format json` lists each dated folder with its kind, confirmed date or `null`, `description.md` path, and screens.
- A capability without an `assets/` folder gives `[]` and exit 0; an unknown capability exits 2.
- `/gin-qa:cases` uses only confirmed `legacy` folders, sets `Legacy:` on the cases it writes from them, and names the unconfirmed ones it skipped.

### US-3: One parity owner and a stated build
As a team lead following the brownfield starter, I want one owner for parity tests and the build they run against, so that parity is neither duplicated nor skipped.

Acceptance criteria:
- `brownfield.md` and `brownfield.vi.md` name the tester as the only parity owner, the `api` type in `qa/` as where they run, and the pull-request build against payloads recorded from staging as what they compare.
- Neither starter says parity scripts run in the `pre-push` hook.
- `docs/roles.md` names parity tests as the tester's.

## Errors and compatibility

- `Legacy:` was a free field before; a case that already used it keeps parsing, but its `hash8` changes once, so its test shows `stale` until `gin-qa tests pin` or `gin-qa e2e` re-pins it.
- `gin-qa cases export` only gains a key; gin-console does not read it.
- gin-qa keeps importing nothing from gin-workflow: the skill calls `gin specs assets list` by command.
- Assets exist only with the SDD layout; with the legacy layout the command lists nothing.

## Testing

- `tests/gin_qa/test_cases_cli.py`: `Legacy:` check findings, hash unchanged, export key (update `test_export_keeps_free_fields`).
- `tests/workflow_core/` (the existing `specs assets` test file): `assets list` rows, ordering, screens, unconfirmed folder, empty capability, unknown capability, workspace child.
- `tests/gin_qa/test_packaging.py` (skill budget), `tests/workflow_core/test_walkthrough_docs.py` (every `gin` command the starter cites is in `cli.md`), `gin docs check` on the changed docs.
- Full suite `python3 -m pytest -n auto` passes.

## Open Technical Questions
