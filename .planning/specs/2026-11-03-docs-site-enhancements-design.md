# Documentation site enhancements, team guides, and Vietnamese translation

Workflow: docs-site-enhancements
Depends on: gin-workflow-qa-case-folders, gin-workflow-qa-playwright-scaffold, gin-workflow-qa-test-types, gin-workflow-qa-manual-bugs, gin-workflow-qa-report, gin-workflow-qa-setup
Status: draft for user review.
Origin: user request on 2026-11-03 following `docs-site-foundation` to consolidate the brownfield starters, separate Tech Lead initial setup from team member onboarding in role guides, hide internal architecture tabs from GitHub Pages navigation, add copy-pasteable prompt templates with realistic dependency and AI-account constraints, add guides for effective AI and Claude Code usage (including a manual CLI workflow when AI quota runs out), improve readability with Mermaid diagrams across user-facing pages, and translate the user-facing documentation to Vietnamese. This epic depends on and executes only after the `QA process` milestone (`gin-workflow-o2nc`: `gin-workflow-qa-case-folders`, `gin-workflow-qa-playwright-scaffold`, `gin-workflow-qa-test-types`, `gin-workflow-qa-manual-bugs`, `gin-workflow-qa-report`, `gin-workflow-qa-setup`) ships, so that all QA documentation, role guides, prompt templates, and Vietnamese translations reflect the completed `gin-qa` workflow without merge conflicts or rework. Skill and CLI changes in `gin-workflow` for native `qa` provider-role routing and automated AI-account tier balancing are scoped into a separate follow-up epic.

## Goal and scope

The GitHub Pages site (`https://giangdhwhtbr.github.io/gin-workflow/`) currently exposes internal contributor and architecture pages in the top navigation, splits brownfield guidance across two starter files, points Business Analysts and other non-lead roles to initial project setup (`/gin-workflow:setup`), lacks copy-pasteable prompt templates and practical AI / Claude Code guides (including how a team continues working when AI quota is exhausted), and has only `docs/index.vi.md` translated into Vietnamese. In addition, the open `QA process` milestone (`gin-workflow-o2nc`) updates `gin-qa` (`qa/cases/<capability>/<type>.md`, `gin-qa cases result`, `/gin-qa:setup`, `/gin-qa:tests`, `/gin-qa:run` with bug beads, `gin-qa report --format xlsx`, and `gin-qa e2e init` Playwright scaffolding) and touches `docs/roles.md`, `docs/guides/qa.md`, `docs/guides/customizing-templates.md`, `docs/reference/skills.md`, and `docs/reference/cli.md`. Sequencing this epic after `gin-workflow-o2nc` ensures the restructured English pages and their Vietnamese translations cover the full QA lifecycle cleanly.

In scope:
- Execution dependency on milestone `gin-workflow-o2nc` (`gin-workflow-qa-case-folders`, `gin-workflow-qa-playwright-scaffold`, `gin-workflow-qa-test-types`, `gin-workflow-qa-manual-bugs`, `gin-workflow-qa-report`, `gin-workflow-qa-setup`): during `/gin-workflow:orchestrate` (or roadmap sync), the `docs-site-enhancements` epic bead adds `gin-workflow task dep add` dependencies on all six QA epics so its tracks do not become `ready` until the QA process milestone is closed.
- Navigation cleanup in `mkdocs.yml`: hide internal tabs (`Concepts`, `Orchestrator`, `Contributing`) and `reference/orchestrator-contract.md` from `nav` using `not_in_nav` while keeping `validation.nav.omitted_files: warn` active for all other pages, update `.planning/knowledge/docs-site-mkdocs.md`, and order `Guides` logically.
- Brownfield starter consolidation: merge `docs/starters/brownfield-modernize.md` and `docs/starters/brownfield-walkthrough.md` into a single `docs/starters/brownfield.md`, folding modernization strategy directly into the walkthrough stages (including the new `gin-qa` per-type case folders, `/gin-qa:setup`, `/gin-qa:tests`, `/gin-qa:run`, and `gin-qa report --format xlsx`), and updating all links and `tests/workflow_core/test_walkthrough_docs.py`.
- Team roles and onboarding restructure (`docs/roles.md`, `docs/getting-started.md`, `docs/guides/team.md`): separate `Tech lead` from `Developer` and other roles (`PM`, `BA`, `Tester`) so only the Tech Lead runs one-time project and team profile setup (`/gin-workflow:setup` and lead `/gin-workflow:team-setup`), while `guides/team.md#join-it-member` links to `getting-started.md#prerequisites` for CLI installation and guides members through member `/gin-workflow:team-setup` (and `/gin-qa:setup` for QA setup).
- Copy-pasteable prompt templates in `docs/reference/skills.md` and `docs/starters/brownfield.md`: realistic prompts for each stage and role (including `/gin-qa:setup`, `/gin-qa:cases`, `/gin-qa:tests`, `/gin-qa:run`, and `/gin-qa:e2e`), featuring legacy JSP-to-Spring Boot + React modernization with a 7-person team (matching 2 Claude Team Premium accounts and 5 Standard Team accounts), single-area tracks that pass `gin-workflow team check-plan`, Beads tracking for every role (including QA tracks and bug beads created via `gin-workflow task create -t bug --deps discovered-from:<epic>`), and the dependency flow (BA spec + API contract first -> parallel QA test cases, Backend API, and Frontend UI with mocks -> Frontend integration and Legacy router cutover -> QA E2E, manual runs, and consolidated report).
- New guide `docs/guides/ai-strategy.md`: recommended model and effort per lifecycle stage and skill (including all `gin-qa` skills) with rationale, allocating Premium vs Standard team accounts by assigning track `Owner:` to members holding those seats, and a step-by-step manual CLI fallback workflow (`gin-workflow team`, `task`, `worktree`, `rules`, `gin-qa cases/tests/e2e/report`) when all team AI accounts run out of quota.
- New guide `docs/guides/claude-workflow.md`: customizing personal AI guidance locally (`~/.claude/CLAUDE.md` so instructions apply across worktrees without git diffs, `.git/info/exclude` for local untracked files, `/model`, `gin-workflow setup harness-override`, `.agent-workflow/executables.local.yaml`, and `.agent-workflow/orchestrator.local.yaml` executable paths) vs shared team files, plus context hygiene and Claude Code habits.
- Readability and Mermaid diagram upgrades across user-facing pages (`getting-started.md`, `roles.md`, `starters/greenfield.md`, `starters/brownfield.md`, `guides/team.md`, `guides/sdd.md`, `guides/qa.md`, `guides/customizing-templates.md`, `guides/recommended-tools.md`, `guides/windows.md`): replace ASCII box diagrams with Mermaid diagrams, add visual workflow/handoff diagrams, and remove internal Python module/function references that do not help end users.
- Vietnamese translation (`*.vi.md`) for all 17 user-facing pages (`index.vi.md`, `getting-started.vi.md`, `roles.vi.md`, `starters/greenfield.vi.md`, `starters/brownfield.vi.md`, all 11 `guides/*.vi.md` pages, and `reference/skills.vi.md`), with `attr_list` enabled in `mkdocs.yml` so cross-referenced headings preserve stable anchor IDs across English and Vietnamese.

