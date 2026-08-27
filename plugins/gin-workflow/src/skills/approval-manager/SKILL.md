---
name: approval-manager
description: Enforce native-harness approval, freshness, and durable audit boundaries for protected actions.
---

# Approval Manager Skill

Authorize one protected action at a time.

## Required inputs

- resolved `EffectiveConfig`
- `ArtifactRegistry`
- stage-specific `ContextManifest`
- current native-harness `ApprovalDecision`

## Protected actions

The following always require an explicit native-harness decision immediately before execution and a matching durable audit event:

- isolation disablement (`disable_isolation`)
- current-branch execution (`current_branch_execution`)
- scope change (`scope_change`)
- execution-strategy change (`execution_strategy_change`)
- production-impacting parallel work (`production_parallel_work`)

Commit, push, upgrade, and data movement retain the same approval boundary.

## Rules

1. Create a typed `ApprovalRequest` naming one action, workflow, reason, and bounded details.
2. Ask through the native harness. A notification reply is never an approval substitute. There is no per-harness adapter class: whichever agent (Claude, Codex, Antigravity, ...) is running is itself responsible for asking the user directly through its own harness's native "ask the user a question" mechanism, then constructing the portable `ApprovalDecision` dataclass (`workflow_core/approvals.py`) from that answer.
3. Require a matching typed `ApprovalDecision`; reject mappings, denied decisions, request/action/workflow mismatches, invalid timestamps, and decisions more than five minutes old.
4. Persist the request and decision in a matching `approval.recorded` `WorkflowEvent` through the evidence manager.
5. Immediately before routing, re-read the event from the typed `WorkflowEventStore`. Revalidate its serialized form and require matching action, workflow, request, decision, actor, and a timestamp no more than five minutes old and not earlier than the decision.
6. Call the protected capability only after the persisted-stream check succeeds; otherwise hold at `progress`.

Notifications are optional and use only the configured notification capability.
