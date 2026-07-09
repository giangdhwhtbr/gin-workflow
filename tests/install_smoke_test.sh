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
  if ! rg -q "$pattern" "$path"; then
    echo "Expected '$path' to contain pattern: $pattern" >&2
    exit 1
  fi
}

assert_not_contains() {
  local path="$1"
  local pattern="$2"
  if rg -q "$pattern" "$path"; then
    echo "Expected '$path' to not contain pattern: $pattern" >&2
    exit 1
  fi
}

rm -rf plugins/gin-workflow/dist
rm -rf plugins/gin-workflow-advanced/dist

output_file="$(mktemp)"
trap 'rm -f "$output_file"' EXIT

./install.sh --platform claude --dry-run >"$output_file"

assert_contains "$output_file" "Processing plugin: gin-workflow"
assert_not_contains "$output_file" "gin-workflow-advanced"

assert_exists "plugins/gin-workflow/dist/claude-code/commands/tech-doc.md"
assert_exists "plugins/gin-workflow/dist/claude-code/skills/systematic-debugging/SKILL.md"
assert_exists "plugins/gin-workflow/dist/claude-code/skills/requesting-code-review/SKILL.md"
assert_exists "plugins/gin-workflow/dist/claude-code/skills/receiving-code-review/SKILL.md"

assert_not_exists "plugins/gin-workflow/dist/claude-code/commands/quick.md"
assert_not_exists "plugins/gin-workflow/dist/claude-code/commands/new-project.md"
assert_not_exists "plugins/gin-workflow/dist/claude-code/commands/map-codebase.md"
assert_not_exists "plugins/gin-workflow-advanced"

assert_contains "plugins/gin-workflow/dist/claude-code/commands/plan.md" "compares implementation approaches"
assert_contains "plugins/gin-workflow/dist/claude-code/skills/writing-plans/SKILL.md" "Propose 2-3 approaches"

./install.sh --platform codex --dry-run >"$output_file"

assert_exists "plugins/gin-workflow/dist/codex/.codex-plugin/plugin.json"
assert_exists "plugins/gin-workflow/dist/codex/hooks/hooks.json"
assert_contains "plugins/gin-workflow/dist/codex/.codex-plugin/plugin.json" "\"name\": \"gin-workflow\""
assert_contains "plugins/gin-workflow/dist/codex/hooks/hooks.json" "\"description\""
assert_contains "plugins/gin-workflow/dist/codex/hooks/hooks.json" "\"hooks\": \{"
assert_contains "plugins/gin-workflow/dist/codex/hooks/hooks.json" "\"PreToolUse\""
assert_contains ".claude-plugin/marketplace.json" "\"path\": \"plugins/gin-workflow/src\""
assert_not_contains ".claude-plugin/marketplace.json" "gin-workflow-advanced"
