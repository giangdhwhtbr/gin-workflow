# Plan: Reuse native worker bridge dispatch construction

## Goal

Remove the duplicated payload factory and cancellable dispatch construction from the three native worker bridges while preserving behavior. Scope is `plugins/gin-workflow/src/scripts/workflow_providers/{codex_worker,claude_worker,antigravity_worker,native_cli}.py` and, only if coverage is missing, `tests/` for those modules. Generated `dist` copies follow the normal build path. Other audit findings have separate scopes. The roughly 50-line saving is an estimate, not an acceptance threshold.

## Architecture

Add two functions to the existing `native_cli.py`:

- `native_worker_payload(request)` returns `{**request.to_payload(), "delegate_to": "subagent-driven-development"}`, replacing the three identical `_payload` functions.
- `native_cancellable_dispatch(native_runner, build_invocation)` returns a `(payload, cancel_event)` callable that runs `build_invocation(worker_prompt(payload))` through `native_runner.run(..., cancel_event=cancel_event)` and returns `direct_worker_result(...)` of the output.

Each adapter keeps its `__init__` signature, `provider_name`, and its `native_dispatch is None and all((native_runner, executable, model, workspace))` guard. Inside the guard it passes a one-argument builder (a lambda over the prompt) that calls its own `build_*_invocation` with `str(executable)`, `str(model)`, `Path(workspace)`, `timeout_seconds`, and, for Codex only, `effort`. `available`, `payload_factory`, and `cancellable_runner` are passed to `SynchronousWorkerAdapter` as today.

## Tech Stack

Python 3 standard library, existing `unittest` suite. No new dependencies.

## Global Constraints

No base class, registry, mixin, configuration, or dependency is introduced. `build_*_invocation` and `*_health` functions, `SCOPED_BASH_ALLOWLIST`, and `SynchronousWorkerAdapter` are unchanged. `native_cli.py` already imports from `worker_dispatch` and `worker_dispatch` does not import `native_cli`, so importing `WorkerRequest` there adds no cycle.

Unchanged: an explicit `native_dispatch` still takes precedence and disables the cancellable path; availability is still true when either is present; the invocation is still built lazily at dispatch time from the payload; cancellation still flows from `SynchronousWorkerAdapter` into `NativeCliRunner.run`; `NativeCliError` and result-contract handling stay in their current owners.

Out of scope: changing provider flags, health probes, model probing, timeouts, result parsing, or adapter public APIs; touching other providers or unused-helper cleanup (gin-workflow-f7g.4).

## Model Guidance

- `default_model_class`: `standard_impl`
- `phase_guidance`: brainstorm/design/review `high_reasoning`; plan/implement/verify `standard_impl`; docs `cheap_simple`.
- `override_rule`: use `high_reasoning` only if execution boundaries or major tradeoffs become unresolved.

## Requirement Analysis

- Problem: three adapters repeat an identical `_payload` and an identical nested `cancellable_dispatch` that differ only in the invocation builder call.
- Success: one payload factory and one dispatch constructor in `native_cli.py`; adapters keep public signatures and behavior; adapter tests and full Python suite pass; independent review approves.
- Constraints: Global Constraints above.
- Non-goals: other audit findings, provider behavior changes, new abstractions.

## Approach Options

1. Shared payload factory and dispatch constructor in `native_cli.py` taking an invocation-builder callable: selected by the user.
2. Share only the payload factory: less indirection but leaves the principal duplication. Not selected.

## Scope and File Map

Spec: `.planning/specs/2026-10-05-ponytail-native-worker-reuse-design.md`.
Audit epic: `gin-workflow-f7g`. Parent deliverable and workflow ID for this plan: `gin-workflow-f7g.3`.

| File | Responsibility | Track |
|---|---|---|
| plugins/gin-workflow/src/scripts/workflow_providers/native_cli.py | Shared payload factory and cancellable dispatch constructor | 1 |
| plugins/gin-workflow/src/scripts/workflow_providers/codex_worker.py | Codex adapter uses shared helpers | 1 |
| plugins/gin-workflow/src/scripts/workflow_providers/claude_worker.py | Claude adapter uses shared helpers | 1 |
| plugins/gin-workflow/src/scripts/workflow_providers/antigravity_worker.py | Antigravity adapter uses shared helpers | 1 |
| tests/workflow_providers/test_worker_adapters.py | Two minimal missing characterization checks | 1 |

