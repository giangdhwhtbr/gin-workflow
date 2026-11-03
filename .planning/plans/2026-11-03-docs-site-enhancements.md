# Plan: Documentation site enhancements, team guides, and Vietnamese translation

Spec: `.planning/specs/2026-11-03-docs-site-enhancements-design.md` (Workflow: `docs-site-enhancements`, Depends on: `gin-workflow-qa-case-folders`, `gin-workflow-qa-playwright-scaffold`, `gin-workflow-qa-test-types`, `gin-workflow-qa-manual-bugs`, `gin-workflow-qa-report`, `gin-workflow-qa-setup`).

## Objective

Reorganize and enhance `https://giangdhwhtbr.github.io/gin-workflow/` after the `QA process` milestone (`gin-workflow-o2nc`) ships: hide internal architecture and contributor pages from the top navigation (`mkdocs.yml`), consolidate the two brownfield starter files into `docs/starters/brownfield.md`, separate Tech Lead initial setup from team member onboarding in `docs/roles.md`, add copy-pasteable prompt templates in `docs/reference/skills.md`, add two new practical guides (`docs/guides/ai-strategy.md` including manual CLI fallback when AI quota runs out, and `docs/guides/claude-workflow.md`), upgrade user-facing pages with Mermaid diagrams, and translate all 17 user-facing pages into Vietnamese (`*.vi.md`).

## Architecture

- MkDocs Material (`mkdocs.yml`) builds `docs/` into `site/` with `mkdocs-static-i18n` (`docs_structure: suffix`, `en` default, `vi` falling back to `en`) and `attr_list` so translated `.vi.md` headings can declare `{ #english-anchor }` attributes matching English section anchors.
- Internal reference pages (`docs/concepts/*`, `docs/orchestrator/*`, `docs/contributing.md`, `docs/reference/orchestrator-contract.md`) remain on disk in `docs/` so repository rules in `AGENTS.md` and `tests/workflow_core/test_docs_coverage.py` stay green, while `not_in_nav` in `mkdocs.yml` hides them from the site navigation tabs and sidebar.
- `tests/workflow_core/test_docs_coverage.py` checks skill/CLI coverage, relative links, README documentation map membership (exempting `*.vi.md`), Mermaid diagram types, forbidden phrases (`BEADS_DEFAULT`), and mechanical style rules (`workflow_core/docs_check.py`) across every English and `.vi.md` page.
- `tests/workflow_core/test_walkthrough_docs.py` verifies that every `gin-workflow <command> [<sub>]` token in `docs/starters/brownfield.md` and `docs/guides/ai-strategy.md` is documented in `docs/reference/cli.md` and that `docs/starters/brownfield.md` contains the required milestone headings.

## Tech Stack

Python 3.12, `mkdocs-material==9.8.0`, `mkdocs-static-i18n==1.3.1` (pinned in `requirements-docs.txt`), `unittest`, `workflow_core.docs_check`.

## Global Constraints

Copied verbatim from the spec:

- Execution dependency on milestone `gin-workflow-o2nc` (`gin-workflow-qa-case-folders`, `gin-workflow-qa-playwright-scaffold`, `gin-workflow-qa-test-types`, `gin-workflow-qa-manual-bugs`, `gin-workflow-qa-report`, `gin-workflow-qa-setup`): during `/gin-workflow:orchestrate` (or roadmap sync), the `docs-site-enhancements` epic bead adds `gin-workflow task dep add` dependencies on all six QA epics so its tracks do not become `ready` until the QA process milestone is closed.
- Out of scope: implementing the `gin-qa` runtime features of `gin-workflow-o2nc` (those belong to the six `gin-workflow-qa-*` epics that this epic depends on); modifying `gin-workflow` Python runtime behavior or skill instructions for native `qa` provider-role routing (covered by the follow-up epic); translating `docs/concepts/*`, `docs/orchestrator/*`, `docs/contributing.md`, or low-level reference pages (`cli.md`, `config.md`, `troubleshooting.md`, `orchestrator-contract.md`) into Vietnamese; deleting the Markdown files of hidden sections from the repository.
- Plan steps are instructions for the executor, never page prose to copy verbatim into Markdown files; every claim in a documentation page must match the repository's code and CLI (`docs/reference/cli.md`).
- Deliverable merge-holds ("remain open until human-confirmed merge") apply only to the Parent Bead; individual track beads close as soon as their tests and review pass so downstream tracks unblock.
- Every English and `.vi.md` page obeys the mechanical style rules enforced by `workflow_core/docs_check.py` and `tests/workflow_core/test_docs_coverage.py`: no en-dash or em-dash outside code blocks, no list item opening with bold text, no numbered headings, no emoji (including checkmarks), no forbidden `beads` default/required phrasing without `optional`, typed Mermaid fences starting at column 0 without `%%{init}%%`, and valid relative links and anchors under `mkdocs build --strict`.

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

