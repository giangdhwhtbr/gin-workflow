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

## Workflow Model

The plugin’s canonical workflow is:

1. Start with `discuss` to explore the requirement, clarify ambiguity, and align on understanding
2. Wait for explicit user confirmation that the summarized understanding is correct
3. Use `plan` to create the approved implementation plan
4. Use `orchestrate` to automatically create and connect Beads tasks from that plan
5. Use `execute` to implement the work through Beads-backed worker execution
6. Use `verify` to confirm the result against the original requirement and acceptance criteria
7. Use `ship` to complete the delivery workflow once verification passes


## Optional Commands

Some hosts also surface plugin commands. Where available, these are optional aliases for the primary skills above:

- `/discuss`
- `/plan`
- `/orchestrate`
- `/execute`
- `/verify`
- `/ship`
- `/progress`, `/tech-doc`

For the detailed workflow contracts:

- Agent lifecycle: [docs/agent-task-lifecycle.md](docs/agent-task-lifecycle.md)
- Orchestration state ownership: [docs/orchestration-state-model.md](docs/orchestration-state-model.md)
- Verification and handoff: [docs/verification-and-handoff-workflow.md](docs/verification-and-handoff-workflow.md)

---

## Telegram Integration (Optional)

Agents can send notifications and receive replies via a private Telegram bot during workflow lifecycle events. This is fully opt-in — when not configured, all skills behave exactly as before.

### Setup

1. Create a bot via [@BotFather](https://t.me/BotFather) on Telegram.
2. Send any message to your bot to start a private conversation.
3. Get your chat ID (send a message to the bot, then check `https://api.telegram.org/bot<TOKEN>/getUpdates`).
4. Set environment variables:
   ```bash
   export TELEGRAM_BOT_TOKEN="your-bot-token"
   export TELEGRAM_CHAT_ID="your-chat-id"
   ```

### Notification Events

| Event | Mode | Trigger |
|---|---|---|
| 📋 Plan ready | Two-way | After plan is written, before approval |
| ✅ Task completed | One-way | After a bead passes verification |
| 🚫 Work blocked | One-way | When a worker hits out-of-scope changes or ambiguity |
| ✅/❌ Verification result | One-way | After quality gates run |
| 🚀 Ship ready | Two-way | Before final delivery |
| 🎉 All work complete | One-way | After all beads are closed |

**Two-way** events send a message and wait up to 10 minutes for your reply. **One-way** events are fire-and-forget.

### Timeout and Resume

When the agent waits for your reply and you don't respond within 10 minutes:
- The agent saves its state and exits gracefully.
- The Telegram message remains in your chat with the session ID.
- Resume later using your platform's resume command:
  - `agy resume <session-id>`
  - `claude --resume <session-id>`
  - `codex resume <session-id>`

### Dependencies

- `curl` (required) — for Telegram Bot API calls.
- `jq` (recommended) — for JSON parsing during two-way polling. Falls back to send-only if unavailable.

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
