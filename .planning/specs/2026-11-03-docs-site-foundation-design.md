# Documentation site foundation

Workflow: docs-site-foundation
Status: draft for user review.
Origin: user request on 2026-11-03 to publish the documentation on GitHub Pages in English and Vietnamese with a language switcher, deployed by the release pipeline, which also produces an installable release package. This is part 1 of 3. Part 2 (content rewrite: installation page, role guides, getting started for non-technical readers) and part 3 (Vietnamese translation) get their own specs after this one ships.

## Goal and scope

Readers today find the documentation only by browsing `docs/` on GitHub. After this change `https://giangdhwhtbr.github.io/gin-workflow/` serves the same pages with navigation, search, and an English / Vietnamese switcher, and every tagged release both updates the site and attaches an installable source archive to the GitHub release.

In scope:
- A MkDocs Material site built from `docs/` as it is, with explicit navigation and Mermaid support.
- Bilingual layout with `mkdocs-static-i18n` (suffix structure, English default, Vietnamese falling back to English), proven by one translated page.
- Removal of the slide decks and the 2.0 / 2.1 upgrade guides, and of every link to them.
- `release.yml`: source archive attached to the release, then a Pages deploy job.
- `test.yml`: a strict site build on Linux so broken links fail pull requests.
- Documentation of local preview, the one-time Pages enablement, and the extended release procedure.

Out of scope:
- Rewriting or restructuring page content (part 2) and translating pages (part 3).
- Versioned documentation per release (`mike`), a custom domain, PR preview deployments.
- Generating `docs/reference/cli.md` or `skills.md` from source; the coverage tests keep enforcing them by hand.
- Changing `remote-install.sh` or `install.sh` to consume the release archive.
- A prebuilt per-harness `dist/` package.

Decided with the user on 2026-11-03: MkDocs Material over Docusaurus and VitePress (Python-only CI, files stay in place, per-page fallback); the release package is the source archive, not a built `dist/`; `docs/presentations/` and both upgrade guides are deleted rather than carried over.

## Requirements

### R1. `mkdocs.yml` at the repository root

- `site_name: gin-workflow`, `site_url: https://giangdhwhtbr.github.io/gin-workflow/`, `repo_url` pointing at the GitHub repository, `docs_dir: docs`, `site_dir: site`.
- Theme `material` with navigation tabs, section indexes, search, and the light / dark palette toggle. No custom CSS or overrides in this part.
- Markdown extensions: `admonition`, `tables`, `toc` with permalinks, `pymdownx.superfences` with the `mermaid` custom fence so the existing Mermaid blocks render, `pymdownx.highlight`.
- `nav` lists every page under `docs/` explicitly, grouped as the README table groups them: Home, Getting started, Roles, Starters, Concepts, Guides, Orchestrator, Reference, Contributing. `mkdocs build --strict` fails when a page in `docs/` is missing from `nav` or a link does not resolve, so the nav cannot drift silently.
- Plugins: `search` and `i18n` (R3).

### R2. Home page

- New `docs/index.md`: a short landing page (under 150 words) that says what gin-workflow is and links to Getting started, Roles, the guides, and the reference. It follows the mechanical style rules enforced by `tests/workflow_core/test_docs_coverage.py` (no numbered headings, no bold-label list items, no dashes, no emoji) and is linked from the README documentation table so `test_every_docs_page_is_in_the_readme_map` passes.
- Part 2 rewrites this page; here it only has to exist and route readers.

### R3. Bilingual layout

- `mkdocs-static-i18n` with `docs_structure: suffix`: a translation sits next to its source, `docs/<page>.vi.md` beside `docs/<page>.md`. Languages: `en` (default, name `English`) and `vi` (name `Tiếng Việt`). `fallback_to_default: true`, `reconfigure_material: true`, `reconfigure_search: true`.
- The Material header shows the language switcher on every page. Opening a `vi` URL for a page without a `.vi.md` file shows the English content at the `vi` URL, so translation can land page by page in part 3.
- Exactly one translated page ships in this part: `docs/index.vi.md`, a Vietnamese version of the home page, which proves the switcher, the `vi` build, and the fallback for every other page.
- Nav titles are translated through the plugin's `nav_translations` for `vi`; untranslated titles stay English.

