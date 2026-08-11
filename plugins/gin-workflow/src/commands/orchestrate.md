---
name: orchestrate
description: Convert one approved plan into provider-backed durable execution state.
---

# /orchestrate Command

Route one orchestration action to the `orchestrate` skill. State ownership follows [orchestration-state-model.md](file://../references/orchestration-state-model.md).

## Wrapper boundary

At entry, call `load_effective_config(repository)` and build `ArtifactRegistry` from that generated configuration. If setup is required, stop and instruct the user to run `/setup` once; never run setup or configuration resolution from a lifecycle command. Then create `ContextManifest(stage="orchestrate")` and receive the native-harness `ApprovalDecision`. All durable task operations use the configured task-tracking capability; workspace preparation uses the configured workspace capability.

## Instructions

1. Require an approved plan resolved from the artifact registry.
2. Use the `bead-orchestrator` methodology through task create/read/update capabilities.
3. Mirror plan tracks and dependencies into durable task state and verify readiness through that provider.
4. Use workspace isolation by default. Disabling isolation or selecting current-branch execution requires approval-manager authorization and a durable audit event.
5. Keep required context to plan decomposition and validation intent; related symbols, tests, and project knowledge stay discoverable on demand.
6. Return `orchestration_ready` state. Do not begin execution.
