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

The manifest requires the confirmed requirement and accepted decisions only. Use the context and knowledge capabilities to discover related symbols, tests, and project knowledge on demand.

## Execution

1. Require evidence that `requirement_confirmed` is true.
2. Apply the `writing-plans` methodology and write the plan under `ArtifactRegistry["plans"]`.
3. Include approved scope, concrete file ownership, dependency-aware tracks, validation, risks, and abstract model-class guidance.
4. Obtain native-harness approval of the plan and record it through the evidence capability.
5. Return state showing whether `plan_approved` is true. Do not invoke orchestration.
