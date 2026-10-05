# Gin Workflow (`gin-workflow`)

`gin-workflow` is a workflow plugin for **Claude Code**, **Antigravity CLI**, and **Codex CLI** that combines durable planning with Beads-backed execution tracking.

It is built around a simple ownership model:

- Beads owns durable task state, dependencies, and closure.
- Plan files under `.planning/plans/` own approved decomposition and scope.
- Worktrees, branches, and any runtime orchestration metadata are disposable implementation details.
- Skills are 100% self-contained — no external base plugins (such as `superpowers`) are required.

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
| `report` | Report AI usage per bead or epic: tokens and estimated cost per model and stage, next to reopens, bugs, and review rework. |
| `tech-doc` | Scan the codebase and write a human-readable technical document covering stack, architecture, structure, conventions, and risks. |

## Support Skills

Each lifecycle stage skill is self-contained (methodology + gin-workflow rules) and shares `references/stage-contract.md`; `superpowers` is not a dependency. Shared support skills load on demand:

- `review` — request or perform an independent review through the review ledger
- `quick` — small, low-risk change without plan or beads, verified per rigor
- `gin-debugging` — root cause before fix
- `gin-worktrees` — isolated workspaces and clean baselines
- `gin-review-response` — triage review findings in the ledger
- `gin-parallel-agents` — bounded concurrent agents for independent work
- `gin-knowledge` — capture and reconcile durable project knowledge

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
6. Coordinate Code Review through the review capability; this is provider-backed activity between execution and verification, not a router stage
7. Use `verify` to confirm the result against the original requirement, acceptance criteria, and terminal review evidence
8. Use `ship` to complete the delivery workflow once verification passes

`workflow` may be used instead of choosing a stage manually; it routes one next implemented stage only. Code Review is coordinated separately and does not become a `workflow` route or a new router gate. Plugin installation makes the skills and CLI available; it does not initialize any repository or write `.agent-workflow/`.

### Common Use Cases

| Need | Guide | Durable starting point |
| :--- | :--- | :--- |
| New multi-track change | [Large task](docs/use-cases/large-task.md) | `discuss` → confirmed requirement |
| Continue existing work | [Resume in progress](docs/use-cases/resume-in-progress.md) | `progress` / `workflow` and Beads |
| Small bounded defect | [Quick debug](docs/use-cases/quick-debug.md) | bounded diagnosis and approved plan |

The guides describe prerequisites, state/evidence gates, failure handling, and safe recovery.


## Optional Commands

Some hosts also surface plugin commands. Where available, these are optional aliases for the primary skills above:

- `/discuss`
- `/setup`, `/workflow`
- `/plan`
- `/orchestrate`
- `/execute`
- `/verify`
- `/ship`
- `/progress`, `/tech-doc`, `/report`

AI usage: `gin-workflow usage collect --bead <id>` summarizes the bead's tokens from local Claude Code and Codex logs into its metadata (the `execute` and `ship` skills run it at close); `gin-workflow usage report [--bead|--epic|--since]` reads the summaries back. Costs are estimated from `.agent-workflow/usage-prices.yaml` (`prices: {<model>: {input, output, cache_read, cache_write}}`, USD per million tokens); a model without a price is listed as unpriced.

For the detailed workflow contracts:

- Architecture and flow diagrams: [docs/concepts/architecture.md](docs/concepts/architecture.md)
- Lifecycle, gates, verification, and handoff: [docs/concepts/lifecycle.md](docs/concepts/lifecycle.md)
- State ownership: [docs/concepts/state-model.md](docs/concepts/state-model.md)
- Providers, routing, and evidence: [docs/concepts/providers.md](docs/concepts/providers.md)
- Configuration, versions, and migration: [docs/reference/config.md](docs/reference/config.md)
- CLI: [docs/reference/cli.md](docs/reference/cli.md)

---

## Rule Packs