- Problem statement: the documentation site exposes internal contributor/architecture tabs, splits brownfield onboarding across two files, routes non-lead roles (`BA`, `PM`, `Developer`, `Tester`) to initial project setup (`/gin-workflow:setup`), lacks copy-pasteable team prompt templates and practical AI / Claude Code guides (including a manual CLI workflow when AI quota runs out), uses ASCII box art instead of Mermaid diagrams in several guides, and has only `docs/index.vi.md` translated into Vietnamese.
- Success criteria: spec US-1 through US-6 and R0 through R8. Locally: `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.workflow_core.test_docs_coverage tests.workflow_core.test_walkthrough_docs -v` passes, `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m workflow_core.cli docs check` exits 0 on all modified/created pages, and `uv run --with-requirements requirements-docs.txt -- mkdocs build --strict` exits 0 with zero warnings across `en` and `vi`.
- Constraints: Global Constraints above.
- Non-goals: runtime code changes in `gin-workflow` or `gin-qa`, translating `concepts/`, `orchestrator/`, `contributing.md`, or low-level reference files.

## Approach Options

### Option 1: Four sequential tracks on `feat/docs-site-enhancements`
- Summary:
  - Track 1 (`R0`, `R1`, `R2`, `R3`): Consolidate `brownfield-modernize.md` and `brownfield-walkthrough.md` into `docs/starters/brownfield.md`, restructure `docs/roles.md`, `docs/getting-started.md`, `docs/index.md`, `docs/starters/greenfield.md`, and `docs/guides/team.md` with Mermaid diagrams, update `mkdocs.yml` (`not_in_nav`, `attr_list`, hiding internal tabs), `README.md`, `.planning/knowledge/docs-site-mkdocs.md`, and `tests/workflow_core/test_walkthrough_docs.py`.
  - Track 2 (`R4`, `R5`, `R6`, `R7`): Create `docs/guides/ai-strategy.md` and `docs/guides/claude-workflow.md`, add `## Prompt templates` to `docs/reference/skills.md`, upgrade `docs/guides/sdd.md`, `docs/guides/qa.md`, `docs/guides/customizing-templates.md`, `docs/guides/recommended-tools.md`, and `docs/guides/windows.md` with Mermaid diagrams and simplified prose, and register the two new guides in `mkdocs.yml`, `README.md`, and `tests/workflow_core/test_walkthrough_docs.py`.
  - Track 3 (`R8` part 1): Write and verify the Vietnamese translations (`*.vi.md`) for the 6 entry, role, starter, and skills reference pages (`index.vi.md`, `getting-started.vi.md`, `roles.vi.md`, `starters/greenfield.vi.md`, `starters/brownfield.vi.md`, `reference/skills.vi.md`).
  - Track 4 (`R8` part 2): Write and verify the Vietnamese translations (`*.vi.md`) for all 11 guide pages under `docs/guides/`.
- Pros: Each track leaves `test_docs_coverage.py`, `test_walkthrough_docs.py`, and `mkdocs build --strict` green; English structural and content changes finish in Tracks 1 and 2 before any `.vi.md` translation is written in Tracks 3 and 4; translation work is split into two bounded, reviewable batches (6 pages + 11 pages).
- Cons: Sequential execution across the four tracks.

### Option 2: Parallel English and Vietnamese tracks
- Summary: Translate pages in parallel with the English restructuring.
- Pros: Faster wall-clock time if multiple workers run simultaneously.
- Cons: Translating pages while their English headings, links, and Mermaid diagrams are changing causes anchor drift and duplicate work.

### Recommended Approach
- Selected option: Option 1.
- Rationale: Completing and verifying all English structural edits, new guides, prompt templates, and anchor IDs in Tracks 1 and 2 guarantees that Tracks 3 and 4 translate stable, tested pages once.

## Scope

