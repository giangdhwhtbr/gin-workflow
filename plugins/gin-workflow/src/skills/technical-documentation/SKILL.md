---
name: technical-documentation
description: Scan a codebase and write a human-readable technical document covering stack, architecture, storage, structure, conventions, concerns, and quality risks.
---

# Technical Documentation Skill

This skill generates a durable technical document for humans. It is intended for onboarding,
architecture review, planning, and maintenance work, not just a raw file listing.

## Core Flow

1. **Scope the request**:
   - Determine whether the document covers the whole repository or a specific subsystem.
   - If the user provides a feature area or directory, focus the analysis there while still noting key dependencies outside the scope.
2. **Gather codebase evidence**:
   - Use the `codebase-mapper` agent and direct repository inspection to identify modules, entry points, libraries, runtime boundaries, and storage choices.
   - Prefer evidence from the code, lockfiles, configuration, migrations, schema files, and top-level docs.
3. **Write a readable technical document**:
   - Save to `docs/technical/<timestamp>-<scope>.md` unless the user asks for another path.
   - Explain the system in clear prose, with section headings and short lists where they improve scanability.
4. **Call out uncertainty explicitly**:
   - If a section cannot be verified from the repository, say what is unknown and which files or systems likely hold the answer.

## Required Sections

Every generated document should include:

1. **Overview**: what the project or subsystem does.
2. **Tech Stack**: languages, frameworks, build tools, runtime dependencies.
3. **Architecture Design**: major components, boundaries, and interaction paths.
4. **Database or Storage Design**: databases, schemas, persistence patterns, migrations, or file-based storage.
5. **Code Structure**: directories, modules, and responsibility boundaries.
6. **Code Conventions**: naming patterns, workflow conventions, architecture patterns, or testing expectations visible in the repo.
7. **Operational or Cross-Cutting Concerns**: auth, configuration, observability, safety rails, background jobs, deployment assumptions.
8. **Quality Concerns and Risks**: fragile areas, missing verification, unclear ownership, duplicated logic, or unresolved design debt.
9. **Follow-up Work**: recommended Beads to file if the scan reveals actionable gaps.

## Output Standard

- Prefer explanation over exhaustive enumeration.
- Reference concrete files when making claims.
- Separate verified facts from inference.
- Highlight the top risks instead of burying them in long prose.
