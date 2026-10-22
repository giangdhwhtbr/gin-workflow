# Orchestrator contract

`workflow_core` reaches the worker library (`gin_orchestrator`, in `plugins/gin-orchestrator`) only through this versioned CLI contract. The commands run as `gin-orchestrator <command>`; from a checkout, `python -m gin_orchestrator <command>` with both `src/scripts` directories on `PYTHONPATH` is the same CLI. Every command prints one JSON document on stdout and exits 0 on success.

`gin_orchestrator.cli.CONTRACT_VERSION` is `1`.

## `version`

```
version --json
```

```json
{"contract_version": 1, "orchestrator_version": "bundled"}
```

`orchestrator_version` is `"bundled"` while the package ships inside this repository; it gets its own release version after the split.

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

## Lookup and mismatch rule

The client (`workflow_core.orchestrator_client`) looks for `gin-orchestrator` on `PATH`. If it is absent, the client raises `orchestrator_missing`; `models` then returns `[]`.

Before any other command the client checks `version` once per process and compares `contract_version` with its own constant. A mismatch raises `orchestrator_contract_mismatch` and never falls back; a command that cannot be run or parsed raises `orchestrator_failed`. Only a passing check is cached, so a failed check is retried on the next call.
