---
name: orchestrate
description: Convert one approved plan into provider-backed durable execution state.
---

# Orchestrate Skill

Perform exactly one orchestration stage.

## Required inputs

- resolved `EffectiveConfig`
- `ArtifactRegistry`
- `ContextManifest(stage="orchestrate")`
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

1. Require evidence that `plan_approved` is true and resolve the plan through the artifact registry.
2. Reject implementation or review tracks that omit provider role or reasoning guidance.
3. Build the complete set of `AssignmentRequest` values and call `resolve_all_assignments(requests, config, local)` before any manifest write or task-tracking capability call. If any route is unresolved, report every diagnostic and stop without durable mutation.
4. Only after the full batch resolves, persist every runtime-only preview with `write_assignment_manifest`. Concrete provider/model aliases never enter Beads or the portable plan.
5. Apply the `bead-orchestrator` methodology using only the task-tracking capability for durable identity, dependency, readiness, ownership, and status.
6. Use the workspace capability for isolation metadata; it is never authoritative task state.
7. Send isolation disablement or current-branch execution through the approval manager and evidence manager before any workspace call.
8. Keep plan tracks and validation intent required. Leave symbols, tests, and project knowledge discoverable on demand through the context manifest.
9. Return `orchestration_ready` state without invoking execution.

Use the resolved effective configuration as the sole lifecycle configuration input. Read [state ownership](../../references/orchestration-state-model.md) and [provider contracts](../../references/capability-provider-contracts.md); lifecycle guidance does not reproduce provider command syntax.
