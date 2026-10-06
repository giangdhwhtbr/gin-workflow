---
name: tech-doc
description: On /tech-doc only, write human-readable technical documentation (features, API, stack, integrations, architecture, structure, conventions, testing, concerns) from verified repository evidence.
---

# Tech Doc Skill

Write durable technical documentation for onboarding, architecture review, and planning. Run only when the user asks for `/tech-doc`; other stages look code up on demand instead of reading these files.

## Flow

1. **Scope**: whole repository or one subsystem (focus there, but note key outside dependencies). Confirm the target output before writing unless the request, Beads task, or approved plan already authorizes it.
2. **Gather evidence**: when `.codegraph/` exists, start with `codegraph files` for structure and `codegraph explore "<subsystem or question>"` for symbols and call paths; otherwise use grep and read. Treat index output as hints until verified against the files. Prefer code, lockfiles, configuration, migrations, schemas, tests, and workflow files. For `API.md`, find route declarations (`codegraph explore` first; then grep the frameworks present, e.g. Express/Fastify routers, NestJS decorators, FastAPI/Flask decorators, Django `urls.py`, Rails `routes.rb`, Next.js route handlers and server actions). For `FEATURES.md`, find frontend routes and screens and the calls they make (`fetch`, axios, generated API clients, GraphQL hooks), and match each call to an endpoint by method and path. If the repository ships an OpenAPI or GraphQL schema, link it from `API.md` and still list the compact table.
3. **Choose the shape**: default to the split set below under `.planning/codebase/` (with `project.layout: sdd`, `artifacts.codebase`, default `docs/codebase/`; a subsystem gets a `<scope-slug>/` subfolder). Start each file from `gin-workflow specs template codebase/<FILE>.md`, which honors project overrides in `.agent-workflow/templates/`. Use a single combined document only when the user asks for one, the scope is very narrow, or an approved plan says so. Do not invent alternate names (`Backend.md`, `Database.md`) when a canonical file covers the topic.
4. **Write**: clear prose with headings and short lists; Mermaid only where it clarifies architecture, data flow, or ownership; one topic per file, linking to siblings instead of repeating them.
5. **Mark uncertainty and check completeness**: separate verified facts from inference; name what is unknown and where the answer likely lives. Every `API.md` and `FEATURES.md` row cites `file:line`; a cell without a citation is marked as inference. In `API.md` → `Completeness Check`, record the search method, the number of route declarations found, and the number of table rows, and explain any difference. In `FEATURES.md` → `Coverage Gaps`, list endpoints with no frontend caller, frontend calls with no matching endpoint, and features missing one side; serious gaps also go to `CONCERNS.md`.

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

When a column cannot apply, say so once instead of filling it: a CLI or library uses commands or public functions as the `FEATURES.md` entry point and drops the Frontend and API columns; a backend-only repository writes `—` for Frontend and lists only feature-level gaps in `Coverage Gaps`; a frontend-only repository writes no `API.md`, lists the third-party APIs it calls in `INTEGRATIONS.md`, and names the external endpoint in the API column.

These files are evidence for humans and planning, not runtime status; they never replace Beads state.

## Output standard

- Explain rather than enumerate; highlight the top risks.
- Back claims with concrete files and line numbers.
- Never present guessed behavior, stale references, or index-only findings as verified facts.
