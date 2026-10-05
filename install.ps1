#requires -Version 7.0
[CmdletBinding()]
param(
    [ValidateSet('claude', 'antigravity', 'codex', 'both', 'all')]
    [string]$Platform = 'all',
    [ValidateSet('gin-workflow', 'gin-qa', 'all')]
    [string]$Plugin = 'gin-workflow',
    [switch]$Link,
    [string]$Project,
    [switch]$Uninstall,
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$LauncherVersion = '2.7'
$QaLauncherVersion = '0.4'
$ScriptRoot = $PSScriptRoot
$UserHome = $env:HOME
if ([string]::IsNullOrWhiteSpace($UserHome)) {
    $UserHome = $HOME
}
$UserHome = [IO.Path]::GetFullPath($UserHome)

function Test-Platform {
    param([Parameter(Mandatory)][string]$Name)
    return $Platform -eq $Name -or $Platform -eq 'both' -or $Platform -eq 'all'
}

function New-Directory {
    param([Parameter(Mandatory)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }
}

function Write-Utf8File {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$Content
    )
    New-Directory (Split-Path -Parent $Path)
    [IO.File]::WriteAllText($Path, $Content, [Text.UTF8Encoding]::new($false))
}

function Copy-DirectoryContent {
    param(
        [Parameter(Mandatory)][string]$Source,
        [Parameter(Mandatory)][string]$Destination,
        [switch]$AsLink
    )
    if (-not (Test-Path -LiteralPath $Source -PathType Container)) {
        return
    }
    New-Directory $Destination
    foreach ($item in Get-ChildItem -LiteralPath $Source -Force) {
        $target = Join-Path $Destination $item.Name
        if (Test-Path -LiteralPath $target) {
            Remove-Item -LiteralPath $target -Recurse -Force
        }
        if ($AsLink) {
            try {
                New-Item -ItemType SymbolicLink -Path $target -Target $item.FullName | Out-Null
            }
            catch {
                throw "Unable to create symbolic link '$target'. Enable Windows Developer Mode or run PowerShell with suitable privileges. $($_.Exception.Message)"
            }
        }
        else {
            Copy-Item -LiteralPath $item.FullName -Destination $target -Recurse -Force
        }
    }
}

function Copy-PluginSource {
    param(
        [Parameter(Mandatory)][string]$PluginSource,
        [Parameter(Mandatory)][string]$Destination
    )
    foreach ($directory in @('commands', 'skills', 'agents', 'scripts', 'references', 'examples', 'rules', 'templates')) {
        Copy-DirectoryContent `
            -Source (Join-Path $PluginSource $directory) `
            -Destination (Join-Path $Destination $directory) `
            -AsLink:$Link
    }
}

function New-PluginManifest {
    param(
        [Parameter(Mandatory)][string]$PluginDirectory,
        [Parameter(Mandatory)][string]$OutputPath,
        [switch]$IncludeSchema
    )
    $metadata = Get-Content -LiteralPath (Join-Path $PluginDirectory 'plugin.meta.json') -Raw | ConvertFrom-Json
    $manifest = [ordered]@{
        name = $metadata.name
        version = $metadata.version
        description = $metadata.description
        author = $metadata.author
        repository = $metadata.repository
    }
    if ($IncludeSchema) {
        $manifest['$schema'] = 'https://antigravity.google/schemas/v1/plugin.json'
    }
    Write-Utf8File -Path $OutputPath -Content (($manifest | ConvertTo-Json -Depth 10) + "`n")
}

function New-HooksFile {
    param(
        [Parameter(Mandatory)][ValidateSet('claude', 'antigravity', 'codex')][string]$Harness,
        [Parameter(Mandatory)][string]$OutputPath,
        [Parameter(Mandatory)][string]$HooksRoot
    )
    if ($Harness -eq 'antigravity') {
        $root = '${PLUGIN_ROOT:-' + $HooksRoot + '}'
        $hooks = [ordered]@{
            PreToolUse = [ordered]@{
                matcher = 'Bash|run_command'
                type = 'command'
                command = "$root/scripts/safety-check.sh"
                timeout = 30
            }
            PostToolUse = [ordered]@{
                matcher = 'write_to_file|replace_file_content'
                type = 'command'
                command = "$root/scripts/post-edit.sh"
            }
        }
    }
    else {
        $preMatcher = if ($Harness -eq 'claude') { 'Bash' } else { 'Bash|run_command' }
        $postMatcher = if ($Harness -eq 'claude') { 'Write|Edit' } else { 'write_to_file|replace_file_content' }
        $hooks = [ordered]@{
            hooks = [ordered]@{
                PreToolUse = @([ordered]@{
                    matcher = $preMatcher
                    hooks = @([ordered]@{
                        type = 'command'
                        command = "$HooksRoot/scripts/safety-check.sh"
                        timeout = 30
                    })
                })
                PostToolUse = @([ordered]@{
                    matcher = $postMatcher
                    hooks = @([ordered]@{
                        type = 'command'
                        command = "$HooksRoot/scripts/post-edit.sh"
                    })
                })
            }
        }
        if ($Harness -eq 'codex') {
            $hooks = [ordered]@{
                description = 'Gin workflow safety and post-edit hooks for Codex.'
                hooks = $hooks.hooks
            }
        }
    }
    Write-Utf8File -Path $OutputPath -Content (($hooks | ConvertTo-Json -Depth 20) + "`n")
}

function Convert-ClaudeAgents {
    param([Parameter(Mandatory)][string]$AgentsDirectory)
    if (-not (Test-Path -LiteralPath $AgentsDirectory -PathType Container)) {
        return
    }
    foreach ($agent in Get-ChildItem -LiteralPath $AgentsDirectory -Filter '*.md' -File) {
        $content = Get-Content -LiteralPath $agent.FullName -Raw
        $content = $content.Replace('"view_file"', '"Read"')
        $content = $content.Replace('"grep_search"', '"Grep"')
        $content = $content.Replace('"list_dir"', '"Glob"')
        $content = $content.Replace('"search_web"', '"WebSearch"')
        $content = $content.Replace('"run_command"', '"Bash"')
        if ($Link -and $null -ne $agent.LinkType) {
            Remove-Item -LiteralPath $agent.FullName -Force
        }
        Write-Utf8File -Path $agent.FullName -Content $content
    }
}

function Install-PlatformLayout {
    param(
        [Parameter(Mandatory)][ValidateSet('claude', 'antigravity', 'codex')][string]$Harness,
        [Parameter(Mandatory)][string]$PluginDirectory,
        [Parameter(Mandatory)][string]$Destination,
        [Parameter(Mandatory)][string]$HooksRoot,
        [string]$ManifestPath
    )
    Copy-PluginSource -PluginSource (Join-Path $PluginDirectory 'src') -Destination $Destination
    if (Test-Path -LiteralPath (Join-Path $PluginDirectory 'src/hooks') -PathType Container) {
        New-HooksFile -Harness $Harness -OutputPath (Join-Path $Destination 'hooks/hooks.json') -HooksRoot $HooksRoot
    }
    if ($Harness -eq 'claude') {
        Convert-ClaudeAgents -AgentsDirectory (Join-Path $Destination 'agents')
    }
    if (-not [string]::IsNullOrWhiteSpace($ManifestPath)) {
        New-PluginManifest `
            -PluginDirectory $PluginDirectory `
            -OutputPath $ManifestPath `
            -IncludeSchema:($Harness -eq 'antigravity')
    }
}

function Enable-ClaudePlugin {
    param([Parameter(Mandatory)][string]$Name)
    $settingsPath = Join-Path $UserHome '.claude/settings.json'
    $settings = [ordered]@{}
    if (Test-Path -LiteralPath $settingsPath -PathType Leaf) {
        try {
            $existing = Get-Content -LiteralPath $settingsPath -Raw | ConvertFrom-Json -AsHashtable
            if ($null -ne $existing) {
                $settings = $existing
            }
        }
        catch {
            $settings = [ordered]@{}
        }
    }
    if (-not $settings.Contains('enabledPlugins')) {
        $settings.enabledPlugins = [ordered]@{}
    }
    $settings.enabledPlugins["$Name@skills-dir"] = $true
    Write-Utf8File -Path $settingsPath -Content (($settings | ConvertTo-Json -Depth 20) + "`n")
}

function Test-ManagedLauncherShim {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$ManagedRoot,
        [string]$Name = 'gin-workflow'
    )
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $false
    }
    $content = [IO.File]::ReadAllText($Path).Replace("`r`n", "`n").Replace("`r", "`n")
    if ($content -notmatch '\A@echo off\npython "([^"\n]+)" %\*\n?\z') {
        return $false
    }
    $candidate = $Matches[1].Replace('%USERPROFILE%', $UserHome, [StringComparison]::OrdinalIgnoreCase)
    try {
        $candidate = [IO.Path]::GetFullPath($candidate)
        $managed = [IO.Path]::GetFullPath($ManagedRoot).TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)
    }
    catch {
        return $false
    }
    if (-not [IO.Path]::GetFileName($candidate).Equals($Name, [StringComparison]::OrdinalIgnoreCase)) {
        return $false
    }
    $versionDirectory = [IO.Directory]::GetParent($candidate)
    if ($null -eq $versionDirectory -or $versionDirectory.Name -in @('', '.', '..')) {
        return $false
    }
    $ownerDirectory = $versionDirectory.Parent
    if ($null -eq $ownerDirectory) {
        return $false
    }
    return $ownerDirectory.FullName.TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar).Equals(
        $managed,
        [StringComparison]::OrdinalIgnoreCase
    )
}