`gin-workflow rules --files <paths>` gives the `developer` agent, `/quick`, and the reviewer the best-practice rules for the files in scope. `core` and `lean` load by default; language and framework packs come from `rules.packs` in `.agent-workflow/config.yaml`, and `rules.disabled: [lean]` turns a pack off. `lean` asks for the shortest correct solution: reuse what exists, prefer the standard library, the platform, and installed dependencies, and add nothing speculative, without cutting validation, error handling, security, accessibility, or required tests. Its ideas come from [ponytail](https://github.com/dietrichgebert/ponytail) (MIT).

---

## Notifications (Optional)

Notifications are optional and provider-backed. Existing Telegram support may be selected through configuration, but lifecycle guidance neither requires it nor exposes provider-specific commands or credential instructions. See [Providers](docs/concepts/providers.md#capabilities).

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

### QA add-on (`gin-qa`, optional)
`gin-qa` writes and checks test cases derived from the specs (`/gin-qa:cases`). It is not installed by default and needs `gin-workflow`. Install the plugin and its `gin-qa` launcher with `--plugin gin-qa` (or `--plugin all` for both):
```bash
./install.sh --plugin gin-qa
# or remotely
curl -sSL https://raw.githubusercontent.com/giangdhwhtbr/gin-workflow/master/remote-install.sh | bash -s -- --plugin gin-qa
```
Test cases live in `qa/cases/<capability>.md` (configurable with `qa.cases` in `.agent-workflow/config.yaml`); team rules for writing them go in `qa/guidelines.md` (`qa.guidelines`). `gin-qa cases export --format json` feeds your own report tooling.

`/gin-qa:e2e <capability>` turns `Type: e2e` cases into Playwright specs under `qa/e2e/<capability>/` (`qa.e2e`) and runs them with `gin-qa e2e run`. `gin-qa e2e init` copies the evidence fixture `qa/e2e/evidence.ts` (yours to edit) and git-ignores `qa/evidence/`; each run leaves a screenshot per step and a `result.json` per case (per case and Playwright project when the config names projects) there, checked by `gin-qa e2e check --run <folder>` and exported with `gin-qa e2e export --run <folder> --format json`. The skill builds each spec step by step against the running application, reading the ARIA snapshot (`NN.aria.yml`) and URL the fixture records after every step, and reviews the screenshots before it reports a case; on platforms with subagents it works on several cases in parallel (`--parallel N`, default 3). The project provides `@playwright/test` (1.49 or later) and its Playwright config (`baseURL`, browsers, video, trace).

---

## Troubleshooting

See [Troubleshooting](docs/reference/troubleshooting.md).

---


## Local Development & Compilation

### Linux and macOS

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

### Windows (PowerShell 7)

Native Windows installation requires [PowerShell 7](https://learn.microsoft.com/powershell/) and Python 3 available as `python` on `PATH`.

```powershell
# Build and register all detected harness plugins
pwsh -NoProfile -File .\install.ps1 -Platform all

# Install Codex files into one project
pwsh -NoProfile -File .\install.ps1 -Platform codex -Project C:\path\to\repository

# Preview launcher and registration changes
pwsh -NoProfile -File .\install.ps1 -Platform all -DryRun
```

PowerShell parameters:

- `-Platform <claude | antigravity | codex | both | all>` (default: `all`)
- `-Plugin <gin-workflow | all>` (default: `gin-workflow`)
- `-Link`: Creates symbolic links for active development. Windows may require Developer Mode or elevated privileges.
- `-Project <path>`: Installs harness files into one repository instead of registering globally.
- `-Uninstall`: Cleans generated repository `dist` directories.
- `-DryRun`: Previews user-level writes and registration while still rebuilding repository-local `dist` output.

The versioned launcher is installed beneath `$HOME\.local\lib\gin-workflow`, with a command shim at `$HOME\.local\bin\gin-workflow.cmd`. The installer warns when `$HOME\.local\bin` is not on `PATH`; it does not change the persistent user environment automatically.

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
│           ├── agents/       # developer, researcher, reviewer, docs writer
│           ├── hooks/        # Pre/Post tool hooks
│           ├── scripts/      # helper scripts
│           └── skills/       # workflow and retained support skills
├── install.sh                # Main build and install script
├── install.ps1               # Native build and installer for PowerShell 7
├── remote-install.sh         # Helper for curl-pipe installation
└── README.md                 # Documentation
```
