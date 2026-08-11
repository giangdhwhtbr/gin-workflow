# Setup System

`gin-workflow setup` prepares one repository without beginning lifecycle work. Plugin installation only makes the versioned CLI and skills available; it never initializes a repository, moves user artifacts, or silently changes its configuration.

## Configuration

Setup resolves built-in, profile, repository, harness, local, and approved command overrides into `.agent-workflow/generated/effective-config.yaml`, with `config-provenance.yaml` beside it. Lifecycle wrappers consume only this effective configuration. Portable config contains logical capability selections, artifact names, policy, logical model tiers, and `secret_ref` values; it contains no provider commands, provider model identifiers, or literal credentials.

## Interface and versions

The versioned CLI is `gin-workflow setup`. Its supported actions are `detect`, `init`, `configure`, `refresh`, `update`, `doctor`, `status`, `diff`, `rollback`, `export-bundle`, and `verify-bundle`. `init` is idempotent; `configure` and an update application require explicit approval; read-only inspection actions do not write user configuration.

Schema, workflow, and setup-CLI versions are separate compatibility channels. The current supported values are `schema_version: "2.1"`, `workflow_version: "2.1"`, and `setup_cli_version: "2.1"`; all three must be compatible with the installed 2.1 CLI before lifecycle routing proceeds.

Releases progress development → preview → stable. Development may be evaluated only in an explicitly selected development environment; preview is an explicit opt-in before production adoption; stable is the normal adoption channel. Pin the exact schema, workflow, and CLI version required by automation before promotion. A pin holds the selected version across channel changes: moving from development to preview or stable requires an explicit pin change and approval, never an automatic replacement. `update` first proposes a registered versioned migration, and applies it only after explicit approval.

## Backup and rollback

An approved migration creates a validated backup under `.agent-workflow/backups/` before changing configuration. Rollback requires an explicit validated backup target. Migration never automatically moves plans, Beads data, knowledge, review ledgers, worktrees, runtime evidence, archives, or any other repository artifact. Artifact locations are resolved, not migrated.
