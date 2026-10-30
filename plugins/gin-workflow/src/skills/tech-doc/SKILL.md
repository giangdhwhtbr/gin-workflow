---
name: tech-doc
description: On /tech-doc only, write human-readable technical documentation (features, API, stack, integrations, architecture, structure, conventions, testing, concerns) from verified repository evidence.
---

# Tech Doc Skill

Write durable technical documentation for onboarding, architecture review, and planning. Run only when the user asks for `/tech-doc`; other stages look code up on demand instead of reading these files.

## Roles and routes

Pick catalog routes from `gin-workflow state --format json` under `catalog` ({harness, models weakest to strongest, efforts lowest to highest}). Refer to models by position (weakest, middle, strongest), never by name.

| Role | Agent | Route | Work |
|---|---|---|---|
| Scout | `gin-workflow:agent-researcher` | weakest or middle model, `low` | One scout per code area. Returns evidence notes with `file:line`, tagged by the document topic they serve (stack, routes, integrations, conventions, risks, and so on), so each source file is read once. |
| Writer | `gin-workflow:docs-writer` | by document: weakest model for `STACK`, `STRUCTURE`, `CONVENTIONS`, `TESTING`; middle model for `API`, `FEATURES`, `INTEGRATIONS`, `OVERVIEW`; strongest model for `ARCHITECTURE`, `CONCERNS` | One writer per document. Writes from the scout notes and the template, and opens only cited lines. `02-FEATURES.md` starts after `05-API.md`; the other writers run in parallel. |
| Reviewer | `gin-workflow:agent-researcher`, fresh session with a claim-verification brief | middle model, `medium` | Checks each claim against its citation and flags claims that are unbacked, wrong, or inference. Read-only. The writer fixes the findings, bounded by `routing.review.max_cycles`. |

Scout notes are runtime data under `.agent-workflow/runtime/tech-doc/<run>/` and are not committed. Ambiguity goes into the document's `Inference And Uncertainty` section and is never guessed. A failed writer escalates as in execute (next model in catalog at same effort; at strongest model, next effort; at top of both, stop and ask the user).

## Execution flow

The main session coordinates the run, agrees scope, splits code areas, picks catalog routes, checks cross-file consistency, and reports.

1. Agree scope with the user: whole repository or one subsystem. Confirm target output before writing.
2. Index and areas: run `codegraph files` (or a directory listing without `.codegraph/`) once and split code into areas. Pick catalog routes for each unit from `gin-workflow state --format json` under `catalog`.
3. Scout notes: spawn one scout per code area at its route from the roles table. Scouts write their notes to `.agent-workflow/runtime/tech-doc/<run>/`. They prefer code, lockfiles, configuration, migrations, schemas, tests, and workflow files, and treat index output as hints until verified against the files. For `05-API.md`, scouts find route declarations (`codegraph explore` first; then grep the frameworks present, e.g. Express/Fastify routers, NestJS decorators, FastAPI/Flask decorators, Django `urls.py`, Rails `routes.rb`, Next.js route handlers and server actions). For `02-FEATURES.md`, they find frontend routes and screens and the calls they make (`fetch`, axios, generated API clients, GraphQL hooks), and match each call to an endpoint by method and path. If the repository ships an OpenAPI or GraphQL schema, `05-API.md` links it and still lists the compact table.
4. Document shape: default to the split set below under `.planning/codebase/` (with `project.layout: sdd`, `artifacts.codebase`, default `docs/codebase/`; a subsystem gets a `<scope-slug>/` subfolder). Start each file from `gin-workflow specs template codebase/<FILE>.md`, which honors overrides in `.agent-workflow/templates/`. Files from before numbering (`OVERVIEW.md` … `CONCERNS.md`) in the output folder or in `.agent-workflow/templates/codebase/` are renamed to their numbered names with `git mv` before writing, so history and project overrides carry over. Use a single combined document only when the user asks for one, the scope is very narrow, or an approved plan says so. Do not invent alternate names (`Backend.md`, `Database.md`) when a canonical file covers the topic.
5. Write: spawn one writer per document at its route from the roles table. Give each writer the output of `gin-workflow rules --files <pages to write>` and [references/docs-style.md](../../references/docs-style.md). Clear prose with headings and short lists; Mermaid only where it clarifies architecture, data flow, or ownership; one topic per file, linking to siblings instead of repeating them. Writers separate verified facts from inference and name what is unknown and where the answer likely lives. Every `05-API.md` and `02-FEATURES.md` row cites `file:line`; a cell without a citation is marked as inference.
6. Review: spawn one reviewer per document at its route from the roles table. The writer fixes the findings, bounded by `routing.review.max_cycles`; unresolved ambiguity goes into `Inference And Uncertainty`.
7. Check and report: check consistency across the written files (terms, links, `02-FEATURES.md` against `05-API.md`). In the `Completeness Check` section of `05-API.md`, record the search method, the number of route declarations found, and the number of table rows, and explain any difference. In the `Coverage Gaps` section of `02-FEATURES.md`, list endpoints with no frontend caller, frontend calls with no matching endpoint, and features missing one side; serious gaps also go to `10-CONCERNS.md`. Report the files written, and `gin-workflow setup refresh` to update the links in `AGENTS.md`.