Coverage already present in `tests/workflow_providers/test_worker_adapters.py` at `b328c5b`: per-provider argv/model/timeout via native runner (lines 81–112), Codex effort (114–137), real-process cancellation through the Claude adapter (140–191), unavailable with no arguments (246–256), `delegate_to` via `native_dispatch` (258–277). Missing: `delegate_to` reaching the native-runner prompt, and `native_dispatch` precedence when a runner is also supplied. Only those two checks are added. `_payload` has no importers outside its own module (checked with grep across `plugins/` and `tests/`). `plugins/*/dist/` is gitignored and is not committed.

The Parent Bead `gin-workflow-f7g.3` stays open until human-confirmed integration. The track bead closes after its tests and independent review pass. Epic `gin-workflow-f7g` is not closed by this plan.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: One bounded Python refactor track with no independent parallel work.
```

## Tasks

### Track 1: Share native worker payload and dispatch construction

- **Dependencies**: none.
- **Provider role**: `backend`.
- **Reasoning**: `medium`.
- **Model guidance**: `standard_impl`.
- **Review routing**: role `review`, reasoning `high`, model class `high_reasoning`; resolve a different provider under the active independence policy.
- **Estimated complexity**: low.
- **Files**: modify `native_cli.py:17–22,128–158` (imports; add after `direct_worker_result`), `codex_worker.py:1–142`, `claude_worker.py:1–140`, `antigravity_worker.py:1–128` (imports, `_payload`, adapter `__init__`); test `tests/workflow_providers/test_worker_adapters.py:81–112,258–277`.
- **Interfaces**:
  - Produces `native_worker_payload(request: WorkerRequest) -> Mapping[str, object]`.
  - Produces `native_cancellable_dispatch(native_runner: NativeCliRunner, build_invocation: Callable[[str], NativeCliInvocation]) -> Callable[[Mapping[str, object], threading.Event], Mapping[str, object]]`.
  - Consumes unchanged `worker_prompt`, `direct_worker_result`, `NativeCliRunner.run(invocation, *, cancel_event=None)`, `build_codex_invocation`, `build_claude_invocation`, `build_antigravity_invocation`, `SynchronousWorkerAdapter.__init__(runner, *, available, payload_factory, cancellable_runner)`.
  - Removes module-private `_payload` from the three worker modules.
- **Acceptance criteria**: three adapters use both shared helpers; signatures, availability, precedence, effort, timeout, cancellation unchanged; adapter tests and full suite pass; `git diff --check` clean; independent review approves.

1. Add characterization checks before production edits. In `test_native_adapters_build_model_specific_invocations_and_normalize_output`, after the existing timeout assertion, add:

   ```python
                invocation = runner.invocations[0]
                prompt = (
                    invocation.argv[invocation.argv.index("--print") + 1]
                    if adapter_type == AntigravityWorkerAdapter
                    else invocation.stdin.decode("utf-8")
                )
                self.assertIn('"delegate_to": "subagent-driven-development"', prompt)
   ```

   `NativeCliInvocation.stdin` is `bytes` (`native_cli.py:28–33`); `worker_prompt` uses `json.dumps` default separators, so the key/value appear exactly as asserted. In `test_native_adapters_normalize_without_provider_model_or_methodology_duplication`, construct the adapter with a runner that must not be called, so precedence is covered by the existing assertions:

   ```python
            class UnusedRunner:
                def run(self, invocation, *, cancel_event=None):
                    raise AssertionError("native_dispatch must take precedence over native_runner")

            with self.subTest(adapter=adapter_type.__name__):
                adapter = adapter_type(
                    native_dispatch=native_dispatch,
                    native_runner=UnusedRunner(),
                    executable="native",
                    model="model",
                    workspace=Path.cwd(),
                )
   ```

   Run `PYTHONPATH=plugins/gin-workflow/src/scripts:tests python3 -m unittest tests.workflow_providers.test_worker_adapters -v` from the repo root (baseline at `b328c5b`: 12 tests OK). Expect all pass: these characterize existing behavior, so do not manufacture a failure. If one fails, determine whether the fixture is wrong before touching production code; behavior fixes are out of scope.

2. In `native_cli.py`, change `from typing import Callable` to keep `Callable` and change `from .worker_dispatch import _SECRET_VALUE` to `from .worker_dispatch import _SECRET_VALUE, WorkerRequest`. Add `import threading` only if not already imported (it is, line 14). After `direct_worker_result`, add:

   ```python
   def native_worker_payload(request: WorkerRequest) -> Mapping[str, object]:
       return {**request.to_payload(), "delegate_to": "subagent-driven-development"}


   def native_cancellable_dispatch(
       native_runner: "NativeCliRunner",
       build_invocation: Callable[[str], NativeCliInvocation],
   ) -> Callable[[Mapping[str, object], threading.Event], Mapping[str, object]]:
       def dispatch(payload: Mapping[str, object], cancel_event: threading.Event) -> Mapping[str, object]:
           invocation = build_invocation(worker_prompt(payload))
           return direct_worker_result(native_runner.run(invocation, cancel_event=cancel_event))
       return dispatch
   ```

   The module has `from __future__ import annotations`, so the forward reference to `NativeCliRunner` (defined later in the file) may be written unquoted; match surrounding style.

3. In each worker module, delete `_payload`, drop `direct_worker_result` and `worker_prompt` from the `native_cli` import, add `native_cancellable_dispatch` and `native_worker_payload`, and drop `WorkerRequest` from the `worker_dispatch` import if no longer used. Replace the nested `def cancellable_dispatch` block. Codex:

   ```python
           cancellable_dispatch = None
           if native_dispatch is None and all((native_runner, executable, model, workspace)):
               cancellable_dispatch = native_cancellable_dispatch(
                   native_runner,
                   lambda prompt: build_codex_invocation(
                       str(executable),
                       str(model),
                       Path(workspace),
                       prompt,
                       timeout_seconds=timeout_seconds,
                       effort=effort,
                   ),
               )
           super().__init__(
               native_dispatch,
               available=native_dispatch is not None or cancellable_dispatch is not None,
               payload_factory=native_worker_payload,
               cancellable_runner=cancellable_dispatch,
           )
   ```

   Claude and Antigravity are identical except they call `build_claude_invocation` / `build_antigravity_invocation` and omit `effort=effort`. Keep `Any`, `Callable`, `Mapping`, `WorkerResult` imports only while still referenced by the `native_dispatch` annotation.

4. Run `grep -rn "_payload\b" plugins/gin-workflow/src/scripts/workflow_providers/{codex,claude,antigravity}_worker.py`; expect no output. Run `python3 -m py_compile` on the four modules; expect no output. pyflakes is not installed, so check unused imports by grepping each name dropped or kept in step 3 against its module body. Re-run the adapter test command from step 1; expect all pass. Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests/test_all.py`; expect exit 0 and record actual counts and skips (baseline 836 tests, 3 skipped). Run `git diff --check`; expect no output. Obtain independent review, then commit only the five track files on the feature branch.

## Integration

- **Branch**: `chore/ponytail-audit-f7g`.
- **Merge strategy**: sequential; no merge or PR without explicit user authorization.
- Do not commit generated `dist` output.

## Validation and Traceability

| Spec requirement | Evidence |
|---|---|
| Shared `native_worker_payload` replaces three `_payload` | Step 3 diff, step 4 grep, `delegate_to` assertions in both dispatch paths |
| Shared `native_cancellable_dispatch` with invocation builder | Step 2–3 diff; native-runner argv/model/timeout test |
| Codex effort preserved | `test_codex_adapter_passes_reasoning_effort_configuration` |
| `native_dispatch` precedence | Strengthened normalize test with unused runner |
| Availability unchanged | `test_native_adapters_detect_missing_harness_support` |
| Cancellation unchanged | `test_started_native_worker_can_be_cancelled_and_process_is_terminated` |
| No new abstraction, dependency, or cycle | Scoped diff review; import succeeds in full suite |

## Approval

Status: awaiting explicit user approval of this plan. Once approved, record `plan-approved` with workflow ID `gin-workflow-f7g.3` and this file as evidence. Stop before orchestration.
