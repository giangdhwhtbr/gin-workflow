---
name: tech-doc
description: Scan the codebase and write a human-readable technical document covering stack, architecture, structure, conventions, and risks.
---

# /tech-doc Command

Generate a technical document for the current project, or for a scoped directory/feature area,
that a human can use for onboarding, architecture review, planning, or code quality work.

## Instructions

1. Use the `technical-documentation` skill.
2. Dispatch the `codebase-mapper` specialist agent (see [codebase-mapper.md](file://../agents/codebase-mapper.md)) to gather the relevant codebase evidence.
3. Pass along any scope hint the user supplied, such as a directory, subsystem, feature area, or specific question.
4. Write the resulting document to `docs/technical/<timestamp>-<scope>.md` unless the user specifies another path.
