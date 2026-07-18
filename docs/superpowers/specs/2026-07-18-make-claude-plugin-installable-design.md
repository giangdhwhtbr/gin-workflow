# Design Specification: Make Claude Code Plugin Installable Globally

**Date**: 2026-07-18  
**Author**: Antigravity  
**Topic**: Claude Code Plugin Global Installation  

---

## 1. Goal

Make the `gin-workflow` plugin globally installable for Claude Code. Currently, `install.sh` builds the plugin into a local `dist/` folder and instructs the user to run Claude Code with `--plugin-dir` pointing to that folder every time. We will update `install.sh` to install the plugin directly to the user's global skills directory (`~/.claude/skills/gin-workflow`) and programmatically enable it.

---

## 2. Target Directory & Autoloading

Claude Code automatically discovers and autoloads plugins placed in `~/.claude/skills/` if they contain a `.claude-plugin/plugin.json` manifest.
- **Global Path**: `~/.claude/skills/gin-workflow`
- **Subagents Path**: `~/.claude/skills/gin-workflow/agents/`
- **Skills Path**: `~/.claude/skills/gin-workflow/skills/`

When the user runs `./install.sh` (or `./install.sh --link` to symlink files for active development), the script will install directly into the global path.

---

## 3. Toggle Plugin Active in Settings

Claude Code manages plugin states in `~/.claude/settings.json`. If a plugin is listed as `false` under `"enabledPlugins"`, it is disabled. We will add Python-based automation inside `install.sh` to ensure `"gin-workflow@skills-dir": true` is set.

### Settings Modification Script
```bash
enable_claude_plugin() {
  local p_name="$1"
  local settings_path="${HOME}/.claude/settings.json"
  echo "Ensuring plugin $p_name is enabled in Claude Code settings..."
  python3 - "$settings_path" "${p_name}@skills-dir" <<'PYEOF'
import json, os, sys
settings_path, plugin_key = sys.argv[1], sys.argv[2]
data = {}
if os.path.exists(settings_path):
    try:
        with open(settings_path, 'r') as f:
            data = json.load(f)
    except Exception:
        pass

if 'enabledPlugins' not in data:
    data['enabledPlugins'] = {}

data['enabledPlugins'][plugin_key] = True

os.makedirs(os.path.dirname(settings_path), exist_ok=True)
with open(settings_path, 'w') as f:
    json.dump(data, f, indent=2)
PYEOF
}
```

---

## 4. Modified Logic in `install.sh`

1. **Global Installation for Claude**:
   ```bash
   if matches_platform "claude"; then
     echo "Configuring Claude Code plugin structure for $p_name..."
     local claude_install_dir="${HOME}/.claude/skills/${p_name}"
     if [ "$DRY_RUN" = true ]; then
       echo "(dry-run) would install global Claude Code plugin to $claude_install_dir"
     else
       echo "Installing $p_name globally to Claude Code skills directory: $claude_install_dir"
       rm -rf "$claude_install_dir"
       mkdir -p "$claude_install_dir/.claude-plugin"
       install_platform "claude" "$p_name" "$claude_install_dir" "\${CLAUDE_PLUGIN_ROOT}" "$claude_install_dir/.claude-plugin/plugin.json" "false"
       enable_claude_plugin "$p_name"
     fi
   fi
   ```

2. **Success Messages**:
   Modify success block to print:
   ```bash
   if matches_platform "claude" && [ "$HAS_CLAUDE" = true ]; then
     echo "Successfully installed and enabled $p_name globally in Claude Code!"
     echo "It will automatically load the next time you run: claude"
   fi
   ```

---

## 5. Verification Plan

1. **Dry-run verification**: Run `./install.sh --dry-run` and verify it reports the correct global installation target path.
2. **Actual installation**: Run `./install.sh`. Verify that:
   - The directory `~/.claude/skills/gin-workflow` is created and populated with `skills`, `commands`, `agents`, `hooks`, etc.
   - `~/.claude/settings.json` has `"gin-workflow@skills-dir": true` set.
3. **Subagent tool verification**: Verify that the templating of agents has replaced tool names (e.g., `view_file` changed to `Read`).
