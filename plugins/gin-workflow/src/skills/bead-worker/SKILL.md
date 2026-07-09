---
name: bead-worker
description: Handles execution, implementation, validation, and reporting for a single assigned bead (task track).
---

# Bead Worker Skill

This skill guides a specialized subagent or local worker executing a single bead.

## Execution Rules

1. **Bead Startup**:
   - Read the assigned bead's metadata from `bd show <track-id> --json` (status, dependencies, description, acceptance criteria).
   - Read the bead's in-scope files from the plan file under `.planning/plans/` — match the track by its title/id and use the `Files:` / file list declared there. (`bd` issues have no `files` field, so the authoritative file scope comes from the plan, not `bd show`.)
   - Update its state via the `bd` CLI (e.g. `bd update <track-id> --status in_progress`, or `bd update <track-id> --claim`) and set the `worker_agent` identifier if applicable.
   - Treat any worker-local branch or worktree metadata as supplemental only; it does not replace the bead status.
2. **Implementation**:
   - Limit file edits strictly to the in-scope files read from the plan in step 1.
   - If changes outside these files are needed, stop and notify the orchestrator.
3. **Verification & Testing**:
   - Run the relevant unit tests or checks to verify the change meets the acceptance criteria.
   - If tests fail, iterate and fix issues locally.
4. **Completion**:
   - Write a summary of changes, diff metrics, and test outputs.
   - Transition the status of the bead using the `bd` CLI (e.g. `bd update <track-id> --status closed` or `bd close <track-id>`).
