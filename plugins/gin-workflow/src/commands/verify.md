---
name: verify
description: Validate implementation against approved requirements and evidence.
---

# /verify Command

Route one verification action to the `verify` skill and follow [verification-and-handoff-workflow.md](file://../references/verification-and-handoff-workflow.md).

## Wrapper boundary

At entry, call `load_effective_config(repository)` and build `ArtifactRegistry` from that generated configuration. Setup is required ONLY when `load_effective_config` fails or `effective-config.yaml` is missing; an empty `capabilities: {}` is the valid default where all capabilities and stages are enabled. Never treat `capabilities: {}` as missing setup. If setup is required, stop and instruct the user to run `/setup` once; never run setup or configuration resolution from a lifecycle command. Then create `ContextManifest(stage="verify")` and receive the native-harness `ApprovalDecision`. Review, evidence, knowledge, and notification operations use configured capabilities only.

## Instructions

1. Require `implementation_complete` evidence.
2. Apply the `verification-before-completion` methodology and the repository handoff checklist.
3. Verify the original confirmed requirement, approved plan, acceptance criteria, review state, and relevant quality gates.
4. Keep those artifacts required; discover related symbols, tests, and project knowledge on demand.
5. Record pass/fail evidence honestly and return `verification_passed` state. Do not ship in the same action.
