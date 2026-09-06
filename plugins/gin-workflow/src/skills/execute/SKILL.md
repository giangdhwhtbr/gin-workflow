---
name: execute
description: Execute one approved work unit through configured capabilities.
---

# Execute Skill

Perform exactly one implementation work unit.

## Required inputs

- resolved `EffectiveConfig`
- `ArtifactRegistry`
- `ContextManifest(stage="execute")`
- native-harness `ApprovalDecision`

The caller must obtain `EffectiveConfig` through
`load_effective_config(repository)`. Setup is required ONLY when
`load_effective_config` raises `ConfigValidationError` (i.e.
`.agent-workflow/generated/effective-config.yaml` is missing). An empty
`capabilities: {}` mapping in `EffectiveConfig` is the valid default state where
all capabilities and lifecycle stages are enabled; task tracking is provided by
Beads (`artifacts.beads`) and workers by `routing.roles`. Never treat
`capabilities: {}` as missing configuration. If setup is required, stop and
instruct the user to run `/setup` once. Never run setup or resolve raw
configuration from this lifecycle skill.

## Execution

1. Require `orchestration_ready` evidence and read one ready durable work unit through the task-tracking capability.
2. Apply the `executing-plans` and `bead-worker` methodologies inside the plan-declared scope.
3. Dispatch through the configured worker capability; use workspace, knowledge, and notification capabilities only when enabled.
4. Use the approval manager and evidence manager before isolation disablement, current-branch execution, execution-strategy or scope changes, or production-impacting parallel work.
5. Keep selected scope and validation intent required; discover related symbols, tests, and project knowledge on demand.
6. Record work-unit results and return `implementation_complete` state. Do not invoke verification.
