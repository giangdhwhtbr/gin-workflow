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

## Execution

1. Require evidence that `plan_approved` is true and resolve the plan through the artifact registry.
2. Apply the `bead-orchestrator` methodology using only task-tracking capabilities for durable identity, dependency, readiness, ownership, and status.
3. Use the workspace capability for isolation metadata; it is never authoritative task state.
4. Send isolation disablement or current-branch execution through the approval manager and evidence manager before any workspace call.
5. Keep plan tracks and validation intent required. Leave symbols, tests, and project knowledge discoverable on demand through the context manifest.
6. Return `orchestration_ready` state without invoking execution.

Use the resolved effective configuration as the sole lifecycle configuration input. Read [state ownership](../../references/orchestration-state-model.md) and [provider contracts](../../references/capability-provider-contracts.md); lifecycle guidance does not reproduce provider command syntax.
