---
name: progress
description: Report Beads task status, blockers, open waivers, and next ready work without mutating anything.
---

## Before you start
1. If `.agent-workflow/generated/effective-config.yaml` does not exist in the main checkout (the parent of `git rev-parse --path-format=absolute --git-common-dir`; linked worktrees have none), stop: tell the user to run `/setup` once and do nothing else. (`capabilities: {}` is a valid config.)
2. Read [references/stage-contract.md](../../references/stage-contract.md) now: it defines the gate CLI, valid evidence, approval, and git rules this stage relies on.

# Progress

Read-only status report.

1. Query Beads: `bd list --status open,in_progress`, `bd ready`, `bd blocked`, and `bd show <id>` for requested tasks. For a sprint: `bd list --label sprint:<name> --all --json` gives the epics; `bd list --parent <epic> --all --json` gives each one's tracks.
2. Group as Pending, Active, Complete, and Failed. Recommend active dependencies first, then ready work by priority, then root blockers.
3. Add review status (`python3 review-ledger.py status --bead-id <id>`) and gate state (`gin-workflow state --format json`) when relevant, and recent `/quick` runs (`recent_quick` in `gin-workflow state`).
4. Report open gate waivers (gates shown as `waived(<reason>)` by `gin-workflow state`) and check their follow-up tasks with `bd show`, so waivers do not become a habit.
5. Label worker and worktree details as derived runtime metadata, never authoritative state.
6. Return the report. Never mutate state or chain into another stage.