- In scope: R0, R1, R2, R3 in Track 1; R4, R5, R6, R7 (and the new-guide registrations of R1/R2) in Track 2; R8 (entry, roles, starters, skills reference `.vi.md`) in Track 3; R8 (all 11 `guides/*.vi.md`) in Track 4.
- Out of scope: Global Constraints above.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Track 2 builds on Track 1's mkdocs.yml, README.md, brownfield.md anchors, and test_walkthrough_docs.py; Tracks 3 and 4 translate the English pages finalized in Tracks 1 and 2 and validate cross-page anchors with mkdocs build --strict.
```

## Tasks

### Track 1: Consolidate brownfield starter, separate team roles onboarding, and clean up site navigation
- **Dependencies**: none
- **Files**:
  - Delete `docs/starters/brownfield-modernize.md`
  - Delete `docs/starters/brownfield-walkthrough.md`
  - Create `docs/starters/brownfield.md`
  - Modify `docs/roles.md:1-50` (add Mermaid role handoff diagram, split Tech lead and Developer as rows in `## Who owns what` and as `### Tech lead` and `### Developer` subsections in `## What each role reads`, remove `concepts/lifecycle.md` link, and point PM/BA/Developer/Tester to `guides/team.md#join-it-member` and `starters/brownfield.md`)
  - Modify `docs/getting-started.md:1-93` (add Mermaid gate diagram, remove hidden `orchestrator/README.md` links at lines 38 and 93, add team-mode callout under One-time setup, and update Starters and guides links to `starters/brownfield.md`)
  - Modify `docs/index.md:1-13` (point Starters bullet to `starters/greenfield.md` and `starters/brownfield.md`)
  - Modify `docs/starters/greenfield.md:100-162` (replace ASCII diagram at lines 113-147 with a Mermaid `flowchart TD` diagram and drop `orchestrator/README.md` from Next steps)
  - Modify `docs/guides/team.md:1-60` (add Mermaid diagram of Lead setup vs Member join & PR gates, add `../getting-started.md#prerequisites` link at the top of `## Join it (member)`, and update `brownfield-walkthrough.md` links at lines 48-49 to `../starters/brownfield.md#execute` and `../starters/brownfield.md#ship`)
  - Modify `mkdocs.yml:1-115` (add `attr_list`, configure `not_in_nav` for internal pages, remove `Concepts`, `Orchestrator`, `Contributing`, and `reference/orchestrator-contract.md` from `nav`, replace the two brownfield nav entries with `Brownfield: starters/brownfield.md`, update `nav_translations`)
  - Modify `README.md:11-19` (replace the two brownfield starter links on line 12 with `[brownfield](docs/starters/brownfield.md)`)
  - Modify `.planning/knowledge/docs-site-mkdocs.md:1-22` (record `not_in_nav` for internal pages and `attr_list` for bilingual anchors)
  - Modify `tests/workflow_core/test_walkthrough_docs.py:1-49` (point `WALKTHROUGH` to `ROOT / "docs/starters/brownfield.md"`)
  - Modify `tests/workflow_core/test_docs_coverage.py:1-155` (assert every user-facing page is in `mkdocs.yml` `nav` if `validation.nav.omitted_files: ignore` fallback is used)
  - Test `tests/workflow_core/test_walkthrough_docs.py`
  - Test `tests/workflow_core/test_docs_coverage.py`
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** consolidates two large starter documents while preserving every CLI command and heading invariant checked by `test_walkthrough_docs.py` and `mkdocs build --strict`.
- **Interfaces**:
  - Consumes `workflow_core.docs_check.style_violations` and `tests/workflow_core/test_walkthrough_docs.py:undocumented`.
  - Produces `docs/starters/brownfield.md` with natural H2/H3 section anchors `#repository-and-workspace-setup`, `#discuss-an-epic`, `#capture-current-behavior-first`, `#plan-and-orchestrate`, `#strangler-fig`, `#test-cases`, `#execute`, `#e2e`, `#ship`, and `docs/roles.md` with unique H3 anchors `#tech-lead`, `#pm`, `#ba`, `#developer`, `#tester`.
- **Acceptance criteria**: `docs/starters/brownfield-modernize.md` and `docs/starters/brownfield-walkthrough.md` do not exist; `docs/starters/brownfield.md` exists; `grep -rn "brownfield-modernize\|brownfield-walkthrough\|#developer-and-tech-lead" README.md AGENTS.md docs plugins tests` prints nothing; `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.workflow_core.test_walkthrough_docs tests.workflow_core.test_docs_coverage -v` passes; `uv run --with-requirements requirements-docs.txt -- mkdocs build --strict` exits 0.
- **Estimated complexity**: medium

Steps:

1. Update `tests/workflow_core/test_walkthrough_docs.py:7` so `WALKTHROUGH = ROOT / "docs/starters/brownfield.md"` and remove the two old brownfield files:
   ```bash
   git rm docs/starters/brownfield-modernize.md docs/starters/brownfield-walkthrough.md
   ```
   Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.workflow_core.test_walkthrough_docs -v` and confirm it fails with `FileNotFoundError: .../docs/starters/brownfield.md`.
2. Create `docs/starters/brownfield.md` combining `brownfield-modernize.md` and `brownfield-walkthrough.md`:
   - Keep `## The scenario` and `## The flow at a glance` (`flowchart LR`). In `## The scenario`, list the 7-person team (`Lan` `pm` linking to `../roles.md#pm`, `An` `ba` linking to `../roles.md#ba`, `Binh` `be_lead` linking to `../roles.md#tech-lead`, `Em` and `Dung` `be_dev` linking to `../roles.md#developer`, `Hoa` `fe_dev` linking to `../roles.md#developer`, `Chi` `qe` linking to `../roles.md#tester`), explaining that `Lan` and `Binh` hold the 2 Claude Team Premium seats while `An`, `Em`, `Dung`, `Hoa`, and `Chi` hold the 5 Standard seats.
   - Use non-overlapping `team.areas` (`legacy: {paths: ["legacy/**"], lead: be_lead, roles: [be_dev]}`, `api: {paths: ["services/api/**"], lead: be_lead, roles: [be_dev]}`, `web: {paths: ["apps/web/**"], lead: be_lead, roles: [fe_dev]}`, `qa: {paths: ["qa/**"], lead: be_lead, roles: [qe]}`) and `team.approvals` (`requirement_confirmed: [ba, be_lead]`, `plan_approved: area_lead`, `ship: [qe, be_lead]`, `roadmap: [pm, be_lead]`).
   - Fold the repository strategy (`git subtree add`, `git subtree pull`, when a legacy repo stays separate, `project.packages` for Maven + npm) into `## Repository and workspace setup`.
   - In `## Setup and team setup`, include Tech Lead `/gin-workflow:team-setup`, member `/gin-workflow:team-setup`, and QA running `/gin-qa:setup` once to create `qa/guidelines.md`, `qa/README.md`, and the project QA skill.
   - Keep `## Survey the legacy system`, `## Roadmap overview`, and `## Milestone planning`.
   - Fold capturing current behavior as living specs (`REQ-AUTH-001` example) and explicit REST API contracts into `## Discuss an epic` under subsection `### Capture current behavior first` (so both `#discuss-an-epic` and `#capture-current-behavior-first` exist as distinct anchors).
   - Fold the Strangler Fig pattern, data migration strategy (dual-write or backfill and rollback criteria), and the 6 single-area tracks (Track 1 `qa` test cases, Track 2 `api` Spring Boot API & parity tests, Track 3 `web` React UI with mocks, Track 4 `web` integration, Track 5 `legacy` router cutover, Track 6 `qa` E2E & report) with a Mermaid `flowchart LR` dependency diagram into `## Plan and orchestrate` under subsection `### Strangler Fig` (so both `#plan-and-orchestrate` and `#strangler-fig` exist as distinct anchors).
   - Fold parity / characterization testing (Golden Master payloads) and per-type case files (`qa/cases/catalog/api.md`, `qa/cases/catalog/e2e.md`, `qa/cases/catalog/manual.md`) plus `/gin-qa:tests catalog --type api` into `## Test cases`.
   - Keep `## Execute`, `## E2E` (including `gin-qa e2e init` generating `playwright.config.ts`, `/gin-qa:e2e catalog`, `/gin-qa:run catalog` with `gin-qa cases result` and `gin-workflow task create -t bug --deps discovered-from:<epic>`, and `gin-qa report --format xlsx --out qa/report.xlsx`), `## Ship`, `## Milestone review and spill-over`, `## Customizing outputs`, and `## Solo variant`.
   - Wrap every prose occurrence of `` `gin-workflow` `` in backticks and never use the word `sprint`.
3. Update `docs/roles.md` to add a Mermaid `flowchart LR` role-handoff diagram at the top, split `Tech lead` and `Developer` as separate rows in the `## Who owns what` table and as `### Tech lead` and `### Developer` subsections in `## What each role reads` per R3 (keeping heading IDs `#tech-lead` and `#developer` unique), remove `[concepts/lifecycle.md](concepts/lifecycle.md)` from `## What each role reads`, update the `Tester` row to include `/gin-qa:setup`, `/gin-qa:cases`, `/gin-qa:tests`, `/gin-qa:run`, `/gin-qa:e2e`, and update all walkthrough links to `starters/brownfield.md`.
4. Update `docs/getting-started.md` (add a Mermaid `flowchart LR` gate diagram at the top, remove the hidden `orchestrator/README.md` link at line 38 and line 93, add a team-mode note under `## One-time setup` pointing non-lead teammates to `guides/team.md#join-it-member`, and update `## Starters and guides` to link to `starters/brownfield.md`), `docs/index.md` (update Starters description), `docs/starters/greenfield.md` (replace the ASCII diagram at lines 113-147 with a `flowchart TD` Mermaid block and drop the `orchestrator/README.md` bullet), and `docs/guides/team.md` (add a Mermaid `flowchart TD` diagram of Lead setup vs Member join & PR gates, link `../getting-started.md#prerequisites` at the start of `## Join it (member)`, and update `brownfield-walkthrough.md` links to `../starters/brownfield.md#execute` and `../starters/brownfield.md#ship`).
5. Update `mkdocs.yml`, `README.md:12`, and `.planning/knowledge/docs-site-mkdocs.md` per R1 and R2:
   - In `mkdocs.yml`, add `attr_list` under `markdown_extensions`, configure `not_in_nav` for `/concepts/**`, `/orchestrator/**`, `/contributing.md`, `/reference/orchestrator-contract.md` (if `mkdocs-static-i18n` warns on `vi` fallback pages, set `validation.nav.omitted_files: ignore` in `mkdocs.yml` and add a test in `tests/workflow_core/test_docs_coverage.py` asserting that every user-facing page is present in `mkdocs.yml` `nav`), remove `Concepts`, `Orchestrator`, `Contributing`, and `reference/orchestrator-contract.md` from `nav`, and replace the two brownfield lines under `Starters` with `- Brownfield: starters/brownfield.md`.
