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

assert_workflow_v22_layout() {
  local root="$1"
  local relative
  local required=(
    "commands/setup.md"
    "commands/workflow.md"
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
    "skills/verify/SKILL.md"
    "skills/ship/SKILL.md"
    "skills/review/SKILL.md"
    "references/setup-system.md"
    "references/capability-provider-contracts.md"
    "references/context-and-evidence-policy.md"
    "references/stage-contract.md"
    "scripts/gin-workflow"
    "scripts/workflow_core/configuration.py"
    "scripts/workflow_core/setup_service.py"
    "scripts/workflow_core/router.py"
    "scripts/workflow_core/worker_scheduler.py"
    "scripts/workflow_core/provider_config.py"
    "scripts/workflow_core/assignments.py"
    "scripts/workflow_core/review_coordinator.py"
    "scripts/workflow_providers/__init__.py"
    "scripts/workflow_providers/contracts.py"
    "scripts/workflow_providers/registry.py"
    "scripts/workflow_providers/task_tracking.py"
    "scripts/workflow_providers/knowledge.py"
    "scripts/workflow_providers/workspace.py"
    "scripts/workflow_providers/review.py"
    "scripts/workflow_providers/evidence.py"
    "scripts/workflow_providers/notifications.py"
    "scripts/workflow_providers/fakes.py"
    "scripts/workflow_providers/worker_dispatch.py"
    "scripts/workflow_providers/claude_worker.py"
    "scripts/workflow_providers/codex_worker.py"
    "scripts/workflow_providers/antigravity_worker.py"
    "scripts/workflow_providers/sequential_worker.py"
    "scripts/workflow_providers/circuit_breaker.py"
    "scripts/workflow_providers/native_cli.py"
    "scripts/workflow_providers/routed_worker.py"
    "examples/config.full.yaml"
    "examples/providers.local.example.yaml"
  )
  for relative in "${required[@]}"; do
    assert_exists "$root/$relative"
  done
}

rm -rf plugins/gin-workflow/dist
rm -rf plugins/gin-workflow-advanced/dist

output_file="$(mktemp)"
trap 'rm -f "$output_file"' EXIT

./install.sh --platform claude --dry-run >"$output_file"

assert_contains "$output_file" "Processing plugin: gin-workflow"
assert_not_contains "$output_file" "gin-workflow-advanced"
assert_contains "$output_file" "would install global Claude Code plugin to"
assert_contains "$output_file" "would install gin-workflow launcher version 2.3 to"
assert_contains "$output_file" "would link gin-workflow launcher on PATH at"

assert_exists "plugins/gin-workflow/dist/claude-code/commands/tech-doc.md"
assert_exists "plugins/gin-workflow/dist/claude-code/agents/solution-architect.md"
assert_exists "plugins/gin-workflow/dist/claude-code/agents/full-stack-developer.md"
assert_exists "plugins/gin-workflow/dist/claude-code/agents/qa-agent.md"
assert_exists "plugins/gin-workflow/dist/claude-code/agents/docs-writer.md"
assert_exists "plugins/gin-workflow/dist/claude-code/agents/bead-worker.md"
assert_exists "plugins/gin-workflow/dist/claude-code/skills/gin-debugging/SKILL.md"
assert_exists "plugins/gin-workflow/dist/claude-code/skills/gin-debugging/find-polluter.sh"
assert_exists "plugins/gin-workflow/dist/claude-code/skills/gin-review-response/SKILL.md"
assert_exists "plugins/gin-workflow/dist/claude-code/skills/gin-worktrees/SKILL.md"
assert_exists "plugins/gin-workflow/dist/claude-code/skills/gin-parallel-agents/SKILL.md"
assert_exists "plugins/gin-workflow/dist/claude-code/skills/gin-knowledge/SKILL.md"
assert_exists "plugins/gin-workflow/dist/claude-code/skills/review/SKILL.md"
assert_exists "plugins/gin-workflow/dist/claude-code/commands/review.md"
assert_exists "plugins/gin-workflow/dist/claude-code/references/verification-and-handoff-workflow.md"
assert_exists "plugins/gin-workflow/dist/claude-code/references/orchestration-state-model.md"
assert_exists "plugins/gin-workflow/dist/claude-code/scripts/gin-workflow"
assert_workflow_v22_layout "plugins/gin-workflow/dist/claude-code"

assert_not_exists "plugins/gin-workflow/dist/claude-code/commands/quick.md"
assert_not_exists "plugins/gin-workflow/dist/claude-code/commands/new-project.md"
assert_not_exists "plugins/gin-workflow/dist/claude-code/commands/map-codebase.md"
assert_not_exists "plugins/gin-workflow-advanced"

