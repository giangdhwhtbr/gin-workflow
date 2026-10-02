---
name: tech-doc
description: On /tech-doc only, write human-readable technical documentation (stack, integrations, architecture, structure, conventions, testing, concerns) from verified repository evidence.
---

# Tech Doc Skill

Write durable technical documentation for onboarding, architecture review, and planning. Run only when the user asks for `/tech-doc`; other stages look code up on demand instead of reading these files.

## Flow

1. **Scope**: whole repository or one subsystem (focus there, but note key outside dependencies). Confirm the target output before writing unless the request, Beads task, or approved plan already authorizes it.
2. **Gather evidence**: when `.codegraph/` exists, start with `codegraph files` for structure and `codegraph explore "<subsystem or question>"` for symbols and call paths; otherwise use grep and read. Treat index output as hints until verified against the files. Prefer code, lockfiles, configuration, migrations, schemas, tests, and workflow files.
3. **Choose the shape**: default to the split set below under `.planning/codebase/` (or `.planning/codebase/<scope-slug>/` for a subsystem). Use a single combined document only when the user asks for one, the scope is very narrow, or an approved plan says so. Do not invent alternate names (`Backend.md`, `Database.md`) when a canonical file covers the topic.
4. **Write**: clear prose with headings and short lists; Mermaid only where it clarifies architecture, data flow, or ownership; one topic per file, linking to siblings instead of repeating them.
5. **Mark uncertainty**: separate verified facts from inference; name what is unknown and where the answer likely lives.

## Split documentation set

| File | Covers |
|---|---|
| `OVERVIEW.md` | purpose, capabilities, primary workflows, entry points, non-goals |
| `STACK.md` | languages, runtimes, package managers, frameworks and versions, build and test tools, platform requirements |
| `INTEGRATIONS.md` | external services, APIs, auth, webhooks, CI/CD, deployment, observability, env var names (never values) |
| `ARCHITECTURE.md` | components and responsibilities, layers, request and data flows, key abstractions, constraints, error handling, cross-cutting concerns |
| `STRUCTURE.md` | directory layout, module responsibilities, key files, naming, generated assets, where to add new code |
| `CONVENTIONS.md` | formatting, linting, imports, naming, error handling, logging, comments |
| `TESTING.md` | runners and commands, organization, fixtures and mocking, coverage, test types |
| `CONCERNS.md` | top risks with evidence, impact, remediation, suggested Beads, confidence |

Every file starts with `Analysis Date`, `Scope`, `Evidence` (files inspected, with line numbers when available), and `Index Use` (codegraph or direct inspection), and ends with `Inference And Uncertainty` and `Follow-up` (Beads to create, or "None identified").

These files are evidence for humans and planning, not runtime status; they never replace Beads state.

## Output standard

- Explain rather than enumerate; highlight the top risks.
- Back claims with concrete files and line numbers.
- Never present guessed behavior, stale references, or index-only findings as verified facts.
