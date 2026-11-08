#requires -Version 7.0
[CmdletBinding()]
param(
    [ValidateSet('claude', 'antigravity', 'codex', 'opencode', 'copilot', 'both', 'all')]
    [string]$Platform = 'all',
    [ValidateSet('gin-workflow', 'gin-qa', 'gin-ba', 'gin-orchestrator', 'all')]
    [string]$Plugin = 'gin-workflow',
    [switch]$Link,
    [string]$Project,
    [switch]$Uninstall,
    [switch]$DryRun,
    [switch]$NoModifyPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$LauncherVersion = '3.0'
$QaLauncherVersion = '0.11'
$OrchLauncherVersion = '0.1'
$ScriptRoot = $PSScriptRoot
$UserHome = $env:HOME
if ([string]::IsNullOrWhiteSpace($UserHome)) {
    $UserHome = $HOME
}
$UserHome = [IO.Path]::GetFullPath($UserHome)
$script:LinkFallbackWarned = $false
if ($IsWindows) {
    Add-Type -Namespace GinWorkflow -Name NativeMethods -MemberDefinition '[DllImport("user32.dll", SetLastError = true, CharSet = CharSet.Auto)] public static extern IntPtr SendMessageTimeout(IntPtr hWnd, uint Msg, UIntPtr wParam, string lParam, uint fuFlags, uint uTimeout, out UIntPtr lpdwResult);'
}

function Test-Platform {
    param([Parameter(Mandatory)][string]$Name)
    return $Platform -eq $Name -or $Platform -eq 'both' -or $Platform -eq 'all'
}

# The plugin directory keeps its name; the plugin id (the `name` in its
# plugin.meta.json) names the launcher and every install target.
function Get-PluginId {
    param([Parameter(Mandatory)][string]$Name)
    if ($Name -eq 'gin-workflow') { return 'gin' }
    return $Name
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
        [switch]$AsLink,
        [switch]$LinkFiles
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
        if ($AsLink -and $LinkFiles -and $item.PSIsContainer) {
            # Link files, not directories (as `cp -rs` does), so a later rewrite
            # replaces only the link and never edits the source through it.
            Copy-DirectoryContent -Source $item.FullName -Destination $target -AsLink -LinkFiles
        }
        elseif ($AsLink) {
            try {
                New-Item -ItemType SymbolicLink -Path $target -Target $item.FullName | Out-Null
            }
            catch {
                if (-not $script:LinkFallbackWarned) {
                    Write-Warning "Unable to create symbolic link '$target'; copying instead. Enable Windows Developer Mode or run PowerShell with suitable privileges for -Link. $($_.Exception.Message)"
                    $script:LinkFallbackWarned = $true
                }
                Copy-Item -LiteralPath $item.FullName -Destination $target -Recurse -Force
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
                command = "python `"$root/scripts/safety_check.py`""
                timeout = 30
            }
        }
    }
    else {
        $preMatcher = if ($Harness -eq 'claude') { 'Bash' } else { 'Bash|run_command' }
        $hooks = [ordered]@{
            hooks = [ordered]@{
                PreToolUse = @([ordered]@{
                    matcher = $preMatcher
                    hooks = @([ordered]@{
                        type = 'command'
                        command = "python `"$HooksRoot/scripts/safety_check.py`""
                        timeout = 30
                    })
                })
            }
        }
        if ($Harness -eq 'codex') {
            $hooks = [ordered]@{
                description = 'Gin workflow safety hooks for Codex.'
                hooks = $hooks.hooks
            }
        }
    }
    Write-Utf8File -Path $OutputPath -Content (($hooks | ConvertTo-Json -Depth 20) + "`n")
}

function New-CopilotHooksFile {
    param([Parameter(Mandatory)][string]$OutputPath)
    $content = @'
{
  "version": 1,
  "hooks": {
    "PreToolUse": [
      {"type": "command", "matcher": "bash", "bash": "s=\"${PLUGIN_ROOT:-${COPILOT_HOME:-$HOME/.copilot}/installed-plugins/_direct/gin}/scripts/safety_check.py\"; if [ -f \"$s\" ]; then exec python3 \"$s\"; fi; echo \"gin: $s not found, hook skipped\" >&2", "timeoutSec": 30}
    ]
  }
}
'@ + "`n"
    Write-Utf8File -Path $OutputPath -Content $content
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
        $content = $content.Replace('"replace_file_content"', '"Edit"')
        $content = $content.Replace('"write_to_file"', '"Write"')
        if ($Link -and $null -ne $agent.LinkType) {
            Remove-Item -LiteralPath $agent.FullName -Force
        }
        Write-Utf8File -Path $agent.FullName -Content $content
    }
}

