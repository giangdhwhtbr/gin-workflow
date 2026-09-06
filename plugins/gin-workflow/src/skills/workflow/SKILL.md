---
name: workflow
description: Route current durable state to exactly one guarded lifecycle action.
---

# Workflow Skill

Evaluate state and invoke one wrapper only.

## Required inputs

- resolved `EffectiveConfig`
- `ArtifactRegistry`
- `ContextManifest(stage="workflow")`
- native-harness `ApprovalDecision`

The caller must obtain `EffectiveConfig` through
`load_effective_config(repository)`. Setup is required ONLY when
`load_effective_config` raises `ConfigValidationError` (i.e.
`.agent-workflow/generated/effective-config.yaml` is missing). An empty
`capabilities: {}` mapping in `EffectiveConfig` is the valid default state where
all capabilities and lifecycle stages are enabled. Never treat
`capabilities: {}` as missing configuration. If setup is required, stop and
instruct the user to run `/setup` once. Never run setup or resolve raw
configuration from this lifecycle skill.

## Routing contract

Build state from configured task-tracking, evidence, review, and workspace capabilities. The router consumes these completion gates in order: `requirement_confirmed`, `plan_approved`, `orchestration_ready`, `implementation_complete`, `verification_passed`, and `shipped`. Gates evaluate to tri-state values (`satisfied`, `waived`, or `unmet`). Blocked state routes to `progress`.

1. Resolve provider selection only from `EffectiveConfig`.
2. Build bounded state with typed protected-action requests and decisions plus the typed `WorkflowEventStore` that owns persisted audit evidence (including `gate.waived` events). Do not supply or trust in-memory audit candidates.
3. Call `route_next_stage(state, config)` once. The router re-reads and revalidates the persisted event stream and enforces scope-bound approval validity with configured policy TTL (`policy.approval.ttl_seconds`, default 86,400 seconds).
4. Preserve the returned stage, transition decision, evidence, and any returned remedies.
5. Build a fresh context request for only that target stage, call `create_context_manifest(target_stage, request)`, and pass the result through the context manager for sanitization and stage verification.
6. Invoke the selected wrapper with `EffectiveConfig`, `ArtifactRegistry`, the sanitized target-stage `ContextManifest`, and the native-harness `ApprovalDecision`, then stop.

## Diagnostic Inspection and Recovery

When a workflow is held or blocked:

- Run `gin-workflow state [--format text|json]` to inspect the gate status table (`satisfied` / `waived` / `unmet`), active decision, evidence, and actionable remedies.
- Use `gin-workflow unblock --gate GATE --reason TEXT --actor ID [--follow-up TASK_ID]` to record a process or safety gate waiver. Safety gates (`verification_passed`, `review_approved`) require `--follow-up`. Non-waivable gates (`implementation_complete`, `shipped`) are rejected.
- Use `gin-workflow unblock --clear-blocker --reason TEXT --actor ID` to clear a blocked status with an audited `blocker.cleared` event.

Never reuse the routing manifest as a stage manifest and never invoke a second stage based on the first stage's result. Notifications are optional, provider-backed side effects and never approval evidence.

