# Offline diagrams: embed Mermaid in the SRS and explain pages

Epic: gin-workflow-1w5p
Workflow: gin-workflow-1w5p
Kind: capability
Status: confirmed by the user on 2026-11-19.

## Goal and scope

`gin specs export` writes diagrams as `<pre class="mermaid">` blocks, and `templates/srs.html` (line 94) loads `mermaid@11.4.1` from jsDelivr to draw them in the browser; `templates/explain.html` (line 60), written by `specs_explain`, does the same. Opened without network access, or printed to PDF offline, each diagram shows its Mermaid source instead of the drawing. The SRS goes to customers, so it must stand alone. Group D of the BA review follow-ups of `gin-workflow-cyb8`. Images are already embedded and the templates load nothing else from the network.

Confirmed decisions (2026-11-19):

- Embed the Mermaid library in the page instead of pre-rendering SVG: the `gin` CLI stays standard-library Python, with no Node, mermaid-cli, or Chromium needed to export, on any platform.
- Always embed when the page holds a diagram; no flag.
- Both the SRS and the `/gin:explain` page.

Assumptions (defaults, not asked):

- The vendored copy is `mermaid.min.js` 11.4.1, the file the CDN serves today (sha384 `rbtjAdnIQE/aQJGEgXrVUlMibdfTSa4PQju4HDhN3sR2PmaKFzhEafuePsl9H/9I`, 2,571,900 bytes, MIT licence), so the drawings do not change. Upgrading it is a manual replacement of the file and its pinned hash.
- A page with a diagram grows by about 2.5 MB; a page without one does not grow.
- A project template override that still holds the CDN `<script src>` keeps working online, unchanged; no lint or doctor warning for it.
- Out of scope: pre-rendered SVG, the gin-qa report, Mermaid versions other than 11.4.1.

## Requirements

### R1. Vendored Mermaid

The plugin ships `mermaid.min.js` 11.4.1 with a README naming its source URL, version, sha384, and licence. A test checks the file's sha384 against the pinned value and that the file holds no `</script` (case-insensitive), so it can sit inside an inline `<script>` element.

### R2. Embedded in the SRS

In `templates/srs.html`, the CDN `<script src>` element is replaced by a `{{mermaid}}` placeholder; the initialisation script stays. `specs export` fills `{{mermaid}}` with `<script>` + the vendored file + `</script>` when the exported page holds at least one `<pre class="mermaid">`, and with the empty string otherwise. The file is embedded once per page, for one capability or `--all`.

### R3. Embedded in the explain page

`templates/explain.html` gets the same `{{mermaid}}` placeholder, filled by `specs_explain` under the same rule. The tab script that runs Mermaid per tab stays.

### R4. Missing vendored file

When the vendored file is missing (a broken install), export and explain stop with an error naming its path, as other `SpecsError`s do; they never fall back to the CDN.

### R5. Documentation

- `docs/guides/sdd.md` and `docs/guides/ba.md` with their `.vi.md` versions: the SRS opens and prints with its diagrams offline.
- `docs/guides/customizing-templates.md` and its `.vi.md` version: the `{{mermaid}}` placeholder, and that an override keeping the CDN script needs network access to draw diagrams.
- `docs/reference/cli.md`: the `specs export` row and the explain command say the page embeds Mermaid when it has a diagram.

## User Stories

### US-1: Send an SRS that works offline
As a business analyst, I want the exported SRS to draw its diagrams without network access, so that a customer can open it or print it to PDF anywhere.

Acceptance criteria:
- `gin specs export --all` on a project with use cases writes an `srs.html` that holds no `cdn.jsdelivr.net` and exactly one inline script with the Mermaid library.
- Opened in Chromium with every network request blocked, each `pre.mermaid` of that file becomes an SVG and no Mermaid syntax error shows; printing to PDF shows the diagrams.
- An export with no diagram at all holds no Mermaid library.

### US-2: Read an explain page offline
As a developer, I want the `/gin:explain` page to draw its diagrams without network access, so that I can read it on a plane or behind a proxy.

Acceptance criteria:
- An explain page with a diagram holds no `cdn.jsdelivr.net` and exactly one inline Mermaid script; each tab draws its diagrams with the network blocked.
- An explain page with no diagram holds no Mermaid library.

### US-3: Keep a customised template working
As a project maintainer, I want my overridden `srs.html` to keep working after the upgrade, so that the change does not break my export.

Acceptance criteria:
- An override in `.agent-workflow/templates/srs.html` that keeps the CDN script and has no `{{mermaid}}` exports with its CDN script unchanged and no embedded library.

## Errors and compatibility

- A missing vendored file stops export and explain with `SpecsError` naming the path (exit code as for other specs errors).
- Pages exported before the upgrade keep loading from the CDN; re-exporting makes them offline.
- Overridden templates without `{{mermaid}}` behave as before.
- `dist/` is regenerated by the build; no hand edits there.

## Testing

- Unit: vendored file hash and no `</script`; SRS export with and without diagrams; explain with and without diagrams; an override without the placeholder; a missing vendored file raises `SpecsError`.
- Browser: an exported SRS and an explain page in Chromium (Node Playwright) with all requests aborted: SVG count equals `pre.mermaid` count, no "Syntax error"; a PDF printed from the SRS shows the diagrams.

## Open Technical Questions
