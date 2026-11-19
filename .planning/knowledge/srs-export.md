# SRS export: one self-contained HTML from living specs, confined to the repository

**Context**
Epic `gin-workflow-bel0` (2026-11-06). BAs send the living specs to customers; `docs/specs/` is a folder of Markdown, Mermaid, and images that a customer cannot open as one document.

**Decision/Solution**
- `gin-workflow specs export (CAP | --all) [--out FILE]` (`workflow_core/specs_export.py`) writes one HTML file: default `srs-<cap>.html` or `srs.html` at the repository root, overwritten each run. Exit 1 lists missing images; exit 2 is usage, an unknown capability, an `--out` outside the repository, or a write error.
- Markdown is converted with a stdlib-only converter for the subset specs use (headings shifted to a chapter level, lists, tables, fences, inline code, links, images); every piece of text is escaped, and placeholders are filled in one pass (`fill`), so spec text is never substituted again.
- Images are embedded as `data:` URIs, so the file can be sent alone. Since `gin-workflow-1w5p`, the page embeds the vendored Mermaid 11.4.1 library inline (only when it holds a diagram), so diagrams draw offline; `templates/vendor/README.md` says how to upgrade it.
- Layout comes from `templates/srs.html` and `srs-capability.html`, overridable in `.agent-workflow/templates/`; a relative `src` in a template is embedded from the repository root. Since `gin-workflow-fm8l` (2026-11-09) each chapter also prints use cases (`{{use_cases}}`, between Purpose and Diagrams; see [spec-use-cases](spec-use-cases.md)); since `gin-workflow-cyb8` (2026-11-15) a generated use case diagram opens that section. Since `gin-workflow-414v` (2026-11-16) the document also holds a revision history, a sign-off page, a glossary, an actor catalogue, and a traceability matrix ([srs-document-matter](srs-document-matter.md)).
- The file goes to customers, so the export is a trust boundary: an image (Markdown, template, or asset) is embedded only when it resolves to a file inside the repository with an extension in `MEDIA_TYPES`, else it counts as missing (an asset symlink pointing out is listed by name); a link keeps its `href` only for `http(s)://`, `mailto:`, `#`, or a scheme-less relative target.

**Consequences**
- The vendored Mermaid text holds `src="`, `<iframe`, `<!--`, and `{{`. It is filled last and once, after `_template` has stripped comments and embedded `src`, so nothing rescans it; tests that assert a whole page has none of these strip the vendored text first. A page with a diagram is about 2.5 MB larger.
- Review cycle 1 caught an infinite loop on a `|` line without a table rule row, file leaks through `../` and absolute image paths, and `javascript:` hrefs; all fixed with tests in `tests/workflow_core/test_specs_export.py`. Any new Markdown construct must keep the parser consuming at least one line per branch.
- Known limits left open: table cells split on every `|` (also inside code spans); a link target with `)` ends early; `--out` may overwrite any file inside the repository.

**References**
- `plugins/gin-workflow/src/scripts/workflow_core/specs_export.py`, `specs_cli.py`, `plugins/gin-workflow/src/templates/srs.html`, `srs-capability.html`, `docs/guides/sdd.md#exporting-an-srs`, `docs/guides/customizing-templates.md#srs-export-templates`, `docs/reference/cli.md`
- `.planning/specs/2026-11-05-srs-export-design.md`, `.planning/plans/2026-11-06-srs-export.md`
- Beads: `gin-workflow-bel0`, `gin-workflow-bel0.1`, `gin-workflow-bel0.2`
- Related: [spec-diagrams](spec-diagrams.md), [spec-asset-iterations](spec-asset-iterations.md), [explain-page](explain-page.md) (`specs_explain.py` imports the private helpers of `specs_export.py`; a change to them changes both outputs)

**Scope**
SDD layout living specs and the `specs export` command only.
