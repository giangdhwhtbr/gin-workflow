---
name: discuss
description: Clarify a requirement before planning or durable task creation.
---

# Discuss Skill

Perform exactly one requirement-discovery stage and return its transition evidence.

## Required inputs

- resolved `EffectiveConfig`
- `ArtifactRegistry`
- `ContextManifest(stage="discuss")`
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

Reject unbounded parent context. Use the context manager to keep the requirement and relevant repository facts required while leaving related symbols, tests, and project knowledge discoverable on demand.

## Execution

1. Apply the `discovering-work` methodology.
2. Clarify ambiguity, constraints, alternatives, risks, and acceptance criteria.
3. Ask for explicit confirmation in the native harness.
4. Use the evidence capability to record the confirmed requirement and decision.
5. Return state showing whether `requirement_confirmed` is true. Do not invoke another lifecycle stage.
