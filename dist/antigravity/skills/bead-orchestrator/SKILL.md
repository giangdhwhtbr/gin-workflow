---
name: bead-orchestrator
description: Parses plans, manages the track execution state, dispatches workers, and tracks status via local beads files.
---

# Bead Orchestrator Skill

This skill governs the central coordination of development plans. It manages dependency-aware execution of tasks using file-based beads.

## Core Flow

1. **Plan Discovery**: Locate the latest plan under `.planning/plans/` or the path passed via `--plan`.
2. **Beads Initialization**:
   - Parse the plan markdown file.
   - For each track defined under the `## Tasks` section, create a bead using `bd create` (e.g., `bd create "Track Title" -t task`). `bd create` prints the new issue's ID (e.g. `bd-7`) — capture it and record the mapping from the plan's `<track-id>` to this bd issue ID in `.planning/orchestration-state.json`, since later commands take the bd issue ID, not the plan track-id.
   - Use `bd dep add <issue-id> <depends-on-id>` to configure dependencies between tracks if specified in the plan (both IDs are the bd issue IDs returned by `bd create`).
3. **Agent Injection (optional)**:
   - If `--inject-agents-md` is specified, copy the specialist agent definitions from the plugin's `agents/` directory (such as `agent-researcher.md`, `code-reviewer.md`, `codebase-mapper.md`) into the project's local agent directory (e.g. `.claude/agents/` for Claude Code or `.agents/agents/` for Antigravity) before dispatching any workers.
4. **Execution Loop**:
   - Use `bd ready --json` to identify work items that have no blocking dependencies.
   - Dispatch workers for these beads (up to the limit specified by `--max-tracks`).
   - Mark a bead active via `bd update <issue-id> --status in_progress` (or `bd update <issue-id> --claim` to atomically assign + set in_progress).
5. **Integration**:
   - When a worker finishes a bead successfully, close it via `bd close <issue-id>` (equivalently `bd update <issue-id> --status closed`).
   - If worktree isolation is active, perform safety checks and merge the worktree branch into the integration branch.
6. **State File**:
   - Maintain a master execution state at `.planning/orchestration-state.json` containing the overall progress, target branch, and list of active workers.
