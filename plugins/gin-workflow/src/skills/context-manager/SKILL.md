---
name: context-manager
description: Validate bounded stage-specific ContextManifest values with on-demand discovery.
---

# Context Manager Skill

Validate and coordinate one `ContextManifest` without copying parent transcripts or unrelated task state.

## Required inputs

- resolved `EffectiveConfig`
- `ArtifactRegistry`
- stage-specific `ContextManifest`
- native-harness `ApprovalDecision`

## Manifest rules

Every manifest uses the `required`, `conditional`, `discoverable`, `reference`, and `prohibited` categories. Required context is the smallest set needed for the current action. Every stage includes discoverable entries for related symbols, relevant tests, and project knowledge; resolve them only on demand through the configured context or knowledge capability.

Stage requirements are bounded as follows:

- `setup`: repository target, selected setup action, and proposed changes.
- `workflow`: durable completion gates, blockers, guarded actions, and audit evidence.
- `discuss`: the current requirement and directly relevant constraints.
- `plan`: confirmed requirement, accepted decisions, and planning constraints.
- `orchestrate`: approved plan tracks, dependencies, scopes, and validation intent.
- `execute`: one selected work unit, its dependencies, file scope, and validation intent.
- `review`: reviewed diff/tree, confirmed requirement, acceptance criteria, and test evidence.
- `verify`: confirmed requirement, approved plan, acceptance criteria, review state, and quality-gate evidence.
- `ship`: terminal verification/review evidence, approvals, and handoff record.
- `progress`: durable task status and dependency facts.

Review manifests prohibit private reasoning, chain-of-thought, self-assessment, persuasive summaries, unrelated history, and secret material. Other manifests prohibit private reasoning, unrelated history, and secrets. Return the sanitized manifest before any provider or methodology call.
