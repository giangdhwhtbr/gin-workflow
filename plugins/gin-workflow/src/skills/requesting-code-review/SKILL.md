---
name: requesting-code-review
description: Request provider-backed review with structured findings and durable evidence.
---

# Requesting Code Review Skill

This skill extends `superpowers:requesting-code-review` for the `gin-workflow` plugin.

## Required inputs

- resolved `EffectiveConfig`
- `ArtifactRegistry`
- `ContextManifest(stage="review")`
- native-harness `ApprovalDecision`

## Gin Workflow overlay

1. Request review after an implementation pass has local validation evidence.
2. Initialize review state and capture repository identity through the review capability.
3. Dispatch an independent reviewer through the worker capability and update durable status through the task-tracking capability.
4. The review manifest contains only the reviewed tree/diff, confirmed requirement, acceptance criteria, and test evidence. It excludes private reasoning, self-assessment, persuasive summaries, unrelated history, and secrets.
5. Record structured findings, reviewer identity, terminal state, and repository identity through the evidence capability.
6. Route returned findings through `receiving-code-review`; never manufacture approval or close work from notification delivery.
