# Plan: Orchestrator CLI boundary (gin-workflow 1.7)

Spec: `.planning/specs/2026-10-20-split-orchestrator-design.md` (release step 1 only).

## Objective
`workflow_core` reaches the worker library (`workflow_providers`) only through a versioned CLI contract, and nothing under `workflow_core/` imports `workflow_providers`. `setup doctor --probe` and `setup models` print exactly what they print today. This makes the later repo split (step 2) a move of one package plus a PATH lookup.

## Model Guidance
- `default_model_class`: `standard_impl`
- `phase_guidance`:
  - `brainstorm`: `high_reasoning`
  - `design`: `high_reasoning`
  - `plan`: `standard_impl`
  - `implement`: `standard_impl`
  - `review`: `high_reasoning`
  - `docs`: `cheap_simple`
- `override_rule`: Use `high_reasoning` for planning only when execution boundaries, dependency sequencing, or major tradeoffs are still unresolved.

## Requirement Analysis
- Problem statement: the lifecycle engine and the worker library share one package tree. `setup_service.py` imports `workflow_providers` directly (`:510`, `:932`), and `worker_scheduler.py`/`review_coordinator.py` sit in `workflow_core` although only `workflow_providers` and tests use them. The library cannot leave the repo while these links exist.
- Success criteria:
  - `grep -rn "workflow_providers" plugins/gin-workflow/src/scripts/workflow_core` prints nothing.
  - `python -m workflow_providers version|health|models --json` prints the contract JSON.
  - `test_doctor_offline_and_opt_in_probe_behavior` and `tests/workflow_providers/test_list_models.py` pass unchanged.
  - A `gin-orchestrator` on PATH with `contract_version` 2 makes `doctor --probe` report `orchestrator_contract_mismatch`.
- Global constraints (from the spec):
  - `workflow_core` imports nothing from `workflow_providers`; the only link is the CLI contract.
  - Every contract command prints one JSON document on stdout and exits 0 on success.
  - Until the split, the commands run as `python -m workflow_providers <command>`; after it, as `gin-orchestrator <command>`.
  - The client checks `contract_version` once per process; a mismatch never falls back to the bundled copy.
  - 1.7 changes no command output.
- Non-goals: the repo split, the reverse imports from `workflow_providers` into `workflow_core`, a `dispatch`/`review` contract, task-tracking default changes, team-mode messages, gin-harness.

## Approach Options
### Option 1: Subprocess contract now, bundled module as the fallback
- Summary: a `__main__` CLI in `workflow_providers`, and a small client in `workflow_core` that prefers `gin-orchestrator` on PATH.
- Pros: proves the exact boundary the split needs; the split becomes a package move.
- Cons: a subprocess per probe (setup only, not a hot path).

### Option 2: Keep in-process imports, behind a lazy import shim
- Summary: one `workflow_core` module wraps the imports.
- Pros: no subprocess.
- Cons: the import stays, so the split still breaks setup; nothing is proven.

### Recommended Approach
- Selected option: Option 1.
- Reasoning: it is the approach the user confirmed (phương án A), and it is the only one that lets the package leave without touching `workflow_core` again.

