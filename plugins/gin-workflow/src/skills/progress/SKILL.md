---
name: progress
description: Report provider-backed workflow status without mutation.
---

# Progress Skill

Perform exactly one read-only status action.

## Required inputs

- resolved `EffectiveConfig`
- `ArtifactRegistry`
- `ContextManifest(stage="progress")`
- native-harness `ApprovalDecision`

## Execution

1. Query the task-tracking capability for all work, ready work, aggregate status, and requested task details.
2. Group results as Pending, Active, Complete, and Failed. Recommend active dependencies first, then ready work by priority, then root blockers.
3. Enrich review status through the review capability and validation state through the evidence capability when enabled.
4. Label worker and workspace details as derived runtime metadata, never authoritative durable state.
5. Keep status and dependency facts required; discover related symbols, tests, and project knowledge on demand.
6. Return the report without mutation or lifecycle chaining.
