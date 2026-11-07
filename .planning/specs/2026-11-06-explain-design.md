# gin:explain: interactive HTML page explaining a capability or a change

Epic: gin-workflow-explain
Status: draft for user review.

## Goal and scope

A developer, PM, or BA wants to understand one capability or one change without reading `spec.md`, the diagrams, the dated asset folders, and the change files one by one. `gin specs export` (epic `gin-workflow-bel0`) already turns a living spec into one printable HTML file (`plugins/gin-workflow/src/scripts/workflow_core/specs_export.py`); it is built for print, has no navigation, shows user stories nowhere, and lists a mockup only by file name.

This spec adds:
- a CLI command `gin specs explain <name> [--narrative FILE] [--out FILE]` that renders one interactive HTML page for a capability or an active change, reusing the export's Markdown converter, embedding, and trust boundary with a new template;
- a skill `gin:explain` in the gin-workflow plugin that reads the spec, writes a short narrative summary in Markdown, runs the command with it, and reports the path;
- the reference and guide entries for both.

Decisions confirmed with the user:
- The page is written to `.agent-workflow/runtime/explain/<name>.html`, which `gin setup` ignores (`runtime/` in `.agent-workflow/.gitignore`, `setup_service.py:95`). It is overwritten on every run and never committed.
- The CLI renders the page deterministically; the model writes only the narrative, passed with `--narrative`.

Out of scope:
- Archived changes: once a change is archived, explain its capability.
- Publishing the page to the docs site, or opening a browser.
- The legacy (`.planning`) layout.
- Changes to `specs export` or its templates.

## Requirements

### R1. Command and target
- `gin specs explain <name> [--narrative FILE] [--out FILE]` in `workflow_core/specs_explain.py`, wired in `specs_cli.py` next to `export`, with the common `--repository` and `--format text|json`.
- It needs `artifacts.layout: sdd` (`specs.require_layout`), like `export`.
- `<name>` is a capability when `<specs>/<name>/spec.md` exists; otherwise it is a change found with `specs.find_change` (exact folder, then a unique `<id>-*` match). A name that is neither, or an ambiguous change id, exits 2 and writes nothing.
- Output: `.agent-workflow/runtime/explain/<name>.html`, where `<name>` is the capability or the change folder name; the folder is created when missing. `--out FILE` writes elsewhere; like `export --out`, it must resolve inside the repository.
- `--narrative FILE`: a Markdown file inside the repository; a missing file or one outside the repository exits 2. Without it, the page has no narrative section and the command still succeeds.
- Text output prints the path, then one `missing image: <path>` line per image not embedded; `--format json` prints `{"path", "kind", "missing"}` with `kind` `capability` or `change`.
- Exit codes as `export`: 0 ok, 1 images not embedded (the page is still written), 2 usage or configuration error.

### R2. Reuse and safety
- Markdown goes through `specs_export.markdown_html` and images through `specs_export.Embed`, so every piece of spec and narrative text is escaped, an image is embedded only when it resolves to a file inside the repository with a `MEDIA_TYPES` suffix, and a link keeps its `href` only for the schemes the export allows. Values are placed with `specs_export.fill` (one pass).
- The template is `templates/explain.html`, resolved with `specs.template_text`, so a project overrides it in `.agent-workflow/templates/explain.html` like the SRS templates.
- Mermaid loads from jsDelivr pinned to `mermaid@11.4.1` with the same SRI `integrity` as `srs.html`; offline, a diagram shows its source.
- `specs_export.py` changes only where a private helper must become shared (for example the asset-folder walk); `specs export` output stays byte-identical for the existing tests.

