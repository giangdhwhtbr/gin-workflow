# Plan: GitHub Copilot CLI as a skill-install platform

Spec: `.planning/specs/2026-10-15-copilot-platform-design.md`
Branch: `feat/copilot-platform`

## Objective
`install.sh --platform copilot` and `install.ps1 -Platform copilot` build `plugins/<plugin>/dist/copilot` in the Claude plugin layout without hooks or agents, and register it with `copilot plugin install <path>` when the Copilot CLI is on `PATH`. Docs name Copilot as a platform and state its limits.

**Goal (from spec):** Let a user run the gin-workflow skills inside GitHub Copilot CLI (`copilot`), installed by the existing installers on Linux, macOS, and Windows 11.

**Architecture:** installer-only change. One `copilot` branch in each installer's platform layout function, reusing the existing directory-copy loop (extracted from the OpenCode bundle function into a shared helper) and the existing manifest generator. No change to `workflow_core`, `workflow_providers`, or `SUPPORTED_HARNESSES`.

**Tech stack:** bash, PowerShell 7, Python 3 `unittest`.

**Global Constraints (verbatim from spec):**
- Copilot is a skill host only. Routed workers and reviewers keep running through another installed CLI (`claude`, `codex`, `agy`, or `opencode`); `/setup` run from Copilot selects that CLI as `harness`. The workflow core (`SUPPORTED_HARNESSES`, providers, routing) does not change.
- Existing platforms: their `dist/` output and registration stay byte-for-byte the same. `all` now also builds `dist/copilot`.
- Without the hooks, nothing blocks dangerous git commands inside Copilot. This is documented, and the hook port is a follow-up.

## Model Guidance
- `default_model_class`: `standard_impl`
- `phase_guidance`:
  - `implement`: `standard_impl`
  - `review`: `high_reasoning`
  - `docs`: `cheap_simple`
- `override_rule`: none needed; boundaries are settled.

## Requirement Analysis
- Problem statement: the installers know Claude, Codex, Antigravity, and OpenCode, but not Copilot CLI, which loads plugins in the Claude layout and cannot use the nested OpenCode-style skill copy.
- Success criteria: spec requirements 1–8 and US-1..US-3 acceptance criteria, checked by the smoke tests, the packaging test, and one manual Copilot run.
- Constraints: Global Constraints above.
- Non-goals: Copilot-format hooks, VS Code Copilot, a Copilot worker adapter, Copilot-only machines, a `copilot` harness value.

## Approach Options
### Option 1: Shared copy helper + `copilot` branch (selected)
- Pros: reuses the OpenCode directory loop and the manifest generator; no duplicated loop.
- Cons: touches `install_opencode_bundle` / `Install-OpenCodeBundle` to call the helper (behavior unchanged).

### Option 2: Reuse `copy_src` / `Copy-PluginSource`, then delete `hooks/`, `agents/`, `commands/`
- Pros: no refactor.
- Cons: copy-then-delete; with `--link`, `agents/` is a tree of symlinks to clean up; easy to leave a stray directory.

### Recommended Approach
- Selected option: Option 1. Reasoning: the bundle contents are an explicit allow-list (spec requirement 1), which is exactly what the OpenCode loop already expresses.

