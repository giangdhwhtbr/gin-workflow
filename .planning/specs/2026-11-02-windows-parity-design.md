# Windows parity phase 2: native launcher, hooks, workers, and CI

Epic: gin-workflow-rm-windows-parity
Workflow: windows-parity
Status: draft for user review.

## Goal and scope

Every gin-workflow command, hook, and orchestrator worker runs on Windows 10/11 and macOS from a plain terminal after `install.ps1` or `install.sh`, with no Git Bash, WSL, or manual `PATH` edit, and CI proves it on every push and pull request.

Today `install.ps1` already writes a `.cmd` shim at `~\.local\bin\gin-workflow.cmd` (`install.ps1:364,418`) and `install.sh` links `~/.local/bin/gin-workflow` to a Python script with a shebang (`install.sh:478,521`). Neither installer puts `~/.local/bin` on `PATH`; both only warn (`install.sh:526`, `install.ps1:450`). The safety hook is a 211-line bash script that needs `jq` or `python3` (`scripts/safety-check.sh:13-29`). Orchestrator workers spawn with a POSIX-only environment allowlist and signal handling (`gin_orchestrator/native_cli.py:85-101,340-349,409-436`). There is no CI on push; `release.yml` runs tests only on tags.

In scope, as four tracks:
- A. Installers: `PATH` registration with an opt-out, the `.cmd` shim, `-Link` fallback.
- B. Safety hook ported to Python; `jq` dropped.
- C. Orchestrator and hook runner on Windows.
- D. CI on `ubuntu-latest` and `windows-latest`; documentation.

Out of scope:
- The `.beads` symlink on Windows: `docs/guides/windows.md` documents a junction or copy fallback only.
- `merge-integration.sh` (referenced nowhere).
- The `{env, argv}` form of `verify_commands` and a config schema bump: R10 covers the only failing case without a new config shape (decided in `/discuss`).
- Adding `encoding="utf-8"` to each `subprocess(text=True)` call: R3 puts the CLI process in UTF-8 mode instead, which covers every site in both packages (decided in `/discuss`).
- The `.beads.gate.lock` writer, Beads on Windows, and the Windows build of `bd`.

## Requirements

### Track A: installers, launcher, PATH

#### R1. `install.sh` registers `~/.local/bin` on `PATH`
After installing the gin-workflow launcher, when `~/.local/bin` is not in `PATH` and `--no-modify-path` was not passed, `install.sh` appends this block to the shell startup file chosen by the basename of `$SHELL`: `~/.zshrc` for `zsh`, `~/.bashrc` for `bash`:

```sh
# gin-workflow PATH
export PATH="$HOME/.local/bin:$PATH"
```

For any other shell, or with `--no-modify-path`, it prints the `export` line and the file to put it in instead of the current warning. The block is written once: a file that already contains the marker line `# gin-workflow PATH` is left unchanged. After writing, the installer prints that a new terminal (or `source <file>`) is needed. `--uninstall` removes the two-line block when present, using `python3` (already required) rather than `sed -i`, which differs between GNU and BSD. `--dry-run` prints what it would write. `remote-install.sh` passes its arguments through unchanged, so `--no-modify-path` works there too.

#### R2. `install.ps1` registers `.local\bin` on the user `PATH`
`install.ps1` gains `-NoModifyPath`. Without it, after installing the launcher, when the full path of `$UserHome\.local\bin` is not among the entries of the user-scope `PATH` (`[Environment]::GetEnvironmentVariable('Path', 'User')`, compared case-insensitively after `GetFullPath` and trailing-separator trimming, as `install.ps1:434-447` already does for the process `PATH`), it appends the absolute path (no `%USERPROFILE%`, so the registry value type does not matter) and writes it back with `SetEnvironmentVariable(..., 'User')`. It also prepends the directory to `$env:PATH` of the current process so the same session can run `gin-workflow`. It prints that other open terminals need restarting. `-Uninstall` removes exactly that entry from the user `PATH`. `-DryRun` prints the change without writing. With `-NoModifyPath`, the installer prints the directory to add instead of the warning.

#### R3. `.cmd` shim prefers `py -3` and runs Python in UTF-8 mode
The shim content becomes:

```bat
@echo off
where py >nul 2>nul
if %errorlevel%==0 (py -3 -X utf8 "<launcher>" %*) else (python -X utf8 "<launcher>" %*)
```

