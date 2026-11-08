#!/bin/bash
# install.sh - Installs gin-workflow to Claude Code, Antigravity, Codex CLI, OpenCode, and GitHub Copilot CLI.

set -euo pipefail

PLATFORM="all"
LINK=false
PROJECT_DIR=""
UNINSTALL=false
DRY_RUN=false
TARGET_PLUGIN="gin-workflow"
LAUNCHER_VERSION="3.0"
QA_LAUNCHER_VERSION="0.11"
ORCH_LAUNCHER_VERSION="0.1"
MODIFY_PATH=true
PATH_MARKER='# gin-workflow PATH'

# The plugin directory keeps its name; the plugin id (the `name` in its
# plugin.meta.json) names the launcher and every install target.
plugin_id() {
  case "$1" in
    gin-workflow) echo gin ;;
    *) echo "$1" ;;
  esac
}

while [[ "$#" -gt 0 ]]; do
  case $1 in
    --no-modify-path)
      MODIFY_PATH=false
      shift
      ;;
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
        echo "Error: --plugin requires a value (gin-workflow|gin-qa|gin-ba|gin-orchestrator|all)" >&2
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
  gin-ba)
    PLUGINS=(gin-ba)
    ;;
  gin-orchestrator)
    PLUGINS=(gin-orchestrator)
    ;;
  all)
    PLUGINS=(gin-workflow gin-qa gin-orchestrator gin-ba)
    ;;
  core|advanced)
    echo "Warning: --plugin $TARGET_PLUGIN is deprecated; using gin-workflow." >&2
    PLUGINS=(gin-workflow)
    ;;
  *)
    echo "Error: --plugin must be 'gin-workflow', 'gin-qa', 'gin-ba', 'gin-orchestrator', or 'all' (got '$TARGET_PLUGIN')" >&2
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

path_rc_file() {
  case "$(basename "${SHELL:-}")" in
    zsh) echo "${HOME}/.zshrc" ;;
    bash) echo "${HOME}/.bashrc" ;;
    *) echo "" ;;
  esac
}

register_path() {
  local bin="${HOME}/.local/bin" rc
  case ":${PATH}:" in *":${bin}:"*) return ;; esac
  rc="$(path_rc_file)"
  if [ "$MODIFY_PATH" != true ] || [ -z "$rc" ]; then
    echo "Add ${bin} to PATH: put 'export PATH=\"\$HOME/.local/bin:\$PATH\"' in ${rc:-your shell startup file}." >&2
    return
  fi
  if [ -f "$rc" ] && grep -qF "$PATH_MARKER" "$rc"; then return; fi
  if [ "$DRY_RUN" = true ]; then
    echo "(dry-run) would add ${bin} to PATH in $rc"
    return
  fi
  if ! printf '\n%s\nexport PATH="$HOME/.local/bin:$PATH"\n' "$PATH_MARKER" >> "$rc" 2>/dev/null; then
    echo "Warning: could not write $rc; add 'export PATH=\"\$HOME/.local/bin:\$PATH\"' to it." >&2
    return
  fi
  echo "Added ${bin} to PATH in $rc; open a new terminal or run: source $rc"
}

unregister_path() {
  local rc
  for rc in "${HOME}/.zshrc" "${HOME}/.bashrc"; do
    { [ -f "$rc" ] && grep -qF "$PATH_MARKER" "$rc"; } || continue
    python3 - "$rc" "$PATH_MARKER" <<'PYEOF'
import sys
path, marker = sys.argv[1], sys.argv[2]
lines = open(path, encoding="utf-8").read().split("\n")
out, drop_next = [], False
for line in lines:
    if line == marker:
        drop_next = True
        continue
    if drop_next:
        drop_next = False
        if line == 'export PATH="$HOME/.local/bin:$PATH"':
            continue
    out.append(line)
open(path, "w", encoding="utf-8").write("\n".join(out))
PYEOF
    echo "Removed the gin-workflow PATH block from $rc"
  done
}

