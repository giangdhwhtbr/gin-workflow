---
name: tech-doc
description: Scan the codebase and write mapper-style split technical documentation covering stack, integrations, architecture, structure, conventions, testing, and risks.
---

# /tech-doc Command

Generate technical documentation for the current project, or for a scoped directory/feature area, that a human and downstream agents can use for onboarding, architecture review, planning, research, or code quality work.

## Instructions

1. Use the `technical-documentation` skill.
2. Confirm the target path only when the user request, Beads task, approved plan, or handoff context does not already authorize it.
3. Default to split documentation under `.planning/codebase/` for full-repository scans.
4. For scoped scans, default to `.planning/codebase/<scope-slug>/` and use the same canonical filenames.
5. Use a single combined document only when the user explicitly requests one or the approved plan authorizes a different target.
6. Gather concrete evidence with existing mapper findings, the `codebase-mapper` specialist agent (see [codebase-mapper.md](file://../agents/codebase-mapper.md)), or direct repository inspection.
7. Prefer codegraph or equivalent index tools when exposed, but verify claims against concrete files and fall back to direct inspection when no index is available.
8. Pass along any scope hint the user supplied, such as a directory, subsystem, feature area, or specific question.
9. Write the canonical documentation set when relevant:
   - `OVERVIEW.md`
   - `STACK.md`
   - `INTEGRATIONS.md`
   - `ARCHITECTURE.md`
   - `STRUCTURE.md`
   - `CONVENTIONS.md`
   - `TESTING.md`
   - `CONCERNS.md`
10. Include Mermaid diagrams only where they clarify structure or flow, and label uncertainty, inference, or missing evidence explicitly.
11. Treat generated documentation as durable planning evidence. Do not use it as task status; Beads remains the source of truth for readiness, blockers, ownership, and closure.
