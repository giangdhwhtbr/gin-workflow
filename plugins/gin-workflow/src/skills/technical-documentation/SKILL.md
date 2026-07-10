---
name: technical-documentation
description: Scan a codebase and write human-readable technical documentation as concrete mapper-style split files covering stack, integrations, architecture, structure, conventions, testing, concerns, and subsystem overview.
---

# Technical Documentation Skill

This skill generates durable technical documentation for humans and downstream agents. It is intended for onboarding, architecture review, planning, research, and maintenance work, not just a raw file listing.

By default, write a mapper-style split documentation set under `.planning/codebase/`. Each major documentation concern gets its own file so planners, researchers, implementers, and reviewers can load only the context they need.

## Core Flow

1. **Scope the request**:
   - Determine whether the documentation covers the whole repository or a specific subsystem.
   - If the user provides a feature area or directory, focus the analysis there while still noting key dependencies outside the scope.
   - Confirm the target output before writing unless the user request, Beads task, approved plan, or handoff context already authorizes the documentation path and format.
2. **Gather codebase evidence**:
   - Use existing `codebase-mapper` findings when present, or gather mapper-style evidence directly with repository inspection.
   - Prefer codegraph or equivalent repository-index tools when exposed by the platform, but treat index output as hints until verified against concrete files. Direct inspection is sufficient when no index is available.
   - Identify modules, entry points, libraries, runtime boundaries, storage choices, external integrations, operational files, conventions, tests, and quality risks.
   - Prefer evidence from code, lockfiles, configuration, migrations, schema files, top-level docs, tests, and workflow files.
3. **Choose the documentation shape**:
   - Default to the canonical split file set in `.planning/codebase/`.
   - Use a single combined document only when the user explicitly asks for one, the scope is very narrow, or an approved plan authorizes a different target.
   - For subsystem-scoped requests, write the same canonical sections under `.planning/codebase/<scope-slug>/`.
   - Do not invent alternate names such as `Backend.md`, `Frontend.md`, or `Database.md` when the canonical files below cover the topic.
4. **Write readable technical documentation**:
   - Explain the system in clear prose, with section headings and short lists where they improve scanability.
   - Include Mermaid diagrams only when they clarify architecture, data flow, lifecycle, deployment, or ownership better than prose.
   - Keep each file focused on its canonical topic and link to sibling files instead of duplicating long sections.
5. **Call out uncertainty explicitly**:
   - If a section cannot be verified from the repository, say what is unknown and which files or systems likely hold the answer.
   - Separate verified facts from inference, assumptions, and stale-looking references.

## Canonical Split Documentation Set

Write these files for a full-repository scan:

1. `.planning/codebase/OVERVIEW.md`
   - Project purpose, scope, major capabilities, user-facing workflows, and what is intentionally out of scope.
   - Use this only for human orientation. Do not duplicate detailed stack, architecture, or risk content from the files below.
2. `.planning/codebase/STACK.md`
   - Languages, runtimes, package managers, framework versions, build tools, test tools, lockfiles, and platform requirements.
3. `.planning/codebase/INTEGRATIONS.md`
   - External services, APIs, SDKs, auth providers, webhooks, CI/CD, deployment targets, observability, and environment variable names. Never include secret values.
4. `.planning/codebase/ARCHITECTURE.md`
   - System overview, component responsibilities, layers, primary request/data flows, entry points, architectural constraints, error handling, and cross-cutting concerns.
5. `.planning/codebase/STRUCTURE.md`
   - Directory layout, module responsibilities, key file locations, naming conventions, generated assets, and where to add new code.
6. `.planning/codebase/CONVENTIONS.md`
   - Formatting, linting, import organization, naming, error handling, logging, comments, module design, and workflow conventions visible in the repository.
7. `.planning/codebase/TESTING.md`
   - Test frameworks, run commands, file organization, fixture/mocking patterns, test types, coverage expectations, and common async/error testing patterns.
8. `.planning/codebase/CONCERNS.md`
   - Technical debt, quality risks, fragile areas, missing verification, unclear ownership, duplicated logic, stale references, and recommended follow-up Beads.

For a subsystem scan, write the same filenames below `.planning/codebase/<scope-slug>/`.

## Required File Contents

Every split file must include:

- `Analysis Date`: the current date supplied by the environment or prompt.
- `Scope`: full repository or subsystem path/topic.
- `Evidence`: concrete files inspected, with line numbers when available.
- `Index Use`: whether codegraph or another repository index was used; if not, state that direct inspection was used.
- `Verified Facts`: claims supported by repository evidence.
- `Inference And Uncertainty`: assumptions, missing files, ambiguous ownership, or stale-looking references.
- `Follow-up`: concrete Beads to create when the scan reveals actionable gaps; write "None identified" when there are no follow-ups.

Each file also needs its topic-specific sections:

- `OVERVIEW.md`: capabilities, primary workflows, key entry points, non-goals.
- `STACK.md`: languages, runtime, package manager, frameworks, dependencies, configuration, platform requirements.
- `INTEGRATIONS.md`: APIs and external services, storage, auth, monitoring, deployment, env vars by name only, webhooks.
- `ARCHITECTURE.md`: system overview, component responsibilities, layers, data flow, key abstractions, entry points, constraints, anti-patterns, error handling, cross-cutting concerns.
- `STRUCTURE.md`: directory layout, directory purposes, key file locations, naming conventions, where to add new code, special directories.
- `CONVENTIONS.md`: naming patterns, code style, import organization, error handling, logging, comments, function design, module design.
- `TESTING.md`: runner and commands, test organization, suite structure, mocking, fixtures, coverage, test types, common patterns.
- `CONCERNS.md`: top risks, evidence, impact, recommended remediation, suggested Beads, and confidence.

## Routing For Downstream Agents

Downstream agents should load only the files relevant to their phase:

| Phase Type | Documents To Load |
| --- | --- |
| UI / frontend / components | `CONVENTIONS.md`, `STRUCTURE.md` |
| API / backend / endpoints | `ARCHITECTURE.md`, `CONVENTIONS.md` |
| database / schema / models | `ARCHITECTURE.md`, `STACK.md`, `INTEGRATIONS.md` |
| testing / tests | `TESTING.md`, `CONVENTIONS.md` |
| integration / external API | `INTEGRATIONS.md`, `STACK.md` |
| refactor / cleanup | `CONCERNS.md`, `ARCHITECTURE.md` |
| setup / config | `STACK.md`, `STRUCTURE.md` |
| documentation / onboarding | `OVERVIEW.md`, plus topic-specific files |
| mixed / unclear | `OVERVIEW.md`, `STACK.md`, `ARCHITECTURE.md`, `CONVENTIONS.md` |

These files are durable evidence inputs for planning and implementation. They are not runtime status and must not replace Beads issue state.

## Output Standard

- Prefer explanation over exhaustive enumeration.
- Reference concrete files when making claims, including line numbers when available.
- Separate verified facts from inference, assumptions, and uncertainty.
- Do not present guessed behavior, stale-looking references, or index-only findings as verified facts.
- State whether codegraph or another repository index was used.
- Highlight the top risks instead of burying them in long prose.
- Keep each file focused on its canonical topic. Link to sibling files instead of duplicating long sections.
