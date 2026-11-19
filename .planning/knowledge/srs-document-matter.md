# SRS document matter: revision history, sign-off, glossary, actors, traceability

**Context**
Epic `gin-workflow-414v` (2026-11-16). After the BA review of `gin-workflow-cyb8`, eleven SRS gaps were split into four epics; this one adds the document-level matter a customer-ready SRS needs, generated from data the project already holds. The other groups are `gin-workflow-ngiz` (NFRs, business rules), `gin-workflow-16jz` (cross-capability includes, generalization, context diagram), and `gin-workflow-1w5p` (offline diagrams).

**Decision/Solution**
- `workflow_core/specs_matter.py` returns plain rows; `specs_export._matter` renders them into the `srs.html` placeholders `revisions`, `glossary`, `actors`, `traceability`. The sign-off table is static HTML in the template, no placeholder. Order: cover, revision history, sign-off, contents, glossary, actors, chapters, traceability matrix. Since `gin-workflow-ngiz` the non-functional requirements and business rules catalogues follow the actors, and the matrix has a Type column ([requirement-types](requirement-types.md)). The table of contents links only the sections whose `id` the (possibly overridden) template holds.
- Revisions: one row per `<changes>/archive/YYYY-MM-DD-*` folder, newest first, from its `01-proposal.md` (title, `Epic:`) and archived delta (capabilities, REQ-IDs per section). A one-capability export keeps only rows touching it.
- Glossary: `confirmed` rows of `## Terms` in `<codebase>/11-GLOSSARY.md`, columns found by header name, sorted by English; never filtered by capability.
- Actors: from `Actor:` and `Secondary actors:` of every use case, matched by `specs.actor_key` (shared with the use case diagram); optional `<specs>/actors.md` table adds descriptions. `specs.lint_actors` reports a file without `Actor`/`Description` columns, an actor no use case names, and an unreadable file. `specs_migrate._foreign` owns the top-level `actors.md` so `setup doctor` does not flag it. Since `gin-workflow-16jz` the Actors table has an `Is a` column after Actor (`specs_matter.actors` rows carry `is_a`), and the section opens with a generated context diagram (`specs_export.context_diagram`): one node per exported capability inside a system subgraph, actors outside with a solid edge where primary and `-.->` where only secondary, plus `is a` edges; a one-capability export limits it to that capability; no diagram when there are no actors.
- Traceability: one row per living requirement (sorted by capability, prefix, number): use cases from `Requirements:`, test files from `specs_trace.req_sources` (extracted from `trace`, which keeps its output), QA cases as `TC-<CAP>-<NNN>` file names under `qa.cases` or `<qa.dir or qa>/cases` (resolved inside the repository, else ignored). `qa_cases_dir` loads the config again because `sdd_config` drops `qa`.
- Use cases are cited as `<cap>/<slug>` (`<p class="use-case-id">` after the title, links to `#<cap>-<slug>` in the catalogue and matrix). No generated numbers.
- `specs.table_rows` reads the first Markdown table: escaped `\|` stays in the cell, short rows are padded, tables inside comments are skipped with line numbers kept.

**Consequences**
- Every file read for the SRS or lint goes through `specs.read_text_or_none`: one non-UTF-8 file aborted the whole export until review caught it.
- The test scan reads only git-tracked files, like `specs trace`: an uncommitted test file leaves its requirement `missing`.
- Open MINOR items: section ids (`actors`, `glossary`, ...) share the id namespace with chapter ids, so a capability named `actors` collides; no test for an override that drops a whole section or for a use case without a heading; `_matter` builds every table even when the template lacks its placeholder.
- In the SRS, the header lines of a use case render as a field table since `gin-workflow-fx3z`.

**References**
- `plugins/gin-workflow/src/scripts/workflow_core/specs_matter.py`, `specs_export.py`, `specs.py`, `specs_trace.py`, `specs_migrate.py`, `plugins/gin-workflow/src/templates/srs.html`
- Tests: `tests/workflow_core/test_specs_matter.py`, `test_specs_export.py`, `test_specs.py`, `test_specs_migrate.py`
- Docs: `docs/guides/sdd.md`, `ba.md`, `customizing-templates.md`, their `.vi.md` pairs, `docs/reference/cli.md`
- `.planning/specs/2026-11-16-srs-document-matter-design.md`, `.planning/plans/2026-11-16-srs-document-matter.md`
- Beads: `gin-workflow-414v`, `.1` to `.3`
- Related: [srs-export](srs-export.md), [spec-use-cases](spec-use-cases.md), [codebase-glossary](codebase-glossary.md), [gin-qa-case-files](gin-qa-case-files.md)

**Scope**
SDD layout only: the SRS export, `specs lint` of `actors.md`, and the SDD, BA, and template guides.
