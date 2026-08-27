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
2. Initialize review state and capture repository identity through the review capability, before requesting review. A task whose ledger has never been created has no review state to transition: `review.request` reports `unavailable` rather than bootstrapping one. Call `review.initialize` with a `ReviewInitRequest` declaring the task, actor, repository id/role, repository path relative to the configured repository root (the nested implementation worktree when the reviewed source lives in one), base ref, a review ref unique to this task, and the approved source scope. Initialization is idempotent and never re-initializes or overwrites an existing ledger. Never hand-write `review.json`, copy another task's ledger, or invoke the ledger adapter script directly.
3. Dispatch an independent reviewer through the worker capability and update durable status through the task-tracking capability.
4. The review manifest contains only the reviewed tree/diff, confirmed requirement, acceptance criteria, and test evidence. It excludes private reasoning, self-assessment, persuasive summaries, unrelated history, and secrets.
5. Record structured findings, reviewer identity, terminal state, and repository identity through the evidence capability.
6. Route returned findings through `receiving-code-review`; never manufacture approval or close work from notification delivery.
7. Record the implementation's original provider/model route as runtime affinity metadata. Do not copy concrete aliases into the portable plan or durable task fields.
8. A completed implementation result starts review; it is not evidence that the task may close.