### R4. Removed pages

Deleted, with every link to them removed and the surrounding sentence or list item rewritten so it still reads correctly:
- `docs/presentations/` (`adlc.html`, `adlc.pptx`, `brownfield-modernization.html`, `brownfield-modernization.pptx`, `brownfield-modernization-script.md`, `build_brownfield_pptx.py`). Links: `README.md` Reference row, `docs/getting-started.md` "Starters and guides", `docs/starters/brownfield-modernize.md` "Related".
- `docs/reference/upgrade-2.0.md` and `docs/reference/upgrade-2.1.md`. Links: `README.md` Reference row, `docs/orchestrator/routing.md` (the schema 2.8 sentence keeps its pointer to `config.md#versions-and-migration` and drops the two upgrade links).
- `tests/workflow_core/test_adlc_deck.py` and the `STYLE_EXEMPT` entry in `test_docs_coverage.py`.
- `.gitattributes` keeps its `*.pptx binary` line; it is harmless.

### R5. Links that leave `docs/`

The site contains only `docs/`, so the four relative links into the repository root are rewritten as absolute `https://github.com/giangdhwhtbr/gin-workflow/blob/master/...` URLs: `docs/orchestrator/README.md` and `docs/reference/orchestrator-contract.md` to `plugins/gin-orchestrator/src/README.md`, `docs/guides/recommended-tools.md` to `plugins/gin-workflow/src/references/stage-contract.md` and to `README.md#dependencies`. `test_relative_links_resolve` skips `https:` links, and `mkdocs build --strict` no longer warns about them.

### R6. Tests and pull-request CI

- `tests/workflow_core/test_docs_coverage.py`: `test_every_docs_page_is_in_the_readme_map` ignores files whose name ends in `.vi.md`. Every other check (relative links, Mermaid types, style rules, forbidden phrases) still runs on translated pages. A new test asserts the exemption: a `.vi.md` page absent from the README does not fail the map check, and a `.md` page absent from it still does.
- `.github/workflows/test.yml`, `linux` job: after the unit tests, `python3 -m pip install -r requirements-docs.txt` then `mkdocs build --strict`. The Windows job is unchanged.
- `requirements-docs.txt` at the repository root pins `mkdocs-material` and `mkdocs-static-i18n` to exact versions, the current releases at implementation time. It is the single source for CI and for local preview.

### R7. Release workflow

`.github/workflows/release.yml` keeps its trigger (`v*.*.*` tags and `workflow_dispatch`) and gains:

- In job `release`, after the tests and before `gh release create`: a packaging step that runs `git archive` twice from the tagged commit with prefix `gin-workflow-<tag>/` and the explicit path list `plugins scripts install.sh install.ps1 remote-install.sh README.md LICENSE docs`, producing `gin-workflow-<tag>.tar.gz` and `gin-workflow-<tag>.zip`. `gh release create` uploads both as assets. Both steps keep the existing `if: startsWith(github.ref, 'refs/tags/')` guard, so `workflow_dispatch` still only runs the tests.
- A new job `pages` with `needs: release`, `permissions: { contents: read, pages: write, id-token: write }` at job level (the `release` job keeps `contents: write` only), `concurrency: { group: pages, cancel-in-progress: false }`, and `environment: github-pages`. Steps: checkout, `setup-python` 3.12, `pip install -r requirements-docs.txt`, `mkdocs build --strict`, `actions/configure-pages`, `actions/upload-pages-artifact` with `path: site`, `actions/deploy-pages`. It runs on tag pushes and on `workflow_dispatch`, so the site can be redeployed by hand without cutting a release.
- Pages must be enabled once in the repository settings with source "GitHub Actions"; `GITHUB_TOKEN` cannot do it from the workflow. Until then the `pages` job fails at `configure-pages` while the `release` job has already succeeded.

### R8. Documentation and housekeeping

- `docs/contributing.md`: a "Documentation site" section with local preview (`python3 -m pip install -r requirements-docs.txt`, `mkdocs serve`), where translations go (`<page>.vi.md`), and the one-time Pages enablement; step 4 of "Releasing" states that the tag also attaches the source archives and deploys the site, and that `workflow_dispatch` redeploys the site only.
- `README.md` "Documentation": the site URL on the first line; the table of in-repo links stays, minus the removed pages, plus the home page.
- `.gitignore`: `/site/`.

