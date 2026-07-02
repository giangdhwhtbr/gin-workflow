# Gin Workflow (`gin-workflow`) & Gin Workflow Advanced (`gin-workflow-advanced`)

A plan-driven developer workflow suite designed for **Claude Code**, **Antigravity CLI**, and **Codex CLI**. 

The suite is split into two plugins:
1. **`gin-workflow` (Core)**: Handles the plan-driven execution lifecycle (plan → orchestrate → execute → verify → ship).
2. **`gin-workflow-advanced`**: Adds supplementary productivity skills (brainstorming, debugging, TDD, code review integration, etc.).

---

## Key Features & Architecture

### 1. Core Workflow Commands (`gin-workflow`)
The core plugin provides a set of slash commands to manage your development lifecycle:

| Command | Description |
| :--- | :--- |
| `/plan` | Create or refine a structured implementation plan in `.planning/plans/` using the `writing-plans` skill. |
| `/orchestrate` | Execute a plan by decomposing it into tracked work items (beads) and running them in parallel via subagents. |
| `/execute` | Run implementation work directly from a plan or a specified task list using the `executing-plans` skill. |
| `/verify` | Validate implementation correctness by running test/compile suites using the `verification-before-completion` skill. |
| `/ship` | Complete development work, merge track outputs into the integration branch, and clean up active worktrees. |
| `/progress` | Report detailed execution status of all active subagents and tasks. |
| `/beads-status` | Display status of tracked work items (beads) and execution tracks. |
| `/map-codebase` | Build a structural mapping of the codebase to discover modules, interfaces, and dependencies. |
| `/quick` | Execute lightweight, fast-turnaround tasks that do not warrant a plan. |
| `/new-project` | Scaffold a new project, component structure, or boilerplate code. |

### 2. Advanced Skills (`gin-workflow-advanced`)
Surfaces additional agent instructions and flows as skills:

*   **`brainstorming`**: Explores design alternatives, pros/cons, and options non-destructively before planning.
*   **`systematic-debugging`**: Reproduce, isolate, hypothesize root cause, minimal fix, and verify.
*   **`test-driven-development`**: Standard Red-Green-Refactor development loop.
*   **`requesting-code-review` / `receiving-code-review`**: Integration workflow for triggering and applying code reviews.
*   **`subagent-driven-development`**: Rules for context-splitting, tasks delegate to subagents.
*   **`using-claude-draft`**: Defer tool side-effects until plans or diffs are approved.
*   **`agent-browser`**: Browse and select specialist subagents.
*   **`writing-skills`**: Framework instructions for writing new SKILL.md modules.

---

## Installation

### Remote Installation (Direct from GitHub)

#### 1. Claude Code
Claude Code supports remote installation via marketplaces. Register the repository as a marketplace, then install either or both plugins:
```bash
# Register this repository as a marketplace
claude plugin marketplace add giangdhwhtbr/gin-workflow

# Install the plugins
claude plugin install gin-workflow@gin-workflow-marketplace
claude plugin install gin-workflow-advanced@gin-workflow-marketplace
```

#### 2. Antigravity CLI
Antigravity does not natively support Git-based installation yet. Use the remote-install script to clone, build, and register the plugins automatically:
```bash
# Install both plugins globally
curl -sSL https://raw.githubusercontent.com/giangdhwhtbr/gin-workflow/master/remote-install.sh | bash -s -- --platform antigravity --plugin all
```

---

## Local Development & Compilation

### Running the Installer Locally
Use `install.sh` to compile plugins into the `plugins/<plugin-name>/dist/` directory and install them.

```bash
# Build and register both plugins locally
./install.sh --platform all --plugin all

# Install only the core plugin to Antigravity
./install.sh --platform antigravity --plugin core
```

#### Options:
- `--platform <claude | antigravity | codex | both | all>` (default: `all`)
- `--plugin <core | advanced | all>` (default: `all`)
- `--link`: Creates symbolic links from your development tree instead of copying files. Use this for active development.
- `--uninstall`: Cleans up the compiled `dist` files.
- `--dry-run`: Preview changes without copying files.

---

## Repository Structure

```
gin-workflow/
├── .claude-plugin/
│   └── marketplace.json     # Claude Code marketplace index
├── plugins/
│   ├── gin-workflow/         # Core Plugin
│   │   ├── plugin.meta.json  # Metadata
│   │   └── src/
│   │       ├── agents/       # core agents (researcher, reviewer, mapper)
│   │       ├── commands/     # core commands
│   │       ├── hooks/        # Pre/Post tool hooks
│   │       ├── scripts/      # helper scripts
│   │       └── skills/       # core skills
│   └── gin-workflow-advanced/ # Advanced Plugin
│       ├── plugin.meta.json
│       └── src/
│           └── skills/       # advanced skills (brainstorming, debug, etc.)
├── install.sh                # Main build and install script
├── remote-install.sh         # Helper for curl-pipe installation
└── README.md                 # Documentation
```