## Split documentation set

The number prefix is the reading order, so a directory listing reads top to bottom. A file that is not written (no `05-API.md` for a CLI) leaves its number unused; the other files keep theirs.

| File | Covers |
|---|---|
| `01-OVERVIEW.md` | purpose, capabilities summary (catalog in `02-FEATURES.md`), primary workflows, entry points, non-goals |
| `02-FEATURES.md` | feature catalog; map of each feature to frontend route/screen, API endpoint, backend handler, and data; coverage gaps |
| `03-ARCHITECTURE.md` | components and responsibilities, layers, request and data flows, key abstractions, constraints, error handling, cross-cutting concerns |
| `04-STRUCTURE.md` | directory layout, module responsibilities, key files, naming, generated assets, where to add new code |
| `05-API.md` | endpoints the repository exposes, grouped by module: method, path, handler, auth, summary, feature; other interfaces (GraphQL, WebSocket, inbound webhooks, gRPC); completeness check. Not written when the repository exposes no HTTP or RPC API |
| `06-INTEGRATIONS.md` | external services and APIs the repository calls, auth, webhooks, CI/CD, deployment, observability, env var names (never values) |
| `07-STACK.md` | languages, runtimes, package managers, frameworks and versions, build and test tools, platform requirements |
| `08-CONVENTIONS.md` | formatting, linting, imports, naming, error handling, logging, comments |
| `09-TESTING.md` | runners and commands, organization, fixtures and mocking, coverage, test types |
| `10-CONCERNS.md` | top risks with evidence, impact, remediation, suggested Beads, confidence |

Every file starts with `Analysis Date`, `Scope`, `Evidence` (files inspected, with line numbers when available), and `Index Use` (codegraph or direct inspection), and ends with `Inference And Uncertainty` and `Follow-up` (Beads to create, or "None identified").

When a column cannot apply, say so once instead of filling it: a CLI or library uses commands or public functions as the `02-FEATURES.md` entry point and drops the Frontend and API columns; a backend-only repository writes none for Frontend and lists only feature-level gaps in `Coverage Gaps`; a frontend-only repository writes no `05-API.md`, lists the third-party APIs it calls in `06-INTEGRATIONS.md`, and names the external endpoint in the API column.

These files are evidence for humans and planning, not runtime status; they never replace Beads state.

## Output standard

- Explain rather than enumerate; highlight the top risks.
- Back claims with concrete files and line numbers.
- Never present guessed behavior, stale references, or index-only findings as verified facts.

## Regrounding existing docs

When the user asks to reground (re-check) pages or a docs folder, check those pages against the code instead of writing new ones. Regrounding uses the same roles (scouts, writers, reviewers), with one writer per page.

1. Scouts inspect code at HEAD and record citations with `file:line` under `.agent-workflow/runtime/tech-doc/<run>/`.
2. Writers check each factual claim against citations, fix wrong claims, remove claims nothing backs, or call team practice a convention.
3. Reviewers verify claims and flag unbacked or inferential changes, bounded by `routing.review.max_cycles`.
4. Report per page: claims checked, fixed, and removed, and open questions.

Write only the pages in scope and only the claims you fix; add sections or restyle a page only when the request says so.
