#!/bin/bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

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

for event_name in ("PreToolUse", "PostToolUse"):
    if event_name not in hooks:
        raise SystemExit(f"missing hooks.{event_name}")
PYEOF
}

rm -rf plugins/gin-workflow/dist
rm -rf plugins/gin-workflow-advanced/dist

output_file="$(mktemp)"
trap 'rm -f "$output_file"' EXIT

./install.sh --platform claude --dry-run >"$output_file"

assert_contains "$output_file" "Processing plugin: gin-workflow"
assert_not_contains "$output_file" "gin-workflow-advanced"
assert_contains "$output_file" "would install global Claude Code plugin to"

assert_exists "plugins/gin-workflow/dist/claude-code/commands/tech-doc.md"
assert_exists "plugins/gin-workflow/dist/claude-code/agents/solution-architect.md"
assert_exists "plugins/gin-workflow/dist/claude-code/agents/full-stack-developer.md"
assert_exists "plugins/gin-workflow/dist/claude-code/agents/qa-agent.md"
assert_exists "plugins/gin-workflow/dist/claude-code/agents/docs-writer.md"
assert_exists "plugins/gin-workflow/dist/claude-code/agents/bead-worker.md"
assert_exists "plugins/gin-workflow/dist/claude-code/skills/systematic-debugging/SKILL.md"
assert_exists "plugins/gin-workflow/dist/claude-code/skills/requesting-code-review/SKILL.md"
assert_exists "plugins/gin-workflow/dist/claude-code/skills/receiving-code-review/SKILL.md"
assert_exists "plugins/gin-workflow/dist/claude-code/skills/cross-agent-code-review/SKILL.md"
assert_exists "plugins/gin-workflow/dist/claude-code/commands/review.md"
assert_exists "plugins/gin-workflow/dist/claude-code/references/verification-and-handoff-workflow.md"
assert_exists "plugins/gin-workflow/dist/claude-code/references/orchestration-state-model.md"

assert_not_exists "plugins/gin-workflow/dist/claude-code/commands/quick.md"
assert_not_exists "plugins/gin-workflow/dist/claude-code/commands/new-project.md"
assert_not_exists "plugins/gin-workflow/dist/claude-code/commands/map-codebase.md"
assert_not_exists "plugins/gin-workflow-advanced"

assert_contains "plugins/gin-workflow/dist/claude-code/commands/plan.md" "durable, git-tracked plan"
assert_contains 'plugins/gin-workflow/dist/claude-code/skills/writing-plans/SKILL.md' 'extends `superpowers:writing-plans`'
assert_contains 'plugins/gin-workflow/dist/claude-code/skills/executing-plans/SKILL.md' 'extends `superpowers:executing-plans`'
assert_contains 'plugins/gin-workflow/dist/claude-code/skills/verification-before-completion/SKILL.md' 'extends `superpowers:verification-before-completion`'
assert_contains 'plugins/gin-workflow/dist/claude-code/skills/systematic-debugging/SKILL.md' 'extends `superpowers:systematic-debugging`'
assert_contains 'plugins/gin-workflow/dist/claude-code/skills/dispatching-parallel-agents/SKILL.md' 'extends `superpowers:dispatching-parallel-agents`'
assert_contains 'plugins/gin-workflow/dist/claude-code/skills/receiving-code-review/SKILL.md' 'extends `superpowers:receiving-code-review`'
assert_contains 'plugins/gin-workflow/dist/claude-code/skills/requesting-code-review/SKILL.md' 'extends `superpowers:requesting-code-review`'
assert_contains 'plugins/gin-workflow/dist/claude-code/skills/finishing-a-development-branch/SKILL.md' 'extends `superpowers:finishing-a-development-branch`'
assert_contains 'plugins/gin-workflow/dist/claude-code/skills/using-git-worktrees/SKILL.md' 'extends `superpowers:using-git-worktrees`'
assert_contains 'plugins/gin-workflow/dist/claude-code/skills/verification-before-completion/SKILL.md' 'file://../../references/verification-and-handoff-workflow.md'
assert_contains 'plugins/gin-workflow/dist/claude-code/commands/verify.md' 'file://../references/verification-and-handoff-workflow.md'
assert_contains 'plugins/gin-workflow/dist/claude-code/commands/orchestrate.md' 'file://../references/orchestration-state-model.md'
assert_contains "plugins/gin-workflow/dist/claude-code/skills/tech-doc/SKILL.md" "single combined document"
assert_contains "plugins/gin-workflow/dist/claude-code/skills/tech-doc/SKILL.md" "ARCHITECTURE.md"
assert_contains "plugins/gin-workflow/dist/claude-code/skills/tech-doc/SKILL.md" "codegraph"

