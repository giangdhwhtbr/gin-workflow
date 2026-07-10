---
name: executing-plans
description: Extends superpowers:executing-plans with Beads-backed status tracking, scoped file constraints, and explicit close-out checks.
---

# Executing Plans Skill

This skill extends `superpowers:executing-plans` for the `gin-workflow` plugin.

## Base Skill

When `superpowers:executing-plans` is available, use it first as the base contract. Then apply the Gin Workflow overlay below.

If `superpowers:executing-plans` is unavailable, continue with this skill's self-contained rules and say that the Superpowers base skill could not be loaded.

## Gin Workflow Overlay

Gin Workflow keeps the Superpowers standards, with these plugin-specific overrides:

1. Update the bead status using the standard `bd` CLI commands (e.g. `bd update <id> --status in_progress` to start or `bd update <id> --claim` when ownership needs to be established) rather than simple checkbox edits in plans.
2. Treat the plan files under `.planning/plans/` as approved scope and validation intent, not as the status ledger.
3. Keep changes minimal and focused strictly on the files in scope.
4. Perform local validation/testing immediately after implementing a track's changes.
5. Before treating a track as complete or running `bd close`, follow [verification-and-handoff-workflow.md](file://../../references/verification-and-handoff-workflow.md). Validation success alone is not enough without Beads outcome notes, `git status`, and explicit handoff evidence.
6. Do not proceed to the next track if the current track has failing tests, does not meet the acceptance criteria, or still lacks required close-out evidence.
7. If validation fails or close-out evidence is incomplete, leave the bead in progress or mark it blocked with notes instead of closing it.