## Scope
- In scope: `workflow_providers/__main__.py`, `workflow_core/orchestrator_client.py`, the two setup call sites, moving `worker_scheduler.py` and `review_coordinator.py` into `workflow_providers/`, the import-boundary test, `docs/reference/orchestrator-contract.md`.
- Out of scope: everything listed under Non-goals.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Three tracks, each depending on the previous one, all in one package tree.
```

## Tasks

### Track 1: Contract CLI in `workflow_providers`
- **Dependencies**: none
- **Provider role**: `backend`
- **Reasoning**: `medium`
- **Model class**: `standard_impl`
- **Estimated complexity**: low
- **Files**:
  - Create: `plugins/gin-workflow/src/scripts/workflow_providers/__main__.py`
  - Create: `docs/reference/orchestrator-contract.md`
  - Modify: `docs/reference/cli.md` (one line linking the contract page, under the setup section)
  - Test: `tests/workflow_providers/test_contract_cli.py`
- **Interfaces produced**:
  - `python -m workflow_providers version --json` → `{"contract_version": 1, "orchestrator_version": "bundled"}`
  - `python -m workflow_providers health --provider {claude,codex,antigravity,opencode} --executable PATH [--model M] [--effort E] [--workspace DIR] --json` → `{"available": bool, "reason": str}`
  - `python -m workflow_providers models --provider P --json` → the list `native_cli.list_models(P)` returns
  - `workflow_providers.__main__.CONTRACT_VERSION: int = 1`
- **Steps**:
  1. Write `tests/workflow_providers/test_contract_cli.py`, following the header of `tests/workflow_providers/test_list_models.py` for `SCRIPTS`/`sys.path`. A helper runs `subprocess.run([sys.executable, "-m", "workflow_providers", *argv], env={**os.environ, "PYTHONPATH": str(SCRIPTS)}, capture_output=True, text=True)`. Tests:
     - `version --json` exits 0 and prints `{"contract_version": 1, "orchestrator_version": "bundled"}`.
     - `health --provider codex --executable <stub> --json`, where `<stub>` is the same `fake-codex` script `test_doctor_offline_and_opt_in_probe_behavior` writes (`tests/workflow_core/test_setup_cli.py:564`): for `exec --help` it echoes `usage: codex exec --model MODEL --json --ephemeral --dangerously-bypass-approvals-and-sandbox --cd DIR`. Expect `available` true and exit 0.
     - `health --provider codex --executable /nonexistent --json` → `available` false, exit 0.
     - `health --provider nope ...` exits 2 (argparse choices).
     - `models --provider claude --json` prints the same list as `native_cli.list_models("claude")`.
  2. Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests/workflow_providers/test_contract_cli.py`. Expect failure: `No module named workflow_providers.__main__`.
  3. Create `workflow_providers/__main__.py`:
     ```python
     """`python -m workflow_providers`: the orchestrator CLI contract (v1) — version, health, models."""

     from __future__ import annotations

     import argparse
     import json
     from pathlib import Path
     from typing import Any, Sequence

     from .antigravity_worker import antigravity_health
     from .claude_worker import claude_health
     from .codex_worker import codex_health
     from .native_cli import NativeCliRunner, list_models
     from .opencode_worker import opencode_health

     CONTRACT_VERSION = 1
     # ponytail: no own version until the split gives this package its own release
     ORCHESTRATOR_VERSION = "bundled"
     HEALTH = {"claude": claude_health, "codex": codex_health, "antigravity": antigravity_health,
               "opencode": opencode_health}


     def _health(args: argparse.Namespace) -> dict[str, Any]:
         kwargs: dict[str, Any] = {}
         if args.model is not None:
             kwargs = {"model": args.model, "native_runner": NativeCliRunner(), "workspace": args.workspace}
             if args.provider == "codex" and args.effort is not None:
                 kwargs["effort"] = args.effort
         health = HEALTH[args.provider](args.executable, **kwargs)
         return {"available": health.available, "reason": health.reason}


     def main(argv: Sequence[str] | None = None) -> int:
         parser = argparse.ArgumentParser(prog="gin-orchestrator")
         commands = parser.add_subparsers(dest="command", required=True)
         version = commands.add_parser("version")
         health = commands.add_parser("health")
         health.add_argument("--provider", required=True, choices=tuple(HEALTH))
         health.add_argument("--executable", required=True)
         health.add_argument("--model")
         health.add_argument("--effort")
         health.add_argument("--workspace", type=Path)
         models = commands.add_parser("models")
         models.add_argument("--provider", required=True)
         for command in (version, health, models):
             command.add_argument("--json", action="store_true")
         args = parser.parse_args(argv)
         if args.command == "version":
             payload: Any = {"contract_version": CONTRACT_VERSION, "orchestrator_version": ORCHESTRATOR_VERSION}
         elif args.command == "health":
             payload = _health(args)
         else:
             payload = list_models(args.provider)
         print(json.dumps(payload))
         return 0


     if __name__ == "__main__":
         raise SystemExit(main())
     ```
  4. Run the test again. Expect all tests to pass.
  5. Write `docs/reference/orchestrator-contract.md`: the three commands, their arguments and JSON output (copy the Interfaces above), the PATH-then-bundled lookup, and the mismatch rule. Add one line to `docs/reference/cli.md` linking it.
  6. Commit: `feat(providers): add the orchestrator CLI contract (version, health, models)`.
