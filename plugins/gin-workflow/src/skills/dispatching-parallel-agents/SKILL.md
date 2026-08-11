---
name: dispatching-parallel-agents
description: Extend parallel dispatch with provider selection, bounded context, approval, and concurrency controls.
---

# Dispatching Parallel Agents Skill

This skill extends `superpowers:dispatching-parallel-agents` for the `gin-workflow` plugin.

## Required inputs

- resolved `EffectiveConfig`
- `ArtifactRegistry`
- `ContextManifest(stage="execute")`
- native-harness `ApprovalDecision`

## Gin Workflow overlay

1. Select worker dispatch only through the configured worker capability; do not branch on harness names or invoke harness-specific tools directly.
2. Give each worker only its selected durable task, dependencies, approved file scope, validation intent, and on-demand discovery references.
3. Enforce the effective-config concurrency limit and dependency readiness from the task-tracking capability.
4. Execution-strategy changes and production-impacting parallel work require approval-manager authorization and durable audit evidence before dispatch.
5. Record dispatch identity and normalized outcomes through the evidence capability. Worker metadata remains disposable, not authoritative task state.
