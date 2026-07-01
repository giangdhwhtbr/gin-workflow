# Plan: Migrate to Beads CLI

## Objective
Update the `agent-plugin` workflow to use the standard `bd` CLI for tracking beads (tasks) instead of manually defining and manipulating JSON files in `.planning/beads/`.

## Scope
- In scope: Updating `bead-orchestrator`, `bead-worker`, `executing-plans`, and `progress` commands/skills to use `bd` CLI commands (`bd create`, `bd ready`, `bd list`, `bd status`, etc.).
- Out of scope: Migrating existing `.planning/beads/` JSON files to the `bd` Dolt database.

## Tasks
### Track 1: Update Orchestrator Skill
- **Dependencies**: none
- **Files**: `src/skills/bead-orchestrator/SKILL.md`
- **Acceptance criteria**: The skill instructs agents to use `bd create` to initialize tracks and `bd ready` to dispatch pending work, instead of creating and parsing `.planning/beads/<track-id>.json`.
- **Estimated complexity**: low

### Track 2: Update Worker Skill
- **Dependencies**: none
- **Files**: `src/skills/bead-worker/SKILL.md`
- **Acceptance criteria**: The worker skill correctly instructs the agent to read bead details using `bd show <id> --json` and update status using the `bd` CLI upon completion.
- **Estimated complexity**: low

### Track 3: Update Executing Plans Skill
- **Dependencies**: none
- **Files**: `src/skills/executing-plans/SKILL.md`
- **Acceptance criteria**: References to `.planning/beads/` are replaced with instructions to use the `bd` CLI to select and update tasks.
- **Estimated complexity**: low

### Track 4: Update Progress Command
- **Dependencies**: none
- **Files**: `src/commands/progress.md`
- **Acceptance criteria**: The progress command instructs reading state from `bd list` or `bd ready` instead of parsing files under `.planning/beads/`.
- **Estimated complexity**: low

## Integration
- **Branch**: `migrate-to-beads-cli`
- **Merge strategy**: sequential

## Validation
- [ ] No references to `.planning/beads/` remain in the updated files.
- [ ] Manual verification steps: Run `/progress` and `/orchestrate` (dry-run) to ensure they invoke `bd` commands properly.