- **Acceptance criteria**:
  - All tests in `test_contract_cli.py` pass.
  - The contract page lists every command and output field the client uses.

### Track 2: `orchestrator_client` and setup switched to it
- **Dependencies**: Track 1
- **Provider role**: `backend`
- **Reasoning**: `medium`
- **Model class**: `standard_impl`
- **Estimated complexity**: medium
- **Files**:
  - Create: `plugins/gin-workflow/src/scripts/workflow_core/orchestrator_client.py`
  - Modify: `plugins/gin-workflow/src/scripts/workflow_core/setup_service.py` (`doctor` probe block, lines 508–566; `models`, lines 929–935)
  - Test: `tests/workflow_core/test_orchestrator_client.py`, `tests/workflow_core/test_setup_cli.py` (one new test)
- **Interfaces consumed**: the Track 1 commands.
- **Interfaces produced**:
  - `class OrchestratorError(Exception)`; `str(error)` is `"orchestrator_contract_mismatch"` or `"orchestrator_failed"`
  - `MISMATCH = "orchestrator_contract_mismatch"`, `FAILED = "orchestrator_failed"`
  - `HEALTH_PROVIDERS: frozenset[str] = frozenset({"claude", "codex", "antigravity", "opencode"})`
  - `health(provider: str, executable: str, *, model: str | None = None, effort: str | None = None, workspace: Path | None = None) -> dict[str, Any]`
  - `models(provider: str) -> list[dict]`