## User Stories

### US-1: Read the documentation on the web
As a team member, I want to open the documentation in a browser with navigation and search, so that I can find a page without browsing the repository tree.

Acceptance criteria:
- `https://giangdhwhtbr.github.io/gin-workflow/` serves the home page with a navigation tree that lists every page under `docs/`.
- Search returns results for a term that appears in `docs/reference/cli.md`.
- The Mermaid diagrams in `docs/concepts/architecture.md` render as diagrams, not as code blocks.

### US-2: Switch language
As a Vietnamese-speaking team member, I want a language switcher on every page, so that I read a page in Vietnamese when it exists and still get the English page when it does not.

Acceptance criteria:
- The header on every page offers `English` and `Tiếng Việt`.
- Switching to `Tiếng Việt` on the home page shows the content of `docs/index.vi.md` at the `/vi/` URL.
- Switching to `Tiếng Việt` on Getting started shows the English content at `/vi/getting-started/`, with the switcher still present.

### US-3: Release updates the package and the site
As the maintainer, I want pushing a release tag to attach an installable archive and redeploy the site, so that the published documentation never lags the released plugin.

Acceptance criteria:
- After `git push origin vX.Y.Z` the GitHub release lists `gin-workflow-vX.Y.Z.tar.gz` and `gin-workflow-vX.Y.Z.zip`; unpacking the tarball gives `gin-workflow-vX.Y.Z/install.sh` and `plugins/`, and no `tests/`, `.github/`, or `.planning/`.
- The same workflow run has a green `pages` job and the site shows the content of the tagged commit.
- A `workflow_dispatch` run redeploys the site and creates no release.

### US-4: Broken documentation fails the pull request
As a contributor, I want a broken link or a page missing from the navigation to fail CI, so that the site never deploys with a dead link.

Acceptance criteria:
- A pull request that adds `docs/guides/new.md` without a `nav` entry fails the `linux` job at `mkdocs build --strict`.
- A pull request that links `docs/missing.md` fails `test_relative_links_resolve` and `mkdocs build --strict`.
- A pull request that adds `docs/guides/qa.vi.md` without touching the README passes `test_every_docs_page_is_in_the_readme_map`.

## Errors and compatibility

- Pages not yet enabled: the `pages` job fails at `configure-pages` with the GitHub error; the release and its assets are already published. Enabling Pages and re-running the job, or running `workflow_dispatch`, deploys the site.
- `mkdocs build --strict` treats every warning as an error, including a page missing from `nav`, a broken relative link, and an unknown Mermaid fence. CI output names the file and link.
- Relative `.md` links keep working when the pages are read on GitHub; MkDocs rewrites them to site URLs at build time. Links from specs and plans under `.planning/` to the deleted pages are historical and are not rewritten.
- `remote-install.sh`, `install.sh`, `install.ps1`, and the marketplace installs are unchanged; the archive is an additional way to obtain the same tree.
- Job-level permissions on `pages` do not widen the `release` job. `concurrency: pages` serialises deploys when two tags are pushed close together.
- `docs_structure: suffix` leaves `docs/` readable in the repository: every `.vi.md` sits next to its English source and nothing moves into language folders.

## Testing

- `python3 -m unittest discover -s tests` passes after removing `test_adlc_deck.py` and extending `test_docs_coverage.py`; the new exemption test fails if the `.vi.md` filter is removed.
- Local: `python3 -m pip install -r requirements-docs.txt && mkdocs build --strict` prints no warning; `mkdocs serve` shows the switcher, `docs/index.vi.md` at `/vi/`, English fallback at `/vi/getting-started/`, and rendered Mermaid in Architecture.
- Local: `git archive --format=tar.gz --prefix=gin-workflow-test/ -o /tmp/pkg.tar.gz HEAD plugins scripts install.sh install.ps1 remote-install.sh README.md LICENSE docs`, unpack, run `./install.sh --help` from inside the unpacked tree.
- Workflows: `actionlint` on both YAML files when it is installed; the first tag push after merge, or one `workflow_dispatch` run, is the end-to-end proof for R7 and is recorded in the ship handoff.
