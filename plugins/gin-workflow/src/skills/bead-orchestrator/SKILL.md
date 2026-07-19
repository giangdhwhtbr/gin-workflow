---
name: bead-orchestrator
description: Parses approved plans, creates dependency-aware Beads execution state, dispatches workers, and tracks durable status automatically.
---

# Bead Orchestrator Skill

This skill governs the central coordination of development plans. It manages dependency-aware execution of tasks using Beads as the durable workflow state.

State ownership is defined in [orchestration-state-model.md](file://../../references/orchestration-state-model.md).

## Core Flow

1. **Plan Discovery**:
   - Locate the latest approved plan under `.planning/plans/` or the path passed via `--plan`.
2. **Beads Initialization**:
   - Parse the plan markdown file.
   - For each track defined under the plan task section, create a bead using `bd create`.
   - Capture any mapping between a plan track-id and a bead id in a way that is disposable and reproducible from the plan plus Beads.
   - Use `bd dep add` to configure dependencies between tracks.
   - Perform any needed claim or status initialization internally; do not require the user to run manual `bd` commands.
3. **Agent Injection (optional)**:
   - If `--inject-agents-md` is specified, copy specialist agent definitions into the local agent directory before dispatching any workers.
4. **Execution Preparation**:
   - Use Beads dependency state to identify ready work.
   - Dispatch workers for ready beads up to the configured parallelism limit.
   - Mark active work internally through the `bd` CLI when ownership or in-progress state must be recorded.
5. **Integration And Close-out**:
   - When a worker finishes successfully, treat the bead as ready for integration and close-out review.
   - Dispatch the code-reviewer agent using `python3 review-ledger.py start-review --bead-id <bead-id>` to run findings checks.
   - Follow [verification-and-handoff-workflow.md](file://../../references/verification-and-handoff-workflow.md) and run the `knowledge-reconciliation` skill to reconcile Obsidian.
   - Close beads only after verification evidence (replaying ledger, confirming active approval event, tree hash matching, review.md check), Beads notes, `git status`, follow-up capture, and handoff evidence are complete.
   - When all beads are closed, use `telegram-notify` to send an `all_work_complete` notification.
6. **Runtime Metadata**:
   - Any local cache for active workers, branch names, or worktree paths must be disposable and reconstructible.
   - Beads remains the source of truth for status, ownership, readiness, dependencies, blockers, and closure.