- **Steps**:
  1. Write `tests/workflow_core/test_orchestrator_client.py` (header as in `test_setup_cli.py`). `setUp` calls `orchestrator_client._checked.cache_clear()`. Tests:
     - With no `gin-orchestrator` on PATH, `health("codex", "/nonexistent")` returns `{"available": False, ...}` through the bundled module.
     - A fake `gin-orchestrator` script in a temp dir prepended to `PATH` (via `mock.patch.dict(os.environ, {"PATH": ...})`) that prints `{"contract_version": 2, "orchestrator_version": "x"}` for `version`: `health(...)` raises `OrchestratorError` with `str() == "orchestrator_contract_mismatch"`, and `models("codex")` raises the same.
     - A fake that exits 1 for every command: `health(...)` raises `OrchestratorError("orchestrator_failed")`, and `models("codex")` returns `[]`.
     - A fake that answers `version` with contract 1 and `models` with `[{"id": "m"}]`: `models("codex") == [{"id": "m"}]`, which shows PATH wins over the bundled module.
     - In `tests/workflow_core/test_setup_cli.py`, add `test_doctor_probe_reports_contract_mismatch` next to `test_doctor_offline_and_opt_in_probe_behavior`: `init`, write the same `fake-codex` stub and `providers.local.yaml`, put the version-2 fake `gin-orchestrator` in a temp dir, and call `self.run_cli(repository, "doctor", "--probe", env={**os.environ, "PATH": f"{fake_dir}{os.pathsep}{os.environ['PATH']}"})`. Expect `checks.providers` false and `checks_details.providers["codex.low"]["reason"] == "orchestrator_contract_mismatch"`.

  2. Run it. Expect failure: `No module named workflow_core.orchestrator_client`.
  3. Create `workflow_core/orchestrator_client.py`:
     ```python
     """The orchestrator CLI contract (v1), run as `gin-orchestrator` from PATH or the bundled `python -m workflow_providers`."""

     from __future__ import annotations

     import functools
     import json
     import os
     from pathlib import Path
     import shutil
     import subprocess
     import sys
     from typing import Any

     CONTRACT_VERSION = 1
     MISMATCH = "orchestrator_contract_mismatch"
     FAILED = "orchestrator_failed"
     HEALTH_PROVIDERS = frozenset({"claude", "codex", "antigravity", "opencode"})
     _SCRIPTS = Path(__file__).resolve().parents[1]


     class OrchestratorError(Exception):
         """The orchestrator cannot be used; the message is MISMATCH or FAILED."""


     def _run(argv: list[str], *, timeout: float) -> Any:
         installed = shutil.which("gin-orchestrator")
         command = [installed] if installed else [sys.executable, "-m", "workflow_providers"]
         path = os.pathsep.join(filter(None, (str(_SCRIPTS), os.environ.get("PYTHONPATH"))))
         try:
             done = subprocess.run([*command, *argv, "--json"], capture_output=True, text=True, timeout=timeout,
                                   check=False, env={**os.environ, "PYTHONPATH": path})
             if done.returncode == 0:
                 return json.loads(done.stdout)
         except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
             pass
         raise OrchestratorError(FAILED)


     @functools.cache
     def _checked() -> None:
         version = _run(["version"], timeout=30)
         if not isinstance(version, dict) or version.get("contract_version") != CONTRACT_VERSION:
             raise OrchestratorError(MISMATCH)


     def health(provider: str, executable: str, *, model: str | None = None, effort: str | None = None,
                workspace: Path | None = None) -> dict[str, Any]:
         _checked()
         argv = ["health", "--provider", provider, "--executable", executable]
         for flag, value in (("--model", model), ("--effort", effort), ("--workspace", workspace)):
             if value is not None:
                 argv += [flag, str(value)]
         return _run(argv, timeout=120)


     def models(provider: str) -> list[dict]:
         try:
             _checked()
             return _run(["models", "--provider", provider], timeout=60)
         except OrchestratorError as error:
             if str(error) == MISMATCH:
                 raise
             return []
     ```
     `functools.cache` does not cache a raised error, so a failed check is retried on the next call; only a passing check is remembered.
  4. In `setup_service.py`, replace the probe block (lines 510–566):
     - Delete the five `workflow_providers` imports, `runner = NativeCliRunner()` and `probe_builders`. Keep `from .provider_config import PROVIDER_DEFAULT, PROVIDER_DEFAULT_PROVIDERS`, and add `from . import orchestrator_client` beside it.
     - Replace `builder = probe_builders.get(provider)` / `if builder is None: continue` with `if provider not in orchestrator_client.HEALTH_PROVIDERS: continue`.
     - Replace the two health calls with:
       ```python
       try:
           if provider in PROVIDER_DEFAULT_PROVIDERS and model == PROVIDER_DEFAULT:
               health = orchestrator_client.health(provider, resolved_exe)
           else:
               health = orchestrator_client.health(
                   provider, resolved_exe, model=model, workspace=probe_dir,
                   effort=effort if provider == "codex" else None)
       except orchestrator_client.OrchestratorError as error:
           health = {"available": False, "reason": str(error)}
       ```
       and drop the `probe_kwargs` dict.
     - Replace `health.available` with `health["available"]` and `health.reason` with `health["reason"]`.
  5. Replace `models` (lines 929–935):
     ```python
     def models(repository: Path, *, provider: str | None = None, **_: Any) -> dict[str, Any]:
         if not provider:
             raise SetupError("--provider is required")
         from . import orchestrator_client

         try:
             listed = orchestrator_client.models(provider)
         except orchestrator_client.OrchestratorError as error:
             raise SetupError(str(error)) from error
         return {"status": "listed", "provider": provider, "models": listed, "manual_entry": True, "actions": []}
     ```
  6. Run `test_orchestrator_client.py`, `tests/workflow_core/test_setup_cli.py` and `tests/workflow_providers/test_list_models.py`. Expect all to pass, with `test_doctor_offline_and_opt_in_probe_behavior` unchanged.
  7. Commit: `feat(setup): reach provider health and models through the orchestrator contract`.
- **Acceptance criteria**:
  - `setup_service.py` has no `workflow_providers` import.
  - `doctor --probe` output for the stubbed-codex repository is identical to before (the existing test passes unchanged).
  - A version-2 `gin-orchestrator` on PATH yields `orchestrator_contract_mismatch` in `doctor --probe` and a `SetupError` in `setup models`.

