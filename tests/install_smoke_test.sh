#!/bin/bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

TEST_HOME="$(mktemp -d)"
export HOME="$TEST_HOME"

assert_exists() {
  local path="$1"
  if [ ! -e "$path" ]; then
    echo "Expected path to exist: $path" >&2
    exit 1
  fi
}

assert_not_exists() {
  local path="$1"
  if [ -e "$path" ]; then
    echo "Expected path to be absent: $path" >&2
    exit 1
  fi
}

assert_contains() {
  local path="$1"
  local pattern="$2"
  if ! grep -F -q "$pattern" "$path"; then
    echo "Expected '$path' to contain pattern: $pattern" >&2
    exit 1
  fi
}

assert_not_contains() {
  local path="$1"
  local pattern="$2"
  if grep -F -q "$pattern" "$path"; then
    echo "Expected '$path' to not contain pattern: $pattern" >&2
    exit 1
  fi
}

assert_line() {
  local path="$1"
  local line="$2"
  if ! grep -F -x -q "$line" "$path"; then
    echo "Expected '$path' to contain the line: $line" >&2
    exit 1
  fi
}

assert_line_order() {
  local path="$1"
  local first="$2"
  local second="$3"
  local first_line second_line
  first_line="$(grep -n -F -m1 "$first" "$path" | cut -d: -f1)"
  second_line="$(grep -n -F -m1 "$second" "$path" | cut -d: -f1)"
  if [ -z "$first_line" ] || [ -z "$second_line" ] || [ "$first_line" -ge "$second_line" ]; then
    echo "Expected '$first' before '$second' in $path" >&2
    exit 1
  fi
}

assert_codex_hooks_schema() {
  local path="$1"
  python3 - "$path" <<'PYEOF'
import json
import sys

path = sys.argv[1]
with open(path, encoding="utf-8") as f:
    data = json.load(f)

top_level_keys = set(data)
if not top_level_keys <= {"description", "hooks"}:
    raise SystemExit(f"unexpected top-level keys: {sorted(top_level_keys)}")

hooks = data.get("hooks")
if not isinstance(hooks, dict):
    raise SystemExit("hooks must be an object")

if "PreToolUse" not in hooks:
    raise SystemExit("missing hooks.PreToolUse")
if "PostToolUse" in hooks:
    raise SystemExit("unexpected hooks.PostToolUse")
PYEOF
}

assert_workflow_v22_layout() {
  local root="$1"
  local relative
  local required=(
    "skills/setup/SKILL.md"
    "skills/workflow/SKILL.md"
    "skills/discuss/SKILL.md"
    "skills/plan/SKILL.md"
    "skills/plan/plan-schema.md"
    "skills/orchestrate/SKILL.md"
    "skills/execute/SKILL.md"
    "skills/execute/references/worker-lifecycle.md"
    "skills/execute/references/delegation-policy.md"
    "skills/execute/references/result-contract.md"
    "skills/ship/SKILL.md"
    "skills/review/SKILL.md"
    "references/stage-contract.md"
    "scripts/gin"
    "scripts/workflow_core/configuration.py"
    "scripts/workflow_core/setup_service.py"
    "scripts/workflow_core/router.py"
    "scripts/workflow_core/provider_config.py"
    "scripts/workflow_core/assignments.py"
    "examples/config.full.yaml"
  )
  for relative in "${required[@]}"; do
    assert_exists "$root/$relative"
  done
}

rm -rf plugins/gin-workflow/dist
rm -rf plugins/gin-workflow-advanced/dist
rm -rf plugins/gin-qa/dist
rm -rf plugins/gin-orchestrator/dist

output_file="$(mktemp)"
trap 'rm -f "$output_file"' EXIT

# Seed leftovers from an older build; the installer must rebuild dist from scratch.
mkdir -p plugins/gin-workflow/dist/claude-code/commands plugins/gin-workflow/dist/claude-code/skills/writing-plans
touch plugins/gin-workflow/dist/claude-code/commands/stale-from-old-build.md plugins/gin-workflow/dist/claude-code/skills/writing-plans/SKILL.md

./install.sh --platform claude --dry-run >"$output_file"

assert_contains "$output_file" "Processing plugin: gin-workflow"
assert_not_contains "$output_file" "gin-workflow-advanced"
assert_contains "$output_file" "would install global Claude Code plugin to"
assert_contains "$output_file" "would install gin launcher version 3.0 to"
assert_contains "$output_file" "would link gin launcher on PATH at"
assert_not_contains "$output_file" "gin-qa"
assert_not_exists "plugins/gin-qa/dist"
assert_not_exists "plugins/gin-orchestrator/dist"

assert_exists "plugins/gin-workflow/dist/claude-code/skills/tech-doc/SKILL.md"
assert_exists "plugins/gin-workflow/dist/claude-code/skills/write-doc/SKILL.md"
assert_exists "plugins/gin-workflow/dist/claude-code/skills/roadmap/SKILL.md"
assert_exists "plugins/gin-workflow/dist/claude-code/skills/report/SKILL.md"
assert_not_exists "plugins/gin-workflow/dist/claude-code/agents/solution-architect.md"
assert_exists "plugins/gin-workflow/dist/claude-code/agents/developer.md"
assert_not_exists "plugins/gin-workflow/dist/claude-code/agents/full-stack-developer.md"
assert_not_exists "plugins/gin-workflow/dist/claude-code/agents/codebase-mapper.md"
assert_exists "plugins/gin-workflow/dist/claude-code/agents/qa-agent.md"
assert_exists "plugins/gin-workflow/dist/claude-code/agents/docs-writer.md"
assert_not_exists "plugins/gin-workflow/dist/claude-code/agents/bead-worker.md"
assert_exists "plugins/gin-workflow/dist/claude-code/skills/debugging/SKILL.md"
assert_exists "plugins/gin-workflow/dist/claude-code/skills/debugging/find-polluter.sh"
assert_exists "plugins/gin-workflow/dist/claude-code/skills/review-response/SKILL.md"
assert_exists "plugins/gin-workflow/dist/claude-code/skills/worktrees/SKILL.md"
assert_exists "plugins/gin-workflow/dist/claude-code/skills/parallel-agents/SKILL.md"
assert_exists "plugins/gin-workflow/dist/claude-code/skills/learn/SKILL.md"
assert_exists "plugins/gin-workflow/dist/claude-code/skills/review/SKILL.md"
assert_exists "plugins/gin-workflow/dist/claude-code/scripts/gin"
assert_workflow_v22_layout "plugins/gin-workflow/dist/claude-code"

