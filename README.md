# Gin Workflow (`gin-workflow`)

`gin-workflow` is a workflow plugin for **Claude Code**, **Antigravity CLI**, and **Codex CLI** that combines durable planning with Beads-backed execution tracking.

It is built around a simple ownership model:

- Beads owns durable task state, dependencies, and closure.
- Plan files under `.planning/plans/` own approved decomposition and scope.
- Worktrees, branches, and any runtime orchestration metadata are disposable implementation details.

---

## Primary Skills

The plugin is skill-first across all supported platforms. These skills are the primary user-facing workflow entry points:

| Skill | Description |
| :--- | :--- |
| `discuss` | Start requirement discovery and discussion before any plan or beads are created. |
| `setup` | Run one-time repository initialization and configuration, or explicitly request later maintenance. |
| `workflow` | Route to exactly one valid next lifecycle stage. |
| `plan` | After you confirm the understanding, create a durable implementation plan in `.planning/plans/`. |
| `orchestrate` | After plan approval, automatically create and wire Beads tasks from the plan for execution. |
| `execute` | Run implementation from the approved plan using Beads-backed worker execution and progress updates. |
| `verify` | Validate the implementation against the approved requirement, plan, and acceptance criteria. |
| `ship` | Prepare the verified implementation for delivery and perform the final completion workflow. |
| `progress` | Display strict Beads-first status, active execution context, and recommended next tasks. |
| `tech-doc` | Scan the codebase and write a human-readable technical document covering stack, architecture, structure, conventions, and risks. |

## Support Skills

The plugin also provides lower-level and support skills used internally or for advanced workflows:

- `discovering-work`
- `writing-plans`
- `bead-orchestrator`
- `bead-worker`
- `executing-plans`
- `verification-before-completion`
- `finishing-a-development-branch`
- `dispatching-parallel-agents`
- `using-git-worktrees`
- `systematic-debugging`
- `requesting-code-review`
- `receiving-code-review`

## One-Time Repository Setup

Run `setup` once for a repository before its first `discuss`. The initial
setup session detects the harness, collects portable settings, previews the
write, and creates both the human-authored configuration and generated
effective configuration. Setup is a repository prerequisite, not a lifecycle
stage.

Normal lifecycle invocations load the existing
`.agent-workflow/generated/effective-config.yaml`. They never run setup
automatically. If that file is absent, the lifecycle stops with an instruction
to run `setup` once. Later `setup` invocations occur only when explicitly
requested for status, diagnosis, reconfiguration, migration, rollback, or
bundle maintenance.

## Workflow Model

The plugin’s canonical workflow is:

1. Start with `discuss` to explore the requirement, clarify ambiguity, and align on understanding
2. Wait for explicit user confirmation that the summarized understanding is correct
3. Use `plan` to create the approved implementation plan
4. Use `orchestrate` to automatically create and connect Beads tasks from that plan
5. Use `execute` to implement the work through Beads-backed worker execution
6. Use `verify` to confirm the result against the original requirement and acceptance criteria
7. Use `ship` to complete the delivery workflow once verification passes

`workflow` may be used instead of choosing a stage manually; it routes one next stage only. It does not add, remove, or reorder lifecycle stages. Plugin installation makes the skills and CLI available; it does not initialize any repository or write `.agent-workflow/`.


## Optional Commands

Some hosts also surface plugin commands. Where available, these are optional aliases for the primary skills above:

- `/discuss`
- `/setup`, `/workflow`
- `/plan`
- `/orchestrate`
- `/execute`
- `/verify`
- `/ship`
- `/progress`, `/tech-doc`

For the detailed workflow contracts:

- Agent lifecycle: [docs/agent-task-lifecycle.md](docs/agent-task-lifecycle.md)
- Orchestration state ownership: [docs/orchestration-state-model.md](docs/orchestration-state-model.md)
- Setup, versions, and migration: [docs/setup-system.md](docs/setup-system.md)
- Capability boundaries: [docs/capability-provider-contracts.md](docs/capability-provider-contracts.md)
- Context and evidence: [docs/context-and-evidence-policy.md](docs/context-and-evidence-policy.md)
- Verification and handoff: [docs/verification-and-handoff-workflow.md](docs/verification-and-handoff-workflow.md)

---

## Notifications (Optional)

Notifications are optional and provider-backed. Existing Telegram support may be selected through configuration, but lifecycle guidance neither requires it nor exposes provider-specific commands or credential instructions. See [capability provider contracts](docs/capability-provider-contracts.md).

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

#### 3. Codex CLI
Codex installs plugins from marketplaces. Register this repository as a marketplace, then add `gin-workflow`:
```bash
# Register this repository as a marketplace
codex plugin marketplace add giangdhwhtbr/gin-workflow --ref master

# Install the plugin
codex plugin add gin-workflow@gin-workflow-marketplace
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

# Install to Codex
./install.sh --platform codex
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