function Convert-CodexAgents {
    param([Parameter(Mandatory)][string]$AgentsDirectory)
    if (-not (Test-Path -LiteralPath $AgentsDirectory -PathType Container)) {
        return
    }
    foreach ($agent in Get-ChildItem -LiteralPath $AgentsDirectory -Filter '*.md' -File) {
        $content = [IO.File]::ReadAllText($agent.FullName)
        $content = [regex]::Replace($content, '(?m)^tools:.*\r?\n', '')
        if ($Link -and $null -ne $agent.LinkType) {
            Remove-Item -LiteralPath $agent.FullName -Force
        }
        Write-Utf8File -Path $agent.FullName -Content $content
    }
}

function Convert-CopilotAgents {
    param([Parameter(Mandatory)][string]$AgentsDirectory)
    if (-not (Test-Path -LiteralPath $AgentsDirectory -PathType Container)) {
        return
    }
    foreach ($agent in Get-ChildItem -LiteralPath $AgentsDirectory -Filter '*.md' -File) {
        $content = Get-Content -LiteralPath $agent.FullName -Raw
        $content = [regex]::Replace($content, '(?m)^tools:.*$', {
            param($match)
            $toolsLine = $match.Value
            $toolsLine = $toolsLine.Replace('"view_file"', '"view"')
            $toolsLine = $toolsLine.Replace('"grep_search"', '"grep"')
            $toolsLine = $toolsLine.Replace('"list_dir"', '"glob"')
            $toolsLine = $toolsLine.Replace('"search_web"', '"web_fetch"')
            $toolsLine = $toolsLine.Replace('"run_command"', '"bash"')
            $toolsLine = $toolsLine.Replace('"replace_file_content"', '"edit"')
            $toolsLine = $toolsLine.Replace('"write_to_file"', '"edit"')
            while ($toolsLine -match '"edit",\s*"edit"') {
                $toolsLine = [regex]::Replace($toolsLine, '"edit",\s*"edit"', '"edit"')
            }
            return $toolsLine
        })
        if ($Link -and $null -ne $agent.LinkType) {
            Remove-Item -LiteralPath $agent.FullName -Force
        }
        Write-Utf8File -Path $agent.FullName -Content $content
    }
}

function Convert-OpenCodeAgents {
    param(
        [Parameter(Mandatory)][string]$SourceDirectory,
        [Parameter(Mandatory)][string]$DestinationDirectory,
        [Parameter(Mandatory)][string]$PluginName
    )
    $sourceAgents = Join-Path $SourceDirectory 'agents'
    if (-not (Test-Path -LiteralPath $sourceAgents -PathType Container)) {
        return
    }
    $destAgents = Join-Path $DestinationDirectory 'agents'
    New-Directory $destAgents
    foreach ($agent in Get-ChildItem -LiteralPath $sourceAgents -Filter '*.md' -File) {
        $stem = [IO.Path]::GetFileNameWithoutExtension($agent.Name)
        $content = [IO.File]::ReadAllText($agent.FullName)
        $match = [regex]::Match($content, '(?s)\A---\r?\n(.*?)\r?\n---\r?\n(.*)\z')
        if ($match.Success) {
            $fm = $match.Groups[1].Value
            $body = $match.Groups[2].Value
            $lines = @()
            foreach ($line in $fm -split '\r?\n') {
                if ($line -match '^name:' -or $line -match '^tools:') {
                    continue
                }
                $lines += $line
            }
            $lines += 'mode: subagent'
            $newFm = $lines -join "`n"
            $newContent = "---`n$newFm`n---`n$body"
        }
        else {
            $newContent = $content
        }
        Write-Utf8File -Path (Join-Path $destAgents "$PluginName-$stem.md") -Content $newContent
    }
}

function Copy-BundleDirectories {
    param(
        [Parameter(Mandatory)][string]$Source,
        [Parameter(Mandatory)][string]$Destination,
        [switch]$LinkFiles
    )
    New-Directory $Destination
    foreach ($directory in @('skills', 'scripts', 'references', 'examples', 'rules', 'templates')) {
        Copy-DirectoryContent `
            -Source (Join-Path $Source $directory) `
            -Destination (Join-Path $Destination $directory) `
            -AsLink:$Link `
            -LinkFiles:$LinkFiles
    }
}

