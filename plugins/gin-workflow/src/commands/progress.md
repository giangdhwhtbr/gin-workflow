---
name: progress
description: Report provider-backed workflow status without mutation.
---

# /progress Command

Route one read-only status action to the `progress` skill.

## Wrapper boundary

At entry, call `load_effective_config(repository)` and build `ArtifactRegistry` from that generated configuration. If setup is required, stop and instruct the user to run `/setup` once; never run setup or configuration resolution from a lifecycle command. Then create `ContextManifest(stage="progress")` and receive the native-harness `ApprovalDecision`. Durable status comes only from the configured task-tracking capability; evidence and review enrichment use their configured providers.

## Instructions

1. Read durable task identity, dependencies, status, ownership, blockers, readiness, and closure through the task-tracking capability.
2. Group pending, active, complete, and failed work and recommend dependency-ready next work.
3. Label workspace or worker metadata as derived, supplemental context.
4. Keep only status and dependency facts required; related symbols, tests, and project knowledge remain discoverable on demand.
5. Do not mutate state or invoke another lifecycle stage.
