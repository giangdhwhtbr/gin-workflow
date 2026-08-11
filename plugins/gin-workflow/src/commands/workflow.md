---
name: workflow
description: Route current durable state to exactly one guarded lifecycle action.
---

# /workflow Command

Use the `workflow` skill to inspect state, evaluate guards, and select one next action.

## Wrapper boundary

Before routing, call `load_effective_config(repository)` and build `ArtifactRegistry` from that generated configuration. If setup is required, stop and instruct the user to run `/setup` once; never run setup or configuration resolution from `/workflow`. Then create `ContextManifest(stage="workflow")` and receive the native-harness `ApprovalDecision`. Use `route_next_stage(state, config)` and preserve its decision and evidence.

After routing, construct a new `ContextManifest` whose stage exactly matches the selected target, sanitize it through the context manager, and pass `EffectiveConfig`, `ArtifactRegistry`, that target-stage manifest, and `ApprovalDecision` to the selected wrapper.

Invoke at most one of `discuss`, `plan`, `orchestrate`, `execute`, `verify`, `ship`, or `progress`. Never loop, combine lifecycle actions, or infer success from a prior action's return value. A later `/workflow` invocation re-reads durable state and routes again.