assert_contains "plugins/gin-workflow/dist/claude-code/commands/plan.md" "durable, git-tracked plan"
for skill_file in plugins/gin-workflow/dist/claude-code/skills/*/SKILL.md; do
  assert_not_contains "$skill_file" 'superpowers'
done

assert_contains 'plugins/gin-workflow/dist/claude-code/skills/verify/SKILL.md' 'Follow references/stage-contract.md.'
assert_contains 'plugins/gin-workflow/dist/claude-code/commands/verify.md' 'Use the `verify` skill.'
assert_contains 'plugins/gin-workflow/dist/claude-code/commands/orchestrate.md' 'Use the `orchestrate` skill.'
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
assert_exists "plugins/gin-workflow/dist/codex/skills/review/SKILL.md"
assert_exists "plugins/gin-workflow/dist/codex/commands/review.md"
assert_contains "plugins/gin-workflow/dist/codex/.codex-plugin/plugin.json" "\"name\": \"gin-workflow\""
assert_contains "plugins/gin-workflow/dist/codex/hooks/hooks.json" "\"description\""
assert_contains "plugins/gin-workflow/dist/codex/hooks/hooks.json" "\"hooks\": {"
assert_contains "plugins/gin-workflow/dist/codex/hooks/hooks.json" "\"PreToolUse\""
assert_codex_hooks_schema "plugins/gin-workflow/dist/codex/hooks/hooks.json"
assert_contains 'plugins/gin-workflow/dist/codex/skills/verify/SKILL.md' 'Follow references/stage-contract.md.'
assert_contains 'plugins/gin-workflow/dist/codex/commands/orchestrate.md' 'Use the `orchestrate` skill.'
assert_contains "plugins/gin-workflow/dist/codex/skills/tech-doc/SKILL.md" "single combined document"
assert_contains "plugins/gin-workflow/dist/codex/skills/tech-doc/SKILL.md" "ARCHITECTURE.md"
assert_contains "plugins/gin-workflow/dist/codex/skills/tech-doc/SKILL.md" "codegraph"
assert_workflow_v22_layout "plugins/gin-workflow/dist/codex"
assert_contains ".claude-plugin/marketplace.json" "\"path\": \"plugins/gin-workflow/src\""
assert_not_contains ".claude-plugin/marketplace.json" "gin-workflow-advanced"

./install.sh --platform antigravity --dry-run >"$output_file"

assert_exists "plugins/gin-workflow/dist/antigravity/plugin.json"
assert_exists "plugins/gin-workflow/dist/antigravity/hooks/hooks.json"
assert_workflow_v22_layout "plugins/gin-workflow/dist/antigravity"

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
assert_exists "$MOCK_HOME/.local/lib/gin-workflow/2.3/gin-workflow"
assert_exists "$MOCK_HOME/.local/lib/gin-workflow/2.3/workflow_core/cli.py"
assert_exists "$MOCK_HOME/.local/bin/gin-workflow"
launcher_version="$(HOME="$MOCK_HOME" "$MOCK_HOME/.local/bin/gin-workflow" --version)"
if [ "$launcher_version" != "gin-workflow 2.3" ]; then
  echo "Unexpected launcher version: $launcher_version" >&2
  exit 1
fi

UPGRADE_HOME="$MOCK_HOME/upgrade-home"
mkdir -p "$UPGRADE_HOME/.local/lib/gin-workflow/2.1" "$UPGRADE_HOME/.local/bin"
printf '%s\n' '#!/usr/bin/env python3' > "$UPGRADE_HOME/.local/lib/gin-workflow/2.1/gin-workflow"
ln -s "$UPGRADE_HOME/.local/lib/gin-workflow/2.1/gin-workflow" "$UPGRADE_HOME/.local/bin/gin-workflow"

HOME="$UPGRADE_HOME" ./install.sh --platform claude >/dev/null

expected_target="$UPGRADE_HOME/.local/lib/gin-workflow/2.3/gin-workflow"
actual_target="$(readlink "$UPGRADE_HOME/.local/bin/gin-workflow")"
if [ "$actual_target" != "$expected_target" ]; then
  echo "Expected managed launcher upgrade to target $expected_target, got $actual_target" >&2
  exit 1
fi

FOREIGN_LINK_HOME="$MOCK_HOME/foreign-link-home"
mkdir -p "$FOREIGN_LINK_HOME/.local/bin"
foreign_target="$FOREIGN_LINK_HOME/not-gin-workflow"
printf '%s\n' 'foreign launcher' > "$foreign_target"
ln -s "$foreign_target" "$FOREIGN_LINK_HOME/.local/bin/gin-workflow"
if HOME="$FOREIGN_LINK_HOME" ./install.sh --platform claude >"$output_file" 2>&1; then
  echo "Expected foreign launcher link collision to fail installation" >&2
  exit 1
fi
assert_contains "$output_file" "refusing to replace a different launcher"
if [ "$(readlink "$FOREIGN_LINK_HOME/.local/bin/gin-workflow")" != "$foreign_target" ]; then
  echo "Foreign launcher link was modified" >&2
  exit 1
fi

MALFORMED_LINK_HOME="$MOCK_HOME/malformed-link-home"
malformed_target="$MALFORMED_LINK_HOME/.local/lib/gin-workflow/2.1/nested/gin-workflow"
mkdir -p "$MALFORMED_LINK_HOME/.local/bin" "$(dirname "$malformed_target")"
printf '%s\n' 'malformed managed launcher' > "$malformed_target"
ln -s "$malformed_target" "$MALFORMED_LINK_HOME/.local/bin/gin-workflow"
if HOME="$MALFORMED_LINK_HOME" ./install.sh --platform claude >"$output_file" 2>&1; then
  echo "Expected malformed managed launcher link to fail installation" >&2
  exit 1
fi
assert_contains "$output_file" "refusing to replace a different launcher"
if [ "$(readlink "$MALFORMED_LINK_HOME/.local/bin/gin-workflow")" != "$malformed_target" ]; then
  echo "Malformed managed launcher link was modified" >&2
  exit 1
fi

COLLISION_HOME="$(mktemp -d)"
trap 'rm -rf "$MOCK_HOME" "$COLLISION_HOME"; rm -f "$output_file"' EXIT
mkdir -p "$COLLISION_HOME/.local/bin"
echo 'different launcher' > "$COLLISION_HOME/.local/bin/gin-workflow"
if HOME="$COLLISION_HOME" ./install.sh --platform claude >"$output_file" 2>&1; then
  echo "Expected launcher collision to fail installation" >&2
  exit 1
fi
assert_contains "$output_file" "refusing to replace a different launcher"
assert_contains "$COLLISION_HOME/.local/bin/gin-workflow" "different launcher"
rmdir "$TEST_HOME"
