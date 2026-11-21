# Troubleshooting

## `gin: command not found` after a marketplace install

Cause: a marketplace install (`claude plugin install`, `codex plugin add`) copies the plugin but does not link the `gin` launcher that the skills call, or the `gin-qa` launcher of the QA add-on. Only the installer links them, at `~/.local/bin/gin` and `~/.local/bin/gin-qa`.

1. Run the installer, with `--platform claude` for Claude Code and `--plugin all` to add `gin-qa`; the other options are in [Contributing](../contributing.md#build-and-install-locally):

   ```bash
   curl -sSL https://raw.githubusercontent.com/giangdhwhtbr/gin-workflow/master/remote-install.sh | bash -s -- --platform codex
   ```

2. If you installed with `--no-modify-path`, add `~/.local/bin` to `PATH`.
3. Run `gin --version`; it prints `gin X.Y.Z`, the release version.

## `gin` runs `Get-ComputerInfo` in PowerShell

Cause: PowerShell has a built-in `gin` alias for `Get-ComputerInfo`, and an alias wins over the `~/.local/bin/gin.cmd` launcher. `install.ps1` removes the alias with a marked block in `profile.ps1` under `Documents\PowerShell` and `Documents\WindowsPowerShell`. The alias stays when the profile has no block (an install with `-NoModifyPath`) or does not run (`-NoProfile`, or an execution policy that blocks scripts).

1. Type `gin.cmd` instead of `gin`, for example `gin.cmd --version`.
2. Or rerun `install.ps1` without `-NoModifyPath`, or add the block's lines to your profile (`notepad $PROFILE`) yourself. The alias comes from the `Microsoft.PowerShell.Management` module, so import it first; otherwise its later automatic load brings the alias back:

   ```powershell
   Import-Module Microsoft.PowerShell.Management
   Remove-Item Alias:gin -Force -ErrorAction SilentlyContinue
   ```

3. Open a new terminal and run `Get-Command gin`; it shows `gin.cmd` with the type `Application`.

## OpenCode does not show the gin skills

Cause: the skill bundle is missing from `~/.config/opencode/skills/gin`, where OpenCode discovers global skills. The installer writes it when `--platform` is `opencode` or `all`, and does not need the `opencode` CLI on `PATH`. The bundle layout is in [Contributing](../contributing.md#build-and-install-locally).

1. Check the bundle: `ls ~/.config/opencode/skills/gin/skills`. If it is missing, run `./install.sh --platform opencode`.
2. Reload OpenCode, then list its skills to confirm they registered.

## Copilot does not list the gin plugin

Cause: the installer registers the bundle with `copilot plugin install` only when `copilot` is on `PATH`; otherwise it prints `Copilot CLI not found; skipped registration. Run: copilot plugin install <path>`. With `--project` it skips Copilot and warns `Copilot plugins are global; --project skips copilot.`

1. Run the `copilot plugin install <path>` command the installer printed, or rerun `./install.sh --platform copilot` without `--project`.
2. Check with `copilot plugin list` and `copilot skill list`.

## `gin: <path>/scripts/safety_check.py not found, hook skipped`

Cause: the Copilot bundle's `hooks/hooks.json` runs `scripts/safety_check.py` with `python3` before the `bash` tool. The hook looks for its script under `$PLUGIN_ROOT`, or else under `~/.copilot/installed-plugins/_direct/gin` (`$COPILOT_HOME` replaces `~/.copilot` when set). Copilot does not set `PLUGIN_ROOT`. After a marketplace install the plugin is not in the `_direct` directory, so the hook prints this warning and lets the tool run. The hook defines only a `bash` command, so it does not run on Windows PowerShell.

1. Install with `./install.sh --platform copilot`, which installs from a local path into the `_direct` directory, or set `PLUGIN_ROOT` to the directory that holds the plugin's `scripts/`.
2. Run a shell command in Copilot; the warning no longer appears.

## `bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted`

Cause: on Ubuntu 24.04 and later, AppArmor restricts unprivileged user namespaces by default (`kernel.apparmor_restrict_unprivileged_userns=1`). The Codex CLI sandbox (`bwrap`) and the Antigravity CLI sandbox (`agy --sandbox`) both need one, so every sandboxed shell action, `apply_patch` included, fails for any file in any project. The restriction belongs to the host, not to gin-workflow, Codex CLI, or Antigravity CLI. A Codex session and an Antigravity session both fail until the restriction is lifted.

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

## A CLI works in your shell but gin-workflow reports it missing or uses an old copy

Cause: `.agent-workflow/executables.local.yaml` records the path found when `setup` last ran, and `setup doctor` lists stale entries under `checks_details.executables`. Run `gin setup refresh` to record the current paths, or edit the file. See [`executables.local.yaml`](config.md#executableslocalyaml).

## A repository still hits a gin-workflow bug that was already fixed and shipped on `master`

Cause: each harness runs the copy of the plugin taken at install time, and the `gin` CLI runs from its copy under `~/.local/lib/gin/<version>/`. Pushing a fix to `master` updates neither, even when the plugin version is unchanged. The steps below refresh the current host only; a machine that installed through a marketplace or `remote-install.sh` reruns its own install flow from [Installation](https://github.com/giangdhwhtbr/gin-workflow/blob/master/README.md#installation).

1. Commit the fix. Codex installs from the `git-subdir` source in `.claude-plugin/marketplace.json`, and a git source holds only committed content.
2. Refresh every install on the host:

   ```bash
   ./install.sh --platform all
   ```

   The installer replaces the CLI copy and recopies the Claude Code bundle to `~/.claude/skills/<plugin>` and the OpenCode bundle to `~/.config/opencode/skills/<plugin>`. It reruns `agy plugin install` for Antigravity. For Codex and Copilot it removes the registration and adds it again, because `codex plugin marketplace add` and `codex plugin add` do nothing for a name already registered. A harness CLI that is not on `PATH` is skipped. Use `--platform claude`, `codex`, `antigravity`, `opencode`, or `copilot` to refresh one harness.
3. Open a changed file in the refreshed install directory and check that it has the fix. For a Python fix, import the module from `~/.local/lib/gin/<version>/` and run the fixed code.

## `git push` exits 141 after the `pre-push` checks pass

Cause: git opens the SSH connection before `pre-push` runs, so a long test run lets the server close it as idle, and the push dies with SIGPIPE.

1. Run `gin hooks install`. It sets a repo-local `core.sshCommand` of `ssh -o ServerAliveInterval=30` unless `core.sshCommand`, `GIT_SSH`, or `GIT_SSH_COMMAND` is already set.
2. If you set one of them yourself, add `-o ServerAliveInterval=30` to your `core.sshCommand` or `GIT_SSH_COMMAND`.

## `Routing Decision: hold` from `gin state`

Cause: the router holds the workflow at the `progress` stage when a blocker is recorded, an approval check fails, a gate is `unknown`, or the capability for the next stage is disabled. `gin state` lists the reason under `Evidence:`, the fix under `Remedies:`, and each gate as `satisfied`, `waived`, `unmet`, or `unknown`. A gate is `unknown` when `state` cannot read the task tracker or the event log. Its remedy names the cause: `tracker unavailable: <cause>` or `event log unreadable: <error>; waivers not applied`.

1. Read the reason:

   ```bash
   gin state [--format text|json]
   ```

2. Apply the listed remedy. For an `unknown` gate, restore the task tracker or the event log named in the remedy, then rerun `gin state`; do not waive that gate. To waive a gate or clear a blocker on the record ([CLI](cli.md#gin-unblock)):
   - a process gate (`requirement_confirmed`, `plan_approved`, `orchestration_ready`):
     ```bash
     gin unblock --gate <gate> --reason "stated reason" --actor <your-id>
     ```
   - the safety gate `review_approved`, which also needs a follow-up task:
     ```bash
     gin unblock --gate <gate> --reason "stated reason" --actor <your-id> --follow-up <follow-up-task-id>
     ```
   - a recorded blocker:
     ```bash
     gin unblock --clear-blocker --reason "cleared blocker reason" --actor <your-id>
     ```

## `orchestrator, provider_mode, and routing.review.independence are ignored since gin 3.3.0`

Cause: the configuration is below schema 2.11 and still holds one of the keys the worker extension used. gin 3.3.0 runs every stage in the main harness, so `gin state` warns and `gin setup doctor` lists one action; nothing else changes. A schema 2.11 configuration that holds one of them is refused with `<key> was removed in schema 2.11`.

Fix: remove the keys with the update. Role names found only under `orchestrator.roles` move to `routing.roles`.

```bash
gin setup update --to-version 2.11 --approve
```

## `.beads exists but providers.task_tracking is unset, so tasks use markdown`

Cause: `gin setup doctor` prints this when a `.beads` directory exists, `providers.task_tracking` is unset, and no `team:` block is configured. Tasks then use Markdown files ([`providers`](config.md#providers)).

To keep Beads as the task backend:

```bash
gin setup configure --set providers.task_tracking=beads --approve
```

To keep Markdown tasks, set `providers.task_tracking=markdown` the same way.

## `gin <version> is older than this project needs`

Cause: `.ginrc` in the project pins a gin version higher than the one installed, so every `gin` command that reads the project stops, `gin hooks run` included. The git commit and push hooks fail with it.

1. Update gin on your machine as the [upgrade guide](../guides/upgrading.md#update-a-machine) describes.
2. Run `gin version` and check for `compatible: yes`.

## Upgrading from gin-workflow 2.x

Version 3.0 renames the CLI to `gin` and the skills to the `gin:` namespace (`/gin:discuss`, `gin:learn`), with no `gin-workflow` alias. `./install.sh` installs `gin` and removes the old `gin-workflow` launcher and plugin installs it manages. It also reinstalls the gin-qa add-on when the installer manages its launcher, so it calls `gin`; a `--project` install refreshes that launcher too but writes only the plugins named on the command line into the project. A global install also reinstalls gin-ba when `~/.claude/skills/gin-ba` exists, since gin-ba has no launcher.

In each repository, run `gin hooks install`, then `gin setup refresh`; with team mode, also `gin team init`. A hook installed before 3.0 stops the commit with `gin-workflow is not on PATH`, so no check is skipped silently. `gin setup doctor` reports what is still on the old name.

A plugin installed with `claude plugin install gin-workflow@gin-workflow-marketplace` is not upgraded in place: run `claude plugin uninstall gin-workflow`, then `claude plugin install gin@gin-workflow-marketplace`. Scripts and CI jobs that call `gin-workflow` need `gin` instead; the `GIN_WORKFLOW_*` variables keep their names. For the move to 3.1, see the [upgrade guide](../guides/upgrading.md).
