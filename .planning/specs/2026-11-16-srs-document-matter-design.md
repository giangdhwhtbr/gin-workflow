# SRS document matter: revision history, sign-off, glossary, actors, traceability

Epic: gin-workflow-414v
Workflow: gin-workflow-414v
Kind: capability
Status: confirmed by the user on 2026-11-16.

## Goal and scope

`gin specs export` writes an SRS with a cover, a table of contents, and one chapter per capability (`specs_export.py`, `templates/srs.html`, `srs-capability.html`). A customer-ready SRS also needs document-level matter that a BA writes by hand today: a revision history, a sign-off page, a glossary, an actor catalogue, and a traceability matrix, and use case IDs a reader can cite. Most of it can be generated from data the project already holds.

Epic `gin-workflow-414v` held eleven follow-ups from the BA review of `gin-workflow-cyb8`. At discuss (2026-11-16) the user split it into four groups and chose group A for this epic:

- A (this epic): glossary, actor catalogue, traceability matrix, revision history and sign-off, citable use case IDs (items 3, 5, 7, 8, 10).
- B (`gin-workflow-ngiz`): NFRs and a business rules catalogue with their own IDs (items 4, 6).
- C (`gin-workflow-16jz`): includes and extends across capabilities, actor and use case generalization, a system context diagram (items 1, 2, 9).
- D (`gin-workflow-1w5p`): Mermaid pre-rendered to SVG for an offline PDF (item 11).

Confirmed decisions (2026-11-16):

- Revision history is generated from the archived change folders.
- The traceability matrix lists, per requirement, its use cases, the test files that cite it (as `specs trace` finds them), and the gin-qa cases that cite it.
- The actor catalogue is generated from the use cases; an optional `<specs>/actors.md` adds a description per actor.
- A use case is cited as `<cap>/<slug>`; no generated numbers.
- The data is built in a new module `workflow_core/specs_matter.py` and rendered by `specs_export.py` through new placeholders of `srs.html` (approach 1 of 3: no separate matrix command, no hand-written matter).

Assumptions (defaults, not asked):

- Glossary: only `confirmed` rows of `11-GLOSSARY.md` in the codebase docs folder (`artifacts.codebase`, default `docs/codebase`), shown as English, Term (Lang), Meaning; `proposed` rows are left out.
- Sign-off: a fixed table in `srs.html` with the rows Prepared by, Reviewed by, Approved by and the columns Name, Role, Signature, Date, left blank; a project changes it by overriding the template.
- Exporting one capability limits the revision history, actors, and traceability to that capability; the glossary stays whole.

Out of scope:
- Groups B, C, and D above.
- QA cases in a workspace `shape: qa` child repository; only the project's own QA cases folder is read.
- A separate matrix command or CSV output.
- Gin-qa run results (pass or fail) in the matrix: a case is listed when it cites the requirement.
- The legacy layout, which has no living specs and no SRS.

## Requirements

### R1. Document order and placeholders

`templates/srs.html` gains the placeholders `revisions`, `glossary`, `actors`, and `traceability`, and a static sign-off section, in this order: cover, revision history, sign-off, contents, glossary, actors, chapters, traceability matrix. Each section has an `<h2>` heading and an `id` (`revisions`, `signoff`, `glossary`, `actors`, `traceability`). The sign-off section is plain HTML in the template (no code fills it), so an override edits, moves, or drops it directly. The table of contents links each of these sections the template holds.

A project's overridden `srs.html` without one of the new placeholders exports without that section and without an error. The template comment lists the new placeholders.

### R2. Revision history

`specs_matter.revisions(root, cfg, cap=None)` returns one row per folder in `<changes>/archive/` whose name starts with `YYYY-MM-DD-`, newest first: date, epic (the `Epic:` line of `01-proposal.md`), title (its `# ` line, else the folder name after the date), the capabilities its archived `02-spec-delta.md` touches, and the REQ-IDs it added, modified, and removed. With `cap`, only rows that touch `cap` are kept. A folder without a delta (a technical change) has empty capability and REQ cells; with `cap`, it is left out. No archive folder gives no rows, and the section shows "No revisions yet."

