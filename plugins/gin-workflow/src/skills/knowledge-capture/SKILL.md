---
name: knowledge-capture
description: Propose reusable implementation knowledge through the configured knowledge capability.
---

# Knowledge Capture Skill

Use this skill during implementation for high-value codebase discoveries, configuration choices, architectural decisions, or non-obvious workarounds.

## Required inputs

- resolved `EffectiveConfig`
- `ArtifactRegistry`
- stage-specific `ContextManifest`
- native-harness `ApprovalDecision`

## Capture rules

1. Capture reusable knowledge, not routine implementation steps, transient worker state, private reasoning, or self-assessment.
2. Use `knowledge.search` to find an existing project/module record and avoid duplicate proposals.
3. Build a concise `KnowledgeProposal` containing context, decision or solution, consequences, repository references, and relevant scope.
4. Submit it through `knowledge.propose`; provider acceptance is separate from task success.
5. Record the proposal identity and provider result through the evidence capability.

Good candidates include compatibility constraints, environment limitations, architectural decisions, counterintuitive APIs, and durable debugging lessons. Knowledge-provider unavailability is recorded in handoff evidence and never bypassed through a concrete adapter.
