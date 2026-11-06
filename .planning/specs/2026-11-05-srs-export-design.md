# SRS export: printable HTML from living specs with a customizable template

Epic: gin-workflow-bel0
Status: draft for user review.

## Goal and scope

With the SDD layout, a capability's requirements live in `docs/specs/<capability>/spec.md`, its diagrams in `diagrams/`, and its customer inputs in `assets/` (flat files and dated iteration folders). A BA who must send a customer a Software Requirements Specification has no way to turn these into one document: they copy text by hand.

This spec adds, for the SDD layout only:
- `gin-workflow specs export <capability>` and `specs export --all`, writing one self-contained HTML file that prints to PDF from the browser;
- two templates, `srs.html` and `srs-capability.html`, overridable per project like every template, so a project sets its logo, customer, product brief, cover, and section order;
- a stdlib Markdown-to-HTML converter for the subset the specs use;
- the command in the CLI reference, the SDD guide, the template guide, and `gin-sdd`.

Out of scope:
- Exporting a change (`docs/changes/<epic>/`) or a spec delta: the SRS holds only the confirmed living requirements.
- User stories (they live in archived change proposals) and a traceability table to tests.
- Producing PDF: the user prints the HTML from the browser.
- The interactive explainer (`gin-workflow-explain`); it may reuse the converter later.
- A Markdown dependency, vendored JavaScript, and raw HTML pass-through in Markdown.
- The legacy layout.

## Requirements

### R1. Command

`gin-workflow specs export (<capability> | --all) [--out <file>]`, with the common `--repository` and `--format` options of `specs`:
- `<capability>` is a folder name under `artifacts.specs` that holds a `spec.md`; `--all` exports every such capability, sorted by name, one chapter each. Exactly one of the two is given.
- `--out` is relative to the repository root. The default is `srs-<capability>.html` for one capability and `srs.html` for `--all`, at the repository root. An existing file is overwritten: the output is generated.
- Text output prints the written path; `--format json` prints `{"path": "...", "capabilities": [...], "missing": [...]}`.
- Exit 0 when the file is written and every referenced local image was found; exit 1 when the file is written but `missing` lists images (each `<file>: <image path>`); exit 2 for the legacy layout, an unknown capability, no capability at all with `--all`, or neither or both of `<capability>` and `--all`.

### R2. Document content

`srs.html` receives:
- `{{title}}`: the `# ` heading of the capability's `spec.md` for one capability; the repository folder name for `--all`;
- `{{date}}`: today's date, `YYYY-MM-DD`;
- `{{toc}}`: a nested list linking each chapter and each requirement by its REQ-ID;
- `{{chapters}}`: each capability rendered through `srs-capability.html`, in order.

`srs-capability.html` receives, for one capability:
- `{{capability}}`: the `# ` heading of `spec.md`;
- `{{cap}}`: the capability folder name, used as the chapter's anchor;
- `{{purpose}}`: the body of `spec.md` `## Purpose`;
- `{{diagrams}}`: each `diagrams/*.md` file, sorted by name, converted; a ```` ```mermaid ```` block becomes `<pre class="mermaid">` holding the escaped source;
- `{{requirements}}`: each requirement block of `spec.md` (`parse_blocks`), in file order, converted, with the REQ-ID as the block's anchor;
- `{{assets}}`: each dated iteration folder under `assets/`, oldest first, as its `description.md` converted (or a heading with the folder name when it has none), then every image in that folder and its subfolders not already shown by `description.md`, then the names of its other files; after the dated folders, the flat files under `assets/` the same way under a `Files` heading. Other subfolders of `assets/` are not exported.

An empty section renders as empty: the template decides whether to show a heading for it. HTML comments are removed from both templates before they are filled. Placeholders are filled in one pass, so text from a spec that contains `{{...}}` is never substituted.

### R3. Markdown conversion

`workflow_core/specs_export.py` converts the Markdown the specs use: ATX headings, paragraphs, bullet and numbered lists (one nesting level), fenced code blocks, pipe tables, inline code, bold, italic, links, and images. HTML comments are removed before conversion (`<!-- base: ... -->` lines and template comments). Every piece of text is HTML-escaped; raw HTML in Markdown is shown as text.

Headings shift so that a converted file's highest heading lands on the level its section needs: `###` for a diagram file, a requirement block, or a `description.md`, with each lower heading one level further down, capped at `######`.

Images:
- a local image path is resolved against the folder of the Markdown file that names it, and embedded as a `data:` URI (base64, media type from the file extension); an image file shown by R2's asset listing is embedded the same way;
- a missing local image renders its alt text and is added to `missing`;
- an `http://` or `https://` image is kept as a link.

### R4. Templates

`plugins/gin-workflow/src/templates/srs.html` and `srs-capability.html`, printed by `gin-workflow specs template srs.html` / `srs-capability.html` and overridden in `.agent-workflow/templates/` as every template is.

