---
name: verify
description: Validate implementation against approved requirements and evidence.
---

# /verify Command

Route one verification action to the `verify` skill and follow [verification-and-handoff-workflow.md](file://../references/verification-and-handoff-workflow.md).

## Wrapper boundary

Before delegation, receive `EffectiveConfig`, `ArtifactRegistry`, `ContextManifest(stage="verify")`, and the native-harness `ApprovalDecision`. Review, evidence, knowledge, and notification operations use configured capabilities only.

## Instructions

1. Require `implementation_complete` evidence.
2. Apply the `verification-before-completion` methodology and the repository handoff checklist.
3. Verify the original confirmed requirement, approved plan, acceptance criteria, review state, and relevant quality gates.
4. Keep those artifacts required; discover related symbols, tests, and project knowledge on demand.
5. Record pass/fail evidence honestly and return `verification_passed` state. Do not ship in the same action.
