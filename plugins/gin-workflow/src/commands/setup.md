---
name: setup
description: Interactively coordinate deterministic gin-workflow repository setup.
---

# /setup Command

Use the `setup` skill for one-time repository bootstrap or explicitly requested maintenance. Setup is outside the lifecycle and delegates deterministic work to the setup CLI.

## CLI subcommands

`detect`, `init`, `configure`, `refresh`, `update`, `doctor`, `status`, `diff`, `rollback`, `export-bundle`, `verify-bundle`.

`init`, `configure`, and `update` accept portable `--set` and machine-local `--provider-set` assignments. Ask the skill's question groups one at a time, dry-run to preview both layers, then invoke with the exact approved assignments. Portable policy goes to `.agent-workflow/config.yaml`; executable/model aliases go to the gitignored `.agent-workflow/providers.local.yaml`.

Initial setup needs no pre-existing configuration or approval record. A successful session reports status and stops; it never starts `discuss`.
