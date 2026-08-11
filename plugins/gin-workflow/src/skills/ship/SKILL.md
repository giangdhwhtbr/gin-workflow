---
name: ship
description: Perform one approved delivery action after verification.
---

# Ship Skill

Perform exactly one delivery stage.

## Required inputs

- resolved `EffectiveConfig`
- `ArtifactRegistry`
- `ContextManifest(stage="ship")`
- native-harness `ApprovalDecision`

The caller must obtain `EffectiveConfig` through
`load_effective_config(repository)`. If setup is required, stop and instruct
the user to run `/setup` once. Never run setup or resolve raw configuration
from this lifecycle skill.

## Execution

1. Require `verification_passed`, terminal review evidence, and the canonical handoff record.
2. Apply the `finishing-a-development-branch` methodology.
3. Revalidate reviewed tree identity and every protected-action approval immediately before use.
4. Use the approval and evidence managers for commit, push, upgrade, data movement, or other protected delivery actions. Optional notification and knowledge reconciliation remain provider-backed.
5. Use task-tracking and workspace capabilities for durable closure and cleanup; workspace metadata never proves completion.
6. Return `shipped` state without invoking another lifecycle stage.
