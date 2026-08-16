# Plan: Installer Upgrades and Native Windows Support

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Every behavior change follows red-green-refactor. Do not commit or push unless the user explicitly authorizes it.

## Objective

Upgrade launcher links and shims created by older gin-workflow releases without weakening collision protection, and add a native PowerShell 7 installer that matches the supported Unix installer contract.

## Model Guidance

- `default_model_class`: `standard_impl`
- `phase_guidance`:
  - `brainstorm`: `high_reasoning`
  - `design`: `high_reasoning`
  - `plan`: `standard_impl`
  - `implement`: `standard_impl`
  - `verify`: `standard_impl`
  - `review`: `high_reasoning`
  - `docs`: `cheap_simple`
- `override_rule`: Use `high_reasoning` for review of launcher ownership checks because an overly broad predicate could overwrite an unrelated executable.

## Requirement Analysis

- Problem statement: `install.sh` accepts only a link to the current launcher version, so a valid link installed by version 2.1 is rejected when 2.2 attempts to upgrade it. Windows users have no native installer.
- Success criteria: managed Unix links and managed Windows shims upgrade to 2.2; foreign launchers remain byte-for-byte untouched; PowerShell 7 supports dry-run, global, project, link, and uninstall flows for all three harness layouts; documentation and automated smoke tests cover the behavior.
- Constraints: PowerShell 7 is the Windows minimum; launcher version remains `2.2`; Unix paths remain under `$HOME/.local`; Windows uses the same `$HOME/.local` hierarchy and a `.cmd` shim; installers must not modify persistent `PATH`; older launcher payload directories must remain available; no commit or push without explicit authorization.
- Non-goals: changing workflow/configuration schemas, changing lifecycle behavior, removing old launcher versions, changing `remote-install.sh`, supporting Windows PowerShell 5.1, or silently installing Python/PowerShell/harness CLIs.

## Approach Options

### Option 1: Native shell implementations with the same behavioral contract

- Summary: Harden `install.sh` in place and add a PowerShell-native `install.ps1`, with platform-specific smoke suites encoding matching safety behavior.
- Pros: Native user experience on Unix and Windows; minimal change to the existing Unix architecture; foreign launcher protection remains explicit.
- Cons: Some installer logic exists in both shell languages and must be kept behaviorally aligned.

### Option 2: PowerShell wrapper around Git Bash

- Summary: Invoke `install.sh` from PowerShell through Git Bash.
- Pros: Little duplicated logic.
- Cons: Not native Windows support and adds an undeclared Git Bash dependency.

### Option 3: Shared Python installer core

- Summary: Move installation behavior into Python and make both scripts thin wrappers.
- Pros: One implementation of most logic.
- Cons: Large refactor, broader regression surface, and unnecessary migration work for the requested behavior.

### Recommended Approach

- Selected option: Option 1.
- Reasoning: It delivers native PowerShell 7 support while keeping the Unix fix narrow. Contract-focused tests offset the small amount of duplicated installer logic.

## Scope

- In scope: `install.sh`, new `install.ps1`, Unix and PowerShell smoke tests, README installation instructions, and the repository structure listing.
- Out of scope: `remote-install.sh`, workflow core Python behavior, plugin source content, schema/version changes, and automatic deletion of older launcher payloads.

## Technical Approach and File Map

- `install.sh`: add a strict `is_managed_launcher_link` predicate; permit only exact versioned paths beneath `$HOME/.local/lib/gin-workflow`; atomically retarget a valid managed link after the new payload is copied.
- `tests/install_smoke_test.sh`: reproduce the 2.1-to-2.2 failure first, then protect foreign regular files and foreign symbolic links.
- `install.ps1`: own PowerShell parameter validation, layout generation/copying, native harness registration, managed launcher payload installation, and `.cmd` shim safety.
- `tests/install_smoke_test.ps1`: exercise PowerShell behavior only through public installer invocations in temporary homes and repositories.
- `README.md`: document PowerShell 7 commands, parameters, PATH behavior, and the additional installer file.

## Tasks

### Track 1: Safely upgrade managed Unix launcher links

