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

## Execution

1. Require `orchestration_ready` evidence and read one ready durable work unit through the task-tracking capability.
2. Apply the `executing-plans` and `bead-worker` methodologies inside the plan-declared scope.
3. Dispatch through the configured worker capability; use workspace, knowledge, and notification capabilities only when enabled.
4. Use the approval manager and evidence manager before isolation disablement, current-branch execution, execution-strategy or scope changes, or production-impacting parallel work.
5. Keep selected scope and validation intent required; discover related symbols, tests, and project knowledge on demand.
6. Record work-unit results and return `implementation_complete` state. Do not invoke verification.
