# GitHub Copilot CLI as a skill-install platform

Status: draft for user review.

## Goal and scope

Let a user run the gin-workflow skills inside GitHub Copilot CLI (`copilot`), installed by the existing installers on Linux, macOS, and Windows 11.

Copilot is a skill host only. Routed workers and reviewers keep running through another installed CLI (`claude`, `codex`, `agy`, or `opencode`); `/setup` run from Copilot selects that CLI as `harness`. The workflow core (`SUPPORTED_HARNESSES`, providers, routing) does not change.

Copilot CLI loads plugins in the Claude layout: it reads `.claude-plugin/plugin.json` and discovers skills as `skills/<name>/SKILL.md` ([CLI plugin reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-plugin-reference)). Copying the bundle into `~/.copilot/skills/gin-workflow` (the OpenCode approach) does not work, because Copilot scans only immediate subdirectories there.

Out of scope, each a follow-up bead:
- a Copilot-format port of the `safety-check` and `post-edit` hooks;
- VS Code Copilot agent mode;
- a Copilot-only machine (no other CLI for workers and reviewers), including a Copilot worker adapter.

## Requirements

1. `install.ps1 -Platform copilot` and `install.sh --platform copilot` build `plugins/<plugin>/dist/copilot` from `src`: `.claude-plugin/plugin.json`, `skills/`, `references/`, `scripts/`, `templates/`, `rules/`, `examples/`. The bundle has no `hooks/` and no `agents/`.
2. `all` includes `copilot`.
3. When `copilot` is on `PATH`, the installer runs `copilot plugin install <absolute path to dist/copilot>`. When it is not, the installer builds the bundle, prints that registration was skipped and the command to run, and exits 0.
4. Dry run prints `would install Copilot plugin from <path>` and does not call `copilot`.
5. Uninstall runs `copilot plugin uninstall <plugin>` when `copilot` is on `PATH`, and removes `dist/copilot`.
6. A project install (`-Project` / `--project`) with the copilot platform prints a warning that Copilot plugins are global and skips copilot. The other selected platforms still install.
7. The `gin-workflow` launcher shim is linked exactly as for the other platforms.
8. The plugin version gets a minor bump in `plugin.meta.json` and the plugin manifests.

## User Stories

### US-1: Install gin-workflow into Copilot CLI
As a developer whose machine has Copilot CLI, I want the installer to register gin-workflow with Copilot, so that I can run the lifecycle skills there.

Acceptance criteria:
- `install.ps1 -Platform copilot` on Windows 11 with `copilot` on `PATH` registers the plugin, and `copilot plugin list` shows `gin-workflow`.
- `install.sh --platform copilot` does the same on Linux and macOS.
- In Copilot CLI, the `setup` and `workflow` skills can be invoked, and the invocation syntax is recorded in `docs/reference/skills.md`.

### US-2: Predictable behavior without Copilot or in a project install
As a developer running the installer, I want copilot handled safely when it does not apply, so that the other platforms are unaffected.

Acceptance criteria:
- Without `copilot` on `PATH`, the installer builds `dist/copilot`, prints the skip message with the manual command, and exits 0.
- `-DryRun` prints `would install Copilot plugin from <path>` and calls no `copilot` command.
- A project install that includes copilot prints the global-only warning and installs the other platforms.
- Uninstall removes `dist/copilot` and calls `copilot plugin uninstall gin-workflow` when `copilot` is present.

### US-3: Know the Copilot limits
As a Copilot user, I want the documentation to state what Copilot does not cover, so that I set up a worker CLI and do not count on the safety hook.

Acceptance criteria:
- README, `docs/contributing.md`, and the architecture build/install diagram list copilot as a platform.
- `docs/reference/troubleshooting.md` states that Copilot has no safety hook and that workers and reviewers need one of `claude`, `codex`, `agy`, or `opencode`.

## Errors and compatibility

- `copilot plugin install` failing: the installer prints the CLI's error and exits non-zero, matching how Claude registration failures are reported.
- Existing platforms: their `dist/` output and registration stay byte-for-byte the same. `all` now also builds `dist/copilot`.
- Re-running the install replaces the registered plugin. If `copilot plugin install` refuses an already-installed plugin, the installer uninstalls it first.
- Without the hooks, nothing blocks dangerous git commands inside Copilot. This is documented, and the hook port is a follow-up.

## Testing

- `tests/install_smoke_test.sh` and `tests/install_smoke_test.ps1`:
  - a copilot dry run produces `dist/copilot/skills/setup/SKILL.md` and `dist/copilot/.claude-plugin/plugin.json`, with no `hooks/` and no `agents/`, and prints the dry-run line;
  - with a stub `copilot` on `PATH`, the installer calls `plugin install <dist/copilot path>`, and uninstall calls `plugin uninstall gin-workflow`;
  - without `copilot`, the installer exits 0 and prints the skip message;
  - a project install with copilot prints the warning.
- `tests/workflow_providers/test_harness_packaging.py` covers the `dist/copilot` layout.
- Manual check against a real Copilot CLI: install, then invoke `setup` and `workflow`. The output is recorded as bead evidence; if no Copilot CLI is available, the bead says so.