function Install-OpenCodeBundle {
    param(
        [Parameter(Mandatory)][string]$Source,
        [Parameter(Mandatory)][string]$Destination,
        [Parameter(Mandatory)][string]$InstallRoot,
        [Parameter(Mandatory)][string]$PluginName
    )
    # OpenCode loads skills, references, scripts, rules, and templates. It has no
    # use for the Claude/Codex commands/ files, and copying them would risk
    # clobbering a repository's own .opencode/commands. Agents are translated
    # into namespaced subagents (<plugin>-<agent>.md).
    Copy-BundleDirectories -Source $Source -Destination $Destination -LinkFiles
    Convert-OpenCodeAgents -SourceDirectory $Source -DestinationDirectory $Destination -PluginName $PluginName

    # OpenCode selects a skill by its bare directory id, so gin's generic skill
    # names get a gin- prefix, with the display `name` kept aligned.
    $prefixedSkills = if ($PluginName -eq 'gin') { @('learn', 'sdd', 'team', 'worktrees', 'debugging', 'review-response', 'parallel-agents', 'report') } else { @() }
    foreach ($skill in $prefixedSkills) {
        $skillDirectory = Join-Path $Destination "skills/$skill"
        if (-not (Test-Path -LiteralPath $skillDirectory)) {
            continue
        }
        $renamed = Join-Path $Destination "skills/gin-$skill"
        if (Test-Path -LiteralPath $renamed) {
            Remove-Item -LiteralPath $renamed -Recurse -Force
        }
        Move-Item -LiteralPath $skillDirectory -Destination $renamed
        $skillFile = Join-Path $renamed 'SKILL.md'
        if (Test-Path -LiteralPath $skillFile) {
            $content = [regex]::Replace([IO.File]::ReadAllText($skillFile), "(?m)^name: $([regex]::Escape($skill))`$", "name: gin-$skill")
            if ($null -ne (Get-Item -LiteralPath $skillFile).LinkType) {
                Remove-Item -LiteralPath $skillFile -Force
            }
            Write-Utf8File -Path $skillFile -Content $content
        }
    }

    # gin-qa's `setup` would shadow gin-workflow's `setup`, which has the same directory id.
    $setupDirectory = Join-Path $Destination 'skills/setup'
    if ($PluginName -eq 'gin-qa' -and (Test-Path -LiteralPath $setupDirectory)) {
        $renamed = Join-Path $Destination 'skills/gin-qa-setup'
        if (Test-Path -LiteralPath $renamed) {
            Remove-Item -LiteralPath $renamed -Recurse -Force
        }
        Move-Item -LiteralPath $setupDirectory -Destination $renamed
        $setupSkill = Join-Path $renamed 'SKILL.md'
        if (Test-Path -LiteralPath $setupSkill) {
            $content = [regex]::Replace([IO.File]::ReadAllText($setupSkill), '(?m)^name: setup$', 'name: gin-qa-setup')
            if ($null -ne (Get-Item -LiteralPath $setupSkill).LinkType) {
                Remove-Item -LiteralPath $setupSkill -Force
            }
            Write-Utf8File -Path $setupSkill -Content $content
        }
    }

    # Shell commands run from the agent's working directory, so point support
    # scripts at the absolute install location; ${PLUGIN_ROOT} does not exist here.
    if (-not [string]::IsNullOrWhiteSpace($InstallRoot)) {
        foreach ($file in Get-ChildItem -LiteralPath $Destination -Recurse -File) {
            $content = [IO.File]::ReadAllText($file.FullName)
            if (-not $content.Contains('${PLUGIN_ROOT}')) {
                continue
            }
            $content = $content.Replace('${PLUGIN_ROOT}', $InstallRoot)
            if ($null -ne $file.LinkType) {
                Remove-Item -LiteralPath $file.FullName -Force
            }
            Write-Utf8File -Path $file.FullName -Content $content
        }
    }
}

