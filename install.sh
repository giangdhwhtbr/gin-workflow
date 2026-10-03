#!/bin/bash
# install.sh - Installs gin-workflow to Claude Code, Antigravity, and Codex CLI.

set -euo pipefail

PLATFORM="all"
LINK=false
PROJECT_DIR=""
UNINSTALL=false
DRY_RUN=false
TARGET_PLUGIN="gin-workflow"
LAUNCHER_VERSION="2.7"
QA_LAUNCHER_VERSION="0.1"

while [[ "$#" -gt 0 ]]; do
  case $1 in
    --platform)
      if [ -z "${2:-}" ]; then
        echo "Error: --platform requires a value" >&2
        exit 1
      fi
      PLATFORM="$2"
      shift 2
      ;;
    --plugin)
      if [ -z "${2:-}" ]; then
        echo "Error: --plugin requires a value (gin-workflow|gin-qa|all)" >&2
        exit 1
      fi
      TARGET_PLUGIN="$2"
      shift 2
      ;;
    --link)
      LINK=true
      shift
      ;;
    --project)
      if [ -z "${2:-}" ]; then
        echo "Error: --project requires a value" >&2
        exit 1
      fi
      PROJECT_DIR="$2"
      shift 2
      ;;
    --uninstall)
      UNINSTALL=true
      shift
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    *)
      echo "Unknown parameter passed: $1" >&2
      exit 1
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

case "$TARGET_PLUGIN" in
  gin-workflow)
    PLUGINS=(gin-workflow)
    ;;
  gin-qa)
    PLUGINS=(gin-qa)
    ;;
  all)
    PLUGINS=(gin-workflow gin-qa)
    ;;
  core|advanced)
    echo "Warning: --plugin $TARGET_PLUGIN is deprecated; using gin-workflow." >&2
    PLUGINS=(gin-workflow)
    ;;
  *)
    echo "Error: --plugin must be 'gin-workflow', 'gin-qa', or 'all' (got '$TARGET_PLUGIN')" >&2
    exit 1
    ;;
esac

if [ -n "$PROJECT_DIR" ]; then
  if [ ! -d "$PROJECT_DIR" ]; then
    echo "Error: --project directory '$PROJECT_DIR' does not exist" >&2
    exit 1
  fi
  PROJECT_DIR="$(cd "$PROJECT_DIR" && pwd)"
fi

if [ "$UNINSTALL" = true ]; then
  echo "Uninstalling plugins..."
  rm -rf plugins/gin-workflow/dist plugins/gin-workflow-advanced/dist plugins/gin-qa/dist
  echo "Cleaned built dist folders. Perform CLI manual uninstall/disable if registered globally."
  exit 0
fi

HAS_CLAUDE=false
HAS_AGY=false
HAS_CODEX=false
if command -v claude &> /dev/null; then
  HAS_CLAUDE=true
fi
if command -v agy &> /dev/null; then
  HAS_AGY=true
fi
if command -v codex &> /dev/null; then
  HAS_CODEX=true
fi

matches_platform() {
  local target="$1"
  [ "$PLATFORM" = "$target" ] || [ "$PLATFORM" = "both" ] || [ "$PLATFORM" = "all" ]
}

generate_manifest() {
  local p_dir="$1"
  local output_path="$2"
  local include_schema="$3"
  python3 - "$p_dir" "$output_path" "$include_schema" <<'PYEOF'
import json, sys
p_dir, out_path, inc_schema = sys.argv[1], sys.argv[2], sys.argv[3]
meta = json.load(open(p_dir + '/plugin.meta.json'))
manifest = dict(name=meta['name'], version=meta['version'],
                description=meta['description'], author=meta['author'],
                repository=meta['repository'])
if inc_schema == 'true':
    # Verified on 2026-07-09: this endpoint resolves and returns the
    # Antigravity plugin manifest JSON schema.
    manifest['$schema'] = 'https://antigravity.google/schemas/v1/plugin.json'
with open(out_path, 'w') as f:
    json.dump(manifest, f, indent=2)
PYEOF
}

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

