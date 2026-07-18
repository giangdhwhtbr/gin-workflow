---
name: knowledge-reconciliation
description: Close the knowledge loop by updating story notes, linking commit history, and regenerating MOC indexes in Obsidian at task completion.
---

# Knowledge Reconciliation Skill

Use this skill during the **Ship** phase, immediately after verification has succeeded and prior to closing the task in Beads.

This skill ensures that all changes and story completions are correctly recorded in the Obsidian Second Brain, closing the loop between active task execution and long-term knowledge.

## Purpose

To keep the Second Brain's documentation and MOC (Map of Content) indexes accurate, matching the current codebase reality, and ensuring that no stale status remains in our vault notes.

## Execution Steps

1. **Update User Story Status**:
   - Locate the User Story note for the completed task (e.g. `stories/Qwikfone Office 3.0/US_RM23.md`).
   - Use `update_frontmatter` to change its status:
     ```yaml
     status: "completed"
     ```
   - Append a brief completion summary under a `## Completion Summary` heading, listing key changes, relevant pull requests, and commit hashes.

2. **Reconcile Contradictions**:
   - If the implementation required modifying existing APIs or architecture rules, check all related notes (including the parent project index) for conflicting information.
   - Edit the outdated notes using `patch_note` or overwrite them to reflect the updated codebase design. Do not leave stale instructions in the vault.

3. **Update Map of Content (MOC) Indexes**:
   - Open the Project or Module index note under `/indexes/` that maps these stories (e.g. `indexes/_Index - Project - QFO Revamp.md`).
   - Find the story table and update its status cell from `-` or `in-progress` to `completed` or `[x]`.
   - Run any background sync or index generation scripts if available in the repository.

4. **Confirm Handoff**:
   Only after the Obsidian Second Brain is fully updated and reconciled should you proceed to run `bd close` to close out the task in Beads.