Out of scope:
- Implementing the `gin-qa` runtime features of `gin-workflow-o2nc` (those belong to the six `gin-workflow-qa-*` epics that this epic depends on).
- Modifying `gin-workflow` Python runtime behavior or skill instructions for native `qa` provider-role routing (covered by the follow-up epic).
- Translating `docs/concepts/*`, `docs/orchestrator/*`, `docs/contributing.md`, or low-level reference pages (`cli.md`, `config.md`, `troubleshooting.md`, `orchestrator-contract.md`) into Vietnamese; those remain in English and use `fallback_to_default: true`.
- Deleting the Markdown files of hidden sections (`docs/concepts/*`, `docs/orchestrator/*`, `docs/contributing.md`, `docs/reference/orchestrator-contract.md`) from the repository, because `AGENTS.md` and `test_docs_coverage.py` require them in the repo.

## Requirements

### R0. Beads dependency on the `QA process` milestone (`gin-workflow-o2nc`)

- When the parent epic bead for `docs-site-enhancements` is created in Beads, it registers blocking dependencies (`gin-workflow task dep add <docs-epic> <qa-epic>`) on all six open epics of milestone `gin-workflow-o2nc`:
  - `gin-workflow-qa-case-folders`
  - `gin-workflow-qa-playwright-scaffold`
  - `gin-workflow-qa-test-types`
  - `gin-workflow-qa-manual-bugs`
  - `gin-workflow-qa-report`
  - `gin-workflow-qa-setup`
- Execution of `docs-site-enhancements` tracks begins only after those six epics are closed and merged into `master`, so that `docs/roles.md`, `docs/guides/qa.md`, `docs/guides/customizing-templates.md`, `docs/reference/skills.md`, and `docs/reference/cli.md` already contain the `gin-workflow-o2nc` changes before `docs-site-enhancements` restructures, diagrams, and translates them.

### R1. Navigation and hidden internal pages (`mkdocs.yml`, `README.md`, and `.planning/knowledge/docs-site-mkdocs.md`)

- `mkdocs.yml` removes the `Concepts`, `Orchestrator`, and `Contributing` top-level sections and the `reference/orchestrator-contract.md` entry from `nav`, and removes `Concepts`, `Orchestrator`, and `Contributing` from `nav_translations`.
- `mkdocs.yml` lists `/concepts/**`, `/orchestrator/**`, `/contributing.md`, and `/reference/orchestrator-contract.md` under `not_in_nav` while keeping `validation.nav.omitted_files: warn` (if `mkdocs-static-i18n` 1.3.1 emits a warning for `not_in_nav` on fallback `vi` pages during `mkdocs build --strict`, fallback to `validation.nav.omitted_files: ignore` and assert `nav` membership for user-facing pages in `tests/workflow_core/test_docs_coverage.py`).
- `mkdocs.yml` adds `attr_list` to `markdown_extensions` so translated `.vi.md` headings can carry explicit `{ #anchor-id }` attributes matching English anchors.
- Top-level `nav` tabs in `mkdocs.yml` are: `Home` (`index.md`), `Getting started` (`getting-started.md`), `Team roles` (`roles.md`), `Starters` (`starters/greenfield.md`, `starters/brownfield.md`), `Guides` (`guides/use-cases.md`, `guides/team.md`, `guides/ai-strategy.md`, `guides/claude-workflow.md`, `guides/sdd.md`, `guides/qa.md`, `guides/customizing-templates.md`, `guides/rules.md`, `guides/usage-report.md`, `guides/recommended-tools.md`, `guides/windows.md`), and `Reference` (`reference/skills.md`, `reference/cli.md`, `reference/config.md`, `reference/troubleshooting.md`).
- `nav_translations` under the `vi` locale in `mkdocs.yml` translates every top-level tab and child item in `Starters`, `Guides`, and `Reference`.
- `README.md` updates its documentation table to replace `brownfield-modernize.md` and `brownfield-walkthrough.md` with `docs/starters/brownfield.md` and adds `docs/guides/ai-strategy.md` and `docs/guides/claude-workflow.md`, keeping every non-`.vi.md` file in `docs/` linked so `test_every_docs_page_is_in_the_readme_map` passes.
- `.planning/knowledge/docs-site-mkdocs.md` is updated to record that internal architecture and contributor pages are hidden from `nav` while remaining in `docs/`.
- User-facing onboarding and starter pages (`docs/index.md`, `docs/getting-started.md`, `docs/roles.md`, `docs/starters/greenfield.md`, `docs/starters/brownfield.md`) do not route users to the hidden `concepts/` or `orchestrator/` pages in their reading lists or next-steps sections.