- **Dependencies**: none
- **Files**: `tests/install_smoke_test.sh`, `install.sh`
- **Model class**: `standard_impl`
- **Interfaces**:
  - Consumes: `LAUNCHER_VERSION`, `$HOME`, and the current `install_launcher` flow.
  - Produces: `is_managed_launcher_link <link> <managed-root>` returning success only for exact `$managed_root/<one-version-component>/gin-workflow` symlink targets.
- **Acceptance criteria**: A simulated 2.1 managed link upgrades to 2.2; a regular file, a foreign symlink, and a malformed path under the managed root all fail without modification; current-version reinstall remains idempotent.
- **Estimated complexity**: medium

- [ ] **Step 1: Add the failing managed-upgrade smoke case**

  Append a temporary `UPGRADE_HOME` case before the collision cases in `tests/install_smoke_test.sh`:

  ```bash
  UPGRADE_HOME="$(mktemp -d)"
  mkdir -p "$UPGRADE_HOME/.local/lib/gin-workflow/2.1" "$UPGRADE_HOME/.local/bin"
  printf '%s\n' '#!/usr/bin/env python3' > "$UPGRADE_HOME/.local/lib/gin-workflow/2.1/gin-workflow"
  ln -s "$UPGRADE_HOME/.local/lib/gin-workflow/2.1/gin-workflow" "$UPGRADE_HOME/.local/bin/gin-workflow"
  HOME="$UPGRADE_HOME" ./install.sh --platform claude >/dev/null
  expected_target="$UPGRADE_HOME/.local/lib/gin-workflow/2.2/gin-workflow"
  actual_target="$(readlink "$UPGRADE_HOME/.local/bin/gin-workflow")"
  if [ "$actual_target" != "$expected_target" ]; then
    echo "Expected managed launcher upgrade to target $expected_target, got $actual_target" >&2
    exit 1
  fi
  ```

- [ ] **Step 2: Run the Unix smoke suite and verify the regression fails for the intended reason**

  Run: `bash tests/install_smoke_test.sh`

  Expected: non-zero exit with `Error: refusing to replace a different launcher` during the new upgrade case.

- [ ] **Step 3: Add strict managed-link recognition and retargeting**

  Add this contract near `install_launcher` in `install.sh`, using quoted variables and shell pattern matching that rejects nested or empty version components:

  ```bash
  is_managed_launcher_link() {
    local launcher_link="$1"
    local managed_root="$2"
    local target version
    [ -L "$launcher_link" ] || return 1
    target="$(readlink "$launcher_link")"
    case "$target" in
      "$managed_root"/*/gin-workflow) ;;
      *) return 1 ;;
    esac
    version="${target#"$managed_root"/}"
    version="${version%/gin-workflow}"
    [ -n "$version" ] &&
      [ "$version" != "." ] &&
      [ "$version" != ".." ] &&
      [ "${version#*/}" = "$version" ]
  }
  ```

  In `install_launcher`, set `managed_root="${HOME}/.local/lib/gin-workflow"`, accept the current target or `is_managed_launcher_link`, copy the payload, and run `ln -sfn "$launcher_target" "$launcher_link"` only after the copy succeeds. Preserve the existing collision message for all rejected paths.

- [ ] **Step 4: Run the smoke suite and verify green**

  Run: `bash tests/install_smoke_test.sh`

  Expected: exit 0 and the mock launcher reports `gin-workflow 2.2`.

- [ ] **Step 5: Add foreign-link and malformed-managed-link regression cases**

  Create isolated homes whose launcher links point to `/tmp/not-gin-workflow` and `$HOME/.local/lib/gin-workflow/2.1/nested/gin-workflow`. For each invocation, assert non-zero status, assert output contains `refusing to replace a different launcher`, and assert `readlink` still returns the original target.

- [ ] **Step 6: Re-run syntax and Unix installer checks**

  Run:

  ```bash
  bash -n install.sh
  bash tests/install_smoke_test.sh
  ```

  Expected: both commands exit 0.

### Track 2: Add native PowerShell layout installation

- **Dependencies**: Track 1
- **Files**: create `install.ps1`, create `tests/install_smoke_test.ps1`
- **Model class**: `standard_impl`
- **Interfaces**:
  - Consumes: `plugins/gin-workflow/plugin.meta.json` and `plugins/gin-workflow/src/{commands,skills,agents,scripts,references,examples,hooks}`.
  - Produces: `install.ps1` parameters `Platform`, `Plugin`, `Link`, `Project`, `Uninstall`, and `DryRun`; functions `Test-Platform`, `Copy-PluginSource`, `New-PluginManifest`, `Install-PlatformLayout`, and `Install-Plugin`.
