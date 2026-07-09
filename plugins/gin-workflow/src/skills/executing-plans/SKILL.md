---
name: executing-plans
description: Instructions and guidelines for executing a plan directly without a full multi-track orchestrator.
---

# Executing Plans Skill

This skill provides step-by-step guidance on how to execute a plan sequentially, ensuring progress is tracked, changes are localized, and outcomes are verified.

## Execution Rules

1. Always read the plan file at the start of implementation to understand the scope and objectives.
2. Select a single track or task to work on. Update the Bead status using the standard `bd` CLI commands (e.g. `bd update <id> --status in_progress` to start or `bd update <id> --claim` when ownership needs to be established).
3. Treat the plan as approved scope and validation intent, not as a status ledger.
4. Keep changes minimal and focused strictly on the files in scope.
5. Perform local validation/testing immediately after implementing a track's changes.
6. Before treating a track as complete or running `bd close`, follow [docs/verification-and-handoff-workflow.md](file://../../../../docs/verification-and-handoff-workflow.md). Validation success alone is not enough without Beads outcome notes, `git status`, and explicit handoff evidence.
7. Do not proceed to the next track if the current track has failing tests, does not meet the acceptance criteria, or still lacks required close-out evidence.
8. If validation fails or close-out evidence is incomplete, leave the bead in progress or mark it blocked with notes instead of closing it.
