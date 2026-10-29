# Orchestrator contract

gin-workflow reaches gin-orchestrator (`plugins/gin-orchestrator`) only through this versioned CLI contract. The commands run as `gin-orchestrator <command> ... --json`; from a checkout, `python -m gin_orchestrator <command>` with both `src/scripts` directories on `PYTHONPATH` is the same CLI. Every command prints one JSON document on stdout and exits 0 on success. This is contract version **2**.

gin-orchestrator imports gin-workflow only through `workflow_core.ext`; see [the plugin README](../../plugins/gin-orchestrator/src/README.md). gin-workflow never imports gin-orchestrator.

## No bundled fallback

gin-workflow runs without gin-orchestrator: every role resolves to the main harness. When `provider_mode: multi` is set, the orchestrator is installed, and it lists the capability a command needs, gin-workflow delegates that command to it. In every other case, and whenever the orchestrator fails, gin-workflow resolves for the main harness. With `provider_mode: multi`, it also prints a warning when the orchestrator is missing, mismatched, or fails. Nothing in gin-workflow contains worker routing.

## `version`

```
version --json
```

```json
{"contract": 2, "orchestrator_version": "0.2.0", "requires_gin_workflow": ">=2.0,<3",
 "capabilities": ["health", "models", "routes", "reviewer", "doctor"]}
```

`capabilities` lists the commands gin-workflow may delegate. `configure` is not listed: it is run by a person through the `providers` skill, never by gin-workflow.

## `health`

```
health --provider {claude,codex,antigravity,opencode} --executable PATH [--model M] [--effort E] [--workspace DIR] --json
```

```json
{"available": true, "reason": "ready"}
```

`available` is whether the provider CLI is usable. `reason` is the short machine-readable explanation (`ready`, `executable_or_help_unavailable`, `required_flags_unverified`, `invalid_model`, and so on). Without `--model` the command only checks the executable and its help text; with `--model` it also probes the model, and `--effort` applies to `codex` only. An unknown provider exits 2 (argparse choices).

## `models`

```
models --provider P --json
```

Prints the list `gin_orchestrator.native_cli.list_models(P)` returns:

```json
[{"id": "opus", "label": "Opus", "description": "alias tracks the latest model", "reasoning_levels": []}]
```

An unknown provider prints `[]`.

## `routes resolve`

```
routes resolve --workflow-id W --tracks FILE --main-harness H [--repository DIR] --json
```

`FILE` is a JSON list of tracks, each with `task_id`, `provider_role`, and `reasoning`. The command resolves every track against `orchestrator.roles` (merged over `routing.roles`) and `.agent-workflow/orchestrator.local.yaml`. It writes nothing; gin-workflow writes the assignment manifest.

```json
{"workflow_id": "W", "main_harness": "H", "routes": [], "diagnostics": []}
```

Each entry of `routes` is the assignment manifest entry of one track (`task_id`, `requested`, `resolved`, `fallback`). A track that cannot be resolved adds a string to `diagnostics` (`<task_id>.<field>: <message>`) and `routes` is then `[]`. The exit code stays 0: a non-zero exit means the orchestrator itself failed, and gin-workflow then falls back to the main harness. `gin-workflow routes resolve` exits 2 when `diagnostics` is not empty.

## `reviewer`

```
reviewer --base B --implementer P [--tier {low,medium,high}] [--repository DIR] --json
```

```json
[{"provider": "codex", "model": "...", "effort": null, "actor_id": "reviewer:codex"}]
```

The routes of the role named by `routing.review.role`, in order. `--tier` defaults to `medium`. Routes on the implementer's provider are dropped when three conditions hold: `routing.review.independence` is not `session`, `require_independent` is not false, and the tier is above `low`. If none are left, all candidates are used when `allow_self_review_fallback` is true, otherwise the list is `[]`. `actor_id` is `reviewer:<provider>`, plus `:session-<8 hex>` when the provider is the implementer's.

## `doctor`

```
doctor [--repository DIR] --json
```

```json
{"providers": {"codex.low": {"available": true, "reason": "ready"}}}
```

The provider report with model probes: one entry per mapped provider and tier, plus missing mappings and executables.

## `configure`

```
configure --set K=V... [--local-set K=V...] [--dry-run] [--approve] [--repository DIR] --json
```

```json
{"status": "configured", "actions": ["update .agent-workflow/config.yaml", "refresh generated configuration"]}
```

`--set` keys must start with `orchestrator.`; anything else exits 2 and writes nothing. `--local-set` keys edit `.agent-workflow/orchestrator.local.yaml`. The command validates the candidate configuration first. `--dry-run` prints the actions (`status: would_configure`) and writes nothing. Without `--dry-run`, `--approve` is required. The command first runs `gin-workflow setup configure --set ... --approve`, which writes the portable keys and refreshes the effective configuration. Only after that succeeds does it write `orchestrator.local.yaml` atomically and add it to `.agent-workflow/.gitignore`, so a rejected portable change leaves the local file untouched.

## Errors

Errors exit 2 with `error: <message>` on stderr, except the launcher's own three, which exit 1:

- `error: gin-workflow is not on PATH; install it with ./install.sh --plugin gin-orchestrator`
- `error: gin-workflow paths failed; reinstall with ./install.sh --plugin gin-orchestrator`
- `error: gin-workflow facade EXT_VERSION <n>; this gin-orchestrator supports 1`

## Lookup and mismatch rule

The client (`workflow_core.orchestrator_client`) looks for `gin-orchestrator` on `PATH`. If it is absent, the client reports `orchestrator_missing`.

Before any other command the client checks `version` once per process. A `contract` that differs from the client's own constant reports `orchestrator_contract_mismatch`; a command that cannot be run or parsed reports `orchestrator_failed`. A command missing from `capabilities` is not delegated. With `provider_mode: multi`, gin-workflow turns each reason into a warning and resolves for the main harness instead.