- **Acceptance criteria**: PowerShell dry-run and project installation produce the same required Claude, Antigravity, and Codex layouts as the Unix installer; invalid parameters and missing project paths fail before writes; uninstall removes only generated dist directories.
- **Estimated complexity**: high

- [ ] **Step 1: Write the failing PowerShell dry-run and project-layout tests**

  Create `tests/install_smoke_test.ps1` with `$ErrorActionPreference = 'Stop'`, a temporary HOME, assertion helpers, and public invocations such as:

  ```powershell
  $output = & pwsh -NoProfile -File $Installer -Platform codex -DryRun 2>&1 | Out-String
  Assert-Contains $output 'would install gin-workflow launcher version 2.2'
  Assert-Exists (Join-Path $Root 'plugins/gin-workflow/dist/codex/.codex-plugin/plugin.json')

  $project = Join-Path $testRoot 'project'
  New-Item -ItemType Directory -Path $project | Out-Null
  & pwsh -NoProfile -File $Installer -Platform all -Project $project
  Assert-Exists (Join-Path $project '.claude/commands/setup.md')
  Assert-Exists (Join-Path $project '.agents/commands/setup.md')
  Assert-Exists (Join-Path $project '.codex/commands/setup.md')
  ```

  The test must restore the original `HOME` and delete its temporary root in `finally`.

- [ ] **Step 2: Verify the PowerShell suite fails because `install.ps1` is absent**

  Run: `pwsh -NoProfile -File tests/install_smoke_test.ps1`

  Expected when PowerShell 7 is installed: non-zero exit identifying the missing `install.ps1`. If `pwsh` is unavailable, record that execution limitation and continue writing the test; do not report it as passing.

- [ ] **Step 3: Implement parameter validation and shared helpers in `install.ps1`**

  Start the file with:

  ```powershell
  #requires -Version 7.0
  [CmdletBinding()]
  param(
      [ValidateSet('claude', 'antigravity', 'codex', 'both', 'all')]
      [string]$Platform = 'all',
      [ValidateSet('gin-workflow', 'all')]
      [string]$Plugin = 'gin-workflow',
      [switch]$Link,
      [string]$Project,
      [switch]$Uninstall,
      [switch]$DryRun
  )
  Set-StrictMode -Version Latest
  $ErrorActionPreference = 'Stop'
  $LauncherVersion = '2.2'
  $ScriptRoot = $PSScriptRoot
  ```

  Implement `Test-Platform` to treat `both` and `all` as matches, validate and normalize `Project` with `[IO.Path]::GetFullPath`, and use `ConvertFrom-Json`/`ConvertTo-Json -Depth 10` for manifests and Claude settings. Do not interpolate repository paths into executable code.

- [ ] **Step 4: Implement layout copying and hook generation**

  `Copy-PluginSource` creates the six supported content directories and copies or symbolic-links each source child. `Install-PlatformLayout` generates platform-specific hooks and manifests, including the Codex `.codex-plugin/plugin.json` and Antigravity schema URI. Agent templating for Claude replaces `view_file`, `grep_search`, `list_dir`, `search_web`, and `run_command` with their Claude tool names.

  Keep all filesystem writes behind a `DryRun` check except dist generation, matching `install.sh`: dry-run may rebuild repository-local `dist` but must not write user-global or project locations.

- [ ] **Step 5: Implement global/project registration and uninstall**

  For project mode, install directly to `.claude`, `.agents`, and `.codex` and return without global registration. For global mode, generate `dist`, copy Claude layout to `$HOME/.claude/skills/gin-workflow` when `claude` is discoverable, invoke `agy plugin install <dist>` for Antigravity, and invoke the two Codex marketplace/plugin commands for Codex. Use `Get-Command -ErrorAction SilentlyContinue` before each optional harness registration.

  `-Uninstall` removes only `plugins/gin-workflow/dist` and the legacy `plugins/gin-workflow-advanced/dist`, then exits.

- [ ] **Step 6: Run the PowerShell layout suite to green where available**

  Run: `pwsh -NoProfile -File tests/install_smoke_test.ps1`

  Expected: exit 0. If `pwsh` is unavailable, perform source-level review now and leave runtime verification explicitly pending for Track 4.

