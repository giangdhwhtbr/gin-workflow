---
name: evidence-manager
description: Persist and query provider-backed workflow evidence and audit events.
---

# Evidence Manager Skill

Coordinate one evidence operation without treating prose or self-assessment as proof.

## Required inputs

- resolved `EffectiveConfig`
- `ArtifactRegistry`
- stage-specific `ContextManifest`
- native-harness `ApprovalDecision`

## Rules

1. Select the evidence provider from `EffectiveConfig` and resolve its storage location through `ArtifactRegistry`.
2. Use `evidence.record`, `evidence.query`, or `evidence.completeness`; do not call a concrete adapter.
3. Persist approval decisions as typed `WorkflowEvent` values in `WorkflowEventStore`, with the serialized request and decision in the event payload.
4. Before reporting an approval guard satisfied, re-read the store and revalidate each candidate with `WorkflowEvent.from_mapping(event.to_dict())`. Never trust in-memory routing candidates.
5. Require action, workflow, request, decision, and actor identity to match. Both decision and event must be no more than five minutes old, and the event cannot predate the decision.
6. Treat test output, terminal review state, repository identity, and current native-harness decisions as evidence. Never treat private reasoning, self-assessment, persuasive summaries, notification delivery, or workspace existence as evidence.
7. Return normalized evidence and provider availability so the router can choose one stage.
