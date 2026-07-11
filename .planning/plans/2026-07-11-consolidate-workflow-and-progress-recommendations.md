# Plan: Consolidate Workflow and Implement Progress Recommendations

## Objective
Streamline the `gin-workflow` plugin by eliminating duplicate commands/skills (e.g., discover/discuss and beads-status/progress), renaming skills to match command names exactly, and introducing hierarchical dependency-aware next-task recommendations into the `/progress` command.

## Model Guidance
- `default_model_class`: `standard_impl`
- `phase_guidance`:
  - `brainstorm`: `high_reasoning`
  - `design`: `high_reasoning`
  - `plan`: `standard_impl`
  - `implement`: `standard_impl`
  - `verify`: `standard_impl`
  - `review`: `high_reasoning`
  - `docs`: `cheap_simple`
- `override_rule`: Use `high_reasoning` for planning only when execution boundaries, dependency sequencing, or major tradeoffs are still unresolved.

## Requirement Analysis
- Problem statement: The plugin contains duplicate entry points (`discover` as alias of `discuss`, and both `/progress` and `/beads-status` status interfaces). Additionally, wrapper skill names do not match their corresponding commands, leading to confusion. Finally, the status command lacks next-task recommendations, particularly handling parent-child tasks/epics with ready children.
- Success criteria:
  - `/discover` command and `discover` skill are completely removed.
  - `/beads-status` command and `beads-status` skill are removed.
  - `/progress` command and a new `progress` skill are the single status interface.
  - The `progress` skill outputs next-task recommendations using hierarchical dependency-aware logic.
  - Wrapper skills are renamed to exactly match their command names (`plan`, `orchestrate`, `execute`, `verify`, `ship`, `tech-doc`).
  - README.md, install.sh, and reference documents are fully updated.
  - The plugin builds, installs, and runs successfully on Antigravity.
- Constraints: Maintain pure-`bd` CLI as the source of truth for task state; do not read planning/runtime JSON directly.
- Non-goals: Do not alter the core functionality of Beads or the behavior of generic `superpowers` skills.

## Approach Options
### Option 1: Hierarchical Dependency-Aware Next-Task Recommendations (Selected)
- Summary: Trace active tasks (`in_progress`). For each, check if it has open/ready children or dependencies (using `bd list` or `bd show`). Recommend these ready children first. If no active task dependencies exist, recommend unclaimed ready tasks (P0-P4). If all tasks are blocked, recommend root blockers. If empty, suggest `/plan`.
- Pros: Keeps developer focused on current active epics/tasks and resolves blockers efficiently.
- Cons: Slightly more complex traversal logic.

## Scope
- In scope: Modifying `plugins/gin-workflow/src/commands/` and `plugins/gin-workflow/src/skills/`, updating `README.md`, `install.sh`, and `orchestration-state-model.md`.
- Out of scope: Changing any generic `superpowers` base skills or the `bd` CLI tool itself.

## Tasks
### Track 1: Cleanup discover and discuss redundant commands/skills
- **Dependencies**: none
- **Files**:
  - [DELETE] `plugins/gin-workflow/src/commands/discover.md`
  - [DELETE] `plugins/gin-workflow/src/skills/discover/SKILL.md`
  - [MODIFY] `plugins/gin-workflow/src/commands/discuss.md`
  - [MODIFY] `plugins/gin-workflow/src/skills/discuss/SKILL.md`
- **Model class**: `standard_impl`
- **Acceptance criteria**:
  - The `discover` command and skill are deleted.
  - The `discuss` command and skill are updated to remove any alias/discover references.
- **Estimated complexity**: low

### Track 2: Consolidate progress status and implement next-task recommendations
- **Dependencies**: none
- **Files**:
  - [DELETE] `plugins/gin-workflow/src/commands/beads-status.md`
  - [DELETE] `plugins/gin-workflow/src/skills/beads-status/SKILL.md`
  - [MODIFY] `plugins/gin-workflow/src/commands/progress.md`
  - [NEW] `plugins/gin-workflow/src/skills/progress/SKILL.md`
- **Model class**: `standard_impl`
- **Acceptance criteria**:
  - `beads-status` command and skill are deleted.
  - `progress` command points to the new `progress` skill.
  - `progress` skill implements pure-`bd` status tracking plus hierarchical dependency-aware next-task recommendations (tracing active tasks' ready dependencies first, then other ready tasks, then root blockers).
- **Estimated complexity**: medium

### Track 3: Align Wrapper Skill Names with Commands
- **Dependencies**: none
- **Files**:
  - [DELETE] `plugins/gin-workflow/src/skills/create-plan/SKILL.md`
  - [NEW] `plugins/gin-workflow/src/skills/plan/SKILL.md`
  - [DELETE] `plugins/gin-workflow/src/skills/orchestrate-work/SKILL.md`
  - [NEW] `plugins/gin-workflow/src/skills/orchestrate/SKILL.md`
  - [DELETE] `plugins/gin-workflow/src/skills/implement-work/SKILL.md`
  - [NEW] `plugins/gin-workflow/src/skills/execute/SKILL.md`
  - [DELETE] `plugins/gin-workflow/src/skills/verify-work/SKILL.md`
  - [NEW] `plugins/gin-workflow/src/skills/verify/SKILL.md`
  - [DELETE] `plugins/gin-workflow/src/skills/ship-work/SKILL.md`
  - [NEW] `plugins/gin-workflow/src/skills/ship/SKILL.md`
  - [DELETE] `plugins/gin-workflow/src/skills/technical-documentation/SKILL.md`
  - [NEW] `plugins/gin-workflow/src/skills/tech-doc/SKILL.md`
  - [MODIFY] `plugins/gin-workflow/src/commands/plan.md`
  - [MODIFY] `plugins/gin-workflow/src/commands/orchestrate.md`
  - [MODIFY] `plugins/gin-workflow/src/commands/execute.md`
  - [MODIFY] `plugins/gin-workflow/src/commands/verify.md`
  - [MODIFY] `plugins/gin-workflow/src/commands/ship.md`
  - [MODIFY] `plugins/gin-workflow/src/commands/tech-doc.md`
- **Model class**: `standard_impl`
- **Acceptance criteria**:
  - Wrapper skills renamed to match commands.
  - Command markdown instructions updated to reference correct renamed skill names.
- **Estimated complexity**: low

### Track 4: Update Documentation, Installer, and State Model References
- **Dependencies**: Track 1, Track 2, Track 3
- **Files**:
  - [MODIFY] `README.md`
  - [MODIFY] `install.sh`
  - [MODIFY] `plugins/gin-workflow/src/references/orchestration-state-model.md`
- **Model class**: `standard_impl`
- **Acceptance criteria**:
  - `README.md` documents the consolidated list of commands and skills.
  - `install.sh` builds and installs successfully with no broken references.
  - `orchestration-state-model.md` replaces `beads-status` references with `progress` and documents the recommendation behavior.
- **Estimated complexity**: low

## Integration
- **Branch**: master
- **Merge strategy**: sequential

## Validation
- [ ] All tests pass
- [ ] Type checks clean
- [ ] Manual verification of the installer run
- [ ] Verify that `/progress` displays status and recommendations correctly for various simulated Beads states.
