#!/bin/bash
# install.sh - Installs gin-workflow core/advanced to Claude Code, Antigravity, and Codex CLI.

set -euo pipefail

PLATFORM="all"
LINK=false
PROJECT_DIR=""
UNINSTALL=false
DRY_RUN=false
TARGET_PLUGIN="all"  # core, advanced, all

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
        echo "Error: --plugin requires a value (core|advanced|all)" >&2
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

# Validate TARGET_PLUGIN
case "$TARGET_PLUGIN" in
  core|advanced|all) ;;
  *)
    echo "Error: --plugin must be 'core', 'advanced', or 'all' (got '$TARGET_PLUGIN')" >&2
    exit 1
    ;;
esac

# Validate and normalize PROJECT_DIR
if [ -n "$PROJECT_DIR" ]; then
  if [ ! -d "$PROJECT_DIR" ]; then
    echo "Error: --project directory '$PROJECT_DIR' does not exist" >&2
    exit 1
  fi
  PROJECT_DIR="$(cd "$PROJECT_DIR" && pwd)"
fi

if [ "$UNINSTALL" = true ]; then
  echo "Uninstalling plugins..."
  rm -rf plugins/gin-workflow/dist plugins/gin-workflow-advanced/dist
  echo "Cleaned built dist folders. Perform CLI manual uninstall/disable if registered globally."
  exit 0
fi

# Detect platforms
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

# Helper: check if PLATFORM matches a target
matches_platform() {
  local target="$1"
  [ "$PLATFORM" = "$target" ] || [ "$PLATFORM" = "both" ] || [ "$PLATFORM" = "all" ]
}

# Helper: generate plugin manifest JSON (shared across all three platforms)
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
    manifest['$schema'] = 'https://antigravity.google/schemas/v1/plugin.json'
with open(out_path, 'w') as f:
    json.dump(manifest, f, indent=2)
PYEOF
}

# Helper functions for templating
template_agents_for_claude() {
  local src="$1"
  local dest="$2"
  sed -e 's/"view_file"/"Read"/g' \
      -e 's/"grep_search"/"Grep"/g' \
      -e 's/"list_dir"/"Glob"/g' \
      -e 's/"search_web"/"WebSearch"/g' \
      -e 's/"run_command"/"Bash"/g' \
      "$src" > "$dest"
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
  local root_var="$2"
  # Antigravity expects hooks.json as map[string]JSONHookSpec: an object keyed by
  # event name where each value is a SINGLE flat spec object (not the array-of-
  # {matcher,hooks:[...]} shape Claude Code uses).
  cat <<EOF > "$dest"
{
  "PreToolUse": {
    "matcher": "Bash|run_command",
    "type": "command",
    "command": "${root_var}/scripts/safety-check.sh",
    "timeout": 30
  },
  "PostToolUse": {
    "matcher": "write_to_file|replace_file_content",
    "type": "command",
    "command": "${root_var}/scripts/post-edit.sh"
  }
}
EOF
}

template_hooks_for_codex() {
  local dest="$1"
  local root_var="$2"
  cat <<EOF > "$dest"
{
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
EOF
}

# Prepare directories helper
copy_src() {
  local plugin_src_dir="$1"
  local target="$2"
  
  mkdir -p "$target/commands" "$target/skills" "$target/agents" "$target/scripts"
  
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
}

# Helper: install a single platform's files into a target directory
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
      claude)    template_hooks_for_claude       "$target_dir/hooks/hooks.json" "$hooks_root" ;;
      antigravity) template_hooks_for_antigravity "$target_dir/hooks/hooks.json" "$hooks_root" ;;
      codex)     template_hooks_for_codex         "$target_dir/hooks/hooks.json" "$hooks_root" ;;
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

  # Project-level install
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

  # Global distribution build
  local dist_dir="$p_dir/dist"
  mkdir -p "$dist_dir/claude-code/.claude-plugin"
  mkdir -p "$dist_dir/antigravity"
  mkdir -p "$dist_dir/codex"

  if matches_platform "claude"; then
    echo "Configuring Claude Code plugin structure for $p_name..."
    install_platform "claude" "$p_name" "$dist_dir/claude-code" "\${CLAUDE_PLUGIN_ROOT}" "$dist_dir/claude-code/.claude-plugin/plugin.json" "false"
  fi
  if matches_platform "antigravity"; then
    echo "Configuring Antigravity plugin structure for $p_name..."
    install_platform "antigravity" "$p_name" "$dist_dir/antigravity" "\${PLUGIN_ROOT}" "$dist_dir/antigravity/plugin.json" "true"
  fi
  if matches_platform "codex"; then
    echo "Configuring Codex plugin structure for $p_name..."
    install_platform "codex" "$p_name" "$dist_dir/codex" "\${PLUGIN_ROOT}" "$dist_dir/codex/plugin.json" "false"
  fi

  if [ "$DRY_RUN" = true ]; then
    echo "(dry-run) registration skipped for $p_name"
    return
  fi

  # CLI Registrations
  if matches_platform "claude" && [ "$HAS_CLAUDE" = true ]; then
    echo "To register $p_name with Claude Code, run:"
    echo "  claude --plugin-dir \"$SCRIPT_DIR/$dist_dir/claude-code\""
  fi
  if matches_platform "antigravity" && [ "$HAS_AGY" = true ]; then
    echo "Registering $p_name with Antigravity..."
    agy plugin install "$SCRIPT_DIR/$dist_dir/antigravity"
  fi
  if matches_platform "codex" && [ "$HAS_CODEX" = true ]; then
    echo "Registering $p_name with Codex..."
    codex plugin install "$SCRIPT_DIR/$dist_dir/codex"
  fi
}

# Run the installation
if [ "$TARGET_PLUGIN" = "core" ] || [ "$TARGET_PLUGIN" = "all" ]; then
  install_plugin "gin-workflow"
fi

if [ "$TARGET_PLUGIN" = "advanced" ] || [ "$TARGET_PLUGIN" = "all" ]; then
  install_plugin "gin-workflow-advanced"
fi

echo "Install processes completed successfully!"
