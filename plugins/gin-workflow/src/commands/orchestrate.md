---
name: orchestrate
description: Execute a plan through parallel tracked work items using subagents.
---

# /orchestrate Command

Orchestrate the execution of a development plan using Beads-backed tracked work items and optional parallel subagents.

State ownership is defined in [orchestration-state-model.md](file://../references/orchestration-state-model.md).

## Usage

```bash
/orchestrate [--plan <path>] [--worktree|--no-worktree] [--max-tracks <N>] [--integration-branch <name>] [--inject-agents-md]
```

## Options

- `--plan <path>`: Path to a specific plan markdown file. Defaults to the latest file in `.planning/plans/`.
- `--worktree` / `--no-worktree`: Enable or disable Git worktree isolation. Defaults to `--worktree`.
- `--max-tracks <N>`: Maximum parallel execution tracks (default: `4`).
- `--integration-branch <name>`: Integration branch to merge changes into.
- `--inject-agents-md`: Inject agent instructions pre-flight.

## Instructions

1. Use the `bead-orchestrator` skill to coordinate and manage execution.
2. Treat Beads as the durable source of truth for track status, ownership, dependencies, readiness, blockers, and closure.
3. Use `.planning/plans/` as the approved plan/spec input for decomposition, scope, and validation intent.
4. Mirror plan dependencies into Beads with `bd dep add` so Beads, not local runtime files, determines readiness.
5. If temporary runtime metadata is needed for active workers or worktrees, keep it disposable and reconstructible from Beads plus the approved plan.
