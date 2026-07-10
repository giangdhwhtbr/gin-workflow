# Architecture

**Analysis Date:** 2026-07-10
**Scope:** Full repository (`/home/gin/gin-workflow`)
**Evidence:** 
- [plugins/gin-workflow/src/hooks/hooks.json](file:///home/gin/gin-workflow/plugins/gin-workflow/src/hooks/hooks.json)
- [plugins/gin-workflow/src/scripts/safety-check.sh](file:///home/gin/gin-workflow/plugins/gin-workflow/src/scripts/safety-check.sh)
- [docs/agent-task-lifecycle.md](file:///home/gin/gin-workflow/docs/agent-task-lifecycle.md)
- [docs/orchestration-state-model.md](file:///home/gin/gin-workflow/docs/orchestration-state-model.md)
- [install.sh](file:///home/gin/gin-workflow/install.sh)
**Index Use:** Direct inspection was used (no repository index present).

## System Overview

```text
┌─────────────────────────────────────────────────────────────┐
│                   Agent Platform / CLI                      │
│            (Claude Code / Antigravity / Codex)              │
├──────────────────┬──────────────────┬───────────────────────┤
│    Commands      │   Hooks Config   │      Subagents        │
│ `src/commands/`  │   `hooks.json`   │     `src/agents/`     │
└────────┬─────────┴────────┬─────────┴──────────┬────────────┘
         │                  │                     │
         ▼                  ▼                     ▼
┌─────────────────────────────────────────────────────────────┐
│                 Plugin Compilation & Shell                  │
│       `install.sh` / `src/scripts/` / `src/skills/`          │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│             Beads Local Task Tracking & Git                 │
│              `.beads/` / `.planning/`                       │
└─────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| Manifest Compiler | Compiles plugin configurations and templates them for platforms | [install.sh](file:///home/gin/gin-workflow/install.sh) |
| Pre-Tool Safety Check | Validates execution bounds and rejects dangerous rm targets | [plugins/gin-workflow/src/scripts/safety-check.sh](file:///home/gin/gin-workflow/plugins/gin-workflow/src/scripts/safety-check.sh) |
| Hook Definition | Directs the platform hook runners to run validation scripts | [plugins/gin-workflow/src/hooks/hooks.json](file:///home/gin/gin-workflow/plugins/gin-workflow/src/hooks/hooks.json) |
| Worktree Manager | Safely provisions worktree isolation directories | [plugins/gin-workflow/src/scripts/worktree-create.sh](file:///home/gin/gin-workflow/plugins/gin-workflow/src/scripts/worktree-create.sh) |
| System Specs | Declares the canonical state boundaries and close-out checklist | [docs/](file:///home/gin/gin-workflow/docs/) |

## Pattern Overview

**Overall:** Plan-driven execution orchestration.

**Key Characteristics:**
- State Separation: Beads owns task state; Markdown plans own execution specifications; Git worktrees own execution isolation.
- Fall-closed Security: Commands run in sandboxes or verified by pre-tool check hooks to fail closed on dangerous commands.

## Layers

**Platform Interface Layer:**
- Purpose: Direct command bindings inside agent environments.
- Location: `plugins/gin-workflow/src/commands/`
- Contains: Plugin commands (e.g., `tech-doc.md`, `plan.md`, `orchestrate.md`).
- Depends on: Skills Layer.

**Skills Layer:**
- Purpose: Reusable task implementation modules.
- Location: `plugins/gin-workflow/src/skills/`
- Contains: Specialized skill workflows (e.g., `bead-orchestrator`, `executing-plans`).

**Automation Script Layer:**
- Purpose: Operational file-system and environment tasks.
- Location: `plugins/gin-workflow/src/scripts/`
- Contains: Bash utility scripts.

## Data Flow

### Primary Request Path

1. **User trigger:** A slash command is executed in the CLI (e.g. `/plan` or `/verify`).
2. **Hook Execution:** Platform processes hooks defined in `hooks.json`. Before executing a shell tool, the platform intercepts the request and runs `safety-check.sh`.
3. **Task Orchestration:** The orchestrator dispatches workers, allocating new beads via `bd update` and creating git worktrees via `worktree-create.sh`.
4. **Execution Summary:** `/progress` reads data from `.beads/` and prints progress tables.

**State Management:**
- Beads tracks the active task lifecycle (`open -> in_progress -> closed`).
- Plan files track decomposition. No plan file checkbox or local orchestration JSON is considered the authoritative task state.

## Key Abstractions

**Bead:**
- Purpose: A durable execution unit containing ID, status, assignment, and blockers.
- Examples: Managed via `bd` CLI.

**Worktree:**
- Purpose: An isolated directory containment to run parallel subagent implementation tasks safely.
- Examples: `.planning/worktrees/<track-id>`

## Entry Points

**install.sh:**
- Location: `install.sh`
- Triggers: User setup / compilation.
- Responsibilities: Prepares the package directory structure.

**commands:**
- Location: `plugins/gin-workflow/src/commands/`
- Triggers: Target CLI invocation.

## Architectural Constraints

- **Single State Owner:** Local task state resides strictly in Beads.
- **Safety checks:** Commands must fail closed if JSON inputs are malformed.
- **CLAUDE.md / AGENTS.md directives:** Non-interactive execution is required. No commits or pushes without explicit approval.

## Anti-Patterns

### Checkbox Orchestration
- **What happens:** Checking off items in planning files instead of using `bd close <id>`.
- **Why it's wrong:** Planning files are templates and do not synchronize state across multi-agent environments.
- **Do this instead:** Use `bd close` for final task resolution.

## Error Handling

**Strategy:** Fail closed.

**Patterns:**
- `set -euo pipefail` in all shell scripts.
- Schema verification throws system exit errors during tests.

## Cross-Cutting Concerns

**Logging:** Output redirection to stdout/stderr.
**Validation:** `safety-check.sh` intercepts shell execution to validate safety constraints.

---

*Architecture analysis: 2026-07-10*
