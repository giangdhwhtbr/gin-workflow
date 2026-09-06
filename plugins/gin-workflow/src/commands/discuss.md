---
name: discuss
description: Clarify a requirement before planning or durable task creation.
---

# /discuss Command

Route one requirement-discovery action to the `discuss` skill. Stop after that action; a later `/workflow` invocation chooses the next stage.

## Wrapper boundary

At entry, call `load_effective_config(repository)` and build `ArtifactRegistry` from that generated configuration. Setup is required ONLY when `load_effective_config` fails or `effective-config.yaml` is missing; an empty `capabilities: {}` is the valid default where all capabilities and stages are enabled. Never treat `capabilities: {}` as missing setup. If setup is required, stop and instruct the user to run `/setup` once; never run setup or configuration resolution from a lifecycle command. Then create a `ContextManifest` whose stage is `discuss` and receive the native-harness `ApprovalDecision`. Do not read raw configuration or call a concrete adapter.

The manifest requires only the user's requirement and directly relevant repository context. Related symbols, tests, and project knowledge remain discoverable on demand through their configured capabilities.

## Instructions

1. Use the `discovering-work` methodology skill.
2. Resolve ambiguity, edge cases, dependencies, constraints, and acceptance intent.
3. Summarize the understanding and obtain native-harness confirmation.
4. Record the confirmation through the evidence capability.
5. Do not create a plan or durable execution tasks in this stage.
