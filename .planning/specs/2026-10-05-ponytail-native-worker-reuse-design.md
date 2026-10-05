# Design: Reuse native worker bridge dispatch construction

Date: 2026-10-05
Status: design option confirmed in conversation on 2026-10-05 (option 1); spec pending user review
Epic: gin-workflow-f7g
Bead and workflow ID: gin-workflow-f7g.3

## Goal and Scope

Remove the duplicated payload factory and cancellable dispatch construction from the three native worker bridges while preserving behavior. Scope is `plugins/gin-workflow/src/scripts/workflow_providers/{codex_worker,claude_worker,antigravity_worker,native_cli}.py` and, only if coverage is missing, `tests/` for those modules. Generated `dist` copies follow the normal build path. Other audit findings have separate scopes. The roughly 50-line saving is an estimate, not an acceptance threshold.

## Architecture

Add two functions to the existing `native_cli.py`:

- `native_worker_payload(request)` returns `{**request.to_payload(), "delegate_to": "subagent-driven-development"}`, replacing the three identical `_payload` functions.
- `native_cancellable_dispatch(native_runner, build_invocation)` returns a `(payload, cancel_event)` callable that runs `build_invocation(worker_prompt(payload))` through `native_runner.run(..., cancel_event=cancel_event)` and returns `direct_worker_result(...)` of the output.

Each adapter keeps its `__init__` signature, `provider_name`, and its `native_dispatch is None and all((native_runner, executable, model, workspace))` guard. Inside the guard it passes a one-argument builder (a lambda over the prompt) that calls its own `build_*_invocation` with `str(executable)`, `str(model)`, `Path(workspace)`, `timeout_seconds`, and, for Codex only, `effort`. `available`, `payload_factory`, and `cancellable_runner` are passed to `SynchronousWorkerAdapter` as today.

No base class, registry, mixin, configuration, or dependency is introduced. `build_*_invocation` and `*_health` functions, `SCOPED_BASH_ALLOWLIST`, and `SynchronousWorkerAdapter` are unchanged. `native_cli.py` already imports from `worker_dispatch` and `worker_dispatch` does not import `native_cli`, so importing `WorkerRequest` there adds no cycle.

## Data Flow and Error Handling

Unchanged: an explicit `native_dispatch` still takes precedence and disables the cancellable path; availability is still true when either is present; the invocation is still built lazily at dispatch time from the payload; cancellation still flows from `SynchronousWorkerAdapter` into `NativeCliRunner.run`; `NativeCliError` and result-contract handling stay in their current owners.

## Testing

Run the existing worker adapter, native CLI, and cancellation tests, then the full Python suite (`PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests/test_all.py`). Before implementation, confirm coverage for each provider's built argv (including Codex effort), `delegate_to` in the payload, `native_dispatch` precedence, availability with missing arguments, and cancel-event propagation; add only the minimal missing checks. Independent provider review is required.

## Out of Scope

Changing provider flags, health probes, model probing, timeouts, result parsing, or adapter public APIs; touching other providers or unused-helper cleanup (gin-workflow-f7g.4).
