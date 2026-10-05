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
rm -rf plugins/gin-qa/dist

output_file="$(mktemp)"
trap 'rm -f "$output_file"' EXIT

# Seed leftovers from an older build; the installer must rebuild dist from scratch.
mkdir -p plugins/gin-workflow/dist/claude-code/commands plugins/gin-workflow/dist/claude-code/skills/writing-plans
touch plugins/gin-workflow/dist/claude-code/commands/stale-from-old-build.md plugins/gin-workflow/dist/claude-code/skills/writing-plans/SKILL.md

./install.sh --platform claude --dry-run >"$output_file"

assert_contains "$output_file" "Processing plugin: gin-workflow"
assert_not_contains "$output_file" "gin-workflow-advanced"
assert_contains "$output_file" "would install global Claude Code plugin to"
assert_contains "$output_file" "would install gin-workflow launcher version 2.7 to"
assert_contains "$output_file" "would link gin-workflow launcher on PATH at"
assert_not_contains "$output_file" "gin-qa"
assert_not_exists "plugins/gin-qa/dist"

assert_exists "plugins/gin-workflow/dist/claude-code/skills/tech-doc/SKILL.md"
assert_exists "plugins/gin-workflow/dist/claude-code/skills/report/SKILL.md"
assert_exists "plugins/gin-workflow/dist/claude-code/agents/solution-architect.md"
assert_exists "plugins/gin-workflow/dist/claude-code/agents/developer.md"
assert_not_exists "plugins/gin-workflow/dist/claude-code/agents/full-stack-developer.md"
assert_not_exists "plugins/gin-workflow/dist/claude-code/agents/codebase-mapper.md"
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
assert_exists "plugins/gin-workflow/dist/claude-code/scripts/gin-workflow"
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

assert_contains 'plugins/gin-workflow/dist/claude-code/skills/verify/SKILL.md' 'Read [references/stage-contract.md](../../references/stage-contract.md) now'
assert_contains 'plugins/gin-workflow/dist/claude-code/skills/orchestrate/SKILL.md' 'Read [references/stage-contract.md](../../references/stage-contract.md) now'
assert_contains "plugins/gin-workflow/dist/claude-code/skills/tech-doc/SKILL.md" "single combined document"
assert_contains "plugins/gin-workflow/dist/claude-code/skills/tech-doc/SKILL.md" "ARCHITECTURE.md"
assert_contains "plugins/gin-workflow/dist/claude-code/skills/tech-doc/SKILL.md" "codegraph"

./install.sh --platform claude --plugin gin-qa --dry-run >"$output_file"

assert_contains "$output_file" "Processing plugin: gin-qa"
assert_not_contains "$output_file" "Processing plugin: gin-workflow"
assert_contains "$output_file" "would install gin-qa launcher version 0.4 to"
assert_exists "plugins/gin-qa/dist/claude-code/.claude-plugin/plugin.json"
assert_exists "plugins/gin-qa/dist/claude-code/skills/cases/SKILL.md"
assert_exists "plugins/gin-qa/dist/claude-code/skills/e2e/SKILL.md"
assert_exists "plugins/gin-qa/dist/claude-code/skills/e2e/references/explore-case.md"
assert_exists "plugins/gin-qa/dist/claude-code/templates/evidence.ts"
assert_exists "plugins/gin-qa/dist/claude-code/templates/guidelines.md"
assert_exists "plugins/gin-qa/dist/claude-code/scripts/gin_qa/cli.py"
assert_contains ".claude-plugin/marketplace.json" "\"path\": \"plugins/gin-qa/src\""

./install.sh --platform codex --dry-run >"$output_file"