### Track 3: Move the scheduler and review coordinator, enforce the boundary
- **Dependencies**: Track 2
- **Provider role**: `backend`
- **Reasoning**: `low`
- **Model class**: `cheap_simple`
- **Estimated complexity**: low
- **Files**:
  - Move: `plugins/gin-workflow/src/scripts/workflow_core/worker_scheduler.py` → `plugins/gin-workflow/src/scripts/workflow_providers/worker_scheduler.py`
  - Move: `plugins/gin-workflow/src/scripts/workflow_core/review_coordinator.py` → `plugins/gin-workflow/src/scripts/workflow_providers/review_coordinator.py`
  - Move: `tests/workflow_core/test_worker_scheduler.py` → `tests/workflow_providers/test_worker_scheduler.py`
  - Move: `tests/workflow_core/test_review_coordinator.py` → `tests/workflow_providers/test_review_coordinator.py`
  - Modify: `plugins/gin-workflow/src/scripts/workflow_providers/registry.py:431`
  - Modify: `tests/workflow_core/test_end_to_end.py:27,29`
  - Modify: `tests/install_smoke_test.sh:90,93`, `tests/workflow_providers/test_harness_packaging.py:44,47`
  - Test: `tests/workflow_core/test_import_boundary.py`
- **Steps**:
  1. Write `tests/workflow_core/test_import_boundary.py`, in the style of `tests/test_no_direct_bd.py`: for every `*.py` under `plugins/gin-workflow/src/scripts/workflow_core`, collect lines matching `^\s*(from|import)\s+workflow_providers\b` as `path:line`, and assert the list is empty.
  2. Run it. Expect failure listing `worker_scheduler.py:11,12` and `review_coordinator.py:9,21`.
  3. `git mv` both modules and both test files (paths above).
  4. In the moved `worker_scheduler.py`, change `from workflow_providers.contracts` → `from .contracts` and `from workflow_providers.worker_dispatch` → `from .worker_dispatch`.
  5. In the moved `review_coordinator.py`, change `from workflow_providers.contracts` → `from .contracts`, `from workflow_providers.worker_dispatch` → `from .worker_dispatch`, and the four relative core imports to absolute ones: `from workflow_core.assignments import RouteCandidate`, `from workflow_core.identity import AcceptanceIdentity`, `from workflow_core.manifests import ContextRequest, create_context_manifest`, `from workflow_core.models import freeze, thaw`.
  6. `registry.py:431`: `from workflow_core.worker_scheduler import WorkerScheduler` → `from .worker_scheduler import WorkerScheduler`.
  7. In the moved tests and `test_end_to_end.py`, change `workflow_core.worker_scheduler` → `workflow_providers.worker_scheduler` and `workflow_core.review_coordinator` → `workflow_providers.review_coordinator`. Check each moved test's `SCRIPTS`/`ROOT` path still resolves (both test dirs are at the same depth).
  8. In `install_smoke_test.sh` and `test_harness_packaging.py`, change the two `scripts/workflow_core/...` paths to `scripts/workflow_providers/...`.
  9. Run `grep -rn "workflow_core.worker_scheduler\|workflow_core.review_coordinator\|workflow_core/worker_scheduler\|workflow_core/review_coordinator" plugins/gin-workflow/src tests docs`. Expect no output.
  10. Run the full suite: `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests/test_all.py` and `python3 -m unittest discover -s tests`. Expect the same pass count as the baseline plus the new tests, with no failures. Run `bash tests/install_smoke_test.sh` if the baseline ran it cleanly.
  11. Commit: `refactor(providers): move the worker scheduler and review coordinator out of workflow_core`.
- **Acceptance criteria**:
  - `test_import_boundary.py` passes.
  - The full suite passes with no test removed.

## Integration
- **Branch**: `feat/split-orchestrator-spec` (spec and plan already on it; tracks run in a worktree from it)
- **Merge strategy**: sequential

## Validation
- [ ] `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests/test_all.py` passes
- [ ] `python3 -m unittest discover -s tests` passes (CI command)
- [ ] `grep -rn "workflow_providers" plugins/gin-workflow/src/scripts/workflow_core` prints nothing
- [ ] Manual: in a repository with `providers.local.yaml`, `gin-workflow setup doctor --probe --format json` and `gin-workflow setup models --provider codex --format json` print the same JSON as on `master`

## Notes
- Model guidance is planning metadata, not Beads state.
- Concrete providers and models are resolved from machine-local configuration during orchestration; they never belong in this plan.
- The Parent Bead stays open until the human-confirmed merge; track beads close after tests and review pass.
- Release bump to 1.7 happens at ship, not in a track.
