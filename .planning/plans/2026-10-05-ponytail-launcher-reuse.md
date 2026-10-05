# Plan: Reuse launcher installation logic

## Goal

Remove duplicated launcher installation logic for gin-workflow and gin-qa while preserving existing behavior. Scope is install.sh, install.ps1, and relevant coverage in tests/install_smoke_test.sh and tests/install_smoke_test.ps1. Other audit findings have separate scopes. Line-count savings are an estimate, not an acceptance threshold.

## Architecture

Use one shared launcher installation function in each shell, taking the launcher name and version. Update the existing dispatch sites to supply the two supported launchers. Keep a small explicit branch for plugin-specific content and warnings; do not introduce a registry, callbacks, configuration format, dependency, or cross-shell abstraction.

## Tech Stack

Existing Bash and PowerShell installers, shell smoke tests, and Python unittest packaging coverage. No new tooling or dependencies.

## Global Constraints

gin-workflow installs workflow_core, rules, and templates. gin-qa installs gin_qa and templates. Preserve existing source paths, versioned installation paths, executable names, permissions, and platform-specific link or shim formats. Reuse the existing managed-launcher ownership checks with the appropriate launcher name.

Preserve each launcher's current sequence: derive paths, validate any existing launcher, emit the gin-qa dependency warning when applicable, handle dry-run, copy files, publish the launcher, and emit completion output. The gin-workflow PATH warning remains after successful installation; gin-qa does not acquire that warning.

Keep existing dry-run messages and launcher-write behavior, error propagation, upgrade eligibility, and refusal to replace foreign or malformed launchers. Preserve Bash symlink behavior and PowerShell temporary-file replacement with cleanup in finally. This refactor does not change the broader installer's existing dry-run behavior or add transactional guarantees to package copying.

Run bash tests/install_smoke_test.sh. On 2026-10-05 the user explicitly waived running PowerShell verification: change the PowerShell implementation, close the corresponding work after static inspection and independent review, and leave runtime verification to the user, who will report any later issue. Do not install or run pwsh for this change. Report PowerShell runtime tests as not run by user instruction, not as passed. Verify the final diff and obtain independent review before closing the bead.

## Model Guidance

- `default_model_class`: `standard_impl`
- `phase_guidance`: brainstorm/design/review `high_reasoning`; plan/implement/verify `standard_impl`; docs `cheap_simple`.
- `override_rule`: use `high_reasoning` only if execution boundaries or major tradeoffs become unresolved.

## Requirement Analysis

- Problem: two almost identical launcher installation flows in each shell require duplicate maintenance.
- Success: one flow per shell, unchanged behavior, Bash smoke tests pass, and independent review approves both tracks.
- Constraints: the verbatim spec constraints above; no PowerShell runtime verification by explicit user instruction.
- Non-goals: other audit findings, release/version changes, changes to plugin registration, generic installer frameworks, and new runtime guarantees.

## Approach Options

1. Shared name/version installation function per shell: selected by the user; removes the duplicated flow with small plugin-specific branches.
2. Smaller helpers while retaining two flows: less movement, but retains duplicated orchestration. Not selected.

## Scope and File Map

Spec: `.planning/specs/2026-10-05-ponytail-launcher-reuse-design.md`.
Audit epic: `gin-workflow-f7g`. Parent deliverable and workflow ID for this plan: `gin-workflow-f7g.1`.

| File | Responsibility | Track |
|---|---|---|
| install.sh | Bash launcher installation and dispatch | 1 |
| tests/install_smoke_test.sh | Bash launcher regression coverage | 1 |
| install.ps1 | PowerShell launcher installation and dispatch | 2 |
| tests/install_smoke_test.ps1 | PowerShell regression cases for later user execution | 2 |

