# Plan: Documentation site foundation

Spec: `.planning/specs/2026-11-03-docs-site-foundation-design.md` (Workflow: `docs-site-foundation`).

## Objective

`https://giangdhwhtbr.github.io/gin-workflow/` serves every page under `docs/` with navigation, search, Mermaid diagrams, and an English / Vietnamese switcher; pushing a release tag attaches `gin-workflow-vX.Y.Z.tar.gz` and `.zip` to the GitHub release and redeploys the site; a broken link or a page missing from the navigation fails the pull-request CI. The slide decks and the 2.0 / 2.1 upgrade guides are gone.

## Architecture

- MkDocs Material builds `docs/` into `site/`. `mkdocs.yml` at the repository root holds the explicit `nav`, the Mermaid fence, and the `i18n` plugin (suffix layout: `docs/<page>.vi.md` beside `docs/<page>.md`, `vi` falls back to `en`).
- `tests/workflow_core/test_docs_coverage.py` keeps enforcing link resolution and style on every `docs/**/*.md`; only the "linked from README" rule exempts `*.vi.md`.
- `.github/workflows/test.yml` adds `mkdocs build --strict` to the Linux job. `.github/workflows/release.yml` packages the source tree with `git archive`, attaches it to the release, then a second job deploys `site/` with the official Pages actions.

## Tech Stack

Python 3.12, `mkdocs-material==9.8.0`, `mkdocs-static-i18n==1.3.1` (pinned in `requirements-docs.txt`), GitHub Actions (`actions/configure-pages@v5`, `actions/upload-pages-artifact@v3`, `actions/deploy-pages@v4`), `git archive`, `unittest`.

## Global Constraints

Copied from the spec:

- Out of scope: rewriting or restructuring page content (part 2) and translating pages (part 3); versioned documentation per release (`mike`), a custom domain, PR preview deployments; generating `docs/reference/cli.md` or `skills.md` from source; changing `remote-install.sh` or `install.sh` to consume the release archive; a prebuilt per-harness `dist/` package.
- Decided with the user on 2026-11-03: MkDocs Material over Docusaurus and VitePress; the release package is the source archive, not a built `dist/`; `docs/presentations/` and both upgrade guides are deleted rather than carried over.
- `docs_structure: suffix` leaves `docs/` readable in the repository: every `.vi.md` sits next to its English source and nothing moves into language folders.
- Job-level permissions on `pages` do not widen the `release` job.
- Pages must be enabled once in the repository settings with source "GitHub Actions"; `GITHUB_TOKEN` cannot do it from the workflow.
- Every page under `docs/` follows the mechanical style rules of `test_docs_coverage.py`: no numbered headings, no bold-label list items, no en or em dash, no emoji.

## Route Rubric

- Choose the weakest model that can do the work.
- Raise the model for broad context or design judgement.
- Raise the effort for intrinsic difficulty: intricate logic, many edge cases, or long chains of steps.

| Kind of work | Model | Effort |
|---|---|---|
| Mechanical edits, documentation, boilerplate | weakest | `low` |
| Bounded implementation with a clear spec | middle | `medium` |
| Cross-module change, security, migration, concurrency | strongest | `high` |

Unclear requirements never raise the model or effort.

## Requirement Analysis

- Problem statement: the documentation is readable only by browsing `docs/` on GitHub, has no search, no navigation, no Vietnamese, and nothing redeploys it when the plugin changes; the release has no downloadable package.
- Success criteria: spec US-1 to US-4. Locally: `python3 -m unittest tests/workflow_core/test_docs_coverage.py` passes, `mkdocs build --strict` prints no warning, `/vi/` shows `index.vi.md`, `/vi/getting-started/` shows the English text with the switcher. In CI: the Linux job runs the strict build; a tag push produces two assets and a green `pages` job.
- Constraints: Global Constraints above; CI has Python only (no Node); `test_docs_coverage.py` scans every `docs/**/*.md` including translations.
- Non-goals: content rewrite, translation beyond `index.vi.md`, versioned docs, custom domain, PR previews, doc generation, install-script changes.

