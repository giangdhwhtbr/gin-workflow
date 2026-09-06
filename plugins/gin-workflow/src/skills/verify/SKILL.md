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

There is no separate adapter class per harness for the `ApprovalDecision`: the
running agent asks the user/operator directly through its own harness's native
"ask the user a question" mechanism, then builds the portable `ApprovalDecision`
dataclass (`workflow_core/approvals.py`) from that answer (see the
approval-manager skill).

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

1. Require evidence that `implementation_complete` is true.
2. Apply `verification-before-completion` and the canonical handoff workflow.
3. Validate against the confirmed requirement, approved plan, acceptance criteria, and review evidence rather than only the diff.
4. Use bounded required context and discover related symbols, tests, and project knowledge on demand.
5. Record every run, omitted check, failure, risk, and provider availability through the evidence capability. Optional notifications use the configured notification provider.
6. Return `verification_passed` state. Do not invoke shipping.