### R3. Glossary

`specs_matter.glossary(root, cfg)` returns the `confirmed` rows of the `## Terms` table of `<codebase>/11-GLOSSARY.md`: English, Term, Lang, Meaning, sorted by English (case-insensitive). A missing file, a missing table, or no confirmed row gives no rows, and the section shows "No glossary." Columns are found by their header names, so a reordered table still reads.

### R4. Actor catalogue

`specs_matter.actors(root, cfg, cap=None)` returns one row per actor across every capability's use cases (`Actor:` and `Secondary actors:`), matched without regard to case or repeated spaces and labelled with the first spelling met (capabilities and slugs in sorted order): the actor, its description, and the use cases it takes part in as `<cap>/<slug>`, marking secondary participation `(secondary)`. The matching function is shared with `specs_export.use_case_diagram`, which keeps its output.

`<specs>/actors.md` is optional: a Markdown table whose header has `Actor` and `Description` columns. A description is matched to an actor the same way. With `cap`, only actors of that capability's use cases are kept.

`specs lint` (living and `--change`) reports, when `<specs>/actors.md` exists:
- no table with `Actor` and `Description` columns: `docs/specs/actors.md: needs a table with Actor and Description columns`;
- an actor no use case names: `docs/specs/actors.md:5: actor 'Auditor' is in no use case`.

### R5. Traceability matrix

`specs_matter.traceability(root, cfg, cap=None)` returns one row per requirement block of the living specs, ordered by capability then REQ-ID: REQ-ID, title, capability, use cases (`<cap>/<slug>` of each use case whose `Requirements:` line names it), tests (repository paths of test files citing the REQ-ID), QA cases (the `TC-…` ID of each file under the QA cases folder citing the REQ-ID), and status `covered` (a test or a QA case) or `missing`.

- Test files are found as `specs trace` finds them: the files matching `test_globs` among the tracked files, plus each workable workspace child, read as text. The scan moves from `specs_trace.trace` into a shared function `specs_trace.req_sources(root, cfg, req_ids) -> tuple[dict[str, list[str]], list[str]]` (sources per REQ-ID, and the workspace children skipped because they could not be listed); `trace` calls it and its output does not change.
- The QA cases folder is `qa.cases` when set, else `<qa.dir or qa>/cases`, under the project root. Its `*.md` files (recursive) are read; the case ID is the `TC-<CAP>-<NNN>` at the start of the file name. A missing folder gives empty QA cells.
- With `cap`, only that capability's requirements are kept.

### R6. Citable use case IDs

Each use case in an SRS chapter shows `<cap>/<slug>` next to its title (a `<p class="use-case-id">` right after the heading). The actor catalogue and the traceability matrix cite use cases the same way, as links to the use case's anchor (`#<cap>-<slug>`) when the use case is in the exported document.

### R7. Rendering

`specs_export.py` renders each section as an escaped HTML table (or the "No …" line), fills the placeholders in one pass with `fill`, and adds table-of-contents entries for the sections the template holds. `export` for one capability passes `cap` to R2, R4, and R5. No new dependency.

### R8. Documentation

- `docs/guides/sdd.md` and `.vi.md`: the SRS paragraph lists the new sections and their sources.
- `docs/guides/ba.md` and `.vi.md`: `actors.md`, citing use cases as `<cap>/<slug>`, and that the glossary comes from confirmed terms.
- `docs/guides/customizing-templates.md` and `.vi.md`: the new `srs.html` placeholders.
- `docs/reference/cli.md`: the `export` row (new sections) and the `lint` row (`actors.md` checks).

## User Stories

### US-1: See what changed between SRS versions
As a business analyst, I want the SRS to open with a revision history built from the archived changes, so that the customer sees what changed in each version without me keeping a log.