### R3. Page content
The page has a header (the capability or change name and the generation date) and a navigation bar with one tab per section; the tab shown follows the URL hash, so a section can be linked. A section with no content is left out of the navigation.
- **Overview:** the narrative (when given), then for a capability its `## Purpose`, for a change the `## Why` and `## What Changes` of `01-proposal.md`.
- **Requirements:** one card per requirement block (`specs.parse_blocks`), with its REQ-ID, title, body, and scenarios. A capability groups blocks by their `##` section (`Block.section`); a change groups the blocks of `02-spec-delta.md` under `ADDED`, `MODIFIED`, and `REMOVED`. A search box filters the cards by text and REQ-ID. A `Source:` path that names a dated asset folder file links to that file's place in the Mockups and images section.
- **Stories:** for a change, the `### US-<n>` blocks under `## User Stories` of its `01-proposal.md`. For a capability, the stories of every active and archived change proposal under `artifacts.changes` whose `REQ:` line names a REQ-ID of the capability's `spec.md`, each labelled with its change folder. Each story shows its REQ-IDs as links to the requirement cards on the page.
- **Diagrams:** for a capability, each `diagrams/*.md` rendered with its Mermaid block; for a change, `03-design.md` rendered, then the diagram files of each capability named in its delta.
- **Mockups and images:** the dated asset folders, oldest first: a capability shows all of its folders, a change shows the folders its delta's `Source:` lines cite. Each folder shows its `description.md` (with its `Confirmed:` line), its images in a viewer (click to enlarge, Escape or click to close), and each `mockup/index.html` embedded in an `<iframe sandbox="allow-scripts" srcdoc="...">` with a screen picker built from its `<section id>` elements. A `Source:` link to `mockup/index.html#<screen-id>` opens that screen in the embedded mockup (the parent page sends the screen id with `postMessage`; the CLI adds a listener to the embedded document that only accepts a value matching `[a-z][a-z0-9-]*`). A mockup is embedded only when it resolves to an `.html` file inside the repository under an `assets/<date>/` folder of the shown capability; otherwise it is listed by name and counted as missing.

The page is one file: inline CSS and JavaScript, images as `data:` URIs, the only network request being the pinned Mermaid script. It works from `file://` and at phone width.

### R4. Skill gin:explain
`plugins/gin-workflow/src/skills/explain/SKILL.md`, invoked as `/gin:explain <capability|change>`:
1. Preconditions: `gin state --format json` reports `project.layout: sdd`; otherwise stop and name `/gin:migrate-specs`.
2. Read the target: for a capability, `spec.md`, `diagrams/`, and each dated folder's `description.md`; for a change, its `01-proposal.md`, `02-spec-delta.md`, and `03-design.md`.
3. Write `.agent-workflow/runtime/explain/<name>.narrative.md`, 150 to 300 words: what the capability or change does and for whom, the main flow, the key decisions or rules, and what is still open (unconfirmed dated folders, `## Open questions`, `?` values). Cite REQ-IDs; state nothing the files do not say.
4. Run `gin specs explain <name> --narrative <that file>`; report the page path and any `missing image:` lines; on exit 2, report the error and stop.
5. Never commit and never edit the specs.
The skill's frontmatter description stays short: the total description budget is 4,000 characters and 3,370 are used.

### R5. Documentation
- `docs/reference/cli.md`: an `explain` row in the `gin specs` table and the exit codes.
- `docs/reference/skills.md` and `skills.vi.md`: `explain` with one line.
- `docs/guides/sdd.md` and `sdd.vi.md`: a section "Explaining a capability" after "Exporting an SRS": the command, the default path, that the page is not committed, the narrative from the skill, and the template override.
- `docs/guides/customizing-templates.md` (and `.vi.md`): `explain.html` and its placeholders.

## User Stories

### US-1: Understand a capability at a glance
As a developer joining a project, I want one page that explains a capability with its requirements, diagrams, mockups, and the stories behind them, so that I understand it without opening every spec file.

Acceptance criteria:
- `/gin:explain reports` in an SDD project writes `.agent-workflow/runtime/explain/reports.html` and reports its path.
- The page opens offline from `file://` with tabs Overview, Requirements, Stories, Diagrams, and Mockups and images; Mermaid diagrams draw when online and show their source offline.
- The Overview tab starts with a narrative that cites REQ-IDs of `reports`.
- The Stories tab lists the stories of archived and active changes whose `REQ:` lines name a `REQ-REPORTS-*` ID.
- `git status` shows no new file after the run.

