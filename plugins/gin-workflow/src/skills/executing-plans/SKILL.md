---
name: executing-plans
description: Instructions and guidelines for executing a plan directly without a full multi-track orchestrator.
---

# Executing Plans Skill

This skill provides step-by-step guidance on how to execute a plan sequentially, ensuring progress is tracked, changes are localized, and outcomes are verified.

## Execution Rules

1. Always read the plan file at the start of implementation to understand the scope and objectives.
2. Select a single track or task to work on. Update the Bead status using the standard `bd` CLI commands (e.g. `bd update <id> --status in_progress` to start, `bd update <id> --status closed` or `bd close <id>` to finish) or update the corresponding plan status in the plan file.
3. Keep changes minimal and focused strictly on the files in scope.
4. Perform local validation/testing immediately after implementing a track's changes.
5. Do not proceed to the next track if the current track has failing tests or does not meet the acceptance criteria.
