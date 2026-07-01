# Gin Workflow (`gin-workflow`)

A plan-driven developer workflow plugin designed for **Claude Code**, **Antigravity CLI**, and **Codex CLI**. 

`gin-workflow` structures development by putting planning first. It decomposes large goals into structured plans, breaks those plans into tracked work items, and executes them concurrently using parallel subagents with optional Git worktree isolation and structured integration workflows.

---

## Key Features & Architecture

### 1. Commands & Workflows
The plugin provides a powerful set of slash commands to manage your development lifecycle:

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
| `/debug` | Run a systematic debugging workflow (reproduce, isolate, fix, verify) using the `systematic-debugging` skill. |
| `/discuss` | Support interactive design discussion or problem exploration. |
| `/quick` | Execute lightweight, fast-turnaround tasks that do not warrant a plan. |
| `/new-project` | Scaffold a new project, component structure, or boilerplate code. |

---

### 2. Core Orchestration Model
The `/orchestrate` command is the main execution engine. It coordinates plan execution via:
- **Plan-Driven Execution**: Reads the implementation plan as the source of truth.
- **Tracked Work Items (Beads)**: Breaks the plan into discrete tasks or "beads" representing bounded implementation units.
- **Parallel Subagents**: Runs multiple subagents in parallel to execute separate tracks concurrently.
- **Git Worktree Isolation**: Spawns isolated Git worktrees (`--worktree`) for each active execution track to prevent branch pollution and merge conflicts.
- **Integration Branch Management**: Consolidates finished track outputs onto a shared integration branch.

**Supported options for `/orchestrate`:**
- `--plan <path>`: Path to a specific plan markdown file (defaults to the latest file in `.planning/plans/`).
- `--worktree` / `--no-worktree`: Enable/disable Git worktree isolation (defaults to `--worktree`).
- `--max-tracks <N>`: Maximum parallel execution tracks (default: `4`).
- `--integration-branch <name>`: Integration branch to merge changes into.
- `--inject-agents-md`: Inject agent instructions pre-flight.

---

### 3. Specialist Agents
`gin-workflow` leverages dedicated specialist agents defined under `agents/` to divide and conquer tasks:

*   **`agent-researcher`**: Investigate requirements, API references, library behaviors, or implementation options.
*   **`code-reviewer`**: Reviews modifications for bugs, code style compliance, and performance/security risks.
*   **`codebase-mapper`**: Analyzes codebase architecture and maps file relationships.

---

### 4. Lifecycle Hooks
The plugin hooks into tool execution to automate checks and post-execution behaviors (`hooks/hooks.json`):
*   **`PreToolUse`**: Matches shell executions (`Bash`/`run_command`) to run `safety-check.sh`, avoiding unsafe operations.
*   **`PostToolUse`**: Matches write/edit actions to execute `post-edit.sh` for auto-formatting, linting, or state synchronization.

---

## Installation

### Prerequisites
Make sure you have `bash` and `python3` (used for manifest building) available on your system.

### Running the Installer
Use the provided `install.sh` script to install, link, or uninstall the plugin.

#### 1. Global Installation
To install the plugin for all compatible CLI platforms:
```bash
./install.sh --platform all
```

You can target specific platforms using `--platform <claude | antigravity | codex | both | all>` (default: `all`):
```bash
# Install only for Antigravity
./install.sh --platform antigravity

# Install only for Claude Code
./install.sh --platform claude
```

During installation, the script compiles files to the `dist/` directory and registers the plugin:
*   **Antigravity CLI**: Automatically registered by running `agy plugin install dist/antigravity`.
*   **Codex CLI**: Automatically registered by running `codex plugin install dist/codex`.
*   **Claude Code**: Registered interactively by running:
    ```bash
    claude --plugin-dir "/absolute/path/to/dist/claude-code"
    ```

#### 2. Local Project-Level Installation
To install the plugin configurations locally to a specific project directory:
```bash
./install.sh --project /path/to/your/project
```
This scaffolds local configurations inside the target directory:
- `.claude/` for Claude Code project configurations and hooks.
- `.agents/` for Antigravity project configurations.
- `.codex/` for Codex project configurations.

#### 3. Installer Options
- `--link`: Creates symbolic links from your development tree instead of copying files. Use this for active development.
- `--uninstall`: Cleans up the compiled `dist` files.
- `--dry-run`: Preview where files would be copied/installed without actually modifying the filesystem.

---

## Workflow Guide: Step-by-Step

A typical plan-driven development workflow using `gin-workflow`:

1.  **Analyze & Map**:
    Identify codebase structures and dependency layouts.
    ```
    /map-codebase
    ```
2.  **Plan**:
    Design your implementation plan. The system prompts you to resolve ambiguities and saves the result to `.planning/plans/<timestamp>-<description>.md`.
    ```
    /plan
    ```
3.  **Orchestrate**:
    Decompose the plan and kick off parallel subagents to execute implementation tasks.
    ```
    /orchestrate --max-tracks 3
    ```
4.  **Monitor**:
    Track execution states (pending, active, blocked, complete, failed) of each track.
    ```
    /progress
    ```
5.  **Verify**:
    Verify that tests pass and the changes meet the objective requirements.
    ```
    /verify
    ```
6.  **Review**:
    Invoke the `code-reviewer` agent to verify compliance and catch remaining issues.
7.  **Ship**:
    Finalize changes, merge the integration branch, and clean up temporary worktrees.
    ```
    /ship
    ```

---

## Repository Structure

```
gin-workflow/
├── dist/                # Target compilation output for CLI registrations
├── install.sh           # Core plugin installation script
├── plugin.meta.json     # Manifest metadata definition
├── Plan.md              # Original development plan for gin-workflow
├── README.md            # Plugin documentation (this file)
└── src/                 # Original source files
    ├── agents/          # Specialist agent definitions (researcher, reviewer, mapper)
    ├── commands/        # Commands exposed to the CLI platforms (plan, orchestrate, etc.)
    ├── hooks/           # Pre-tool and post-tool lifecycle hooks configuration
    ├── scripts/         # Automated helper scripts (safety checking, branch merging, etc.)
    └── skills/          # Reusable prompt instructions and workflows (TDD, worktrees, orchestration)
```