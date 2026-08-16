---
name: using-git-worktrees
description: Extend isolated workspace handling with provider-backed safety constraints.
---

# Using Git Worktrees Skill

This skill extends `superpowers:using-git-worktrees` for the `gin-workflow` plugin.

## Required inputs

- resolved `EffectiveConfig`
- `ArtifactRegistry`
- stage-specific `ContextManifest`
- native-harness `ApprovalDecision`

## Gin Workflow overlay

1. Create, isolate, inspect, and clean workspaces only through the configured workspace capability.
2. Resolve the workspace root from `ArtifactRegistry["worktrees"]` and use one explicit track identity; reject wildcards or unresolved paths.
3. Require unique branch/workspace identities and enforce the configured filesystem safety boundary before mutation.
4. Isolation disablement or current-branch execution requires approval-manager authorization plus durable audit evidence.
5. Treat workspace paths and branch names as supplemental runtime metadata. Durable status and completion remain owned by the task-tracking capability.
