# Explain page: the CLI renders, the skill narrates

**Context**
Epic `gin-workflow-explain` (2026-11-07). A complex capability is hard to grasp from its living spec folder alone; the user asked for `gin:explain <capability|change>` to produce an interactive HTML page that explains it.

**Decision/Solution**
- `gin specs explain NAME [--narrative FILE] [--out FILE]` (`workflow_core/specs_explain.py`) renders one page with the tabs Overview, Requirements, Stories, Diagrams, and Mockups from a capability, else from an active change. Exit 1 lists images or mockups not embedded; exit 2 is usage, an unknown name, or a narrative or `--out` outside the repository.
- The `gin:explain` skill writes only the narrative (a Markdown file) and passes it with `--narrative`; the CLI owns rendering, so the page is deterministic and tested.
- Output goes under `artifacts.explain` (default `.agent-workflow/runtime/explain/`, never committed): `<explain>/<name>/<name>.html` with the narrative `<name>.md` beside it. Since `explain-legacy` (2026-11-13), `--legacy APP` writes `<explain>/legacy/<APP>/<cap>/<cap>.html` for a frozen workspace entry, with the kind line `legacy capability (<APP>)` (escaped: APP comes from config), and the skill explains the legacy code with `file:line` in the repository's response language. A team that keeps pages points `artifacts.explain` at an internal workspace repository and commits there.
- `specs_explain.py` reuses the private helpers of `specs_export.py` (`_section`, `_title`, `_template`, `markdown_html`, `Embed`, `fill`, `data_uri`, `MEDIA_TYPES`), so the trust boundary of the SRS export (images only from inside the repository, escaped text, safe hrefs) applies unchanged.
- A `mockup/index.html` is embedded only when it sits under the capability's `assets/<date>/`; it runs in an `<iframe srcdoc>` sandboxed with `allow-scripts` and without `allow-same-origin`. A mockup not embedded is reported as missing.
- Layout comes from `templates/explain.html`, overridable in `.agent-workflow/templates/`; Mermaid 11.4.1 loads with the same SRI hash as `srs.html` and runs only on the shown tab.

**Consequences**
- The base URL of a `srcdoc` document is the parent page, so `<a href="#id">` inside a mockup navigated the parent. The page injects a click handler into each mockup that sets `location.hash` and skips a click already `defaultPrevented`; the same injected listener accepts a screen message from the page picker only when it matches `^[a-z][a-z0-9-]*$`. Any new mockup feature that relies on relative URLs must account for this.
- A malformed or unknown hash keeps the current tab instead of throwing or jumping to Overview.
- Known limit, marked `simplified:` in `_anchor`: two headings with the same slug share an id.
- Not verified in a browser: Mermaid rendering online and the layout at phone width.

**References**
- `plugins/gin-workflow/src/scripts/workflow_core/specs_explain.py`, `specs_cli.py`, `plugins/gin-workflow/src/templates/explain.html`, `plugins/gin-workflow/src/skills/explain/SKILL.md`, `tests/workflow_core/test_specs_explain.py`, `docs/guides/sdd.md#explaining-a-capability`, `docs/guides/customizing-templates.md#explain-page-template`, `docs/reference/cli.md`
- `.planning/specs/2026-11-06-explain-design.md`, `.planning/plans/2026-11-07-explain.md`
- Commits `7b14096`, `f367af8`, `d887507`, `22bb446`
- Beads: `gin-workflow-explain`, `gin-workflow-explain.1`, `gin-workflow-explain.2`
- Related: [srs-export](srs-export.md), [spec-asset-iterations](spec-asset-iterations.md), [ba-plugin](ba-plugin.md)

**Scope**
SDD layout living specs and change folders, the `specs explain` command, and the `gin:explain` skill only.
