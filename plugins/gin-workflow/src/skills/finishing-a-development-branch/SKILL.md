---
name: finishing-a-development-branch
description: Extend delivery with provider-backed integration, cleanup, and handoff safety.
---

# Finishing a Development Branch Skill

This skill extends `superpowers:finishing-a-development-branch` for the `gin-workflow` plugin.

## Required inputs

- resolved `EffectiveConfig`
- `ArtifactRegistry`
- `ContextManifest(stage="ship")`
- native-harness `ApprovalDecision`

## Gin Workflow overlay

1. Follow [verification-and-handoff-workflow.md](file://../../references/verification-and-handoff-workflow.md) before treating work as shippable.
2. Generate and inspect repository identity/diff evidence against the approved baseline when integration is in scope.
3. Use configured repository/workspace capabilities for authorized integration and cleanup; never invoke adapter scripts directly.
4. Revalidate native-harness approval and persist durable audit evidence immediately before commit, push, merge, data movement, or protected cleanup.
5. Discover cleanup targets from bounded execution context and workspace-provider records. Reject wildcards and unresolved paths.
6. Use task-tracking capabilities for durable handoff and closure. Branch or workspace cleanup never proves task completion.