template_agents_for_claude() {
  local src="$1"
  local dest="$2"
  sed -e 's/"view_file"/"Read"/g'               -e 's/"grep_search"/"Grep"/g'               -e 's/"list_dir"/"Glob"/g'               -e 's/"search_web"/"WebSearch"/g'               -e 's/"run_command"/"Bash"/g'               "$src" > "$dest"
}

template_hooks_for_claude() {
  local dest="$1"
  local root_var="$2"
  cat <<EOF > "$dest"
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "${root_var}/scripts/safety-check.sh",
            "timeout": 30
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "${root_var}/scripts/post-edit.sh"
          }
        ]
      }
    ]
  }
}
EOF
}

template_hooks_for_antigravity() {
  local dest="$1"
  local default_root="$2"
  cat <<EOF > "$dest"
{
  "PreToolUse": {
    "matcher": "Bash|run_command",
    "type": "command",
    "command": "\${PLUGIN_ROOT:-${default_root}}/scripts/safety-check.sh",
    "timeout": 30
  },
  "PostToolUse": {
    "matcher": "write_to_file|replace_file_content",
    "type": "command",
    "command": "\${PLUGIN_ROOT:-${default_root}}/scripts/post-edit.sh"
  }
}
EOF
}

template_hooks_for_codex() {
  local dest="$1"
  local root_var="$2"
  cat <<EOF > "$dest"
{
  "description": "Gin workflow safety and post-edit hooks for Codex.",
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash|run_command",
        "hooks": [
          {
            "type": "command",
            "command": "${root_var}/scripts/safety-check.sh",
            "timeout": 30
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "write_to_file|replace_file_content",
        "hooks": [
          {
            "type": "command",
            "command": "${root_var}/scripts/post-edit.sh"
          }
        ]
      }
    ]
  }
}
EOF
}

copy_src() {
  local plugin_src_dir="$1"
  local target="$2"

  mkdir -p "$target/commands" "$target/skills" "$target/agents" "$target/scripts" "$target/references" "$target/examples" "$target/rules" "$target/templates"

  if [ -d "$plugin_src_dir/commands" ] && [ "$(ls -A "$plugin_src_dir/commands" 2>/dev/null)" ]; then
    if [ "$LINK" = true ]; then
      cp -rsf "$plugin_src_dir/commands/." "$target/commands/"
    else
      cp -rf "$plugin_src_dir/commands/." "$target/commands/"
    fi
  fi

  if [ -d "$plugin_src_dir/skills" ] && [ "$(ls -A "$plugin_src_dir/skills" 2>/dev/null)" ]; then
    if [ "$LINK" = true ]; then
      cp -rsf "$plugin_src_dir/skills/." "$target/skills/"
    else
      cp -rf "$plugin_src_dir/skills/." "$target/skills/"
    fi
  fi

  if [ -d "$plugin_src_dir/agents" ] && [ "$(ls -A "$plugin_src_dir/agents" 2>/dev/null)" ]; then
    if [ "$LINK" = true ]; then
      cp -rsf "$plugin_src_dir/agents/." "$target/agents/"
    else
      cp -rf "$plugin_src_dir/agents/." "$target/agents/"
    fi
  fi

  if [ -d "$plugin_src_dir/scripts" ] && [ "$(ls -A "$plugin_src_dir/scripts" 2>/dev/null)" ]; then
    if [ "$LINK" = true ]; then
      cp -rsf "$plugin_src_dir/scripts/." "$target/scripts/"
    else
      cp -rf "$plugin_src_dir/scripts/." "$target/scripts/"
    fi
  fi

  if [ -d "$plugin_src_dir/references" ] && [ "$(ls -A "$plugin_src_dir/references" 2>/dev/null)" ]; then
    if [ "$LINK" = true ]; then
      cp -rsf "$plugin_src_dir/references/." "$target/references/"
    else
      cp -rf "$plugin_src_dir/references/." "$target/references/"
    fi
  fi

  if [ -d "$plugin_src_dir/examples" ] && [ "$(ls -A "$plugin_src_dir/examples" 2>/dev/null)" ]; then
    if [ "$LINK" = true ]; then
      cp -rsf "$plugin_src_dir/examples/." "$target/examples/"
    else
      cp -rf "$plugin_src_dir/examples/." "$target/examples/"
    fi
  fi

  if [ -d "$plugin_src_dir/rules" ] && [ "$(ls -A "$plugin_src_dir/rules" 2>/dev/null)" ]; then
    if [ "$LINK" = true ]; then
      cp -rsf "$plugin_src_dir/rules/." "$target/rules/"
    else
      cp -rf "$plugin_src_dir/rules/." "$target/rules/"
    fi
  fi

  if [ -d "$plugin_src_dir/templates" ] && [ "$(ls -A "$plugin_src_dir/templates" 2>/dev/null)" ]; then
    if [ "$LINK" = true ]; then
      cp -rsf "$plugin_src_dir/templates/." "$target/templates/"
    else
      cp -rf "$plugin_src_dir/templates/." "$target/templates/"
    fi
  fi
}

