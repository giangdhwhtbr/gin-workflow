---
name: plan
description: Turn a confirmed requirement into a durable implementation plan.
---

# Plan Skill

Perform exactly one planning stage.

## Required inputs

- resolved `EffectiveConfig`
- `ArtifactRegistry`
- `ContextManifest(stage="plan")`
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

The manifest requires the confirmed requirement and accepted decisions only. Use the context and knowledge capabilities to discover related symbols, tests, and project knowledge on demand.

## Execution

1. Require evidence that `requirement_confirmed` is true.
2. Apply the `writing-plans` methodology and write the plan under `ArtifactRegistry["plans"]`.
3. Include approved scope, concrete file ownership, dependency-aware tracks, validation, risks, and abstract model-class guidance.
4. Assign every implementation or review track a portable provider role and reasoning tier. Do not select a concrete provider or model.
5. Call `validate_plan_assignments(tasks, config)` for the complete plan. Report every task-specific diagnostic in task order and reject the plan when any error is returned.
6. Obtain native-harness approval only after aggregate assignment validation succeeds, and record it through the evidence capability.
7. Return state showing whether `plan_approved` is true. Do not invoke orchestration.