HAS_CLAUDE=false
HAS_AGY=false
HAS_CODEX=false
HAS_COPILOT=false
if command -v claude &> /dev/null; then
  HAS_CLAUDE=true
fi
if command -v agy &> /dev/null; then
  HAS_AGY=true
fi
if command -v codex &> /dev/null; then
  HAS_CODEX=true
fi
if command -v copilot &> /dev/null; then
  HAS_COPILOT=true
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

disable_claude_plugin() {
  local settings_path="${HOME}/.claude/settings.json"
  [ -f "$settings_path" ] || return 0
  python3 - "$settings_path" "$1@skills-dir" <<'PYEOF'
import json, sys
path, key = sys.argv[1], sys.argv[2]
try:
    data = json.load(open(path, encoding="utf-8"))
except ValueError:
    data = None
if not isinstance(data, dict) or not isinstance(data.get("enabledPlugins", {}), dict):
    sys.exit(f"Error: cannot parse {path}; fix it and re-run ./install.sh")
plugins = data.get("enabledPlugins", {})
if key in plugins:
    del plugins[key]
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")
PYEOF
}

template_agents_for_claude() {
  local src="$1"
  local dest="$2"
  sed -e 's/"view_file"/"Read"/g' \
      -e 's/"grep_search"/"Grep"/g' \
      -e 's/"list_dir"/"Glob"/g' \
      -e 's/"search_web"/"WebSearch"/g' \
      -e 's/"run_command"/"Bash"/g' \
      -e 's/"replace_file_content"/"Edit"/g' \
      -e 's/"write_to_file"/"Write"/g' \
      "$src" > "$dest"
}

template_agents_for_codex() {
  local src="$1"
  local dest="$2"
  sed -e '/^tools:/d' "$src" > "$dest"
}

template_agents_for_copilot() {
  local src="$1"
  local dest="$2"
  sed -e '/^tools:/ {' \
      -e 's/"view_file"/"view"/g' \
      -e 's/"grep_search"/"grep"/g' \
      -e 's/"list_dir"/"glob"/g' \
      -e 's/"search_web"/"web_fetch"/g' \
      -e 's/"run_command"/"bash"/g' \
      -e 's/"replace_file_content"/"edit"/g' \
      -e 's/"write_to_file"/"edit"/g' \
      -e ':a' \
      -e 's/"edit",[[:space:]]*"edit"/"edit"/g' \
      -e 'ta' \
      -e '}' "$src" > "$dest"
}