assert_exists "plugins/gin-workflow/dist/codex/.codex-plugin/plugin.json"
assert_exists "plugins/gin-workflow/dist/codex/hooks/hooks.json"
assert_exists "plugins/gin-workflow/dist/codex/agents/solution-architect.md"
assert_exists "plugins/gin-workflow/dist/codex/agents/developer.md"
assert_not_exists "plugins/gin-workflow/dist/codex/agents/full-stack-developer.md"
assert_not_exists "plugins/gin-workflow/dist/codex/agents/codebase-mapper.md"
assert_exists "plugins/gin-workflow/dist/codex/agents/qa-agent.md"
assert_exists "plugins/gin-workflow/dist/codex/agents/docs-writer.md"
assert_exists "plugins/gin-workflow/dist/codex/agents/bead-worker.md"
assert_exists "plugins/gin-workflow/dist/codex/skills/review/SKILL.md"
assert_exists "plugins/gin-workflow/dist/codex/skills/report/SKILL.md"
assert_contains "plugins/gin-workflow/dist/codex/.codex-plugin/plugin.json" "\"name\": \"gin-workflow\""
assert_contains "plugins/gin-workflow/dist/codex/hooks/hooks.json" "\"description\""
assert_contains "plugins/gin-workflow/dist/codex/hooks/hooks.json" "\"hooks\": {"
assert_contains "plugins/gin-workflow/dist/codex/hooks/hooks.json" "\"PreToolUse\""
assert_codex_hooks_schema "plugins/gin-workflow/dist/codex/hooks/hooks.json"
assert_contains 'plugins/gin-workflow/dist/codex/skills/verify/SKILL.md' 'Read [references/stage-contract.md](../../references/stage-contract.md) now'
assert_contains 'plugins/gin-workflow/dist/codex/skills/orchestrate/SKILL.md' 'Read [references/stage-contract.md](../../references/stage-contract.md) now'
assert_contains "plugins/gin-workflow/dist/codex/skills/tech-doc/SKILL.md" "single combined document"
assert_contains "plugins/gin-workflow/dist/codex/skills/tech-doc/SKILL.md" "ARCHITECTURE.md"
assert_contains "plugins/gin-workflow/dist/codex/skills/tech-doc/SKILL.md" "codegraph"
assert_workflow_v22_layout "plugins/gin-workflow/dist/codex"
assert_contains ".claude-plugin/marketplace.json" "\"path\": \"plugins/gin-workflow/src\""
assert_not_contains ".claude-plugin/marketplace.json" "gin-workflow-advanced"

./install.sh --platform antigravity --dry-run >"$output_file"

assert_exists "plugins/gin-workflow/dist/antigravity/plugin.json"
assert_exists "plugins/gin-workflow/dist/antigravity/hooks/hooks.json"
assert_exists "plugins/gin-workflow/dist/antigravity/skills/report/SKILL.md"
assert_workflow_v22_layout "plugins/gin-workflow/dist/antigravity"

# Test actual installation with a mocked HOME
echo "Running mock HOME global installation test..."
MOCK_HOME="$(mktemp -d)"
trap 'rm -rf "$MOCK_HOME"; rm -f "$output_file"' EXIT

mkdir -p "$MOCK_HOME/.claude"
echo '{"enabledPlugins": {"gin-workflow@skills-dir": false}}' > "$MOCK_HOME/.claude/settings.json"

HOME="$MOCK_HOME" ./install.sh --platform claude >/dev/null

assert_exists "$MOCK_HOME/.claude/skills/gin-workflow/skills/tech-doc/SKILL.md"
assert_exists "$MOCK_HOME/.claude/skills/gin-workflow/agents/bead-worker.md"
assert_contains "$MOCK_HOME/.claude/settings.json" '"gin-workflow@skills-dir": true'
assert_exists "$MOCK_HOME/.local/lib/gin-workflow/2.7/gin-workflow"
assert_exists "$MOCK_HOME/.local/lib/gin-workflow/2.7/workflow_core/cli.py"
assert_exists "$MOCK_HOME/.local/bin/gin-workflow"
launcher_version="$(HOME="$MOCK_HOME" "$MOCK_HOME/.local/bin/gin-workflow" --version)"
if [ "$launcher_version" != "gin-workflow 2.7" ]; then
  echo "Unexpected launcher version: $launcher_version" >&2
  exit 1
