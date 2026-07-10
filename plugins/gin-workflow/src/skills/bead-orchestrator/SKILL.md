---
name: bead-orchestrator
description: Parses plans, manages dependency-aware execution, dispatches workers, and tracks durable status via Beads.
---

# Bead Orchestrator Skill

This skill governs the central coordination of development plans. It manages dependency-aware execution of tasks using Beads as the durable workflow state.

State ownership is defined in [orchestration-state-model.md](file://../../references/orchestration-state-model.md).

## Core Flow

1. **Plan Discovery**: Locate the latest plan under `.planning/plans/` or the path passed via `--plan`.
2. **Beads Initialization**:
   - Parse the plan markdown file.
   - For each track defined under the `## Tasks` section, create a bead using `bd create` (e.g., `bd create "Track Title" -t task`).
   - Capture any mapping between a plan track-id and a bead id in a way that is disposable and reproducible from the plan plus Beads. Do not treat a local runtime file as the authoritative execution state.
   - Use `bd dep add <issue-id> <depends-on-id>` to configure dependencies between tracks if specified in the plan (both IDs are the bd issue IDs returned by `bd create`).
3. **Agent Injection (optional)**:
   - If `--inject-agents-md` is specified, copy the specialist agent definitions from the plugin's `agents/` directory (such as `agent-researcher.md`, `code-reviewer.md`, `codebase-mapper.md`) into the project's local agent directory (e.g. `.claude/agents/` for Claude Code or `.agents/agents/` for Antigravity) before dispatching any workers.
4. **Execution Loop**:
   - Use `bd ready --json` to identify work items that have no blocking dependencies.
   - Dispatch workers for these beads (up to the limit specified by `--max-tracks`).
   - Mark a bead active via `bd update <issue-id> --status in_progress` (or `bd update <issue-id> --claim` to atomically assign + set in_progress).
5. **Integration**:
   - When a worker finishes successfully, treat the bead as ready for integration and close-out review, not ready for immediate closure.
   - If worktree isolation is active, perform safety checks and merge the worktree branch into the integration branch before final closure.
   - Follow [verification-and-handoff-workflow.md](file://../../references/verification-and-handoff-workflow.md) before running `bd close <issue-id>`.
   - Close the bead only after integration work is complete when in scope, verification evidence exists, Beads outcome notes are recorded, `git status` has been reviewed, follow-up work is captured, and handoff evidence is complete.
   - If integration or verification fails, or the handoff is incomplete, leave the bead active or mark it blocked with notes instead of closing it.
6. **Runtime Metadata**:
   - Any local cache for active workers, branch names, or worktree paths must be disposable and reconstructible.
   - Beads remains the source of truth for status, ownership, readiness, dependencies, blockers, and closure.