### Track 3: Add safe Windows launcher installation and upgrades

- **Dependencies**: Track 2
- **Files**: `tests/install_smoke_test.ps1`, `install.ps1`
- **Model class**: `high_reasoning`
- **Interfaces**:
  - Consumes: `$LauncherVersion`, `$HOME`, `plugins/gin-workflow/src/scripts/gin-workflow`, and `workflow_core`.
  - Produces: `Test-ManagedLauncherShim([string]$Path, [string]$ManagedRoot)` and `Install-Launcher`; a `$HOME/.local/bin/gin-workflow.cmd` shim invoking the current versioned Python entry point.
- **Acceptance criteria**: A managed 2.1 shim upgrades to 2.2; an unrelated shim is preserved byte-for-byte; the installed shim runs `gin-workflow --version` through Python and returns `gin-workflow 2.2`; PATH is warned about but never modified.
- **Estimated complexity**: medium

- [ ] **Step 1: Write failing PowerShell launcher tests**

  Add cases that seed a 2.1 payload and shim containing exactly:

  ```bat
  @echo off
  python "%USERPROFILE%\.local\lib\gin-workflow\2.1\gin-workflow" %*
  ```

  Run `install.ps1`, assert the resulting shim contains `\2.2\gin-workflow`, and assert the 2.1 payload directory still exists. Add a foreign shim containing `@echo off` and `echo foreign launcher`; assert installation fails and `[IO.File]::ReadAllBytes()` remains identical.

- [ ] **Step 2: Verify the launcher cases fail for missing behavior**

  Run: `pwsh -NoProfile -File tests/install_smoke_test.ps1`

  Expected: the managed upgrade case fails because launcher installation is not implemented, while the test harness itself runs correctly.

- [ ] **Step 3: Implement normalized managed-shim recognition**

  `Test-ManagedLauncherShim` reads the complete file, normalizes CRLF to LF for comparison, extracts the quoted Python entry-point path from the only non-echo command, expands `%USERPROFILE%`, obtains a full path, and accepts it only when its parent structure is exactly `<ManagedRoot>/<one-version-component>/gin-workflow`. Reject empty, `.` or `..` version components, extra commands, nested version paths, different executable names, and paths outside `ManagedRoot`.

- [ ] **Step 4: Install the launcher payload and current shim**

  `Install-Launcher` computes:

  ```powershell
  $managedRoot = Join-Path $HOME '.local/lib/gin-workflow'
  $installDir = Join-Path $managedRoot $LauncherVersion
  $launcherTarget = Join-Path $installDir 'gin-workflow'
  $launcherShim = Join-Path $HOME '.local/bin/gin-workflow.cmd'
  ```

  Reject a pre-existing shim unless `Test-ManagedLauncherShim` succeeds. In non-dry-run mode, copy `gin-workflow` and `workflow_core`, then write the shim atomically via a temporary file in the same directory and `Move-Item -Force`. The shim must use `python` and forward `%*`. Warn when the normalized PATH entry list does not contain `$HOME/.local/bin`; never call `SetEnvironmentVariable`.

- [ ] **Step 5: Run launcher tests and the full PowerShell suite**

  Run: `pwsh -NoProfile -File tests/install_smoke_test.ps1`

  Expected: exit 0, managed upgrade points to 2.2, foreign shim remains unchanged, and invoking the installed shim with `--version` outputs `gin-workflow 2.2` on Windows.

### Track 4: Document and verify cross-platform installer behavior

- **Dependencies**: Track 1, Track 2, Track 3
- **Files**: `README.md`; verify `install.sh`, `install.ps1`, `tests/install_smoke_test.sh`, and `tests/install_smoke_test.ps1`
- **Model class**: `cheap_simple` for docs, `standard_impl` for verification
- **Interfaces**:
  - Consumes: final command-line parameters and launcher paths from Tracks 1-3.
  - Produces: user-facing Windows installation instructions and final verification evidence.
- **Acceptance criteria**: README accurately documents PowerShell 7 and all parameters; Unix smoke tests pass; PowerShell tests pass when `pwsh` is available or are explicitly reported as unexecuted; git status contains no unexpected installer-related files.
- **Estimated complexity**: low

