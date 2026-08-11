---
name: executing-plans
description: Extend plan execution with provider-backed status, scoped changes, and close-out evidence.
---

# Executing Plans Skill

This skill extends `superpowers:executing-plans` for the `gin-workflow` plugin. Use that skill as methodology guidance, then apply this provider-neutral overlay.

## Required inputs

- resolved `EffectiveConfig`
- `ArtifactRegistry`
- `ContextManifest(stage="execute")`
- native-harness `ApprovalDecision`

## Gin Workflow overlay

1. Read and update durable ownership/status through task-tracking capabilities, never plan checkboxes.
2. Resolve approved scope and validation intent from the plan artifact.
3. Keep changes minimal and strictly in scope; discover related symbols, tests, and project knowledge on demand.
4. Validate immediately after each work unit and record the evidence.
5. Follow the canonical verification and handoff workflow before task closure. Validation alone is insufficient without outcome notes, repository status, and handoff evidence.
6. Do not proceed while tests fail, acceptance criteria remain unmet, review is nonterminal, or close-out evidence is incomplete.
7. Use the task-tracking capability to keep incomplete work active or blocked with durable notes.
