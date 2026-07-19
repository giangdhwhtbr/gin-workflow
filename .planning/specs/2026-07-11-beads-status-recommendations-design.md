# Design Specification: beads-status next-task recommendations

This document specifies the implementation of next-task recommendations within the `/beads-status` command and the `beads-status` skill.

## Objective

Update the `/beads-status` command output to include a "Next Task Recommendations" section. This will assist developers by identifying the most logical next steps based on current task states, parent-child relationships (e.g., active epics with ready children), priority, and blocker graphs.

## Proposed Logic (Approach 1: Hierarchical Dependency-Aware)

The recommendation engine follows these rules to suggest the next tasks:

1. **Active Tasks & Dependencies (High Priority)**:
   - Identify all active tasks (status: `in_progress`).
   - For each active task:
     - Check if it has any uncompleted child tasks or dependencies.
     - If it does, find those that are in `open` state and are **ready to work** (appear in `bd ready` / have satisfied dependencies).
     - Recommend these ready child/dependency tasks first to ensure the active epic/parent task can progress.
       - *Format*: `[Ready Child] <child_id>: <title> (required to progress active parent <parent_id>)`
     - If the active task has no unresolved dependencies or children, recommend continuing work on it.
       - *Format*: `[Active] <id>: <title> (Continue current work)`

2. **Unclaimed Ready Tasks**:
   - If there are no active tasks, or after listing active tasks/dependencies:
   - Recommend the highest-priority `ready` tasks (from `bd ready`) that are not already claimed, sorted by priority (P0 to P4).
     - *Format*: `[Ready] <id>: <title> (Priority: <priority>)`

3. **Root Blockers (Fallback)**:
   - If all open tasks are blocked (no active or ready tasks):
   - Traverse the dependency graph to find root blocking tasks (tasks that block others but are themselves waiting on completed/closed tasks or are the root of a block).
     - *Format*: `[Root Blocker] <id>: <title> (unblocks <dependent_id>)`

4. **Empty Queue**:
   - If there are no open tasks, recommend running `/plan` to start new work or finishing/shipping the current branch.

## Proposed Changes

We will modify the following files:
1. `plugins/gin-workflow/src/skills/beads-status/SKILL.md`: Update the Execution Rules to specify how the recommendation section is gathered, computed, and structured.
2. `plugins/gin-workflow/src/commands/beads-status.md`: Update instructions to explicitly mention retrieving recommendations.
3. `plugins/gin-workflow/src/references/orchestration-state-model.md`: Document the next-task recommendation section as part of the state model.

## Verification Plan

### Automated/Unit Tests
- Verify that running the installer registers the updated skills and commands.

### Manual Verification
- Simulate various Beads states (active tasks, active epic with ready children, no active tasks but ready tasks, blocked tasks only, empty queue).
- Run the updated `/beads-status` command and verify that the generated recommendations match the expected output.
