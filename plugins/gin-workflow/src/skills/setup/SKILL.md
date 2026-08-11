---
name: setup
description: Own setup interaction and approval while delegating deterministic work to the CLI.
---

# Setup Skill

Coordinate one setup action.

## Required inputs

- resolved `EffectiveConfig`
- `ArtifactRegistry`
- `ContextManifest(stage="setup")`
- native-harness `ApprovalDecision`

## Execution

1. Ask questions in the native harness and select one documented setup subcommand.
2. Present dry-run output before user-authored configuration changes, upgrades, rollback, or data movement.
3. Use the approval manager and evidence manager for protected mutations. Pass approval to the CLI only after the matching decision is durably recorded.
4. Delegate deterministic work to one of: `detect`, `init`, `configure`, `refresh`, `update`, `doctor`, `status`, `diff`, `rollback`, `export-bundle`, or `verify-bundle`.
5. Keep repository target and selected action required. Make related symbols, tests, and project knowledge discoverable on demand.
6. Report structured CLI results without chaining into a lifecycle stage.

The CLI must not prompt, choose policy, or manufacture approval. Optional notifications use the configured notification capability.