install_platform() {
  local platform="$1"
  local p_name="$2"
  local target_dir="$3"
  local hooks_root="$4"
  local manifest_path="$5"
  local include_schema="$6"

  copy_src "$SCRIPT_DIR/plugins/$p_name/src" "$target_dir"
  if [ -d "$SCRIPT_DIR/plugins/$p_name/src/hooks" ]; then
    mkdir -p "$target_dir/hooks"
    case "$platform" in
      claude)    template_hooks_for_claude "$target_dir/hooks/hooks.json" "$hooks_root" ;;
      antigravity) template_hooks_for_antigravity "$target_dir/hooks/hooks.json" "$hooks_root" ;;
      codex)     template_hooks_for_codex "$target_dir/hooks/hooks.json" "$hooks_root" ;;
    esac
  fi
  if [ "$platform" = "claude" ]; then
    for f in "$target_dir/agents"/*.md; do
      [ -e "$f" ] || continue
      local tmp_file
      tmp_file=$(mktemp)
      template_agents_for_claude "$f" "$tmp_file"
      mv "$tmp_file" "$f"
    done
  fi
  if [ -n "$manifest_path" ]; then
    generate_manifest "plugins/$p_name" "$manifest_path" "$include_schema"
  fi
}

is_managed_launcher_link() {
  local launcher_link="$1"
  local managed_root="$2"
  local name="${3:-gin-workflow}"
  local target version

  [ -L "$launcher_link" ] || return 1
  target="$(readlink "$launcher_link")"
  case "$target" in
    "$managed_root"/*/"$name") ;;
    *) return 1 ;;
  esac

  version="${target#"$managed_root"/}"
  version="${version%/"$name"}"
  [ -n "$version" ] &&
    [ "$version" != "." ] &&
    [ "$version" != ".." ] &&
    [ "${version#*/}" = "$version" ]
}

install_launcher() {
  local source_dir="$SCRIPT_DIR/plugins/gin-workflow/src/scripts"
  local install_dir="${HOME}/.local/lib/gin-workflow/${LAUNCHER_VERSION}"
  local launcher_target="${install_dir}/gin-workflow"
  local launcher_link="${HOME}/.local/bin/gin-workflow"
  local managed_root="${HOME}/.local/lib/gin-workflow"

  if [ -e "$launcher_link" ] || [ -L "$launcher_link" ]; then
    if [ ! -L "$launcher_link" ] || { [ "$(readlink "$launcher_link")" != "$launcher_target" ] && ! is_managed_launcher_link "$launcher_link" "$managed_root"; }; then
      echo "Error: refusing to replace a different launcher at $launcher_link" >&2
      return 1
    fi
  fi

  if [ "$DRY_RUN" = true ]; then
    echo "(dry-run) would install gin-workflow launcher version $LAUNCHER_VERSION to $launcher_target"
    echo "(dry-run) would link gin-workflow launcher on PATH at $launcher_link"
    return
  fi

  mkdir -p "$install_dir/workflow_core" "$install_dir/rules" "$install_dir/templates" "$(dirname "$launcher_link")"
  cp -f "$source_dir/gin-workflow" "$launcher_target"
  cp -rf "$source_dir/workflow_core/." "$install_dir/workflow_core/"
  cp -rf "$source_dir/../rules/." "$install_dir/rules/"
  cp -rf "$source_dir/../templates/." "$install_dir/templates/"
  chmod 755 "$launcher_target"
  ln -sfn "$launcher_target" "$launcher_link"
  echo "Installed gin-workflow launcher version $LAUNCHER_VERSION to $launcher_link"
  case ":${PATH}:" in
    *":${HOME}/.local/bin:"*) ;;
    *) echo "Warning: ${HOME}/.local/bin is not on PATH." >&2 ;;
  esac
}

