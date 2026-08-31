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
| `tech-doc` | Scan the codebase and write a human-readable technical document covering stack, architecture, structure, conventions, and risks. |

## Support Skills

The plugin provides fully self-contained support skills (bundled reasoning methodology + gin-workflow rules; `superpowers` is no longer a dependency):

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
- `/progress`, `/tech-doc`

For the detailed workflow contracts:

- Agent lifecycle: [docs/agent-task-lifecycle.md](docs/agent-task-lifecycle.md)
- Orchestration state ownership: [docs/orchestration-state-model.md](docs/orchestration-state-model.md)
- Setup, versions, and migration: [docs/setup-system.md](docs/setup-system.md)
- Capability boundaries: [docs/capability-provider-contracts.md](docs/capability-provider-contracts.md)
- Context and evidence: [docs/context-and-evidence-policy.md](docs/context-and-evidence-policy.md)
- Native provider routing and model aliases: [docs/provider-routing.md](docs/provider-routing.md)
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

## Troubleshooting

### Codex/Antigravity sandbox fails with `bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted`

On Ubuntu 24.04+ hosts, the kernel's AppArmor policy restricts unprivileged user namespace creation by default (`kernel.apparmor_restrict_unprivileged_userns=1`). Codex CLI's sandbox (`bwrap`) and Antigravity CLI's sandbox (`agy --sandbox`, backed by `nsjail`) both need to create an unprivileged user+network namespace to isolate file/network access. When that AppArmor restriction is active and no profile grants `userns,` to the sandbox helper, namespace creation fails outright — before the sandboxed process can even read the file it's trying to edit. Every sandboxed shell action (including `apply_patch`) then fails immediately, for any file, in any project.

This is a host/OS-level restriction, not a bug in gin-workflow, Codex CLI, or Antigravity CLI. Fix it once per host, in a real interactive terminal (`sudo` needs a TTY for the password prompt — it won't work through a piped or non-interactive shell):

```bash
# Take effect immediately
sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=0

# Persist across reboots
echo 'kernel.apparmor_restrict_unprivileged_userns=0' | sudo tee /etc/sysctl.d/99-disable-userns-restrict.conf
```

Verify:
```bash
sysctl kernel.apparmor_restrict_unprivileged_userns   # should print 0
codex sandbox -- echo hello                            # should print "hello", not a bwrap error
```

gin-workflow's own Codex-provider worker dispatch (`codex_worker.py`) works around this for workers it dispatches itself, by invoking `codex exec` with `--dangerously-bypass-approvals-and-sandbox` — skipping Codex's internal sandbox entirely, since gin-workflow already isolates each worker in its own git worktree. That has no effect on a Codex CLI session you run directly, or on Antigravity's `--sandbox`, which is why the sysctl fix above is what actually resolves this everywhere on an affected host.

### Review routing reports a provider as "not available" (e.g. `claude not available`) when invoked from Codex/Antigravity

gin-workflow's routed dispatcher (`registry.py`) health-checks a native provider by running `<executable> --help` in a subprocess with a *sanitized* environment (`native_cli.py`'s `sanitized_environment()`/`probe_help()`) — it forwards `PATH` from whatever process is running the gin-workflow script, but that process's `PATH` did not come from your interactive shell's rc file. If a provider's CLI binary is only reachable because `~/.zshrc`/`~/.bashrc` prepends a directory to `PATH` (for example, an npm global install landing in `~/.npm-global/bin`), it resolves fine in an interactive shell but fails when gin-workflow is driven by Codex or Antigravity, whose exec/sandbox environments don't source your shell rc files. The health check then can't even launch the binary, and the dispatcher reports it as unavailable — well before any quota, auth, or model issue.

Fix by putting the CLI binary somewhere already on the default system `PATH` (not dependent on shell rc files), e.g.:

```bash
sudo ln -s "$(which claude)" /usr/local/bin/claude
```

Verify it resolves independent of your shell's `PATH` customizations:
```bash
env -i PATH="/usr/local/bin:/usr/bin:/bin" claude --version
```

Apply the same fix for any other native provider CLI (`codex`, `agy`) that isn't already reachable from a minimal `PATH`.

### A repository still hits a `gin-workflow` bug that was already fixed and shipped on `master`

Harness plugin managers install `gin-workflow` by snapshotting its files into a local cache at install time (e.g. Codex's `~/.codex/plugins/cache/<marketplace>/gin-workflow/<version>/`, Claude Code's global skills directory). That snapshot is not a live view of this repository — pushing a fix to `master` does not, by itself, update any consuming repository's cached install, even when the plugin's declared version number hasn't changed. A repository on the same host can keep failing with the exact symptoms of an already-fixed bug simply because its cached snapshot predates the fix.

After shipping a fix in this repository, refresh every installed platform's cache on the host:

```bash
./install.sh --platform all
```

The fix must be **committed** first. Codex's marketplace registration uses a `git-subdir` source (see `.claude-plugin/marketplace.json`) that reads the plugin's tree from the repository's committed `HEAD`, not the working directory — re-running the install with only an uncommitted change staged or edited will re-register the plugin successfully but still snapshot the pre-fix content.

This is safe to re-run any time — for Codex it explicitly removes and re-adds the plugin/marketplace registration (`codex plugin marketplace add`/`plugin add` are no-ops when already registered by name, and the local-source snapshot is only taken at add-time, so a plain repeat run would keep serving the stale snapshot without the explicit remove-then-add), and for Claude Code/Antigravity it recopies the compiled `dist/` output into the global install location. Use `--platform codex`/`claude`/`antigravity` to target just one. This only refreshes installs on the current host; a consumer on a different machine (installed via the GitHub marketplace or `remote-install.sh`) needs to re-run its own install/update flow from the "Remote Installation" section above.

Verify the fix actually landed by checking a changed file's content inside the refreshed install directory (or, for a Python fix, importing the module from that path and exercising the fixed behavior directly) rather than assuming a successful install command means the fix is present.

### Workflow is held at `progress` or a gate is blocked

When a task holds at `progress` or fails to advance to the next lifecycle stage, run `gin-workflow state` to diagnose the exact reason:

```bash
gin-workflow state [--format text|json]
```

This displays the current decision, target stage, evidence, and per-gate statuses (`satisfied`, `waived`, or `unmet`), along with concrete remedies for any unmet gate or missing approval.

To resolve an unmet gate:
- For **process gates** (`requirement_confirmed`, `plan_approved`, `orchestration_ready`):
  ```bash
  gin-workflow unblock --gate <gate> --reason "stated reason" --actor <your-id>
  ```
- For **safety gates** (`verification_passed`, `review_approved`):
  ```bash
  gin-workflow unblock --gate <gate> --reason "stated reason" --actor <your-id> --follow-up <follow-up-task-id>
  ```
- To **clear a task-tracking blocker**:
  ```bash
  gin-workflow unblock --clear-blocker --reason "cleared blocker reason" --actor <your-id>
  ```

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
│           ├── agents/       # researcher, reviewer, mapper
│           ├── commands/     # workflow commands
│           ├── hooks/        # Pre/Post tool hooks
│           ├── scripts/      # helper scripts
│           └── skills/       # workflow and retained support skills
├── install.sh                # Main build and install script
├── install.ps1               # Native build and installer for PowerShell 7
├── remote-install.sh         # Helper for curl-pipe installation
└── README.md                 # Documentation
```