function Install-PlatformLayout {
    param(
        [Parameter(Mandatory)][ValidateSet('claude', 'antigravity', 'codex', 'opencode', 'copilot')][string]$Harness,
        [Parameter(Mandatory)][string]$PluginDirectory,
        [Parameter(Mandatory)][string]$Destination,
        [Parameter(Mandatory)][string]$HooksRoot,
        [string]$ManifestPath,
        [string]$InstallRoot
    )
    if ($Harness -eq 'opencode') {
        Install-OpenCodeBundle `
            -Source (Join-Path $PluginDirectory 'src') `
            -Destination $Destination `
            -InstallRoot $InstallRoot `
            -PluginName (Get-PluginId (Split-Path -Leaf $PluginDirectory))
        return
    }
    if ($Harness -eq 'copilot') {
        # Copilot CLI reads the Claude layout (.claude-plugin/plugin.json,
        # skills/<name>/SKILL.md); hooks get Copilot's own format and agents get
        # Copilot tool names.
        Copy-BundleDirectories -Source (Join-Path $PluginDirectory 'src') -Destination $Destination
        if (Test-Path -LiteralPath (Join-Path $PluginDirectory 'src/agents') -PathType Container) {
            Copy-DirectoryContent `
                -Source (Join-Path $PluginDirectory 'src/agents') `
                -Destination (Join-Path $Destination 'agents') `
                -AsLink:$Link
            Convert-CopilotAgents -AgentsDirectory (Join-Path $Destination 'agents')
        }
        if (Test-Path -LiteralPath (Join-Path $PluginDirectory 'src/hooks') -PathType Container) {
            New-CopilotHooksFile -OutputPath (Join-Path $Destination 'hooks/hooks.json')
        }
        New-PluginManifest -PluginDirectory $PluginDirectory -OutputPath $ManifestPath
        return
    }
    Copy-PluginSource -PluginSource (Join-Path $PluginDirectory 'src') -Destination $Destination
    if (Test-Path -LiteralPath (Join-Path $PluginDirectory 'src/hooks') -PathType Container) {
        New-HooksFile -Harness $Harness -OutputPath (Join-Path $Destination 'hooks/hooks.json') -HooksRoot $HooksRoot
    }
    if ($Harness -eq 'claude') {
        Convert-ClaudeAgents -AgentsDirectory (Join-Path $Destination 'agents')
    }
    if ($Harness -eq 'codex') {
        Convert-CodexAgents -AgentsDirectory (Join-Path $Destination 'agents')
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

function Disable-ClaudePlugin {
    param([Parameter(Mandatory)][string]$Name)
    $settingsPath = Join-Path $UserHome '.claude/settings.json'
    if (-not (Test-Path -LiteralPath $settingsPath -PathType Leaf)) {
        return
    }
    $parseError = "Error: cannot parse $settingsPath; fix it and re-run ./install.ps1"
    try {
        $settings = Get-Content -LiteralPath $settingsPath -Raw | ConvertFrom-Json -AsHashtable
    }
    catch {
        throw $parseError
    }
    if ($settings -isnot [System.Collections.IDictionary] -or ($settings.Contains('enabledPlugins') -and $settings.enabledPlugins -isnot [System.Collections.IDictionary])) {
        throw $parseError
    }
    if (-not $settings.Contains('enabledPlugins') -or -not $settings.enabledPlugins.Contains("$Name@skills-dir")) {
        return
    }
    $settings.enabledPlugins.Remove("$Name@skills-dir")
    Write-Utf8File -Path $settingsPath -Content (($settings | ConvertTo-Json -Depth 32) + "`n")
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
    $oldShape = '\A@echo off\npython "([^"\n]+)" %\*\n?\z'
    $newShape = '\A@echo off\nwhere py >nul 2>nul\nif %errorlevel%==0 \(py -3 -X utf8 "([^"\n]+)" %\*\) else \(python -X utf8 "\1" %\*\)\n?\z'
    if ($content -notmatch $oldShape -and $content -notmatch $newShape) {
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

# Remove ~/.local/bin/<name>.cmd and ~/.local/lib/<name> only when the shim is one
# this installer wrote; a foreign file of that name is kept and reported.
function Remove-ManagedLauncher {
    param([Parameter(Mandatory)][string]$Name)
    $shim = Join-Path $UserHome ".local/bin/$Name.cmd"
    $managedRoot = Join-Path $UserHome ".local/lib/$Name"
    if (Test-Path -LiteralPath $shim) {
        if (-not (Test-ManagedLauncherShim -Path $shim -ManagedRoot $managedRoot -Name $Name)) {
            Write-Warning "kept ${shim}: not a $Name launcher this installer manages"
            return
        }
        if ($DryRun) {
            Write-Output "(dry-run) would remove the $Name launcher at $shim"
            return
        }
        Remove-Item -LiteralPath $shim -Force
        Write-Output "Removed the $Name launcher at $shim"
    }
    if (-not (Test-Path -LiteralPath $managedRoot -PathType Container)) {
        return
    }
    if ($DryRun) {
        Write-Output "(dry-run) would remove $managedRoot"
        return
    }
    Remove-Item -LiteralPath $managedRoot -Recurse -Force
    Write-Output "Removed $managedRoot"
}

function Get-LauncherBin {
    return [IO.Path]::GetFullPath((Join-Path $UserHome '.local/bin')).TrimEnd('\', '/')
}

function Test-PathContains {
    param([Parameter(Mandatory)][AllowEmptyString()][string]$PathValue, [Parameter(Mandatory)][string]$Directory)
    foreach ($entry in ($PathValue -split [Regex]::Escape([IO.Path]::PathSeparator))) {
        if ([string]::IsNullOrWhiteSpace($entry)) { continue }
        try {
            if ([IO.Path]::GetFullPath([Environment]::ExpandEnvironmentVariables($entry)).TrimEnd('\', '/').Equals($Directory, [StringComparison]::OrdinalIgnoreCase)) { return $true }
        }
        catch { continue }
    }
    return $false
}

# Read/write the user Path through the registry so %VAR% references are not expanded and lost.
function Get-RawUserPath {
    $key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey('Environment', $false)
    try { return [string]$key.GetValue('Path', '', [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames) }
    finally { $key.Close() }
}

function Set-RawUserPath {
    param([Parameter(Mandatory)][AllowEmptyString()][string]$Value)
    $key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey('Environment', $true)
    try { $key.SetValue('Path', $Value, [Microsoft.Win32.RegistryValueKind]::ExpandString) }
    finally { $key.Close() }
    [GinWorkflow.NativeMethods]::SendMessageTimeout([IntPtr]0xffff, 0x1A, [UIntPtr]::Zero, 'Environment', 2, 5000, [ref]([UIntPtr]::Zero)) | Out-Null
}

function Register-UserPath {
    $launcherBin = Get-LauncherBin
    if (-not (Test-PathContains -PathValue $env:PATH -Directory $launcherBin)) {
        $env:PATH = "$launcherBin$([IO.Path]::PathSeparator)$env:PATH"
    }
    if (-not $IsWindows) {
        Write-Warning "$launcherBin is not on PATH."
        return
    }
    $userPath = Get-RawUserPath
    if (Test-PathContains -PathValue $userPath -Directory $launcherBin) { return }
    if ($NoModifyPath) {
        Write-Output "Add $launcherBin to your user PATH (install.ps1 -NoModifyPath leaves it unchanged)."
        return
    }
    if ($DryRun) {
        Write-Output "(dry-run) would add $launcherBin to the user PATH"
        return
    }
    $entries = @($userPath -split ';' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }) + $launcherBin
    Set-RawUserPath ($entries -join ';')
    Write-Output "Added $launcherBin to the user PATH; open a new terminal for other sessions to see it."
}

function Unregister-UserPath {
    if (-not $IsWindows -or $NoModifyPath) { return }
    $launcherBin = Get-LauncherBin
    $userPath = Get-RawUserPath
    $entries = @($userPath -split ';' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    $kept = @($entries | Where-Object { -not (Test-PathContains -PathValue $_ -Directory $launcherBin) })
    if ($kept.Count -eq $entries.Count) { return }
    Set-RawUserPath ($kept -join ';')
    Write-Output "Removed $launcherBin from the user PATH."
}

# Add-ons call gin; warn when it is neither installed by this installer nor on PATH.
function Write-GinMissingWarning {
    param([string]$Name)
    $workflowShim = Join-Path $UserHome '.local/bin/gin.cmd'
    if (-not (Test-Path -LiteralPath $workflowShim) -and -not (Get-Command gin -ErrorAction SilentlyContinue)) {
        Write-Warning "gin is not installed; $Name needs it (./install.ps1 -Plugin gin-workflow)."
    }
}

function Install-Launcher {
    param(
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][string]$Version
    )
    # $Name is the plugin directory; the launcher carries the plugin id.
    $launcherName = Get-PluginId $Name
    $sourceDirectory = Join-Path $ScriptRoot "plugins/$Name/src/scripts"
    $managedRoot = Join-Path $UserHome ".local/lib/$launcherName"
    $installDirectory = Join-Path $managedRoot $Version
    $launcherTarget = Join-Path $installDirectory $launcherName
    $launcherShim = Join-Path $UserHome ".local/bin/$launcherName.cmd"
    $packages = switch ($Name) {
        'gin-workflow' { @('workflow_core', 'review_ledger') }
        'gin-qa' { @('gin_qa') }
        'gin-orchestrator' { @('gin_orchestrator') }
    }

    if (Test-Path -LiteralPath $launcherShim) {
        if (-not (Test-ManagedLauncherShim -Path $launcherShim -ManagedRoot $managedRoot -Name $launcherName)) {
            throw "Error: refusing to replace a different launcher at $launcherShim"
        }
    }

    if ($Name -eq 'gin-qa') {
        Write-GinMissingWarning -Name 'gin-qa'
    }

    if ($DryRun) {
        Write-Output "(dry-run) would install $launcherName launcher version $Version to $launcherTarget"
        Write-Output "(dry-run) would install $launcherName launcher shim at $launcherShim"
        if ($Name -eq 'gin-workflow') {
            Register-UserPath
            Remove-ManagedLauncher -Name 'gin-workflow'
        }
        return
    }

    New-Directory (Split-Path -Parent $launcherShim)
    New-Directory $installDirectory
    Copy-Item -LiteralPath (Join-Path $sourceDirectory $launcherName) -Destination $launcherTarget -Force
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

    if ($Name -eq 'gin-workflow') {
        $previous = $env:PYTHONPATH
        $env:PYTHONPATH = $sourceDirectory
        try { & python -B -m workflow_core.snapshot (Join-Path $ScriptRoot 'plugins/gin-workflow/src') $installDirectory }
        finally { $env:PYTHONPATH = $previous }
        if ($LASTEXITCODE) { throw 'Error: could not write the installed snapshot stamp' }
    }

    $shimContent = "@echo off`r`nwhere py >nul 2>nul`r`nif %errorlevel%==0 (py -3 -X utf8 `"$launcherTarget`" %*) else (python -X utf8 `"$launcherTarget`" %*)`r`n"
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

    Write-Output "Installed $launcherName launcher version $Version to $launcherShim"
    if ($Name -eq 'gin-workflow') {
        Register-UserPath
        Remove-ManagedLauncher -Name 'gin-workflow'
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

# Remove the global OpenCode agents an earlier install of plugin id $Id copied, as
# its bundle lists them; a gin-*.md filter would also match gin-qa's and the user's own.
function Remove-OpenCodeAgents {
    param([Parameter(Mandatory)][string]$Id)
    $bundleAgents = Join-Path $UserHome ".config/opencode/skills/$Id/agents"
    if (-not (Test-Path -LiteralPath $bundleAgents -PathType Container)) {
        return
    }
    foreach ($agent in Get-ChildItem -LiteralPath $bundleAgents -Filter '*.md' -File) {
        $installed = Join-Path $UserHome ".config/opencode/agents/$($agent.Name)"
        if (Test-Path -LiteralPath $installed) {
            Remove-Item -LiteralPath $installed -Force
        }
    }
}

# The 2.x global install of this plugin under its old id, for each selected harness.
function Remove-LegacyPlugin {
    $old = 'gin-workflow'
    if ($DryRun) {
        Write-Output "(dry-run) would remove the old $old plugin installs"
        return
    }
    $legacyDirectories = @()
    if ((Test-Platform 'claude') -and (Get-Command claude -ErrorAction SilentlyContinue)) {
        $legacyDirectories += Join-Path $UserHome ".claude/skills/$old"
        Disable-ClaudePlugin -Name $old
    }
    if (Test-Platform 'opencode') {
        $legacyDirectories += Join-Path $UserHome ".config/opencode/skills/$old"
        $opencodeAgents = Join-Path $UserHome '.config/opencode/agents'
        if (Test-Path -LiteralPath $opencodeAgents -PathType Container) {
            Get-ChildItem -LiteralPath $opencodeAgents -Filter "$old-*.md" -File | Remove-Item -Force
        }
    }
    if ((Test-Platform 'antigravity') -and (Get-Command agy -ErrorAction SilentlyContinue)) {
        $legacyDirectories += Join-Path $UserHome ".gemini/config/plugins/$old"
    }
    foreach ($directory in $legacyDirectories) {
        if (Test-Path -LiteralPath $directory) {
            Remove-Item -LiteralPath $directory -Recurse -Force
        }
    }
    # Best effort: the old plugin may not be registered, and then the harness CLI exits non-zero.
    if ((Test-Platform 'codex') -and (Get-Command codex -ErrorAction SilentlyContinue)) {
        & codex plugin remove "$old@gin-workflow-marketplace" *> $null
    }
    if ((Test-Platform 'copilot') -and (Get-Command copilot -ErrorAction SilentlyContinue)) {
        & copilot plugin uninstall $old *> $null
    }
}

# Skill folders a 2.x project install wrote under the old names, for each selected harness.
function Remove-LegacyProjectInstall {
    $roots = [ordered]@{ claude = '.claude'; antigravity = '.agents'; codex = '.codex'; opencode = '.opencode' }
    foreach ($harness in $roots.Keys) {
        if (-not (Test-Platform $harness)) {
            continue
        }
        $root = Join-Path $Project $roots[$harness]
        $skills = @('gin-knowledge', 'gin-sdd', 'gin-team', 'gin-worktrees', 'gin-debugging', 'gin-review-response', 'gin-parallel-agents')
        if ($harness -eq 'opencode') {
            $skills += 'gin-workflow-report'
            $projectAgents = Join-Path $root 'agents'
            if (Test-Path -LiteralPath $projectAgents -PathType Container) {
                Get-ChildItem -LiteralPath $projectAgents -Filter 'gin-workflow-*.md' -File | Remove-Item -Force
            }
        }
        foreach ($skill in $skills) {
            $directory = Join-Path $root "skills/$skill"
            if (Test-Path -LiteralPath $directory) {
                Remove-Item -LiteralPath $directory -Recurse -Force
            }
        }
    }
}

function Install-Plugin {
    param([Parameter(Mandatory)][string]$Name)
    $pluginDirectory = Join-Path $ScriptRoot "plugins/$Name"
    $id = Get-PluginId $Name
    if (-not (Test-Path -LiteralPath $pluginDirectory -PathType Container)) {
        Write-Warning "Plugin directory '$pluginDirectory' not found. Skipping."
        return
    }

    Write-Output '=========================================='
    Write-Output "Processing plugin: $Name"
    Write-Output '=========================================='

    if (-not [string]::IsNullOrWhiteSpace($Project)) {
        if (Test-Platform 'copilot') {
            Write-Warning 'Copilot plugins are global; -Project skips copilot.'
        }
        if ($DryRun) {
            Write-Output "(dry-run) would install project-level configs for $Name to $Project"
            if ($Name -eq 'gin-workflow') {
                Write-Output "(dry-run) would remove the old gin-workflow skill folders from $Project"
            }
            return
        }
        if ($Name -eq 'gin-workflow') { Remove-LegacyProjectInstall }
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
        if (Test-Platform 'opencode') {
            $target = Join-Path $Project '.opencode'
            Install-PlatformLayout -Harness opencode -PluginDirectory $pluginDirectory -Destination $target -HooksRoot '${PLUGIN_ROOT}' -ManifestPath '' -InstallRoot $target
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
        $installedRoot = Join-Path $UserHome ".gemini/config/plugins/$id"
        Install-PlatformLayout -Harness antigravity -PluginDirectory $pluginDirectory -Destination $target -HooksRoot $installedRoot -ManifestPath (Join-Path $target 'plugin.json')
    }
    if (Test-Platform 'codex') {
        $target = Join-Path $distDirectory 'codex'
        if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Recurse -Force }
        Install-PlatformLayout -Harness codex -PluginDirectory $pluginDirectory -Destination $target -HooksRoot '${PLUGIN_ROOT}' -ManifestPath (Join-Path $target '.codex-plugin/plugin.json')
    }
    if (Test-Platform 'opencode') {
        $target = Join-Path $distDirectory 'opencode'
        if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Recurse -Force }
        Write-Output "Configuring OpenCode skill structure for $Name..."
        Install-PlatformLayout -Harness opencode -PluginDirectory $pluginDirectory -Destination $target -HooksRoot '${PLUGIN_ROOT}' -ManifestPath '' -InstallRoot (Join-Path $UserHome ".config/opencode/skills/$id")
    }
    if (Test-Platform 'copilot') {
        $target = Join-Path $distDirectory 'copilot'
        if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Recurse -Force }
        Write-Output "Configuring Copilot plugin structure for $Name..."
        # Copilot names a direct install after the source directory, so the
        # bundle directory carries the plugin id to keep plugins apart.
        $bundle = Join-Path $target $id
        Install-PlatformLayout -Harness copilot -PluginDirectory $pluginDirectory -Destination $bundle -HooksRoot '${PLUGIN_ROOT}' -ManifestPath (Join-Path $bundle '.claude-plugin/plugin.json')
    }

    if ($Name -eq 'gin-workflow') { Remove-LegacyPlugin }

    if ($DryRun) {
        Write-Output "(dry-run) registration skipped for $Name"
        if (Test-Platform 'claude') {
            Write-Output "(dry-run) would install global Claude Code plugin to $(Join-Path $UserHome ".claude/skills/$id")"
        }
        if (Test-Platform 'opencode') {
            Write-Output "(dry-run) would install global OpenCode skills to $(Join-Path $UserHome ".config/opencode/skills/$id")"
        }
        if (Test-Platform 'copilot') {
            Write-Output "(dry-run) would install Copilot plugin from $(Join-Path $distDirectory "copilot/$id")"
        }
        return
    }

    if ((Test-Platform 'claude') -and (Get-Command claude -ErrorAction SilentlyContinue)) {
        $source = Join-Path $distDirectory 'claude-code'
        $destination = Join-Path $UserHome ".claude/skills/$id"
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
        Enable-ClaudePlugin -Name $id
        Write-Output "Successfully installed and enabled $id globally in Claude Code!"
    }
    if (Test-Platform 'opencode') {
        $source = Join-Path $distDirectory 'opencode'
        $destination = Join-Path $UserHome ".config/opencode/skills/$id"
        Remove-OpenCodeAgents -Id $id
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
        $sourceAgents = Join-Path $source 'agents'
        if (Test-Path -LiteralPath $sourceAgents -PathType Container) {
            $destAgents = Join-Path $UserHome '.config/opencode/agents'
            New-Directory $destAgents
            foreach ($agent in Get-ChildItem -LiteralPath $sourceAgents -Filter "$id-*.md" -File) {
                Copy-Item -LiteralPath $agent.FullName -Destination (Join-Path $destAgents $agent.Name) -Force
            }
        }
        Write-Output "Successfully installed $id globally in OpenCode!"
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
            -CommandArguments @('plugin', 'add', "$id@gin-workflow-marketplace")
    }
    if (Test-Platform 'copilot') {
        $copilotBundle = Join-Path $distDirectory "copilot/$id"
        if (Get-Command copilot -ErrorAction SilentlyContinue) {
            Write-Output "Registering $id with Copilot..."
            # Remove first so a re-run replaces the installed copy.
            & copilot plugin uninstall $id *> $null
            Invoke-NativeCommand -Executable 'copilot' -CommandArguments @('plugin', 'install', $copilotBundle)
        }
        else {
            Write-Output "Copilot CLI not found; skipped registration. Run: copilot plugin install $copilotBundle"
        }
    }
}

if (-not [string]::IsNullOrWhiteSpace($Project)) {
    if (-not (Test-Path -LiteralPath $Project -PathType Container)) {
        throw "Error: --project directory '$Project' does not exist"
    }
    $Project = [IO.Path]::GetFullPath((Resolve-Path -LiteralPath $Project).Path)
}

$Plugins = switch ($Plugin) {
    'all' { @('gin-workflow', 'gin-qa', 'gin-orchestrator', 'gin-ba') }
    default { @($Plugin) }
}

if ($Uninstall) {
    $ids = @($Plugins | ForEach-Object { Get-PluginId $_ })
    if ($Plugins -contains 'gin-workflow') { $ids += 'gin-workflow' }
    $opencodeAgents = Join-Path $UserHome '.config/opencode/agents'
    foreach ($id in $ids) {
        if ($id -eq 'gin-workflow') {
            if (Test-Path -LiteralPath $opencodeAgents -PathType Container) {
                Get-ChildItem -LiteralPath $opencodeAgents -Filter 'gin-workflow-*.md' -File | Remove-Item -Force
            }
        }
        else {
            Remove-OpenCodeAgents -Id $id
        }
        $opencodeSkills = Join-Path $UserHome ".config/opencode/skills/$id"
        if (Test-Path -LiteralPath $opencodeSkills) {
            Remove-Item -LiteralPath $opencodeSkills -Recurse -Force
        }
    }
    # After the OpenCode agents: a -Link install lists them through dist.
    foreach ($directory in @(
        (Join-Path $ScriptRoot 'plugins/gin-workflow/dist'),
        (Join-Path $ScriptRoot 'plugins/gin-workflow-advanced/dist'),
        (Join-Path $ScriptRoot 'plugins/gin-qa/dist'),
        (Join-Path $ScriptRoot 'plugins/gin-orchestrator/dist'),
        (Join-Path $ScriptRoot 'plugins/gin-ba/dist')
    )) {
        if (Test-Path -LiteralPath $directory) {
            Remove-Item -LiteralPath $directory -Recurse -Force
        }
    }
    if (Get-Command copilot -ErrorAction SilentlyContinue) {
        foreach ($id in $ids) {
            # Best effort: a plugin that is not registered makes the CLI exit non-zero.
            & copilot plugin uninstall $id *> $null
        }
    }
    if ($Plugins -contains 'gin-workflow') {
        Remove-ManagedLauncher -Name 'gin'
        Remove-ManagedLauncher -Name 'gin-workflow'
    }
    Unregister-UserPath
    Write-Output 'Removed generated dist output, the gin launcher, the global OpenCode skill install, and the Copilot plugin registration, under the gin and the old gin-workflow name. Project installs and the Claude Code, Codex, and Antigravity registrations are left for manual removal.'
    return
}

if ($Plugins -contains 'gin-orchestrator' -and $Plugins -notcontains 'gin-workflow') {
    $workflowShim = Join-Path $UserHome '.local/bin/gin.cmd'
    $workflowTarget = Join-Path (Join-Path (Join-Path $UserHome '.local/lib/gin') $LauncherVersion) 'gin'
    if (-not (Test-Path -LiteralPath $workflowShim -PathType Leaf) -or
        -not [IO.File]::ReadAllText($workflowShim).Contains("`"$workflowTarget`"", [StringComparison]::Ordinal)) {
        Write-Output "gin-orchestrator requires gin $LauncherVersion; installing it first."
        $Plugins = @('gin-workflow') + $Plugins
    }
}

# An installed add-on runs its own library copy, which calls gin; installing gin
# refreshes each add-on whose launcher this installer manages. A project install
# writes only the requested plugins: the add-ons would land in the same
# .opencode/skills, where gin-qa's `setup` replaces gin's.
if (($Plugins -contains 'gin-workflow') -and [string]::IsNullOrWhiteSpace($Project)) {
    foreach ($addon in @('gin-qa', 'gin-orchestrator')) {
        $addonShim = Join-Path $UserHome ".local/bin/$addon.cmd"
        $addonRoot = Join-Path $UserHome ".local/lib/$addon"
        if ($Plugins -notcontains $addon -and (Test-ManagedLauncherShim -Path $addonShim -ManagedRoot $addonRoot -Name $addon)) {
            Write-Output "Refreshing the installed $addon add-on."
            $Plugins = @($Plugins) + $addon
        }
    }
}

foreach ($name in $Plugins) {
    if ($name -eq 'gin-ba') {
        Write-GinMissingWarning -Name 'gin-ba'
    } else {
        $version = switch ($name) {
            'gin-workflow' { $LauncherVersion }
            'gin-qa' { $QaLauncherVersion }
            'gin-orchestrator' { $OrchLauncherVersion }
        }
        Install-Launcher -Name $name -Version $version
    }
    Install-Plugin -Name $name
}
Write-Output 'Install processes completed successfully!'
