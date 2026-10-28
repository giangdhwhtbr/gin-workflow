# gin-orchestrator

Worker harnesses for gin-workflow: route roles and reasoning tiers to other agent harnesses. gin-workflow runs the whole lifecycle with one main harness; this add-on only matters when you want another harness to run some of the work.

## Install

From a gin-workflow clone:

```bash
./install.sh --plugin gin-orchestrator
```

This installs gin-workflow first when its launcher is missing, then the `gin-orchestrator` launcher under `~/.local/lib/gin-orchestrator/<version>` with a link at `~/.local/bin/gin-orchestrator`. On Windows use `.\install.ps1 -Plugin gin-orchestrator`. `--plugin all` installs gin-workflow, gin-qa, and gin-orchestrator.

## Dependency on gin-workflow

The launcher asks `gin-workflow paths --json` for gin-workflow's library directory and imports gin-workflow's facade, `workflow_core.ext`, from there. This add-on imports nothing else from gin-workflow. If `gin-workflow` is not on `PATH`, the launcher exits 1 with `error: gin-workflow is not on PATH; install it with ./install.sh --plugin gin-orchestrator`.

The facade carries `EXT_VERSION`. A change that removes a name or alters a signature raises it, and the launcher exits 1 when it differs from the version this add-on supports (`error: gin-workflow facade EXT_VERSION <n>; this gin-orchestrator supports 1`). The add-on requires gin-workflow `>=2.0,<3`.

The worker library creates and removes worktrees through `workflow_core.ext.create_worktree` and `cleanup_worktree`, the same code as `gin-workflow worktree`.

## Contract

gin-workflow calls `gin-orchestrator <command> ... --json` (contract version 2; full reference in [orchestrator-contract.md](../../../docs/reference/orchestrator-contract.md)).

| Command | Output |
|---|---|
| `version` | contract, add-on version, required gin-workflow range, capabilities |
| `health` | whether a provider CLI is usable |
| `models` | the models a provider offers |
| `routes resolve` | routes for plan tracks, and diagnostics for tracks that cannot be resolved |
| `reviewer` | ordered reviewer routes with `actor_id` |
| `doctor` | provider tier report with model probes |
| `configure` | validates and writes `orchestrator.*` configuration |

## Configuration

Worker routing lives under `orchestrator:` in `.agent-workflow/config.yaml`; gin-workflow passes that section through without validating it. Machine-local executables and models live in `.agent-workflow/orchestrator.local.yaml`, which is not committed. See `examples/orchestrator.local.example.yaml`.

## Skill

`/gin-orchestrator:providers` asks which harnesses may run work, a model per tier, preferred and fallback harnesses per role and tier, concurrency, and limits. It previews the change with `gin-orchestrator configure --dry-run`, applies it after approval, turns on `provider_mode: multi`, and probes each provider with `gin-workflow setup doctor --probe`.
