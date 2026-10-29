# Using gin-workflow on Windows

This guide covers native installation, configuration, and day-to-day usage of `gin-workflow` on **Windows 10 / Windows 11**.

---

## 1. Prerequisites

### A. PowerShell 7+
Install modern PowerShell (pwsh) rather than Windows PowerShell 5.1:
```powershell
winget install Microsoft.PowerShell
```

### B. Python 3.10+
Install Python from python.org or via winget:
```powershell
winget install Python.Python.3.12
```
Ensure PyYAML is installed:
```powershell
pip install pyyaml
```

### C. Git for Windows
Install Git with symlink support enabled:
```powershell
winget install Git.Git
```

---

## 2. Environment Configuration

### A. Enable Developer Mode (Recommended for Symlinks)
`gin-workflow` and `git worktrees` use symbolic links. On Windows, creating symlinks without administrator privileges requires Developer Mode:
1. Open **Windows Settings** (`Win + I`).
2. Navigate to **System** $\rightarrow$ **For developers**.
3. Toggle **Developer Mode** to **On**.

Then configure Git to allow symlinks globally:
```powershell
git config --global core.symlinks true
```

### B. PowerShell Execution Policy
Allow executing signed or local scripts in PowerShell:
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### C. Line Endings (CRLF vs LF)
The repository includes `.gitattributes` to enforce `LF` for repository files. If configuring Git globally:
```powershell
git config --global core.autocrlf false
```

---

## 3. Installation

Run the native PowerShell installer `install.ps1` from the root of the cloned `gin-workflow` repository:

### Install for all AI harnesses (Claude, Antigravity, Copilot, Codex, OpenCode):
```powershell
pwsh -ExecutionPolicy Bypass -File .\install.ps1 -Platform all
```

### Install for a specific platform:
```powershell
# For Claude Code
pwsh -ExecutionPolicy Bypass -File .\install.ps1 -Platform claude

# For Antigravity
pwsh -ExecutionPolicy Bypass -File .\install.ps1 -Platform antigravity

# For GitHub Copilot CLI
pwsh -ExecutionPolicy Bypass -File .\install.ps1 -Platform copilot
```

### Install project-local into the current repository:
```powershell
pwsh -ExecutionPolicy Bypass -File .\install.ps1 -Project .
```

---

## 4. Task Tracking on Windows

`gin-workflow` supports two task tracking backends:

1. **Markdown (Default, Recommended for Windows)**:
   - Zero dependencies. Tasks and epics are stored as `.planning/tasks/*.md`.
   - Selected automatically during `/gin-workflow:setup` when `bd` is not installed.

2. **Beads (`bd`)**:
   - If you prefer Beads, install `bd` and `dolt` binaries for Windows and ensure they are on your system `PATH`.

---

## 5. Daily Usage & Lifecycle Commands

Inside your AI harness (Claude Code, Antigravity, etc.), use slash commands normally:

- `/gin-workflow:setup` — Initialize `.agent-workflow/config.yaml`.
- `/gin-workflow:discuss` — Requirement discovery and spec authoring.
- `/gin-workflow:plan` — Decompose specs into implementation plans.
- `/gin-workflow:orchestrate` — Worktree and task initialization.
- `/gin-workflow:execute` — Implement changes with test verification.
- `/gin-workflow:review` — Independent review cycles.
- `/gin-workflow:ship` — Close out tasks and merge.

From PowerShell terminal, you can interact directly with the CLI:
```powershell
# Check current workflow state
gin-workflow state

# Record a gate
gin-workflow record requirement-confirmed --evidence "docs/specs/my-feature.md" --actor user

# Query tasks
gin-workflow task list
```

---

## 6. Verifying Your Installation

Run the automated smoke test script to verify that installation, launchers, and CLI tools work cleanly on your machine:

```powershell
pwsh -ExecutionPolicy Bypass -File .\tests\install_smoke_test.ps1
```

All assertions should pass with zero exit code.

---

## 7. Troubleshooting

- **`PermissionError: [WinError 32]` or `[WinError 5]`**:
  - `gin-workflow` includes built-in retry logic for file locks and atomic file replacement on Windows.
  - If Windows Defender or an enterprise antivirus causes slow scans during test execution, consider adding a folder exclusion for your repository's `.planning/worktrees/` directory in Windows Security.
- **`EventPersistenceError: event persistence requires POSIX or Windows advisory file locking`**:
  - Make sure you are running a supported CPython release where the standard library module `msvcrt` is available.
- **Symlink creation errors (`OSError: [WinError 1314]`)**:
  - Verify that **Developer Mode** is turned ON in Windows Settings, or run PowerShell as Administrator.
