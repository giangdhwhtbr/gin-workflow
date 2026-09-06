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

The caller must obtain `EffectiveConfig` through
`load_effective_config(repository)`. Setup is required ONLY when
`load_effective_config` raises `ConfigValidationError` (i.e.
`.agent-workflow/generated/effective-config.yaml` is missing). An empty
`capabilities: {}` mapping in `EffectiveConfig` is the valid default state where
all capabilities and lifecycle stages are enabled. Never treat
`capabilities: {}` as missing configuration. If setup is required, stop and
instruct the user to run `/setup` once. Never run setup or resolve raw
configuration from this lifecycle skill.

## Execution

1. Query the task-tracking capability for all work, ready work, aggregate status, and requested task details.
2. Group results as Pending, Active, Complete, and Failed. Recommend active dependencies first, then ready work by priority, then root blockers.
3. Enrich review status through the review capability and validation state through the evidence capability when enabled.
4. Query `gate.waived` audit events from the event store. Report any open gate waivers alongside task status, including their stated reasons and unclosed follow-up tasks — this is the mitigation that prevents waivers from becoming a habit.
5. Label worker and workspace details as derived runtime metadata, never authoritative durable state.
6. Keep status and dependency facts required; discover related symbols, tests, and project knowledge on demand.
7. Return the report without mutation or lifecycle chaining.

