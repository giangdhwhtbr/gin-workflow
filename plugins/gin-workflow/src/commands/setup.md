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

`init`, `configure`, and `update` accept portable `--set` assignments and
machine-local `--provider-set` assignments. The wrapper asks the setup skill's
nine question groups one at a time. Dry-run displays both proposed layers;
the approved invocation repeats the exact same assignments.

## Wrapper boundary

Initial setup requires only the repository target, detected/native harness context, and user-selected portable settings. It must not require `EffectiveConfig`, `ArtifactRegistry`, a setup context manifest, or a pre-existing approval record because those facilities do not exist before bootstrap.

In one `/setup` session, preview and then invoke `init` with the approved harness,
`--set`, and `--provider-set` assignments. Portable policy is written to
`.agent-workflow/config.yaml`; executable/model aliases are written to the
gitignored `.agent-workflow/providers.local.yaml`. A successful initial session
stops after reporting setup status; it never starts `discuss`. On an initialized
repository, load the existing effective config only when an explicitly requested
maintenance action needs it. The CLI remains deterministic and non-interactive.