Acceptance criteria:
- `gin specs export --all` with two archived changes prints a revision history table with two rows, newest first, each with date, epic, title, capabilities, and REQ-IDs added, modified, and removed.
- An archived technical change without a delta shows a row with empty capability and REQ cells in `--all`, and no row in `export <cap>`.
- Without `<changes>/archive/` the section reads "No revisions yet."

### US-2: Get the SRS signed off
As a business analyst, I want a sign-off page in the SRS, so that the customer can sign the version they approve.

Acceptance criteria:
- The exported SRS has a sign-off section after the revision history with rows Prepared by, Reviewed by, Approved by and columns Name, Role, Signature, Date.
- An overridden `srs.html` without the sign-off section exports without it and without an error.

### US-3: Read the business terms in one place
As a customer reading the SRS, I want a glossary of the project's business terms, so that I read each term the same way the team does.

Acceptance criteria:
- With a `11-GLOSSARY.md` holding one `confirmed` and one `proposed` row, the glossary section lists only the confirmed term, with English, Term (Lang), and Meaning.
- Without the file the section reads "No glossary."

### US-4: Know who uses the system
As a business analyst, I want an actor catalogue generated from the use cases, with descriptions I can add, so that the SRS lists every user role and what each one does.

Acceptance criteria:
- Two use cases with `Actor: Customer` and `Actor: customer` give one actor row labelled `Customer` listing both use cases as `<cap>/<slug>`; a secondary actor's use case is marked `(secondary)`.
- With `<specs>/actors.md` describing `Customer`, the row shows that description.
- `specs lint` reports an actor in `actors.md` that no use case names, with file and line, and an `actors.md` without the two columns.
- `export <cap>` lists only actors of that capability's use cases.

### US-5: Trace each requirement to use cases and tests
As a customer, I want a traceability matrix from each requirement to its use cases, tests, and QA cases, so that I can see every requirement is covered.

Acceptance criteria:
- A requirement cited by a use case, a test file, and a QA case file `TC-AUTH-001-login.md` shows all three, with status `covered`.
- A requirement cited by none shows status `missing`.
- `specs trace --change <epic>` prints the same output as before.

### US-6: Cite a use case in a meeting
As a customer, I want each use case to carry a short stable ID, so that I can refer to it in meetings and emails.

Acceptance criteria:
- Each use case in a chapter shows `<cap>/<slug>` right after its title.
- The actor catalogue and the matrix link `<cap>/<slug>` to that use case's anchor.

## Errors and compatibility

- Missing sources are never errors: each section shows its "No …" line, and the QA cases cell is empty.
- An archived change without `01-proposal.md` takes its title from the folder name; an unreadable file is skipped, as `trace` skips one.
- `actors.md` findings exit 1 like other lint findings; a project without the file sees no new finding.
- `gin setup doctor` and `gin setup preset` count `<specs>/actors.md` as an SDD file, like `README.md`, so it is not reported as foreign.
- A project's overridden `srs.html` without the new placeholders exports as before, without the new sections.
- The SRS of every SDD project gains the new sections and the use case IDs; that output change is intended.
- `specs trace` output is unchanged.
- `dist/` is regenerated by the build; no hand edits there.

## Testing

- `tests/workflow_core/test_specs_matter.py` (new): `revisions` (two archived changes, a technical one, `cap` filter, no archive, no proposal), `glossary` (confirmed only, reordered columns, missing file), `actors` (case-insensitive merge, secondary marking, descriptions from `actors.md`, `cap` filter), `traceability` (use case, test file, QA case, missing, `cap` filter, no QA folder, `qa.cases` set).
- `tests/workflow_core/test_specs.py`: `lint_actors` findings and no finding without `actors.md`.
- `tests/workflow_core/test_specs_archive_trace.py`: `trace` unchanged after `req_sources` is extracted.
- `tests/workflow_core/test_specs_export.py`: section order and table-of-contents entries, use case IDs and anchors, `export <cap>` filtering, an override without the new placeholders, the use case diagram unchanged.
- `gin docs check` on the changed pages exits 0.
- Full suite `python3 -m pytest -n auto` through the pre-push hook, and once with `bd` off PATH before a release.

## Open Technical Questions
