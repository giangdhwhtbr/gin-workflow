---
name: progress
description: Report Beads task status, blockers, open waivers, and next ready work without mutating anything.
---

Follow [references/stage-contract.md](../../references/stage-contract.md) (the plugin's shared stage contract).

# Progress

Read-only status report.

1. Query Beads: `bd list --status open,in_progress`, `bd ready`, `bd blocked`, and `bd show <id>` for requested tasks.
2. Group as Pending, Active, Complete, and Failed. Recommend active dependencies first, then ready work by priority, then root blockers.
3. Add review status (`python3 review-ledger.py status --bead-id <id>`) and gate state (`gin-workflow state --format json`) when relevant.
4. Report open gate waivers (gates shown as `waived(<reason>)` by `gin-workflow state`) and check their follow-up tasks with `bd show`, so waivers do not become a habit.
5. Label worker and worktree details as derived runtime metadata, never authoritative state.
6. Return the report. Never mutate state or chain into another stage.