## Approach Options

### Option 1: Three sequential tracks on one branch
- Summary: Track 1 deletes the deprecated pages and rewrites the links that leave `docs/`; Track 2 adds `mkdocs.yml`, the home pages, the i18n layout, the test exemption, and the strict build in `test.yml`; Track 3 extends `release.yml` and `contributing.md`.
- Pros: each track has its own test cycle (`test_docs_coverage.py`, then `mkdocs build --strict`, then workflow syntax plus archive check); Track 2's strict build only passes once Track 1 removed the links that leave `docs/`, so the order mirrors the dependency; `README.md` is edited in Track 1 and Track 2 without conflict because the tracks run one after another.
- Cons: no parallelism; a reviewer sees three small pull-request-sized changes instead of one.

### Option 2: One track for everything
- Summary: a single track with all files.
- Pros: one review.
- Cons: the review mixes a file deletion sweep, a new build system, and CI permissions; a failure in the strict build is harder to attribute; it violates the smallest-independently-rejectable-unit rule.

### Recommended Approach
- Selected option: Option 1.
- Rationale: three independent review units with clear tests, ordered by their real dependency.

## Scope

- In scope: R1 to R8 of the spec, mapped below (R4, R5 to Track 1; R1, R2, R3, R6 and the README and `.gitignore` parts of R8 to Track 2; R7 and the `contributing.md` part of R8 to Track 3).
- Out of scope: Global Constraints above.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Track 2 needs Track 1's link rewrites for the strict build to pass, Track 3 needs Track 2's mkdocs.yml and requirements-docs.txt, and Tracks 1 and 2 both edit README.md.
```

## Tasks

### Track 1: Remove deprecated pages and rewrite links that leave docs/
- **Dependencies**: none
- **Files**:
  - Delete `docs/presentations/adlc.html`, `docs/presentations/adlc.pptx`, `docs/presentations/brownfield-modernization.html`, `docs/presentations/brownfield-modernization.pptx`, `docs/presentations/brownfield-modernization-script.md`, `docs/presentations/build_brownfield_pptx.py`
  - Delete `docs/reference/upgrade-2.0.md`, `docs/reference/upgrade-2.1.md`
  - Delete `tests/workflow_core/test_adlc_deck.py`
  - Modify `README.md:16` (drop the upgrade and deck links from the Reference row)
  - Modify `docs/getting-started.md:94` (delete the ADLC deck bullet)
  - Modify `docs/starters/brownfield-modernize.md:72` (delete the deck bullet)
  - Modify `docs/orchestrator/routing.md:58` (drop the two upgrade links)
  - Modify `docs/guides/recommended-tools.md:3,31` (absolute GitHub URLs)
  - Modify `docs/orchestrator/README.md:21` (absolute GitHub URL)
  - Modify `docs/reference/orchestrator-contract.md:5` (absolute GitHub URL)
  - Modify `docs/reference/troubleshooting.md:80`, `docs/starters/greenfield.md:9` (absolute GitHub URLs)
  - Modify `tests/workflow_core/test_docs_coverage.py:22,89-94` (remove `STYLE_EXEMPT`)
  - Test `tests/workflow_core/test_docs_coverage.py`
- **Provider role**: `docs`
- **Model:** `haiku`
- **Effort:** `low`
- **Why:** mechanical deletions and line edits with the exact replacement text below; the existing test suite is the check.
- **Acceptance criteria**: `docs/presentations/`, both upgrade guides, and `test_adlc_deck.py` no longer exist; `grep -rn "presentations/\|upgrade-2\." README.md docs tests` prints nothing; `python3 -m unittest tests/workflow_core/test_docs_coverage.py -v` passes; `grep -rn "\](\.\./\.\./" docs` prints nothing.
- **Estimated complexity**: low

Steps:

1. Run the test first to see the current baseline: `python3 -m unittest tests/workflow_core/test_docs_coverage.py -v` passes (10 tests). Delete the files:
   ```bash
   git rm -q -r docs/presentations docs/reference/upgrade-2.0.md docs/reference/upgrade-2.1.md tests/workflow_core/test_adlc_deck.py
   ```
   Run the test again: `test_relative_links_resolve` fails with the dead links (`README.md -> docs/reference/upgrade-2.0.md`, `README.md -> docs/reference/upgrade-2.1.md`, `README.md -> docs/presentations/...`, `docs/getting-started.md -> presentations/adlc.html`, `docs/starters/brownfield-modernize.md -> ../presentations/...`, `docs/orchestrator/routing.md -> ../reference/upgrade-2.0.md`), and `test_pages_follow_the_mechanical_style_rules` still passes.
2. `README.md:16` becomes exactly:
   ```markdown
   | Reference | [skills](docs/reference/skills.md), [CLI](docs/reference/cli.md), [configuration](docs/reference/config.md), [troubleshooting](docs/reference/troubleshooting.md), [orchestrator contract](docs/reference/orchestrator-contract.md) |
   ```
3. Delete `docs/getting-started.md:94` (`- The lifecycle on slides: the [ADLC deck](presentations/adlc.html) ([PPTX](presentations/adlc.pptx)).`) and `docs/starters/brownfield-modernize.md:72` (`- [Brownfield modernization deck](../presentations/brownfield-modernization.html) ([PPTX](../presentations/brownfield-modernization.pptx)) for executive and team presentations.`). The surrounding lists keep their other bullets.
4. `docs/orchestrator/routing.md:58`: replace `moves them ([upgrade notes](../reference/upgrade-2.0.md), [2.1](../reference/upgrade-2.1.md)). The schema 2.9 migration` with `moves them. The schema 2.9 migration`.
5. Rewrite the six links that leave `docs/`:
   - `docs/guides/recommended-tools.md:3`: `[required dependencies](../../README.md#dependencies)` becomes `[required dependencies](https://github.com/giangdhwhtbr/gin-workflow/blob/master/README.md#dependencies)`.
   - `docs/guides/recommended-tools.md:31`: `[stage contract](../../plugins/gin-workflow/src/references/stage-contract.md)` becomes `[stage contract](https://github.com/giangdhwhtbr/gin-workflow/blob/master/plugins/gin-workflow/src/references/stage-contract.md)`.
   - `docs/orchestrator/README.md:21`: `[plugin README](../../plugins/gin-orchestrator/src/README.md)` becomes `[plugin README](https://github.com/giangdhwhtbr/gin-workflow/blob/master/plugins/gin-orchestrator/src/README.md)`.
   - `docs/reference/orchestrator-contract.md:5`: `[the plugin README](../../plugins/gin-orchestrator/src/README.md)` becomes `[the plugin README](https://github.com/giangdhwhtbr/gin-workflow/blob/master/plugins/gin-orchestrator/src/README.md)`.
   - `docs/reference/troubleshooting.md:80`: `[Installation](../../README.md#installation)` becomes `[Installation](https://github.com/giangdhwhtbr/gin-workflow/blob/master/README.md#installation)`.
   - `docs/starters/greenfield.md:9`: `[dependencies](../../README.md#dependencies)` becomes `[dependencies](https://github.com/giangdhwhtbr/gin-workflow/blob/master/README.md#dependencies)`.
6. `tests/workflow_core/test_docs_coverage.py`: delete line 22 (`STYLE_EXEMPT = {...}`) and the blank line after it, and replace lines 89 to 94 with:
   ```python
       def test_pages_follow_the_mechanical_style_rules(self):
           problems = [f"{page.relative_to(ROOT).as_posix()}:{found}"
                       for page in [ROOT / "README.md", *sorted(DOCS.rglob("*.md"))]
                       for found in style_violations(page.read_text(encoding="utf-8"))]
           self.assertEqual(problems, [])
   ```
7. Run `python3 -m unittest tests/workflow_core/test_docs_coverage.py -v`: 10 tests, `OK`. Run `grep -rn "presentations/\|upgrade-2\." README.md docs tests` and `grep -rn "\](\.\./\.\./" docs`: both print nothing. Commit: `docs: remove slide decks and upgrade guides, link out of docs/ by URL`.

### Track 2: MkDocs site with bilingual layout and CI build
- **Dependencies**: Track 1
- **Files**:
  - Create `mkdocs.yml`
  - Create `requirements-docs.txt`
  - Create `docs/index.md`
  - Create `docs/index.vi.md`
  - Modify `.gitignore:45` (append `/site/`)
  - Modify `README.md:5-9` (site URL line and the home page link)
  - Modify `.github/workflows/test.yml:28-29` (strict build step)
  - Modify `tests/workflow_core/test_docs_coverage.py:25-27,55-59` (`unlisted_pages` helper, `.vi.md` exemption, new test)
  - Test `tests/workflow_core/test_docs_coverage.py`
- **Provider role**: `general`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** bounded implementation with the exact configuration below, but the strict build and the i18n plugin interact with every existing page, so the executor must read build output and fix whatever the strict build reports under the rules in step 7.
- **Acceptance criteria**: `python3 -m unittest tests/workflow_core/test_docs_coverage.py -v` passes with 11 tests, including `test_translations_are_exempt_from_the_readme_map`; `uv run --with-requirements requirements-docs.txt -- mkdocs build --strict` exits 0 with no `WARNING` line; `site/index.html` and `site/vi/index.html` exist and differ; `site/vi/getting-started/index.html` exists and contains the English heading `Getting started`; `site/concepts/architecture/index.html` contains `class="mermaid"`; `grep -c 'hreflang' site/index.html` is at least 2 (the language switcher).
- **Estimated complexity**: medium

Steps:

1. Failing test first. In `tests/workflow_core/test_docs_coverage.py` add, after `pages()` (line 27), the helper:
   ```python
   def unlisted_pages(readme: str, docs_pages: list[Path]) -> list[str]:
       """Docs pages the README map does not link; translations (`*.vi.md`) are exempt."""
       linked = {(ROOT / target.split("#", 1)[0]).resolve() for target in LINK.findall(readme)}
       return [str(p.relative_to(ROOT)) for p in docs_pages
               if not p.name.endswith(".vi.md") and p.resolve() not in linked]
   ```
   Replace `test_every_docs_page_is_in_the_readme_map` (lines 55 to 59) with:
   ```python
       def test_every_docs_page_is_in_the_readme_map(self):
           readme = (ROOT / "README.md").read_text(encoding="utf-8")
           self.assertEqual(unlisted_pages(readme, sorted(DOCS.rglob("*.md"))), [])

       def test_translations_are_exempt_from_the_readme_map(self):
           pages_ = [DOCS / "guides/qa.vi.md", DOCS / "guides/missing.md"]
           self.assertEqual(unlisted_pages("[qa](docs/guides/qa.md)", pages_), ["docs/guides/missing.md"])
   ```
   Run `python3 -m unittest tests/workflow_core/test_docs_coverage.py -v`: 11 tests, `OK` (the helper and its test land together; the next steps keep it green while `docs/index.md` and `docs/index.vi.md` appear).
2. Create `requirements-docs.txt`:
   ```
   mkdocs-material==9.8.0
   mkdocs-static-i18n==1.3.1
   ```
   If `mkdocs build --strict` in step 6 fails with an import or version error from `mkdocs-static-i18n` against this `mkdocs-material`, pin `mkdocs-material` to the newest 9.x release that builds and note the pair in the commit message.
3. Create `docs/index.md`:
   ```markdown
   # gin-workflow

   gin-workflow is a plugin for Claude Code, Codex CLI, Antigravity CLI, and OpenCode that takes a change from requirement to merge through recorded gates: discuss, plan, orchestrate, execute, verify, ship. Nothing is merged without your approval, and a `/quick` path handles small changes.

   ## Where to start

   - [Getting started](getting-started.md): install the plugin and run one feature from idea to merge.
   - [Team roles](roles.md): what a PM, a BA, a developer, and a tester each do and read.
   - [Starters](starters/greenfield.md): greenfield and brownfield entry points.
   - [Guides](guides/use-cases.md): use cases, recommended tools, Windows, team mode, and the QA add-on.
   - [Reference](reference/skills.md): every skill, CLI command, and configuration key.

   The source and issue tracker live on [GitHub](https://github.com/giangdhwhtbr/gin-workflow).
   ```
   Create `docs/index.vi.md`:
   ```markdown
   # gin-workflow

   gin-workflow là plugin cho Claude Code, Codex CLI, Antigravity CLI và OpenCode, đưa một thay đổi từ yêu cầu tới lúc merge qua các cổng được ghi nhận: discuss, plan, orchestrate, execute, verify, ship. Không có gì được merge khi bạn chưa duyệt, và đường `/quick` dành cho các thay đổi nhỏ.

   ## Bắt đầu từ đâu

   - [Bắt đầu](getting-started.md): cài plugin và chạy một tính năng từ ý tưởng tới merge.
   - [Vai trò trong nhóm](roles.md): PM, BA, developer và tester mỗi người làm gì và đọc gì.
   - [Khởi đầu](starters/greenfield.md): điểm vào cho dự án mới và dự án có sẵn.
   - [Hướng dẫn](guides/use-cases.md): tình huống sử dụng, công cụ khuyến nghị, Windows, chế độ nhóm và add-on QA.
   - [Tham chiếu](reference/skills.md): mọi skill, lệnh CLI và khóa cấu hình.

   Mã nguồn và issue tracker nằm trên [GitHub](https://github.com/giangdhwhtbr/gin-workflow).
   ```
   `README.md:5-9` becomes:
   ```markdown
   ## Documentation

   Read it on the [documentation site](https://giangdhwhtbr.github.io/gin-workflow/) in English or Vietnamese, or start from the [home page](docs/index.md) in this repository:

   | Start here | |
   |---|---|
   | [Getting started](docs/getting-started.md) | one feature from idea to merge with Claude Code |
   ```
   (the table header and rows from line 7 on are unchanged apart from the inserted sentence and blank line). Run the unit test: 11 tests, `OK` (`index.md` is linked, `index.vi.md` is exempt, both pass the style rules).
4. Create `mkdocs.yml`:
   ```yaml
   site_name: gin-workflow
   site_url: https://giangdhwhtbr.github.io/gin-workflow/
   site_description: A workflow plugin that takes a change from requirement to merge through recorded gates.
   repo_url: https://github.com/giangdhwhtbr/gin-workflow
   repo_name: giangdhwhtbr/gin-workflow
   edit_uri: edit/master/docs/
   docs_dir: docs
   site_dir: site

   theme:
     name: material
     features:
       - navigation.tabs
       - navigation.sections
       - navigation.indexes
       - navigation.top
       - search.suggest
       - search.highlight
       - content.code.copy
       - toc.follow
     palette:
       - media: "(prefers-color-scheme: light)"
         scheme: default
         primary: indigo
         toggle:
           icon: material/weather-night
           name: Switch to dark mode
       - media: "(prefers-color-scheme: dark)"
         scheme: slate
         primary: indigo
         toggle:
           icon: material/weather-sunny
           name: Switch to light mode

   markdown_extensions:
     - admonition
     - tables
     - toc:
         permalink: true
     - pymdownx.highlight
     - pymdownx.superfences:
         custom_fences:
           - name: mermaid
             class: mermaid
             format: !!python/name:pymdownx.superfences.fence_code_format

   plugins:
     - search
     - i18n:
         docs_structure: suffix
         fallback_to_default: true
         reconfigure_material: true
         reconfigure_search: true
         languages:
           - locale: en
             default: true
             name: English
             build: true
           - locale: vi
             name: Tiếng Việt
             build: true
             nav_translations:
               Home: Trang chủ
               Getting started: Bắt đầu
               Team roles: Vai trò trong nhóm
               Starters: Khởi đầu
               Concepts: Khái niệm
               Guides: Hướng dẫn
               Orchestrator: Điều phối
               Reference: Tham chiếu
               Contributing: Đóng góp

   validation:
     nav:
       omitted_files: warn
       not_found: warn
       absolute_links: warn
     links:
       not_found: warn
       anchors: warn
       unrecognized_links: warn

   nav:
     - Home: index.md
     - Getting started: getting-started.md
     - Team roles: roles.md
     - Starters:
         - Greenfield: starters/greenfield.md
         - Brownfield and modernization: starters/brownfield-modernize.md
         - Brownfield walkthrough: starters/brownfield-walkthrough.md
     - Concepts:
         - Architecture: concepts/architecture.md
         - Lifecycle and gates: concepts/lifecycle.md
         - State model: concepts/state-model.md
         - Providers and routing: concepts/providers.md
     - Guides:
         - Use cases: guides/use-cases.md
         - Customizing templates: guides/customizing-templates.md
         - Recommended tools: guides/recommended-tools.md
         - Windows: guides/windows.md
         - Rule packs: guides/rules.md
         - SDD living specs: guides/sdd.md
         - Team mode: guides/team.md
         - QA add-on: guides/qa.md
         - AI usage report: guides/usage-report.md
     - Orchestrator:
         - Worker harnesses: orchestrator/README.md
         - Routing and configuration: orchestrator/routing.md
     - Reference:
         - Skills: reference/skills.md
         - CLI: reference/cli.md
         - Configuration: reference/config.md
         - Troubleshooting: reference/troubleshooting.md
         - Orchestrator contract: reference/orchestrator-contract.md
     - Contributing: contributing.md
   ```
   Append `/site/` to `.gitignore` after line 45 with a comment line `# MkDocs output` above it.
5. `.github/workflows/test.yml`: insert after line 28 (`- run: python3 -m unittest tests/test_all.py -v`) and before the smoke-test step:
   ```yaml
         - run: python3 -m pip install -r requirements-docs.txt
         - run: mkdocs build --strict
   ```
6. Build locally (this machine's Python is externally managed, so use `uv`):
   ```bash
   uv run --with-requirements requirements-docs.txt -- mkdocs build --strict
   ```
   Expected: exit 0, last line `INFO    -  Documentation built in N seconds`, no `WARNING`.
7. If the strict build reports a problem, fix it by these rules and nothing else: a relative link to a file outside `docs/` becomes the matching `https://github.com/giangdhwhtbr/gin-workflow/blob/master/<path>` URL; a page the build names as absent from `nav` is added under the matching section; an anchor the build cannot find is corrected to the heading's actual slug. Rerun step 6 until it is clean. Then run the acceptance checks:
   ```bash
   test -f site/index.html && test -f site/vi/index.html && ! cmp -s site/index.html site/vi/index.html && echo home-ok
   grep -q 'Getting started' site/vi/getting-started/index.html && echo fallback-ok
   grep -q 'class="mermaid"' site/concepts/architecture/index.html && echo mermaid-ok
   test "$(grep -c hreflang site/index.html)" -ge 2 && echo switcher-ok
   ```
   Expected: `home-ok`, `fallback-ok`, `mermaid-ok`, `switcher-ok`. Run `python3 -m unittest tests/workflow_core/test_docs_coverage.py -v` once more: 11 tests, `OK`. Confirm `git status --short` does not list `site/`. Commit: `docs: build the documentation site with MkDocs Material and a Vietnamese layout`.

### Track 3: Release package and Pages deployment
- **Dependencies**: Track 2
- **Files**:
  - Modify `.github/workflows/release.yml:30-36` (package step, assets on the release, new `pages` job)
  - Modify `docs/contributing.md:101-108` (new "Documentation site" section, step 4 of Releasing)
  - Test `tests/workflow_core/test_docs_coverage.py`
- **Provider role**: `general`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** the YAML is given in full, but it grants deployment permissions and runs only in GitHub, so the executor must check the archive contents and the workflow structure carefully rather than rely on a local test.
- **Acceptance criteria**: `python3 -c "import yaml; d = yaml.safe_load(open('.github/workflows/release.yml')); assert set(d['jobs']) == {'release', 'pages'}; assert d['jobs']['pages']['needs'] == 'release'; assert d['jobs']['pages']['permissions'] == {'contents': 'read', 'pages': 'write', 'id-token': 'write'}; assert d['permissions'] == {'contents': 'write'}; print('ok')"` prints `ok`; the local `git archive` check in step 2 lists `install.sh` and `plugins/` and no `tests/`, `.github/`, or `.planning/`; `python3 -m unittest tests/workflow_core/test_docs_coverage.py -v` passes (contributing.md still follows the style rules); `uv run --with-requirements requirements-docs.txt -- mkdocs build --strict` still exits 0.
- **Estimated complexity**: medium

Steps:

1. Replace `.github/workflows/release.yml` lines 30 to 36 (from `- name: Tests` to the end) with:
   ```yaml
         - name: Tests
           run: python3 -m unittest discover -s tests -v
         - name: Package the release
           if: startsWith(github.ref, 'refs/tags/')
           run: |
             prefix="gin-workflow-$GITHUB_REF_NAME"
             paths="plugins scripts install.sh install.ps1 remote-install.sh README.md LICENSE docs"
             git archive --format=tar.gz --prefix="$prefix/" -o "$prefix.tar.gz" "$GITHUB_REF_NAME" $paths
             git archive --format=zip --prefix="$prefix/" -o "$prefix.zip" "$GITHUB_REF_NAME" $paths
             tar -tzf "$prefix.tar.gz" | grep -q "^$prefix/install.sh$"
         - name: Create the release
           if: startsWith(github.ref, 'refs/tags/')
           env:
             GH_TOKEN: ${{ github.token }}
           run: gh release create "$GITHUB_REF_NAME" --title "$GITHUB_REF_NAME" --generate-notes --verify-tag "gin-workflow-$GITHUB_REF_NAME.tar.gz" "gin-workflow-$GITHUB_REF_NAME.zip"
     pages:
       needs: release
       runs-on: ubuntu-latest
       timeout-minutes: 15
       permissions:
         contents: read
         pages: write
         id-token: write
       concurrency:
         group: pages
         cancel-in-progress: false
       environment:
         name: github-pages
         url: ${{ steps.deployment.outputs.page_url }}
       steps:
         - uses: actions/checkout@v4
         - uses: actions/setup-python@v5
           with:
             python-version: "3.12"
         - run: python3 -m pip install -r requirements-docs.txt
         - run: mkdocs build --strict
         - uses: actions/configure-pages@v5
         - uses: actions/upload-pages-artifact@v3
           with:
             path: site
         - id: deployment
           uses: actions/deploy-pages@v4
   ```
   Lines 1 to 29 (trigger, workflow-level `permissions: contents: write`, checkout, Python, tag check, dependencies, git identity) are unchanged. Run the YAML acceptance command above: `ok`.
2. Prove the archive recipe locally against the current commit (the workflow passes the tag where this passes `HEAD`):
   ```bash
   git archive --format=tar.gz --prefix=gin-workflow-test/ -o /tmp/gin-workflow-test.tar.gz HEAD plugins scripts install.sh install.ps1 remote-install.sh README.md LICENSE docs
   tar -tzf /tmp/gin-workflow-test.tar.gz | grep -c '^gin-workflow-test/\(tests\|\.github\|\.planning\)/'
   tar -tzf /tmp/gin-workflow-test.tar.gz | grep -E '^gin-workflow-test/(install\.sh|plugins/gin-workflow/plugin\.meta\.json)$'
   ```
   Expected: `0`, then the two listed paths. Remove `/tmp/gin-workflow-test.tar.gz`.
3. `docs/contributing.md`: insert before `## Releasing` (line 102) the section:
   ````markdown
   ## Documentation site

   `mkdocs.yml` builds `docs/` into the site at `https://giangdhwhtbr.github.io/gin-workflow/`. Preview it locally:

   ```bash
   python3 -m pip install -r requirements-docs.txt
   mkdocs serve
   ```

   `mkdocs build --strict` runs in CI (`test.yml`) and fails on a broken link or a page missing from `nav`, so add every new page under `docs/` to `nav` in `mkdocs.yml` and to the documentation table in `README.md`. A Vietnamese translation sits next to its source as `<page>.vi.md`; a page without one shows the English text under the `vi` language.

   Publishing needs GitHub Pages enabled once, in the repository settings under Pages, with source "GitHub Actions". The `pages` job of `release.yml` fails until that is done.

   ````
   Replace step 4 of Releasing (line 107) with:
   ```markdown
   4. Tag the merge commit `vX.Y.Z` (the `gin-workflow` version) and push the tag: `git tag vX.Y.Z && git push origin vX.Y.Z`. `.github/workflows/release.yml` fails unless the tag equals the version in `plugins/gin-workflow/plugin.meta.json`, runs the full test suite, creates the GitHub release with generated notes and the installable source tree attached as `gin-workflow-vX.Y.Z.tar.gz` and `.zip`, then deploys the documentation site. Running the workflow by hand (`workflow_dispatch`) runs the tests and redeploys the site without creating a release. `gin-qa` and `gin-orchestrator` ship in the same release under their own versions.
   ```
4. Run `python3 -m unittest tests/workflow_core/test_docs_coverage.py -v` (11 tests, `OK`) and `uv run --with-requirements requirements-docs.txt -- mkdocs build --strict` (exit 0). Commit: `ci: attach the source archive to releases and deploy the docs site to Pages`.

## Integration
- **Branch**: `feat/docs-site-foundation`
- **Merge strategy**: sequential

## Validation
- [ ] `python3 -m unittest tests/test_all.py` passes (full suite, as the pre-push hook runs it)
- [ ] `uv run --with-requirements requirements-docs.txt -- mkdocs build --strict` exits 0 with no warning
- [ ] Manual: `uv run --with-requirements requirements-docs.txt -- mkdocs serve`, open `http://127.0.0.1:8000/gin-workflow/`, switch to Tiếng Việt on the home page (Vietnamese text) and on Getting started (English text, switcher still shown), open Architecture and see rendered diagrams
- [ ] Before the first tag after merge, the maintainer enables GitHub Pages in the repository settings with source "GitHub Actions"
- [ ] After merge: one `workflow_dispatch` run of `release` deploys the site without creating a release; the first tag push lists `gin-workflow-vX.Y.Z.tar.gz` and `.zip` on the release and the `pages` job is green. Both are recorded in the ship handoff as the end-to-end proof of R7.

## Notes
- `Model:` and `Effort:` are chosen from the main harness catalog (`haiku`, `sonnet`, `opus`; `low` to `max`) using the route rubric.
- The user may override `Model:` and `Effort:` before plan approval.
- Parent Bead: the epic for this plan stays open until the user confirms the merge. Track beads close when their tests and review pass.
- `uv` is installed on this machine at `/home/gin/.local/bin/uv`; CI uses `pip` because its Python is not externally managed.
