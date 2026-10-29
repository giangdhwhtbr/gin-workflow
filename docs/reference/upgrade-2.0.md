# Upgrading to gin-workflow 2.0

For the 2.1 changes (Telegram off by default, `gin-workflow goal`), see [upgrading to 2.1](upgrade-2.1.md).

gin-workflow 2.0 runs the whole lifecycle in one main harness with no required external tool. Two things moved out of the core:

- worker harness routing now belongs to the [gin-orchestrator](../orchestrator/README.md) extension, and its configuration sits under `orchestrator:` (schema 2.8);
- task tracking defaults to local Markdown files; Beads (`bd`) is optional.

## What changed

`gin-workflow setup update --to-version 2.8 --approve` makes these changes to a 2.7 repository:

| Before (2.7) | After (2.8) |
|---|---|
| `concurrency`, `queue`, `worker`, and `circuit_breaker` under `routing:` | The same keys under `orchestrator:` |
| A role in `routing.roles` that names a worker provider | The role under `orchestrator.roles`, and `{preferred: [main_harness]}` in `routing.roles` so plans keep validating |
| `provider_mode` and `routing.review.independence` unset | `provider_mode: multi` and `routing.review.independence: provider`, when `orchestrator:` is not empty |
| `providers.task_tracking` unset | `providers.task_tracking: beads`, so an existing Beads repository keeps working |
| `.agent-workflow/providers.local.yaml` | `.agent-workflow/orchestrator.local.yaml`, unless that file already exists |
| `schema_version`, `workflow_version`, and `setup_cli_version` at `2.7` | All three at `2.8` |

## Steps

1. Reinstall gin-workflow on each machine:

   ```bash
   ./install.sh --platform all
   ```

2. Migrate each repository's configuration. Run this in the repository (add `--dry-run` first to preview):

   ```bash
   gin-workflow setup update --to-version 2.8 --approve
   ```

   It writes a validated backup to `.agent-workflow/backups/<timestamp>-2.7-to-2.8/`, then makes the changes listed in [What changed](#what-changed).

3. Keep worker harnesses. If the repository routed work to other harnesses, install the extension, then check the providers:

   ```bash
   ./install.sh --plugin gin-orchestrator
   gin-workflow setup doctor --probe
   ```

   With `provider_mode: multi` and no gin-orchestrator, every route stays on the main harness and `gin-workflow state` warns ([troubleshooting](troubleshooting.md#orchestrator_missing-orchestrator_contract_mismatch-or-orchestrator_failed)).

4. Without migrating, the repository keeps its 2.7 configuration. Tasks use Markdown files under `.planning/tasks/` instead of the existing Beads database. `gin-workflow setup doctor` warns when a `.beads` directory exists and `providers.task_tracking` is unset, and when worker routing keys are still under `routing:`.

## Rollback

`gin-workflow setup rollback` restores `.agent-workflow/config.yaml` from a backup that `setup update` wrote, after checking the backup's SHA-256 hash and version:

```bash
gin-workflow setup rollback --backup <path>
```

`<path>` is the backup directory, absolute or relative to `.agent-workflow/backups/`; `setup update --format json` prints it as `backup`. When the restored version is not 2.8, rollback also renames `orchestrator.local.yaml` back to `providers.local.yaml`. Add `--dry-run` to preview.

## What does not change

Migrations change configuration only; plans, Beads data, review ledgers, and worktrees stay where they are ([configuration](config.md#versions-and-migration)).
