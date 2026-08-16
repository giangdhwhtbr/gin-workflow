---
name: execute
description: Execute one approved work unit through configured capabilities.
---

# /execute Command

Route one implementation action to the `execute` skill. One invocation handles one ready work unit and never includes verification or shipping.

## Wrapper boundary

At entry, call `load_effective_config(repository)` and build `ArtifactRegistry` from that generated configuration. If setup is required, stop and instruct the user to run `/setup` once; never run setup or configuration resolution from a lifecycle command. Then create `ContextManifest(stage="execute")` and receive the native-harness `ApprovalDecision`. Worker dispatch, task tracking, workspace isolation, knowledge capture, and notifications are capability calls selected from effective configuration.

## Instructions

1. Require `orchestration_ready` evidence and select one ready unit from the task-tracking capability.
2. Use the `executing-plans` methodology and the worker-dispatch capability within the plan-declared file scope.
3. Keep only the selected work unit, dependencies, file scope, and validation intent required. Discover related symbols, tests, and project knowledge on demand.
4. Execution strategy or scope changes and production-impacting parallel work require approval-manager authorization plus a durable audit event.
5. Record validation and outcomes through the evidence capability and return `implementation_complete` state.
