$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Installer = Join-Path $Root 'install.ps1'
$TestRoot = Join-Path ([IO.Path]::GetTempPath()) ("gin-workflow-install-{0}" -f [guid]::NewGuid().ToString('N'))
$TestHome = Join-Path $TestRoot 'home'
$OriginalHome = $env:HOME
$OriginalUserProfile = $env:USERPROFILE
$OriginalPath = $env:PATH

function Assert-True {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) {
        throw $Message
    }
}

function Assert-Exists {
    param([string]$Path)
    Assert-True (Test-Path -LiteralPath $Path) "Expected path to exist: $Path"
}

function Assert-Contains {
    param([string]$Text, [string]$Pattern)
    Assert-True $Text.Contains($Pattern, [StringComparison]::Ordinal) "Expected text to contain: $Pattern"
}

function Invoke-Installer {
    param([hashtable]$Parameters)
    if (-not $Parameters.ContainsKey('NoModifyPath')) { $Parameters['NoModifyPath'] = $true }
    $output = & $Installer @Parameters 2>&1 | Out-String
    return $output
}

function New-MockCommand {
    param(
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][int]$ExitCode
    )
    $mockBin = Join-Path $TestRoot 'mock-bin'
    New-Item -ItemType Directory -Path $mockBin -Force | Out-Null
    if ($IsWindows) {
        $path = Join-Path $mockBin "$Name.cmd"
        $content = "@echo off`r`necho %*>>`"%GIN_WORKFLOW_MOCK_LOG%`"`r`nexit /b $ExitCode`r`n"
    }
    else {
        $path = Join-Path $mockBin $Name
        $content = "#!/bin/sh`nprintf '%s\n' `"`$*`" >> `"`$GIN_WORKFLOW_MOCK_LOG`"`nexit $ExitCode`n"
    }
    [IO.File]::WriteAllText($path, $content, [Text.UTF8Encoding]::new($false))
    if (-not $IsWindows) {
        & chmod +x $path
    }
    return $mockBin
}

New-Item -ItemType Directory -Path $TestHome -Force | Out-Null
$env:HOME = $TestHome
$env:USERPROFILE = $TestHome