function Install-Launcher {
    param(
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][string]$Version
    )
    $sourceDirectory = Join-Path $ScriptRoot "plugins/$Name/src/scripts"
    $managedRoot = Join-Path $UserHome ".local/lib/$Name"
    $installDirectory = Join-Path $managedRoot $Version
    $launcherTarget = Join-Path $installDirectory $Name
    $launcherShim = Join-Path $UserHome ".local/bin/$Name.cmd"
    $packages = if ($Name -eq 'gin-workflow') { @('workflow_core', 'workflow_providers', 'review_ledger') } else { @('gin_qa') }

    if (Test-Path -LiteralPath $launcherShim) {
        if (-not (Test-ManagedLauncherShim -Path $launcherShim -ManagedRoot $managedRoot -Name $Name)) {
            throw "Error: refusing to replace a different launcher at $launcherShim"
        }
    }

    if ($Name -eq 'gin-qa') {
        $workflowShim = Join-Path $UserHome '.local/bin/gin-workflow.cmd'
        if (-not (Test-Path -LiteralPath $workflowShim) -and -not (Get-Command gin-workflow -ErrorAction SilentlyContinue)) {
            Write-Warning 'gin-workflow is not installed; gin-qa needs it (./install.ps1 -Plugin gin-workflow).'
        }
    }

    if ($DryRun) {
        Write-Output "(dry-run) would install $Name launcher version $Version to $launcherTarget"
        Write-Output "(dry-run) would install $Name launcher shim at $launcherShim"
        return
    }

    New-Directory (Split-Path -Parent $launcherShim)
    Copy-Item -LiteralPath (Join-Path $sourceDirectory $Name) -Destination $launcherTarget -Force
    foreach ($package in $packages) {
        New-Directory (Join-Path $installDirectory $package)
        Copy-DirectoryContent `
            -Source (Join-Path $sourceDirectory $package) `
            -Destination (Join-Path $installDirectory $package)
    }
    if ($Name -eq 'gin-workflow') {
        Copy-DirectoryContent `
            -Source (Join-Path (Split-Path -Parent $sourceDirectory) 'rules') `
            -Destination (Join-Path $installDirectory 'rules')
    }
    if ($Name -eq 'gin-qa') {
        New-Directory (Join-Path $installDirectory 'templates')
    }
    Copy-DirectoryContent `
        -Source (Join-Path (Split-Path -Parent $sourceDirectory) 'templates') `
        -Destination (Join-Path $installDirectory 'templates')

    $shimContent = "@echo off`r`npython `"$launcherTarget`" %*`r`n"
    $temporaryShim = "$launcherShim.$([guid]::NewGuid().ToString('N')).tmp"
    try {
        Write-Utf8File -Path $temporaryShim -Content $shimContent
        Move-Item -LiteralPath $temporaryShim -Destination $launcherShim -Force
    }
    finally {
        if (Test-Path -LiteralPath $temporaryShim) {
            Remove-Item -LiteralPath $temporaryShim -Force
        }
    }

    Write-Output "Installed $Name launcher version $Version to $launcherShim"
    if ($Name -eq 'gin-workflow') {
        $launcherBin = [IO.Path]::GetFullPath((Split-Path -Parent $launcherShim)).TrimEnd('\', '/')
        $pathContainsLauncher = $false
        foreach ($entry in ($env:PATH -split [Regex]::Escape([IO.Path]::PathSeparator))) {
            if ([string]::IsNullOrWhiteSpace($entry)) {
                continue
            }
            try {
                if ([IO.Path]::GetFullPath($entry).TrimEnd('\', '/').Equals($launcherBin, [StringComparison]::OrdinalIgnoreCase)) {
                    $pathContainsLauncher = $true
                    break
                }
            }
            catch {
                continue
            }
        }
        if (-not $pathContainsLauncher) {
            Write-Warning "$launcherBin is not on PATH."
        }
    }
}

function Invoke-NativeCommand {
    param(
        [Parameter(Mandatory)][string]$Executable,
        [Parameter(Mandatory)][string[]]$CommandArguments
    )
    & $Executable @CommandArguments
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        $displayCommand = (@($Executable) + $CommandArguments) -join ' '
        throw "Error: native command '$displayCommand' failed with exit code $exitCode"
    }
}

function Install-Plugin {
    param([Parameter(Mandatory)][string]$Name)
    $pluginDirectory = Join-Path $ScriptRoot "plugins/$Name"
    if (-not (Test-Path -LiteralPath $pluginDirectory -PathType Container)) {
        Write-Warning "Plugin directory '$pluginDirectory' not found. Skipping."
        return
    }

    Write-Output '=========================================='
    Write-Output "Processing plugin: $Name"
    Write-Output '=========================================='

    if (-not [string]::IsNullOrWhiteSpace($Project)) {
        if ($DryRun) {
            Write-Output "(dry-run) would install project-level configs for $Name to $Project"
            return
        }
        if (Test-Platform 'claude') {
            $target = Join-Path $Project '.claude'
            Install-PlatformLayout -Harness claude -PluginDirectory $pluginDirectory -Destination $target -HooksRoot '${CLAUDE_PROJECT_DIR}/.claude' -ManifestPath (Join-Path $target '.claude-plugin/plugin.json')
        }
        if (Test-Platform 'antigravity') {
            $target = Join-Path $Project '.agents'
            Install-PlatformLayout -Harness antigravity -PluginDirectory $pluginDirectory -Destination $target -HooksRoot $target -ManifestPath (Join-Path $target 'plugin.json')
        }
        if (Test-Platform 'codex') {
            $target = Join-Path $Project '.codex'
            Install-PlatformLayout -Harness codex -PluginDirectory $pluginDirectory -Destination $target -HooksRoot '${PLUGIN_ROOT}' -ManifestPath (Join-Path $target '.codex-plugin/plugin.json')
        }
        return
    }

    $distDirectory = Join-Path $pluginDirectory 'dist'
    # dist/ is fully generated: rebuild each selected platform from scratch so files
    # removed from src (commands, skills) never linger and shadow same-name skills.
    if (Test-Platform 'claude') {
        $target = Join-Path $distDirectory 'claude-code'
        if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Recurse -Force }
        Install-PlatformLayout -Harness claude -PluginDirectory $pluginDirectory -Destination $target -HooksRoot '${CLAUDE_PLUGIN_ROOT}' -ManifestPath (Join-Path $target '.claude-plugin/plugin.json')
    }
    if (Test-Platform 'antigravity') {
        $target = Join-Path $distDirectory 'antigravity'
        if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Recurse -Force }
        $installedRoot = Join-Path $UserHome ".gemini/config/plugins/$Name"
        Install-PlatformLayout -Harness antigravity -PluginDirectory $pluginDirectory -Destination $target -HooksRoot $installedRoot -ManifestPath (Join-Path $target 'plugin.json')
    }
    if (Test-Platform 'codex') {
        $target = Join-Path $distDirectory 'codex'
        if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Recurse -Force }
        Install-PlatformLayout -Harness codex -PluginDirectory $pluginDirectory -Destination $target -HooksRoot '${PLUGIN_ROOT}' -ManifestPath (Join-Path $target '.codex-plugin/plugin.json')
    }

    if ($DryRun) {
        Write-Output "(dry-run) registration skipped for $Name"
        if (Test-Platform 'claude') {
            Write-Output "(dry-run) would install global Claude Code plugin to $(Join-Path $UserHome ".claude/skills/$Name")"
        }
        return
    }

    if ((Test-Platform 'claude') -and (Get-Command claude -ErrorAction SilentlyContinue)) {
        $source = Join-Path $distDirectory 'claude-code'
        $destination = Join-Path $UserHome ".claude/skills/$Name"
        if (Test-Path -LiteralPath $destination) {
            Remove-Item -LiteralPath $destination -Recurse -Force
        }
        New-Directory (Split-Path -Parent $destination)
        if ($Link) {
            New-Item -ItemType SymbolicLink -Path $destination -Target $source | Out-Null
        }
        else {
            Copy-Item -LiteralPath $source -Destination $destination -Recurse -Force
        }
        Enable-ClaudePlugin -Name $Name
        Write-Output "Successfully installed and enabled $Name globally in Claude Code!"
    }
    if ((Test-Platform 'antigravity') -and (Get-Command agy -ErrorAction SilentlyContinue)) {
        Invoke-NativeCommand `
            -Executable 'agy' `
            -CommandArguments @('plugin', 'install', (Join-Path $distDirectory 'antigravity'))
    }
    if ((Test-Platform 'codex') -and (Get-Command codex -ErrorAction SilentlyContinue)) {
        Invoke-NativeCommand `
            -Executable 'codex' `
            -CommandArguments @('plugin', 'marketplace', 'add', $ScriptRoot)
        Invoke-NativeCommand `
            -Executable 'codex' `
            -CommandArguments @('plugin', 'add', "$Name@gin-workflow-marketplace")
    }
}

if (-not [string]::IsNullOrWhiteSpace($Project)) {
    if (-not (Test-Path -LiteralPath $Project -PathType Container)) {
        throw "Error: --project directory '$Project' does not exist"
    }
    $Project = [IO.Path]::GetFullPath((Resolve-Path -LiteralPath $Project).Path)
}

$Plugins = switch ($Plugin) {
    'all' { @('gin-workflow', 'gin-qa') }
    default { @($Plugin) }
}

if ($Uninstall) {
    foreach ($directory in @(
        (Join-Path $ScriptRoot 'plugins/gin-workflow/dist'),
        (Join-Path $ScriptRoot 'plugins/gin-workflow-advanced/dist'),
        (Join-Path $ScriptRoot 'plugins/gin-qa/dist')
    )) {
        if (Test-Path -LiteralPath $directory) {
            Remove-Item -LiteralPath $directory -Recurse -Force
        }
    }
    Write-Output 'Cleaned built dist folders. Perform CLI manual uninstall/disable if registered globally.'
    return
}

foreach ($name in $Plugins) {
    $version = if ($name -eq 'gin-workflow') { $LauncherVersion } else { $QaLauncherVersion }
    Install-Launcher -Name $name -Version $version
    Install-Plugin -Name $name
}
Write-Output 'Install processes completed successfully!'
