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
   - Use the `knowledge-capture` skill to record any notable codebase discoveries, environment workarounds, or architectural decisions in the Obsidian vault.
   - If changes outside these files are needed, use `telegram-notify` to send a `work_blocked` notification before stopping and notifying the orchestrator.
3. **Verification & Testing**:
   - Run the relevant unit tests or checks to verify the change meets the acceptance criteria.
   - If tests fail, iterate and fix issues locally.
4. **Review & Triage**:
   - If the bead is in `changes-requested` state, the worker must route its flow through the `receiving-code-review` skill to resolve all findings.
   - Halt execution if the ledger enters `blocked-human` state or if a `WorkflowIntegrityError` is encountered, and notify the orchestrator or user.
5. **Completion**:
   - Prior to closure, validate that the review is approved: `python3 review-ledger.py status --bead-id <track-id>`. Ensure "Unresolved Findings: 0" and "State: review-approved".
   - Follow [verification-and-handoff-workflow.md](file://../../references/verification-and-handoff-workflow.md) before treating the bead as complete.
   - Use the `knowledge-reconciliation` skill to update story status, link commit history, and regenerate MOC indexes in Obsidian.
   - Use `telegram-notify` to send a `task_completed` notification after verification passes.
   - Write Beads outcome notes plus a handoff summary that covers changes, validation, and any follow-up work.
   - Run `git status` before closure and include the changed-file state in the handoff.
   - Close the bead only after acceptance criteria, validation, Beads notes, `git status`, review approval, and handoff evidence are complete.
   - If validation fails, there are unresolved findings, or the handoff is incomplete, leave the bead in progress or mark it blocked with notes instead of closing it.
