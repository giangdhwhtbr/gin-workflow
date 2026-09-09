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
2. Distinguish Parent Bead (Deliverable) vs Track Beads (Work Units):
   - **Parent Bead (Deliverable / Epic)**: Represents the overall feature or release deliverable. Requirements such as "remain open until human-confirmed merge" or release-level merge gates belong strictly to the Parent Bead.
   - **Track Beads (Work Units)**: Represent bounded technical execution units (e.g. T1, T2). The orchestrator must NEVER copy parent-level merge-hold restrictions (e.g. "No commit/push authorized. Code tasks remain open until human-confirmed merge") into child track bead descriptions or acceptance criteria.
3. Parse its tracks, create one durable task per track through `task.create`, and mirror dependencies through `task.update`. Track acceptance criteria must be strictly technical (in-scope code, test validation, code review approval).
4. Verify dependency readiness through `task.read`; any local mapping is disposable and reconstructible. Each track bead must be closed upon technical completion and review pass to unblock downstream dependent tracks in the Beads graph.
5. Prepare isolated workspaces through the workspace capability. Isolation disablement or current-branch execution requires approval-manager authorization plus durable audit evidence.
6. Prepare ready work for the worker-dispatch capability up to configured parallelism. Production-impacting parallel work or an execution-strategy change requires approval and audit evidence.
7. Keep review, verification, handoff, and closure as later lifecycle actions. Optional notifications remain provider-backed.

Durable status, ownership, readiness, dependencies, blockers, and closure come only from the task-tracking capability. Workspace and worker metadata are supplemental.

The generated effective configuration is the sole lifecycle configuration input. See [state ownership](../../references/orchestration-state-model.md) and [provider contracts](../../references/capability-provider-contracts.md).