./install.sh --platform codex --dry-run >"$output_file"

assert_exists "plugins/gin-workflow/dist/codex/.codex-plugin/plugin.json"
assert_exists "plugins/gin-workflow/dist/codex/hooks/hooks.json"
assert_exists "plugins/gin-workflow/dist/codex/agents/solution-architect.md"
assert_exists "plugins/gin-workflow/dist/codex/agents/full-stack-developer.md"
assert_exists "plugins/gin-workflow/dist/codex/agents/qa-agent.md"
assert_exists "plugins/gin-workflow/dist/codex/agents/docs-writer.md"
assert_exists "plugins/gin-workflow/dist/codex/agents/bead-worker.md"
assert_exists "plugins/gin-workflow/dist/codex/references/verification-and-handoff-workflow.md"
assert_exists "plugins/gin-workflow/dist/codex/references/orchestration-state-model.md"
assert_exists "plugins/gin-workflow/dist/codex/skills/cross-agent-code-review/SKILL.md"
assert_exists "plugins/gin-workflow/dist/codex/commands/review.md"
assert_contains "plugins/gin-workflow/dist/codex/.codex-plugin/plugin.json" "\"name\": \"gin-workflow\""
assert_contains "plugins/gin-workflow/dist/codex/hooks/hooks.json" "\"description\""
assert_contains "plugins/gin-workflow/dist/codex/hooks/hooks.json" "\"hooks\": {"
assert_contains "plugins/gin-workflow/dist/codex/hooks/hooks.json" "\"PreToolUse\""
assert_codex_hooks_schema "plugins/gin-workflow/dist/codex/hooks/hooks.json"
assert_contains "plugins/gin-workflow/dist/codex/skills/verification-before-completion/SKILL.md" "file://../../references/verification-and-handoff-workflow.md"
assert_contains "plugins/gin-workflow/dist/codex/commands/orchestrate.md" "file://../references/orchestration-state-model.md"
assert_contains "plugins/gin-workflow/dist/codex/skills/tech-doc/SKILL.md" "single combined document"
assert_contains "plugins/gin-workflow/dist/codex/skills/tech-doc/SKILL.md" "ARCHITECTURE.md"
assert_contains "plugins/gin-workflow/dist/codex/skills/tech-doc/SKILL.md" "codegraph"
assert_contains ".claude-plugin/marketplace.json" "\"path\": \"plugins/gin-workflow/src\""
assert_not_contains ".claude-plugin/marketplace.json" "gin-workflow-advanced"

# Test actual installation with a mocked HOME
echo "Running mock HOME global installation test..."
MOCK_HOME="$(mktemp -d)"
trap 'rm -rf "$MOCK_HOME"; rm -f "$output_file"' EXIT

mkdir -p "$MOCK_HOME/.claude"
echo '{"enabledPlugins": {"gin-workflow@skills-dir": false}}' > "$MOCK_HOME/.claude/settings.json"

HOME="$MOCK_HOME" ./install.sh --platform claude >/dev/null

assert_exists "$MOCK_HOME/.claude/skills/gin-workflow/commands/tech-doc.md"
assert_exists "$MOCK_HOME/.claude/skills/gin-workflow/agents/bead-worker.md"
assert_contains "$MOCK_HOME/.claude/settings.json" '"gin-workflow@skills-dir": true'
