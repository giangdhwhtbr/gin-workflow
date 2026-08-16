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
`load_effective_config(repository)`. If setup is required, stop and instruct
the user to run `/setup` once. Never run setup or resolve raw configuration
from this lifecycle skill.

## Execution

1. Require evidence that `plan_approved` is true and resolve the plan through the artifact registry.
2. Reject implementation or review tracks that omit provider role or reasoning guidance.
3. Resolve each approved track through `resolve_assignment` and persist its runtime-only preview with `write_assignment_manifest`. Concrete provider/model aliases never enter Beads or the portable plan.
4. Apply the `bead-orchestrator` methodology using only task-tracking capabilities for durable identity, dependency, readiness, ownership, and status.
5. Use the workspace capability for isolation metadata; it is never authoritative task state.
6. Send isolation disablement or current-branch execution through the approval manager and evidence manager before any workspace call.
7. Keep plan tracks and validation intent required. Leave symbols, tests, and project knowledge discoverable on demand through the context manifest.
8. Return `orchestration_ready` state without invoking execution.

Use the resolved effective configuration as the sole lifecycle configuration input. Read [state ownership](../../references/orchestration-state-model.md) and [provider contracts](../../references/capability-provider-contracts.md); lifecycle guidance does not reproduce provider command syntax.