try {
    Assert-Exists $Installer

    $dryRunOutput = Invoke-Installer @{ Platform = 'codex'; DryRun = $true }
    Assert-Contains $dryRunOutput 'would install gin launcher version 3.0'
    Assert-Exists (Join-Path $Root 'plugins/gin-workflow/dist/codex/.codex-plugin/plugin.json')
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $TestHome '.local/bin/gin.cmd'))) 'Dry-run wrote the launcher shim'
    Assert-True (-not $dryRunOutput.Contains('gin-qa', [StringComparison]::Ordinal)) 'Default install processed gin-qa'

    $qaDryRun = Invoke-Installer @{ Platform = 'codex'; Plugin = 'gin-qa'; DryRun = $true }
    Assert-Contains $qaDryRun 'would install gin-qa launcher version 0.11'
    Assert-True (-not $qaDryRun.Contains('Processing plugin: gin-workflow', [StringComparison]::Ordinal)) 'gin-qa install processed gin-workflow'
    Assert-Exists (Join-Path $Root 'plugins/gin-qa/dist/codex/skills/cases/SKILL.md')
    Assert-Exists (Join-Path $Root 'plugins/gin-qa/dist/codex/skills/e2e/SKILL.md')
    Assert-Exists (Join-Path $Root 'plugins/gin-qa/dist/codex/skills/tests/SKILL.md')
    Assert-Exists (Join-Path $Root 'plugins/gin-qa/dist/codex/skills/e2e/references/explore-case.md')
    Assert-Exists (Join-Path $Root 'plugins/gin-qa/dist/codex/skills/setup/SKILL.md')
    Assert-Exists (Join-Path $Root 'plugins/gin-qa/dist/codex/agents/e2e-tester.md')

    $baDryRun = Invoke-Installer @{ Platform = 'codex'; Plugin = 'gin-ba'; DryRun = $true }
    Assert-True (-not $baDryRun.Contains('Processing plugin: gin-workflow', [StringComparison]::Ordinal)) 'gin-ba install processed gin-workflow'
    Assert-True (-not $baDryRun.Contains('launcher', [StringComparison]::Ordinal)) 'gin-ba install wrote a launcher'
    Assert-Exists (Join-Path $Root 'plugins/gin-ba/dist/codex/skills/mockup/SKILL.md')
    Assert-Exists (Join-Path $Root 'plugins/gin-ba/dist/codex/skills/capture/references/legacy-description.md')
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $TestHome '.local/bin/gin-ba.cmd'))) 'gin-ba install wrote a launcher shim'

    # gin-orchestrator needs gin-workflow: an empty HOME installs gin-workflow first.
    $orchDryRun = Invoke-Installer @{ Platform = 'codex'; Plugin = 'gin-orchestrator'; DryRun = $true }
    Assert-Contains $orchDryRun 'gin-orchestrator requires gin 3.0; installing it first.'
    Assert-Contains $orchDryRun 'would install gin launcher version 3.0'
    Assert-Contains $orchDryRun 'would install gin-orchestrator launcher version 0.1'
    Assert-True ($orchDryRun.IndexOf('installing it first.', [StringComparison]::Ordinal) -lt $orchDryRun.IndexOf('would install gin launcher', [StringComparison]::Ordinal)) 'gin-workflow was not installed first'
    Assert-True ($orchDryRun.IndexOf('would install gin launcher', [StringComparison]::Ordinal) -lt $orchDryRun.IndexOf('would install gin-orchestrator launcher', [StringComparison]::Ordinal)) 'gin-orchestrator was installed before gin-workflow'
    Assert-Exists (Join-Path $Root 'plugins/gin-orchestrator/dist/codex/skills/providers/SKILL.md')
    Assert-Exists (Join-Path $Root 'plugins/gin-orchestrator/dist/codex/.codex-plugin/plugin.json')

    $allDryRun = Invoke-Installer @{ Platform = 'codex'; Plugin = 'all'; DryRun = $true }
    Assert-Contains $allDryRun 'Processing plugin: gin-workflow'
    Assert-Contains $allDryRun 'Processing plugin: gin-qa'
    Assert-Contains $allDryRun 'Processing plugin: gin-orchestrator'
    Assert-Contains $allDryRun 'Processing plugin: gin-ba'
    Assert-True (-not $allDryRun.Contains('installing it first', [StringComparison]::Ordinal)) 'Plugin all installed gin-workflow twice'

    $opencodeDryRun = Invoke-Installer @{ Platform = 'opencode'; DryRun = $true }
    Assert-Contains $opencodeDryRun 'Configuring OpenCode skill structure for gin-workflow'
    Assert-Contains $opencodeDryRun 'would install global OpenCode skills to'
    Assert-Exists (Join-Path $Root 'plugins/gin-workflow/dist/opencode/skills/setup/SKILL.md')
    Assert-Exists (Join-Path $Root 'plugins/gin-workflow/dist/opencode/skills/gin-report/SKILL.md')
    Assert-Exists (Join-Path $Root 'plugins/gin-workflow/dist/opencode/agents/gin-developer.md')
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $Root 'plugins/gin-workflow/dist/opencode/hooks'))) 'OpenCode dry-run wrote hooks'

    $qaOpencodeDryRun = Invoke-Installer @{ Platform = 'opencode'; Plugin = 'gin-qa'; DryRun = $true }
    Assert-Exists (Join-Path $Root 'plugins/gin-qa/dist/opencode/skills/gin-qa-setup/SKILL.md')
    Assert-Contains ([IO.File]::ReadAllText((Join-Path $Root 'plugins/gin-qa/dist/opencode/skills/gin-qa-setup/SKILL.md'))) 'name: gin-qa-setup'
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $Root 'plugins/gin-qa/dist/opencode/skills/setup'))) 'gin-qa OpenCode bundle kept skills/setup'

    $project = Join-Path $TestRoot 'project'
    New-Item -ItemType Directory -Path $project | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $project '.opencode/agents') -Force | Out-Null
    [IO.File]::WriteAllText((Join-Path $project '.opencode/agents/user-agent.md'), '# user agent')
    # A 2.x project install left skills and agents under the old names.
    foreach ($legacySkill in @('.claude/skills/gin-sdd', '.codex/skills/gin-knowledge', '.opencode/skills/gin-workflow-report')) {
        New-Item -ItemType Directory -Path (Join-Path $project $legacySkill) -Force | Out-Null
    }
    [IO.File]::WriteAllText((Join-Path $project '.opencode/agents/gin-workflow-developer.md'), '# old agent')
    Invoke-Installer @{ Platform = 'all'; Project = $project } | Out-Null
    Assert-Exists (Join-Path $project '.claude/skills/setup/SKILL.md')
    Assert-Exists (Join-Path $project '.agents/skills/setup/SKILL.md')
    Assert-Exists (Join-Path $project '.codex/skills/setup/SKILL.md')
    Assert-Exists (Join-Path $project '.opencode/skills/setup/SKILL.md')
    Assert-Exists (Join-Path $project '.opencode/skills/gin-report/SKILL.md')
    Assert-Exists (Join-Path $project '.opencode/agents/user-agent.md')
    Assert-Exists (Join-Path $project '.opencode/agents/gin-developer.md')
    Assert-Contains ([IO.File]::ReadAllText((Join-Path $project '.opencode/skills/gin-report/SKILL.md'))) 'name: gin-report'
    foreach ($legacySkill in @('.claude/skills/gin-sdd', '.codex/skills/gin-knowledge', '.opencode/skills/gin-workflow-report', '.opencode/agents/gin-workflow-developer.md')) {
        Assert-True (-not (Test-Path -LiteralPath (Join-Path $project $legacySkill))) "Project install kept the old $legacySkill"
    }
    Assert-Exists (Join-Path $project '.claude/skills/report/SKILL.md')
    Assert-Exists (Join-Path $project '.codex/skills/report/SKILL.md')
    Assert-Exists (Join-Path $project '.codex/.codex-plugin/plugin.json')
    Assert-Exists (Join-Path $project '.claude/scripts/safety_check.py')
    $claudeHook = (Get-Content -Raw -LiteralPath (Join-Path $project '.claude/hooks/hooks.json') | ConvertFrom-Json).hooks.PreToolUse[0].hooks[0].command
    Assert-True ($claudeHook -ceq 'python "${CLAUDE_PROJECT_DIR}/.claude/scripts/safety_check.py"') "Unexpected Claude hook command: $claudeHook"
    Assert-Exists (Join-Path $TestHome '.local/lib/gin/3.0/workflow_core/cli.py')
    Assert-Exists (Join-Path $TestHome '.local/lib/gin/3.0/.gin-workflow-src.json')
    Assert-Exists (Join-Path $TestHome '.local/lib/gin/3.0/rules/core.md')
    Assert-Exists (Join-Path $TestHome '.local/lib/gin/3.0/templates/spec-delta.md')
    Assert-Exists (Join-Path $TestHome '.local/lib/gin/3.0/templates/team/commit-msg')
    Assert-Exists (Join-Path $TestHome '.local/bin/gin.cmd')

    $qaProject = Join-Path $TestRoot 'qa-project'
    New-Item -ItemType Directory -Path $qaProject | Out-Null
    Invoke-Installer @{ Platform = 'claude'; Plugin = 'all'; Project = $qaProject } | Out-Null
    Assert-Exists (Join-Path $qaProject '.claude/skills/setup/SKILL.md')
    Assert-Exists (Join-Path $qaProject '.claude/skills/cases/SKILL.md')
    Assert-Exists (Join-Path $TestHome '.local/lib/gin-qa/0.11/gin_qa/cli.py')
    Assert-Exists (Join-Path $TestHome '.local/lib/gin-qa/0.11/templates/evidence.ts')
    Assert-Exists (Join-Path $TestHome '.local/lib/gin-qa/0.11/templates/playwright.config.ts')
    Assert-Exists (Join-Path $TestHome '.local/lib/gin-qa/0.11/templates/qa-readme.md')
    Assert-Exists (Join-Path $TestHome '.local/lib/gin-qa/0.11/templates/report.html')
    Assert-Exists (Join-Path $TestHome '.local/bin/gin-qa.cmd')
    Assert-Exists (Join-Path $TestHome '.local/lib/gin-orchestrator/0.1/gin_orchestrator/cli.py')
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $TestHome '.local/lib/gin-orchestrator/0.1/templates'))) 'gin-orchestrator copied templates'
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $TestHome '.local/lib/gin-orchestrator/0.1/worktree-create.sh'))) 'gin-orchestrator copied worktree scripts'
    Assert-Exists (Join-Path $TestHome '.local/bin/gin-orchestrator.cmd')

    $linkProject = Join-Path $TestRoot 'link-project'
    New-Item -ItemType Directory -Path $linkProject | Out-Null
    $sourceAgents = Join-Path $Root 'plugins/gin-workflow/src/agents'
    $sourceSnapshots = @{}
    foreach ($sourceAgent in Get-ChildItem -LiteralPath $sourceAgents -Filter '*.md' -File) {
        $sourceSnapshots[$sourceAgent.FullName] = [IO.File]::ReadAllBytes($sourceAgent.FullName)
    }
    try {
        $linkOutput = Invoke-Installer @{ Platform = 'claude'; Project = $linkProject; Link = $true } 3>&1 | Out-String
        foreach ($snapshot in $sourceSnapshots.GetEnumerator()) {
            $sourceAfter = [IO.File]::ReadAllBytes($snapshot.Key)
            Assert-True `
                ([Convert]::ToBase64String($snapshot.Value) -eq [Convert]::ToBase64String($sourceAfter)) `
                "Linked Claude installation modified source agent $($snapshot.Key)"
        }
        $linkedSkill = Get-Item -LiteralPath (Join-Path $linkProject '.claude/skills/setup')
        if ($linkOutput.Contains('copying instead')) {
            # Symlinks unavailable (Windows without Developer Mode): the copy fallback must warn exactly once.
            Assert-True (([regex]::Matches($linkOutput, 'copying instead')).Count -eq 1) 'Link fallback warning was not emitted exactly once'
        }
        else {
            Assert-True ($null -ne $linkedSkill.LinkType) 'Linked installation copied a non-templated skill instead of linking it'
        }
        $linkedAgent = Join-Path $linkProject '.claude/agents/developer.md'
        Assert-True ($null -eq (Get-Item -LiteralPath $linkedAgent).LinkType) 'Templated Claude agent remained a source symlink'
        $linkedContent = [IO.File]::ReadAllText($linkedAgent)
        Assert-Contains $linkedContent '"Read"'
        Assert-True (-not $linkedContent.Contains('"view_file"', [StringComparison]::Ordinal)) 'Claude agent was not templated'
    }
    finally {
        foreach ($snapshot in $sourceSnapshots.GetEnumerator()) {
            if ([Convert]::ToBase64String($snapshot.Value) -ne [Convert]::ToBase64String([IO.File]::ReadAllBytes($snapshot.Key))) {
                [IO.File]::WriteAllBytes($snapshot.Key, $snapshot.Value)
            }
        }
    }

    if ($IsWindows) {
        # -Link falls back to copying without Developer Mode; either way the skill must exist.
        Assert-Exists (Join-Path $linkProject '.claude/skills/setup/SKILL.md')
        $version = & cmd.exe /d /c (Join-Path $TestHome '.local/bin/gin.cmd') --version
        Assert-True (($version | Out-String).Trim() -eq 'gin 3.0') "Unexpected launcher version: $version"
        $rulesList = & cmd.exe /d /c (Join-Path $TestHome '.local/bin/gin.cmd') rules --list --repository $TestHome
        Assert-True (($rulesList | Out-String).Contains('core (plugin, core)')) "Launcher did not list the core rule pack: $rulesList"
    }

    foreach ($launcherCase in @(
        @{ Plugin = 'gin-workflow'; Name = 'gin'; Old = '2.1'; Current = '3.0' },
        @{ Plugin = 'gin-qa'; Name = 'gin-qa'; Old = '0.4'; Current = '0.11' },
        @{ Plugin = 'gin-orchestrator'; Name = 'gin-orchestrator'; Old = '0.0'; Current = '0.1' }
    )) {
        $launcherName = $launcherCase.Name
        $managedRoot = Join-Path $TestHome ".local/lib/$launcherName"
        $oldInstall = Join-Path $managedRoot $launcherCase.Old
        $oldLauncher = Join-Path $oldInstall $launcherName
        $shim = Join-Path $TestHome ".local/bin/$launcherName.cmd"
        New-Item -ItemType Directory -Path $oldInstall -Force | Out-Null
        [IO.File]::WriteAllText($oldLauncher, '# old launcher')
        $oldShim = "@echo off`r`npython `"$oldLauncher`" %*`r`n"
        [IO.File]::WriteAllText($shim, $oldShim, [Text.UTF8Encoding]::new($false))

        Invoke-Installer @{ Platform = 'codex'; Plugin = $launcherCase.Plugin; Project = $project } | Out-Null
        $upgradedShim = [IO.File]::ReadAllText($shim)
        Assert-Contains $upgradedShim (Join-Path $managedRoot "$($launcherCase.Current)/$launcherName")
        Assert-Exists $oldLauncher

        Invoke-Installer @{ Platform = 'codex'; Plugin = $launcherCase.Plugin; Project = $project } | Out-Null

        $nestedLauncher = Join-Path $managedRoot "$($launcherCase.Old)/nested/$launcherName"
        New-Item -ItemType Directory -Path (Split-Path -Parent $nestedLauncher) -Force | Out-Null
        [IO.File]::WriteAllText($nestedLauncher, '# nested launcher')
        $nestedShim = "@echo off`r`npython `"$nestedLauncher`" %*`r`n"
        [IO.File]::WriteAllText($shim, $nestedShim, [Text.UTF8Encoding]::new($false))
        $nestedBefore = [IO.File]::ReadAllBytes($shim)
        $nestedFailed = $false
        try {
            Invoke-Installer @{ Platform = 'codex'; Plugin = $launcherCase.Plugin; Project = $project } | Out-Null
        }
        catch {
            $nestedFailed = $true
            Assert-Contains $_.Exception.Message 'refusing to replace a different launcher'
        }
        Assert-True $nestedFailed 'Expected a nested managed launcher path to fail installation'
        Assert-True `
            ([Convert]::ToBase64String($nestedBefore) -eq [Convert]::ToBase64String([IO.File]::ReadAllBytes($shim))) `
            'Nested managed launcher shim was modified'
        [IO.File]::WriteAllText($shim, $upgradedShim, [Text.UTF8Encoding]::new($false))

        $foreignShim = "@echo off`r`necho foreign launcher`r`n"
        [IO.File]::WriteAllText($shim, $foreignShim, [Text.UTF8Encoding]::new($false))
        $before = [IO.File]::ReadAllBytes($shim)
        $collisionFailed = $false
        try {
            Invoke-Installer @{ Platform = 'codex'; Plugin = $launcherCase.Plugin; Project = $project } | Out-Null
        }
        catch {
            $collisionFailed = $true
            Assert-Contains $_.Exception.Message 'refusing to replace a different launcher'
        }
        Assert-True $collisionFailed 'Expected a foreign launcher collision to fail installation'
        $after = [IO.File]::ReadAllBytes($shim)
        Assert-True ([Convert]::ToBase64String($before) -eq [Convert]::ToBase64String($after)) 'Foreign launcher shim was modified'
        [IO.File]::WriteAllText($shim, $upgradedShim, [Text.UTF8Encoding]::new($false))
    }

    # Installing gin refreshes the add-ons whose launchers the installer manages.
    $staleAddon = Join-Path $TestHome '.local/lib/gin-qa/0.11/gin-qa'
    [IO.File]::WriteAllText($staleAddon, '# stale add-on copy')
    $refreshOutput = Invoke-Installer @{ Platform = 'codex'; Project = $project }
    Assert-Contains $refreshOutput 'Refreshing the installed gin-qa add-on.'
    Assert-True (-not [IO.File]::ReadAllText($staleAddon).Contains('# stale add-on copy')) 'gin-qa library copy was not refreshed'

    $shimText =[IO.File]::ReadAllText((Join-Path $TestHome '.local/bin/gin.cmd'))
    Assert-Contains $shimText 'py -3 -X utf8 "'
    Assert-Contains $shimText 'else (python -X utf8 "'
    Assert-True (-not $shimText.Contains('||')) 'shim must not chain the CLI with ||'
    if ($IsWindows) {
        $pathDryRun = Invoke-Installer @{ Platform = 'codex'; Project = $project; DryRun = $true; NoModifyPath = $false }
        Assert-Contains $pathDryRun 'would add'
        $noPathOutput = Invoke-Installer @{ Platform = 'codex'; Project = $project; NoModifyPath = $true }
        Assert-Contains $noPathOutput 'Add '
    }
    if ($IsWindows -and $env:GITHUB_ACTIONS) {
        $binDir = [IO.Path]::GetFullPath((Join-Path $TestHome '.local/bin')).TrimEnd('\', '/')
        Invoke-Installer @{ Platform = 'codex'; Project = $project; NoModifyPath = $false } | Out-Null
        Assert-True (([Environment]::GetEnvironmentVariable('Path', 'User') -split ';') -contains $binDir) 'user PATH entry missing after install'
        Invoke-Installer @{ Uninstall = $true; NoModifyPath = $false } | Out-Null
        Assert-True (-not (([Environment]::GetEnvironmentVariable('Path', 'User') -split ';') -contains $binDir)) 'user PATH entry still present after -Uninstall'
    }

    $mockLog = Join-Path $TestRoot 'harness-commands.log'
    $env:GIN_WORKFLOW_MOCK_LOG = $mockLog
    $mockBin = New-MockCommand -Name 'codex' -ExitCode 0
    $env:PATH = "$mockBin$([IO.Path]::PathSeparator)$OriginalPath"
    Invoke-Installer @{ Platform = 'codex' } | Out-Null
    $codexLog = [IO.File]::ReadAllText($mockLog)
    Assert-Contains $codexLog 'plugin marketplace add'
    Assert-Contains $codexLog 'plugin add gin@gin-workflow-marketplace'
    Assert-Contains $codexLog 'plugin remove gin-workflow@gin-workflow-marketplace'

    New-MockCommand -Name 'codex' -ExitCode 23 | Out-Null
    $codexFailureDetected = $false
    try {
        Invoke-Installer @{ Platform = 'codex' } | Out-Null
    }
    catch {
        $codexFailureDetected = $true
        Assert-Contains $_.Exception.Message 'exit code 23'
    }
    Assert-True $codexFailureDetected 'Expected a failing Codex registration command to fail installation'

    New-MockCommand -Name 'agy' -ExitCode 19 | Out-Null
    $agyFailureDetected = $false
    try {
        Invoke-Installer @{ Platform = 'antigravity' } | Out-Null
    }
    catch {
        $agyFailureDetected = $true
        Assert-Contains $_.Exception.Message 'exit code 19'
    }
    Assert-True $agyFailureDetected 'Expected a failing Antigravity registration command to fail installation'

    Invoke-Installer @{ Platform = 'opencode' } | Out-Null
    Assert-Exists (Join-Path $TestHome '.config/opencode/skills/gin/skills/setup/SKILL.md')
    # OpenCode selects a skill by its bare directory id, so gin's generic names get a gin- prefix.
    foreach ($skill in @('learn', 'sdd', 'team', 'worktrees', 'debugging', 'review-response', 'parallel-agents', 'report')) {
        $prefixedSkill = Join-Path $TestHome ".config/opencode/skills/gin/skills/gin-$skill/SKILL.md"
        Assert-Exists $prefixedSkill
        Assert-Contains ([IO.File]::ReadAllText($prefixedSkill)) "name: gin-$skill"
        Assert-True (-not (Test-Path -LiteralPath (Join-Path $TestHome ".config/opencode/skills/gin/skills/$skill"))) "OpenCode install kept skills/$skill"
    }
    Assert-Exists (Join-Path $TestHome '.config/opencode/skills/gin/agents/gin-developer.md')
    Assert-Exists (Join-Path $TestHome '.config/opencode/agents/gin-developer.md')
    Assert-Exists (Join-Path $TestHome '.config/opencode/skills/gin/references/stage-contract.md')
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $TestHome '.config/opencode/skills/gin/hooks'))) 'OpenCode install wrote hooks'

    $opencodeLinkProject = Join-Path $TestRoot 'opencode-link-project'
    New-Item -ItemType Directory -Path $opencodeLinkProject | Out-Null
    $sourceReport = Join-Path $Root 'plugins/gin-workflow/src/skills/report/SKILL.md'
    $reportBefore = [IO.File]::ReadAllBytes($sourceReport)
    Invoke-Installer @{ Platform = 'opencode'; Project = $opencodeLinkProject; Link = $true } | Out-Null
    Assert-Exists (Join-Path $opencodeLinkProject '.opencode/skills/setup/SKILL.md')
    Assert-Exists (Join-Path $opencodeLinkProject '.opencode/skills/gin-report/SKILL.md')
    Assert-True `
        ([Convert]::ToBase64String($reportBefore) -eq [Convert]::ToBase64String([IO.File]::ReadAllBytes($sourceReport))) `
        'Linked OpenCode install renamed the source report skill'

    $copilotDryRun = Invoke-Installer @{ Platform = 'copilot'; DryRun = $true }
    $copilotDist = Join-Path $Root 'plugins/gin-workflow/dist/copilot/gin'
    Assert-Contains $copilotDryRun 'Configuring Copilot plugin structure for gin-workflow'
    Assert-Contains $copilotDryRun "(dry-run) would install Copilot plugin from $copilotDist"
    Assert-Exists (Join-Path $copilotDist '.claude-plugin/plugin.json')
    Assert-Exists (Join-Path $copilotDist 'skills/setup/SKILL.md')
    Assert-Exists (Join-Path $copilotDist 'references/stage-contract.md')
    Assert-Exists (Join-Path $copilotDist 'hooks/hooks.json')
    Assert-Contains ([IO.File]::ReadAllText((Join-Path $copilotDist 'hooks/hooks.json'))) '/scripts/safety_check.py\"; if [ -f \"$s\" ]; then exec python3 \"$s\"'
    Assert-Exists (Join-Path $copilotDist 'agents/developer.md')
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $copilotDist 'commands'))) 'Copilot bundle has commands'

    Set-Content -LiteralPath $mockLog -Value '' -NoNewline
    New-MockCommand -Name 'copilot' -ExitCode 0 | Out-Null
    $copilotInstall = Invoke-Installer @{ Platform = 'copilot' }
    $copilotLog = [IO.File]::ReadAllText($mockLog)
    Assert-Contains $copilotInstall 'Registering gin with Copilot...'
    Assert-True (($copilotLog -split '\r?\n') -contains 'plugin uninstall gin') 'Copilot install did not replace the gin plugin'
    Assert-True (($copilotLog -split '\r?\n') -contains 'plugin uninstall gin-workflow') 'Copilot install did not remove the old gin-workflow plugin'
    Assert-Contains $copilotLog "plugin install $copilotDist"

    Set-Content -LiteralPath $mockLog -Value '' -NoNewline
    Invoke-Installer @{ Platform = 'copilot'; Plugin = 'all' } | Out-Null
    $copilotAllLog = [IO.File]::ReadAllText($mockLog)
    Assert-Contains $copilotAllLog "plugin install $copilotDist"
    Assert-Contains $copilotAllLog "plugin install $(Join-Path $Root 'plugins/gin-qa/dist/copilot/gin-qa')"
    $qaCopilotDev = Join-Path $Root 'plugins/gin-qa/dist/copilot/gin-qa/agents/e2e-tester.md'
    Assert-Exists $qaCopilotDev
    $qaCopilotDevText = [IO.File]::ReadAllText($qaCopilotDev)
    Assert-Contains $qaCopilotDevText '"bash", "edit"]'
    Assert-True (-not $qaCopilotDevText.Contains('"edit", "edit"', [StringComparison]::Ordinal)) 'Copilot agent has duplicate edit tool'

    $copilotProject = Join-Path $TestRoot 'copilot-project'
    New-Item -ItemType Directory -Path $copilotProject | Out-Null
    $copilotProjectOutput = & $Installer -Platform copilot -Project $copilotProject 3>&1 | Out-String
    Assert-Contains $copilotProjectOutput 'Copilot plugins are global; -Project skips copilot.'

    Set-Content -LiteralPath $mockLog -Value '' -NoNewline
    & $Installer -Uninstall | Out-Null
    $uninstallLog = [IO.File]::ReadAllText($mockLog) -split '\r?\n'
    Assert-True ($uninstallLog -contains 'plugin uninstall gin') 'Uninstall did not remove the gin Copilot plugin'
    Assert-True ($uninstallLog -contains 'plugin uninstall gin-workflow') 'Uninstall did not remove the old gin-workflow Copilot plugin'
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $TestHome '.config/opencode/agents/gin-developer.md'))) 'OpenCode global agent still present after uninstall'
    # Later blocks run without the stub.
    Remove-Item -LiteralPath (Join-Path $TestRoot "mock-bin/$(if ($IsWindows) { 'copilot.cmd' } else { 'copilot' })") -Force
    $env:PATH = $OriginalPath

    if (-not (Get-Command copilot -ErrorAction SilentlyContinue)) {
        $copilotSkip = Invoke-Installer @{ Platform = 'copilot' }
        Assert-Contains $copilotSkip "Copilot CLI not found; skipped registration. Run: copilot plugin install $(Join-Path $Root 'plugins/gin-workflow/dist/copilot/gin')"
    }

    $shim = Join-Path $TestHome '.local/bin/gin.cmd'
    $foreignShim = "@echo off`r`necho foreign launcher`r`n"
    [IO.File]::WriteAllText($shim, $foreignShim, [Text.UTF8Encoding]::new($false))

    $missingProjectFailed = $false
    try {
        Invoke-Installer @{ Platform = 'codex'; Project = (Join-Path $TestRoot 'missing') } | Out-Null
    }
    catch {
        $missingProjectFailed = $true
        Assert-Contains $_.Exception.Message 'does not exist'
    }
    Assert-True $missingProjectFailed 'Expected a missing project path to fail installation'

    $shimBeforeUninstall = [IO.File]::ReadAllBytes($shim)
    $foreignUninstall = & $Installer -Uninstall -NoModifyPath 3>&1 | Out-String
    Assert-Contains $foreignUninstall 'gin.cmd: not a gin launcher this installer manages'
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $Root 'plugins/gin-workflow/dist'))) 'Uninstall preserved gin-workflow dist output'
    Assert-Exists $shim
    Assert-True `
        ([Convert]::ToBase64String($shimBeforeUninstall) -eq [Convert]::ToBase64String([IO.File]::ReadAllBytes($shim))) `
        'Uninstall modified the user launcher shim'
    Assert-Exists (Join-Path $project '.codex/skills/setup/SKILL.md')

    # Upgrade over a managed 2.9 gin-workflow install: the old launcher and the old
    # plugin installs go, one platform at a time, and only after a real run.
    $legacyHome = Join-Path $TestRoot 'legacy-home'
    $env:HOME = $legacyHome
    $env:USERPROFILE = $legacyHome
    $legacyLauncher = Join-Path $legacyHome '.local/lib/gin-workflow/2.9/gin-workflow'
    $legacyShim = Join-Path $legacyHome '.local/bin/gin-workflow.cmd'
    $legacyClaude = Join-Path $legacyHome '.claude/skills/gin-workflow'
    $legacyOpenCode = Join-Path $legacyHome '.config/opencode/skills/gin-workflow'
    $legacyAgents = Join-Path $legacyHome '.config/opencode/agents'
    $legacySettings = Join-Path $legacyHome '.claude/settings.json'
    foreach ($directory in @((Split-Path -Parent $legacyLauncher), (Split-Path -Parent $legacyShim), $legacyClaude, $legacyOpenCode, $legacyAgents)) {
        New-Item -ItemType Directory -Path $directory -Force | Out-Null
    }
    [IO.File]::WriteAllText($legacyLauncher, '# old launcher')
    [IO.File]::WriteAllText($legacyShim, "@echo off`r`npython `"$legacyLauncher`" %*`r`n", [Text.UTF8Encoding]::new($false))
    [IO.File]::WriteAllText($legacySettings, '{"enabledPlugins": {"gin-workflow@skills-dir": true}}')
    foreach ($agent in @('gin-workflow-developer.md', 'gin-qa-e2e-tester.md', 'gin-mine.md')) {
        [IO.File]::WriteAllText((Join-Path $legacyAgents $agent), '# agent')
    }
    # Claude Code counts as installed when a `claude` command exists.
    $env:PATH = "$(New-MockCommand -Name 'claude' -ExitCode 0)$([IO.Path]::PathSeparator)$OriginalPath"

    $legacyDryRun = Invoke-Installer @{ Platform = 'claude'; DryRun = $true }
    Assert-Contains $legacyDryRun 'would remove the gin-workflow launcher at'
    Assert-Contains $legacyDryRun '(dry-run) would remove the old gin-workflow plugin installs'
    foreach ($path in @($legacyShim, $legacyLauncher, $legacyClaude)) {
        Assert-Exists $path
    }
    Assert-True ((Get-Content -Raw -LiteralPath $legacySettings | ConvertFrom-Json -AsHashtable).enabledPlugins.Contains('gin-workflow@skills-dir')) 'Dry-run changed the Claude settings'

    Invoke-Installer @{ Platform = 'claude' } | Out-Null
    foreach ($path in @($legacyShim, (Join-Path $legacyHome '.local/lib/gin-workflow'), $legacyClaude)) {
        Assert-True (-not (Test-Path -LiteralPath $path)) "Upgrade kept the old $path"
    }
    $enabledPlugins = (Get-Content -Raw -LiteralPath $legacySettings | ConvertFrom-Json -AsHashtable).enabledPlugins
    Assert-True (-not $enabledPlugins.Contains('gin-workflow@skills-dir')) 'Upgrade kept the gin-workflow@skills-dir key'
    Assert-True ($enabledPlugins['gin@skills-dir'] -eq $true) 'Upgrade did not enable gin@skills-dir'
    Assert-Exists (Join-Path $legacyHome '.claude/skills/gin/skills/learn/SKILL.md')
    Assert-Exists (Join-Path $legacyHome '.local/bin/gin.cmd')
    Assert-Exists $legacyOpenCode
    if ($IsWindows) {
        $legacyVersion = & cmd.exe /d /c (Join-Path $legacyHome '.local/bin/gin.cmd') --version
        Assert-True (($legacyVersion | Out-String).Trim() -eq 'gin 3.0') "Unexpected launcher version after the upgrade: $legacyVersion"
    }

    Invoke-Installer @{ Platform = 'opencode' } | Out-Null
    Assert-True (-not (Test-Path -LiteralPath $legacyOpenCode)) 'Upgrade kept the old OpenCode skills'
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $legacyAgents 'gin-workflow-developer.md'))) 'Upgrade kept the old OpenCode agent'
    foreach ($agent in @('gin-developer.md', 'gin-qa-e2e-tester.md', 'gin-mine.md')) {
        Assert-Exists (Join-Path $legacyAgents $agent)
    }

    # Uninstall removes the managed launcher and the OpenCode install under both names.
    New-Item -ItemType Directory -Path $legacyOpenCode -Force | Out-Null
    [IO.File]::WriteAllText((Join-Path $legacyAgents 'gin-workflow-developer.md'), '# old agent')
    Invoke-Installer @{ Uninstall = $true } | Out-Null
    foreach ($path in @(
        (Join-Path $legacyHome '.local/bin/gin.cmd'),
        (Join-Path $legacyHome '.local/lib/gin'),
        (Join-Path $legacyHome '.config/opencode/skills/gin'),
        $legacyOpenCode,
        (Join-Path $legacyAgents 'gin-developer.md'),
        (Join-Path $legacyAgents 'gin-workflow-developer.md')
    )) {
        Assert-True (-not (Test-Path -LiteralPath $path)) "Uninstall kept $path"
    }
    Assert-Exists (Join-Path $legacyAgents 'gin-qa-e2e-tester.md')
    Assert-Exists (Join-Path $legacyAgents 'gin-mine.md')

    # An unparsable Claude settings.json stops the upgrade before the old Claude
    # install or the settings file is touched.
    $badHome = Join-Path $TestRoot 'bad-settings-home'
    $env:HOME = $badHome
    $env:USERPROFILE = $badHome
    $badClaude = Join-Path $badHome '.claude/skills/gin-workflow'
    $badSettings = Join-Path $badHome '.claude/settings.json'
    foreach ($badContent in @('', '// comment', '[]', '{"enabledPlugins": []}')) {
        if (Test-Path -LiteralPath $badHome) {
            Remove-Item -LiteralPath $badHome -Recurse -Force
        }
        New-Item -ItemType Directory -Path $badClaude -Force | Out-Null
        [IO.File]::WriteAllText($badSettings, $badContent)
        $badBefore = [IO.File]::ReadAllBytes($badSettings)
        $badFailed = $false
        try {
            Invoke-Installer @{ Platform = 'claude' } | Out-Null
        }
        catch {
            $badFailed = $true
            Assert-Contains $_.Exception.Message "Error: cannot parse $badSettings; fix it and re-run ./install.ps1"
        }
        Assert-True $badFailed "Expected an unparsable settings.json ('$badContent') to fail installation"
        Assert-Exists $badClaude
        Assert-True `
            ([Convert]::ToBase64String($badBefore) -eq [Convert]::ToBase64String([IO.File]::ReadAllBytes($badSettings))) `
            "Installer changed the unparsable settings.json ('$badContent')"
    }

    # A gin-workflow file the installer does not manage is kept and reported.
    $foreignHome = Join-Path $TestRoot 'foreign-legacy-home'
    $env:HOME = $foreignHome
    $env:USERPROFILE = $foreignHome
    $foreignLegacyShim = Join-Path $foreignHome '.local/bin/gin-workflow.cmd'
    $foreignLegacyRoot = Join-Path $foreignHome '.local/lib/gin-workflow/2.9'
    New-Item -ItemType Directory -Path (Split-Path -Parent $foreignLegacyShim) -Force | Out-Null
    New-Item -ItemType Directory -Path $foreignLegacyRoot -Force | Out-Null
    [IO.File]::WriteAllText($foreignLegacyShim, "@echo off`r`necho my own gin-workflow`r`n", [Text.UTF8Encoding]::new($false))
    $foreignLegacyBefore = [IO.File]::ReadAllBytes($foreignLegacyShim)
    $foreignOutput = & $Installer -Platform opencode -NoModifyPath 3>&1 | Out-String
    Assert-Contains $foreignOutput 'gin-workflow.cmd: not a gin-workflow launcher this installer manages'
    Assert-True `
        ([Convert]::ToBase64String($foreignLegacyBefore) -eq [Convert]::ToBase64String([IO.File]::ReadAllBytes($foreignLegacyShim))) `
        'Foreign gin-workflow launcher was modified'
    Assert-Exists $foreignLegacyRoot
    Assert-Exists (Join-Path $foreignHome '.local/bin/gin.cmd')
    $env:PATH = $OriginalPath

    Write-Host 'PowerShell installer smoke tests passed.'
}
finally {
    $env:HOME = $OriginalHome
    $env:USERPROFILE = $OriginalUserProfile
    $env:PATH = $OriginalPath
    Remove-Item -LiteralPath $TestRoot -Recurse -Force -ErrorAction SilentlyContinue
}