6. Run the tests and strict build:
   ```bash
   PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.workflow_core.test_walkthrough_docs tests.workflow_core.test_docs_coverage -v
   uv run --with-requirements requirements-docs.txt -- mkdocs build --strict
   ```
   Confirm all tests pass and `mkdocs build --strict` exits 0. Commit on `feat/docs-site-enhancements`: `docs(starters,roles): consolidate brownfield starter, split team roles, hide internal nav tabs`.

### Track 2: Add AI strategy and Claude Code guides, reference prompt templates, and Mermaid upgrades
- **Dependencies**: Track 1
- **Files**:
  - Create `docs/guides/ai-strategy.md`
  - Create `docs/guides/claude-workflow.md`
  - Modify `docs/roles.md:1-60` (link Tech Lead reading list to `guides/ai-strategy.md` and Developer reading list to `guides/claude-workflow.md`)
  - Modify `docs/reference/skills.md:1-75` (include `gin-qa` skills `setup`, `tests`, `run`, and append `## Prompt templates` with copy-pasteable prompts and the Mermaid track-dependency diagram)
  - Modify `docs/guides/sdd.md:1-72` (add Mermaid `flowchart LR` diagram showing Living Specs, Change Delta `01-proposal` to `04-plan`, QA cases pinned to `REQ@hash8`, and `specs archive` on `ship`)
  - Modify `docs/guides/qa.md:1-95` (add Mermaid `flowchart LR` diagram of the QA traceability and reporting pipeline and reflect per-type case folders, `/gin-qa:setup`, `/gin-qa:tests`, `/gin-qa:run`, `gin-qa cases result`, and `gin-qa report --format xlsx`)
  - Modify `docs/guides/customizing-templates.md:1-164` (replace ASCII lookup diagram at lines 9-14 with a Mermaid `flowchart LR` diagram and remove the internal `(`template_text` in `workflow_core/specs.py`)` reference at line 16)
  - Modify `docs/guides/recommended-tools.md:1-48` (replace the internal `stage-contract.md` link and hidden `../orchestrator/README.md` link with user-facing descriptions)
  - Modify `docs/guides/windows.md:1-140` (remove internal module references `rules_checks.py` at line 15 and `workflow_core/atomic.py` at line 128)
  - Modify `mkdocs.yml:50-100` (add `Using AI effectively: guides/ai-strategy.md` and `Working with Claude Code: guides/claude-workflow.md` under `Guides` in logical order, plus `nav_translations` entries in `vi`)
  - Modify `README.md:16` (add `[using AI effectively](docs/guides/ai-strategy.md)` and `[working with Claude Code](docs/guides/claude-workflow.md)` to the `Guides` row)
  - Modify `tests/workflow_core/test_walkthrough_docs.py:1-49` (add `"dep"` to `BD_PASSTHROUGH`, add `AI_STRATEGY = ROOT / "docs/guides/ai-strategy.md"`, and add `test_ai_strategy_cites_only_documented_commands`)
  - Test `tests/workflow_core/test_walkthrough_docs.py`
  - Test `tests/workflow_core/test_docs_coverage.py`
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** writes two new technical guides and the reference prompt templates while enforcing CLI command accuracy in `test_walkthrough_docs.py` and style/link rules in `test_docs_coverage.py`.
- **Interfaces**:
  - Consumes `tests/workflow_core/test_walkthrough_docs.py:undocumented` and `workflow_core.docs_check.style_violations`.
  - Produces `docs/guides/ai-strategy.md` (with `#model-and-effort-by-stage`, `#allocating-team-accounts`, `#working-manually-when-ai-quota-runs-out`), `docs/guides/claude-workflow.md` (with `#personal-customization-without-affecting-the-team`, `#context-hygiene-and-session-habits`), and `docs/reference/skills.md#prompt-templates`.
- **Acceptance criteria**: `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.workflow_core.test_walkthrough_docs tests.workflow_core.test_docs_coverage -v` passes; `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m workflow_core.cli docs check docs/roles.md docs/guides/ai-strategy.md docs/guides/claude-workflow.md docs/reference/skills.md docs/guides/sdd.md docs/guides/qa.md docs/guides/customizing-templates.md docs/guides/recommended-tools.md docs/guides/windows.md` prints `ok`; `uv run --with-requirements requirements-docs.txt -- mkdocs build --strict` exits 0.
- **Estimated complexity**: medium

Steps:

1. In `tests/workflow_core/test_walkthrough_docs.py`, update `BD_PASSTHROUGH = {"graph", "dep"}` (so `gin-workflow task dep add` is recognized alongside `cli.md`'s `` `dep add|remove|list` `` entry), add `AI_STRATEGY = ROOT / "docs/guides/ai-strategy.md"`, and add a test method:
   ```python
   def test_ai_strategy_cites_only_documented_commands(self):
       cli = (ROOT / "docs/reference/cli.md").read_text(encoding="utf-8")
       text = AI_STRATEGY.read_text(encoding="utf-8")
       self.assertEqual([], undocumented(cli, text))
   ```
   Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.workflow_core.test_walkthrough_docs -v` and confirm it fails because `docs/guides/ai-strategy.md` does not exist yet.
2. Create `docs/guides/ai-strategy.md` per R5:
   - `## Model and effort by stage`: table covering `/gin-workflow:setup`, `/gin-workflow:team-setup`, `/gin-workflow:tech-doc`, `/gin-workflow:roadmap`, `/gin-workflow:roadmap --milestone`, `/gin-workflow:discuss`, `/gin-workflow:plan`, `/gin-workflow:orchestrate`, `/gin-workflow:execute` (low/medium/high tracks), `/gin-workflow:review`, `/gin-workflow:ship`, `/gin-qa:setup`, `/gin-qa:cases`, `/gin-qa:tests`, `/gin-qa:run`, and `/gin-qa:e2e`, with recommended model (`haiku`, `sonnet`, `opus`), effort (`low`, `medium`, `high`), and `Why`.
   - `## Allocating team accounts`: Mermaid `flowchart TD` diagram and guide showing how a 7-person team with 2 Premium seats and 5 Standard seats assigns track `Owner:` in `/gin-workflow:plan` so Premium seat holders (`lan`, `binh`) run `/roadmap`, complex `/discuss`, `/plan`, `opus`/`high` tracks, and reviews, while Standard seat holders (`an`, `em`, `dung`, `hoa`, `chi`) execute bounded parallel tracks at `sonnet`/`medium` and `haiku`/`low`, backed by `usage.budget_usd`.
   - `## Working manually when AI quota runs out`: Mermaid `flowchart LR` diagram and step-by-step CLI commands covering single-member handover (`gin-workflow team reassign <bead> <email>` plus `git fetch origin && git worktree add .planning/worktrees/<bead> feat/<topic>-t<N>` and `gin-workflow team claim <bead>`), manual orchestration if quota ran out before `/gin-workflow:orchestrate` (`gin-workflow task create`, `gin-workflow task dep add`, `gin-workflow record orchestration-ready`), claiming tasks (`gin-workflow team deps`, `gin-workflow team ready`, `gin-workflow team claim <bead>` in team mode; `gin-workflow task ready`, `gin-workflow task update <bead> --claim` in solo mode), worktree creation (`gin-workflow worktree create <bead> feat/<topic>-t<N>`), checking rules (`gin-workflow rules --files ...`), manual QA CLI (`gin-qa cases`, `gin-qa tests`, `gin-qa e2e`, `gin-qa report`), closing tracks (`gin-workflow task close <bead> --reason ...` and `--waive-review "<reason>" --actor <email>` under `strict` rigor), pushing and filling `Plan:` and `Tracks:` in the PR, and checking `ship` (`gin-workflow team check <pr-url> --gate ship`, `gin-workflow task close <epic>`, `gin-workflow worktree cleanup <bead>`). Wrap every prose mention of `` `gin-workflow` `` in backticks.
3. Create `docs/guides/claude-workflow.md` per R6:
   - `## Personal customization without affecting the team`: Mermaid `flowchart LR` diagram contrasting shared git-tracked files (`.agent-workflow/config.yaml`, `AGENTS.md`, `CLAUDE.md`, `.planning/knowledge/`) with personal local files (`~/.claude/CLAUDE.md` which applies inside every `.planning/worktrees/<id>` worktree without git diffs, `.git/info/exclude`, `/model`, `gin-workflow setup harness-override --harness <name>`, `.agent-workflow/executables.local.yaml`, and `.agent-workflow/orchestrator.local.yaml` `providers.<name>.executable`). Include a copy-pasteable `~/.claude/CLAUDE.md` example (such as responding in Vietnamese while keeping code, paths, and commands verbatim).
   - `## Context hygiene and session habits`: picking `/model` per stage, running `/clear` or `/compact` between stages, using `codegraph explore` first, and using `/goal` (`gin-workflow goal --workflow-id <id>`) for unattended tracks without a `Human gate:`.
4. Update `docs/reference/skills.md` to list the `gin-qa` skills (`setup`, `cases`, `tests`, `run`, `e2e`) and add `## Prompt templates` per R4, including the Mermaid `flowchart LR` dependency diagram (`BA discuss -> parallel QA cases + BE API + FE with mocks -> FE integration & Legacy router -> QA E2E & report`) and copy-pasteable prompts for `setup`, `team-setup` (lead and member), `tech-doc`, `roadmap`, `roadmap --milestone`, `discuss`, `plan`, `orchestrate`, `execute`, `cases`, `tests`, `run`, `e2e`, `ship`, and `report`. Also update `docs/roles.md` to link Tech Lead to `guides/ai-strategy.md` and Developer to `guides/claude-workflow.md`.
5. Upgrade `docs/guides/sdd.md`, `docs/guides/qa.md`, `docs/guides/customizing-templates.md`, `docs/guides/recommended-tools.md`, and `docs/guides/windows.md` per R7, and register `ai-strategy.md` and `claude-workflow.md` in `mkdocs.yml` (`nav` and `nav_translations`) and `README.md:16`.
6. Run the tests, docs check, and strict MkDocs build:
   ```bash
   PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.workflow_core.test_walkthrough_docs tests.workflow_core.test_docs_coverage -v
   PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m workflow_core.cli docs check docs/roles.md docs/guides/ai-strategy.md docs/guides/claude-workflow.md docs/reference/skills.md docs/guides/sdd.md docs/guides/qa.md docs/guides/customizing-templates.md docs/guides/recommended-tools.md docs/guides/windows.md
   uv run --with-requirements requirements-docs.txt -- mkdocs build --strict
   ```
   Commit on `feat/docs-site-enhancements`: `docs(guides,reference): add AI strategy and Claude workflow guides, prompt templates, and Mermaid diagrams`.

### Track 3: Vietnamese translations for entry pages, roles, starters, and skills reference
- **Dependencies**: Track 2
- **Files**:
  - Modify `docs/index.vi.md:1-13`
  - Create `docs/getting-started.vi.md`
  - Create `docs/roles.vi.md`
  - Create `docs/starters/greenfield.vi.md`
  - Create `docs/starters/brownfield.vi.md`
  - Create `docs/reference/skills.vi.md`
  - Test `tests/workflow_core/test_docs_coverage.py`
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `low`
- **Why:** raises model above `haiku` because natural, idiomatic Vietnamese technical translation across 6 long pages (including `brownfield.md` and `skills.md` prompt templates) requires bilingual domain judgement while keeping `Effort: low` because page structure, code blocks, and anchors are already fixed in Tracks 1 and 2.
- **Interfaces**:
  - Consumes English source files `docs/index.md`, `docs/getting-started.md`, `docs/roles.md`, `docs/starters/greenfield.md`, `docs/starters/brownfield.md`, `docs/reference/skills.md`.
  - Produces their `.vi.md` counterparts with matching `{ #english-anchor }` attributes on every heading targeted by an intra-page or cross-page `#anchor` link.
- **Acceptance criteria**: All 6 `.vi.md` files exist; `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m workflow_core.cli docs check docs/index.vi.md docs/getting-started.vi.md docs/roles.vi.md docs/starters/greenfield.vi.md docs/starters/brownfield.vi.md docs/reference/skills.vi.md` prints `ok`; `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.workflow_core.test_docs_coverage -v` passes; `uv run --with-requirements requirements-docs.txt -- mkdocs build --strict` exits 0 and builds `site/vi/getting-started/index.html`, `site/vi/roles/index.html`, `site/vi/starters/greenfield/index.html`, `site/vi/starters/brownfield/index.html`, and `site/vi/reference/skills/index.html`.
- **Estimated complexity**: medium

Steps:

1. Verify the current baseline before creating the 5 new `.vi.md` files (`ls docs/getting-started.vi.md docs/roles.vi.md docs/starters/greenfield.vi.md docs/starters/brownfield.vi.md docs/reference/skills.vi.md` exits non-zero) and extract all `#anchor` targets referenced across `docs/`:
   ```bash
   grep -rnEo '\]\([^)]*#[a-z0-9_-]+\)' docs/
   ```
2. Update `docs/index.vi.md` and create `docs/getting-started.vi.md`, `docs/roles.vi.md`, `docs/starters/greenfield.vi.md`, `docs/starters/brownfield.vi.md`, and `docs/reference/skills.vi.md`:
   - Keep all code blocks, CLI commands, slash commands, configuration keys, file paths, and `REQ-ID`s verbatim; translate the prose and prompt explanations into natural Vietnamese.
   - Add `{ #english-anchor }` attributes to every heading targeted by any `#anchor` link found in Step 1 (including `#prerequisites`, `#one-time-setup`, `#tech-lead`, `#pm`, `#ba`, `#developer`, `#tester`, `#repository-and-workspace-setup`, `#capture-current-behavior-first`, `#strangler-fig`, `#milestone-planning`, `#discuss-an-epic`, `#plan-and-orchestrate`, `#test-cases`, `#execute`, `#e2e`, `#ship`, `#prompt-templates`), never assigning the same `#id` twice in one file.
   - Do not use en-dash/em-dash (`–`, `—`), bold-label list items (`- **...**`), numbered headings (`## 1.`), or emoji outside code blocks.
3. Run `docs check`, `test_docs_coverage.py`, and `mkdocs build --strict`:
   ```bash
   PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m workflow_core.cli docs check docs/index.vi.md docs/getting-started.vi.md docs/roles.vi.md docs/starters/greenfield.vi.md docs/starters/brownfield.vi.md docs/reference/skills.vi.md
   PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.workflow_core.test_docs_coverage -v
   uv run --with-requirements requirements-docs.txt -- mkdocs build --strict
   ```
   Confirm all commands exit 0. Commit on `feat/docs-site-enhancements`: `docs(vi): translate entry pages, roles, starters, and skills reference to Vietnamese`.

### Track 4: Vietnamese translations for all 11 guide pages
- **Dependencies**: Track 3
- **Files**:
  - Create `docs/guides/use-cases.vi.md`
  - Create `docs/guides/team.vi.md`
  - Create `docs/guides/ai-strategy.vi.md`
  - Create `docs/guides/claude-workflow.vi.md`
  - Create `docs/guides/sdd.vi.md`
  - Create `docs/guides/qa.vi.md`
  - Create `docs/guides/customizing-templates.vi.md`
  - Create `docs/guides/rules.vi.md`
  - Create `docs/guides/usage-report.vi.md`
  - Create `docs/guides/recommended-tools.vi.md`
  - Create `docs/guides/windows.vi.md`
  - Test `tests/workflow_core/test_docs_coverage.py`
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `low`
- **Why:** raises model above `haiku` for accurate, idiomatic Vietnamese technical prose across 11 guides while keeping `Effort: low` because structure, code blocks, and anchor targets are fixed 1-to-1 from the English guides.
- **Interfaces**:
  - Consumes the 11 English guide files under `docs/guides/*.md`.
  - Produces the 11 Vietnamese guide files under `docs/guides/*.vi.md`.
- **Acceptance criteria**: All 17 `.vi.md` files across `docs/` exist; `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m workflow_core.cli docs check docs/guides/*.vi.md` prints `ok`; `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.test_all` passes; `uv run --with-requirements requirements-docs.txt -- mkdocs build --strict` exits 0 with zero warnings.
- **Estimated complexity**: medium

Steps:

1. Verify that the 11 `docs/guides/*.vi.md` files do not exist yet (`ls docs/guides/*.vi.md` exits non-zero) and inspect all `#anchor` links targeting `guides/*.md`:
   ```bash
   grep -rnEo '\]\([^)]*#[a-z0-9_-]+\)' docs/
   ```
2. Create `docs/guides/use-cases.vi.md`, `docs/guides/team.vi.md`, `docs/guides/ai-strategy.vi.md`, `docs/guides/claude-workflow.vi.md`, `docs/guides/sdd.vi.md`, `docs/guides/qa.vi.md`, `docs/guides/customizing-templates.vi.md`, `docs/guides/rules.vi.md`, `docs/guides/usage-report.vi.md`, `docs/guides/recommended-tools.vi.md`, and `docs/guides/windows.vi.md`:
   - Preserve all code blocks, CLI commands, configuration keys, and file paths verbatim.
   - Attach explicit `{ #english-anchor }` attributes on every heading targeted by any intra-page or cross-page `#anchor` link (including `#enable-it-lead`, `#join-it-member`, `#ci-optional` in `team.vi.md`; `#requirements`, `#migrating` in `sdd.vi.md`; `#model-and-effort-by-stage`, `#allocating-team-accounts`, `#working-manually-when-ai-quota-runs-out` in `ai-strategy.vi.md`; `#personal-customization-without-affecting-the-team`, `#context-hygiene-and-session-habits` in `claude-workflow.vi.md`).
   - Follow all mechanical style rules (`docs_check.py`) and avoid pairing `beads` with `default` or `required` on a line without `optional`.
3. Run `docs check`, the unit test suite, and `mkdocs build --strict`:
   ```bash
   PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m workflow_core.cli docs check docs/guides/*.vi.md
   PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.workflow_core.test_docs_coverage tests.workflow_core.test_walkthrough_docs -v
   uv run --with-requirements requirements-docs.txt -- mkdocs build --strict
   ```
   Confirm all commands exit 0. Commit on `feat/docs-site-enhancements`: `docs(vi): translate all user and team guides to Vietnamese`.

## Integration
- **Branch**: `feat/docs-site-enhancements`
- **Merge strategy**: sequential

## Validation
- [ ] `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.workflow_core.test_docs_coverage tests.workflow_core.test_walkthrough_docs -v` passes
- [ ] `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m workflow_core.cli docs check` exits 0 on all modified and created Markdown files
- [ ] `uv run --with-requirements requirements-docs.txt -- mkdocs build --strict` exits 0 with zero warnings across both `en` and `vi`

## Notes
- `Model:` and `Effort:` are chosen from the main harness catalog (`claude`: `haiku`, `sonnet`, `opus`; efforts `low`, `medium`, `high`, `xhigh`, `max`) using the route rubric.
- At the epic level (`R0`), `/gin-workflow:orchestrate` registers `gin-workflow task dep add <epic-id>` dependencies on `gin-workflow-qa-case-folders`, `gin-workflow-qa-playwright-scaffold`, `gin-workflow-qa-test-types`, `gin-workflow-qa-manual-bugs`, `gin-workflow-qa-report`, and `gin-workflow-qa-setup` so this epic runs only after the `QA process` milestone (`gin-workflow-o2nc`) is completed.
- Plan steps are instructions for the executor, not literal text to paste into documentation pages; every documented CLI flag and config key must match `docs/reference/cli.md` and `docs/reference/config.md`.
- Deliverable merge-holds ("remain open until human-confirmed merge") apply exclusively to the Parent Bead. Individual track beads close upon passing tests and code review to unblock downstream dependent tracks.
