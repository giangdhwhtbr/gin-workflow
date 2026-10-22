# Upgrading to gin-workflow 2.0

gin-workflow 2.0 runs the whole lifecycle in one main harness with no required external tool. Two things moved out of the core:

- worker harness routing now belongs to the [gin-orchestrator](../orchestrator/README.md) extension, and its configuration sits under `orchestrator:` (schema 2.8);
- task tracking defaults to local Markdown files; Beads (`bd`) is optional.

## Steps

1. **Reinstall** gin-workflow on each machine:

   ```bash
   ./install.sh --platform all
   ```

2. **Migrate each repository's configuration.** Run this in the repository (add `--dry-run` first to preview):

   ```bash
   gin-workflow setup update --to-version 2.8 --approve
   ```

   It writes a validated backup to `.agent-workflow/backups/`, then:
   - moves `concurrency`, `queue`, `worker`, `circuit_breaker`, and the roles that name worker providers from `routing` to `orchestrator:`; a moved role stays in `routing.roles` as `{preferred: [main_harness]}` so plans keep validating;
   - when it moved anything, sets `provider_mode: multi` and `routing.review.independence: provider` if they were unset;
   - sets `providers.task_tracking: beads` when unset, so an existing Beads repository keeps working;
   - renames `.agent-workflow/providers.local.yaml` to `orchestrator.local.yaml`;
   - sets the schema, workflow, and setup versions to `2.8`.

   To undo it, pass the `backup` path the update printed: `gin-workflow setup rollback --backup <path>`. The rename is reversed too.

3. **Keep worker harnesses.** If the repository routed work to other harnesses, install the extension, then check the providers:

   ```bash
   ./install.sh --plugin gin-orchestrator
   gin-workflow setup doctor --probe
   ```

   With `provider_mode: multi` and no gin-orchestrator, every route stays on the main harness and `gin-workflow state` warns ([troubleshooting](troubleshooting.md#orchestrator-errors-and-warnings-orchestrator_missing-orchestrator_contract_mismatch-orchestrator_failed)).

4. **Without migrating**, the repository keeps its 2.7 configuration. Tasks use Markdown files under `.planning/tasks/` rather than the existing Beads database, and `gin-workflow setup doctor` warns when a `.beads` directory exists and `providers.task_tracking` is unset.

## What does not change

Migrations change configuration only; plans, Beads data, review ledgers, and worktrees stay where they are ([configuration](config.md#versions-and-migration)).
