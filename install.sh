#!/bin/bash
# install.sh - Installs gin-workflow to Claude Code and/or Antigravity.

set -euo pipefail

PLATFORM="all"
LINK=false
PROJECT_DIR=""
UNINSTALL=false
DRY_RUN=false

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

if [ "$UNINSTALL" = true ]; then
  echo "Uninstalling plugin..."
  rm -rf dist
  echo "Plugin files cleaned. Run manual uninstall if registered globally."
  exit 0
fi

# Detect platforms if "both" or "auto"
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

# Helper functions for templating
template_agents_for_claude() {
  local src="$1"
  local dest="$2"
  # Claude Code tool mappings
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
  local target="$1"
  mkdir -p "$target/commands" "$target/skills" "$target/agents" "$target/scripts"
  
  if [ "$LINK" = true ]; then
    cp -rsf "$SCRIPT_DIR/src/commands/." "$target/commands/"
    cp -rsf "$SCRIPT_DIR/src/skills/." "$target/skills/"
    cp -rsf "$SCRIPT_DIR/src/agents/." "$target/agents/"
    cp -rsf "$SCRIPT_DIR/src/scripts/." "$target/scripts/"
  else
    cp -rf src/commands/. "$target/commands/"
    cp -rf src/skills/. "$target/skills/"
    cp -rf src/agents/. "$target/agents/"
    cp -rf src/scripts/. "$target/scripts/"
  fi
}