# Skills are the slash commands; a same-name command would shadow its skill (gin-workflow-04f).
assert_not_exists "plugins/gin-workflow/dist/claude-code/commands/stale-from-old-build.md"
assert_not_exists "plugins/gin-workflow/dist/claude-code/skills/writing-plans/SKILL.md"
if [ -d "plugins/gin-workflow/dist/claude-code/commands" ] && [ -n "$(ls -A plugins/gin-workflow/dist/claude-code/commands)" ]; then
  echo "Expected no commands in dist/claude-code (they shadow same-name skills)" >&2
  exit 1
fi
assert_not_exists "plugins/gin-workflow-advanced"

assert_contains "plugins/gin-workflow/dist/claude-code/skills/plan/SKILL.md" "Beads-ready implementation plan"
for skill_file in plugins/gin-workflow/dist/claude-code/skills/*/SKILL.md; do
  assert_not_contains "$skill_file" 'superpowers'
done

assert_contains 'plugins/gin-workflow/dist/claude-code/skills/orchestrate/SKILL.md' 'Read [references/stage-contract.md](../../references/stage-contract.md) now'
assert_contains "plugins/gin-workflow/dist/claude-code/skills/tech-doc/SKILL.md" "single combined document"
assert_contains "plugins/gin-workflow/dist/claude-code/skills/tech-doc/SKILL.md" "03-ARCHITECTURE.md"
assert_contains "plugins/gin-workflow/dist/claude-code/skills/tech-doc/SKILL.md" "codegraph"
assert_contains "plugins/gin-workflow/dist/claude-code/skills/roadmap/SKILL.md" "every file of the tech-doc folder"
assert_contains "plugins/gin-workflow/dist/claude-code/skills/roadmap/SKILL.md" "never close or delete"
assert_contains "plugins/gin-workflow/dist/claude-code/skills/roadmap/SKILL.md" "no open blocker first"
assert_not_contains "plugins/gin-workflow/dist/claude-code/skills/roadmap/SKILL.md" "sprint:"
assert_contains "plugins/gin-workflow/dist/claude-code/skills/roadmap/SKILL.md" "Never \`gin task create --id\` an existing id"
assert_contains "plugins/gin-workflow/dist/claude-code/skills/discuss/SKILL.md" "/discuss <epic-id>"
assert_contains "plugins/gin-workflow/dist/claude-code/skills/orchestrate/SKILL.md" "create no other epic"
assert_contains "plugins/gin-workflow/dist/claude-code/skills/execute/SKILL.md" "labelled \`roadmap\`"
assert_contains "plugins/gin-workflow/dist/claude-code/skills/progress/SKILL.md" "list --parent <milestone-id>"
assert_not_contains "plugins/gin-workflow/dist/claude-code/skills/progress/SKILL.md" "sprint:"

./install.sh --platform claude --plugin gin-qa --dry-run >"$output_file" 2>&1

assert_contains "$output_file" "Warning: gin is not installed; gin-qa needs it (./install.sh --plugin gin-workflow)."
assert_contains "$output_file" "Processing plugin: gin-qa"
assert_not_contains "$output_file" "Processing plugin: gin-workflow"
assert_contains "$output_file" "would install gin-qa launcher version 0.10 to"
assert_exists "plugins/gin-qa/dist/claude-code/.claude-plugin/plugin.json"
assert_exists "plugins/gin-qa/dist/claude-code/skills/cases/SKILL.md"
assert_exists "plugins/gin-qa/dist/claude-code/skills/e2e/SKILL.md"
assert_exists "plugins/gin-qa/dist/claude-code/skills/tests/SKILL.md"
assert_exists "plugins/gin-qa/dist/claude-code/skills/e2e/references/explore-case.md"
assert_exists "plugins/gin-qa/dist/claude-code/skills/setup/SKILL.md"
assert_exists "plugins/gin-qa/dist/claude-code/templates/project-skill.md"
assert_exists "plugins/gin-qa/dist/claude-code/agents/e2e-tester.md"
assert_contains "plugins/gin-qa/dist/claude-code/agents/e2e-tester.md" '"Bash"'
assert_not_contains "plugins/gin-qa/dist/claude-code/agents/e2e-tester.md" '"run_command"'
assert_exists "plugins/gin-qa/dist/claude-code/templates/evidence.ts"
assert_exists "plugins/gin-qa/dist/claude-code/templates/playwright.config.ts"
assert_exists "plugins/gin-qa/dist/claude-code/templates/guidelines.md"
assert_exists "plugins/gin-qa/dist/claude-code/templates/qa-readme.md"
assert_exists "plugins/gin-qa/dist/claude-code/scripts/gin_qa/cli.py"
assert_contains ".claude-plugin/marketplace.json" "\"path\": \"plugins/gin-qa/src\""

# gin-orchestrator needs gin-workflow: an empty HOME installs gin-workflow first.
empty_home="$(mktemp -d)"
HOME="$empty_home" ./install.sh --platform claude --plugin gin-orchestrator --dry-run >"$output_file"
assert_contains "$output_file" "gin-orchestrator requires gin 3.0; installing it first."
assert_contains "$output_file" "Processing plugin: gin-orchestrator"
assert_contains "$output_file" "would install gin-orchestrator launcher version 0.1 to"
assert_line_order "$output_file" "installing it first." "would install gin launcher version 3.0 to"
assert_line_order "$output_file" "would install gin launcher version 3.0 to" "would install gin-orchestrator launcher version 0.1 to"
assert_exists "plugins/gin-orchestrator/dist/claude-code/.claude-plugin/plugin.json"
assert_exists "plugins/gin-orchestrator/dist/claude-code/skills/providers/SKILL.md"
assert_exists "plugins/gin-orchestrator/dist/claude-code/scripts/gin-orchestrator"
assert_exists "plugins/gin-orchestrator/dist/claude-code/scripts/gin_orchestrator/cli.py"
assert_exists "plugins/gin-orchestrator/dist/claude-code/examples/orchestrator.local.example.yaml"
assert_contains ".claude-plugin/marketplace.json" "\"path\": \"plugins/gin-orchestrator/src\""

HOME="$empty_home" ./install.sh --platform claude --plugin all --dry-run >"$output_file"
assert_contains "$output_file" "Processing plugin: gin-workflow"
assert_contains "$output_file" "Processing plugin: gin-qa"
assert_contains "$output_file" "Processing plugin: gin-orchestrator"
assert_not_contains "$output_file" "installing it first"
assert_contains "$output_file" "would install gin-orchestrator launcher version 0.1 to"
rm -rf "$empty_home"

./install.sh --platform codex --dry-run >"$output_file"

assert_exists "plugins/gin-workflow/dist/codex/.codex-plugin/plugin.json"
assert_exists "plugins/gin-workflow/dist/codex/hooks/hooks.json"
assert_not_exists "plugins/gin-workflow/dist/codex/agents/solution-architect.md"
assert_exists "plugins/gin-workflow/dist/codex/agents/developer.md"
assert_not_exists "plugins/gin-workflow/dist/codex/agents/full-stack-developer.md"
assert_not_exists "plugins/gin-workflow/dist/codex/agents/codebase-mapper.md"
assert_exists "plugins/gin-workflow/dist/codex/agents/qa-agent.md"
assert_exists "plugins/gin-workflow/dist/codex/agents/docs-writer.md"
assert_not_exists "plugins/gin-workflow/dist/codex/agents/bead-worker.md"
assert_exists "plugins/gin-workflow/dist/codex/skills/review/SKILL.md"
assert_exists "plugins/gin-workflow/dist/codex/skills/report/SKILL.md"
assert_contains "plugins/gin-workflow/dist/codex/.codex-plugin/plugin.json" "\"name\": \"gin\""
assert_contains "plugins/gin-workflow/dist/codex/hooks/hooks.json" "\"description\""
assert_contains "plugins/gin-workflow/dist/codex/hooks/hooks.json" "\"hooks\": {"
assert_contains "plugins/gin-workflow/dist/codex/hooks/hooks.json" "\"PreToolUse\""
assert_codex_hooks_schema "plugins/gin-workflow/dist/codex/hooks/hooks.json"
assert_contains "plugins/gin-workflow/dist/codex/hooks/hooks.json" '"command": "python3 \"${PLUGIN_ROOT}/scripts/safety_check.py\""'
assert_contains 'plugins/gin-workflow/dist/codex/skills/orchestrate/SKILL.md' 'Read [references/stage-contract.md](../../references/stage-contract.md) now'
assert_contains "plugins/gin-workflow/dist/codex/skills/tech-doc/SKILL.md" "single combined document"
assert_contains "plugins/gin-workflow/dist/codex/skills/tech-doc/SKILL.md" "03-ARCHITECTURE.md"
assert_contains "plugins/gin-workflow/dist/codex/skills/tech-doc/SKILL.md" "codegraph"
assert_workflow_v22_layout "plugins/gin-workflow/dist/codex"
assert_contains ".claude-plugin/marketplace.json" "\"path\": \"plugins/gin-workflow/src\""
assert_not_contains ".claude-plugin/marketplace.json" "gin-workflow-advanced"

./install.sh --platform antigravity --dry-run >"$output_file"

assert_exists "plugins/gin-workflow/dist/antigravity/plugin.json"
assert_exists "plugins/gin-workflow/dist/antigravity/hooks/hooks.json"
assert_exists "plugins/gin-workflow/dist/antigravity/skills/report/SKILL.md"
assert_workflow_v22_layout "plugins/gin-workflow/dist/antigravity"

./install.sh --platform opencode --dry-run >"$output_file"

assert_contains "$output_file" "Configuring OpenCode skill structure for gin-workflow"
assert_contains "$output_file" "would install global OpenCode skills to"
assert_exists "plugins/gin-workflow/dist/opencode/skills/setup/SKILL.md"
assert_exists "plugins/gin-workflow/dist/opencode/skills/gin-report/SKILL.md"
assert_not_exists "plugins/gin-workflow/dist/opencode/skills/report"
assert_exists "plugins/gin-workflow/dist/opencode/references/stage-contract.md"
assert_exists "plugins/gin-workflow/dist/opencode/agents/gin-developer.md"
assert_not_exists "plugins/gin-workflow/dist/opencode/commands"
assert_not_exists "plugins/gin-workflow/dist/opencode/hooks/hooks.json"
assert_not_exists "plugins/gin-workflow/dist/opencode/plugin.json"
assert_contains "plugins/gin-workflow/dist/opencode/skills/gin-report/SKILL.md" "name: gin-report"
assert_workflow_v22_layout "plugins/gin-workflow/dist/opencode"

./install.sh --platform opencode --plugin gin-qa --dry-run >"$output_file"

assert_exists "plugins/gin-qa/dist/opencode/skills/gin-qa-setup/SKILL.md"
assert_contains "plugins/gin-qa/dist/opencode/skills/gin-qa-setup/SKILL.md" "name: gin-qa-setup"
assert_not_exists "plugins/gin-qa/dist/opencode/skills/setup"
assert_exists "plugins/gin-workflow/dist/opencode/skills/setup/SKILL.md"
assert_contains "plugins/gin-workflow/dist/opencode/skills/setup/SKILL.md" "name: setup"

./install.sh --platform copilot --plugin all --dry-run >"$output_file"

assert_contains "$output_file" "Configuring Copilot plugin structure for gin-workflow"
assert_contains "$output_file" "(dry-run) would install Copilot plugin from $ROOT_DIR/plugins/gin-workflow/dist/copilot/gin"
assert_exists "plugins/gin-workflow/dist/copilot/gin/.claude-plugin/plugin.json"
assert_contains "plugins/gin-workflow/dist/copilot/gin/.claude-plugin/plugin.json" '"name": "gin"'
assert_exists "plugins/gin-workflow/dist/copilot/gin/skills/setup/SKILL.md"
assert_exists "plugins/gin-workflow/dist/copilot/gin/skills/report/SKILL.md"
assert_exists "plugins/gin-workflow/dist/copilot/gin/references/stage-contract.md"
assert_exists "plugins/gin-workflow/dist/copilot/gin/scripts/gin"
assert_exists "plugins/gin-workflow/dist/copilot/gin/hooks/hooks.json"
assert_contains "plugins/gin-workflow/dist/copilot/gin/hooks/hooks.json" '/scripts/safety_check.py\"; if [ -f \"$s\" ]; then exec python3 \"$s\"'
assert_exists "plugins/gin-workflow/dist/copilot/gin/agents/developer.md"
assert_contains "plugins/gin-workflow/dist/copilot/gin/agents/developer.md" '"view", "grep", "glob", "bash", "edit"'
assert_not_exists "plugins/gin-workflow/dist/copilot/gin/commands"
assert_exists "plugins/gin-qa/dist/copilot/gin-qa/agents/e2e-tester.md"
assert_contains "plugins/gin-qa/dist/copilot/gin-qa/agents/e2e-tester.md" '"bash", "edit"]'
assert_not_contains "plugins/gin-qa/dist/copilot/gin-qa/agents/e2e-tester.md" '"edit", "edit"'

# Test actual installation with a mocked HOME
echo "Running mock HOME global installation test..."
MOCK_HOME="$(mktemp -d)"
trap 'rm -rf "$MOCK_HOME"; rm -f "$output_file"' EXIT

mkdir -p "$MOCK_HOME/.claude"
echo '{"enabledPlugins": {"gin-workflow@skills-dir": false}}' > "$MOCK_HOME/.claude/settings.json"

HOME="$MOCK_HOME" ./install.sh --platform claude >/dev/null

assert_exists "$MOCK_HOME/.claude/skills/gin/skills/tech-doc/SKILL.md"
assert_not_exists "$MOCK_HOME/.claude/skills/gin/agents/bead-worker.md"
assert_not_exists "$MOCK_HOME/.claude/skills/gin/agents/solution-architect.md"
assert_exists "$MOCK_HOME/.claude/skills/gin/agents/developer.md"
assert_exists "$MOCK_HOME/.claude/skills/gin/scripts/safety_check.py"
assert_contains "$MOCK_HOME/.claude/skills/gin/hooks/hooks.json" '"command": "python3 \"${CLAUDE_PLUGIN_ROOT}/scripts/safety_check.py\""'
# No installed file names the old bash hook.
if grep -rlF "safety-check" "$MOCK_HOME/.claude/skills/gin"; then
  echo "Expected no installed file to reference the old safety-check script" >&2
  exit 1
fi
assert_contains "$MOCK_HOME/.claude/settings.json" '"gin@skills-dir": true'
assert_not_contains "$MOCK_HOME/.claude/settings.json" 'gin-workflow@skills-dir'
# The install name is the plugin id from plugin.meta.json, not the plugin directory.
assert_contains "plugins/gin-workflow/plugin.meta.json" '"name": "gin"'
assert_exists "$MOCK_HOME/.local/lib/gin/3.0/gin"
assert_exists "$MOCK_HOME/.local/lib/gin/3.0/workflow_core/cli.py"
assert_exists "$MOCK_HOME/.local/lib/gin/3.0/.gin-workflow-src.json"
assert_exists "$MOCK_HOME/.local/bin/gin"
launcher_version="$(HOME="$MOCK_HOME" "$MOCK_HOME/.local/bin/gin" --version)"
if [ "$launcher_version" != "gin 3.0" ]; then
  echo "Unexpected launcher version: $launcher_version" >&2
  exit 1
fi
assert_exists "$MOCK_HOME/.local/lib/gin/3.0/rules/core.md"
# PATH registration: once per rc file, chosen by $SHELL, removed on --uninstall, skipped with --no-modify-path.
path_home="$(mktemp -d)"
HOME="$path_home" SHELL=/bin/zsh PATH="/usr/bin:/bin" ./install.sh --platform opencode >/dev/null
HOME="$path_home" SHELL=/bin/zsh PATH="/usr/bin:/bin" ./install.sh --platform opencode >/dev/null
assert_contains "$path_home/.zshrc" '# gin-workflow PATH'
if [ "$(grep -c '# gin-workflow PATH' "$path_home/.zshrc")" != "1" ]; then echo "PATH block written more than once" >&2; exit 1; fi
assert_contains "$path_home/.zshrc" 'export PATH="$HOME/.local/bin:$PATH"'
HOME="$path_home" SHELL=/bin/zsh PATH="/usr/bin:/bin" ./install.sh --uninstall >/dev/null
assert_not_contains "$path_home/.zshrc" '# gin-workflow PATH'
HOME="$path_home" SHELL=/bin/bash PATH="/usr/bin:/bin" ./install.sh --platform opencode --no-modify-path >"$output_file" 2>&1
assert_not_exists "$path_home/.bashrc"
assert_contains "$output_file" 'export PATH="$HOME/.local/bin:$PATH"'
HOME="$path_home" SHELL=/bin/bash PATH="/usr/bin:/bin" ./install.sh --platform opencode --dry-run >"$output_file"
assert_contains "$output_file" "(dry-run) would add $path_home/.local/bin to PATH in $path_home/.bashrc"
rm -rf "$path_home"
rules_list="$(HOME="$MOCK_HOME" "$MOCK_HOME/.local/bin/gin" rules --list --repository "$MOCK_HOME")"
case "$rules_list" in
  *"core (plugin, core)"*) ;;
  *) echo "Installed launcher did not list the core rule pack: $rules_list" >&2; exit 1 ;;
esac
assert_exists "$MOCK_HOME/.local/lib/gin/3.0/templates/spec-delta.md"
assert_exists "$MOCK_HOME/.local/lib/gin/3.0/templates/team/commit-msg"
assert_exists "$MOCK_HOME/.claude/skills/gin/templates/proposal.md"
HOME="$MOCK_HOME" "$MOCK_HOME/.local/bin/gin" specs --help >/dev/null
HOME="$MOCK_HOME" "$MOCK_HOME/.local/bin/gin" setup models --provider claude >/dev/null
assert_not_exists "$MOCK_HOME/.claude/skills/gin-qa"
assert_not_exists "$MOCK_HOME/.local/bin/gin-qa"

# Global OpenCode install writes into the harness skills directory without
# needing the `opencode` CLI on PATH.
HOME="$MOCK_HOME" ./install.sh --platform opencode >/dev/null
assert_exists "$MOCK_HOME/.config/opencode/skills/gin/skills/setup/SKILL.md"
assert_exists "$MOCK_HOME/.config/opencode/skills/gin/skills/tech-doc/SKILL.md"
# OpenCode selects a skill by its bare directory id, so gin's generic names get a gin- prefix.
for skill in learn sdd team worktrees debugging review-response parallel-agents report; do
  assert_contains "$MOCK_HOME/.config/opencode/skills/gin/skills/gin-$skill/SKILL.md" "name: gin-$skill"
  assert_not_exists "$MOCK_HOME/.config/opencode/skills/gin/skills/$skill"
done
assert_exists "$MOCK_HOME/.config/opencode/skills/gin/agents/gin-developer.md"
assert_exists "$MOCK_HOME/.config/opencode/agents/gin-developer.md"
assert_exists "$MOCK_HOME/.config/opencode/skills/gin/references/stage-contract.md"
assert_not_exists "$MOCK_HOME/.config/opencode/skills/gin/hooks/hooks.json"

# --link installs by symlink; preparing the bundle must never rewrite source.
opencode_link_home="$MOCK_HOME/opencode-link-home"
mkdir -p "$opencode_link_home"
HOME="$opencode_link_home" ./install.sh --platform opencode --link >/dev/null
assert_exists "$opencode_link_home/.config/opencode/skills/gin/skills/setup/SKILL.md"
assert_exists "$opencode_link_home/.config/opencode/skills/gin/skills/gin-report/SKILL.md"

# Project-level OpenCode install writes into the repository without touching the
# repository's own .opencode/agents or .opencode/commands files.
opencode_project="$MOCK_HOME/opencode-project"
mkdir -p "$opencode_project/.opencode/agents" "$opencode_project/.opencode/commands"
printf '%s\n' '# user agent' > "$opencode_project/.opencode/agents/user-agent.md"
printf '%s\n' '# user command' > "$opencode_project/.opencode/commands/user-command.md"
# A 2.x project install left skills and agents under the old names; only the selected platform's are removed.
mkdir -p "$opencode_project/.opencode/skills/gin-knowledge" "$opencode_project/.opencode/skills/gin-workflow-report" "$opencode_project/.claude/skills/gin-sdd"
touch "$opencode_project/.opencode/agents/gin-workflow-developer.md"
HOME="$MOCK_HOME" ./install.sh --platform opencode --project "$opencode_project" >/dev/null
assert_not_exists "$opencode_project/.opencode/skills/gin-knowledge"
assert_not_exists "$opencode_project/.opencode/skills/gin-workflow-report"
assert_not_exists "$opencode_project/.opencode/agents/gin-workflow-developer.md"
assert_exists "$opencode_project/.claude/skills/gin-sdd"
assert_exists "$opencode_project/.opencode/skills/setup/SKILL.md"
assert_exists "$opencode_project/.opencode/skills/gin-report/SKILL.md"
assert_exists "$opencode_project/.opencode/skills/gin-learn/SKILL.md"
assert_not_exists "$opencode_project/.opencode/skills/report"
assert_exists "$opencode_project/.opencode/agents/user-agent.md"
assert_exists "$opencode_project/.opencode/agents/gin-developer.md"
assert_exists "$opencode_project/.opencode/commands/user-command.md"
assert_exists "$opencode_project/.opencode/references/stage-contract.md"
assert_contains "$opencode_project/.opencode/skills/gin-report/SKILL.md" "name: gin-report"

HOME="$MOCK_HOME" ./install.sh --platform claude --plugin gin-qa >"$output_file" 2>&1
assert_not_contains "$output_file" "gin is not installed"
assert_exists "$MOCK_HOME/.claude/skills/gin-qa/skills/cases/SKILL.md"
assert_exists "$MOCK_HOME/.claude/skills/gin-qa/skills/e2e/SKILL.md"
assert_exists "$MOCK_HOME/.claude/skills/gin-qa/skills/tests/SKILL.md"
assert_exists "$MOCK_HOME/.claude/skills/gin-qa/skills/e2e/references/explore-case.md"
assert_exists "$MOCK_HOME/.local/lib/gin-qa/0.10/templates/evidence.ts"
assert_exists "$MOCK_HOME/.local/lib/gin-qa/0.10/templates/playwright.config.ts"
assert_exists "$MOCK_HOME/.local/lib/gin-qa/0.10/templates/qa-readme.md"
assert_exists "$MOCK_HOME/.local/lib/gin-qa/0.10/templates/report.html"
assert_contains "$MOCK_HOME/.claude/settings.json" '"gin-qa@skills-dir": true'
qa_version="$(HOME="$MOCK_HOME" "$MOCK_HOME/.local/bin/gin-qa" --version)"
if [ "$qa_version" != "gin-qa 0.10" ]; then
  echo "Unexpected gin-qa launcher version: $qa_version" >&2
  exit 1
fi

# gin-workflow is already installed in MOCK_HOME, so gin-orchestrator installs alone.
HOME="$MOCK_HOME" ./install.sh --platform claude --plugin gin-orchestrator >"$output_file" 2>&1
assert_not_contains "$output_file" "installing it first"
assert_exists "$MOCK_HOME/.claude/skills/gin-orchestrator/skills/providers/SKILL.md"
assert_contains "$MOCK_HOME/.claude/settings.json" '"gin-orchestrator@skills-dir": true'
assert_exists "$MOCK_HOME/.local/lib/gin-orchestrator/0.1/gin_orchestrator/cli.py"
assert_not_exists "$MOCK_HOME/.local/lib/gin-orchestrator/0.1/templates"
assert_not_exists "$MOCK_HOME/.local/lib/gin-orchestrator/0.1/worktree-create.sh"
orch_version="$(HOME="$MOCK_HOME" PATH="$MOCK_HOME/.local/bin:$PATH" "$MOCK_HOME/.local/bin/gin-orchestrator" version --json)"
case "$orch_version" in
  *'"contract": 2'*) ;;
  *) echo "Unexpected gin-orchestrator version: $orch_version" >&2; exit 1 ;;
esac

# A HOME without gin-workflow gets it first.
orch_home="$MOCK_HOME/orchestrator-home"
mkdir -p "$orch_home"
HOME="$orch_home" ./install.sh --platform claude --plugin gin-orchestrator >"$output_file" 2>&1
assert_contains "$output_file" "gin-orchestrator requires gin 3.0; installing it first."
assert_exists "$orch_home/.local/lib/gin/3.0/workflow_core/cli.py"
assert_exists "$orch_home/.local/bin/gin-orchestrator"

# Success path with the installed launchers: write cases, edit a requirement, re-pin.
QA_REPO="$MOCK_HOME/qa-repo"
mkdir -p "$QA_REPO/.agent-workflow" "$QA_REPO/docs/specs/auth" "$QA_REPO/qa/cases"
git -C "$QA_REPO" init -q
printf '%s\n' "schema_version: '2.7'" 'artifacts:' '  layout: sdd' > "$QA_REPO/.agent-workflow/config.yaml"
cat > "$QA_REPO/docs/specs/auth/spec.md" <<'SPEC'
# Auth

## Requirements

### REQ-AUTH-001: Sign in
The system SHALL sign a user in with a valid password.

#### Scenario: valid password
- GIVEN a registered user
- WHEN they submit the right password
- THEN they are signed in
SPEC
qa_cli() { HOME="$MOCK_HOME" PATH="$MOCK_HOME/.local/bin:$PATH" "$MOCK_HOME/.local/bin/gin-qa" cases "$@" --repository "$QA_REPO"; }
pinned="$(qa_cli plan auth --format json | python3 -c 'import json,sys; print(json.load(sys.stdin)["missing"][0]["hash8"])')"
cat > "$QA_REPO/qa/cases/auth.md" <<CASES
# Test cases: auth

### $(qa_cli next-id auth): Sign in with a valid password
REQ: REQ-AUTH-001@$pinned
Type: e2e

Steps:
1. Open /login
2. Submit the right password

Expected:
- The user is signed in
CASES
qa_cli check >/dev/null
sed -i.bak 's/valid password\./valid password and a code./' "$QA_REPO/docs/specs/auth/spec.md"
if qa_cli check >"$output_file"; then
  echo "Expected gin-qa check to report a stale case" >&2
  exit 1
fi
assert_contains "$output_file" "TC-AUTH-001: REQ-AUTH-001 changed"
qa_cli pin TC-AUTH-001 >/dev/null
qa_cli check >/dev/null

# The installed launcher finds its fixture template and plans the e2e case.
qa_e2e() { HOME="$MOCK_HOME" PATH="$MOCK_HOME/.local/bin:$PATH" "$MOCK_HOME/.local/bin/gin-qa" e2e "$@" --repository "$QA_REPO"; }
qa_e2e init >/dev/null
assert_exists "$QA_REPO/qa/e2e/evidence.ts"
assert_contains "$QA_REPO/playwright.config.ts" "testDir: 'qa/e2e'"
assert_contains "$QA_REPO/.gitignore" "/qa/evidence/"
qa_e2e plan auth >"$output_file"
assert_contains "$output_file" "missing TC-AUTH-001 qa/e2e/auth/tc-auth-001.spec.ts"

for plugin in gin-workflow gin-qa gin-orchestrator; do
  case "$plugin" in
    gin-workflow) launcher=gin; old_version=2.1; current_version=3.0 ;;
    gin-qa) launcher=gin-qa; old_version=0.4; current_version=0.10 ;;
    gin-orchestrator) launcher=gin-orchestrator; old_version=0.0; current_version=0.1 ;;
  esac

  UPGRADE_HOME="$MOCK_HOME/upgrade-home-$launcher"
  mkdir -p "$UPGRADE_HOME/.local/lib/$launcher/$old_version" "$UPGRADE_HOME/.local/bin"
  printf '%s\n' '#!/usr/bin/env python3' > "$UPGRADE_HOME/.local/lib/$launcher/$old_version/$launcher"
  ln -s "$UPGRADE_HOME/.local/lib/$launcher/$old_version/$launcher" "$UPGRADE_HOME/.local/bin/$launcher"

  HOME="$UPGRADE_HOME" ./install.sh --platform claude --plugin "$plugin" >/dev/null

  expected_target="$UPGRADE_HOME/.local/lib/$launcher/$current_version/$launcher"
  actual_target="$(readlink "$UPGRADE_HOME/.local/bin/$launcher")"
  if [ "$actual_target" != "$expected_target" ]; then
    echo "Expected managed launcher upgrade to target $expected_target, got $actual_target" >&2
    exit 1
  fi

  FOREIGN_LINK_HOME="$MOCK_HOME/foreign-link-home-$launcher"
  mkdir -p "$FOREIGN_LINK_HOME/.local/bin"
  foreign_target="$FOREIGN_LINK_HOME/not-$launcher"
  printf '%s\n' 'foreign launcher' > "$foreign_target"
  ln -s "$foreign_target" "$FOREIGN_LINK_HOME/.local/bin/$launcher"
  if HOME="$FOREIGN_LINK_HOME" ./install.sh --platform claude --plugin "$plugin" >"$output_file" 2>&1; then
    echo "Expected foreign launcher link collision to fail installation" >&2
    exit 1
  fi
  assert_contains "$output_file" "refusing to replace a different launcher"
  if [ "$(readlink "$FOREIGN_LINK_HOME/.local/bin/$launcher")" != "$foreign_target" ]; then
    echo "Foreign launcher link was modified" >&2
    exit 1
  fi

  MALFORMED_LINK_HOME="$MOCK_HOME/malformed-link-home-$launcher"
  malformed_target="$MALFORMED_LINK_HOME/.local/lib/$launcher/$old_version/nested/$launcher"
  mkdir -p "$MALFORMED_LINK_HOME/.local/bin" "$(dirname "$malformed_target")"
  printf '%s\n' 'malformed managed launcher' > "$malformed_target"
  ln -s "$malformed_target" "$MALFORMED_LINK_HOME/.local/bin/$launcher"
  if HOME="$MALFORMED_LINK_HOME" ./install.sh --platform claude --plugin "$plugin" >"$output_file" 2>&1; then
    echo "Expected malformed managed launcher link to fail installation" >&2
    exit 1
  fi
  assert_contains "$output_file" "refusing to replace a different launcher"
  if [ "$(readlink "$MALFORMED_LINK_HOME/.local/bin/$launcher")" != "$malformed_target" ]; then
    echo "Malformed managed launcher link was modified" >&2
    exit 1
  fi

  COLLISION_HOME="$MOCK_HOME/collision-home-$launcher"
  mkdir -p "$COLLISION_HOME/.local/bin"
  echo 'different launcher' > "$COLLISION_HOME/.local/bin/$launcher"
  if HOME="$COLLISION_HOME" ./install.sh --platform claude --plugin "$plugin" >"$output_file" 2>&1; then
    echo "Expected launcher collision to fail installation" >&2
    exit 1
  fi
  assert_contains "$output_file" "refusing to replace a different launcher"
  assert_contains "$COLLISION_HOME/.local/bin/$launcher" "different launcher"
done

# Upgrade over a managed 2.9 gin-workflow install: the old launcher and the old
# plugin installs go, one platform at a time, and only after a real run.
legacy_home="$MOCK_HOME/legacy-home"
mkdir -p "$legacy_home/.local/lib/gin-workflow/2.9" "$legacy_home/.local/bin" "$legacy_home/.claude/skills/gin-workflow" \
  "$legacy_home/.config/opencode/skills/gin-workflow" "$legacy_home/.config/opencode/agents"
printf '%s\n' '#!/usr/bin/env python3' > "$legacy_home/.local/lib/gin-workflow/2.9/gin-workflow"
ln -s "$legacy_home/.local/lib/gin-workflow/2.9/gin-workflow" "$legacy_home/.local/bin/gin-workflow"
echo '{"enabledPlugins": {"gin-workflow@skills-dir": true}}' > "$legacy_home/.claude/settings.json"
touch "$legacy_home/.config/opencode/agents/gin-workflow-developer.md" "$legacy_home/.config/opencode/agents/gin-qa-e2e-tester.md" \
  "$legacy_home/.config/opencode/agents/gin-mine.md"
HOME="$legacy_home" ./install.sh --platform claude --dry-run >"$output_file" 2>&1
assert_contains "$output_file" "(dry-run) would remove the gin-workflow launcher at $legacy_home/.local/bin/gin-workflow"
assert_contains "$output_file" "(dry-run) would remove the old gin-workflow plugin installs"
assert_exists "$legacy_home/.local/bin/gin-workflow"
assert_exists "$legacy_home/.local/lib/gin-workflow/2.9/gin-workflow"
assert_exists "$legacy_home/.claude/skills/gin-workflow"
assert_contains "$legacy_home/.claude/settings.json" '"gin-workflow@skills-dir": true'
HOME="$legacy_home" ./install.sh --platform claude >"$output_file" 2>&1
assert_contains "$output_file" "Removed the gin-workflow launcher at $legacy_home/.local/bin/gin-workflow"
if [ -e "$legacy_home/.local/bin/gin-workflow" ] || [ -L "$legacy_home/.local/bin/gin-workflow" ]; then
  echo "Expected the managed gin-workflow launcher to be removed" >&2
  exit 1
fi
assert_not_exists "$legacy_home/.local/lib/gin-workflow"
assert_not_exists "$legacy_home/.claude/skills/gin-workflow"
assert_not_contains "$legacy_home/.claude/settings.json" 'gin-workflow@skills-dir'
assert_contains "$legacy_home/.claude/settings.json" '"gin@skills-dir": true'
assert_exists "$legacy_home/.claude/skills/gin/skills/learn/SKILL.md"
assert_exists "$legacy_home/.config/opencode/skills/gin-workflow"
legacy_version="$(HOME="$legacy_home" "$legacy_home/.local/bin/gin" --version)"
if [ "$legacy_version" != "gin 3.0" ]; then
  echo "Unexpected launcher version after the upgrade: $legacy_version" >&2
  exit 1
fi
HOME="$legacy_home" ./install.sh --platform opencode >/dev/null
assert_not_exists "$legacy_home/.config/opencode/skills/gin-workflow"
assert_not_exists "$legacy_home/.config/opencode/agents/gin-workflow-developer.md"
assert_exists "$legacy_home/.config/opencode/agents/gin-developer.md"
assert_exists "$legacy_home/.config/opencode/agents/gin-qa-e2e-tester.md"
assert_exists "$legacy_home/.config/opencode/agents/gin-mine.md"

# A gin-workflow file the installer does not manage is kept and reported.
foreign_legacy_home="$MOCK_HOME/foreign-legacy-home"
mkdir -p "$foreign_legacy_home/.local/bin" "$foreign_legacy_home/.local/lib/gin-workflow/2.9"
echo 'my own gin-workflow' > "$foreign_legacy_home/.local/bin/gin-workflow"
HOME="$foreign_legacy_home" ./install.sh --platform claude >"$output_file" 2>&1
assert_contains "$output_file" "kept $foreign_legacy_home/.local/bin/gin-workflow: not a gin-workflow launcher this installer manages"
assert_contains "$foreign_legacy_home/.local/bin/gin-workflow" "my own gin-workflow"
assert_exists "$foreign_legacy_home/.local/lib/gin-workflow/2.9"
assert_exists "$foreign_legacy_home/.local/bin/gin"

# Uninstall removes the generated dist output, the managed launcher, and the
# OpenCode global install under both the new and the old name.
uninstall_home="$MOCK_HOME/uninstall-home"
mkdir -p "$uninstall_home"
HOME="$uninstall_home" ./install.sh --platform opencode >/dev/null
assert_exists "$uninstall_home/.config/opencode/skills/gin/skills/setup/SKILL.md"
assert_exists "$uninstall_home/.config/opencode/agents/gin-developer.md"
mkdir -p "$uninstall_home/.config/opencode/skills/gin-workflow"
touch "$uninstall_home/.config/opencode/agents/gin-workflow-developer.md" "$uninstall_home/.config/opencode/agents/gin-mine.md"
echo 'my own gin-workflow' > "$uninstall_home/.local/bin/gin-workflow"
HOME="$uninstall_home" ./install.sh --uninstall >"$output_file" 2>&1
assert_not_exists "$uninstall_home/.config/opencode/skills/gin"
assert_not_exists "$uninstall_home/.config/opencode/agents/gin-developer.md"
assert_not_exists "$uninstall_home/.config/opencode/skills/gin-workflow"
assert_not_exists "$uninstall_home/.config/opencode/agents/gin-workflow-developer.md"
assert_exists "$uninstall_home/.config/opencode/agents/gin-mine.md"
assert_not_exists "$uninstall_home/.local/bin/gin"
assert_not_exists "$uninstall_home/.local/lib/gin"
assert_contains "$uninstall_home/.local/bin/gin-workflow" "my own gin-workflow"
assert_contains "$output_file" "kept $uninstall_home/.local/bin/gin-workflow: not a gin-workflow launcher this installer manages"


# Copilot: registration through a stub CLI, re-install, skip without the CLI,
# project warning, and uninstall.
copilot_home="$MOCK_HOME/copilot-home"
copilot_bin="$MOCK_HOME/copilot-bin"
copilot_log="$MOCK_HOME/copilot.log"
mkdir -p "$copilot_home" "$copilot_bin"
cat > "$copilot_bin/copilot" <<'EOF'
#!/bin/sh
printf '%s\n' "$*" >> "$COPILOT_LOG"
EOF
chmod +x "$copilot_bin/copilot"

HOME="$copilot_home" PATH="$copilot_bin:$PATH" COPILOT_LOG="$copilot_log" ./install.sh --platform copilot >"$output_file"
assert_line "$copilot_log" "plugin uninstall gin-workflow"
assert_line "$copilot_log" "plugin uninstall gin"
assert_contains "$copilot_log" "plugin install $ROOT_DIR/plugins/gin-workflow/dist/copilot/gin"
assert_contains "$output_file" "Registering gin with Copilot..."
assert_exists "$copilot_home/.local/bin/gin"

# Copilot names a direct install after the source directory, so each plugin
# needs its own bundle directory name or one install overwrites the other.
: > "$copilot_log"
HOME="$copilot_home" PATH="$copilot_bin:$PATH" COPILOT_LOG="$copilot_log" ./install.sh --platform copilot --plugin all >/dev/null
assert_contains "$copilot_log" "plugin install $ROOT_DIR/plugins/gin-workflow/dist/copilot/gin"
assert_contains "$copilot_log" "plugin install $ROOT_DIR/plugins/gin-qa/dist/copilot/gin-qa"

if ! command -v copilot >/dev/null 2>&1; then
  HOME="$copilot_home" ./install.sh --platform copilot >"$output_file"
  assert_contains "$output_file" "Copilot CLI not found; skipped registration. Run: copilot plugin install $ROOT_DIR/plugins/gin-workflow/dist/copilot/gin"
fi

copilot_project="$MOCK_HOME/copilot-project"
mkdir -p "$copilot_project"
HOME="$copilot_home" ./install.sh --platform copilot --project "$copilot_project" >"$output_file" 2>&1
assert_contains "$output_file" "Warning: Copilot plugins are global; --project skips copilot."

: > "$copilot_log"
HOME="$copilot_home" PATH="$copilot_bin:$PATH" COPILOT_LOG="$copilot_log" ./install.sh --uninstall >/dev/null
assert_line "$copilot_log" "plugin uninstall gin"
assert_line "$copilot_log" "plugin uninstall gin-workflow"
assert_not_exists "plugins/gin-workflow/dist/copilot"

rmdir "$TEST_HOME"
