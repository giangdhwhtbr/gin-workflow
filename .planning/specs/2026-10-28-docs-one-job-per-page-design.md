# Docs reorganization: one job per page after role handbooks

Epic: gin-workflow-tvf5
Status: confirmed by the user on 2026-10-28.

## Goal and scope

Branch `chore-role-handbooks` added role handbooks, a template guide, and a brownfield modernization starter. Bring the docs back to the docs-rewrite rules (`.planning/specs/2026-10-04-docs-rewrite-design.md`): one job per page, one copy of each topic, every statement checked against code.

In scope: `docs/starters/team-roles.md`, `docs/guides/{pm,ba,dev,qa}-guide.md`, `docs/guides/{qa,sdd,customizing-templates}.md`, `docs/starters/brownfield-{modernize,walkthrough}.md`, the README docs map, and `tests/workflow_core/test_docs_coverage.py`.

Out of scope: the Windows page (`docs/guides/windows.md`) and the Windows section of `docs/contributing.md`. The user handles them on `fix/windows-support` (gin-workflow-eq77). `docs/guides/recommended-tools.md` keeps its path: `setup_service.py` and the `setup` skill link to its GitHub URL.

## Requirements

1. **One roles page.** `docs/starters/team-roles.md` becomes `docs/roles.md`. It keeps the collaboration matrix and the conflict safeguards. For each role (PM, BA, Dev and tech lead, QA) it gives a short reading path: which pages to read and in what order, as links only, with no mechanics repeated. The per-role step lists are removed.
2. **Handbooks merged into feature pages, then deleted.**
   - `qa-guide.md`: the prompt examples, the `qa/guidelines.md` rule examples, and the ship approval checklist move into `docs/guides/qa.md`. Its cases, plan, pin, and e2e mechanics, which repeat `qa.md`, and its promotional intro are dropped.
   - `ba-guide.md`: the `assets/` convention for screenshots and mockups moves into `docs/guides/sdd.md`. The claim that `specs lint`, `trace`, and `archive` read only `spec.md` and `spec-delta.md` is kept only if the code confirms it.
   - `pm-guide.md`: no new page. `roles.md` links to the walkthrough's roadmap and sprint sections, `usage-report.md`, and the skills reference. Statements the code does not back are dropped: the code labels sprints with `gin-workflow task update <epic> --add-label sprint:<name>`, not `task label`, and the guide names specific model versions.
   - `dev-guide.md`: `roles.md` links to getting-started, lifecycle, and team. Any content not covered elsewhere and confirmed by the code moves to the page that owns that topic.
   - All four files are deleted.
3. **Brownfield split by job.** `brownfield-walkthrough.md` keeps the end-to-end flow (setup, survey, roadmap, sprint, discuss … ship). `brownfield-modernize.md` keeps only strategy: strangler fig, parity and characterization tests, and the migration cycle. It links to the walkthrough for setup and stages. If the walkthrough's "Customizing outputs" repeats `customizing-templates.md`, it is replaced by a link.
4. **Style pass** on every page this epic adds content to or edits (including `customizing-templates.md`): no numbered headings, sentence case headings, no promotional wording, slash commands written as `/gin-workflow:<skill>` or `/gin-qa:<skill>`, and every CLI command named on the page exists in `docs/reference/cli.md`, no em or en dashes, no list items that open with a bold label, and no emoji. A fresh-context prose review (`technical-writer:prose-reviewer`) checks each restyled page; its findings under these rules are fixed, and its other findings are reported without changing the page. Added by the user on 2026-10-29.
5. **README docs map lists every page under `docs/`.** The "Role Handbooks" row is replaced by a link to `docs/roles.md`. `docs/reference/orchestrator-contract.md` is added to the Reference row, and `docs/presentations/brownfield-modernization-script.md` is added next to the modernization deck as "(script)".
6. **Orphan test.** Add `test_every_docs_page_is_in_the_readme_map` to `tests/workflow_core/test_docs_coverage.py`. It fails when any `docs/**/*.md` is not linked directly from `README.md`.

## User Stories

### US-1: Find the page for my role
As a PM, BA, developer, or tester, I want one page that tells me what my role owns and what to read, so that I do not read the same steps on two pages.

Acceptance criteria:
- `docs/roles.md` exists and links to a reading path for each of the four roles.
- `docs/guides/{pm,ba,dev,qa}-guide.md` and `docs/starters/team-roles.md` do not exist.
- No page repeats the per-role step lists.

### US-2: One QA page
As a tester, I want a single page for the QA add-on, so that I do not confuse `qa.md` with `qa-guide.md`.

Acceptance criteria:
- `docs/guides/qa.md` holds the prompt examples, the guideline rule examples, and the ship approval checklist.
- No other page documents the case format, `gin-qa cases plan`, or `gin-qa e2e`; other pages link to `qa.md`.

### US-3: Brownfield pages with one job each
As a team modernizing a legacy system, I want the walkthrough to show the flow and the modernize page to show the strategy, so that I know which page to read.

Acceptance criteria:
- `brownfield-modernize.md` has no setup, survey, or lifecycle stage steps; it links to the walkthrough for those.
- The walkthrough has no strangler fig or parity test strategy beyond a link to `brownfield-modernize.md`.

### US-4: No orphan docs
As a maintainer, I want the tests to fail when a docs page is missing from the README docs map, so that every page can be found.

Acceptance criteria:
- The new test fails when a page under `docs/` is not linked from `README.md`, and passes on the reorganized tree.
- `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.test_all` passes.

## Errors and compatibility

- Deleted and renamed pages break outside links to them. They were added on this unmerged branch, so no released link breaks.
- When `fix/windows-support` merges, `docs/guides/windows.md` must appear in the README docs map, or the new test fails. Whichever branch merges second resolves this.
- Relative links to removed files are caught by the existing `test_relative_links_resolve`.

## Testing

- The new orphan test in `tests/workflow_core/test_docs_coverage.py`, plus the existing link, skill, CLI, and Mermaid checks there.
- Full suite: `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.test_all`.
- Manual check before review: `grep -rn "/discuss\b\|/tech-doc\b\|/roadmap\b" docs` returns no bare slash commands on the edited pages.