# Check project-level install
if [ -n "$PROJECT_DIR" ]; then
  if [ ! -d "$PROJECT_DIR" ]; then
    echo "Error: Project directory '$PROJECT_DIR' does not exist." >&2
    exit 1
  fi
  PROJECT_DIR="$(cd "$PROJECT_DIR" && pwd)"

  # Dry-run guard: project block exits before the global DRY_RUN check,
  # so handle it explicitly here to avoid a real write during a preview.
  if [ "$DRY_RUN" = true ]; then
    echo "(dry-run) would install project-level configs to: $PROJECT_DIR"
    echo "  Claude Code -> $PROJECT_DIR/.claude (hooks root: \$CLAUDE_PROJECT_DIR/.claude)"
    echo "  Antigravity -> $PROJECT_DIR/.agents (hooks root: \$PLUGIN_ROOT)"
    echo "  Codex -> $PROJECT_DIR/.codex (hooks root: \$PLUGIN_ROOT)"
    exit 0
  fi

  echo "Installing plugin locally to project: $PROJECT_DIR"

  if [ "$PLATFORM" = "both" ] || [ "$PLATFORM" = "all" ] || [ "$PLATFORM" = "claude" ]; then
    echo "Configuring project-level Claude Code configs..."
    CLAUDE_TARGET="$PROJECT_DIR/.claude"
    copy_src "$CLAUDE_TARGET"
    mkdir -p "$CLAUDE_TARGET/hooks"
    # Project-level .claude/ configs are NOT an installed plugin, so
    # CLAUDE_PLUGIN_ROOT is unset here. Use CLAUDE_PROJECT_DIR (exported by
    # Claude Code for project hooks) and point at the project's .claude/ tree.
    template_hooks_for_claude "$CLAUDE_TARGET/hooks/hooks.json" "\${CLAUDE_PROJECT_DIR}/.claude"
    for f in "$CLAUDE_TARGET/agents"/*.md; do
      [ -e "$f" ] || continue
      tmp_file=$(mktemp)
      template_agents_for_claude "$f" "$tmp_file"
      mv "$tmp_file" "$f"
    done
  fi
  
  if [ "$PLATFORM" = "both" ] || [ "$PLATFORM" = "all" ] || [ "$PLATFORM" = "antigravity" ]; then
    echo "Configuring project-level Antigravity configs..."
    AGY_TARGET="$PROJECT_DIR/.agents"
    copy_src "$AGY_TARGET"
    mkdir -p "$AGY_TARGET/hooks"
    template_hooks_for_antigravity "$AGY_TARGET/hooks/hooks.json" "\${PLUGIN_ROOT}"
  fi
  
  if [ "$PLATFORM" = "both" ] || [ "$PLATFORM" = "all" ] || [ "$PLATFORM" = "codex" ]; then
    echo "Configuring project-level Codex configs..."
    CODEX_TARGET="$PROJECT_DIR/.codex"
    copy_src "$CODEX_TARGET"
    mkdir -p "$CODEX_TARGET/hooks"
    template_hooks_for_codex "$CODEX_TARGET/hooks/hooks.json" "\${PLUGIN_ROOT}"
  fi
  
  echo "Local project install completed successfully!"
  exit 0
fi

echo "Setting up distribution files..."
mkdir -p dist/claude-code/.claude-plugin
mkdir -p dist/antigravity
mkdir -p dist/codex

# 1. Setup Claude Code Plugin
if [ "$PLATFORM" = "both" ] || [ "$PLATFORM" = "all" ] || [ "$PLATFORM" = "claude" ]; then
  echo "Configuring Claude Code plugin structure..."
  copy_src "dist/claude-code"
  mkdir -p dist/claude-code/hooks
  template_hooks_for_claude "dist/claude-code/hooks/hooks.json" "\${CLAUDE_PLUGIN_ROOT}"
  
  for f in dist/claude-code/agents/*.md; do
    [ -e "$f" ] || continue
    tmp_file=$(mktemp)
    template_agents_for_claude "$f" "$tmp_file"
    mv "$tmp_file" "$f"
  done
  
  # Generate Claude Code manifest (no fabricated $schema URL)
  python3 -c "
import json
meta = json.load(open('plugin.meta.json'))
manifest = {
    'name': meta['name'],
    'version': meta['version'],
    'description': meta['description'],
    'author': meta['author'],
    'repository': meta['repository']
}
with open('dist/claude-code/.claude-plugin/plugin.json', 'w') as f:
    json.dump(manifest, f, indent=2)
"
fi

# 2. Setup Antigravity Plugin
if [ "$PLATFORM" = "both" ] || [ "$PLATFORM" = "all" ] || [ "$PLATFORM" = "antigravity" ]; then
  echo "Configuring Antigravity plugin structure..."
  copy_src "dist/antigravity"
  mkdir -p dist/antigravity/hooks
  template_hooks_for_antigravity "dist/antigravity/hooks/hooks.json" "\${PLUGIN_ROOT}"
  
  # Generate Antigravity manifest (using canonical $schema URL)
  python3 -c "
import json
meta = json.load(open('plugin.meta.json'))
manifest = {
    '\$schema': 'https://antigravity.google/schemas/v1/plugin.json',
    'name': meta['name'],
    'version': meta['version'],
    'description': meta['description'],
    'author': meta['author'],
    'repository': meta['repository']
}
with open('dist/antigravity/plugin.json', 'w') as f:
    json.dump(manifest, f, indent=2)
"
fi

# 3. Setup Codex Plugin
if [ "$PLATFORM" = "both" ] || [ "$PLATFORM" = "all" ] || [ "$PLATFORM" = "codex" ]; then
  echo "Configuring Codex plugin structure..."
  copy_src "dist/codex"
  mkdir -p dist/codex/hooks
  template_hooks_for_codex "dist/codex/hooks/hooks.json" "\${PLUGIN_ROOT}"
  
  # Generate Codex manifest
  python3 -c "
import json
meta = json.load(open('plugin.meta.json'))
manifest = {
    'name': meta['name'],
    'version': meta['version'],
    'description': meta['description'],
    'author': meta['author'],
    'repository': meta['repository']
}
with open('dist/codex/plugin.json', 'w') as f:
    json.dump(manifest, f, indent=2)
"
fi

if [ "$DRY_RUN" = true ]; then
  echo "Dry run complete."
  exit 0
fi

# Run platform installs
if [ "$PLATFORM" = "claude" ] || [ "$PLATFORM" = "both" ] || [ "$PLATFORM" = "all" ]; then
  if [ "$HAS_CLAUDE" = true ]; then
    echo "Registering with Claude Code..."
    echo "Note: Claude Code plugins are registered interactively."
    echo "To register, run: claude --plugin-dir \"$SCRIPT_DIR/dist/claude-code\""
  else
    echo "Claude CLI not found; skipping registration."
  fi
fi

if [ "$PLATFORM" = "antigravity" ] || [ "$PLATFORM" = "both" ] || [ "$PLATFORM" = "all" ]; then
  if [ "$HAS_AGY" = true ]; then
    echo "Registering with Antigravity CLI..."
    if ! agy plugin install "$SCRIPT_DIR/dist/antigravity"; then
      echo "Error: Antigravity plugin installation command failed." >&2
      exit 1
    fi
  else
    echo "Antigravity CLI not found; skipping registration."
  fi
fi

if [ "$PLATFORM" = "codex" ] || [ "$PLATFORM" = "both" ] || [ "$PLATFORM" = "all" ]; then
  if [ "$HAS_CODEX" = true ]; then
    echo "Registering with Codex CLI..."
    if ! codex plugin install "$SCRIPT_DIR/dist/codex"; then
      echo "Error: Codex plugin installation command failed." >&2
      exit 1
    fi
  else
    echo "Codex CLI not found; skipping registration."
  fi
fi

echo "Install process completed successfully!"
