# SRS export: one self-contained HTML from living specs, confined to the repository

**Context**
Epic `gin-workflow-bel0` (2026-11-06). BAs send the living specs to customers; `docs/specs/` is a folder of Markdown, Mermaid, and images that a customer cannot open as one document.

**Decision/Solution**
- `gin-workflow specs export (CAP | --all) [--out FILE]` (`workflow_core/specs_export.py`) writes one HTML file: default `srs-<cap>.html` or `srs.html` at the repository root, overwritten each run. Exit 1 lists missing images; exit 2 is usage, an unknown capability, an `--out` outside the repository, or a write error.
- Markdown is converted with a stdlib-only converter for the subset specs use (headings shifted to a chapter level, lists, tables, fences, inline code, links, images); every piece of text is escaped, and placeholders are filled in one pass (`fill`), so spec text is never substituted again.
- Images are embedded as `data:` URIs, so the file can be sent alone. Mermaid loads from jsDelivr as a classic script pinned to `mermaid@11.4.1` with an SRI `integrity` hash (a `type="module"` script cannot carry SRI); offline, the diagram source shows.
- Layout comes from `templates/srs.html` and `srs-capability.html`, overridable in `.agent-workflow/templates/`; a relative `src` in a template is embedded from the repository root.
- The file goes to customers, so the export is a trust boundary: an image (Markdown, template, or asset) is embedded only when it resolves to a file inside the repository with an extension in `MEDIA_TYPES`, else it counts as missing (an asset symlink pointing out is listed by name); a link keeps its `href` only for `http(s)://`, `mailto:`, `#`, or a scheme-less relative target.

**Consequences**
- Review cycle 1 caught an infinite loop on a `|` line without a table rule row, file leaks through `../` and absolute image paths, and `javascript:` hrefs; all fixed with tests in `tests/workflow_core/test_specs_export.py`. Any new Markdown construct must keep the parser consuming at least one line per branch.
- Known limits left open: table cells split on every `|` (also inside code spans); a link target with `)` ends early; `--out` may overwrite any file inside the repository.

**References**
- `plugins/gin-workflow/src/scripts/workflow_core/specs_export.py`, `specs_cli.py`, `plugins/gin-workflow/src/templates/srs.html`, `srs-capability.html`, `docs/guides/sdd.md#exporting-an-srs`, `docs/guides/customizing-templates.md#srs-export-templates`, `docs/reference/cli.md`
- `.planning/specs/2026-11-05-srs-export-design.md`, `.planning/plans/2026-11-06-srs-export.md`
- Beads: `gin-workflow-bel0`, `gin-workflow-bel0.1`, `gin-workflow-bel0.2`
- Related: [spec-diagrams](spec-diagrams.md), [spec-asset-iterations](spec-asset-iterations.md), [explain-page](explain-page.md) (`specs_explain.py` imports the private helpers of `specs_export.py`; a change to them changes both outputs)

**Scope**
SDD layout living specs and the `specs export` command only.