install_qa_launcher() {
  local source_dir="$SCRIPT_DIR/plugins/gin-qa/src/scripts"
  local install_dir="${HOME}/.local/lib/gin-qa/${QA_LAUNCHER_VERSION}"
  local launcher_target="${install_dir}/gin-qa"
  local launcher_link="${HOME}/.local/bin/gin-qa"
  local managed_root="${HOME}/.local/lib/gin-qa"

  if [ -e "$launcher_link" ] || [ -L "$launcher_link" ]; then
    if [ ! -L "$launcher_link" ] || { [ "$(readlink "$launcher_link")" != "$launcher_target" ] && ! is_managed_launcher_link "$launcher_link" "$managed_root" gin-qa; }; then
      echo "Error: refusing to replace a different launcher at $launcher_link" >&2
      return 1
    fi
  fi
  if [ ! -e "${HOME}/.local/bin/gin-workflow" ] && ! command -v gin-workflow &> /dev/null; then
    echo "Warning: gin-workflow is not installed; gin-qa needs it (./install.sh --plugin gin-workflow)." >&2
  fi

  if [ "$DRY_RUN" = true ]; then
    echo "(dry-run) would install gin-qa launcher version $QA_LAUNCHER_VERSION to $launcher_target"
    echo "(dry-run) would link gin-qa launcher on PATH at $launcher_link"
    return
  fi

  mkdir -p "$install_dir/gin_qa" "$(dirname "$launcher_link")"
  cp -f "$source_dir/gin-qa" "$launcher_target"
  cp -rf "$source_dir/gin_qa/." "$install_dir/gin_qa/"
  chmod 755 "$launcher_target"
  ln -sfn "$launcher_target" "$launcher_link"
  echo "Installed gin-qa launcher version $QA_LAUNCHER_VERSION to $launcher_link"
}

CODEX_MARKETPLACE_READY=false

