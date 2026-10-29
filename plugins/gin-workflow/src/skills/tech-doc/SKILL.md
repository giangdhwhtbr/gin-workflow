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
| Writer | `gin-workflow:docs-writer` | by the R2 rubric: weakest for `STACK`, `STRUCTURE`, `CONVENTIONS`, `TESTING`; middle for `API`, `FEATURES`, `INTEGRATIONS`, `OVERVIEW`; strongest for `ARCHITECTURE`, `CONCERNS` | One writer per document. Writes from the scout notes and the template, and opens only cited lines. `FEATURES.md` starts after `API.md`; the other writers run in parallel. |
| Reviewer | `gin-workflow:agent-researcher`, fresh session with a claim-verification brief | middle model, `medium` | Checks each claim against its citation and flags claims that are unbacked, wrong, or inference. Read-only. The writer fixes the findings, bounded by `routing.review.max_cycles`. |

Scout notes are runtime data under `.agent-workflow/runtime/tech-doc/<run>/` and are not committed. Ambiguity goes into the document's `Inference And Uncertainty` section and is never guessed. A failed writer escalates as in execute (next model in catalog at same effort; at strongest model, next effort; at top of both, stop and ask the user).

## Execution flow

The main session coordinates the run, agrees scope, splits code areas, picks catalog routes, checks cross-file consistency, and reports.

1. Agree scope with the user: whole repository or one subsystem. Confirm target output before writing.
2. Index and areas: run `codegraph files` (or a directory listing without `.codegraph/`) once and split code into areas. Pick catalog routes for each unit from `gin-workflow state --format json` under `catalog`.
3. Scout notes: spawn one `gin-workflow:agent-researcher` scout per code area at weakest or middle model and `low`. Scouts inspect files once, gathering evidence notes with `file:line` tagged by document topic (stack, routes, integrations, conventions, risks). Scouts write runtime notes to `.agent-workflow/runtime/tech-doc/<run>/`. For `API.md`, scouts note route declarations (`codegraph explore` first, then framework routers and decorators). For `FEATURES.md`, scouts note frontend routes and screens and outbound endpoint calls. If OpenAPI or GraphQL schemas exist, link them.
4. Document shape: default to the split set below under `.planning/codebase/` (with `project.layout: sdd`, `artifacts.codebase`, default `docs/codebase/`; a subsystem gets a `<scope-slug>/` subfolder). Start each file from `gin-workflow specs template codebase/<FILE>.md`, which honors overrides in `.agent-workflow/templates/`. Use a single combined document only when requested, scope is very narrow, or an approved plan says so. Do not invent alternate names (`Backend.md`, `Database.md`).
5. Write: spawn one `gin-workflow:docs-writer` per document at its catalog route from the roles table (`FEATURES.md` starts after `API.md`; other writers run in parallel). Run `gin-workflow rules --files <pages to write>` and give its output and [references/docs-style.md](../../references/docs-style.md) to the writer. Writers work from scout notes and templates, opening only cited lines. Write clear prose with headings and short lists; Mermaid only where it clarifies architecture, data flow, or ownership; one topic per file, linking to siblings instead of repeating them. A failed writer escalates as in execute.
6. Review: spawn a fresh `gin-workflow:agent-researcher` reviewer per document at middle model and `medium` with a claim-verification brief. The reviewer checks each claim against citations and flags claims that are unbacked, wrong, or inference. Read-only. The writer fixes findings, bounded by `routing.review.max_cycles`. Record unresolved ambiguity in `Inference And Uncertainty`.
7. Consistency check and report: check consistency across written files (terms, links, `FEATURES.md` against `API.md`). In `API.md` -> `Completeness Check`, record search method, route declarations found, table rows, and explain differences. In `FEATURES.md` -> `Coverage Gaps`, list unmatched endpoints and screens; serious gaps also go to `CONCERNS.md`. Run `gin-workflow setup refresh` to update links in `AGENTS.md`.

## Split documentation set

| File | Covers |
|---|---|
| `OVERVIEW.md` | purpose, capabilities summary (catalog in `FEATURES.md`), primary workflows, entry points, non-goals |
| `FEATURES.md` | feature catalog; map of each feature to frontend route/screen, API endpoint, backend handler, and data; coverage gaps |
| `API.md` | endpoints the repository exposes, grouped by module: method, path, handler, auth, summary, feature; other interfaces (GraphQL, WebSocket, inbound webhooks, gRPC); completeness check. Not written when the repository exposes no HTTP or RPC API |
| `STACK.md` | languages, runtimes, package managers, frameworks and versions, build and test tools, platform requirements |
| `INTEGRATIONS.md` | external services and APIs the repository calls, auth, webhooks, CI/CD, deployment, observability, env var names (never values) |
| `ARCHITECTURE.md` | components and responsibilities, layers, request and data flows, key abstractions, constraints, error handling, cross-cutting concerns |
| `STRUCTURE.md` | directory layout, module responsibilities, key files, naming, generated assets, where to add new code |
| `CONVENTIONS.md` | formatting, linting, imports, naming, error handling, logging, comments |
| `TESTING.md` | runners and commands, organization, fixtures and mocking, coverage, test types |
| `CONCERNS.md` | top risks with evidence, impact, remediation, suggested Beads, confidence |

Every file starts with `Analysis Date`, `Scope`, `Evidence` (files inspected, with line numbers when available), and `Index Use` (codegraph or direct inspection), and ends with `Inference And Uncertainty` and `Follow-up` (Beads to create, or "None identified").

When a column cannot apply, say so once instead of filling it: a CLI or library uses commands or public functions as the `FEATURES.md` entry point and drops the Frontend and API columns; a backend-only repository writes none for Frontend and lists only feature-level gaps in `Coverage Gaps`; a frontend-only repository writes no `API.md`, lists the third-party APIs it calls in `INTEGRATIONS.md`, and names the external endpoint in the API column.

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