Line references below refer to commit `03ec22c`; locate by function name after edits. Do not create track beads until orchestration. Track beads close after their checks and independent review pass; `gin-workflow-f7g.1` remains open until human-confirmed integration. The user waiver removes only PowerShell runtime verification from closure requirements, not review or the integration gate. Epic `gin-workflow-f7g` also contains the other findings and is not closed by this plan.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Two bounded shell-specific tracks with no need for parallel implementation.
```

## Tasks

### Track 1: Share Bash launcher installation

- **Dependencies**: none.
- **Provider role**: `general`.
- **Reasoning**: `medium`.
- **Model guidance**: `standard_impl`.
- **Review routing**: role `review`, reasoning `high`, model class `high_reasoning`; resolve a different provider under the active independence policy.
- **Estimated complexity**: low.
- **Files**: modify `install.sh:380–443,548–553`; test `tests/install_smoke_test.sh:329–381`.
- **Interfaces**: `install_launcher <name:string> <version:string>` returns the existing shell success/failure status; names are the two already-validated plugin choices. Reuse `is_managed_launcher_link <path> <managed_root> <name>` unchanged. Remove `install_qa_launcher` after updating its only dispatch site.
- **Acceptance criteria**: both plugins use the shared function; dry-run, dependencies, permissions, ownership checks, link behavior and output are unchanged; shell tests pass and review approves.

Each numbered step is a small edit/check cycle; a full smoke run may take longer than the edit.

1. Extend the existing upgrade and collision cases to cover gin-qa. Prefer a two-row loop over copying the workflow cases. Use these values:

   ```bash
   for launcher in gin-workflow gin-qa; do
     case "$launcher" in
       gin-workflow) old_version=2.1; current_version=2.7 ;;
       gin-qa) old_version=0.3; current_version=0.4 ;;
     esac
   done
   ```

   Move the existing bodies into this loop: give each temporary home a `$launcher` suffix; replace launcher path literals with `$launcher`; replace old/new version literals with `$old_version`/`$current_version`; pass `--plugin "$launcher"` to every invocation. Cover managed upgrades, foreign symlinks, malformed nested managed targets, and regular-file collisions. Preserve the existing equality/content assertions so rejected installations cannot modify the launcher. Keep temporary homes beneath the already-cleaned mock home and retain cleanup of output files. Do not remove earlier installation, CLI, warning, or dry-run coverage.

2. Run `bash tests/install_smoke_test.sh` before production edits. Expect exit 0: these are characterization tests for behavior already present, so do not manufacture a failing behavior test for this refactor. If a new case fails, determine whether the fixture is wrong or the failure is pre-existing before changing the installer; behavior fixes are outside scope.

3. Replace the two installer bodies with one. Start the shared function with:

   ```bash
   local name="$1" version="$2" package
   local source_dir="$SCRIPT_DIR/plugins/$name/src/scripts"
   local managed_root="${HOME}/.local/lib/$name"
   local install_dir="$managed_root/$version"
   local launcher_target="$install_dir/$name"
   local launcher_link="${HOME}/.local/bin/$name"
   case "$name" in
     gin-workflow) package=workflow_core ;;
     gin-qa) package=gin_qa ;;
   esac
   ```

   Retain the existing collision condition and pass `"$name"` to `is_managed_launcher_link`. Retain the QA dependency warning immediately after that guard, conditional on `name=gin-qa`. Substitute name/version in existing dry-run and success messages. Copy `$package` and templates in the common path; copy rules only for gin-workflow. Preserve `chmod 755`, `ln -sfn`, and the workflow-only PATH warning, including its position after the success message. Retain directory creation before copying, using the same plugin-specific directory sets as before.

4. Change dispatch to:

   ```bash
   case "$p_name" in
     gin-workflow) install_launcher "$p_name" "$LAUNCHER_VERSION" ;;
     gin-qa) install_launcher "$p_name" "$QA_LAUNCHER_VERSION" ;;
   esac
   ```

   Run `bash -n install.sh tests/install_smoke_test.sh`, then `bash tests/install_smoke_test.sh`; expect exit 0. Run `git diff --check`; expect no output. Review the diff against the original warning/guard order and obtain independent approval. Commit only the two track files on the feature branch after approval.

### Track 2: Share PowerShell launcher installation

- **Dependencies**: Track 1, for sequential delivery and one final shared behavior comparison.
- **Provider role**: `general`.
- **Reasoning**: `medium`.
- **Model guidance**: `standard_impl`.
- **Review routing**: role `review`, reasoning `high`, model class `high_reasoning`; resolve a different provider under the active independence policy.
- **Estimated complexity**: low.
- **Files**: modify `install.ps1:265–376,508–511`; test `tests/install_smoke_test.ps1:139–172,207–220`.
- **Interfaces**: `Install-Launcher -Name <string> -Version <string>` emits the current output and throws on existing failure conditions. Reuse `Test-ManagedLauncherShim -Path <string> -ManagedRoot <string> -Name <string>` unchanged. Remove `Install-QaLauncher` after updating dispatch.
- **Acceptance criteria**: shared flow preserves ownership checks, installed files, exact warning conditions, and atomic shim replacement; static diff review and independent review pass. PowerShell runtime tests are explicitly not required by user instruction.

1. Extend managed-upgrade and foreign/malformed shim cases in the existing test file to both plugins with a local table:

   ```powershell
   foreach ($launcherCase in @(
       @{ Name = 'gin-workflow'; Old = '2.1'; Current = '2.7' },
       @{ Name = 'gin-qa'; Old = '0.3'; Current = '0.4' }
   )) {
       $launcherName = $launcherCase.Name
       $managedRoot = Join-Path $TestHome ".local/lib/$launcherName"
       $oldInstall = Join-Path $managedRoot $launcherCase.Old
       $oldLauncher = Join-Path $oldInstall $launcherName
       $shim = Join-Path $TestHome ".local/bin/$launcherName.cmd"
   }
   ```

   Move the existing upgrade, malformed, and foreign shim bodies inside the loop. Add `Plugin = $launcherName` to their `Invoke-Installer` parameter hashtables, derive target strings from the row, and keep byte-for-byte rejection assertions. Restore each valid `$upgradedShim` after its rejection cases. Rebind the later uninstall fixture explicitly to the workflow shim and its original foreign content so the loop's final gin-qa value cannot affect existing downstream assertions. Retain `$IsWindows` checks and all unrelated cases. Do not execute the suite.

2. Give `Install-Launcher` this parameter block and common path derivation:

   ```powershell
   param(
       [Parameter(Mandatory)][string]$Name,
       [Parameter(Mandatory)][string]$Version
   )
   $sourceDirectory = Join-Path $ScriptRoot "plugins/$Name/src/scripts"
   $managedRoot = Join-Path $UserHome ".local/lib/$Name"
   $installDirectory = Join-Path $managedRoot $Version
   $launcherTarget = Join-Path $installDirectory $Name
   $launcherShim = Join-Path $UserHome ".local/bin/$Name.cmd"
   $package = if ($Name -eq 'gin-workflow') { 'workflow_core' } else { 'gin_qa' }
   ```

   Use the existing validated plugin selection. Keep the ownership guard first and pass `-Name $Name`. Keep the dependency warning conditional on gin-qa before the dry-run return. Reuse `Copy-DirectoryContent` for the selected package and templates; branch only for rules. Preserve `New-Directory` behavior, including the existing QA templates-directory creation. Reuse the existing shim-content/temp-file/try/finally sequence verbatim. Substitute name/version in messages; guard the existing PATH check with `$Name -eq 'gin-workflow'` after completion output.

3. Replace launcher dispatch with:

   ```powershell
   $version = if ($name -eq 'gin-workflow') { $LauncherVersion } else { $QaLauncherVersion }
   Install-Launcher -Name $name -Version $version
   ```

   Keep `Install-Plugin -Name $name` in its current position. Read both changed files in full around the edited scopes, inspect string interpolation, named arguments, braces, try/finally, variable lifetime, and test-fixture restoration. Run `git diff --check`; expect no output. Do not install or invoke pwsh. Obtain independent review with the explicit runtime waiver included in the review context, then commit only the two track files on the feature branch.

## Integration

- **Branch**: `chore/ponytail-audit-f7g`.
- **Merge strategy**: sequential; no merge or PR without explicit user authorization.
- Existing finding 2 commit is outside this plan's implementation diff.
- Do not regenerate or commit dist output produced by smoke tests.

## Validation and Traceability

| Spec requirement | Evidence |
|---|---|
| One shared flow per shell; no generic framework | Tracks 1 and 2 diff and independent review |
| Correct package/rules/templates and launcher format | Existing install/CLI smoke cases; PowerShell static comparison |
| Managed upgrades and foreign/malformed refusal | Expanded two-plugin cases; Bash execution and PowerShell static review |
| Unchanged warnings, ordering and dry-run | Existing smoke coverage and explicit old/new control-flow comparison |
| PowerShell runtime waiver | Track 2 closure notes and final handoff state not run by user instruction |
| No new dependency, registration change, or new behavior | Scoped diff review |

At integration run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests/test_all.py`; expect exit 0, recording actual counts/skips. Bash smoke tests and syntax checks must have fresh passing output from the final Bash tree. Do not rerun unchanged checks merely because a documentation or Beads update occurred. No PowerShell runtime claim is permitted. A missing runtime is not a blocker under the user's waiver.

## Approval

Status: awaiting explicit user approval of this plan. Once approved, record `plan-approved` with workflow ID `gin-workflow-f7g.1` and this file as evidence. Stop before orchestration.
