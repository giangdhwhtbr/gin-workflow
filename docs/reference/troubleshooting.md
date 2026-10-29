# Troubleshooting

## `gin-workflow: command not found` after a marketplace install

Cause: a marketplace install (`claude plugin install`, `codex plugin add`) copies the plugin but does not link the `gin-workflow` launcher that the skills call. Only the installer links it, at `~/.local/bin/gin-workflow`.

1. Run the installer, with `--platform claude` for Claude Code; the other options are in [Contributing](../contributing.md#build-and-install-locally):

   ```bash
   curl -sSL https://raw.githubusercontent.com/giangdhwhtbr/gin-workflow/master/remote-install.sh | bash -s -- --platform codex
   ```

2. If the installer warns that `~/.local/bin` is not on `PATH`, add it.
3. Run `gin-workflow --version`; it prints `gin-workflow 2.8`.

## OpenCode does not show the gin-workflow skills

Cause: the skill bundle is missing from `~/.config/opencode/skills/gin-workflow`, where OpenCode discovers global skills. The installer writes it when `--platform` is `opencode` or `all`, and does not need the `opencode` CLI on `PATH`. The bundle layout is in [Contributing](../contributing.md#build-and-install-locally).

1. Check the bundle: `ls ~/.config/opencode/skills/gin-workflow/skills`. If it is missing, run `./install.sh --platform opencode`.
2. Reload OpenCode, then list its skills to confirm they registered.

## Copilot does not list the gin-workflow plugin

Cause: the installer registers the bundle with `copilot plugin install` only when `copilot` is on `PATH`; otherwise it prints `Copilot CLI not found; skipped registration. Run: copilot plugin install <path>`. With `--project` it skips Copilot and warns `Copilot plugins are global; --project skips copilot.`

1. Run the `copilot plugin install <path>` command the installer printed, or rerun `./install.sh --platform copilot` without `--project`.
2. Check with `copilot plugin list` and `copilot skill list`.

## `gin-workflow: <path>/scripts/safety-check.sh not found, hook skipped`

Cause: the Copilot bundle's `hooks/hooks.json` runs `safety-check` before the `bash` tool and `post-edit` after `edit` and `create`. Each hook looks for its script under `$PLUGIN_ROOT`, or else under `~/.copilot/installed-plugins/_direct/gin-workflow` (`$COPILOT_HOME` replaces `~/.copilot` when set). Copilot does not set `PLUGIN_ROOT`. After a marketplace install the plugin is not in the `_direct` directory, so the hook prints this warning and lets the tool run. The hooks define only a `bash` command, so they do not run on Windows PowerShell.

1. Install with `./install.sh --platform copilot`, which installs from a local path into the `_direct` directory, or set `PLUGIN_ROOT` to the directory that holds the plugin's `scripts/`.
2. Run a shell command in Copilot; the warning no longer appears.

## `bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted`

Cause: on Ubuntu 24.04 and later, AppArmor restricts unprivileged user namespaces by default (`kernel.apparmor_restrict_unprivileged_userns=1`). The Codex CLI sandbox (`bwrap`) and the Antigravity CLI sandbox (`agy --sandbox`) both need one, so every sandboxed shell action, `apply_patch` included, fails for any file in any project. The restriction belongs to the host, not to gin-workflow, Codex CLI, or Antigravity CLI. gin-orchestrator avoids it only for the Codex workers it dispatches, which run `codex exec --dangerously-bypass-approvals-and-sandbox` inside their own worktree; a Codex session you start yourself, and Antigravity, still fail.

Fix it once per host, in an interactive terminal, because `sudo` prompts for a password:

1. Lift the restriction now and across reboots:

   ```bash
   # Take effect immediately
   sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=0

   # Persist across reboots
   echo 'kernel.apparmor_restrict_unprivileged_userns=0' | sudo tee /etc/sysctl.d/99-disable-userns-restrict.conf
   ```

2. Check the result:

   ```bash
   sysctl kernel.apparmor_restrict_unprivileged_userns   # should print 0
   codex sandbox -- echo hello                            # should print "hello", not a bwrap error
   ```

## A provider CLI that runs in your shell is reported unavailable

Cause: gin-orchestrator looks for each provider executable on the `PATH` of the process that runs it, then in a fixed list: `~/.npm-global/bin`, `~/.local/bin`, `~/.opencode/bin`, `~/.local/share/pnpm`, `/usr/local/bin`, and `/home/linuxbrew/.linuxbrew/bin`. Codex and Antigravity run commands without sourcing `~/.zshrc` or `~/.bashrc`. A CLI reachable only through a `PATH` entry added in those files is then not found. `gin-workflow setup doctor --probe --format json` reports it under `providers` as `executable_not_found`, or as `executable_or_help_unavailable` when its `--help` cannot run.

1. Link the CLI into `/usr/local/bin`, which is on the fixed list:

   ```bash
   sudo ln -s "$(which claude)" /usr/local/bin/claude
   ```

2. Check that it runs without your shell's `PATH` changes:

   ```bash
   env -i PATH="/usr/local/bin:/usr/bin:/bin" claude --version
   ```

3. Repeat for each other provider CLI (`codex`, `agy`, `opencode`) that a minimal `PATH` cannot reach.

## A repository still hits a `gin-workflow` bug that was already fixed and shipped on `master`

Cause: each harness runs the copy of the plugin taken at install time, and the `gin-workflow` CLI runs from its copy under `~/.local/lib/gin-workflow/2.8/`. Pushing a fix to `master` updates neither, even when the plugin version is unchanged. The steps below refresh the current host only; a machine that installed through a marketplace or `remote-install.sh` reruns its own install flow from [Installation](../../README.md#installation).

1. Commit the fix. Codex installs from the `git-subdir` source in `.claude-plugin/marketplace.json`, and a git source holds only committed content.
2. Refresh every install on the host:

   ```bash
   ./install.sh --platform all
   ```

   The installer replaces the CLI copy and recopies the Claude Code bundle to `~/.claude/skills/<plugin>` and the OpenCode bundle to `~/.config/opencode/skills/<plugin>`. It reruns `agy plugin install` for Antigravity. For Codex and Copilot it removes the registration and adds it again, because `codex plugin marketplace add` and `codex plugin add` do nothing for a name already registered. A harness CLI that is not on `PATH` is skipped. Use `--platform claude`, `codex`, `antigravity`, `opencode`, or `copilot` to refresh one harness.
3. Open a changed file in the refreshed install directory and check that it has the fix. For a Python fix, import the module from `~/.local/lib/gin-workflow/2.8/` and run the fixed code.

## `git push` exits 141 after the `pre-push` checks pass

Cause: git opens the SSH connection before `pre-push` runs, so a long test run lets the server close it as idle, and the push dies with SIGPIPE.

1. Run `gin-workflow hooks install`. It sets a repo-local `core.sshCommand` of `ssh -o ServerAliveInterval=30` unless `core.sshCommand`, `GIT_SSH`, or `GIT_SSH_COMMAND` is already set.
2. If you set one of them yourself, add `-o ServerAliveInterval=30` to your `core.sshCommand` or `GIT_SSH_COMMAND`.

## `Routing Decision: hold` from `gin-workflow state`

Cause: the router holds the workflow at the `progress` stage when a blocker is recorded, an approval check fails, or the capability for the next stage is disabled. `gin-workflow state` lists the reason under `Evidence:`, the fix under `Remedies:`, and each gate as `satisfied`, `waived`, or `unmet`.

1. Read the reason:

   ```bash
   gin-workflow state [--format text|json]
   ```

2. Apply the listed remedy. To waive a gate or clear a blocker on the record ([CLI](cli.md#gin-workflow-unblock)):
   - a process gate (`requirement_confirmed`, `plan_approved`, `orchestration_ready`):
     ```bash
     gin-workflow unblock --gate <gate> --reason "stated reason" --actor <your-id>
     ```
   - the safety gate `review_approved`, which also needs a follow-up task:
     ```bash
     gin-workflow unblock --gate <gate> --reason "stated reason" --actor <your-id> --follow-up <follow-up-task-id>
     ```
   - a recorded blocker:
     ```bash
     gin-workflow unblock --clear-blocker --reason "cleared blocker reason" --actor <your-id>
     ```

## `orchestrator_missing`, `orchestrator_contract_mismatch`, or `orchestrator_failed`

Cause: with `provider_mode: multi`, gin-workflow hands worker routing and reviews to `gin-orchestrator`, and each code says why it cannot. `orchestrator_missing`: `gin-orchestrator` is not on `PATH`. `orchestrator_contract_mismatch`: the installed `gin-orchestrator` reports a contract version other than 2. `orchestrator_failed`: `gin-orchestrator version` or a delegated command (`routes resolve`, `reviewer`, `doctor`) exited non-zero or printed invalid JSON. Work is not blocked. `gin-workflow state` and `setup doctor` warn `<code>; install with ./install.sh --plugin gin-orchestrator`, routes and reviews fall back to the main harness, and `setup models` lists no models.

1. Install or update the extension:

   ```bash
   ./install.sh --plugin gin-orchestrator
   ```

2. Run `gin-workflow setup doctor --probe`; the warning no longer appears.

## `.beads exists but providers.task_tracking is unset, so tasks use markdown`

Cause: `gin-workflow setup doctor` prints this when a `.beads` directory exists, `providers.task_tracking` is unset, and no `team:` block is configured. Tasks then use Markdown files ([`providers`](config.md#providers)).

To keep Beads as the task backend:

```bash
gin-workflow setup configure --set providers.task_tracking=beads --approve
```

To keep Markdown tasks, set `providers.task_tracking=markdown` the same way.
