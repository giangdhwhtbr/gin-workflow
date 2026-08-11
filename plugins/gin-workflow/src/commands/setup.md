---
name: setup
description: Interactively coordinate deterministic gin-workflow repository setup.
---

# /setup Command

Use the `setup` skill for one-time repository bootstrap or explicitly requested maintenance. Setup is outside the `discuss` → `plan` → `orchestrate` → `execute` → `verify` → `ship` lifecycle. Delegate deterministic work to the setup CLI.

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

`init` accepts the selected harness and portable `--set` assignments. Its
dry-run result includes the complete proposed portable configuration, and its
first write requires explicit native-harness approval.

## Wrapper boundary

Initial setup requires only the repository target, detected/native harness context, and user-selected portable settings. It must not require `EffectiveConfig`, `ArtifactRegistry`, a setup context manifest, or a pre-existing approval record because those facilities do not exist before bootstrap.

In one `/setup` session, preview and then invoke `init` with the approved harness and `--set` assignments. A successful initial session stops after reporting setup status; it never starts `discuss`. On an initialized repository, load the existing effective config only when an explicitly requested maintenance action needs it. The CLI remains deterministic and non-interactive.
