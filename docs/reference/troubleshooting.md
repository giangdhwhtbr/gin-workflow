# Troubleshooting

## `gin-workflow` is not on PATH after a marketplace install

Skills call the `gin-workflow` CLI (and `gin-qa` for the QA add-on). A marketplace install (`claude plugin install`, `codex plugin add`) copies the plugin but does not link the launcher, so stages fail with `gin-workflow: command not found`. Install the launcher with the installer, which links `~/.local/bin/gin-workflow`:

```bash
curl -sSL https://raw.githubusercontent.com/giangdhwhtbr/gin-workflow/master/remote-install.sh | bash -s -- --platform codex
```

Use `--platform claude` for Claude Code; installer options are in [Contributing](../contributing.md#build-and-install-locally). Make sure `~/.local/bin` is on `PATH`, then check with `gin-workflow --version`.


## OpenCode does not show the gin-workflow skills

OpenCode discovers global skills in `~/.config/opencode/skills`, and the installer writes the bundle to `~/.config/opencode/skills/gin-workflow` whenever `--platform opencode` (or `all`) runs. It does not need the `opencode` CLI on `PATH`. OpenCode scans nested `SKILL.md` files, so the `skills/<name>/SKILL.md` entries inside the bundle register as skills.

If they are missing:

- Check the bundle exists: `ls ~/.config/opencode/skills/gin-workflow/skills`.
- Reload OpenCode, then list skills to confirm registration.

The installer prunes the Claude/Codex `agents/` and `commands/` files from the OpenCode bundle (leaving a repository's own `.opencode/agents` and `.opencode/commands` untouched) and rewrites the Codex/Antigravity `${PLUGIN_ROOT}` variable to the absolute install path, because shell commands run from the agent's working directory. OpenCode has no `PreToolUse`/`PostToolUse` hook system, so the bundle's safety and post-edit hooks do not run there; lifecycle gates are still enforced by the `gin-workflow` CLI.

`gin-workflow`'s `report` skill installs as `gin-workflow-report` in OpenCode. Its original id would otherwise shadow OpenCode's built-in `report` skill, so invoke it with `@gin-workflow-report`; the built-in `report` skill keeps working.

OpenCode hosts the skills and can also run routed workers and reviews (`opencode run --auto --format json`); it has no sandbox, so isolation relies on the worktree. The resolver also looks in `~/.opencode/bin`, so a binary installed by OpenCode's own script is found without a `PATH` change. See [Providers](../concepts/providers.md).


## Codex/Antigravity sandbox fails with `bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted`

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

## Review routing reports a provider as "not available" (e.g. `claude not available`) when invoked from Codex/Antigravity

gin-workflow's routed dispatcher (`registry.py`) health-checks a native provider by running `<executable> --help` in a subprocess with a *sanitized* environment (`native_cli.py`'s `sanitized_environment()`/`probe_help()`) — it forwards `PATH` from whatever process is running the gin-workflow script, but that process's `PATH` did not come from your interactive shell's rc file. If a provider's CLI binary is only reachable because `~/.zshrc`/`~/.bashrc` prepends a directory to `PATH` (for example, an npm global install landing in `~/.npm-global/bin`), it resolves fine in an interactive shell but fails when gin-workflow is driven by Codex or Antigravity, whose exec/sandbox environments don't source your shell rc files. The health check then can't even launch the binary, and the dispatcher reports it as unavailable — well before any quota, auth, or model issue.

Fix by putting the CLI binary somewhere already on the default system `PATH` (not dependent on shell rc files), e.g.:

```bash
sudo ln -s "$(which claude)" /usr/local/bin/claude
```

Verify it resolves independent of your shell's `PATH` customizations:
```bash
env -i PATH="/usr/local/bin:/usr/bin:/bin" claude --version
```

Apply the same fix for any other native provider CLI (`codex`, `agy`, `opencode`) that isn't already reachable from a minimal `PATH`.

## A repository still hits a `gin-workflow` bug that was already fixed and shipped on `master`

Harness plugin managers install `gin-workflow` by snapshotting its files into a local cache at install time (e.g. Codex's `~/.codex/plugins/cache/<marketplace>/gin-workflow/<version>/`, Claude Code's global skills directory). That snapshot is not a live view of this repository — pushing a fix to `master` does not, by itself, update any consuming repository's cached install, even when the plugin's declared version number hasn't changed. A repository on the same host can keep failing with the exact symptoms of an already-fixed bug simply because its cached snapshot predates the fix.

After shipping a fix in this repository, refresh every installed platform's cache on the host:

```bash
./install.sh --platform all
```

The fix must be **committed** first. Codex's marketplace registration uses a `git-subdir` source (see `.claude-plugin/marketplace.json`) that reads the plugin's tree from the repository's committed `HEAD`, not the working directory — re-running the install with only an uncommitted change staged or edited will re-register the plugin successfully but still snapshot the pre-fix content.

This is safe to re-run any time — for Codex it explicitly removes and re-adds the plugin/marketplace registration (`codex plugin marketplace add`/`plugin add` are no-ops when already registered by name, and the local-source snapshot is only taken at add-time, so a plain repeat run would keep serving the stale snapshot without the explicit remove-then-add), and for Claude Code, Antigravity, and OpenCode it recopies the compiled `dist/` output into the global install location. Use `--platform codex`/`claude`/`antigravity`/`opencode` to target just one. This only refreshes installs on the current host; a consumer on a different machine (installed via the GitHub marketplace or `remote-install.sh`) needs to re-run its own install or update flow from [Installation](../../README.md#installation).

Verify the fix actually landed by checking a changed file's content inside the refreshed install directory (or, for a Python fix, importing the module from that path and exercising the fixed behavior directly) rather than assuming a successful install command means the fix is present.

## Workflow is held at `progress` or a gate is blocked

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
- For the **safety gate** (`review_approved`):
  ```bash
  gin-workflow unblock --gate <gate> --reason "stated reason" --actor <your-id> --follow-up <follow-up-task-id>
  ```
- To **clear a task-tracking blocker**:
  ```bash
  gin-workflow unblock --clear-blocker --reason "cleared blocker reason" --actor <your-id>
  ```