`srs.html` carries:
- a cover with `{{title}}` and `{{date}}`, and an explanatory comment showing where a project puts its logo, customer, and product brief;
- `{{toc}}` and `{{chapters}}`;
- CSS for screen and print: each chapter starts on a new page, and `<pre class="mermaid">` keeps its source readable when Mermaid does not load;
- a `<script src>` that loads Mermaid's single-file build (`dist/mermaid.min.js`) from jsDelivr at an exact pinned version, with `integrity` and `crossorigin`, and a script that renders every `pre.mermaid` when Mermaid loaded. Without network the page shows the diagram sources and everything else. (A module `import` cannot carry `integrity`, and the ES module build loads further chunks.)

`srs-capability.html` anchors the chapter with `{{cap}}`, titles it with `{{capability}}` in an `<h1>`, and lays out the sections in this order, each under an `<h2>`: `{{purpose}}`, `{{diagrams}}`, `{{requirements}}`, `{{assets}}`; a project reorders or deletes a placeholder and its heading to change or drop a section.

A local image that a template names with a relative `src` (a logo, for example) is resolved against the repository root and embedded as a `data:` URI; a missing one is added to `missing`.

### R5. Documentation and skill

- `docs/reference/cli.md`: the `specs export` row with its arguments, default path, and exit codes.
- `docs/guides/sdd.md` and `docs/guides/sdd.vi.md`: a section on exporting an SRS: the command, what each chapter holds, printing to PDF, the network need for diagrams.
- `docs/guides/customizing-templates.md` and `.vi.md`: `srs.html` and `srs-capability.html` in the template list and table, with their placeholders and the logo example.
- `plugins/gin-workflow/src/skills/gin-sdd/SKILL.md`: one line that a BA exports a capability with `specs export`; the file stays within 6,000 characters.

## User Stories

### US-1: Send a capability's SRS to the customer
As a BA, I want to export a capability's living requirements, diagrams, and assets into one printable document, so that I send the customer an SRS without copying text by hand.

Acceptance criteria:
- `gin-workflow specs export auth` writes `srs-auth.html` at the repository root and prints its path.
- The file holds the capability's purpose, each diagram as `<pre class="mermaid">`, each requirement with its scenarios and an anchor named by its REQ-ID, and each image of `assets/` as a `data:` URI.
- No `src` attribute in the file names a local path, so its images show when it is sent alone.

### US-2: One SRS for the whole product
As a BA, I want to export every capability into one document, so that the customer reviews the whole product in one file.

Acceptance criteria:
- `gin-workflow specs export --all` writes `srs.html` with one chapter per capability, sorted by name, and a table of contents linking each chapter and requirement.
- `--out docs/srs/v1.html` writes there instead.

### US-3: The SRS carries the project's identity
As a BA, I want the SRS to carry my company's logo, the customer's name, and the product brief, in the section order the customer expects, so that it reads as our deliverable.

Acceptance criteria:
- With `.agent-workflow/templates/srs.html` naming `src="docs/brand/logo.png"`, the exported file embeds the logo as a `data:` URI.
- With `.agent-workflow/templates/srs-capability.html` listing `{{requirements}}` before `{{purpose}}` and no `{{assets}}`, each chapter shows requirements first and no assets.

### US-4: A broken reference does not stop the export
As a BA, I want the export to finish and tell me which images are missing, so that I fix them without losing the document.

Acceptance criteria:
- A `description.md` that names a missing image: the file is written, shows the alt text, and the command exits 1 naming `<file>: <image path>`.
- `gin-workflow specs export nope` exits 2 with an unknown-capability message and writes nothing.

## Errors and compatibility

- Legacy layout: `specs export` exits 2 like the other `specs` commands that need `layout: sdd`.
- The export does not lint: a malformed requirement block is shown as `parse_blocks` returns it. `specs lint` remains the check.
- A capability without `diagrams/` or `assets/` exports with those sections empty.
- Large images grow the file, since every image is embedded; no size limit is applied.
- Diagrams need network access when the file is opened or printed; without it, their Mermaid source is shown.
- No new dependency: stdlib only.
- Existing commands, templates, and config are unchanged.

## Testing

- `tests/workflow_core/test_specs_export.py`, with the fixtures of `specs_fixtures.py`:
  - one capability: path printed, chapter content (purpose, `<pre class="mermaid">`, REQ anchors, scenarios), images embedded as `data:` URIs, no local `src` left;
  - `--all`: chapter order, table of contents links;
  - `--out`, the default paths, and overwrite;
  - asset order: dated folders oldest first, an image already shown by `description.md` not repeated, a non-image file listed by name, flat files last;
  - missing image: file written, alt text shown, exit 1 with `missing`; unknown capability, neither or both selectors, legacy layout: exit 2;
  - template overrides: a logo `src` embedded, reordered and deleted placeholders, a `{{...}}` inside spec text left as is;
  - converter: each supported construct, HTML comments removed, raw HTML escaped, heading shift and cap.
- `tests/workflow_core/test_specs.py`: `specs template srs.html` and `srs-capability.html` print their placeholders; `srs.html` pins an exact Mermaid version with `integrity`.
- `tests/workflow_core/test_skill_routing.py` and `test_token_budget.py`: `gin-sdd` names `specs export` and stays within 6,000 characters.
- `gin-workflow docs check` on the changed pages exits 0; `mkdocs build --strict` runs in CI.
- Full suite `python3 -m pytest -n auto` through the pre-push hook.
