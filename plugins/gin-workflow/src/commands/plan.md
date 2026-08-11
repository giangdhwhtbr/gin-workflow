---
name: plan
description: Turn a confirmed requirement into a durable implementation plan.
---

# /plan Command

Route one planning action to the `plan` skill only after requirement confirmation is evidenced. Produce a durable, git-tracked plan without starting orchestration.

## Wrapper boundary

At entry, call `load_effective_config(repository)` and build `ArtifactRegistry` from that generated configuration. If setup is required, stop and instruct the user to run `/setup` once; never run setup or configuration resolution from a lifecycle command. Then create `ContextManifest(stage="plan")` and receive the native-harness `ApprovalDecision`. Resolve the plan destination from `ArtifactRegistry["plans"]`; do not hard-code a repository path or concrete provider.

## Instructions

1. Check evidence for an explicitly confirmed requirement; otherwise return to `discuss` on a later routing action.
2. Use the `writing-plans` methodology skill and [plan-schema.md](file://../skills/writing-plans/plan-schema.md).
3. Keep required context to the confirmed requirement, accepted decisions, and applicable constraints. Make related symbols, tests, and project knowledge discoverable on demand.
4. Record scope, file boundaries, validation intent, dependencies, risks, and abstract model classes.
5. Ask for plan approval in the native harness and persist the decision through the evidence capability.
6. Return `plan_approved` state. Do not orchestrate in the same action.
