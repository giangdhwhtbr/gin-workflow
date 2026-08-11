---
name: bead-worker
description: Implement and validate one provider-backed durable work unit.
---

# Bead Worker Skill

Execute one assigned work unit inside its approved plan scope.

## Required inputs

- resolved `EffectiveConfig`
- `ArtifactRegistry`
- `ContextManifest(stage="execute")`
- native-harness `ApprovalDecision`

## Execution rules

1. Read task identity, status, dependencies, description, and acceptance criteria through `task.read`; claim or update it through `task.update`.
2. Resolve its file scope and validation intent from the approved plan in the artifact registry. Durable task state never supplies file scope.
3. Keep that work unit and scope required; discover related symbols, tests, and project knowledge on demand.
4. Implement only in-scope changes and run relevant local validation. Record notable discoveries through the knowledge capability and results through the evidence capability.
5. Route review findings through `receiving-code-review` and read terminal review state through the review capability.
6. Follow the canonical verification and handoff workflow. Write outcome notes and final state through task-tracking capabilities only after validation, review, repository status, follow-up capture, and handoff evidence are complete.

Scope or execution-strategy changes and production-impacting parallel work require native-harness approval plus a durable audit event. Notifications are optional and provider-backed.
