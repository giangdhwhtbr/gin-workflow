---
name: bead-orchestrator
description: Convert approved plan tracks into provider-backed durable execution state.
---

# Bead Orchestrator Skill

Coordinate one approved plan without binding lifecycle behavior to a concrete task, workspace, review, or notification adapter.

## Required inputs

- resolved `EffectiveConfig`
- `ArtifactRegistry`
- `ContextManifest(stage="orchestrate")`
- native-harness `ApprovalDecision`

## Core flow

1. Resolve the approved plan through `ArtifactRegistry["plans"]`.
2. Parse its tracks, create one durable task per track through `task.create`, and mirror dependencies through `task.update`.
3. Verify dependency readiness through `task.read`; any local mapping is disposable and reconstructible.
4. Prepare isolated workspaces through the workspace capability. Isolation disablement or current-branch execution requires approval-manager authorization plus durable audit evidence.
5. Prepare ready work for the worker-dispatch capability up to configured parallelism. Production-impacting parallel work or an execution-strategy change requires approval and audit evidence.
6. Keep review, verification, handoff, and closure as later lifecycle actions. Optional notifications remain provider-backed.

Durable status, ownership, readiness, dependencies, blockers, and closure come only from the task-tracking capability. Workspace and worker metadata are supplemental.