`py -3` comes first because the python.org installer always provides the `py` launcher but adds `python` to `PATH` only when the user ticks that option. `-X utf8` makes every `subprocess(text=True)` call in the CLI decode as UTF-8 instead of the ANSI code page, so no per-site `encoding=` change is needed. The exit code of the CLI is the exit code of the shim (no `||` chaining, which would rerun the CLI on a non-zero exit). `Test-ManagedLauncherShim` (`install.ps1:317`) accepts both the previous one-line `python "<launcher>" %*` content and the new content, so an upgrade from a 2.9 install is not refused, and still rejects any shim that points outside `~\.local\lib\<name>`. The same shim serves `gin-qa` and `gin-orchestrator`.

#### R4. `install.ps1 -Link` falls back to copying
When `New-Item -ItemType SymbolicLink` fails (`install.ps1:70-74`), the installer writes a warning naming the target and the Developer Mode remedy once, then copies the item instead of throwing. The rest of the install proceeds. The warning appears at most once per run.

### Track B: safety hook in Python

#### R5. `safety_check.py` replaces `safety-check.sh`
`plugins/gin-workflow/src/scripts/safety_check.py` reimplements `safety-check.sh` with the same inputs (hook JSON on stdin, or the command as the first argument for tests), the same decisions (`exit 2` with the same `Blocked:` and `Error:` messages, `exit 0` otherwise), and the same bash-escape decoding that `tests/test_safety_check.py` covers, including the `\c` cases fixed in `2db430c`. It needs only the standard library. `safety-check.sh` is deleted. The port is proven by `tests/test_safety_check.py` changing only its `SCRIPT` path and the `exit_code` invocation to `[sys.executable, str(SCRIPT), command]`; every existing test method keeps its assertions.

#### R6. Hook commands name a Python interpreter per platform
The hook command that each installer writes (`install.sh:203,222,242,260`; `install.ps1:128,141,164`) becomes `python3 "<root>/scripts/safety_check.py"` on POSIX and `python "<root>\scripts\safety_check.py"` on Windows (valid in cmd, PowerShell, and Git Bash). The source `plugins/gin-workflow/src/hooks/hooks.json`, used as-is by a Claude Code marketplace install, uses one shell line that runs `python3` when present and `python` otherwise, without running the script twice:

```sh
s="${PLUGIN_ROOT}/scripts/safety_check.py"; if command -v python3 >/dev/null 2>&1; then exec python3 "$s"; fi; exec python "$s"
```

The Copilot hook line keeps its "not found, hook skipped" behavior with the new file name. `README.md` drops the `jq` and Git Bash prerequisite rows; `docs/reference/troubleshooting.md` renames its `safety-check.sh` entry.

### Track C: orchestrator and hook runner on Windows

#### R7. Worker environment allowlist on Windows
`sanitized_environment` (`native_cli.py:85`) also keeps `SYSTEMROOT`, `USERPROFILE`, `APPDATA`, `LOCALAPPDATA`, `TEMP`, `TMP`, and `PATHEXT` when `os.name == "nt"`. On POSIX the allowlist is unchanged.

#### R8. Worker spawn and cancel on Windows
Before `subprocess.Popen` (`native_cli.py:340`), argv[0] is resolved with `shutil.which`; when the resolved file ends in `.cmd` or `.bat` (npm shims such as `claude.cmd`, `codex.cmd`), the process runs as `["cmd", "/c", resolved, *rest]`. On `nt`, `Popen` passes `creationflags=subprocess.CREATE_NEW_PROCESS_GROUP`, and `terminate_tree` (`native_cli.py:409`) runs `taskkill /T /F /PID <pid>` instead of `process.terminate()`, then falls back to `process.kill()` when `taskkill` fails; the POSIX `killpg` path is unchanged. The zombie check at `native_cli.py:395-398` keeps its `nt` branch.

#### R9. Executable resolver finds `.cmd` shims and npm's Windows directory
`workflow_core/executable_resolver.py` replaces the manual `is_file() and os.access(X_OK)` probe over `COMMON_INSTALL_DIRS` with `shutil.which(name, path=str(directory))`, which honors `PATHEXT` on Windows and is equivalent on POSIX. On `nt`, `COMMON_INSTALL_DIRS` also includes `%APPDATA%\npm` when `APPDATA` is set. The absolute-path and relative-path branches use the same `which` call so `claude` resolves to `claude.cmd`.