template_agents_for_opencode() {
  local src_dir="$1"
  local target_dir="$2"
  local plugin_name="$3"
  local f stem
  [ -d "$src_dir/agents" ] || return 0
  mkdir -p "$target_dir/agents"
  for f in "$src_dir/agents"/*.md; do
    [ -e "$f" ] || continue
    stem="$(basename "$f" .md)"
    awk '
      BEGIN { in_fm = 0 }
      NR == 1 && /^---$/ {
        in_fm = 1
        print
        next
      }
      in_fm && /^---$/ {
        print "mode: subagent"
        print
        in_fm = 0
        next
      }
      in_fm {
        if (/^name:/ || /^tools:/) next
        print
        next
      }
      { print }
    ' "$f" > "$target_dir/agents/${plugin_name}-${stem}.md"
  done
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
            "command": "python3 \"${root_var}/scripts/safety_check.py\"",
            "timeout": 30
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
    "command": "python3 \"\${PLUGIN_ROOT:-${default_root}}/scripts/safety_check.py\"",
    "timeout": 30
  }
}
EOF
}

template_hooks_for_codex() {
  local dest="$1"
  local root_var="$2"
  cat <<EOF > "$dest"
{
  "description": "Gin workflow safety hooks for Codex.",
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash|run_command",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"${root_var}/scripts/safety_check.py\"",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
EOF
}

template_hooks_for_copilot() {
  local dest="$1"
  cat <<'EOF' > "$dest"
{
  "version": 1,
  "hooks": {
    "PreToolUse": [
      {"type": "command", "matcher": "bash", "bash": "s=\"${PLUGIN_ROOT:-${COPILOT_HOME:-$HOME/.copilot}/installed-plugins/_direct/gin}/scripts/safety_check.py\"; if [ -f \"$s\" ]; then exec python3 \"$s\"; fi; echo \"gin: $s not found, hook skipped\" >&2", "timeoutSec": 30}
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
  local install_root="${7:-}"

  if [ "$platform" = "opencode" ]; then
    install_opencode_bundle "$SCRIPT_DIR/plugins/$p_name/src" "$target_dir" "$install_root" "$(plugin_id "$p_name")"
    return
  fi

  if [ "$platform" = "copilot" ]; then
    # Copilot CLI reads the Claude layout (.claude-plugin/plugin.json,
    # skills/<name>/SKILL.md); hooks get Copilot's own format and agents get
    # Copilot tool names.
    copy_bundle_dirs "$SCRIPT_DIR/plugins/$p_name/src" "$target_dir"
    if [ -d "$SCRIPT_DIR/plugins/$p_name/src/agents" ]; then
      mkdir -p "$target_dir/agents"
      for f in "$SCRIPT_DIR/plugins/$p_name/src/agents"/*.md; do
        [ -e "$f" ] || continue
        template_agents_for_copilot "$f" "$target_dir/agents/$(basename "$f")"
      done
    fi
    if [ -d "$SCRIPT_DIR/plugins/$p_name/src/hooks" ]; then
      mkdir -p "$target_dir/hooks"
      template_hooks_for_copilot "$target_dir/hooks/hooks.json"
    fi
    mkdir -p "$(dirname "$manifest_path")"
    generate_manifest "plugins/$p_name" "$manifest_path" "false"
    return
  fi

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
  if [ "$platform" = "codex" ]; then
    for f in "$target_dir/agents"/*.md; do
      [ -e "$f" ] || continue
      local tmp_file
      tmp_file=$(mktemp)
      template_agents_for_codex "$f" "$tmp_file"
      rm -f "$f"
      mv "$tmp_file" "$f"
    done
  fi
  if [ -n "$manifest_path" ]; then
    generate_manifest "plugins/$p_name" "$manifest_path" "$include_schema"
  fi
}

# Write a transformed copy, so a --link symlink never edits the source file.
rewrite_file() {
  local file="$1"
  local expression="$2"
  local tmp
  tmp="$(mktemp)"
  sed "$expression" "$file" > "$tmp"
  rm -f "$file"
  mv "$tmp" "$file"
}

copy_tree() {
  if [ "$LINK" = true ]; then
    cp -rsf "$1" "$2"
  else
    cp -rf "$1" "$2"
  fi
}

# Copies the bundle directories of $src into $target; a third argument names one
# skill directory to leave out.
copy_bundle_dirs() {
  local src="$1"
  local target="$2"
  local skip_skill="${3:-}"
  local dir entry

  mkdir -p "$target"
  for dir in skills scripts references examples rules templates; do
    [ -d "$src/$dir" ] || continue
    [ -n "$(ls -A "$src/$dir" 2>/dev/null)" ] || continue
    mkdir -p "$target/$dir"
    if [ "$dir" = skills ] && [ -n "$skip_skill" ]; then
      for entry in "$src/skills"/* "$src/skills"/.[!.]*; do
        [ -e "$entry" ] || continue
        [ "$(basename "$entry")" = "$skip_skill" ] && continue
        copy_tree "$entry" "$target/skills/"
      done
    else
      copy_tree "$src/$dir/." "$target/$dir/"
    fi
  done
}

install_opencode_bundle() {
  local src="$1"
  local target="$2"
  local install_root="$3"
  local plugin_name="${4:-}"
  local file

  # OpenCode loads skills, references, scripts, rules, and templates. It has no
  # use for the Claude/Codex commands/ files, and copying them would risk
  # clobbering a repository's own .opencode/commands. Agents are translated
  # into namespaced subagents (<plugin>-<agent>.md).
  # gin-qa's `setup` would shadow gin's `setup`, which has the same directory id,
  # so it lands as gin-qa-setup without touching a skills/setup already there.
  local skip_skill=""
  if [ "$plugin_name" = gin-qa ] && [ -d "$src/skills/setup" ]; then
    skip_skill=setup
  fi
  copy_bundle_dirs "$src" "$target" "$skip_skill"
  if [ -n "$skip_skill" ]; then
    rm -rf "$target/skills/gin-qa-setup"
    mkdir -p "$target/skills/gin-qa-setup"
    copy_tree "$src/skills/setup/." "$target/skills/gin-qa-setup/"
    rewrite_file "$target/skills/gin-qa-setup/SKILL.md" 's/^name: setup$/name: gin-qa-setup/'
  fi
  if [ -n "$plugin_name" ]; then
    template_agents_for_opencode "$src" "$target" "$plugin_name"
  fi

  # OpenCode selects a skill by its bare directory id, so gin's generic skill
  # names get a gin- prefix, with the display `name` kept aligned.
  if [ "$plugin_name" = gin ]; then
    local skill
    for skill in learn sdd team worktrees debugging review-response parallel-agents report; do
      [ -d "$target/skills/$skill" ] || continue
      rm -rf "$target/skills/gin-$skill"
      mv "$target/skills/$skill" "$target/skills/gin-$skill"
      rewrite_file "$target/skills/gin-$skill/SKILL.md" "s/^name: $skill\$/name: gin-$skill/"
    done
  fi

  # Shell commands run from the agent's working directory, so point support
  # scripts at the absolute install location; ${PLUGIN_ROOT} does not exist here.
  # `find` (not `grep -r`) so a --link symlinked file is still inspected, then
  # materialized only when it actually needs rewriting.
  if [ -n "$install_root" ]; then
    while IFS= read -r file; do
      [ -n "$file" ] || continue
      if grep -qF '${PLUGIN_ROOT}' "$file" 2>/dev/null; then
        rewrite_file "$file" "s#\${PLUGIN_ROOT}#$install_root#g"
      fi
    done < <(find "$target" \( -type f -o -type l \) 2>/dev/null)
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

# Remove ~/.local/bin/<name> and ~/.local/lib/<name> only when the link is one
# this installer made; a foreign file of that name is kept and reported.
remove_managed_launcher() {
  local name="$1"
  local link="${HOME}/.local/bin/$name" root="${HOME}/.local/lib/$name"
  if [ -e "$link" ] || [ -L "$link" ]; then
    if ! is_managed_launcher_link "$link" "$root" "$name"; then
      echo "Warning: kept $link: not a $name launcher this installer manages" >&2
      return 0
    fi
    if [ "$DRY_RUN" = true ]; then
      echo "(dry-run) would remove the $name launcher at $link"
      return 0
    fi
    rm -f "$link"
    echo "Removed the $name launcher at $link"
  fi
  [ -d "$root" ] || return 0
  if [ "$DRY_RUN" = true ]; then
    echo "(dry-run) would remove $root"
    return 0
  fi
  rm -rf "$root"
  echo "Removed $root"
}

# Add-ons call gin; warn when it is neither installed by this installer nor on PATH.
warn_if_gin_missing() {
  if [ ! -e "${HOME}/.local/bin/gin" ] && ! command -v gin &> /dev/null; then
    echo "Warning: gin is not installed; $1 needs it (./install.sh --plugin gin-workflow)." >&2
  fi
}

install_launcher() {
  local dir="$1" version="$2" name packages package script
  name="$(plugin_id "$dir")"
  local source_dir="$SCRIPT_DIR/plugins/$dir/src/scripts"
  local managed_root="${HOME}/.local/lib/$name"
  local install_dir="$managed_root/$version"
  local launcher_target="$install_dir/$name"
  local launcher_link="${HOME}/.local/bin/$name"
  case "$dir" in
    gin-workflow) packages="workflow_core review_ledger" ;;
    gin-qa) packages=gin_qa ;;
    gin-orchestrator) packages=gin_orchestrator ;;
  esac

  if [ -e "$launcher_link" ] || [ -L "$launcher_link" ]; then
    if [ ! -L "$launcher_link" ] || { [ "$(readlink "$launcher_link")" != "$launcher_target" ] && ! is_managed_launcher_link "$launcher_link" "$managed_root" "$name"; }; then
      echo "Error: refusing to replace a different launcher at $launcher_link" >&2
      return 1
    fi
  fi
  if [ "$dir" = gin-qa ]; then
    warn_if_gin_missing gin-qa
  fi

  if [ "$DRY_RUN" = true ]; then
    echo "(dry-run) would install $name launcher version $version to $launcher_target"
    echo "(dry-run) would link $name launcher on PATH at $launcher_link"
    if [ "$dir" = gin-workflow ]; then
      register_path
      remove_managed_launcher gin-workflow
    fi
    return
  fi

  mkdir -p "$install_dir" "$(dirname "$launcher_link")"
  if [ "$dir" = gin-workflow ]; then
    mkdir -p "$install_dir/rules"
  fi
  cp -f "$source_dir/$name" "$launcher_target"
  for package in $packages; do
    mkdir -p "$install_dir/$package"
    cp -rf "$source_dir/$package/." "$install_dir/$package/"
  done
  if [ "$dir" = gin-workflow ]; then
    cp -rf "$source_dir/../rules/." "$install_dir/rules/"
  fi
  if [ -d "$source_dir/../templates" ]; then
    mkdir -p "$install_dir/templates"
    cp -rf "$source_dir/../templates/." "$install_dir/templates/"
  fi
  if [ "$dir" = gin-workflow ]; then
    PYTHONPATH="$source_dir" python3 -B -m workflow_core.snapshot "$SCRIPT_DIR/plugins/gin-workflow/src" "$install_dir"
  fi
  chmod 755 "$launcher_target"
  ln -sfn "$launcher_target" "$launcher_link"
  echo "Installed $name launcher version $version to $launcher_link"
  if [ "$dir" = gin-workflow ]; then
    register_path
    remove_managed_launcher gin-workflow
  fi
}

CODEX_MARKETPLACE_READY=false

# Remove the global OpenCode agents an earlier install of plugin id $1 copied, as
# its bundle lists them; a gin-*.md glob would also match gin-qa's and the user's own.
remove_opencode_agents() {
  local f
  for f in "${HOME}/.config/opencode/skills/$1/agents"/*.md; do
    [ -e "$f" ] || continue
    rm -f "${HOME}/.config/opencode/agents/$(basename "$f")"
  done
}

# The 2.x global install of this plugin under its old id, for each selected harness.
remove_legacy_plugin() {
  local old=gin-workflow
  if [ "$DRY_RUN" = true ]; then
    echo "(dry-run) would remove the old $old plugin installs"
    return
  fi
  if matches_platform "claude" && [ "$HAS_CLAUDE" = true ]; then
    disable_claude_plugin "$old"
    rm -rf "${HOME}/.claude/skills/$old"
  fi
  if matches_platform "opencode"; then
    rm -rf "${HOME}/.config/opencode/skills/$old"
    rm -f "${HOME}/.config/opencode/agents/$old-"*.md
  fi
  if matches_platform "antigravity" && [ "$HAS_AGY" = true ]; then
    rm -rf "${HOME}/.gemini/config/plugins/$old"
  fi
  # Best effort: the old plugin may not be registered, and then the harness CLI exits non-zero.
  if matches_platform "codex" && [ "$HAS_CODEX" = true ]; then
    codex plugin remove "$old@gin-workflow-marketplace" >/dev/null 2>&1 || true
  fi
  if matches_platform "copilot" && [ "$HAS_COPILOT" = true ]; then
    copilot plugin uninstall "$old" >/dev/null 2>&1 || true
  fi
}

# Skill folders a 2.x project install wrote under the old names, for each selected harness.
remove_legacy_project_install() {
  local platform root skill
  for platform in claude antigravity codex opencode; do
    matches_platform "$platform" || continue
    case "$platform" in
      claude) root="$PROJECT_DIR/.claude" ;;
      antigravity) root="$PROJECT_DIR/.agents" ;;
      codex) root="$PROJECT_DIR/.codex" ;;
      opencode)
        root="$PROJECT_DIR/.opencode"
        rm -rf "$root/skills/gin-workflow-report"
        rm -f "$root/agents/gin-workflow-"*.md
        ;;
    esac
    for skill in gin-knowledge gin-sdd gin-team gin-worktrees gin-debugging gin-review-response gin-parallel-agents; do
      rm -rf "$root/skills/$skill"
    done
  done
}

install_plugin() {
  local p_name="$1"
  local p_dir="plugins/$p_name"
  local p_id
  p_id="$(plugin_id "$p_name")"

  if [ ! -d "$p_dir" ]; then
    echo "Warning: Plugin directory $p_dir not found. Skipping."
    return
  fi

  echo "=========================================="
  echo "Processing plugin: $p_name"
  echo "=========================================="

  if [ -n "$PROJECT_DIR" ]; then
    if matches_platform "copilot"; then
      echo "Warning: Copilot plugins are global; --project skips copilot." >&2
    fi
    if [ "$DRY_RUN" = true ]; then
      echo "(dry-run) would install project-level configs for $p_name to $PROJECT_DIR"
      if [ "$p_name" = gin-workflow ]; then
        echo "(dry-run) would remove the old gin-workflow skill folders from $PROJECT_DIR"
      fi
      return
    fi

    if [ "$p_name" = gin-workflow ]; then remove_legacy_project_install; fi
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
    if matches_platform "opencode"; then
      install_platform "opencode" "$p_name" "$PROJECT_DIR/.opencode" "" "" "" "$PROJECT_DIR/.opencode"
    fi
    return
  fi

  local dist_dir="$p_dir/dist"
  # dist/ is fully generated: rebuild each selected platform from scratch so files
  # removed from src (commands, skills) never linger and shadow same-name skills.
  if matches_platform "claude"; then rm -rf "${dist_dir:?}/claude-code"; fi
  if matches_platform "antigravity"; then rm -rf "${dist_dir:?}/antigravity"; fi
  if matches_platform "codex"; then rm -rf "${dist_dir:?}/codex"; fi
  if matches_platform "opencode"; then rm -rf "${dist_dir:?}/opencode"; fi
  if matches_platform "copilot"; then rm -rf "${dist_dir:?}/copilot"; fi
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
    agy_install_path="${HOME}/.gemini/config/plugins/${p_id}"
    install_platform "antigravity" "$p_name" "$dist_dir/antigravity" "$agy_install_path" "$dist_dir/antigravity/plugin.json" "true"
  fi
  if matches_platform "codex"; then
    echo "Configuring Codex plugin structure for $p_name..."
    install_platform "codex" "$p_name" "$dist_dir/codex" "\${PLUGIN_ROOT}" "$dist_dir/codex/.codex-plugin/plugin.json" "false"
  fi
  if matches_platform "opencode"; then
    echo "Configuring OpenCode skill structure for $p_name..."
    install_platform "opencode" "$p_name" "$dist_dir/opencode" "" "" "" "${HOME}/.config/opencode/skills/${p_id}"
  fi
  if matches_platform "copilot"; then
    echo "Configuring Copilot plugin structure for $p_name..."
    # Copilot names a direct install after the source directory, so the
    # bundle directory carries the plugin id to keep plugins apart.
    install_platform "copilot" "$p_name" "$dist_dir/copilot/$p_id" "" "$dist_dir/copilot/$p_id/.claude-plugin/plugin.json" "false"
  fi

  if [ "$p_name" = gin-workflow ]; then remove_legacy_plugin; fi

  if [ "$DRY_RUN" = true ]; then
    echo "(dry-run) registration skipped for $p_name"
    if matches_platform "claude"; then
      local claude_install_dir="${HOME}/.claude/skills/${p_id}"
      echo "(dry-run) would install global Claude Code plugin to $claude_install_dir"
    fi
    if matches_platform "opencode"; then
      local opencode_install_dir="${HOME}/.config/opencode/skills/${p_id}"
      echo "(dry-run) would install global OpenCode skills to $opencode_install_dir"
    fi
    if matches_platform "copilot"; then
      echo "(dry-run) would install Copilot plugin from $SCRIPT_DIR/$dist_dir/copilot/$p_id"
    fi
    return
  fi

  if matches_platform "claude" && [ "$HAS_CLAUDE" = true ]; then
    local claude_install_dir="${HOME}/.claude/skills/${p_id}"
    echo "Installing $p_id globally to Claude Code skills directory: $claude_install_dir"
    rm -rf "$claude_install_dir"
    mkdir -p "$(dirname "$claude_install_dir")"
    if [ "$LINK" = true ]; then
      ln -sf "$SCRIPT_DIR/$dist_dir/claude-code" "$claude_install_dir"
    else
      cp -rf "$dist_dir/claude-code" "$claude_install_dir"
    fi
    enable_claude_plugin "$p_id"
    echo "Successfully installed and enabled $p_id globally in Claude Code!"
  fi
  if matches_platform "opencode"; then
    local opencode_install_dir="${HOME}/.config/opencode/skills/${p_id}"
    echo "Installing $p_id skills globally to OpenCode: $opencode_install_dir"
    remove_opencode_agents "$p_id"
    rm -rf "$opencode_install_dir"
    mkdir -p "$(dirname "$opencode_install_dir")"
    if [ "$LINK" = true ]; then
      ln -sf "$SCRIPT_DIR/$dist_dir/opencode" "$opencode_install_dir"
    else
      cp -rf "$dist_dir/opencode" "$opencode_install_dir"
    fi
    if [ -d "$dist_dir/opencode/agents" ]; then
      mkdir -p "${HOME}/.config/opencode/agents"
      cp -rf "$dist_dir/opencode/agents/${p_id}-"*.md "${HOME}/.config/opencode/agents/"
    fi
    echo "Successfully installed $p_id globally in OpenCode!"
  fi
  if matches_platform "antigravity" && [ "$HAS_AGY" = true ]; then
    echo "Registering $p_id with Antigravity..."
    agy plugin install "$SCRIPT_DIR/$dist_dir/antigravity"
  fi
  if matches_platform "codex" && [ "$HAS_CODEX" = true ]; then
    echo "Registering $p_id with Codex..."
    # codex plugin marketplace add/plugin add are no-ops when already
    # registered by name, and the git-subdir source snapshots content at
    # add-time -- so a repeat run would keep serving a stale snapshot even
    # after local changes are committed. Force a fresh registration.
    # With --plugin all, refresh the marketplace once so the second plugin does not drop the first.
    codex plugin remove "$p_id@gin-workflow-marketplace" >/dev/null 2>&1 || true
    if [ "$CODEX_MARKETPLACE_READY" = false ]; then
      codex plugin marketplace remove "gin-workflow-marketplace" >/dev/null 2>&1 || true
      codex plugin marketplace add "$SCRIPT_DIR"
      CODEX_MARKETPLACE_READY=true
    fi
    codex plugin add "$p_id@gin-workflow-marketplace"
  fi
  if matches_platform "copilot"; then
    if [ "$HAS_COPILOT" = true ]; then
      echo "Registering $p_id with Copilot..."
      # Remove first so a re-run replaces the installed copy.
      copilot plugin uninstall "$p_id" >/dev/null 2>&1 || true
      copilot plugin install "$SCRIPT_DIR/$dist_dir/copilot/$p_id"
    else
      echo "Copilot CLI not found; skipped registration. Run: copilot plugin install $SCRIPT_DIR/$dist_dir/copilot/$p_id"
    fi
  fi
}

if [ "$UNINSTALL" = true ]; then
  echo "Uninstalling plugins..."
  ids=()
  for p_name in "${PLUGINS[@]}"; do
    ids+=("$(plugin_id "$p_name")")
  done
  if [[ " ${PLUGINS[*]} " == *" gin-workflow "* ]]; then ids+=(gin-workflow); fi
  for p_id in "${ids[@]}"; do
    if [ "$p_id" = gin-workflow ]; then
      rm -f "${HOME}/.config/opencode/agents/gin-workflow-"*.md
    else
      remove_opencode_agents "$p_id"
    fi
    rm -rf "${HOME}/.config/opencode/skills/${p_id}"
  done
  # After the OpenCode agents: a --link install lists them through dist.
  rm -rf plugins/gin-workflow/dist plugins/gin-workflow-advanced/dist plugins/gin-qa/dist plugins/gin-orchestrator/dist plugins/gin-ba/dist
  if command -v copilot &> /dev/null; then
    for p_id in "${ids[@]}"; do
      # Best effort: a plugin that is not registered makes the CLI exit non-zero.
      copilot plugin uninstall "$p_id" >/dev/null 2>&1 || true
    done
  fi
  if [[ " ${PLUGINS[*]} " == *" gin-workflow "* ]]; then
    remove_managed_launcher gin
    remove_managed_launcher gin-workflow
  fi
  unregister_path
  echo "Removed generated dist output, the gin launcher, the global OpenCode skill install, and the Copilot plugin registration, under the gin and the old gin-workflow name. Project installs (a repository's .opencode/) and the Claude Code, Codex, and Antigravity registrations are left for manual removal."
  exit 0
fi

if [[ " ${PLUGINS[*]} " == *" gin-orchestrator "* && " ${PLUGINS[*]} " != *" gin-workflow "* ]] &&
   [ "$(readlink "${HOME}/.local/bin/gin" 2>/dev/null)" != "${HOME}/.local/lib/gin/$LAUNCHER_VERSION/gin" ]; then
  echo "gin-orchestrator requires gin $LAUNCHER_VERSION; installing it first."
  PLUGINS=(gin-workflow "${PLUGINS[@]}")
fi

# An installed add-on runs its own library copy, which calls gin; installing gin
# refreshes each add-on whose launcher this installer manages. A project install
# refreshes the launcher only: the add-on's skills are not written into the
# project, where gin-qa's `setup` would replace gin's in the shared .opencode/skills.
REFRESHED_ADDONS=()
if [[ " ${PLUGINS[*]} " == *" gin-workflow "* ]]; then
  for addon in gin-qa gin-orchestrator; do
    if [[ " ${PLUGINS[*]} " != *" $addon "* ]] &&
       is_managed_launcher_link "${HOME}/.local/bin/$addon" "${HOME}/.local/lib/$addon" "$addon"; then
      echo "Refreshing the installed $addon add-on."
      PLUGINS+=("$addon")
      REFRESHED_ADDONS+=("$addon")
    fi
  done
fi

for p_name in "${PLUGINS[@]}"; do
  case "$p_name" in
    gin-workflow) install_launcher "$p_name" "$LAUNCHER_VERSION" ;;
    gin-qa) install_launcher "$p_name" "$QA_LAUNCHER_VERSION" ;;
    gin-orchestrator) install_launcher "$p_name" "$ORCH_LAUNCHER_VERSION" ;;
    gin-ba) warn_if_gin_missing gin-ba ;;
  esac
  if [ -n "$PROJECT_DIR" ] && [[ " ${REFRESHED_ADDONS[*]:-} " == *" $p_name "* ]]; then
    continue
  fi
  install_plugin "$p_name"
done

echo "Install processes completed successfully!"
