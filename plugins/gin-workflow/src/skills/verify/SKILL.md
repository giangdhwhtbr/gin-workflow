---
name: verify
description: Validate implementation against approved requirements and evidence.
---

# Verify Skill

Perform exactly one verification stage.

## Required inputs

- resolved `EffectiveConfig`
- `ArtifactRegistry`
- `ContextManifest(stage="verify")`
- native-harness `ApprovalDecision`

The caller must obtain `EffectiveConfig` through
`load_effective_config(repository)`. If setup is required, stop and instruct
the user to run `/setup` once. Never run setup or resolve raw configuration
from this lifecycle skill.

## Execution

1. Require evidence that `implementation_complete` is true.
2. Apply `verification-before-completion` and the canonical handoff workflow.
3. Validate against the confirmed requirement, approved plan, acceptance criteria, and review evidence rather than only the diff.
4. Use bounded required context and discover related symbols, tests, and project knowledge on demand.
5. Record every run, omitted check, failure, risk, and provider availability through the evidence capability. Optional notifications use the configured notification provider.
6. Return `verification_passed` state. Do not invoke shipping.