#### R10. Hook runner accepts a POSIX environment prefix
`_run_commands` in `workflow_core/hooks.py:100` splits leading `NAME=value` tokens (`[A-Za-z_][A-Za-z0-9_]*=` followed by a non-space value) off the command, puts them in the child environment, and runs the remainder through the shell as today. So `PYTHONPATH=plugins/gin-workflow/src/scripts python -m unittest tests.test_all` works through `cmd.exe`. The interpreter name stays the project's choice (`python3` on POSIX, `python` on Windows); this repository's own config keeps `python3` for its Linux CI. The printed `gin-workflow <hook>: <name>: <command>` line still shows the full configured command. A command with no prefix is unchanged. No config shape or schema version changes.

### Track D: CI and documentation

#### R11. Tests run on push and pull request on Linux and Windows
New `.github/workflows/test.yml` with `on: [push, pull_request]` and two jobs: `ubuntu-latest` runs `python -m unittest discover -s tests -v` and `tests/install_smoke_test.sh`; `windows-latest` runs the same unittest command with `PYTHONUTF8=1` in the job environment and `pwsh -File tests/install_smoke_test.ps1`. Both install `PyYAML` and `jsonschema` and set a git identity, as `release.yml` does. `release.yml` is unchanged. A test that depends on POSIX behavior (bash, `os.killpg`, symlinks that need Developer Mode, `chmod` bits) is marked `@unittest.skipIf(os.name == "nt", "<reason>")`; every other test passes on Windows. A skip without a reason is not accepted in review.

#### R12. Smoke tests cover PATH registration without touching the developer's environment
`tests/install_smoke_test.sh` runs the installer against its temporary `HOME` with `SHELL=/bin/zsh` and asserts the block in `$HOME/.zshrc` once after two installs, and absent after `--uninstall`; a `--no-modify-path` run leaves the file untouched. `tests/install_smoke_test.ps1` passes `-NoModifyPath` to every install it runs and asserts the `-DryRun` output names the `PATH` change; it writes the user `PATH` only when `GITHUB_ACTIONS` is set, where it asserts the entry after install and its absence after `-Uninstall`.

#### R13. Documentation
`docs/guides/windows.md`: the installer registers `PATH` (and `-NoModifyPath`), the shim uses `py -3` or `python`, hooks no longer need Git Bash or `jq`, and the `.beads` junction or copy fallback. `README.md`: prerequisites table without `jq` and Git Bash; one line that the installer adds `~/.local/bin` to `PATH` with an opt-out. `docs/contributing.md`: the `PATH` behavior at line 70 and the new CI workflow. `docs/reference/troubleshooting.md:13`: the opt-out flag. `docs/reference/cli.md` is unchanged (no CLI command changes).

## User Stories

### US-1: Install on Windows and run `gin-workflow` from a new terminal
As a Windows developer, I want `install.ps1` to put the launcher on my `PATH`, so that `gin-workflow` works in the next terminal I open without editing environment variables.

Acceptance criteria:
- After `pwsh -File .\install.ps1 -Platform claude`, a new `cmd` or PowerShell window runs `gin-workflow --help` successfully.
- The same session that ran the installer can run `gin-workflow --help`.
- Running the installer twice leaves one `.local\bin` entry in the user `PATH`.
- `-Uninstall` removes the entry; `-NoModifyPath` never writes it and prints the directory to add.

### US-2: Install on macOS or Linux and run `gin-workflow` from a new shell
As a macOS or Linux developer, I want `install.sh` to add `~/.local/bin` to my shell startup file, so that skills can call `gin-workflow` without a manual `PATH` edit.

Acceptance criteria:
- With `SHELL=/bin/zsh`, `install.sh` writes the marked block to `~/.zshrc` once across repeated installs; with `SHELL=/bin/bash`, to `~/.bashrc`.
- `--no-modify-path` writes nothing and prints the `export` line; `--uninstall` removes the block.
- `curl ... remote-install.sh | bash -s -- --no-modify-path` passes the flag through.

### US-3: Python found through the `py` launcher
As a Windows developer who installed Python without "Add to PATH", I want the shim to use `py -3`, so that `gin-workflow` runs anyway.

Acceptance criteria:
- With `py` present and `python` absent from `PATH`, `gin-workflow --help` runs through the shim.
- A failing CLI command exits the shim with the CLI's non-zero code and runs once.
- `gin-workflow state --format json` run through the shim decodes UTF-8 git output (a branch or path with Vietnamese characters) without `UnicodeDecodeError`.
- Reinstalling over a 2.9-era shim succeeds without "refusing to replace a different launcher".

