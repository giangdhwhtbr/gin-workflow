# Using gin-workflow on Windows

This guide covers native installation, configuration, and daily use of `gin-workflow` on Windows 10 and Windows 11.

## Prerequisites

### PowerShell 7
`install.ps1` requires PowerShell 7 (`#requires -Version 7.0`), so install `pwsh` instead of Windows PowerShell 5.1:
```powershell
winget install Microsoft.PowerShell
```

### Python 3.11

Install Python 3.11 or later from python.org or with winget. `rules_checks.py` imports `tomllib`, which exists from 3.11, and `setup preset` and `setup doctor` load it. The launcher shim calls `python`, so it must be on `PATH`:
```powershell
winget install Python.Python.3.12
```
Install PyYAML, which the CLI needs to read its configuration:
```powershell
pip install pyyaml
```

### Git for Windows
Install Git:
```powershell
winget install Git.Git
```

## Environment configuration

### Developer Mode

Only `install.ps1 -Link` creates symbolic links. Creating them without administrator privileges requires Developer Mode:
1. Open **Windows Settings** (`Win + I`).
2. Go to **System**, then **For developers**.
3. Toggle **Developer Mode** to **On**.

### Execution policy
Allow local scripts to run in PowerShell:
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### Line endings
The repository's `.gitattributes` sets `LF` for repository files and `CRLF` for `*.ps1`, `*.bat`, and `*.cmd`. To stop Git from converting line endings globally:
```powershell
git config --global core.autocrlf false
```

## Installation

Run `install.ps1` from the root of the cloned `gin-workflow` repository:

### Install for all platforms (Claude, Antigravity, Copilot, Codex, OpenCode)
```powershell
pwsh -ExecutionPolicy Bypass -File .\install.ps1 -Platform all
```

### Install for one platform
```powershell
# For Claude Code
pwsh -ExecutionPolicy Bypass -File .\install.ps1 -Platform claude

# For Antigravity
pwsh -ExecutionPolicy Bypass -File .\install.ps1 -Platform antigravity

# For GitHub Copilot CLI
pwsh -ExecutionPolicy Bypass -File .\install.ps1 -Platform copilot
```

### Install into the current repository
```powershell
pwsh -ExecutionPolicy Bypass -File .\install.ps1 -Project .
```

## Task tracking

`gin-workflow` supports two task tracking backends:

1. Markdown, the default. It needs no extra tools and stores tasks and epics as `.planning/tasks/*.md`. `/gin-workflow:setup` asks which backend to use and proposes Markdown by default.
2. Beads (`bd`). Install the `bd` and `dolt` binaries for Windows and put them on `PATH`.

## Daily use

Inside your AI harness (Claude Code, Antigravity, and others), use the slash commands:

- `/gin-workflow:setup`: initialize `.agent-workflow/config.yaml`.
- `/gin-workflow:discuss`: discover requirements and write the spec.
- `/gin-workflow:plan`: turn specs into implementation plans.
- `/gin-workflow:orchestrate`: create worktrees and initialize tasks.
- `/gin-workflow:execute`: implement changes and verify them with tests.
- `/gin-workflow:review`: run independent review cycles.
- `/gin-workflow:ship`: close out tasks and merge.

From a PowerShell terminal, call the CLI directly:
```powershell
# Check current workflow state
gin-workflow state

# Record a gate
gin-workflow record requirement-confirmed --evidence "docs/specs/my-feature.md" --actor user

# Query tasks
gin-workflow task list
```

## Verifying the installation

Run the smoke test to check the installation, launchers, and CLI:

```powershell
pwsh -ExecutionPolicy Bypass -File .\tests\install_smoke_test.ps1
```

A passing run exits with code 0.

## Troubleshooting

### `PermissionError: [WinError 32]` or `[WinError 5]`

`gin-workflow` retries file locks and atomic file replacement on Windows (`workflow_core/atomic.py`). If Windows Defender or another antivirus slows test runs, add a folder exclusion for the repository's `.planning/worktrees/` directory in Windows Security.

### `EventPersistenceError: cannot lock ...: file locking requires POSIX or Windows advisory file locking`

Run a CPython build that provides the standard library module `msvcrt`.

### `OSError: [WinError 1314]` when creating a symlink

Turn on Developer Mode in Windows Settings, or run PowerShell as Administrator. Only `install.ps1 -Link` creates symlinks.
