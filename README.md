# Gin Workflow (`gin-workflow`)

A single plan-driven workflow plugin for **Claude Code**, **Antigravity CLI**, and **Codex CLI**.
It covers requirement analysis, durable planning, Beads-backed task state and orchestration, verification,
technical documentation, and completion handoff.

---

## Commands

The plugin provides a focused set of workflow commands:

| Command | Description |
| :--- | :--- |
| `/plan` | Analyze requirements, compare approaches, clarify scope, and write a durable implementation plan to `.planning/plans/`. |
| `/orchestrate` | Execute a plan by decomposing it into tracked work items (beads) and running them in parallel via subagents. |
| `/execute` | Run implementation work directly from a plan or a specified task list using the `executing-plans` skill. |
| `/verify` | Validate implementation correctness by running test/compile suites using the `verification-before-completion` skill. |
| `/ship` | Complete development work, merge track outputs into the integration branch, and clean up active worktrees. |
| `/progress` | Report detailed execution status of all active subagents and tasks. |
| `/beads-status` | Display status of tracked work items (beads) and execution tracks. |
| `/tech-doc` | Scan the codebase and write a human-readable technical document covering stack, architecture, structure, conventions, and risks. |

## Skills

The plugin keeps the core workflow skills plus a short list of high-value support skills:

- `writing-plans`
- `bead-orchestrator`
- `bead-worker`
- `executing-plans`
- `verification-before-completion`
- `finishing-a-development-branch`
- `dispatching-parallel-agents`
- `using-git-worktrees`
- `beads-status`
- `technical-documentation`
- `systematic-debugging`
- `requesting-code-review`
- `receiving-code-review`

Beads is the durable source of truth for task status, ownership, dependencies, and closure. Plan files under `.planning/plans/` define approved decomposition, scope, and model-guidance metadata, while worktrees and any runtime orchestration metadata are implementation details rather than authoritative workflow state.

---

## Installation

### Remote Installation (Direct from GitHub)

#### 1. Claude Code
Claude Code supports remote installation via marketplaces. Register the repository as a marketplace, then install `gin-workflow`:
```bash
# Register this repository as a marketplace
claude plugin marketplace add giangdhwhtbr/gin-workflow

# Install the plugin
claude plugin install gin-workflow@gin-workflow-marketplace
```

#### 2. Antigravity CLI
Antigravity does not natively support Git-based installation yet. Use the remote-install script to clone, build, and register the plugin automatically:
```bash
# Install globally
curl -sSL https://raw.githubusercontent.com/giangdhwhtbr/gin-workflow/master/remote-install.sh | bash -s -- --platform antigravity
```

---

## Local Development & Compilation

### Running the Installer Locally
Use `install.sh` to compile the plugin into `plugins/gin-workflow/dist/` and install it.

```bash
# Build and register the plugin locally
./install.sh --platform all

# Install to Antigravity
./install.sh --platform antigravity
```

#### Options:
- `--platform <claude | antigravity | codex | both | all>` (default: `all`)
- `--plugin <gin-workflow | all>` (default: `gin-workflow`)
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
│   └── gin-workflow/
│       ├── plugin.meta.json  # Metadata
│       └── src/
│           ├── agents/       # researcher, reviewer, mapper
│           ├── commands/     # workflow commands
│           ├── hooks/        # Pre/Post tool hooks
│           ├── scripts/      # helper scripts
│           └── skills/       # workflow and retained support skills
├── install.sh                # Main build and install script
├── remote-install.sh         # Helper for curl-pipe installation
└── README.md                 # Documentation
```
