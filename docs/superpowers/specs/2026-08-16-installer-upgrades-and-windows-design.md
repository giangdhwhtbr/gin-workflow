# Installer Upgrades and Windows Support Design

## Goal

Allow an existing gin-workflow launcher installed by an older release to upgrade safely, and provide a native Windows installer for PowerShell 7. Foreign launchers must continue to fail closed and remain untouched.

## Scope

This change covers the repository-local installers, launcher installation, automated installer smoke tests, and user-facing installation documentation. It does not change workflow configuration schemas, lifecycle routing, plugin contents, or remote installation behavior.

## Unix Launcher Upgrade

`install.sh` will recognize a launcher as managed only when it is a symbolic link whose target has the exact shape:

```text
$HOME/.local/lib/gin-workflow/<version>/gin-workflow
```

The version segment must be one path component and the target must remain inside the managed launcher root. A managed link may be replaced with a link to the current version. A regular file, a link outside the managed root, or a malformed managed-looking path remains a collision and causes installation to stop without modifying the launcher.

The installer will copy the current launcher first and then update the managed link. Older version directories remain available; the installer does not delete them automatically.

## PowerShell 7 Installer

Add `install.ps1` as a native PowerShell 7 implementation of the supported `install.sh` contract. It will expose PowerShell-style parameters equivalent to the shell installer:

- `-Platform claude|antigravity|codex|both|all`
- `-Plugin gin-workflow|all`
- `-Link`
- `-Project <path>`
- `-Uninstall`
- `-DryRun`

It will generate the same Claude Code, Antigravity, and Codex plugin layouts and manifests. Global registration will use the corresponding native CLI when present. Project installation will populate `.claude`, `.agents`, and `.codex` beneath the selected repository, matching the shell installer.

The Windows launcher payload will be installed below:

```text
$HOME/.local/lib/gin-workflow/<version>/
```

The command shim will be `$HOME/.local/bin/gin-workflow.cmd` and will invoke the versioned Python entry point. The installer will warn when `$HOME/.local/bin` is not on `PATH`; it will not silently mutate the user's persistent environment.

PowerShell launcher upgrades use the same ownership principle as Unix: an existing shim may be replaced only when its normalized contents identify a versioned entry point under the managed gin-workflow launcher root. Unrelated `.cmd` files remain untouched and cause a clear collision error.

`-Link` will use PowerShell symbolic links for plugin development layouts. If Windows policy does not permit symlink creation, the operation will fail with the native error and a concise recommendation to enable Developer Mode or run with suitable privileges.

## Error Handling and Safety

Both installers validate platform, plugin, and project inputs before writing. Dry-run output describes launcher and plugin writes without installing or registering anything. Collision checks run before launcher mutation. Commands that fail propagate a non-zero exit status rather than being suppressed.

Uninstall behavior remains limited to generated repository `dist` directories; it does not remove user configuration, installed launcher versions, or unrelated files.

## Testing

Extend `tests/install_smoke_test.sh` with:

- upgrade from a simulated older managed launcher link;
- confirmation that the link points at the current launcher afterward;
- rejection and preservation of a foreign symbolic link in addition to the existing foreign-file test.

Add `tests/install_smoke_test.ps1` with native temporary-directory coverage for:

- dry-run output and generated layouts;
- actual launcher and plugin installation;
- upgrade from an older managed shim;
- rejection and preservation of a foreign shim;
- project-level installation.

The PowerShell suite will be runnable with `pwsh -NoProfile -File tests/install_smoke_test.ps1`. Environments without PowerShell 7 cannot execute that suite; this limitation must be stated in the verification handoff rather than treated as a passing result.

## Documentation

Update `README.md` to list PowerShell 7 as the Windows prerequisite, show local Windows installation commands, document PowerShell parameter names, and include `install.ps1` in the repository structure.

## Acceptance Criteria

1. A launcher link created by an older Unix installer upgrades to the current version.
2. Foreign Unix launcher files and links fail closed without modification.
3. PowerShell 7 can build and install all supported plugin layouts on Windows.
4. The Windows launcher command invokes the installed current-version CLI.
5. Foreign Windows shims fail closed without modification.
6. Unix and PowerShell smoke suites encode the new behavior.
7. README instructions cover native Windows installation.
