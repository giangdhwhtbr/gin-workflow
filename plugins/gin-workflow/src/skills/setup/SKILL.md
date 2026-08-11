---
name: setup
description: Use when a repository needs first-time gin-workflow configuration or explicitly requested setup maintenance.
---

# Setup Skill

Coordinate one setup session outside the lifecycle.

## Initial setup inputs

- repository target
- native harness context, when detected
- user-selected portable settings

Do not require `EffectiveConfig`, `ArtifactRegistry`, `ContextManifest`, or a
durable approval record before initial setup. They are unavailable until
bootstrap completes.

## First-time execution

1. Detect the repository and harness, then collect the desired portable settings.
2. Run `init --dry-run` with the selected harness and `--set` assignments.
3. Present the complete proposed write and obtain explicit native-harness approval.
4. Run one approved `init` with the same harness and assignments. The CLI validates the complete configuration before any write.
5. Report the structured result and stop. Do not invoke `discuss` or any other lifecycle stage.

One `/setup` invocation completes initial repository setup and configuration.
Repeated identical `init` calls are idempotent, but lifecycle stages never call
setup automatically.

## Explicit maintenance

On an initialized repository, select only the maintenance action the user
requested: `detect`, `configure`, `refresh`, `update`, `doctor`, `status`,
`diff`, `rollback`, `export-bundle`, or `verify-bundle`. Present dry-run output
before user-authored configuration changes, upgrades, rollback, or data
movement. After bootstrap, protected mutations use the approval and evidence
capabilities.

The CLI must not prompt, choose policy, or manufacture approval. Optional notifications use the configured notification capability.
