# Workflow Audit - 2026-07-08

This audit documents the current workflow surfaces in `gin-workflow` and identifies where the agent task lifecycle is duplicated, ambiguous, or inconsistent with Beads as the durable source of truth.

## Scope

Reviewed surfaces:

- Root docs and instructions: `README.md`, `AGENTS.md`, `CLAUDE.md`, `Plan.md`, `review.md`
- Plugin commands: `plugins/gin-workflow/src/commands/*.md`
- Plugin skills: `plugins/gin-workflow/src/skills/**/*.md`
- Hooks and scripts: `plugins/gin-workflow/src/hooks/hooks.json`, `plugins/gin-workflow/src/scripts/*.sh`

## Lifecycle Entry Points

The current workflow is entered through multiple overlapping surfaces:

| Surface | Intended role | Current lifecycle claim |
| --- | --- | --- |
| `README.md` | User-facing plugin overview | Presents `/plan`, `/orchestrate`, `/execute`, `/verify`, `/ship`, `/progress`, `/beads-status`, `/tech-doc` as the primary workflow |
| `AGENTS.md` | Repo-wide agent rules | Declares Beads as required task tracking, `bd prime` as first-step context recovery, and a mandatory session close protocol |
| `CLAUDE.md` | Secondary agent rules | Repeats the Beads workflow and conservative handoff policy |
| `plugins/gin-workflow/src/commands/plan.md` | Planning entry point | Creates a git-tracked implementation plan in `.planning/plans/` |
| `plugins/gin-workflow/src/commands/orchestrate.md` | Execution coordinator | Says orchestration uses parallel tracked work items and stores state in `.planning/orchestration-state.json` |
| `plugins/gin-workflow/src/commands/execute.md` | Direct execution path | Allows task execution directly from a plan or task list |
| `plugins/gin-workflow/src/commands/verify.md` | Verification entry point | Runs validation before completion |
| `plugins/gin-workflow/src/commands/ship.md` | Completion entry point | Merges branches and cleans up worktrees, discovering state from `.planning/` |
| `plugins/gin-workflow/src/commands/progress.md` | Status entry point | Reads both `bd` state and `.planning/orchestration-state.json` |
| `plugins/gin-workflow/src/commands/beads-status.md` | Status entry point | Says state should be read exclusively from `bd` |

## Task-State Stores And Source-Of-Truth Conflicts

The repo currently uses or references four different workflow state stores:

| Store | Intended purpose | Surfaces that rely on it | Audit assessment |
| --- | --- | --- | --- |
| Beads issue DB via `bd` | Durable task tracking | `AGENTS.md`, `CLAUDE.md`, `beads-status` skill, parts of `bead-orchestrator`, `bead-worker`, `execute`, `progress` | This is the clearest intended source of truth |
| `.planning/plans/*.md` | Durable plan/spec input | `plan` command, `orchestrate`, `execute`, `bead-worker` | Acceptable as planning input, but it is also treated as execution scope/state in some places |
| `.planning/orchestration-state.json` | Orchestrator runtime state | `orchestrate`, `progress`, `ship`, `bead-orchestrator` | Conflicts with Beads by becoming a second execution state authority |
| `.planning/worktrees/` | Worktree lifecycle state | `ship`, `finishing-a-development-branch`, worktree scripts | Acceptable as filesystem implementation detail, but currently doubles as discovery/state |

### Primary conflict

The root repo instructions consistently say Beads should be the durable source of truth, but the plugin workflow still models execution around `.planning/orchestration-state.json` and `.planning/` discovery.

Examples:

- `orchestrate.md` says to "Maintain orchestration status under `.planning/orchestration-state.json`".
- `bead-orchestrator/SKILL.md` says to maintain a master execution state in `.planning/orchestration-state.json`.
- `progress.md` says to map active beads from `.planning/orchestration-state.json`.
- `ship.md` and `finishing-a-development-branch/SKILL.md` say to discover active worktrees by reading `.planning/worktrees/` or `.planning/orchestration-state.json`.
- `beads-status.md` and `beads-status/SKILL.md` say state should be read exclusively from `bd`.

### Secondary conflict

The direct execution path still permits non-Beads state updates:

- `executing-plans/SKILL.md` says to update the Bead status "or update the corresponding plan status in the plan file".

That creates a second mutable execution state path outside Beads.

## Handoff And Completion Rules

There are three overlapping handoff/completion rule sets:

1. `AGENTS.md`
   Requires `bd` tracking, quality gates, `git status`, and conservative no-commit/no-push behavior unless explicitly authorized.
2. `CLAUDE.md`
   Repeats the same conservative Beads handoff model.
3. Plugin workflow commands and skills
   `verify`, `ship`, and `finishing-a-development-branch` define a separate operational completion flow focused on tests, merges, and worktree cleanup.

### Current ambiguity

- The repo rules define the mandatory session close protocol.
- The plugin commands define an operational developer workflow.
- There is no single explicit statement describing which layer owns final completion state for an agent task.

In practice, this means an agent could:

- consider `/ship` the end of work,
- or consider `bd close` plus handoff the end of work,
- or consider plan-file/worktree cleanup the end of work.

That ambiguity is visible in the current docs because completion is described in both Beads terms and branch/worktree terms without a clear precedence model.

## Duplicated Or Inconsistent Guidance

### 1. `bd` versus `br`

`AGENTS.md` mixes two Beads ecosystems:

- Early sections require `bd`.
- Later sections introduce `br` and `bv` and recommend `br show`, `br update`, `br close`, and `br sync`.

In this workspace, `br` is not installed, while `bd` and `bv` are available. That makes part of the documented workflow non-executable in the current environment and weakens the "single source of truth" story.

### 2. Plugin README still centers plan/orchestrate flow more than Beads flow

`README.md` presents the plugin as a plan-driven orchestration system first and a Beads-backed workflow second. That is not inherently wrong, but it obscures the repo-level requirement that Beads own task state across sessions.

### 3. Status reporting is split between `progress` and `beads-status`

- `progress.md` is hybrid: `bd` plus `.planning/orchestration-state.json`
- `beads-status.md` is pure-`bd`

These commands overlap enough that their boundaries are unclear.

### 4. Worker scope comes from plan files, not Beads

`bead-worker/SKILL.md` says authoritative file scope comes from the plan because `bd` issues do not carry file scope. That is workable, but it means actual execution scope is distributed across:

- Beads for status/dependencies
- plan markdown for file scope
- `.planning/orchestration-state.json` for worker runtime state

That is a valid design only if explicitly intentional. Right now it is implied, not clearly defined.

### 5. Historical documents still describe outdated assumptions

- `Plan.md` describes the older dual-platform plugin architecture and planned migration path.
- `review.md` documents previous workflow and hook defects, including state-management assumptions that have since partially changed.

These are useful references but should not be treated as current workflow authority.

## Concrete Pain Points

1. There is no single canonical agent task lifecycle from intake to closure.
2. Durable task state is split conceptually between Beads and `.planning/orchestration-state.json`.
3. Direct execution still allows status mutation outside Beads.
4. Status-reporting surfaces overlap without clean separation.
5. Completion semantics are duplicated across repo instructions and plugin workflow commands.
6. The documented toolchain is inconsistent about `bd` versus `br`.
7. Worktree discovery and cleanup are tied to `.planning/` runtime artifacts rather than a clearly defined Beads-backed lifecycle.
8. Planning artifacts are both specifications and partial execution state, which increases drift risk.

## Recommended Follow-Up Targets

These findings map directly to the open epic children:

- `gin-workflow-p80.1`
  Define a single canonical task lifecycle and specify which layer owns each phase.
- `gin-workflow-p80.3`
  Resolve verification/completion precedence between repo instructions and plugin workflow commands.
- `gin-workflow-p80.4`
  Consolidate the verification and handoff checklist into one authoritative workflow.
- `gin-workflow-p80.6`
  Separate human-facing docs from agent execution instructions so reference docs do not compete with runtime rules.
- `gin-workflow-p80.7`
  Redesign orchestration state so Beads owns durable execution state and `.planning/` is reduced to plan/spec and local implementation artifacts.

## Recommended Direction

The clean target model is:

- Beads owns durable task state, dependencies, assignment, and completion.
- Plan documents own approved task decomposition and declared file scope.
- Worktree paths and branch names remain implementation details, not a competing workflow state system.
- Any orchestrator runtime cache must be explicitly disposable and reconstructible from Beads plus the approved plan.
- One command should be the canonical status surface, with any secondary command clearly scoped.

## Acceptance Criteria Coverage

This audit identifies:

- current lifecycle entry points
- task-state stores
- handoff/completion rules
- duplicated guidance
- concrete pain points to address next
