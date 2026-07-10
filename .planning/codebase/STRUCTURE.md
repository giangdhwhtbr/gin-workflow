# Codebase Structure

**Analysis Date:** 2026-07-10
**Scope:** Full repository (`/home/gin/gin-workflow`)
**Evidence:** 
- Files listed in repository root and `plugins/gin-workflow/`
**Index Use:** Direct inspection was used (no repository index present).

## Directory Layout

```
[project-root]/
├── .planning/                  # Planning plans, databases, and worktree allocations
│   ├── beads/                  # Beads local database settings
│   ├── plans/                  # Approved execution plans
│   └── codebase/               # Generated technical documentation (split set)
├── docs/                       # Lifecycle and architecture specifications
├── plugins/                    # Main plugin implementations
│   └── gin-workflow/
│       ├── plugin.meta.json    # Plugin metadata
│       └── src/                # Plugin source files
│           ├── agents/         # Custom platform agents
│           ├── commands/       # Platform-facing slash commands
│           ├── hooks/          # Hooks configuration JSON
│           ├── scripts/        # Operational shell helpers
│           └── skills/         # Executable skill instruction files
├── tests/                      # Testing and verification suites
├── AGENTS.md                   # Agent operating rules
├── CLAUDE.md                   # Command parameters and constraints
├── install.sh                  # Plugin manifest installer
├── remote-install.sh           # Global deployment hook
└── README.md                   # Repository documentation
```

## Directory Purposes

**.planning/:**
- Purpose: Active design, code mapping, and task planning.
- Contains: Plan markdown files and local state trackers.
- Key files: `.planning/orchestration-state.json`

**plugins/gin-workflow/src/commands/:**
- Purpose: Front-end triggers inside target CLI platforms.
- Contains: Markdown files representing target commands.
- Key files: [tech-doc.md](file:///home/gin/gin-workflow/plugins/gin-workflow/src/commands/tech-doc.md), [plan.md](file:///home/gin/gin-workflow/plugins/gin-workflow/src/commands/plan.md)

**plugins/gin-workflow/src/scripts/:**
- Purpose: Automation code for isolated environments.
- Contains: Executable bash scripts.
- Key files: [safety-check.sh](file:///home/gin/gin-workflow/plugins/gin-workflow/src/scripts/safety-check.sh), [worktree-create.sh](file:///home/gin/gin-workflow/plugins/gin-workflow/src/scripts/worktree-create.sh)

## Key File Locations

**Entry Points:**
- `install.sh`: Setup compiler.
- `plugins/gin-workflow/src/commands/plan.md`: Planning entry point.

**Configuration:**
- `plugins/gin-workflow/plugin.meta.json`: Core plugin manifest.
- `plugins/gin-workflow/src/hooks/hooks.json`: Interception rules.

**Core Logic:**
- `plugins/gin-workflow/src/skills/`: Holds workflow execution skills.

**Testing:**
- `tests/install_smoke_test.sh`: Main regression test suite.

## Naming Conventions

**Files:** lowercase-separated-by-dashes (e.g. `safety-check.sh`, `agent-task-lifecycle.md`).
**Directories:** lowercase-separated-by-dashes (e.g. `gin-workflow`, `bead-orchestrator`).

## Where to Add New Code

**New Feature:**
- Define commands in `plugins/gin-workflow/src/commands/`
- Reference corresponding skills in `plugins/gin-workflow/src/skills/`

**New Component / Module:**
- Write scripts under `plugins/gin-workflow/src/scripts/` and verify they exit safely.

**Utilities:**
- Add helper validations or assertions to [tests/install_smoke_test.sh](file:///home/gin/gin-workflow/tests/install_smoke_test.sh).

## Special Directories

**.beads/:**
- Purpose: Local SQL task storage directory managed by the `bd` binary.
- Generated: Yes (by `bd init` or `bd prime`).
- Committed: No (contains developer-specific state).

---

*Structure analysis: 2026-07-10*
