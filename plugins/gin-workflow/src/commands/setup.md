---
name: setup
description: Interactively coordinate deterministic gin-workflow repository setup.
---

# /setup Command

Use the `setup` skill for user interaction, approval, and selection. Delegate deterministic work to the setup CLI.

## CLI subcommands

The CLI exposes exactly these setup subcommands:

- `detect`
- `init`
- `configure`
- `refresh`
- `update`
- `doctor`
- `status`
- `diff`
- `rollback`
- `export-bundle`
- `verify-bundle`

## Wrapper boundary

Before invoking the setup skill or CLI, receive resolved `EffectiveConfig`, `ArtifactRegistry`, `ContextManifest(stage="setup")`, and the native-harness `ApprovalDecision`. The skill owns all questions and approval; the CLI remains deterministic and non-interactive.