install_plugin() {
  local p_name="$1"
  local p_dir="plugins/$p_name"

  if [ ! -d "$p_dir" ]; then
    echo "Warning: Plugin directory $p_dir not found. Skipping."
    return
  fi

  echo "=========================================="
  echo "Processing plugin: $p_name"
  echo "=========================================="

  if [ -n "$PROJECT_DIR" ]; then
    if [ "$DRY_RUN" = true ]; then
      echo "(dry-run) would install project-level configs for $p_name to $PROJECT_DIR"
      return
    fi

    echo "Installing $p_name locally to project: $PROJECT_DIR"
    if matches_platform "claude"; then
      install_platform "claude" "$p_name" "$PROJECT_DIR/.claude" "\${CLAUDE_PROJECT_DIR}/.claude" "" ""
    fi
    if matches_platform "antigravity"; then
      install_platform "antigravity" "$p_name" "$PROJECT_DIR/.agents" "$PROJECT_DIR/.agents" "" ""
    fi
    if matches_platform "codex"; then
      install_platform "codex" "$p_name" "$PROJECT_DIR/.codex" "\${PLUGIN_ROOT}" "" ""
    fi
    return
  fi

  local dist_dir="$p_dir/dist"
  # dist/ is fully generated: rebuild each selected platform from scratch so files
  # removed from src (commands, skills) never linger and shadow same-name skills.
  if matches_platform "claude"; then rm -rf "${dist_dir:?}/claude-code"; fi
  if matches_platform "antigravity"; then rm -rf "${dist_dir:?}/antigravity"; fi
  if matches_platform "codex"; then rm -rf "${dist_dir:?}/codex"; fi
  mkdir -p "$dist_dir/claude-code/.claude-plugin"
  mkdir -p "$dist_dir/antigravity"
  mkdir -p "$dist_dir/codex/.codex-plugin"

  if matches_platform "claude"; then
    echo "Configuring Claude Code plugin structure for $p_name..."
    install_platform "claude" "$p_name" "$dist_dir/claude-code" "\${CLAUDE_PLUGIN_ROOT}" "$dist_dir/claude-code/.claude-plugin/plugin.json" "false"
  fi
  if matches_platform "antigravity"; then
    echo "Configuring Antigravity plugin structure for $p_name..."
    local agy_install_path
    agy_install_path="${HOME}/.gemini/config/plugins/${p_name}"
    install_platform "antigravity" "$p_name" "$dist_dir/antigravity" "$agy_install_path" "$dist_dir/antigravity/plugin.json" "true"
  fi
  if matches_platform "codex"; then
    echo "Configuring Codex plugin structure for $p_name..."
    install_platform "codex" "$p_name" "$dist_dir/codex" "\${PLUGIN_ROOT}" "$dist_dir/codex/.codex-plugin/plugin.json" "false"
  fi

  if [ "$DRY_RUN" = true ]; then
    echo "(dry-run) registration skipped for $p_name"
    if matches_platform "claude"; then
      local claude_install_dir="${HOME}/.claude/skills/${p_name}"
      echo "(dry-run) would install global Claude Code plugin to $claude_install_dir"
    fi
    return
  fi

  if matches_platform "claude" && [ "$HAS_CLAUDE" = true ]; then
    local claude_install_dir="${HOME}/.claude/skills/${p_name}"
    echo "Installing $p_name globally to Claude Code skills directory: $claude_install_dir"
    rm -rf "$claude_install_dir"
    mkdir -p "$(dirname "$claude_install_dir")"
    if [ "$LINK" = true ]; then
      ln -sf "$SCRIPT_DIR/$dist_dir/claude-code" "$claude_install_dir"
    else
      cp -rf "$dist_dir/claude-code" "$claude_install_dir"
    fi
    enable_claude_plugin "$p_name"
    echo "Successfully installed and enabled $p_name globally in Claude Code!"
  fi
  if matches_platform "antigravity" && [ "$HAS_AGY" = true ]; then
    echo "Registering $p_name with Antigravity..."
    agy plugin install "$SCRIPT_DIR/$dist_dir/antigravity"
  fi
  if matches_platform "codex" && [ "$HAS_CODEX" = true ]; then
    echo "Registering $p_name with Codex..."
    # codex plugin marketplace add/plugin add are no-ops when already
    # registered by name, and the git-subdir source snapshots content at
    # add-time -- so a repeat run would keep serving a stale snapshot even
    # after local changes are committed. Force a fresh registration.
    # With --plugin all, refresh the marketplace once so the second plugin does not drop the first.
    codex plugin remove "$p_name@gin-workflow-marketplace" >/dev/null 2>&1 || true
    if [ "$CODEX_MARKETPLACE_READY" = false ]; then
      codex plugin marketplace remove "gin-workflow-marketplace" >/dev/null 2>&1 || true
      codex plugin marketplace add "$SCRIPT_DIR"
      CODEX_MARKETPLACE_READY=true
    fi
    codex plugin add "$p_name@gin-workflow-marketplace"
  fi
}

for p_name in "${PLUGINS[@]}"; do
  case "$p_name" in
    gin-workflow) install_launcher ;;
    gin-qa) install_qa_launcher ;;
  esac
  install_plugin "$p_name"
done

echo "Install processes completed successfully!"
