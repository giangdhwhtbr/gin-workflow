---
name: progress
description: Report provider-backed workflow status without mutation.
---

# /progress Command

Route one read-only status action to the `progress` skill.

## Wrapper boundary

Before delegation, receive `EffectiveConfig`, `ArtifactRegistry`, `ContextManifest(stage="progress")`, and the native-harness `ApprovalDecision`. Durable status comes only from the configured task-tracking capability; evidence and review enrichment use their configured providers.

## Instructions

1. Read durable task identity, dependencies, status, ownership, blockers, readiness, and closure through the task-tracking capability.
2. Group pending, active, complete, and failed work and recommend dependency-ready next work.
3. Label workspace or worker metadata as derived, supplemental context.
4. Keep only status and dependency facts required; related symbols, tests, and project knowledge remain discoverable on demand.
5. Do not mutate state or invoke another lifecycle stage.
