---
name: discuss
description: Clarify a requirement before planning or durable task creation.
---

# /discuss Command

Route one requirement-discovery action to the `discuss` skill. Stop after that action; a later `/workflow` invocation chooses the next stage.

## Wrapper boundary

Before delegation, receive the resolved `EffectiveConfig`, its `ArtifactRegistry`, a `ContextManifest` whose stage is `discuss`, and the native-harness `ApprovalDecision`. Do not read raw configuration or call a concrete adapter.

The manifest requires only the user's requirement and directly relevant repository context. Related symbols, tests, and project knowledge remain discoverable on demand through their configured capabilities.

## Instructions

1. Use the `discovering-work` methodology skill.
2. Resolve ambiguity, edge cases, dependencies, constraints, and acceptance intent.
3. Summarize the understanding and obtain native-harness confirmation.
4. Record the confirmation through the evidence capability.
5. Do not create a plan or durable execution tasks in this stage.
