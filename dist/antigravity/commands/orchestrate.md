---
name: orchestrate
description: Execute a plan through parallel tracked work items using subagents.
---

# /orchestrate Command

Orchestrate the execution of a development plan using parallel subagents and file-based task tracking.

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
2. Maintain orchestration status under `.planning/orchestration-state.json`.