- [ ] **Step 1: Add README Windows installation instructions**

  Under local installation, add:

  ```powershell
  # PowerShell 7 on Windows
  pwsh -NoProfile -File .\install.ps1 -Platform all

  # Install project-local files
  pwsh -NoProfile -File .\install.ps1 -Platform codex -Project C:\path\to\repository

  # Preview global writes and registration
  pwsh -NoProfile -File .\install.ps1 -Platform all -DryRun
  ```

  Document the PowerShell parameter names, the `$HOME\.local\bin` PATH warning, and the Python runtime prerequisite. Add `install.ps1` to the repository tree.

- [ ] **Step 2: Run static checks**

  Run:

  ```bash
  bash -n install.sh
  bash -n tests/install_smoke_test.sh
  ```

  If available, also run `PSScriptAnalyzer` through `Invoke-ScriptAnalyzer -Path install.ps1,tests/install_smoke_test.ps1` and record whether it was available.

- [ ] **Step 3: Run automated behavior checks**

  Run:

  ```bash
  bash tests/install_smoke_test.sh
  python3 -m pytest tests/workflow_providers/test_harness_packaging.py
  ```

  Then, when PowerShell 7 is available:

  ```powershell
  pwsh -NoProfile -File tests/install_smoke_test.ps1
  ```

- [ ] **Step 4: Review safety predicates against all collision cases**

  Confirm from tests and source that both installers reject regular files, links/shims outside the managed root, nested version paths, and malformed launcher content, and that rejection occurs before user launcher mutation.

- [ ] **Step 5: Record Beads evidence and inspect the working tree**

  Update `gin-workflow-95v` notes with changed files, commands, pass/fail results, and any unavailable Windows-only verification. Run `git status --short` and distinguish task files from pre-existing `.beads`, `.agent-workflow`, and `.planning/worktrees` changes.

- [ ] **Step 6: Close only after acceptance criteria are met**

  Close `gin-workflow-95v` only if required Unix checks pass, the PowerShell script has either run under PowerShell 7 or the user accepts the explicitly documented environmental verification gap, and no unresolved safety finding remains. Do not commit or push without new authorization.

## Integration

- **Branch**: current working branch
- **Merge strategy**: sequential (`Track 1` → `Track 2` → `Track 3` → `Track 4`) because `install.ps1` and its smoke test are shared by Tracks 2 and 3.

## Validation

- [ ] `bash -n install.sh` passes.
- [ ] `bash -n tests/install_smoke_test.sh` passes.
- [ ] `bash tests/install_smoke_test.sh` passes, including managed upgrade and foreign-link preservation.
- [ ] `python3 -m pytest tests/workflow_providers/test_harness_packaging.py` passes.
- [ ] `pwsh -NoProfile -File tests/install_smoke_test.ps1` passes on PowerShell 7, or the missing runtime is explicitly recorded as an unresolved verification limitation.
- [ ] PowerShell syntax/static analysis is clean when `PSScriptAnalyzer` is available.
- [ ] README commands and parameter names match the implemented installer.
- [ ] `git status --short` has been reviewed and all task-related files are identified.

## Risks and Mitigations

- Risk: A permissive ownership check overwrites an unrelated launcher. Mitigation: exact managed-root shape checks plus negative tests for regular files, external links, nested paths, and malformed shims.
- Risk: PowerShell path normalization differs across Windows and Linux. Mitigation: use `[IO.Path]::GetFullPath`, `Join-Path`, and Windows-native runtime testing; never compare raw unnormalized paths for ownership.
- Risk: Windows symlink creation requires Developer Mode or privileges. Mitigation: use links only when `-Link` is requested and surface a clear native failure with guidance.
- Risk: PowerShell 7 is absent in the current environment. Mitigation: keep an executable PowerShell smoke suite in-repo, run all Unix/static checks, and report the runtime gap without claiming a pass.
- Risk: Existing unrelated worktree changes are overwritten. Mitigation: edit only declared task files and inspect `git status` before handoff.

## Notes

- Model guidance is planning metadata, not Beads state.
- `standard_impl` is the default for execution.
- The approved design is `docs/superpowers/specs/2026-08-16-installer-upgrades-and-windows-design.md`.
- Beads item `gin-workflow-95v` owns durable execution status.
