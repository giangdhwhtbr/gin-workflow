---
name: ship
description: Perform one approved delivery action after verification.
---

# /ship Command

Route one delivery action to the `ship` skill.

## Wrapper boundary

At entry, call `load_effective_config(repository)` and build `ArtifactRegistry` from that generated configuration. If setup is required, stop and instruct the user to run `/setup` once; never run setup or configuration resolution from a lifecycle command. Then create `ContextManifest(stage="ship")` and receive the native-harness `ApprovalDecision`. Task closure, workspace cleanup, review, evidence, knowledge, and notifications use their configured capabilities.

## Instructions

1. Require `verification_passed` evidence and a terminal review state.
2. Apply the `finishing-a-development-branch` methodology and canonical handoff checklist.
3. Revalidate required approval and reviewed tree identity before any authorized integration action.
4. Obtain native-harness approval for commit, push, upgrade, data movement, or other protected delivery actions and persist the audit event.
5. Keep verification, review, approval, and handoff evidence required; related symbols, tests, and project knowledge remain discoverable on demand.
6. Return `shipped` state after durable close-out. Do not start another lifecycle action.
