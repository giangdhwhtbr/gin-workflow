# Plan: Beads Project Naming Improvement

## Objective
Improve Beads project detection and naming in `gin-workflow` to seamlessly support normal repositories, monorepos, Git submodules, and nested repositories. Specifically, automatically resolve the default project name to the nearest project boundary (derived from `.git` or `.beads` parents) using `kebab-case`, execute all `bd` commands in the resolved boundary context, and dynamically aggregate progress summaries at the parent level in monorepos by dispatching subagents to nested submodules.

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
- `override_rule`: Use `high_reasoning` for implementation of the multi-repo subagent dispatching logic due to concurrency and context parsing complexity.

## Requirement Analysis
- Problem statement: The default project name/prefix for Beads is generated from the current active directory name. If initialized or executed from a subdirectory (like `backend/src`), it defaults to `src`, mixing contexts. In monorepos where multiple submodules or nested repositories exist under one parent directory, running beads at the parent level mixes unrelated project scopes.
- Success criteria:
  - `bd init` naming defaults to the nearest repository/submodule boundary (containing `.git` or `.beads`) converted to `kebab-case`.
  - All command execution and state-tracking skills (`beads`, `bead-orchestrator`, `bead-worker`, `executing-plans`, `progress`) automatically resolve and execute commands relative to the nearest Project Boundary Root (containing `.beads` or `.git`) of the active files/context.
  - In a parent/monorepo directory containing multiple sub-projects, running `/progress` automatically dispatches subagents to query progress in each sub-project and displays a combined parent-level summary report.
- Constraints:
  - Submodules/sub-projects are defined as directories containing either a `.git` file/folder or a `.beads` folder.
  - Prefix generation must sanitize directories to kebab-case (lowercase, alphanumeric characters and dashes only).
  - State must still be queried via the `bd` CLI (never by direct Dolt SQL or JSON parsing of private structures).
- Non-goals: Changing the compiled binary `/home/linuxbrew/.linuxbrew/bin/bd` itself. All improvements must be done via plugin configuration, skills, and command wrappers.

## Approach Options
### Option 1: Nearest Git/Beads Root boundary detection with Subagent-driven Aggregation (Selected)
- Summary: Traverse up from CWD/file path to find the first directory containing `.beads` or `.git`. This is the Project Boundary Root. Convert the directory name to kebab-case for the default prefix. In `/progress`, if CWD is a parent folder containing multiple project boundaries, query each submodule via a subagent and combine findings.
- Pros: Zero-config, aligns perfectly with Git conventions, scales dynamically to monorepos and submodules.
- Cons: Requires clean subagent execution logic and text parsing.

---

## Scope
- In scope:
  - `plugins/gin-workflow/src/skills/beads/SKILL.md`
  - `plugins/gin-workflow/src/skills/progress/SKILL.md`
  - `plugins/gin-workflow/src/skills/bead-orchestrator/SKILL.md`
  - `plugins/gin-workflow/src/skills/bead-worker/SKILL.md`
  - `plugins/gin-workflow/src/skills/executing-plans/SKILL.md`
  - `plugins/gin-workflow/src/commands/progress.md`
- Out of scope: Custom modifications to the `bd` CLI binary.

---

## Tasks

### Track 1: Update Beads Skill for Boundary Detection and Kebab-case Naming
- **Dependencies**: none
- **Files**:
  - [MODIFY] [beads/SKILL.md](file:///home/gin/gin-workflow/plugins/gin-workflow/src/skills/beads/SKILL.md)
- **Model class**: `standard_impl`
- **Acceptance criteria**:
  - `beads/SKILL.md` contains clear guidelines for finding the active Project Boundary Root (the first parent containing `.git` or `.beads`).
  - Instructs how to initialize new projects at the Project Boundary Root, passing a sanitized, kebab-case project prefix via `--prefix`.
- **Estimated complexity**: low

### Track 2: Update Orchestrator, Worker, and Executing-Plans Skills for Context-Aware Execution
- **Dependencies**: Track 1
- **Files**:
  - [MODIFY] [bead-orchestrator/SKILL.md](file:///home/gin/gin-workflow/plugins/gin-workflow/src/skills/bead-orchestrator/SKILL.md)
  - [MODIFY] [bead-worker/SKILL.md](file:///home/gin/gin-workflow/plugins/gin-workflow/src/skills/bead-worker/SKILL.md)
  - [MODIFY] [executing-plans/SKILL.md](file:///home/gin/gin-workflow/plugins/gin-workflow/src/skills/executing-plans/SKILL.md)
- **Model class**: `standard_impl`
- **Acceptance criteria**:
  - Skills explicitly mandate finding the nearest Project Boundary Root of the active file or plan before running any `bd` command.
  - `bd` commands are executed inside the resolved boundary directory using the `Cwd` field of the run tool or `-C <path>`.
- **Estimated complexity**: low

### Track 3: Implement Parent-level /progress Aggregation and Kebab-case references
- **Dependencies**: Track 1
- **Files**:
  - [MODIFY] [progress.md](file:///home/gin/gin-workflow/plugins/gin-workflow/src/commands/progress.md)
  - [MODIFY] [progress/SKILL.md](file:///home/gin/gin-workflow/plugins/gin-workflow/src/skills/progress/SKILL.md)
- **Model class**: `high_reasoning`
- **Acceptance criteria**:
  - `progress/SKILL.md` contains the algorithm for parent-level monorepo progress aggregation:
    1. Scan immediate subdirectories for `.git` or `.beads` boundaries.
    2. If multiple sub-projects are found, dispatch a `research` subagent to run `/progress` in each submodule directory.
    3. Aggregate the reports into a combined summary highlighting each sub-project's status and next steps.
  - Specifies prefix naming formatting rules (forcing conversion to kebab-case).
  - `progress.md` command description is updated to reflect this aggregate progress capability.
- **Estimated complexity**: medium

---

## Integration
- **Branch**: `feat/beads-project-naming-improvement`
- **Merge strategy**: sequential

---

## Validation
- [ ] Verify that all modified markdown instruction files render correctly and match the schema.
- [ ] Run a simulated verification of project boundary lookup from a subdirectory.
- [ ] Verify that parent monorepo subagent dispatch logic is explicitly and clearly defined.
