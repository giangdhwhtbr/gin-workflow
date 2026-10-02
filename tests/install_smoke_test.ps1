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
    Assert-Contains $dryRunOutput 'would install gin-workflow launcher version 2.5'
    Assert-Exists (Join-Path $Root 'plugins/gin-workflow/dist/codex/.codex-plugin/plugin.json')
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $TestHome '.local/bin/gin-workflow.cmd'))) 'Dry-run wrote the launcher shim'

    $project = Join-Path $TestRoot 'project'
    New-Item -ItemType Directory -Path $project | Out-Null
    Invoke-Installer @{ Platform = 'all'; Project = $project } | Out-Null
    Assert-Exists (Join-Path $project '.claude/skills/setup/SKILL.md')
    Assert-Exists (Join-Path $project '.agents/skills/setup/SKILL.md')
    Assert-Exists (Join-Path $project '.codex/skills/setup/SKILL.md')
    Assert-Exists (Join-Path $project '.codex/.codex-plugin/plugin.json')
    Assert-Exists (Join-Path $TestHome '.local/lib/gin-workflow/2.5/workflow_core/cli.py')
    Assert-Exists (Join-Path $TestHome '.local/bin/gin-workflow.cmd')

    $linkProject = Join-Path $TestRoot 'link-project'
    New-Item -ItemType Directory -Path $linkProject | Out-Null
    $sourceAgents = Join-Path $Root 'plugins/gin-workflow/src/agents'
    $sourceSnapshots = @{}
    foreach ($sourceAgent in Get-ChildItem -LiteralPath $sourceAgents -Filter '*.md' -File) {
        $sourceSnapshots[$sourceAgent.FullName] = [IO.File]::ReadAllBytes($sourceAgent.FullName)
    }
    try {
        Invoke-Installer @{ Platform = 'claude'; Project = $linkProject; Link = $true } | Out-Null
        foreach ($snapshot in $sourceSnapshots.GetEnumerator()) {
            $sourceAfter = [IO.File]::ReadAllBytes($snapshot.Key)
            Assert-True `
                ([Convert]::ToBase64String($snapshot.Value) -eq [Convert]::ToBase64String($sourceAfter)) `
                "Linked Claude installation modified source agent $($snapshot.Key)"
        }
        $linkedSkill = Get-Item -LiteralPath (Join-Path $linkProject '.claude/skills/setup')
        Assert-True ($null -ne $linkedSkill.LinkType) 'Linked installation copied a non-templated skill instead of linking it'
        $linkedAgent = Join-Path $linkProject '.claude/agents/solution-architect.md'
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
        $version = & cmd.exe /d /c (Join-Path $TestHome '.local/bin/gin-workflow.cmd') --version
        Assert-True (($version | Out-String).Trim() -eq 'gin-workflow 2.5') "Unexpected launcher version: $version"
    }

    $managedRoot = Join-Path $TestHome '.local/lib/gin-workflow'
    $oldInstall = Join-Path $managedRoot '2.1'
    $oldLauncher = Join-Path $oldInstall 'gin-workflow'
    $shim = Join-Path $TestHome '.local/bin/gin-workflow.cmd'
    New-Item -ItemType Directory -Path $oldInstall -Force | Out-Null
    [IO.File]::WriteAllText($oldLauncher, '# old launcher')
    $oldShim = "@echo off`r`npython `"$oldLauncher`" %*`r`n"
    [IO.File]::WriteAllText($shim, $oldShim, [Text.UTF8Encoding]::new($false))

    Invoke-Installer @{ Platform = 'codex'; Project = $project } | Out-Null
    $upgradedShim = [IO.File]::ReadAllText($shim)
    Assert-Contains $upgradedShim (Join-Path $managedRoot '2.5/gin-workflow')
    Assert-Exists $oldLauncher

    Invoke-Installer @{ Platform = 'codex'; Project = $project } | Out-Null

    $nestedLauncher = Join-Path $managedRoot '2.1/nested/gin-workflow'
    New-Item -ItemType Directory -Path (Split-Path -Parent $nestedLauncher) -Force | Out-Null
    [IO.File]::WriteAllText($nestedLauncher, '# nested launcher')
    $nestedShim = "@echo off`r`npython `"$nestedLauncher`" %*`r`n"
    [IO.File]::WriteAllText($shim, $nestedShim, [Text.UTF8Encoding]::new($false))
    $nestedBefore = [IO.File]::ReadAllBytes($shim)
    $nestedFailed = $false
    try {
        Invoke-Installer @{ Platform = 'codex'; Project = $project } | Out-Null
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

    $mockLog = Join-Path $TestRoot 'harness-commands.log'
    $env:GIN_WORKFLOW_MOCK_LOG = $mockLog
    $mockBin = New-MockCommand -Name 'codex' -ExitCode 0
    $env:PATH = "$mockBin$([IO.Path]::PathSeparator)$OriginalPath"
    Invoke-Installer @{ Platform = 'codex' } | Out-Null
    $codexLog = [IO.File]::ReadAllText($mockLog)
    Assert-Contains $codexLog 'plugin marketplace add'
    Assert-Contains $codexLog 'plugin add gin-workflow@gin-workflow-marketplace'

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
    $env:PATH = $OriginalPath

    $foreignShim = "@echo off`r`necho foreign launcher`r`n"
    [IO.File]::WriteAllText($shim, $foreignShim, [Text.UTF8Encoding]::new($false))
    $before = [IO.File]::ReadAllBytes($shim)
    $collisionFailed = $false
    try {
        Invoke-Installer @{ Platform = 'codex'; Project = $project } | Out-Null
    }
    catch {
        $collisionFailed = $true
        Assert-Contains $_.Exception.Message 'refusing to replace a different launcher'
    }
    Assert-True $collisionFailed 'Expected a foreign launcher collision to fail installation'
    $after = [IO.File]::ReadAllBytes($shim)
    Assert-True ([Convert]::ToBase64String($before) -eq [Convert]::ToBase64String($after)) 'Foreign launcher shim was modified'

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
    Invoke-Installer @{ Uninstall = $true } | Out-Null
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $Root 'plugins/gin-workflow/dist'))) 'Uninstall preserved gin-workflow dist output'
    Assert-Exists $shim
    Assert-True `
        ([Convert]::ToBase64String($shimBeforeUninstall) -eq [Convert]::ToBase64String([IO.File]::ReadAllBytes($shim))) `
        'Uninstall modified the user launcher shim'
    Assert-Exists (Join-Path $project '.codex/skills/setup/SKILL.md')

    Write-Host 'PowerShell installer smoke tests passed.'
}
finally {
    $env:HOME = $OriginalHome
    $env:USERPROFILE = $OriginalUserProfile
    $env:PATH = $OriginalPath
    Remove-Item -LiteralPath $TestRoot -Recurse -Force -ErrorAction SilentlyContinue
}
