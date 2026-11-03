# Documentation site: MkDocs Material, suffix i18n, strict build

**Context**
Epic `gin-workflow-el1v` (2026-11-03) built `https://giangdhwhtbr.github.io/gin-workflow/` from `docs/` with MkDocs Material and `mkdocs-static-i18n`, attached the source archive to releases, and deployed the site from `release.yml`. The plan counted four links that leave `docs/`; a grep found six (`docs/reference/troubleshooting.md`, `docs/starters/greenfield.md` were missing), recorded in the bead notes of `gin-workflow-el1v.1`.

**Decision/Solution**
- The site contains only `docs/`. A relative link to a file outside it is a strict-build failure; write it as `https://github.com/giangdhwhtbr/gin-workflow/blob/master/<path>`. Check with `grep -rn "\](\.\./\.\./" docs` before adding a page.
- Every page under `docs/` is listed twice: in `nav` of `mkdocs.yml` and in the documentation table of `README.md` (`test_docs_coverage.py`). Only the README rule exempts `*.vi.md`; links, Mermaid types, and style rules apply to translations too.
- Translations use the suffix layout (`<page>.vi.md` next to `<page>.md`, `fallback_to_default: true`); nothing moves into language folders.
- Pins live in `requirements-docs.txt` (`mkdocs-material==9.8.0`, `mkdocs-static-i18n==1.3.1`); build locally with `uv run --with-requirements requirements-docs.txt -- mkdocs build --strict` because the system Python is externally managed. The Material end-of-life banner (`NO_MKDOCS_2_WARNING`) is not a build warning.
- `release.yml`: the `release` job keeps workflow-level `contents: write`; the `pages` job carries its own `contents: read`, `pages: write`, `id-token: write`. `workflow_dispatch` runs the tests and redeploys the site; the tag-gated steps are skipped.

**Consequences**
- GitHub Pages must be enabled once in the repository settings with source "GitHub Actions"; the `pages` job fails until then.
- A broken link or an unlisted page now fails the pull-request CI (`test.yml` runs `mkdocs build --strict` after the unit tests).

**References**
- `mkdocs.yml`, `requirements-docs.txt`, `.github/workflows/test.yml`, `.github/workflows/release.yml`, `tests/workflow_core/test_docs_coverage.py`
- `.planning/specs/2026-11-03-docs-site-foundation-design.md`, `.planning/plans/2026-11-03-docs-site-foundation.md`

**Scope**
Every page under `docs/` and every release of gin-workflow.