fi
assert_exists "$MOCK_HOME/.local/lib/gin-workflow/2.7/rules/core.md"
rules_list="$(HOME="$MOCK_HOME" "$MOCK_HOME/.local/bin/gin-workflow" rules --list --repository "$MOCK_HOME")"
case "$rules_list" in
  *"core (plugin, core)"*) ;;
  *) echo "Installed launcher did not list the core rule pack: $rules_list" >&2; exit 1 ;;
esac
assert_exists "$MOCK_HOME/.local/lib/gin-workflow/2.7/templates/spec-delta.md"
assert_exists "$MOCK_HOME/.local/lib/gin-workflow/2.7/templates/team/commit-msg"
assert_exists "$MOCK_HOME/.claude/skills/gin-workflow/templates/proposal.md"
HOME="$MOCK_HOME" "$MOCK_HOME/.local/bin/gin-workflow" specs --help >/dev/null
HOME="$MOCK_HOME" "$MOCK_HOME/.local/bin/gin-workflow" setup models --provider claude >/dev/null
assert_not_exists "$MOCK_HOME/.claude/skills/gin-qa"
assert_not_exists "$MOCK_HOME/.local/bin/gin-qa"

HOME="$MOCK_HOME" ./install.sh --platform claude --plugin gin-qa >"$output_file" 2>&1
assert_not_contains "$output_file" "gin-workflow is not installed"
assert_exists "$MOCK_HOME/.claude/skills/gin-qa/skills/cases/SKILL.md"
assert_exists "$MOCK_HOME/.claude/skills/gin-qa/skills/e2e/SKILL.md"
assert_exists "$MOCK_HOME/.claude/skills/gin-qa/skills/e2e/references/explore-case.md"
assert_exists "$MOCK_HOME/.local/lib/gin-qa/0.4/templates/evidence.ts"
assert_contains "$MOCK_HOME/.claude/settings.json" '"gin-qa@skills-dir": true'
qa_version="$(HOME="$MOCK_HOME" "$MOCK_HOME/.local/bin/gin-qa" --version)"
if [ "$qa_version" != "gin-qa 0.4" ]; then
  echo "Unexpected gin-qa launcher version: $qa_version" >&2
  exit 1
fi

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
assert_contains "$QA_REPO/.gitignore" "/qa/evidence/"
qa_e2e plan auth >"$output_file"
assert_contains "$output_file" "missing TC-AUTH-001 qa/e2e/auth/tc-auth-001.spec.ts"

for launcher in gin-workflow gin-qa; do
  case "$launcher" in
    gin-workflow) old_version=2.1; current_version=2.7 ;;
    gin-qa) old_version=0.3; current_version=0.4 ;;
  esac

  UPGRADE_HOME="$MOCK_HOME/upgrade-home-$launcher"
  mkdir -p "$UPGRADE_HOME/.local/lib/$launcher/$old_version" "$UPGRADE_HOME/.local/bin"
  printf '%s\n' '#!/usr/bin/env python3' > "$UPGRADE_HOME/.local/lib/$launcher/$old_version/$launcher"
  ln -s "$UPGRADE_HOME/.local/lib/$launcher/$old_version/$launcher" "$UPGRADE_HOME/.local/bin/$launcher"

  HOME="$UPGRADE_HOME" ./install.sh --platform claude --plugin "$launcher" >/dev/null

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
  if HOME="$FOREIGN_LINK_HOME" ./install.sh --platform claude --plugin "$launcher" >"$output_file" 2>&1; then
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
  if HOME="$MALFORMED_LINK_HOME" ./install.sh --platform claude --plugin "$launcher" >"$output_file" 2>&1; then
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
  if HOME="$COLLISION_HOME" ./install.sh --platform claude --plugin "$launcher" >"$output_file" 2>&1; then
    echo "Expected launcher collision to fail installation" >&2
    exit 1
  fi
  assert_contains "$output_file" "refusing to replace a different launcher"
  assert_contains "$COLLISION_HOME/.local/bin/$launcher" "different launcher"
done
rmdir "$TEST_HOME"