### US-2: Review a change before it is archived
As a reviewer, I want the page for an active change, so that I see what it adds, modifies, and removes next to its stories, design, and the inputs it cites.

Acceptance criteria:
- `gin specs explain <change-id>` writes `.agent-workflow/runtime/explain/<change-folder>.html`.
- Its Requirements tab groups the delta blocks under ADDED, MODIFIED, and REMOVED, and the search box filters them.
- Its Mockups and images tab shows only the dated folders the delta's `Source:` lines cite.

### US-3: Follow a requirement to its mockup
As a BA, I want a requirement's `Source:` link to open the cited mockup screen on the same page, so that I can check the requirement against the screen the customer confirmed.

Acceptance criteria:
- Clicking `assets/<date>/mockup/index.html#new-order` on a requirement card shows the Mockups and images tab with the embedded mockup on screen `new-order`.
- The embedded mockup runs its own navigation and state buttons, and cannot read the parent page (sandbox without `allow-same-origin`).
- A mockup path outside the repository is not embedded, and the command exits 1 naming it.

### US-4: A team's own look
As a team lead, I want to change the page's layout and branding, so that the page matches our other documents.

Acceptance criteria:
- A `.agent-workflow/templates/explain.html` in the project replaces the built-in template.
- The placeholders are documented in `docs/guides/customizing-templates.md`.

## Errors and compatibility

- Legacy layout or no `gin setup`: exit 2 with the existing `require_layout` or `load_config` message.
- Unknown or ambiguous name: exit 2, nothing written. A name matching both a capability and a change is taken as the capability; the change folder name always carries its epic prefix, so this is unlikely.
- A capability with no `spec.md` requirements, diagrams, assets, or stories: the page shows the sections that have content; this is not an error.
- An archived change id: `find_change` does not see it; exit 2 says the change is unknown, and the guide says to explain its capability.
- Images or mockups not embedded: listed, exit 1, the page is still written (as `export`).
- A narrative with raw HTML or `javascript:` links: escaped or rendered as text by `markdown_html`.
- A large mockup grows the page by its size, escaped once into `srcdoc`; no size limit.
- Risk: `srcdoc` with `postMessage` depends on the mockup skeleton's hash routing (`plugins/gin-ba/src/skills/mockup/references/mockup-html.md`); a hand-written mockup without it still embeds but does not jump to the screen.

## Testing

- `tests/workflow_core/test_specs_explain.py`, on temporary SDD repositories:
  - capability mode: tabs present, blocks grouped by `##` section, diagrams rendered, dated folders oldest first, stories gathered from an active and an archived proposal and not from a proposal naming another capability's REQ-IDs;
  - change mode: delta grouped ADDED/MODIFIED/REMOVED, proposal Why and What Changes in Overview, only cited dated folders shown;
  - mockup: embedded as a sandboxed `srcdoc` iframe without `allow-same-origin`, with the screen picker ids; a mockup symlinked outside the repository is listed as missing and exits 1;
  - narrative: rendered and escaped (`<script>` text stays text); a narrative or `--out` outside the repository exits 2 and writes nothing;
  - unknown and ambiguous names exit 2; legacy layout exits 2;
  - default output path under `.agent-workflow/runtime/explain/` and `--format json` keys;
  - a project template override is used.
- `tests/workflow_core/test_specs_export.py` stays green unchanged.
- `tests/workflow_core/test_skill_routing.py`: the explain skill names `gin specs explain`, `--narrative`, `project.layout: sdd`, and "Never commit"; `description_chars` stays within 4,000.
- `tests/workflow_core/test_docs_coverage.py` passes with `explain` in `docs/reference/skills.md`.
- Review evidence, manual: run `/gin:explain` on a sample capability with a confirmed mockup and on an active change; open both pages offline and online and check tabs, search, stories, diagrams, the image viewer, and a `Source:` jump into the mockup.