### US-4: Safety hook without Git Bash or jq
As a Codex or Copilot user on Windows, I want the safety hook to run with Python alone, so that `--no-verify` and broad `rm -rf` are still blocked without installing Git Bash or `jq`.

Acceptance criteria:
- `tests/test_safety_check.py` passes against `safety_check.py` with only the invocation changed.
- A fresh install writes hook commands that run on `cmd`, PowerShell, and bash, and no installed file references `safety-check.sh`.
- A marketplace install (source `hooks.json`) runs the hook on a machine that has `python3` and on one that has only `python`.

### US-5: Orchestrator workers on Windows
As a gin-orchestrator user on Windows, I want workers to start, see their environment, and stop on cancel, so that routed tracks and reviews work natively.

Acceptance criteria:
- A worker configured as `claude` starts when only `claude.cmd` exists under `%APPDATA%\npm`.
- Cancelling a running worker ends the whole process tree within the cancellation timeout.
- A worker child process sees `SYSTEMROOT` and `TEMP` on Windows; the POSIX allowlist is unchanged (existing tests still pass).

### US-6: Verify command with an environment prefix runs through the git hooks on Windows
As a maintainer of this repository on Windows, I want `PYTHONPATH=... python -m unittest` in `verify.checks` to run from the pre-commit hook, so that I keep one config for every platform.

Acceptance criteria:
- `_run_commands` passes `PYTHONPATH` to the child and runs the rest through the shell; a unit test asserts the environment on both platforms.
- A command without a prefix behaves as before.

### US-7: CI proves both platforms on every push
As a maintainer, I want a Linux and a Windows job on each push and pull request, so that a Windows regression is caught before merge.

Acceptance criteria:
- `test.yml` runs on push and pull request; the Windows job runs unittest with `PYTHONUTF8=1` and `install_smoke_test.ps1`; the Linux job runs unittest and `install_smoke_test.sh`.
- Every `skipIf(os.name == "nt")` has a reason string.
- Both jobs are green on the epic's integration branch.

## Errors and compatibility

- `PATH` registration never edits a file or registry value that already contains the entry; a startup file that cannot be written (permission, missing `HOME`) produces a warning with the `export` line and a zero exit, because the install itself succeeded.
- `install.ps1` refuses to replace a shim it does not recognize (unchanged); the recognizer accepts the previous and the new content only.
- The `-Link` fallback copy leaves a working install; the warning tells the user that later edits to the source are not reflected until reinstall.
- `safety_check.py` exits 2 with `Error: failed to parse PreToolUse hook payload as JSON.` on malformed input, as the shell version does. A missing interpreter is an installer-time error, not a hook-time one: the installers already require Python 3.11.
- `taskkill` unavailable (non-standard Windows) falls back to `process.kill()` and reports the same `FailureKind.CRASH` message as today when the tree survives.
- The env-prefix parser only recognizes the strict `NAME=value` token shape; anything else is passed to the shell unchanged, so no existing command changes meaning.
- Config schema version stays `2.9`; no migration. `gin-console` reads `state --format json`, whose shape does not change.
- No launcher version bump in this epic: `is_managed_launcher_link` and `Test-ManagedLauncherShim` accept any managed version, so a 2.9 install upgrades in place; the release procedure (`docs/contributing.md`, Release step 1) bumps versions.
- `safety_check.py` parses the command one character per byte (UTF-8 bytes mapped through latin-1), matching `LC_ALL=C` in the shell version, so `\c` of a multibyte character takes its first byte.
- Nested `sh -c` and `eval` payloads are checked by an in-process recursive call with `depth + 1`; `SAFETY_CHECK_DEPTH` is still read as the starting depth and the "more than 3 levels deep" block is unchanged.

## Testing

- `tests/test_safety_check.py` against `safety_check.py` (invocation change only).
- New unit tests: `sanitized_environment` on `nt` (patched `os.name`), executable resolver finding a `.cmd` under a temp directory with `PATHEXT`, `_run_commands` env-prefix split, `Test-ManagedLauncherShim`-equivalent cases in `install_smoke_test.ps1` (old content accepted, foreign shim refused).
- `tests/install_smoke_test.sh`: `PATH` block written once, removed on uninstall, skipped with `--no-modify-path`.
- `tests/install_smoke_test.ps1`: shim content, `-NoModifyPath`, `-DryRun` output, `-Link` fallback warning; user `PATH` assertions only under `GITHUB_ACTIONS`.
- `.github/workflows/test.yml` green on `ubuntu-latest` and `windows-latest` is the acceptance evidence for the epic.
