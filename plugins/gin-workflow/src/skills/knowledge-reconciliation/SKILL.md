---
name: knowledge-reconciliation
description: Reconcile long-term project knowledge through the configured knowledge provider.
---

# Knowledge Reconciliation Skill

Run during `ship` after verification succeeds and before durable task closure.

## Required inputs

- resolved `EffectiveConfig`
- `ArtifactRegistry`
- `ContextManifest(stage="ship")`
- native-harness `ApprovalDecision`

## Execution

1. Discover the task's related project knowledge through `knowledge.search`.
2. Propose completion status, a concise evidence-backed summary, and relevant repository references through `knowledge.propose`.
3. Search for related decisions and indexes, then propose corrections for contradictions or stale status.
4. Record accepted knowledge proposals through the evidence capability; do not claim reconciliation from notification delivery.
5. Proceed to task closure only after required proposals are accepted or any unavailable/declined provider outcome is explicitly recorded in handoff evidence.

Knowledge is discoverable on demand and is never copied wholesale into the ship manifest. Optional notifications use the configured notification capability.
