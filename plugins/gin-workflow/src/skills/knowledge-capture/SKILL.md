---
name: knowledge-capture
description: Capture codebase discoveries, configuration choices, and design decisions during implementation and write/update them in Obsidian.
---

# Knowledge Capture Skill

Use this skill during the **Implementation** phase when you discover notable codebase quirks, make significant architectural decisions, or find tricky debugging workarounds that future agents should remember.

## Purpose

To ensure that debugging context, runtime tricks, and structural choices made during active development are permanently captured in the Obsidian Second Brain rather than being lost when the active session is closed.

## Guidelines on When to Capture

Only capture high-value, reusable knowledge. Do not document routine implementation steps. Good candidates for capture include:
- Tricky package/version compatibility issues and how they were resolved.
- Custom Docker-compose environments or network configuration details.
- Database indexing or key architectural design decisions (e.g. why a specific pattern was used).
- Unintuitive APIs or library limitations.

## Documenting Decisions & Lessons

When capturing knowledge:
1. **Locate or Create a Note**:
   - If the learning belongs to an existing project module, read the module's MOC under `/indexes/` first.
   - For a general lesson or decision, write a new note under `/decisions/` or `/lessons/` in the Obsidian vault using `write_note`.
2. **Standard Note Layout**:
   Use structured YAML frontmatter:
   ```yaml
   type: decision | lesson
   project: <project-slug>
   tags:
     - decision | lesson-learned
     - module/<module-name>
   created: YYYY-MM-DD
   ```
3. **Draft the Content**:
   Keep it concise. Focus on:
   - **Context**: The situation or problem faced.
   - **Decision/Solution**: What action was taken and why.
   - **Consequences**: Any side-effects, trade-offs, or guidelines for future tasks.
4. **Update MOC Index**:
   Update the parent project/module index to link to this new note using a wikilink (`[[Note Name]]`).