### R2. Consolidated brownfield starter (`docs/starters/brownfield.md`)

- `docs/starters/brownfield-modernize.md` and `docs/starters/brownfield-walkthrough.md` are replaced by a single `docs/starters/brownfield.md` (with `git rm` on the two old files).
- `docs/starters/brownfield.md` retains `## The scenario` and `## The flow at a glance` and integrates the modernization strategy directly into the walkthrough stages:
  - `## The scenario`: defines a 7-person team (`lan@example.com` as `pm`, `an@example.com` as `ba`, `binh@example.com` as `be_lead`, `em@example.com` and `dung@example.com` as `be_dev`, `hoa@example.com` as `fe_dev`, `chi@example.com` as `qe`) matching 2 Claude Team Premium seats (`lan` for roadmap/milestone and `binh` for architecture/plan/review/complex migration) and 5 Standard Team seats (`an`, `em`, `dung`, `hoa`, `chi`).
  - Non-overlapping `team.areas` that pass `validate_team` (`team.py:105-109`):
    - `legacy: {paths: ["legacy/**"], lead: be_lead, roles: [be_dev]}`
    - `api: {paths: ["services/api/**"], lead: be_lead, roles: [be_dev]}` (removing `qa/api/**`)
    - `web: {paths: ["apps/web/**"], lead: be_lead, roles: [fe_dev]}` (removing `qa/web/**`)
    - `qa: {paths: ["qa/**"], lead: be_lead, roles: [qe]}`
  - Non-deadlocking `team.approvals`: `requirement_confirmed: [ba, be_lead]`, `plan_approved: area_lead`, `ship: [qe, be_lead]` (so `chi`'s own QA track PRs can be approved by `binh` while `chi` approves developer track PRs), `roadmap: [pm, be_lead]`.
  - `## Repository and workspace setup`: monorepo layout, importing legacy history with `git subtree add` / `git subtree pull`, when a legacy repo stays separate, configuring `project.packages` for multi-stack repos (Maven + npm), and path-scoped `team.areas`.
  - `## Setup and team setup`: Tech Lead one-time setup (`/gin-workflow:setup` and `/gin-workflow:team-setup` as lead) vs team member onboarding (`/gin-workflow:team-setup` as member, plus `/gin-qa:setup` run once by `chi` to initialize `qa/guidelines.md`, `qa/README.md`, and the project QA skill).
  - `## Survey the legacy system`: `/gin-workflow:tech-doc` across the legacy monolith.
  - `## Roadmap overview` and `## Milestone planning`: `/gin-workflow:roadmap` and `gin-workflow milestone` commands with team capacity, AI account tiers, and dependency ordering.
  - `## Discuss an epic` (with subsection `### Capture current behavior first`): capturing current legacy behavior, edge cases, and validation rules as living specs (`REQ-...`) plus explicit API contracts so Backend, Frontend, and QA can work in parallel once confirmed.
  - `## Plan and orchestrate` (with subsection `### Strangler Fig`): Strangler Fig facade routing, data migration strategy (dual-write or backfill and rollback criteria), and decomposing an epic into single-area tracks that pass `gin-workflow team check-plan` across `qa`, `api`, `web`, and `legacy` (see R4).
  - `## Test cases`: `/gin-qa:cases` writing per-type case files under `qa/cases/<capability>/<type>.md` (`api.md`, `e2e.md`, `manual.md`), parity / characterization testing (Golden Master payloads comparing legacy and modern responses, plus requirement hash pinning), and `/gin-qa:tests <capability> --type api`, tracked as a QA track bead.
  - `## Execute`, `## E2E` (covering `gin-qa e2e init` with `playwright.config.ts`, `/gin-qa:e2e`, `/gin-qa:run` for manual cases and logging bug beads via `gin-workflow task create -t bug --deps discovered-from:<epic>`, and `gin-qa report --format xlsx`), `## Ship`, `## Milestone review and spill-over`, `## Customizing outputs`, and `## Solo variant`.
- Every prose mention of the tool name `` `gin-workflow` `` in `docs/starters/brownfield.md` (and `docs/guides/ai-strategy.md`) is wrapped in backticks so `test_walkthrough_docs.undocumented` does not mistake prose words for undocumented CLI subcommands, and the word `sprint` never appears.
- `tests/workflow_core/test_walkthrough_docs.py` updates `WALKTHROUGH` to `ROOT / "docs/starters/brownfield.md"` (and also checks `ROOT / "docs/guides/ai-strategy.md"` for undocumented `gin-workflow` CLI subcommands, adding `"dep"` to `BD_PASSTHROUGH`) and continues asserting all required milestone headings (`## Repository and workspace setup`, `## Roadmap overview`, `## Milestone planning`, `## Milestone review and spill-over`).
- Every link across `docs/`, `README.md`, and `plugins/*/src/skills/` that pointed to `brownfield-modernize.md` or `brownfield-walkthrough.md` is updated to `brownfield.md` and its corresponding section anchors (`#repository-and-workspace-setup`, `#capture-current-behavior-first`, `#strangler-fig`, `#discuss-an-epic`, `#plan-and-orchestrate`, `#test-cases`, `#execute`, `#e2e`, `#ship`).

### R3. Team roles and onboarding separation (`docs/roles.md`, `docs/getting-started.md`, `docs/guides/team.md`)

- `docs/roles.md` includes a Mermaid `flowchart LR` diagram showing how the five roles (`Tech lead`, `PM`, `BA`, `Developer`, `Tester`) collaborate across gates from `setup` and `roadmap` through `ship`.
- `docs/roles.md` separates `Tech lead` from `Developer` as distinct rows in the `## Who owns what` table and as separate `### Tech lead` and `### Developer` subsections in `## What each role reads` (so each role heading slug appears only once in the document):
  - `Tech lead`:
    - Skills: `/gin-workflow:setup`, `/gin-workflow:team-setup` (as lead), `/gin-workflow:tech-doc`, `/gin-workflow:plan`, `/gin-workflow:orchestrate`, `/gin-workflow:review`, `/gin-workflow:ship`.
    - Files: `.agent-workflow/config.yaml`, `.planning/codebase/` (`docs/codebase/` with SDD), `.planning/plans/` (`04-plan.md` with SDD), and area source/test paths.
    - Branch: `chore/team-setup`, `plan/<topic>`, `feat/<topic>-t<N>`.
    - Approves: `plan_approved` (`area_lead`), and acts as backup approver for `roadmap`, `requirement_confirmed`, and QA `ship` PRs when a role has a single holder.
    - Reads: `getting-started.md`, `guides/team.md#enable-it-lead`, `guides/ai-strategy.md`, and `starters/brownfield.md`.
  - `PM`:
    - Skills: `/gin-workflow:roadmap`, `/gin-workflow:roadmap --milestone`, `/gin-workflow:progress`, `/gin-workflow:report`.
    - Files: `.planning/roadmap.md` (`docs/roadmap.md` with SDD).
    - Branch: `roadmap/<topic>`.
    - Approves: `roadmap`.
    - Reads: `guides/team.md#join-it-member`, the Roadmap and Milestone sections of `starters/brownfield.md`, `guides/usage-report.md`, and `reference/skills.md`.
  - `BA`:
    - Skills: `/gin-workflow:discuss`, `/gin-workflow:tech-doc`, `/gin-workflow:progress`.
    - Files: `.planning/specs/` (`docs/specs/` and `docs/changes/` with SDD).
    - Branch: `spec/<topic>` (`spec/<epic>-<slug>` with SDD).
    - Approves: `requirement_confirmed`.
    - Reads: `guides/team.md#join-it-member`, `guides/sdd.md`, `guides/customizing-templates.md`, and the `Discuss an epic` section of `starters/brownfield.md`. (`getting-started.md` is removed from BA's reading list so BAs are never instructed to run `/gin-workflow:setup`.)
  - `Developer`:
    - Skills: `/gin-workflow:execute`, `/gin-workflow:review`, `/gin-workflow:ship` (for their own tracks; the Tech Lead declares the epic complete once all track PRs merge, and without shared Beads each owner also runs `/gin-workflow:orchestrate` for their own tracks), `/gin-workflow:quick`, `/gin-workflow:progress`.
    - Files: source and unit/integration test paths in their assigned `team.areas`.
    - Branch: `feat/<topic>-t<N>` per track.
    - Approves: peer code reviews.
    - Reads: `guides/team.md#join-it-member`, `guides/claude-workflow.md`, `guides/rules.md`, and the `Execute` section of `starters/brownfield.md`.
  - `Tester`:
    - Skills: `/gin-qa:setup`, `/gin-qa:cases`, `/gin-qa:tests`, `/gin-qa:run`, `/gin-qa:e2e`, `/gin-workflow:progress`.
    - Files: `qa/guidelines.md`, `qa/README.md`, `qa/cases/<capability>/<type>.md`, `qa/e2e/`, `qa/evidence/`.
    - Branch: `feat/<topic>-t<N>` for QA tracks, and reviews developer pull requests.
    - Approves: `ship`.
    - Reads: `guides/team.md#join-it-member`, `guides/qa.md`, `guides/sdd.md#requirements`, and the `Test cases` and `E2E` sections of `starters/brownfield.md`.
- `docs/guides/team.md#join-it-member` opens with a link to `../getting-started.md#prerequisites` so non-lead team members install Python, Git, the `gin-workflow` (and optional `gin-qa`) plugin, and `bd` before running `/gin-workflow:team-setup` as a member, without reading `getting-started.md#one-time-setup`.
- `docs/getting-started.md` adds a callout under `## One-time setup` stating that in a team repository, only the Tech Lead runs `/gin-workflow:setup` once and commits `.agent-workflow/config.yaml`; teammates join an already-configured repository via `guides/team.md#join-it-member`.

### R4. Copy-pasteable prompt templates (`docs/reference/skills.md` and `docs/starters/brownfield.md`)

- `docs/reference/skills.md` adds a `## Prompt templates` section with ready-to-copy prompt blocks for each stage and role (`setup`, `team-setup` for lead and member, `tech-doc`, `roadmap`, `roadmap --milestone`, `discuss`, `plan`, `orchestrate`, `execute`, `/gin-qa:setup`, `/gin-qa:cases`, `/gin-qa:tests`, `/gin-qa:run`, `/gin-qa:e2e`, `ship`, and `report`).
- The `/gin-workflow:roadmap` and `/gin-workflow:plan` templates (and matching examples in `docs/starters/brownfield.md`) demonstrate a 7-person Java JSP to Spring Boot + React modernization scenario that obeys all `team.py` and `test_docs_coverage.py` invariants:
  - Team composition: 7 members (`lan` PM, `an` BA, `binh` Tech Lead / `be_lead`, `em` and `dung` Backend Devs / `be_dev`, `hoa` Frontend Dev / `fe_dev`, `chi` QA / `qe`) across non-overlapping areas `legacy`, `api`, `web`, and `qa`.
  - AI account allocation: explains that "Premium vs Standard" is modeled by assigning track `Owner:` to the members holding the 2 Claude Team Premium seats (`lan` for `/roadmap`, `binh` for `/plan`, complex Strangler Fig / migration tracks at `opus`/`high` or `sonnet`/`high`, and reviews) and assigning bounded tracks at `sonnet`/`medium` or `haiku`/`low` to the 5 members holding Standard seats (`an`, `em`, `dung`, `hoa`, `chi`).
  - Full Beads tracking across all roles without triggering `BEADS_DEFAULT` (avoid pairing the words `beads` and `required`/`default` on the same line without `optional`): every track for Backend, Frontend, and QA (`qa/cases/**`, `qa/e2e/**`, using `Provider role: general` today) becomes a Track Bead in `/gin-workflow:orchestrate` claimed via `gin-workflow team claim <bead>`, and manual/automated QA defects are logged as bug beads linked via `--deps discovered-from:<epic>`.
  - Single-area track dependency graph (illustrated with a Mermaid `flowchart LR` diagram) that passes `gin-workflow team check-plan`:
    1. Gate prerequisite: BA (`an`) completes `/gin-workflow:discuss <epic-id>` and passes `requirement_confirmed` with an explicit REST API contract and legacy edge cases before any track starts.
    2. Parallel wave after `requirement_confirmed` (zero cross-track blockers):
       - Track 1 (`Area: qa`, `Owner: chi@example.com`, `Provider role: general`, `Files: Create qa/cases/catalog/api.md, qa/cases/catalog/e2e.md, qa/cases/catalog/manual.md`): QA writes per-type test cases (`/gin-qa:cases catalog`).
       - Track 2 (`Area: api`, `Owner: em@example.com`, `Provider role: backend`, `Files: Create services/api/...`): Backend implements the Spring Boot REST API, facade, and parity tests against the contract.
       - Track 3 (`Area: web`, `Owner: hoa@example.com`, `Provider role: frontend`, `Files: Create apps/web/...`): Frontend implements the React UI against contract mocks without waiting for Backend.
    3. Dependent integration and cutover wave:
       - Track 4 (`Area: web`, `Owner: hoa@example.com`, `Dependencies: Track 2, Track 3`, `Files: Modify apps/web/...`): Frontend integration track replacing contract mocks with real API calls.
       - Track 5 (`Area: legacy`, `Owner: binh@example.com`, `Dependencies: Track 2`, `Files: Modify legacy/...`): Legacy Strangler Fig router cutover to the new API facade (assigned to `binh` on a Premium seat at `opus`/`high`).
    4. Final verification and reporting wave:
       - Track 6 (`Area: qa`, `Owner: chi@example.com`, `Dependencies: Track 1, Track 4, Track 5`, `Provider role: general`, `Files: Create qa/e2e/catalog/...`): QA runs `/gin-qa:tests catalog --type api`, `/gin-qa:e2e catalog`, `/gin-qa:run catalog` (recording results with `gin-qa cases result` and filing any bug beads), and exports `gin-qa report --format xlsx --out qa/report.xlsx` before approving `ship`.

### R5. New guide: Using AI effectively in a team (`docs/guides/ai-strategy.md`)

- Creates `docs/guides/ai-strategy.md` covering:
  - A stage-by-stage table of recommended model (`haiku`, `sonnet`, `opus` or catalog equivalents) and effort (`low`, `medium`, `high`) for `/setup`, `/team-setup`, `/tech-doc`, `/roadmap`, `/discuss`, `/plan`, `/orchestrate`, `/execute` (by track complexity), `/review`, `/ship`, `/gin-qa:setup`, `/gin-qa:cases`, `/gin-qa:tests`, `/gin-qa:run`, and `/gin-qa:e2e`, with a clear `Why` column explaining the reasoning and cost/quality trade-off of each choice. (No `✓` or other emoji characters.)
  - A Mermaid diagram and guide for balancing mixed AI subscriptions across a team (2 Premium seats and 5 Standard seats) by routing high-reasoning stages and tracks to Premium seat holders via `Owner:`, and setting `usage.budget_usd`.
  - A `## Working manually when AI quota runs out` section with a Mermaid diagram and exact CLI commands showing how the team continues working without breaking the workflow when one member or the entire team exhausts AI quota:
    - Handing over a track when one member is out of quota: push the track branch `feat/<topic>-t<N>`, run `gin-workflow team reassign <bead> <email>`, and on the new owner's machine run `git fetch origin && git worktree add .planning/worktrees/<bead> feat/<topic>-t<N>` (noting that `gin-workflow worktree create` is only for new branches) followed by `gin-workflow team claim <bead>`.
    - If quota runs out after `plan` is approved but before `orchestrate` has run: how to create track beads manually (`gin-workflow task create --parent <epic> --labels track:<N>,area:<area> --assignee <owner> "<title>"`, `gin-workflow task dep add <blocked> <blocker>`, and `gin-workflow record orchestration-ready --workflow-id <epic> --epic <epic> --evidence "<bead-ids>"`).
    - Continuing manually per track after `orchestrate`:
      1. Update external dependencies and claim a task: in team mode run `gin-workflow team deps`, `gin-workflow team ready`, and `gin-workflow team claim <bead>` (which writes a lease); in solo mode run `gin-workflow task ready` and `gin-workflow task update <bead> --claim`.
      2. Create or enter the worktree (`gin-workflow worktree create <bead> feat/<topic>-t<N>` for a new branch, then `cd .planning/worktrees/<bead>`) and check `gin-workflow team deps --bead <bead>`.
      3. Read the track's `Files:` and `Interfaces:` in the plan, inspect applicable rules with `gin-workflow rules --files <paths>`, implement test-first, and commit (`pre-commit` hook runs `lint` and `typecheck`).
      4. For QA tracks (`Area: qa`): run `gin-qa cases plan <capability>`, `gin-qa cases next-id <capability>`, edit `qa/cases/<capability>/<type>.md`, `gin-qa cases pin <TC-ID>`, `gin-qa cases result <TC-ID> <status> [--run <ref>] [--bug <bead>]`, and `gin-qa cases check` (plus `gin-qa tests run --type <type>`, `gin-qa e2e run`, `gin-qa e2e check --run <folder>`, and `gin-qa report --format xlsx --out <path>`).
      5. Close the track bead: under `easy` or `standard` rigor (`project.review_ledger: false`), run `gin-workflow task close <bead> --reason "Tests pass; implemented manually"`; under `strict` rigor (`project.review_ledger: true`), run `gin-workflow task close <bead> --waive-review "AI quota exhausted; peer reviewed in PR #<num>" --actor <your-email> --reason "Tests and PR review passed"`.
      6. Push `feat/<topic>-t<N>` (`pre-push` hook runs `test` at `easy`, `test` and `build` at `standard`, and `test`, `build`, and `e2e` at `strict`), run `gin-workflow team sync` when shared Beads is configured, and open the PR with `Plan: <plan-path>` and `Tracks: <N>` filled in the PR body so teammates' `gin-workflow team deps` can resolve it.
      7. Verify the `ship` gate and close the epic once all track PRs merge: `gin-workflow team check <pr-url> --gate ship`, `gin-workflow task close <epic> --reason "All tracks merged"`, and `gin-workflow worktree cleanup <bead>`.

### R6. New guide: Working effectively with Claude Code (`docs/guides/claude-workflow.md`)

- Creates `docs/guides/claude-workflow.md` covering:
  - A Mermaid diagram separating shared repository files committed to git (`.agent-workflow/config.yaml`, `AGENTS.md`, `CLAUDE.md`, `.planning/knowledge/`) from personal customization mechanisms that never create git diffs or affect teammates:
    - `~/.claude/CLAUDE.md` (user-scope instructions in Claude Code, such as preferred response language like Vietnamese, explanation verbosity, and personal workflow habits; unlike a repo-root `CLAUDE.local.md`, `~/.claude/CLAUDE.md` is automatically loaded inside every `.planning/worktrees/<id>` worktree without touching the repository).
    - `.git/info/exclude` for ignoring any personal repo-root scratch files locally without modifying the shared `.gitignore`.
    - `/model` inside Claude Code and `gin-workflow setup harness-override --harness <name>` for session-level model/effort and harness selection.
    - `.agent-workflow/executables.local.yaml` and `.agent-workflow/orchestrator.local.yaml` (`providers.<name>.executable`, git-ignored by `.agent-workflow/.gitignore`) for machine-local CLI binary paths when a tool is installed outside standard `PATH` directories.
    - Personal memory (`~/.claude/`) vs shared project knowledge (`.planning/knowledge/` and `bd remember`).
  - Practical Claude Code session habits for `gin-workflow`: switching model and effort (`/model`) before running a stage skill, clearing or compacting context (`/clear`, `/compact`) between lifecycle stages (`discuss`, `plan`, `execute`) to reduce token burn and context drift, using CodeGraph (`codegraph explore`) for targeted lookups, and running `/goal` for unattended tracks that have no `Human gate:`.

### R7. Readability improvements and Mermaid diagrams across existing user-facing docs

- Replaces ASCII box art with Mermaid `flowchart` diagrams in `docs/starters/greenfield.md` (the SDD feature lifecycle diagram) and `docs/guides/customizing-templates.md` (the template override lookup diagram).
- Adds Mermaid overview diagrams to `docs/getting-started.md` (the recorded gate pipeline from `discuss` to `ship`), `docs/guides/team.md` (Lead one-time setup vs Member join and PR-gated track lifecycle), `docs/guides/sdd.md` (living specs vs change delta and archive flow), and `docs/guides/qa.md` (`REQ-ID@hash8` -> `qa/cases/<cap>/<type>.md` -> `gin-qa tests` / `gin-qa e2e` / `/gin-qa:run` -> `gin-qa cases result` & bug beads -> `gin-qa report --format xlsx` & `ship` approval). Every Mermaid block starts at column 0 with a supported diagram type (`flowchart`, `graph`, `sequenceDiagram`, `stateDiagram-v2`, `stateDiagram`, `classDiagram`, `erDiagram`) and no `%%{init}%%` directive on line 1 so `test_mermaid_blocks_name_a_diagram_type` passes.
- Simplifies overly dense technical prose and removes internal Python implementation references from user-facing guides (`workflow_core/specs.py` in `customizing-templates.md`, `rules_checks.py` and `workflow_core/atomic.py` in `windows.md`, and the internal `stage-contract.md` link in `recommended-tools.md`), while preserving all CLI commands, configuration keys, and behavioral accuracy verified against the codebase.

### R8. Vietnamese translations (`*.vi.md`) and mechanical checks

- Writes Vietnamese translations next to their English sources (`docs_structure: suffix`) for all 17 user-facing pages:
  1. `docs/index.vi.md` (updated to match `index.md` links)
  2. `docs/getting-started.vi.md`
  3. `docs/roles.vi.md`
  4. `docs/starters/greenfield.vi.md`
  5. `docs/starters/brownfield.vi.md`
  6. `docs/guides/use-cases.vi.md`
  7. `docs/guides/team.vi.md`
  8. `docs/guides/ai-strategy.vi.md`
  9. `docs/guides/claude-workflow.vi.md`
  10. `docs/guides/sdd.vi.md`
  11. `docs/guides/qa.vi.md`
  12. `docs/guides/customizing-templates.vi.md`
  13. `docs/guides/rules.vi.md`
  14. `docs/guides/usage-report.vi.md`
  15. `docs/guides/recommended-tools.vi.md`
  16. `docs/guides/windows.vi.md`
  17. `docs/reference/skills.vi.md` (with prompt templates in natural Vietnamese prose while keeping slash commands, CLI commands, config keys, file paths, and `REQ-ID`s verbatim).
- Headings in `.vi.md` files that are referenced by `#anchor` links carry explicit `{ #english-anchor }` attributes (enabled by `attr_list` in `mkdocs.yml`) so all cross-page anchor links work identically in both `en` and `vi`.
- Every English and `.vi.md` page obeys the mechanical style rules enforced by `workflow_core/docs_check.py` and `tests/workflow_core/test_docs_coverage.py`: no en-dash or em-dash outside code blocks, no list item opening with bold text, no numbered headings, no emoji (including `✓`), no forbidden `beads` default/required phrasing without `optional`, typed Mermaid fences, and valid relative links and anchors under `mkdocs build --strict`.

## User Stories

### US-1: Single brownfield entry point sequenced after QA process enhancements
As a Tech Lead modernizing a legacy application, I want one consolidated brownfield starter that combines modernization strategy with the step-by-step team and QA walkthrough after the `QA process` milestone (`gin-workflow-o2nc`) completes, so that I do not jump between two brownfield files or read outdated QA instructions.

Acceptance criteria:
- The `docs-site-enhancements` epic bead in Beads depends on `gin-workflow-qa-case-folders`, `gin-workflow-qa-playwright-scaffold`, `gin-workflow-qa-test-types`, `gin-workflow-qa-manual-bugs`, `gin-workflow-qa-report`, and `gin-workflow-qa-setup`.
- `docs/starters/` contains `greenfield.md` and `brownfield.md` (plus their `.vi.md` translations), and `brownfield-modernize.md` and `brownfield-walkthrough.md` no longer exist.
- `docs/starters/brownfield.md` covers repository strategy (`git subtree`, `project.packages`, non-overlapping `team.areas`), capturing legacy behavior in specs, Strangler Fig and single-area migration tracks, parity testing, per-type QA cases (`qa/cases/<cap>/<type>.md`), automated and manual runs, and the full milestone walkthrough.
- `tests/workflow_core/test_walkthrough_docs.py` and `tests/workflow_core/test_docs_coverage.py` pass with zero dead links or undocumented command matches.

### US-2: Role-specific onboarding without setup confusion
As a Business Analyst, PM, Developer, or Tester joining a team repository, I want my role's reading list to guide me through installing prerequisites and joining the existing team configuration rather than running initial project setup, so that I do not accidentally re-run `/gin-workflow:setup` over the Tech Lead's configuration.

Acceptance criteria:
- `docs/roles.md` lists `Tech lead` separately from `Developer` and includes a Mermaid diagram of role handoffs.
- Only `Tech lead` links to `getting-started.md` and `guides/team.md#enable-it-lead`; `PM`, `BA`, `Developer`, and `Tester` link to `guides/team.md#join-it-member` as their first onboarding step, and `guides/team.md#join-it-member` links to `getting-started.md#prerequisites` for CLI installation.
- `docs/getting-started.md` explicitly notes that in team mode only the Tech Lead runs `/gin-workflow:setup` once, while teammates follow `guides/team.md#join-it-member`.

### US-3: Clean user-focused navigation on GitHub Pages
As a reader on the GitHub Pages site, I want internal plugin architecture and contributor pages hidden from the navigation tabs and existing guides illustrated with Mermaid diagrams, so that I can find practical guidance quickly without wading through internal implementation details.

Acceptance criteria:
- `mkdocs.yml` `nav` contains only `Home`, `Getting started`, `Team roles`, `Starters`, `Guides`, and `Reference` (without `orchestrator-contract.md`).
- `uv run --with-requirements requirements-docs.txt -- mkdocs build --strict` exits 0.
- `getting-started.md`, `roles.md`, `starters/greenfield.md`, `starters/brownfield.md`, `guides/team.md`, `guides/sdd.md`, `guides/qa.md`, and `guides/customizing-templates.md` render typed Mermaid diagrams instead of ASCII box art.

### US-4: Copy-pasteable prompts with realistic team, AI-account, and dependency rules
As a Tech Lead or PM, I want copy-pasteable prompt templates on the Skills reference and Brownfield starter pages that model team size, Premium vs Standard AI accounts, Beads tracking for every role including QA, and parallel-safe single-area dependencies, so that I can paste and adapt them directly for my team.

Acceptance criteria:
- `docs/reference/skills.md` contains a `## Prompt templates` section covering the lifecycle stages, `roadmap`, `team-setup`, `tech-doc`, and all `gin-qa` skills (`/gin-qa:setup`, `/gin-qa:cases`, `/gin-qa:tests`, `/gin-qa:run`, `/gin-qa:e2e`).
- The `roadmap` and `plan` prompt templates specify a 7-member team across non-overlapping `team.areas` (`legacy`, `api`, `web`, `qa`), 2 Premium vs 5 Standard Claude accounts mapped via track `Owner:`, Beads tracking for all roles including QA (`qa/cases/**` and `qa/e2e/**`, plus bug beads via `--deps discovered-from:<epic>`), and the single-area dependency flow: BA confirmed spec -> parallel QA test cases, Backend API, and Frontend UI with mocks -> Frontend integration and Legacy router cutover -> QA E2E, manual runs, and xlsx report.

### US-5: Effective AI usage, manual quota-exhaustion fallback, and personal Claude Code customization
As a team member, I want dedicated guides explaining which model and effort to pick per stage, how to customize Claude Code locally without affecting the team, and how to claim, execute, and close tasks via CLI when all AI accounts run out of quota, so that our team uses AI quota efficiently and never halts delivery when quota runs out.

Acceptance criteria:
- `docs/guides/ai-strategy.md` documents the recommended model, effort, and rationale for every stage and skill, how to split work across Premium and Standard accounts, and the complete manual CLI workflow (`team deps`, `team ready`, `team claim`, `worktree create` vs `git worktree add` for reassigned branches, `rules`, `gin-qa cases/tests/e2e/report`, `task close` with and without `--waive-review`, PR `Plan:`/`Tracks:` fields, `team check --gate ship`) when AI quota is exhausted.
- `docs/guides/claude-workflow.md` documents local customization via `~/.claude/CLAUDE.md` (active across worktrees without git diffs), `.git/info/exclude`, `/model`, `gin-workflow setup harness-override`, and `.agent-workflow/executables.local.yaml` vs shared team files, plus Claude Code context hygiene (`/clear`, `/compact`, `/goal`, `codegraph explore`).

### US-6: Vietnamese documentation for user and team guides
As a Vietnamese-speaking user, I want the entry pages, role guide, starters, practical guides, and skills reference translated into Vietnamese (`*.vi.md`), so that my team can read all day-to-day workflow instructions and prompt templates in Vietnamese.

Acceptance criteria:
- All 17 `.vi.md` pages (`index.vi.md`, `getting-started.vi.md`, `roles.vi.md`, `starters/greenfield.vi.md`, `starters/brownfield.vi.md`, all 11 `guides/*.vi.md` pages, and `reference/skills.vi.md`) exist and build under `/vi/` in `mkdocs build --strict`.
- Every `.vi.md` page passes `tests/workflow_core/test_docs_coverage.py` (relative links, Mermaid diagram types, mechanical style rules, and no forbidden `beads` default phrasing).

## Errors and compatibility

- Internal pages omitted from `mkdocs.yml` `nav` (`concepts/*`, `orchestrator/*`, `contributing.md`, `reference/orchestrator-contract.md`) remain on disk in `docs/`, so links from `AGENTS.md`, `CLAUDE.md`, `README.md`, or other docs continue to resolve in both `test_relative_links_resolve` and `mkdocs build --strict`.
- Anchor links in `.vi.md` pages: `attr_list` in `mkdocs.yml` allows `.vi.md` headings targeted by cross-page `#anchor` links to declare `{ #english-anchor }`, avoiding ASCII-stripped Vietnamese slug mismatches while `mkdocs build --strict` verifies every anchor across both locales.
- Mechanical style rules (`docs_check.py`): every English and `.vi.md` file is checked with `gin-workflow docs check` and `test_docs_coverage.py` so no en/em-dash, bold-label list item, numbered heading, or emoji (including `✓`) appears outside fenced code blocks, and every prose mention of `` `gin-workflow` `` in `brownfield.md` and `ai-strategy.md` is backticked.

## Testing

- `gin-workflow specs lint --spec .planning/specs/2026-11-03-docs-site-enhancements-design.md` prints `ok`.
- `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.workflow_core.test_docs_coverage tests.workflow_core.test_walkthrough_docs` passes.
- `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m workflow_core.cli docs check` passes on all created and modified `.md` and `.vi.md` files.
- `uv run --with-requirements requirements-docs.txt -- mkdocs build --strict` exits 0 with no warnings or broken links/anchors in either `en` or `vi`.