## Scope
- In scope: `install.sh`, `install.ps1`, `tests/install_smoke_test.sh`, `tests/install_smoke_test.ps1`, `tests/workflow_providers/test_harness_packaging.py`, version files, README, `docs/contributing.md`, `docs/concepts/architecture.md`, `docs/reference/skills.md`, `docs/reference/troubleshooting.md`.
- Out of scope: everything in Non-goals; `remote-install.sh` (it forwards `--platform` to `install.sh` unchanged); the `telegram-notify` skill's `${PLUGIN_ROOT}` path, which stays unresolved under Copilot (optional skill, listed in troubleshooting).

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Three small tracks; the docs track depends on both installers. One agent in sequence is cheapest.
```

## Tasks

### Track 1: `install.sh` copilot platform
- **Dependencies**: none
- **Provider role**: `backend`
- **Reasoning**: `medium`
- **Estimated complexity**: medium
- **Files**:
  - Modify: `install.sh` (uninstall block ~L90–98, platform detection ~L100–111, `install_platform` ~L330–360, `install_opencode_bundle` ~L379–400, `install_plugin` ~L496–620)
  - Test: `tests/install_smoke_test.sh`, `tests/workflow_providers/test_harness_packaging.py`
- **Interfaces (produced)**:
  - `copy_bundle_dirs <src> <target>`: copies `skills scripts references examples rules templates` from `<src>` into `<target>`, honoring `LINK`.
  - `install_platform copilot <plugin> <target> "" <manifest_path> false`.
  - `HAS_COPILOT` (`true|false`).
  - Output lines: `Configuring Copilot plugin structure for <plugin>...`, `(dry-run) would install Copilot plugin from <abs dist/copilot>`, `Registering <plugin> with Copilot...`, `Copilot CLI not found; skipped registration. Run: copilot plugin install <abs dist/copilot>`, and on stderr `Warning: Copilot plugins are global; --project skips copilot.`
- **Interfaces (consumed)**: `generate_manifest`, `matches_platform`, `LINK`, `DRY_RUN`, `PLUGINS`, `SCRIPT_DIR`.

**Steps**

1. Write the failing smoke checks. In `tests/install_smoke_test.sh`, after the OpenCode dry-run block (after `assert_workflow_v22_layout "plugins/gin-workflow/dist/opencode"`), add:

   ```bash
   ./install.sh --platform copilot --dry-run >"$output_file"

   assert_contains "$output_file" "Configuring Copilot plugin structure for gin-workflow"
   assert_contains "$output_file" "(dry-run) would install Copilot plugin from $ROOT_DIR/plugins/gin-workflow/dist/copilot"
   assert_exists "plugins/gin-workflow/dist/copilot/.claude-plugin/plugin.json"
   assert_contains "plugins/gin-workflow/dist/copilot/.claude-plugin/plugin.json" '"name": "gin-workflow"'
   assert_exists "plugins/gin-workflow/dist/copilot/skills/setup/SKILL.md"
   assert_exists "plugins/gin-workflow/dist/copilot/skills/report/SKILL.md"
   assert_exists "plugins/gin-workflow/dist/copilot/references/stage-contract.md"
   assert_exists "plugins/gin-workflow/dist/copilot/scripts/gin-workflow"
   assert_not_exists "plugins/gin-workflow/dist/copilot/hooks"
   assert_not_exists "plugins/gin-workflow/dist/copilot/agents"
   assert_not_exists "plugins/gin-workflow/dist/copilot/commands"
   ```

   Before the final `rmdir "$TEST_HOME"`, add:

   ```bash
   # Copilot: registration through a stub CLI, re-install, skip without the CLI,
   # project warning, and uninstall.
   copilot_home="$MOCK_HOME/copilot-home"
   copilot_bin="$MOCK_HOME/copilot-bin"
   copilot_log="$MOCK_HOME/copilot.log"
   mkdir -p "$copilot_home" "$copilot_bin"
   cat > "$copilot_bin/copilot" <<'EOF'
   #!/bin/sh
   printf '%s\n' "$*" >> "$COPILOT_LOG"
   EOF
   chmod +x "$copilot_bin/copilot"

   HOME="$copilot_home" PATH="$copilot_bin:$PATH" COPILOT_LOG="$copilot_log" ./install.sh --platform copilot >"$output_file"
   assert_contains "$copilot_log" "plugin uninstall gin-workflow"
   assert_contains "$copilot_log" "plugin install $ROOT_DIR/plugins/gin-workflow/dist/copilot"
   assert_contains "$output_file" "Registering gin-workflow with Copilot..."
   assert_exists "$copilot_home/.local/bin/gin-workflow"

   if ! command -v copilot >/dev/null 2>&1; then
     HOME="$copilot_home" ./install.sh --platform copilot >"$output_file"
     assert_contains "$output_file" "Copilot CLI not found; skipped registration. Run: copilot plugin install $ROOT_DIR/plugins/gin-workflow/dist/copilot"
   fi

   copilot_project="$MOCK_HOME/copilot-project"
   mkdir -p "$copilot_project"
   HOME="$copilot_home" ./install.sh --platform copilot --project "$copilot_project" >"$output_file" 2>&1
   assert_contains "$output_file" "Warning: Copilot plugins are global; --project skips copilot."

   : > "$copilot_log"
   HOME="$copilot_home" PATH="$copilot_bin:$PATH" COPILOT_LOG="$copilot_log" ./install.sh --uninstall >/dev/null
   assert_contains "$copilot_log" "plugin uninstall gin-workflow"
   assert_not_exists "plugins/gin-workflow/dist/copilot"
   ```

   In `tests/workflow_providers/test_harness_packaging.py`, change `test_dry_run_builds_every_harness_layout` to cover copilot:

   ```python
           copilot_removed = {"agents/developer.md"}
           for harness in ("claude-code", "codex", "antigravity", "opencode", "copilot"):
               with self.subTest(harness=harness):
                   root = self.dist / harness
                   removed = opencode_removed if harness == "opencode" else copilot_removed if harness == "copilot" else set()
                   required = [r for r in REQUIRED_ARTIFACTS if r not in removed]
                   if harness == "opencode":
                       required += sorted(opencode_added)
                   missing = [relative for relative in required if not (root / relative).is_file()]
                   self.assertEqual([], missing)
   ```

   and add after `test_opencode_layout_is_a_skill_bundle_without_manifest_or_hooks`:

   ```python
       def test_copilot_layout_is_a_claude_manifest_bundle_without_hooks_or_agents(self):
           # Copilot CLI reads .claude-plugin/plugin.json and skills/<name>/SKILL.md;
           # its hook and agent formats differ, so those are left out.
           root = self.dist / "copilot"
           manifest = json.loads((root / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
           self.assertEqual("gin-workflow", manifest["name"])
           self.assertTrue((root / "skills/setup/SKILL.md").is_file())
           self.assertTrue((root / "skills/report/SKILL.md").is_file())
           self.assertTrue((root / "references/stage-contract.md").is_file())
           self.assertFalse((root / "hooks").exists())
           self.assertFalse((root / "agents").exists())
           self.assertFalse((root / "commands").exists())
   ```

   Add `import json` to the imports if it is not there.

2. Run and confirm the failure: `bash tests/install_smoke_test.sh` fails on `Configuring Copilot plugin structure`; `python3 -m unittest tests.workflow_providers.test_harness_packaging` fails on the `copilot` subtest.

3. Implement in `install.sh`:

   a. Add the shared helper above `install_opencode_bundle`, and replace the `mkdir -p "$target"` + `for dir in ...; done` loop inside `install_opencode_bundle` with `copy_bundle_dirs "$src" "$target"` (keep its comment):

   ```bash
   copy_bundle_dirs() {
     local src="$1"
     local target="$2"
     local dir

     mkdir -p "$target"
     for dir in skills scripts references examples rules templates; do
       [ -d "$src/$dir" ] || continue
       [ -n "$(ls -A "$src/$dir" 2>/dev/null)" ] || continue
       mkdir -p "$target/$dir"
       if [ "$LINK" = true ]; then
         cp -rsf "$src/$dir/." "$target/$dir/"
       else
         cp -rf "$src/$dir/." "$target/$dir/"
       fi
     done
   }
   ```

   b. In `install_platform`, after the opencode branch:

   ```bash
     if [ "$platform" = "copilot" ]; then
       # Copilot CLI reads the Claude layout (.claude-plugin/plugin.json,
       # skills/<name>/SKILL.md); its hook and agent formats differ, so hooks/
       # and agents/ are left out.
       copy_bundle_dirs "$SCRIPT_DIR/plugins/$p_name/src" "$target_dir"
       mkdir -p "$(dirname "$manifest_path")"
       generate_manifest "plugins/$p_name" "$manifest_path" "false"
       return
     fi
   ```

   c. Platform detection: add `HAS_COPILOT=false` and `if command -v copilot &> /dev/null; then HAS_COPILOT=true; fi` next to the other `HAS_*` checks.

   d. Uninstall block: before its `echo`, add

   ```bash
     if command -v copilot &> /dev/null; then
       for p_name in "${PLUGINS[@]}"; do
         copilot plugin uninstall "$p_name" >/dev/null 2>&1 || true
       done
     fi
   ```

   and change the message to: `Removed generated dist output, the global OpenCode skill install, and the Copilot plugin registration. Project installs (a repository's .opencode/) and the Claude Code, Codex, and Antigravity registrations are left for manual removal.`

   e. `install_plugin`, project branch: first statement inside `if [ -n "$PROJECT_DIR" ]; then`:

   ```bash
       if matches_platform "copilot"; then
         echo "Warning: Copilot plugins are global; --project skips copilot." >&2
       fi
   ```

   f. `install_plugin`, dist rebuild: add `if matches_platform "copilot"; then rm -rf "${dist_dir:?}/copilot"; fi` after the opencode `rm`, and after the opencode configure block:

   ```bash
     if matches_platform "copilot"; then
       echo "Configuring Copilot plugin structure for $p_name..."
       install_platform "copilot" "$p_name" "$dist_dir/copilot" "" "$dist_dir/copilot/.claude-plugin/plugin.json" "false"
     fi
   ```

   g. Dry-run block, after the opencode echo:

   ```bash
       if matches_platform "copilot"; then
         echo "(dry-run) would install Copilot plugin from $SCRIPT_DIR/$dist_dir/copilot"
       fi
   ```

   h. Registration, after the codex block:

   ```bash
     if matches_platform "copilot"; then
       if [ "$HAS_COPILOT" = true ]; then
         echo "Registering $p_name with Copilot..."
         # Remove first so a re-run replaces the installed copy.
         copilot plugin uninstall "$p_name" >/dev/null 2>&1 || true
         copilot plugin install "$SCRIPT_DIR/$dist_dir/copilot"
       else
         echo "Copilot CLI not found; skipped registration. Run: copilot plugin install $SCRIPT_DIR/$dist_dir/copilot"
       fi
     fi
   ```

   i. Header comment on line 2: add `GitHub Copilot CLI` to the list of targets. (`install.sh` does not validate `--platform` values, so no list to extend.)

4. Run and confirm the pass: `bash tests/install_smoke_test.sh` and `python3 -m unittest tests.workflow_providers.test_harness_packaging` both pass; `python3 tests/test_all.py` passes.
5. Commit: `feat(install): add GitHub Copilot CLI platform to install.sh`.

- **Acceptance criteria**: spec requirements 1–7 hold for `install.sh`; US-2 criteria pass in `tests/install_smoke_test.sh`; the claude-code, codex, antigravity, and opencode dist trees are unchanged (the existing assertions still pass).

### Track 2: `install.ps1` copilot platform
- **Dependencies**: none
- **Provider role**: `backend`
- **Reasoning**: `medium`
- **Estimated complexity**: medium
- **Files**:
  - Modify: `install.ps1` (`param` L4, `Install-OpenCodeBundle` L182–200, `Install-PlatformLayout` L235–261, `Install-Plugin` L423–551, uninstall L553–570)
  - Test: `tests/install_smoke_test.ps1`
- **Interfaces (produced)**:
  - `Copy-BundleDirectories -Source <string> -Destination <string>`: copies `skills scripts references examples rules templates`, honoring `$Link`.
  - `Install-PlatformLayout -Harness copilot`.
  - The same output lines as Track 1, with `-Project` in the warning: `Copilot plugins are global; -Project skips copilot.` (via `Write-Warning`).
- **Interfaces (consumed)**: `Copy-DirectoryContent`, `New-PluginManifest`, `Invoke-NativeCommand`, `Test-Platform`, `New-MockCommand` (test).

**Steps**

1. Write the failing checks in `tests/install_smoke_test.ps1`. After the OpenCode `--link` project block (before `$env:PATH = $OriginalPath` at ~L262), add:

   ```powershell
       $copilotDryRun = Invoke-Installer @{ Platform = 'copilot'; DryRun = $true }
       $copilotDist = Join-Path $Root 'plugins/gin-workflow/dist/copilot'
       Assert-Contains $copilotDryRun 'Configuring Copilot plugin structure for gin-workflow'
       Assert-Contains $copilotDryRun "(dry-run) would install Copilot plugin from $copilotDist"
       Assert-Exists (Join-Path $copilotDist '.claude-plugin/plugin.json')
       Assert-Exists (Join-Path $copilotDist 'skills/setup/SKILL.md')
       Assert-Exists (Join-Path $copilotDist 'references/stage-contract.md')
       Assert-True (-not (Test-Path -LiteralPath (Join-Path $copilotDist 'hooks'))) 'Copilot bundle has hooks'
       Assert-True (-not (Test-Path -LiteralPath (Join-Path $copilotDist 'agents'))) 'Copilot bundle has agents'
       Assert-True (-not (Test-Path -LiteralPath (Join-Path $copilotDist 'commands'))) 'Copilot bundle has commands'

       Set-Content -LiteralPath $mockLog -Value '' -NoNewline
       New-MockCommand -Name 'copilot' -ExitCode 0 | Out-Null
       $copilotInstall = Invoke-Installer @{ Platform = 'copilot' }
       $copilotLog = [IO.File]::ReadAllText($mockLog)
       Assert-Contains $copilotInstall 'Registering gin-workflow with Copilot...'
       Assert-Contains $copilotLog 'plugin uninstall gin-workflow'
       Assert-Contains $copilotLog "plugin install $copilotDist"

       $copilotProject = Join-Path $TestRoot 'copilot-project'
       New-Item -ItemType Directory -Path $copilotProject | Out-Null
       $copilotProjectOutput = & $Installer -Platform copilot -Project $copilotProject 3>&1 | Out-String
       Assert-Contains $copilotProjectOutput 'Copilot plugins are global; -Project skips copilot.'

       Set-Content -LiteralPath $mockLog -Value '' -NoNewline
       & $Installer -Uninstall | Out-Null
       Assert-Contains ([IO.File]::ReadAllText($mockLog)) 'plugin uninstall gin-workflow'
       # Later blocks run without the stub.
       Remove-Item -LiteralPath (Join-Path $TestRoot "mock-bin/$(if ($IsWindows) { 'copilot.cmd' } else { 'copilot' })") -Force
   ```

   After `$env:PATH = $OriginalPath` (~L262), when `copilot` is not on the original `PATH`:

   ```powershell
       if (-not (Get-Command copilot -ErrorAction SilentlyContinue)) {
           $copilotSkip = Invoke-Installer @{ Platform = 'copilot' }
           Assert-Contains $copilotSkip "Copilot CLI not found; skipped registration. Run: copilot plugin install $(Join-Path $Root 'plugins/gin-workflow/dist/copilot')"
       }
   ```

   The `-Uninstall` call removes `plugins/*/dist`; later blocks in the file only do project installs, which do not read `dist/`.

2. Run and confirm the failure: `pwsh -NoProfile -File tests/install_smoke_test.ps1` fails on the `ValidateSet` for `copilot`.
3. Implement in `install.ps1`:

   a. `param`: `[ValidateSet('claude', 'antigravity', 'codex', 'opencode', 'copilot', 'both', 'all')]`.

   b. Add before `Install-OpenCodeBundle`, and replace the `New-Directory $Destination` + `foreach` in `Install-OpenCodeBundle` with `Copy-BundleDirectories -Source $Source -Destination $Destination` (keep its comment):

   ```powershell
   function Copy-BundleDirectories {
       param(
           [Parameter(Mandatory)][string]$Source,
           [Parameter(Mandatory)][string]$Destination
       )
       New-Directory $Destination
       foreach ($directory in @('skills', 'scripts', 'references', 'examples', 'rules', 'templates')) {
           Copy-DirectoryContent `
               -Source (Join-Path $Source $directory) `
               -Destination (Join-Path $Destination $directory) `
               -AsLink:$Link
       }
   }
   ```

   c. `Install-PlatformLayout`: `ValidateSet('claude', 'antigravity', 'codex', 'opencode', 'copilot')`, and after the opencode branch:

   ```powershell
       if ($Harness -eq 'copilot') {
           # Copilot CLI reads the Claude layout (.claude-plugin/plugin.json,
           # skills/<name>/SKILL.md); its hook and agent formats differ, so hooks/
           # and agents/ are left out.
           Copy-BundleDirectories -Source (Join-Path $PluginDirectory 'src') -Destination $Destination
           New-PluginManifest -PluginDirectory $PluginDirectory -OutputPath $ManifestPath
           return
       }
   ```

   d. `Install-Plugin`, project branch, first statement inside it:

   ```powershell
           if (Test-Platform 'copilot') {
               Write-Warning 'Copilot plugins are global; -Project skips copilot.'
           }
   ```

   e. `Install-Plugin`, dist rebuild, after the opencode block:

   ```powershell
       if (Test-Platform 'copilot') {
           $target = Join-Path $distDirectory 'copilot'
           if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Recurse -Force }
           Write-Output "Configuring Copilot plugin structure for $Name..."
           Install-PlatformLayout -Harness copilot -PluginDirectory $pluginDirectory -Destination $target -HooksRoot '${PLUGIN_ROOT}' -ManifestPath (Join-Path $target '.claude-plugin/plugin.json')
       }
   ```

   f. Dry-run block, after the opencode line:

   ```powershell
           if (Test-Platform 'copilot') {
               Write-Output "(dry-run) would install Copilot plugin from $(Join-Path $distDirectory 'copilot')"
           }
   ```

   g. Registration, after the codex block:

   ```powershell
       if (Test-Platform 'copilot') {
           $copilotBundle = Join-Path $distDirectory 'copilot'
           if (Get-Command copilot -ErrorAction SilentlyContinue) {
               Write-Output "Registering $Name with Copilot..."
               # Remove first so a re-run replaces the installed copy.
               & copilot plugin uninstall $Name *> $null
               Invoke-NativeCommand -Executable 'copilot' -CommandArguments @('plugin', 'install', $copilotBundle)
           }
           else {
               Write-Output "Copilot CLI not found; skipped registration. Run: copilot plugin install $copilotBundle"
           }
       }
   ```

   h. Uninstall block, before its `Write-Output`:

   ```powershell
       if (Get-Command copilot -ErrorAction SilentlyContinue) {
           foreach ($name in $Plugins) {
               & copilot plugin uninstall $name *> $null
           }
       }
   ```

   and change the message to: `Removed generated dist output, the global OpenCode skill install, and the Copilot plugin registration. Project installs and the Claude Code, Codex, and Antigravity registrations are left for manual removal.`

4. Run and confirm the pass: `pwsh -NoProfile -File tests/install_smoke_test.ps1` prints `PowerShell installer smoke tests passed.` If `pwsh` is not available on the implementing machine, record that in the bead as unverified and ask the user to run it on the Windows 11 VDI before the track closes.
5. Commit: `feat(install): add GitHub Copilot CLI platform to install.ps1`.

- **Acceptance criteria**: spec requirements 1–7 hold for `install.ps1`; US-2 criteria pass in `tests/install_smoke_test.ps1`; existing PowerShell smoke assertions still pass.

### Track 3: Docs, version, and manual Copilot check
- **Dependencies**: Track 1, Track 2
- **Provider role**: `docs`
- **Reasoning**: `low`
- **Estimated complexity**: low
- **Files**:
  - Modify: `plugins/gin-workflow/plugin.meta.json`, `plugins/gin-workflow/src/.claude-plugin/plugin.json`, `plugins/gin-workflow/src/.codex-plugin/plugin.json` (`"version": "1.4.2"` → `"1.5.0"`)
  - Modify: `README.md` (L44, after L60), `docs/contributing.md` (L36, L48), `docs/concepts/architecture.md` (L135–140), `docs/reference/skills.md`, `docs/reference/troubleshooting.md`
- **Interfaces**: none.

**Steps**

1. Bump the three version strings to `1.5.0`. Run `python3 tests/test_all.py`; it passes.
2. `README.md`:
   - L44: `Use --platform claude, codex, antigravity, opencode, or copilot for one harness, ...` (keep the existing backtick formatting).
   - After the OpenCode paragraph (L60), add: ``GitHub Copilot CLI: `--platform copilot` builds `dist/copilot` and runs `copilot plugin install` on it. Copilot hosts the skills only; workers and reviews still need `claude`, `codex`, `agy`, or `opencode`, and the safety hook does not run in Copilot ([troubleshooting](docs/reference/troubleshooting.md#github-copilot-cli)).``
3. `docs/contributing.md`: L36 add ``Copilot CLI registers `dist/copilot` with `copilot plugin install`; the bundle keeps the Claude manifest (`.claude-plugin/plugin.json`) and skills but drops `hooks/`, `agents/`, and `commands/`.``; L48 add `copilot` to the `--platform` list.
4. `docs/concepts/architecture.md`: in the build/install diagram add `I --> D5[dist/copilot]` and `D5 --> C5[copilot plugin install]`.
5. `docs/reference/troubleshooting.md`: add a `## GitHub Copilot CLI` section stating: the installer registers `dist/copilot` with `copilot plugin install` and needs `copilot` on `PATH` (otherwise it prints the manual command); the bundle has no hooks, so `safety-check` and `post-edit` do not run in Copilot; workers and reviews route to `claude`, `codex`, `agy`, or `opencode`, so run `/setup` with one of them as `harness`; `--project` skips copilot because Copilot plugins are global; the `telegram-notify` script path (`${PLUGIN_ROOT}`) is not resolved under Copilot.
6. Manual check (US-1): on a machine with Copilot CLI, run `./install.sh --platform copilot` (or `install.ps1 -Platform copilot` on Windows 11), then `copilot plugin list`, then invoke the `setup` and `workflow` skills in a Copilot session. Record the commands and output in the bead. Write the observed invocation syntax into `docs/reference/skills.md` next to the OpenCode `@<skill>` note. If no Copilot CLI is available, record "manual Copilot check not run" in the bead and leave `docs/reference/skills.md` without a Copilot syntax line; the user runs the check on the VDI.
7. Commit: `docs: GitHub Copilot CLI platform; bump gin-workflow to 1.5.0`.

- **Acceptance criteria**: spec requirement 8 and US-1 (manual check recorded, or recorded as not run), US-3 criteria met.

## Integration
- **Branch**: `feat/copilot-platform`
- **Merge strategy**: sequential

## Validation
- [ ] `bash tests/install_smoke_test.sh` passes
- [ ] `pwsh -NoProfile -File tests/install_smoke_test.ps1` passes (or recorded as unverified with the reason)
- [ ] `python3 tests/test_all.py` passes
- [ ] Manual Copilot CLI check recorded (or recorded as not run)

## Notes
- No machine in this session has `pwsh` or `copilot`; Track 2 step 4 and Track 3 step 6 may need the user's Windows 11 VDI.
- Follow-up beads (out of scope): Copilot-format `safety-check`/`post-edit` hooks; VS Code Copilot; Copilot-only machines and a Copilot worker adapter.
