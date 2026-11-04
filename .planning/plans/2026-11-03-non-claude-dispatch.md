# Plan: Non-Claude Main Harness Dispatch & Cost-Control Wiring

## Objective

When Codex, Antigravity, OpenCode, or Copilot is the main harness, tracks, reviews, and explorations run on workers at the catalog model and effort instead of in the main session. Register GitHub Copilot (`copilot`) as a first-class harness and CLI worker, translate `agents/*.md` across all five platforms in `install.sh` and `install.ps1`, unify timeout/retry/queue/circuit-breaker defaults in `ORCHESTRATOR_DEFAULTS`, open the circuit breaker immediately on the first `QUOTA` or `AUTH` failure, restrict retries to transient provider failures (`quota`, `rate_limit`, `service`) while forwarding `prior_changed_files`, and expose `gin-orchestrator dispatch` so stage skills can dispatch work at the resolved route across all harnesses.

- **Architecture:** `workflow_core` owns portable catalog and schema definitions (`DEFAULT_CATALOGS["copilot"] = Catalog(("provider_default",), ())`, `PROVIDER_DEFAULT_PROVIDERS`, `CONFIG_SCHEMA`); `gin_orchestrator` owns native CLI worker adapters (`CopilotWorkerAdapter`, `copilot_health`, `build_copilot_invocation`), agent name mapping in `ProviderRegistry`, resilience policies (`ORCHESTRATOR_DEFAULTS`, `IMMEDIATE_OPEN_FAILURE_KINDS`, `TRANSIENT_FAILURE_BLOCKERS`, `run_with_retries`), and the `gin-orchestrator dispatch` CLI subcommand; `install.sh` and `install.ps1` translate canonical Antigravity agent files (`plugins/*/src/agents/*.md`) into each target harness's layout; and stage skills (`execute`, `review`, `discuss`, `plan`, `tech-doc`) apply the hybrid dispatch rule within the 12,000-character stage token budget.
- **Tech Stack:** Python 3.11+ (`unittest`, `dataclasses`, `subprocess`, `shutil`, `types.MappingProxyType`), Bash (`install.sh`), PowerShell (`install.ps1`), Markdown skills and reference documentation.
- **Source Spec:** `.planning/specs/2026-11-03-non-claude-dispatch-design.md` (`Epic: gin-workflow-dura`).

## Global Constraints

- **Backward compatibility with existing `config.yaml`**: Adding `"copilot"` to `SUPPORTED_HARNESSES`, `DEFAULT_CATALOGS`, and `CONFIG_SCHEMA` is purely additive; existing v2.9 configs for `claude`, `codex`, `antigravity`, and `opencode` continue to validate without migration.
- **Default worker timeout preserved at `900.0` seconds**: `ORCHESTRATOR_DEFAULTS["worker"]["timeout_seconds"]` is set to `900.0` to match the existing runtime default in `registry.py:250` and all worker adapters.
- **Behavior change on `timeout` retries**: Previously `WorkerScheduler._run()` retried any failure where `retry_safe=True` (including `timeout` when cancellation succeeded quiescently). Per epic `gin-workflow-dura`, retries are now restricted to `quota`, `rate_limit`, and `service` failures; `timeout` is no longer retried automatically.
- **Circuit breaker state compatibility**: Existing `.agent-workflow/runtime/circuit-breakers.json` files remain compatible; only the transition condition for `QUOTA` and `AUTH` changes to immediate `OPEN`.
- **Token budget enforcement**: All edits to `SKILL.md` and `references/*.md` must keep every stage chain in `STAGES` `<= 12,000` characters and every agent file `<= 4,000` characters.

## Route Rubric

- Choose the weakest model that can do the work.
- Raise the model for broad context or design judgement.
- Raise the effort for intrinsic difficulty: intricate logic, many edge cases, or long chains of steps.

| Kind of work | Model | Effort |
|---|---|---|
| Mechanical edits, documentation, boilerplate | weakest | `low` |
| Bounded implementation with a clear spec | middle | `medium` |
| Cross-module change, security, migration, concurrency | strongest | `high` |

Unclear requirements never raise the model or effort.

## Requirement Analysis

- Problem statement: Non-Claude main harnesses (`codex`, `antigravity`, `opencode`, `copilot`) cannot pass per-spawn catalog `model` and `effort` arguments through Claude Code's native `Agent` tool, `copilot` is not yet registered in `SUPPORTED_HARNESSES` or `gin_orchestrator` workers, `install.sh` / `install.ps1` drop `agents/*.md` for `opencode` and `copilot` and leave `tools:` in `codex`, and cost-control defaults/retries/circuit-breaker rules need to be unified and wired into worker dispatch.
- Success criteria:
  - All US-1, US-2, and US-3 acceptance criteria in `.planning/specs/2026-11-03-non-claude-dispatch-design.md` pass automated verification.
  - `python3 tests/test_all.py` and `bash tests/install_smoke_test.sh` pass with zero errors.
- Constraints:
  - Stage skill chains must remain `<= 12,000` characters (`tests/workflow_core/test_token_budget.py`).
  - Docs under `docs/` must pass `workflow_core.docs_check.style_violations` (`tests/workflow_core/test_docs_coverage.py`).
  - Direct-mode `gin-orchestrator dispatch` in `execute` stage must enforce worktree root safety so implementation workers never mutate the main checkout.
- Non-goals:
  - Redesigning the schema 2.9 model catalog structure (`Catalog(models, efforts)` and rank-mapping rules from `gin-workflow-btt3`).
  - Changing Claude Code same-harness `Agent` dispatch behavior (shipped in `gin-workflow-btt3`).
  - Multi-process shared semaphore locking for `concurrency` or `CircuitBreakerStore` across separate OS processes.

## Approach Options

### Option 1: Five Bounded Tracks Split by Package and Subsystem
- Summary: Split `workflow_core` Copilot registration (Track 1), `gin_orchestrator` Copilot worker + `effort`/`agent` pass-through (Track 2), installer agent translation (Track 3), resilience/cost-control wiring (Track 4), and `gin-orchestrator dispatch` CLI + stage skills + docs (Track 5).
- Pros: Each track stays small (4–12 files) with an isolated test cycle; Track 1 and Track 3 have no dependencies and disjoint file scopes so they can run in parallel; Track 5 depends on both Track 3 and Track 4 so docs and CLI tests verify the complete behavior.
- Cons: Five tracks instead of four.

### Option 2: Monolithic Single-Track Implementation
- Summary: Combine `workflow_core`, `gin_orchestrator`, installers, stage skills, and docs into one large track.
- Pros: No inter-track dependencies.
- Cons: Violates track-sizing rules (~48 files across two plugins, shell/PowerShell installers, skills, and docs) and cannot be reviewed or rejected modularly.

### Recommended Approach
- Selected option: Option 1 (Five Bounded Tracks Split by Package and Subsystem).
- Rationale: Keeps each track focused on one cohesive subsystem with its own unit test suite and zero file overlap between parallel tracks.

## Scope

- In scope:
  - R1: Copilot harness registration in `workflow_core` and `copilot_worker.py` + `effort`/`agent` pass-through in `gin_orchestrator`.
  - R2: Agent translation in `install.sh` and `install.ps1` for `antigravity`, `codex`, `opencode`, and `copilot`.
  - R3: `ORCHESTRATOR_DEFAULTS` consolidation, immediate circuit breaker `OPEN` on `QUOTA`/`AUTH`, and `run_with_retries()` with `TRANSIENT_FAILURE_BLOCKERS` and `prior_changed_files`.
  - R4: `gin-orchestrator dispatch` CLI subcommand, stage skill hybrid dispatch updates within token budget, and documentation updates.
- Out of scope:
  - Changes to schema 2.9 `Catalog` rank-mapping rules.
  - Changes to Claude Code native `Agent` same-harness dispatch.
  - Cross-process file locking for `concurrency` semaphores.

## Execution Strategy

```yaml
execution_strategy:
  mode: worker
  workers:
    mode: parallel
  rationale: Track 1 (workflow_core Copilot registration) and Track 3 (installer agent translation) have no dependencies and touch completely disjoint files; Track 2, Track 4, and Track 5 follow explicit dependency edges without overlapping active tracks.
```

## Tasks

### Track 1: Register Copilot Harness in `workflow_core`
- **Dependencies**: none
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/catalog.py:14-19`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/provider_config.py:10-18`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/configuration.py:245-250`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/schemas.py:94-98`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/assignments.py:45-50`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/cli.py:30-48`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/project_detect.py:201-203`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/setup_service.py:150-156`
  - Test `tests/workflow_core/test_catalog.py`
  - Test `tests/workflow_core/test_provider_config.py`
  - Test `tests/workflow_core/test_project_detect.py`
  - Test `tests/workflow_core/test_configuration.py`
- **Provider role**: `backend`
- **Model:** `haiku`
- **Effort:** `low`
- **Why:** Mechanical registration of `"copilot"` across `workflow_core` constants, schema enums, CLI choices, and setup detection with clear, bounded locations.
- **Interfaces**:
  - Produces `DEFAULT_CATALOGS["copilot"] = Catalog(("provider_default",), ())` in `workflow_core.catalog`.
  - Produces `DEFAULT_EXECUTABLES["copilot"] = "copilot"` and `PROVIDER_DEFAULT_PROVIDERS = frozenset({"antigravity", "opencode", "copilot"})` in `workflow_core.provider_config`.
- **Acceptance criteria**:
  - `"copilot"` is in `SUPPORTED_HARNESSES`, `DEFAULT_CATALOGS`, `DEFAULT_EXECUTABLES`, `PROVIDER_DEFAULT_PROVIDERS`, and `CONFIG_SCHEMA["properties"]["models"]["propertyNames"]["enum"]`.
  - `RouteCandidate("copilot", "provider_default", False)` succeeds without raising `AssignmentResolutionError`, and the error message for unsupported `provider_default` providers reads `"provider_default is only supported for antigravity, opencode, and copilot"`.
  - `detect_project()` includes `"copilot"` in `result["providers"]`, and `setup_service.detect()` checks `("copilot", ".github/agents")`.
- **Estimated complexity**: low

#### Steps

- [ ] **Step 1: Add failing tests in `tests/workflow_core/test_catalog.py`, `test_provider_config.py`, `test_project_detect.py`, and `test_configuration.py`**
  - In `tests/workflow_core/test_catalog.py`, update `test_default_catalogs_match_spec` to include `"copilot"`:
    ```python
    self.assertEqual(
        DEFAULT_CATALOGS["copilot"],
        Catalog(("provider_default",), ()),
    )
    self.assertFalse(supports_effort("copilot"))
    ```
  - In `tests/workflow_core/test_provider_config.py`, assert `"copilot"` in `DEFAULT_EXECUTABLES`, `PROVIDER_DEFAULT_PROVIDERS`, and `RouteCandidate`:
    ```python
    self.assertEqual(DEFAULT_EXECUTABLES["copilot"], "copilot")
    self.assertIn("copilot", PROVIDER_DEFAULT_PROVIDERS)
    self.assertEqual(
        RouteCandidate("copilot", "provider_default", False).selection_mode,
        "provider_default",
    )
    ```
    And update any assertion matching `"provider_default is only supported for antigravity and opencode"` to `"provider_default is only supported for antigravity, opencode, and copilot"`.
  - In `tests/workflow_core/test_project_detect.py:82`, update the expected `result["providers"]` dict:
    ```python
    self.assertEqual(
        {"claude": True, "codex": False, "antigravity": True, "opencode": False, "copilot": False},
        result["providers"],
    )
    ```
  - In `tests/workflow_core/test_configuration.py`, add a test verifying `harness: "copilot"` and `models: {"copilot": {"models": ["claude-sonnet-4.5"]}}` pass `CONFIG_SCHEMA` and `load_effective_config`, and `setup_service.detect()` detects `.github/agents` as `"copilot"`.

- [ ] **Step 2: Run the `workflow_core` tests and confirm they fail**
  - Run: `python3 -m unittest tests/workflow_core/test_catalog.py tests/workflow_core/test_provider_config.py tests/workflow_core/test_project_detect.py tests/workflow_core/test_configuration.py -v`
  - Expected: `FAIL` / `KeyError: 'copilot'`.

- [ ] **Step 3: Implement `"copilot"` registration in `workflow_core`**
  - In `plugins/gin-workflow/src/scripts/workflow_core/catalog.py:14-19`:
    ```python
    DEFAULT_CATALOGS: Mapping[str, Catalog] = {
        "claude": Catalog(("haiku", "sonnet", "opus"), ("low", "medium", "high", "xhigh", "max")),
        "codex": Catalog(("gpt-5.4-mini", "gpt-5.4"), ("low", "medium", "high", "xhigh")),
        "antigravity": Catalog(("provider_default",), ()),
        "opencode": Catalog(("provider_default",), ()),
        "copilot": Catalog(("provider_default",), ()),
    }
    ```
  - In `plugins/gin-workflow/src/scripts/workflow_core/provider_config.py:10-18`:
    ```python
    DEFAULT_EXECUTABLES: Mapping[str, str] = MappingProxyType({
        "claude": "claude",
        "codex": "codex",
        "antigravity": "agy",
        "opencode": "opencode",
        "copilot": "copilot",
    })
    PROVIDER_DEFAULT = "provider_default"
    PROVIDER_DEFAULT_PROVIDERS = frozenset({"antigravity", "opencode", "copilot"})
    ```
  - In `plugins/gin-workflow/src/scripts/workflow_core/configuration.py:247`:
    ```python
    if harness is not None and harness not in ("claude", "codex", "antigravity", "opencode", "copilot"):
        errors.append("harness must be claude, codex, antigravity, opencode, or copilot")
    ```
  - In `plugins/gin-workflow/src/scripts/workflow_core/schemas.py:96`:
    ```python
    "propertyNames": {"enum": ["claude", "codex", "antigravity", "opencode", "copilot"]},
    ```
  - In `plugins/gin-workflow/src/scripts/workflow_core/assignments.py:46-49`:
    ```python
    if self.model == PROVIDER_DEFAULT and self.provider not in PROVIDER_DEFAULT_PROVIDERS:
        raise AssignmentResolutionError(
            "provider_default is only supported for antigravity, opencode, and copilot"
        )
    ```
  - In `plugins/gin-workflow/src/scripts/workflow_core/cli.py:30` and `:47`:
    ```python
    parser.add_argument("--harness", choices=("claude", "codex", "antigravity", "opencode", "copilot"))
    ...
    parser.add_argument("--provider", choices=("claude", "codex", "antigravity", "opencode", "copilot"))
    ```
  - In `plugins/gin-workflow/src/scripts/workflow_core/project_detect.py:201-202`:
    ```python
    for name in ("claude", "codex", "antigravity", "opencode", "copilot"):
        providers[name] = resolve_harness_executable(name, provider=name, which=which) is not None
    ```
  - In `plugins/gin-workflow/src/scripts/workflow_core/setup_service.py:152`:
    ```python
    for name, marker in (
        ("claude", ".claude"),
        ("codex", ".codex"),
        ("antigravity", ".agents"),
        ("opencode", ".opencode"),
        ("copilot", ".github/agents"),
    ):
    ```

- [ ] **Step 4: Re-run the `workflow_core` tests and commit**
  - Run: `python3 -m unittest tests/workflow_core/test_catalog.py tests/workflow_core/test_provider_config.py tests/workflow_core/test_project_detect.py tests/workflow_core/test_configuration.py -v`
  - Expected: `OK`.
  - Commit: `git add plugins/gin-workflow/src/scripts/workflow_core/ tests/workflow_core/ && git commit -m "feat(workflow-core): register copilot harness in catalog and schemas"`

---

### Track 2: Copilot CLI Worker (`copilot_worker.py`) and Worker `effort`/`agent` Pass-Through
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-orchestrator/src/scripts/gin_orchestrator/native_cli.py:27-44,164-182,229-258,385-397,558-608`
  - Create `plugins/gin-orchestrator/src/scripts/gin_orchestrator/copilot_worker.py`
  - Modify `plugins/gin-orchestrator/src/scripts/gin_orchestrator/antigravity_worker.py:26-125`
  - Modify `plugins/gin-orchestrator/src/scripts/gin_orchestrator/opencode_worker.py:26-111`
  - Modify `plugins/gin-orchestrator/src/scripts/gin_orchestrator/claude_worker.py:47-143`
  - Modify `plugins/gin-orchestrator/src/scripts/gin_orchestrator/routes.py:88-91`
  - Modify `plugins/gin-orchestrator/src/scripts/gin_orchestrator/registry.py:18-45,220-228,295-366`
  - Modify `plugins/gin-orchestrator/src/scripts/gin_orchestrator/cli.py:30-60`
  - Modify `plugins/gin-orchestrator/src/scripts/gin_orchestrator/doctor.py:17-30`
  - Create `tests/gin_orchestrator/test_copilot_worker.py`
  - Modify `tests/gin_orchestrator/test_list_models.py`
  - Modify `tests/gin_orchestrator/test_registry.py`
  - Modify `tests/gin_orchestrator/test_routes.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** Bounded cross-file worker adapter implementation in `gin_orchestrator` with clear spec signatures (`build_copilot_invocation`, `copilot_health`, `CopilotWorkerAdapter`, `env_extra`, JSONL `data` extraction, `list_models("copilot")`, and per-provider `--agent`/`--effort` mapping).
- **Interfaces**:
  - `NativeCliInvocation.env_extra: Mapping[str, str] = field(default_factory=dict, repr=False)` in `gin_orchestrator.native_cli`.
  - `build_copilot_invocation(executable: str, model: str, workspace: Path, prompt: str, *, timeout_seconds: float = 900, effort: str | None = None, agent: str | None = None) -> NativeCliInvocation` in `gin_orchestrator.copilot_worker`.
  - `copilot_health(executable: str, *, help_text: str | None = None, model: str | None = None, native_runner: NativeCliRunner | None = None, workspace: Path | None = None, effort: str | None = None) -> NativeHealth` in `gin_orchestrator.copilot_worker`.
  - `CopilotWorkerAdapter(SynchronousWorkerAdapter)` in `gin_orchestrator.copilot_worker`.
  - `_resolve_worker_agent(provider: str, agent: str | None) -> str | None` in `gin_orchestrator.registry`.
- **Acceptance criteria**:
  - `build_copilot_invocation` constructs `[executable, "-p", prompt, "--allow-all-tools", "--no-ask-user", "--output-format", "json", "--add-dir", str(resolved_workspace)]` plus optional `["--model", model]` (when `model != PROVIDER_DEFAULT`), `["--reasoning-effort", effort]`, and `["--agent", agent]`, and populates `env_extra` only from present keys in `("COPILOT_HOME", "GH_TOKEN", "GITHUB_TOKEN", "COPILOT_GITHUB_TOKEN", "GH_HOST", "COPILOT_GH_HOST")` with `repr=False`.
  - `direct_worker_result` and `_diagnostic_from_stdout` parse Copilot JSONL records where text/error lives under `record["data"]["content"]` or `record["data"]["message"]`.
  - `list_models("copilot")` runs `[executable, "help", "config"]` and parses model IDs from the `model` config section.
  - `ProviderRegistry.factory` maps `request.agent` to `"gin-workflow:<stem>"` for `claude`, `"gin-workflow-<stem>"` for `opencode`, `"<stem>"` for `antigravity` and `copilot`, and omits `agent` for `codex`; passes `effort` for `("claude", "codex", "antigravity", "copilot")`.
  - `gin-workflow routes resolve --harness copilot` and `gin-orchestrator health --provider copilot` succeed without `unknown harness` or `unknown provider` errors.
- **Estimated complexity**: medium

#### Steps

- [ ] **Step 1: Write failing tests in `tests/gin_orchestrator/test_copilot_worker.py`, `test_list_models.py`, `test_registry.py`, and `test_routes.py`**
  - Create `tests/gin_orchestrator/test_copilot_worker.py` testing:
    - `build_copilot_invocation("copilot", "claude-sonnet-4.5", workspace, "do work", timeout_seconds=120, effort="high", agent="developer")` produces `argv == ("copilot", "-p", "do work", "--allow-all-tools", "--no-ask-user", "--output-format", "json", "--add-dir", str(workspace.resolve()), "--model", "claude-sonnet-4.5", "--reasoning-effort", "high", "--agent", "developer")`.
    - `build_copilot_invocation("copilot", "provider_default", workspace, "do work")` omits `--model`, `--reasoning-effort`, and `--agent`.
    - `env_extra` captures present keys from `("COPILOT_HOME", "GH_TOKEN", "GITHUB_TOKEN", "COPILOT_GITHUB_TOKEN", "GH_HOST", "COPILOT_GH_HOST")`, is frozen as `MappingProxyType`, is merged into subprocess `env` in `NativeCliRunner.run`, and does not appear in `repr(invocation)`.
    - `direct_worker_result` extracts the worker result JSON from `{"type": "assistant.message", "data": {"content": json.dumps(contract_payload)}}`.
    - `copilot_health` checks `--prompt`, `--allow-all-tools`, `--output-format`, `--model`, and `--reasoning-effort` (when `effort` is passed), and runs `MODEL_PROBE_PROMPT` when `model != "provider_default"` and `native_runner` + `workspace` are provided, returning `NativeHealth(False, "invalid_model", True)` on `FailureKind.INVALID_MODEL`.
    - `build_antigravity_invocation`, `build_opencode_invocation`, and `build_claude_invocation` pass `--effort` / `--agent` as specified in R1.5.
  - In `tests/gin_orchestrator/test_list_models.py`, add a test for `list_models("copilot")` with a sample `copilot help config` output containing `"claude-sonnet-4.5"`, `"gpt-5.4"`.
  - In `tests/gin_orchestrator/test_routes.py` and `test_registry.py`, add tests for `copilot` route resolution (`provider_default` and explicit models) and `_resolve_worker_agent` mapping across `claude`, `opencode`, `antigravity`, `copilot`, and `codex`.

- [ ] **Step 2: Run Track 2 tests to verify failure**
  - Run: `python3 -m unittest tests/gin_orchestrator/test_copilot_worker.py tests/gin_orchestrator/test_list_models.py tests/gin_orchestrator/test_routes.py tests/gin_orchestrator/test_registry.py -v`
  - Expected: `ModuleNotFoundError: No module named 'gin_orchestrator.copilot_worker'`.

- [ ] **Step 3: Implement `native_cli.py`, `copilot_worker.py`, worker adapters, `routes.py`, `registry.py`, `cli.py`, and `doctor.py`**
  - In `plugins/gin-orchestrator/src/scripts/gin_orchestrator/native_cli.py`:
    - Add `env_extra: Mapping[str, str] = field(default_factory=dict, repr=False)` to `NativeCliInvocation`:
      ```python
      @dataclass(frozen=True)
      class NativeCliInvocation:
          argv: tuple[str, ...]
          cwd: Path
          stdin: bytes
          timeout_seconds: float
          idle_timeout_seconds: float | None = None
          env_extra: Mapping[str, str] = field(default_factory=dict, repr=False)

          def __post_init__(self) -> None:
              object.__setattr__(self, "argv", tuple(str(item) for item in self.argv))
              object.__setattr__(self, "cwd", Path(self.cwd).resolve())
              object.__setattr__(self, "stdin", bytes(self.stdin))
              object.__setattr__(
                  self,
                  "env_extra",
                  MappingProxyType({str(k): str(v) for k, v in dict(self.env_extra).items()}),
              )
              if not self.argv or self.timeout_seconds <= 0:
                  raise ValueError("native CLI requires argv and positive timeout")
              if self.idle_timeout_seconds is not None and self.idle_timeout_seconds <= 0:
                  raise ValueError("native CLI idle_timeout_seconds must be positive when set")
      ```
    - In `direct_worker_result(output: NativeCliOutput)` (`native_cli.py:169-176`), also inspect `record.get("data")`:
      ```python
      data = record.get("data")
      if isinstance(data, Mapping):
          candidates.extend([data.get("content"), data.get("message"), data.get("text")])
      ```
    - In `_diagnostic_from_stdout(stdout: bytes)` (`native_cli.py:249-256`), also inspect `record.get("data")`:
      ```python
      data = record.get("data")
      if isinstance(data, Mapping):
          for field in ("error", "message", "detail", "reason", "content"):
              inner = data.get(field)
              if isinstance(inner, str) and inner.strip():
                  return inner.strip()
      ```
    - In `NativeCliRunner.run` (`native_cli.py:388`), merge `invocation.env_extra`:
      ```python
      env={**sanitized_environment(), **worktree_environment(invocation.cwd), **invocation.env_extra},
      ```
    - In `native_cli.py:559-608`, add `"copilot": ("help", "config")` to `_LIST_COMMANDS` and parse the `model` section in `list_models`:
      ```python
      _LIST_COMMANDS = {
          "codex": ("debug", "models"),
          "antigravity": ("models",),
          "opencode": ("models",),
          "copilot": ("help", "config"),
      }
      ```
      And in `list_models`:
      ```python
      if provider == "copilot":
          in_model_block = False
          models = []
          for line in completed.stdout.splitlines():
              stripped = line.strip()
              if stripped.startswith("`model`:"):
                  in_model_block = True
                  continue
              if in_model_block:
                  if stripped.startswith("`") and stripped.endswith(":"):
                      break
                  match = re.match(r'^-\s+"([^"]+)"', stripped)
                  if match:
                      model_id = match.group(1)
                      models.append({"id": model_id, "label": model_id, "description": "", "reasoning_levels": []})
          return models
      ```
  - Create `plugins/gin-orchestrator/src/scripts/gin_orchestrator/copilot_worker.py`:
    ```python
    """GitHub Copilot native-harness worker bridge (no cloud SDK dependency)."""

    from __future__ import annotations

    import os
    from pathlib import Path
    import re
    from typing import Any, Callable, Mapping

    from workflow_core.ext import PROVIDER_DEFAULT

    from .circuit_breaker import FailureKind
    from .native_cli import (
        MODEL_PROBE_PROMPT,
        MODEL_PROBE_TIMEOUT_SECONDS,
        NativeCliError,
        NativeCliInvocation,
        NativeCliRunner,
        NativeHealth,
        native_cancellable_dispatch,
        native_worker_payload,
        probe_help,
    )
    from .worker_dispatch import SynchronousWorkerAdapter, WorkerResult

    COPILOT_ENV_KEYS = (
        "COPILOT_HOME",
        "GH_TOKEN",
        "GITHUB_TOKEN",
        "COPILOT_GITHUB_TOKEN",
        "GH_HOST",
        "COPILOT_GH_HOST",
    )


    def _copilot_env_extra(source: Mapping[str, str] | None = None) -> dict[str, str]:
        env = os.environ if source is None else source
        return {key: env[key] for key in COPILOT_ENV_KEYS if key in env and env[key]}


    def build_copilot_invocation(
        executable: str,
        model: str,
        workspace: Path,
        prompt: str,
        *,
        timeout_seconds: float = 900,
        effort: str | None = None,
        agent: str | None = None,
    ) -> NativeCliInvocation:
        resolved_workspace = Path(workspace).resolve()
        argv = [
            executable,
            "-p",
            prompt,
            "--allow-all-tools",
            "--no-ask-user",
            "--output-format",
            "json",
            "--add-dir",
            str(resolved_workspace),
        ]
        if model and model != PROVIDER_DEFAULT:
            argv.extend(["--model", model])
        if effort is not None:
            argv.extend(["--reasoning-effort", effort])
        if agent is not None:
            argv.extend(["--agent", agent])
        return NativeCliInvocation(
            tuple(argv),
            resolved_workspace,
            b"",
            timeout_seconds,
            env_extra=_copilot_env_extra(),
        )


    def copilot_health(
        executable: str,
        *,
        help_text: str | None = None,
        model: str | None = None,
        native_runner: NativeCliRunner | None = None,
        workspace: Path | None = None,
        effort: str | None = None,
    ) -> NativeHealth:
        help_text = probe_help(executable, "--help") if help_text is None else help_text
        if help_text is None:
            return NativeHealth(False, "executable_or_help_unavailable", False)
        options = frozenset(re.findall(r"--[A-Za-z0-9][A-Za-z0-9-]*", help_text))
        supported = "--model" in options and (effort is None or "--reasoning-effort" in options)
        if not {"--prompt", "--allow-all-tools", "--output-format"}.issubset(options):
            return NativeHealth(False, "required_flags_unverified", supported)
        if effort is not None and "--reasoning-effort" not in options:
            return NativeHealth(False, "required_flags_unverified", False)
        health = NativeHealth(
            True,
            "ready" if supported else "explicit_model_selection_unverified",
            supported,
        )
        if not supported or model is None or model == PROVIDER_DEFAULT or native_runner is None or workspace is None:
            return health
        try:
            native_runner.run(
                build_copilot_invocation(
                    executable,
                    model,
                    workspace,
                    MODEL_PROBE_PROMPT,
                    timeout_seconds=MODEL_PROBE_TIMEOUT_SECONDS,
                    effort=effort,
                )
            )
        except NativeCliError as error:
            if error.kind is FailureKind.INVALID_MODEL:
                return NativeHealth(False, "invalid_model", supported)
        return health


    class CopilotWorkerAdapter(SynchronousWorkerAdapter):
        provider_name = "copilot"

        def __init__(
            self,
            native_dispatch: Callable[[Mapping[str, Any]], Mapping[str, Any] | WorkerResult] | None = None,
            *,
            native_runner: NativeCliRunner | None = None,
            executable: str | None = None,
            model: str | None = None,
            workspace: Path | None = None,
            timeout_seconds: float = 900,
            effort: str | None = None,
            agent: str | None = None,
        ) -> None:
            cancellable_dispatch = None
            if native_dispatch is None and all((native_runner, executable, model, workspace)):
                cancellable_dispatch = native_cancellable_dispatch(
                    native_runner,
                    lambda prompt: build_copilot_invocation(
                        str(executable),
                        str(model),
                        Path(workspace),
                        prompt,
                        timeout_seconds=timeout_seconds,
                        effort=effort,
                        agent=agent,
                    ),
                )
            super().__init__(
                native_dispatch,
                available=native_dispatch is not None or cancellable_dispatch is not None,
                payload_factory=native_worker_payload,
                cancellable_runner=cancellable_dispatch,
            )
    ```
  - Update `antigravity_worker.py`: add `effort: str | None = None` (`--effort <effort>`) and `agent: str | None = None` (`--agent <agent>`) to `build_antigravity_invocation`, `antigravity_health` (checking `effort is None or "--effort" in options`), and `AntigravityWorkerAdapter.__init__`.
  - Update `opencode_worker.py`: add `agent: str | None = None` (`--agent <agent>`) to `build_opencode_invocation` and `OpenCodeWorkerAdapter.__init__`.
  - Update `claude_worker.py`: add `agent: str | None = None` (`--agent <agent>`) to `build_claude_invocation` and `ClaudeWorkerAdapter.__init__`.
  - Update `routes.py:89` and `registry.py:226` error strings to `"provider_default is only supported for antigravity, opencode, and copilot"`.
  - Update `registry.py`:
    - Add helper `_resolve_worker_agent(provider: str, agent: str | None) -> str | None`:
      ```python
      def _resolve_worker_agent(provider: str, agent: str | None) -> str | None:
          if not agent or not agent.strip():
              return None
          raw = agent.strip()
          if provider == "codex":
              return None
          if ":" in raw:
              plugin_prefix, stem = raw.split(":", 1)
          elif raw.startswith("gin-workflow-"):
              plugin_prefix, stem = "gin-workflow", raw[len("gin-workflow-"):]
          elif raw.startswith("gin-qa-"):
              plugin_prefix, stem = "gin-qa", raw[len("gin-qa-"):]
          else:
              plugin_prefix, stem = "gin-workflow", raw
          if provider == "claude":
              return f"{plugin_prefix}:{stem}"
          if provider == "opencode":
              return f"{plugin_prefix}-{stem}"
          return stem
      ```
    - In `ProviderRegistry.from_effective_config`:
      - Pass `options["effort"] = candidate.effort` when `candidate.provider in ("claude", "codex", "antigravity", "copilot") and candidate.effort is not None`.
      - Pass `options["agent"] = resolved_agent` when `resolved_agent := _resolve_worker_agent(candidate.provider, getattr(request, "agent", None))` is not `None`.
      - Add `if candidate.provider == "copilot": return CopilotWorkerAdapter(**options)`.
      - Add `"copilot": copilot_health` to `health_builders`, include `"copilot"` in the `health_for` provider tuple `("claude", "codex", "antigravity", "opencode", "copilot")`, and pass `probe_kwargs["effort"] = effort` when `provider in ("claude", "codex", "antigravity", "copilot") and effort is not None`.
  - Update `gin_orchestrator/cli.py:44-58` and `doctor.py:24-29`: add `"copilot": copilot_health` to `HEALTH`, and in `cli.py:_health` pass `kwargs["effort"] = args.effort` when `args.provider in ("claude", "codex", "antigravity", "copilot") and args.effort is not None`.

- [ ] **Step 4: Re-run Track 2 tests and commit**
  - Run: `python3 -m unittest tests/gin_orchestrator/test_copilot_worker.py tests/gin_orchestrator/test_list_models.py tests/gin_orchestrator/test_routes.py tests/gin_orchestrator/test_registry.py -v`
  - Expected: `OK`.
  - Commit: `git add plugins/gin-orchestrator/src/scripts/gin_orchestrator/ tests/gin_orchestrator/ && git commit -m "feat(orchestrator): add copilot worker adapter and agent/effort pass-through"`

---

### Track 3: Agent Translation Across All Harnesses in `install.sh` and `install.ps1`
- **Dependencies**: none
- **Files**:
  - Modify `install.sh:153-167,237-249,406-445,477-508,694-705`
  - Modify `install.ps1:181-303,630-644,695-705`
  - Modify `tests/gin_orchestrator/test_harness_packaging.py:114-170,198-210`
  - Modify `tests/install_smoke_test.sh:260-289,350-382`
  - Modify `tests/install_smoke_test.ps1:95-115,295-325`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** Bounded packaging logic in `install.sh` and `install.ps1` with explicit per-platform frontmatter and tool-name translation rules.
- **Interfaces**:
  - Bash functions `template_agents_for_codex`, `template_agents_for_opencode`, `template_agents_for_copilot` in `install.sh`.
  - PowerShell functions `Convert-CodexAgents`, `Convert-OpenCodeAgents`, `Convert-CopilotAgents` in `install.ps1`.
- **Acceptance criteria**:
  - `plugins/<plugin>/dist/antigravity/agents/*.md` are kept as-is with canonical Antigravity tool names.
  - `plugins/<plugin>/dist/codex/agents/*.md` strip the `^tools:` frontmatter line while keeping `name:` and `description:`.
  - `plugins/<plugin>/dist/opencode/agents/<plugin>-<stem>.md` and `$PROJECT_DIR/.opencode/agents/<plugin>-<stem>.md` are generated with `description:` and `mode: subagent` (no `name:` or `tools:`), and global install copies `<plugin>-*.md` into `${HOME}/.config/opencode/agents/` (cleaned up on `--uninstall`).
  - `plugins/<plugin>/dist/copilot/<plugin>/agents/*.md` translate Antigravity tool names to deduplicated Copilot tool names (`"view_file" -> "view"`, `"grep_search" -> "grep"`, `"list_dir" -> "glob"`, `"search_web" -> "web_fetch"`, `"run_command" -> "bash"`, `"replace_file_content"` / `"write_to_file"` -> `"edit"`).
- **Estimated complexity**: medium

#### Steps

- [ ] **Step 1: Update packaging assertions in `tests/gin_orchestrator/test_harness_packaging.py`, `tests/install_smoke_test.sh`, and `tests/install_smoke_test.ps1`**
  - In `tests/gin_orchestrator/test_harness_packaging.py`:
    - In `test_dry_run_builds_every_harness_layout` (`:114-131`):
      ```python
      opencode_removed = {"agents/developer.md", "skills/report/SKILL.md"}
      opencode_added = {"agents/gin-workflow-developer.md", "skills/gin-workflow-report/SKILL.md"}
      copilot_removed: set[str] = set()
      ```
    - In `test_copilot_layout_is_a_claude_manifest_bundle_with_copilot_hooks` (`:153-169`), replace `self.assertFalse((root / "agents").exists())` with:
      ```python
      self.assertTrue((root / "agents/developer.md").is_file())
      dev_text = (root / "agents/developer.md").read_text(encoding="utf-8")
      self.assertIn('tools: ["view", "grep", "glob", "bash", "edit"]', dev_text)
      codex_dev = (self.dist / "codex/agents/developer.md").read_text(encoding="utf-8")
      self.assertNotIn("tools:", codex_dev.split("---", 2)[1])
      ```
    - In `test_opencode_layout_is_a_skill_bundle_without_manifest_or_hooks` (`:198-210`), replace `self.assertFalse((root / "agents").exists())` with:
      ```python
      self.assertTrue((root / "agents/gin-workflow-developer.md").is_file())
      self.assertFalse((root / "agents/developer.md").exists())
      oc_frontmatter = yaml.safe_load((root / "agents/gin-workflow-developer.md").read_text(encoding="utf-8").split("---", 2)[1])
      self.assertEqual("subagent", oc_frontmatter.get("mode"))
      self.assertIn("description", oc_frontmatter)
      self.assertNotIn("name", oc_frontmatter)
      self.assertNotIn("tools", oc_frontmatter)
      ```
  - In `tests/install_smoke_test.sh`:
    - Line 268: replace `assert_not_exists "plugins/gin-workflow/dist/opencode/agents"` with `assert_exists "plugins/gin-workflow/dist/opencode/agents/gin-workflow-developer.md"`.
    - Line 287: replace `assert_not_exists "plugins/gin-workflow/dist/copilot/gin-workflow/agents"` with `assert_exists "plugins/gin-workflow/dist/copilot/gin-workflow/agents/developer.md"` and `assert_contains "plugins/gin-workflow/dist/copilot/gin-workflow/agents/developer.md" '"view", "grep", "glob", "bash", "edit"'`.
    - Line 358: replace `assert_not_exists "$MOCK_HOME/.config/opencode/skills/gin-workflow/agents"` with `assert_exists "$MOCK_HOME/.config/opencode/skills/gin-workflow/agents/gin-workflow-developer.md"` and `assert_exists "$MOCK_HOME/.config/opencode/agents/gin-workflow-developer.md"`.
    - Line 380: add `assert_exists "$opencode_project/.opencode/agents/gin-workflow-developer.md"`.
  - In `tests/install_smoke_test.ps1`:
    - Line 100: replace `Assert-True (-not (Test-Path -LiteralPath (Join-Path $Root 'plugins/gin-workflow/dist/opencode/agents'))) 'OpenCode dry-run kept agents'` with `Assert-Exists (Join-Path $Root 'plugins/gin-workflow/dist/opencode/agents/gin-workflow-developer.md')`.
    - Line 113: add `Assert-Exists (Join-Path $project '.opencode/agents/gin-workflow-developer.md')`.
    - Line 299: replace `Assert-True (-not (Test-Path -LiteralPath (Join-Path $TestHome '.config/opencode/skills/gin-workflow/agents'))) 'OpenCode install kept agents'` with `Assert-Exists (Join-Path $TestHome '.config/opencode/skills/gin-workflow/agents/gin-workflow-developer.md')` and `Assert-Exists (Join-Path $TestHome '.config/opencode/agents/gin-workflow-developer.md')`.
    - Line 323: replace `Assert-True (-not (Test-Path -LiteralPath (Join-Path $copilotDist 'agents'))) 'Copilot bundle has agents'` with `Assert-Exists (Join-Path $copilotDist 'agents/developer.md')`.

- [ ] **Step 2: Run `test_harness_packaging.py` to confirm it fails**
  - Run: `python3 -m unittest tests/gin_orchestrator/test_harness_packaging.py -v`
  - Expected: `FAIL` on missing `agents/gin-workflow-developer.md` and `copilot/gin-workflow/agents/developer.md`.

- [ ] **Step 3: Implement agent translation in `install.sh` and `install.ps1`**
  - In `install.sh`:
    - Add `template_agents_for_codex`, `template_agents_for_copilot`, and `template_agents_for_opencode` right after `template_agents_for_claude` (`install.sh:248`):
      ```bash
      template_agents_for_codex() {
        local src="$1"
        local dest="$2"
        sed -e '/^tools:/d' "$src" > "$dest"
      }

      template_agents_for_copilot() {
        local src="$1"
        local dest="$2"
        sed -e 's/"view_file"/"view"/g' \
            -e 's/"grep_search"/"grep"/g' \
            -e 's/"list_dir"/"glob"/g' \
            -e 's/"search_web"/"web_fetch"/g' \
            -e 's/"run_command"/"bash"/g' \
            -e 's/"replace_file_content", "write_to_file"/"edit"/g' \
            -e 's/"replace_file_content"/"edit"/g' \
            -e 's/"write_to_file"/"edit"/g' \
            "$src" > "$dest"
      }

      template_agents_for_opencode() {
        local src_dir="$1"
        local target_dir="$2"
        local plugin_name="$3"
        local f stem
        [ -d "$src_dir/agents" ] || return 0
        mkdir -p "$target_dir/agents"
        for f in "$src_dir/agents"/*.md; do
          [ -e "$f" ] || continue
          stem="$(basename "$f" .md)"
          sed -e '/^name:/d' \
              -e 's/^tools:.*/mode: subagent/' \
              "$f" > "$target_dir/agents/${plugin_name}-${stem}.md"
        done
      }
      ```
    - In `install_platform` (`install.sh:406-445`):
      - Pass `"$p_name"` as 4th argument to `install_opencode_bundle "$SCRIPT_DIR/plugins/$p_name/src" "$target_dir" "$install_root" "$p_name"`, and call `template_agents_for_opencode "$src" "$target" "$plugin_name"` inside `install_opencode_bundle`.
      - In the `if [ "$platform" = "copilot" ]; then` block (`install.sh:411-423`), copy and translate `agents/*.md`:
        ```bash
        if [ -d "$SCRIPT_DIR/plugins/$p_name/src/agents" ]; then
          mkdir -p "$target_dir/agents"
          for f in "$SCRIPT_DIR/plugins/$p_name/src/agents"/*.md; do
            [ -e "$f" ] || continue
            template_agents_for_copilot "$f" "$target_dir/agents/$(basename "$f")"
          done
        fi
        ```
      - After `if [ "$platform" = "claude" ]; then ... fi` (`install.sh:434-442`), add `codex`:
        ```bash
        if [ "$platform" = "codex" ]; then
          for f in "$target_dir/agents"/*.md; do
            [ -e "$f" ] || continue
            local tmp_file
            tmp_file=$(mktemp)
            template_agents_for_codex "$f" "$tmp_file"
            rm -f "$f"
            mv "$tmp_file" "$f"
          done
        fi
        ```
    - In `install_plugin` global OpenCode install (`install.sh:694-705`), also copy `dist/opencode/agents/${p_name}-*.md` into `${HOME}/.config/opencode/agents/`:
      ```bash
      if [ -d "$dist_dir/opencode/agents" ]; then
        mkdir -p "${HOME}/.config/opencode/agents"
        rm -f "${HOME}/.config/opencode/agents/${p_name}-"*.md
        cp -rf "$dist_dir/opencode/agents/${p_name}-"*.md "${HOME}/.config/opencode/agents/"
      fi
      ```
      And in the `if [ "$UNINSTALL" = true ]; then` block (`install.sh:156-158`), remove `${HOME}/.config/opencode/agents/${p_name}-*.md`:
      ```bash
      for p_name in "${PLUGINS[@]}"; do
        rm -rf "${HOME}/.config/opencode/skills/${p_name}"
        rm -f "${HOME}/.config/opencode/agents/${p_name}-"*.md
      done
      ```
  - In `install.ps1`:
    - Add `Convert-CodexAgents`, `Convert-CopilotAgents`, and `Convert-OpenCodeAgents` right after `Convert-ClaudeAgents` (`install.ps1:200`):
      ```powershell
      function Convert-CodexAgents {
          param([Parameter(Mandatory)][string]$AgentsDirectory)
          if (-not (Test-Path -LiteralPath $AgentsDirectory -PathType Container)) {
              return
          }
          foreach ($agent in Get-ChildItem -LiteralPath $AgentsDirectory -Filter '*.md' -File) {
              $content = [IO.File]::ReadAllText($agent.FullName)
              $content = [regex]::Replace($content, '(?m)^tools:.*\r?\n', '')
              if ($Link -and $null -ne $agent.LinkType) {
                  Remove-Item -LiteralPath $agent.FullName -Force
              }
              Write-Utf8File -Path $agent.FullName -Content $content
          }
      }

      function Convert-CopilotAgents {
          param([Parameter(Mandatory)][string]$AgentsDirectory)
          if (-not (Test-Path -LiteralPath $AgentsDirectory -PathType Container)) {
              return
          }
          foreach ($agent in Get-ChildItem -LiteralPath $AgentsDirectory -Filter '*.md' -File) {
              $content = Get-Content -LiteralPath $agent.FullName -Raw
              $content = $content.Replace('"view_file"', '"view"')
              $content = $content.Replace('"grep_search"', '"grep"')
              $content = $content.Replace('"list_dir"', '"glob"')
              $content = $content.Replace('"search_web"', '"web_fetch"')
              $content = $content.Replace('"run_command"', '"bash"')
              $content = $content.Replace('"replace_file_content", "write_to_file"', '"edit"')
              $content = $content.Replace('"replace_file_content"', '"edit"')
              $content = $content.Replace('"write_to_file"', '"edit"')
              if ($Link -and $null -ne $agent.LinkType) {
                  Remove-Item -LiteralPath $agent.FullName -Force
              }
              Write-Utf8File -Path $agent.FullName -Content $content
          }
      }

      function Convert-OpenCodeAgents {
          param(
              [Parameter(Mandatory)][string]$SourceDirectory,
              [Parameter(Mandatory)][string]$DestinationDirectory,
              [Parameter(Mandatory)][string]$PluginName
          )
          $sourceAgents = Join-Path $SourceDirectory 'agents'
          if (-not (Test-Path -LiteralPath $sourceAgents -PathType Container)) {
              return
          }
          $destAgents = Join-Path $DestinationDirectory 'agents'
          New-Directory $destAgents
          foreach ($agent in Get-ChildItem -LiteralPath $sourceAgents -Filter '*.md' -File) {
              $stem = [IO.Path]::GetFileNameWithoutExtension($agent.Name)
              $content = [IO.File]::ReadAllText($agent.FullName)
              $content = [regex]::Replace($content, '(?m)^name:.*\r?\n', '')
              $content = [regex]::Replace($content, '(?m)^tools:.*$', 'mode: subagent')
              Write-Utf8File -Path (Join-Path $destAgents "$PluginName-$stem.md") -Content $content
          }
      }
      ```
    - In `Install-OpenCodeBundle` (`install.ps1:218`), add `[Parameter(Mandatory)][string]$PluginName` and call `Convert-OpenCodeAgents -SourceDirectory $Source -DestinationDirectory $Destination -PluginName $PluginName`.
    - In `Install-PlatformLayout` (`install.ps1:274-296`):
      - Pass `-PluginName (Split-Path -Leaf $PluginDirectory)` to `Install-OpenCodeBundle`.
      - In `if ($Harness -eq 'copilot')`: copy `src/agents` to `Join-Path $Destination 'agents'` via `Copy-DirectoryContent` and call `Convert-CopilotAgents -AgentsDirectory (Join-Path $Destination 'agents')`.
      - Add `if ($Harness -eq 'codex') { Convert-CodexAgents -AgentsDirectory (Join-Path $Destination 'agents') }`.
    - In `Install-Plugin` global OpenCode section (`install.ps1:630-644`), copy `$source/agents/$Name-*.md` into `Join-Path $UserHome '.config/opencode/agents'`, and in `if ($Uninstall)` (`install.ps1:695-700`) remove `$Name-*.md` from `Join-Path $UserHome '.config/opencode/agents'`.

- [ ] **Step 4: Run packaging and smoke tests and commit**
  - Run: `python3 -m unittest tests/gin_orchestrator/test_harness_packaging.py -v && bash tests/install_smoke_test.sh`
  - Expected: `OK` and `All smoke tests passed!`.
  - Commit: `git add install.sh install.ps1 tests/gin_orchestrator/test_harness_packaging.py tests/install_smoke_test.sh tests/install_smoke_test.ps1 && git commit -m "feat(install): translate agent definitions for codex, opencode, and copilot"`

---

### Track 4: Unified `ORCHESTRATOR_DEFAULTS`, Immediate `QUOTA`/`AUTH` Circuit Breaker, and `run_with_retries`
- **Dependencies**: Track 2
- **Files**:
  - Modify `plugins/gin-orchestrator/src/scripts/gin_orchestrator/config.py:8-13`
  - Modify `plugins/gin-orchestrator/src/scripts/gin_orchestrator/circuit_breaker.py:38-50,229-263`
  - Modify `plugins/gin-orchestrator/src/scripts/gin_orchestrator/worker_dispatch.py:338-411`
  - Modify `plugins/gin-orchestrator/src/scripts/gin_orchestrator/worker_scheduler.py:81-108,176-206`
  - Modify `plugins/gin-orchestrator/src/scripts/gin_orchestrator/registry.py:105-110,214-218,242-254,370-376`
  - Modify `plugins/gin-orchestrator/src/scripts/gin_orchestrator/claude_worker.py:53,122`
  - Modify `plugins/gin-orchestrator/src/scripts/gin_orchestrator/codex_worker.py:30,118`
  - Modify `plugins/gin-orchestrator/src/scripts/gin_orchestrator/antigravity_worker.py:32,106`
  - Modify `plugins/gin-orchestrator/src/scripts/gin_orchestrator/opencode_worker.py:32,92`
  - Modify `plugins/gin-orchestrator/src/scripts/gin_orchestrator/copilot_worker.py`
  - Modify `tests/gin_orchestrator/test_orchestrator_config.py:40-52`
  - Modify `tests/gin_orchestrator/test_circuit_breaker.py`
  - Modify `tests/gin_orchestrator/test_worker_scheduler.py:208-284,352-412`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** Bounded resilience and retry changes across `gin_orchestrator` with explicit constants and state transitions defined in R3.
- **Interfaces**:
  - `ORCHESTRATOR_DEFAULTS` in `gin_orchestrator.config`: `{"circuit_breaker": {"failure_threshold": 3}, "queue": {"max_wait_seconds": 600}, "worker": {"max_retries": 2, "timeout_seconds": 900.0}}`.
  - `IMMEDIATE_OPEN_FAILURE_KINDS = frozenset({FailureKind.QUOTA, FailureKind.AUTH})` in `gin_orchestrator.circuit_breaker`.
  - `WorkerRequest.prior_changed_files: tuple[str, ...] = ()` and `WorkerRequest.agent: str | None = None` in `gin_orchestrator.worker_dispatch`.
  - `TRANSIENT_FAILURE_BLOCKERS = frozenset({"provider_failure:quota", "provider_failure:rate_limit", "provider_failure:service"})` and `run_with_retries(dispatcher: Any, request: WorkerRequest, *, max_retries: int, worker_timeout_seconds: float) -> WorkerResult` in `gin_orchestrator.worker_scheduler`.
- **Acceptance criteria**:
  - `ORCHESTRATOR_DEFAULTS` is the single source of default values for `worker.timeout_seconds` (`900.0`), `worker.max_retries` (`2`), `queue.max_wait_seconds` (`600`), and `circuit_breaker.failure_threshold` (`3`) across `registry.py`, `worker_scheduler.py`, and all 5 worker adapters.
  - `CircuitBreakerStore.record_failure()` transitions `state` to `CircuitState.OPEN` on the first `FailureKind.QUOTA` or `FailureKind.AUTH` failure even when `failure_threshold == 3`, while requiring 3 failures for `RATE_LIMIT`, `SERVICE`, `TIMEOUT`, `CRASH`, or `INVALID_MODEL`.
  - `run_with_retries()` and `WorkerScheduler._run()` retry only when `attempt < max_retries`, `retry_safe` is `True`, and `any(b in TRANSIENT_FAILURE_BLOCKERS for b in result.blockers)`, and pass `prior_changed_files=tuple(result.changed_files)` from attempt `N` into attempt `N+1`'s `WorkerRequest` and `to_payload()`.
- **Estimated complexity**: medium

#### Steps

- [ ] **Step 1: Add failing tests in `test_orchestrator_config.py`, `test_circuit_breaker.py`, and `test_worker_scheduler.py`**
  - In `tests/gin_orchestrator/test_orchestrator_config.py:50`, update the expected `section["worker"]` dict:
    ```python
    self.assertEqual(section["worker"], {"max_retries": 2, "timeout_seconds": 900.0})
    ```
  - In `tests/gin_orchestrator/test_circuit_breaker.py`, add `test_quota_and_auth_open_circuit_immediately_when_threshold_above_one`:
    ```python
    def test_quota_and_auth_open_circuit_immediately_when_threshold_above_one(self):
        with tempfile.TemporaryDirectory() as directory:
            store = CircuitBreakerStore(Path(directory) / "state.json", failure_threshold=3)
            for idx, kind in enumerate((FailureKind.QUOTA, FailureKind.AUTH)):
                record = store.record_failure("claude", f"model-{idx}", kind)
                self.assertEqual(CircuitState.OPEN, record.state)
                self.assertEqual(1, record.failures)
            r1 = store.record_failure("claude", "rate-model", FailureKind.RATE_LIMIT)
            self.assertEqual(CircuitState.CLOSED, r1.state)
    ```
  - In `tests/gin_orchestrator/test_worker_scheduler.py`:
    - Update line 216 (`test_retry_preserves_completed_results_and_does_not_rerun_them`) from `blockers=["timeout"]` to `blockers=["provider_failure:rate_limit"]`.
    - Update line 255 (`test_retry_uses_a_new_acceptance_attempt_identity`) from `blockers=["temporary"]` to `blockers=["provider_failure:service"]`.
    - Update line 380 (`test_timeout_cancels_attempt_and_retries_with_a_deadline`) from `blockers=["timeout"]` to `blockers=["provider_failure:service"]`.
    - Add tests verifying:
      - Non-transient blockers (`"timeout"`, `"provider_failure:auth"`, `"provider_failure:crash"`, `"invalid_result_contract"`) are not retried (`attempts == 1`).
      - Transient blockers (`"provider_failure:quota"`, `"provider_failure:rate_limit"`, `"provider_failure:service"`) are retried and `payload["prior_changed_files"]` on attempt 2 equals `["src/partial.py"]` from attempt 1's `changed_files` (and is replaced by attempt 2's `changed_files`, not accumulated across earlier attempts).
      - `run_with_retries(dispatcher, request, max_retries=1, worker_timeout_seconds=1.0)` works standalone without `WorkerScheduler._prepare`.

- [ ] **Step 2: Run Track 4 tests to confirm they fail**
  - Run: `python3 -m unittest tests/gin_orchestrator/test_orchestrator_config.py tests/gin_orchestrator/test_circuit_breaker.py tests/gin_orchestrator/test_worker_scheduler.py -v`
  - Expected: `FAIL`.

- [ ] **Step 3: Implement `ORCHESTRATOR_DEFAULTS`, `IMMEDIATE_OPEN_FAILURE_KINDS`, `prior_changed_files`/`agent`, and `run_with_retries`**
  - In `plugins/gin-orchestrator/src/scripts/gin_orchestrator/config.py:8-12`:
    ```python
    ORCHESTRATOR_DEFAULTS: Mapping[str, Mapping[str, Any]] = {
        "circuit_breaker": {"failure_threshold": 3},
        "queue": {"max_wait_seconds": 600},
        "worker": {"max_retries": 2, "timeout_seconds": 900.0},
    }
    ```
  - In `plugins/gin-orchestrator/src/scripts/gin_orchestrator/circuit_breaker.py:49` and `:247`:
    ```python
    IMMEDIATE_OPEN_FAILURE_KINDS = frozenset({FailureKind.QUOTA, FailureKind.AUTH})
    ```
    And in `CircuitBreakerStore.record_failure`:
    ```python
    if (
        state is CircuitState.HALF_OPEN
        or kind in IMMEDIATE_OPEN_FAILURE_KINDS
        or failures >= self.failure_threshold
    ):
        state = CircuitState.OPEN
        opened_at = self._clock()
    ```
  - In `plugins/gin-orchestrator/src/scripts/gin_orchestrator/worker_dispatch.py:338-411`:
    - Add fields to `WorkerRequest`:
      ```python
      prior_changed_files: tuple[str, ...] = ()
      agent: str | None = None
      ```
    - In `WorkerRequest.__post_init__`:
      ```python
      object.__setattr__(self, "prior_changed_files", tuple(str(f) for f in self.prior_changed_files))
      ```
    - In `WorkerRequest.to_payload()`:
      ```python
      if self.prior_changed_files:
          payload["prior_changed_files"] = list(self.prior_changed_files)
      if self.agent is not None:
          payload["agent"] = self.agent
      ```
  - In `plugins/gin-orchestrator/src/scripts/gin_orchestrator/worker_scheduler.py`:
    - Import `ORCHESTRATOR_DEFAULTS` from `.config`.
    - Define `TRANSIENT_FAILURE_BLOCKERS = frozenset({"provider_failure:quota", "provider_failure:rate_limit", "provider_failure:service"})`.
    - Extract `_attempt_with_deadline(dispatcher, request, worker_timeout_seconds)` and `run_with_retries`:
      ```python
      def run_with_retries(
          dispatcher: Any,
          request: WorkerRequest,
          *,
          max_retries: int = int(ORCHESTRATOR_DEFAULTS["worker"]["max_retries"]),
          worker_timeout_seconds: float = float(ORCHESTRATOR_DEFAULTS["worker"]["timeout_seconds"]),
      ) -> WorkerResult:
          result: WorkerResult | None = None
          prior_changed_files: tuple[str, ...] = request.prior_changed_files
          for attempt in range(max_retries + 1):
              attempted_request = (
                  request
                  if attempt == 0
                  else WorkerScheduler._retry_request(
                      request, attempt, prior_changed_files=prior_changed_files
                  )
              )
              result, retry_safe = _attempt_with_deadline(
                  dispatcher, attempted_request, worker_timeout_seconds
              )
              if result.status == "completed":
                  return result
              if not retry_safe:
                  return result
              if not any(b in TRANSIENT_FAILURE_BLOCKERS for b in result.blockers):
                  return result
              prior_changed_files = tuple(result.changed_files)
          assert result is not None
          return result
      ```
    - Update `WorkerScheduler.__init__` defaults (`worker_timeout_seconds: float = float(ORCHESTRATOR_DEFAULTS["worker"]["timeout_seconds"])`), `WorkerScheduler._retry_request(request: WorkerRequest, attempt: int, *, prior_changed_files: Sequence[str] = ()) -> WorkerRequest`, and `WorkerScheduler._run` to delegate to `run_with_retries(self.dispatcher, request, max_retries=self.max_retries, worker_timeout_seconds=self.worker_timeout_seconds)`.
  - In `registry.py` (`:107-108`, `:215-216`, `:244`, `:250-252`, `:374`) and the 5 worker adapters (`claude_worker.py`, `codex_worker.py`, `antigravity_worker.py`, `opencode_worker.py`, `copilot_worker.py`), reference `ORCHESTRATOR_DEFAULTS` instead of hardcoded `600.0`, `900`, `120`, and `1`.

- [ ] **Step 4: Re-run Track 4 and full `gin_orchestrator` tests and commit**
  - Run: `python3 -m unittest discover -s tests/gin_orchestrator -v`
  - Expected: `OK`.
  - Commit: `git add plugins/gin-orchestrator/src/scripts/gin_orchestrator/ tests/gin_orchestrator/ && git commit -m "feat(orchestrator): unify defaults, open breaker on quota/auth, and retry transient failures"`

---

### Track 5: `gin-orchestrator dispatch` CLI, Stage Skill Updates, and Documentation
- **Dependencies**: Track 3, Track 4
- **Files**:
  - Modify `plugins/gin-orchestrator/src/scripts/gin_orchestrator/cli.py:15-60,202-260`
  - Modify `plugins/gin-orchestrator/src/scripts/gin_orchestrator/registry.py:257-294`
  - Modify `plugins/gin-workflow/src/skills/execute/references/worker-lifecycle.md:1-24`
  - Modify `plugins/gin-workflow/src/skills/execute/SKILL.md:32-41`
  - Modify `plugins/gin-workflow/src/skills/review/SKILL.md:14-30`
  - Modify `plugins/gin-workflow/src/skills/discuss/SKILL.md:20`
  - Modify `plugins/gin-workflow/src/skills/plan/SKILL.md:22`
  - Modify `plugins/gin-workflow/src/skills/tech-doc/SKILL.md:12-31`
  - Modify `docs/reference/orchestrator-contract.md:18-35,88-100`
  - Modify `docs/reference/cli.md:370-382`
  - Modify `docs/orchestrator/README.md:3-59`
  - Modify `docs/concepts/providers.md:3-36`
  - Modify `tests/gin_orchestrator/test_contract_v2.py:85-95`
  - Modify `tests/gin_orchestrator/test_contract_cli.py:30-40`
  - Modify `tests/workflow_core/test_skill_routing.py`
  - Test `tests/workflow_core/test_token_budget.py`
  - Test `tests/workflow_core/test_docs_coverage.py`
- **Provider role**: `backend`
- **Model:** `opus`
- **Effort:** `high`
- **Why:** Cross-module CLI contract extension (`gin-orchestrator dispatch`), workspace safety enforcement in `registry.py`, stage skill updates under tight 12,000-character token ceilings, and style-checked documentation updates.
- **Interfaces**:
  - CLI command `gin-orchestrator dispatch --workflow-id <id> --task-id <id> --role <provider_role> --model <model> [--effort <effort>] --workspace <path> (--objective <text> | --objective-file <path>) [--constraint <text>...] [--stage <stage>] [--agent <stem>] [--provider <provider>] [--repository <dir>] [--json]`.
  - Direct workspace validation in `ProviderRegistry.workspace_for(request)` when `request.isolation_policy.get("mode") == "direct"`.
- **Acceptance criteria**:
  - `CAPABILITIES` in `gin_orchestrator/cli.py` is `["health", "models", "routes", "reviewer", "doctor", "dispatch"]`.
  - `gin-orchestrator dispatch` works both when `.agent-workflow/orchestrator.local.yaml` exists and in `provider_mode: single` without `orchestrator.local.yaml` or `orchestrator.concurrency` (synthesizing `local` via `default_provider_model_config(harness)` and `orchestrator.concurrency = {p: 1 for p in local}` inside `_dispatch`), while `ProviderRegistry.from_effective_config` preserves its strict `orchestrator.concurrency is required for routed workers` check for direct callers.
  - In direct mode (`isolation_policy.get("mode") == "direct"`), `workspace_for(request)` enforces that when `request.provider_role not in ("review", "research", "docs")` and `request.generated_manifest.stage == "execute"`, `workspace_path` must be a non-symlink directory inside `worktree_root.resolve()` (`.planning/worktrees/<id>`), and allows `root.resolve()` or `worktree_root.resolve()` for `review`/`research`/`docs` or stages `review`, `discuss`, `plan`, `tech-doc`.
  - `gin-orchestrator dispatch` prints the `WorkerResult.to_dict()` JSON and exits `0` when `status == "completed"` or `1` when `status in {"failed", "cancelled"}`.
  - Every stage in `tests/workflow_core/test_token_budget.py` stays `<= 12,000` characters, and `tests/workflow_core/test_docs_coverage.py` passes with zero style or coverage violations.
- **Estimated complexity**: high

#### Steps

- [ ] **Step 1: Add failing tests in `test_contract_v2.py`, `test_contract_cli.py`, and `test_skill_routing.py`**
  - In `tests/gin_orchestrator/test_contract_v2.py:88` and `tests/gin_orchestrator/test_contract_cli.py:33`, update the expected `capabilities` list to:
    ```python
    ["health", "models", "routes", "reviewer", "doctor", "dispatch"]
    ```
  - In `tests/gin_orchestrator/test_contract_cli.py`, add tests for `gin-orchestrator dispatch`:
    - `test_dispatch_runs_worker_without_orchestrator_local_yaml_in_single_mode`: verifies `_dispatch` synthesizes `default_provider_model_config` and `concurrency` in `provider_mode: single` without `orchestrator.local.yaml`, runs a stub executable in `.planning/worktrees/task-1`, prints `WorkerResult` JSON with `status == "completed"`, and returns exit code `0`.
    - `test_dispatch_rejects_main_checkout_workspace_for_execute_stage`: verifies `gin-orchestrator dispatch --stage execute --role backend --workspace <repo_root>` fails with `status == "failed"` and `"worker_routes_unavailable"` / workspace safety error instead of mutating `<repo_root>`.
    - `test_dispatch_allows_main_checkout_workspace_for_review_and_plan_stages`: verifies `--stage review --role review --workspace <repo_root>` and `--stage discuss --role general --workspace <repo_root>` succeed.
    - `test_dispatch_exits_one_when_worker_result_is_failed`: verifies exit code `1` when `result.status == "failed"`.
  - In `tests/workflow_core/test_skill_routing.py`, add assertions that `execute/references/worker-lifecycle.md`, `execute/SKILL.md`, `review/SKILL.md`, `discuss/SKILL.md`, `plan/SKILL.md`, and `tech-doc/SKILL.md` reference `gin-orchestrator dispatch`.

- [ ] **Step 2: Run Track 5 tests to verify failure**
  - Run: `python3 -m unittest tests/gin_orchestrator/test_contract_v2.py tests/gin_orchestrator/test_contract_cli.py tests/workflow_core/test_skill_routing.py -v`
  - Expected: `FAIL`.

- [ ] **Step 3: Implement `workspace_for` direct mode and `resolver` route affinity in `registry.py` and `dispatch` in `gin_orchestrator/cli.py`**
  - In `plugins/gin-orchestrator/src/scripts/gin_orchestrator/registry.py:257-294`:
    - In `resolver(request)`:
      ```python
      def resolver(request):
          affinity_provider = (
              str(request.route_affinity[0])
              if request.route_affinity is not None and len(request.route_affinity) >= 2
              else None
          )
          main_harness = str(config.get("harness", "")) or affinity_provider or "claude"
          assignment = AssignmentRequest(
              request.task_id,
              request.provider_role,
              request.model,
              request.effort,
              main_harness,
          )
          candidates = list(
              resolve_assignment(
                  assignment,
                  config,
                  provider_local,
                  source_harness=affinity_provider or main_harness,
              )
          )
          if affinity_provider is not None and not any(
              c.provider == affinity_provider and c.model == request.model and (c.effort or None) == (request.effort or None)
              for c in candidates
          ):
              candidates.insert(
                  0,
                  RouteCandidate(affinity_provider, request.model, False, effort=request.effort),
              )
          return tuple(candidates)
      ```
    - In `workspace_for(request)`:
      ```python
      def workspace_for(request) -> Path:
          if request.isolation_policy.get("mode") == "direct":
              raw_supplied = request.isolation_policy.get("workspace_path")
              if not raw_supplied:
                  raise WorkspaceUnavailableError("direct workspace mode requires workspace_path")
              supplied_path = Path(str(raw_supplied))
              resolved = supplied_path.resolve()
              supported_worktree_root = worktree_root.resolve()
              supported_repo_root = root.resolve()
              if supplied_path.is_symlink() or not resolved.is_dir():
                  raise WorkspaceUnavailableError("direct workspace_path must be an existing non-symlink directory")
              stage = getattr(request.generated_manifest, "stage", "execute")
              if request.provider_role not in ("review", "research", "docs") and stage == "execute":
                  if not resolved.is_relative_to(supported_worktree_root):
                      raise WorkspaceUnavailableError("direct execute workspace violates worktree root safety")
              else:
                  if not (resolved.is_relative_to(supported_repo_root) or resolved.is_relative_to(supported_worktree_root)):
                      raise WorkspaceUnavailableError("direct workspace_path must reside inside repository or worktree root")
              return resolved
      ```
  - In `plugins/gin-orchestrator/src/scripts/gin_orchestrator/cli.py`:
    - Add `"dispatch"` to `CAPABILITIES = ["health", "models", "routes", "reviewer", "doctor", "dispatch"]`.
    - Import `DEFAULT_CATALOGS`, `ProviderLocalConfigError`, `default_provider_model_config` from `workflow_core.ext`, `ContextRequest`, `create_context_manifest` from `.context_manifest`, `ProviderRegistry` from `.registry`, `EXPECTED_OUTPUT_FIELDS`, `WorkerRequest` from `.worker_dispatch`, and `run_with_retries` from `.worker_scheduler`.
    - Implement `_dispatch(args: argparse.Namespace) -> tuple[dict[str, Any], int]`:
      ```python
      def _dispatch(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
          root = args.repository.resolve()
          objective = (
              args.objective_file.read_text(encoding="utf-8").strip()
              if args.objective_file is not None
              else (args.objective or "").strip()
          )
          if not objective:
              raise CliError("dispatch requires a non-empty --objective or --objective-file")
          config = load_effective_config(root)
          try:
              local = dict(load_local_config(root))
          except ProviderLocalConfigError:
              local = {}
          target_provider = str(args.provider or config.harness or "claude")
          for prov in {target_provider, str(config.harness or "claude")}:
              if prov and prov not in local and prov in DEFAULT_CATALOGS:
                  local[prov] = default_provider_model_config(prov)
          raw_cfg = config.to_dict()
          orch = dict(raw_cfg.get("orchestrator") or {})
          if not orch.get("concurrency"):
              orch["concurrency"] = {prov: 1 for prov in local}
          routing = dict(raw_cfg.get("routing") or {})
          merged_roles = roles(config)
          if args.role not in merged_roles:
              merged_roles[args.role] = {"preferred": [target_provider]}
          routing["roles"] = merged_roles
          effective = EffectiveConfig({**raw_cfg, "orchestrator": orch, "routing": routing}, root)
          registry = ProviderRegistry.from_effective_config(effective, provider_local=local)
          if registry.worker is None:
              raise CliError("worker dispatcher is not available")
          manifest = create_context_manifest(args.stage, ContextRequest())
          affinity = (
              (str(args.provider), str(args.model), args.effort)
              if args.provider
              else None
          )
          worker_request = WorkerRequest(
              objective=objective,
              constraints=tuple(args.constraint or ()),
              generated_manifest=manifest,
              isolation_policy={
                  "mode": "direct",
                  "workspace_path": str(args.workspace.resolve()),
              },
              expected_output=EXPECTED_OUTPUT_FIELDS,
              task_id=args.task_id,
              workflow_id=args.workflow_id,
              retry_identity=f"{args.workflow_id}:{args.task_id}:dispatch",
              provider_role=args.role,
              model=args.model,
              effort=args.effort,
              route_affinity=affinity,
              agent=args.agent,
          )
          result = run_with_retries(
              registry.worker,
              worker_request,
              max_retries=registry.worker_max_retries,
              worker_timeout_seconds=registry.worker_timeout_seconds,
          )
          return result.to_dict(), (0 if result.status == "completed" else 1)
      ```
    - Register the `dispatch` subparser in `main()` with `--workflow-id`, `--task-id`, `--role`, `--model`, `--effort`, `--workspace` (`type=Path, required=True`), mutually exclusive `--objective` / `--objective-file` (`type=Path`), `--constraint` (`action="append", default=[]`), `--stage` (`default="execute"`), `--agent`, `--provider`, `--repository`, and `--json`, and return the exit code (`0` or `1`) after printing `json.dumps(payload)`.

- [ ] **Step 4: Update stage skills (with explicit character trims) and documentation**
  - Update `plugins/gin-workflow/src/skills/execute/references/worker-lifecycle.md` (reducing total size from 1,357 chars to ~950 chars, saving ~400 chars for the `execute` stage budget):
    ```markdown
    # Worker Lifecycle

    ## Launching a worker

    Obtain the route from `gin-workflow routes dispatch --workflow-id <w> --task-id <id> --json`. Run `gin-orchestrator dispatch --workflow-id <w> --task-id <id> --role <role> --provider <provider> --model <model> [--effort <effort>] --stage execute --agent developer --workspace <worktree> --objective "<track objective and rules>" --json`. Verify the diff and tests. When it exits, run `gin-workflow notify --event worker_finished "<track>: <provider>"` (`worker_failed` on failure). If `gin-orchestrator` is absent or lacks `"dispatch"`, fall back to the main harness's native subagent (`invoke_subagent` on Antigravity, custom agent on OpenCode/Copilot) or in-session execution with a warning.

    ## Events

    Record lifecycle events in order: `worker.requested`, `worker.assigned`, `worker.started`, `worker.context_loaded`, `worker.progress_updated`, and one terminal event (`worker.completed`, `worker.failed`, or `worker.cancelled`). Emit `worker.unavailable` before fallback when an adapter is absent, or `context_unavailable` when required context is missing.

    Skip candidates whose circuit is open or adapter unhealthy; a queue wait timeout moves to the next candidate without tripping the circuit. Runtime events record the actual provider, model, and fallback flag without mutating the plan or Beads. If no candidate can run, fail with `worker_routes_unavailable` and leave the task open. Retries use a new attempt identity only for transient failures (`quota`, `rate_limit`, `service`); completed results are never rerun.
    ```
  - Update `plugins/gin-workflow/src/skills/execute/SKILL.md:35` to apply the hybrid dispatch rule:
    ```markdown
    2. When `provider` is the main harness and its native subagent supports the route (`claude` `Agent` with `model`, or `antigravity` `invoke_subagent(TypeName="developer", Model="inherit")` when `model` is `provider_default` and `effort` is null), spawn `gin-workflow:developer` with a bounded context: track text, file scope, `gin-workflow rules` output, worktree path, validation commands (never the parent transcript or secrets). Otherwise (`provider != main_harness`, `codex`/`opencode`/`copilot`, or `antigravity` with an explicit model/effort), dispatch via `gin-orchestrator dispatch` per [worker lifecycle](references/worker-lifecycle.md).
    ```
  - Update `plugins/gin-workflow/src/skills/review/SKILL.md:16,23` (trimming ~160 chars in step 3 of `Reviewing` while adding `gin-orchestrator dispatch` in step 2 of `Requesting` so `review` stays `< 11,900` chars):
    - In `Requesting` step 2: specify spawning `gin-workflow:code-reviewer` natively when `route.provider == main_harness` supports the route (`claude` `Agent`, or `antigravity` `invoke_subagent` at `provider_default`), else running `gin-orchestrator dispatch --workflow-id <id> --task-id <id> --role review --provider <provider> --model <model> [--effort <effort>] --stage review --agent code-reviewer --workspace <worktree> --objective "<review brief>" --json` (falling back to native subagent if `gin-orchestrator` is absent).
  - Update `plugins/gin-workflow/src/skills/discuss/SKILL.md:20`, `plan/SKILL.md:22`, and `tech-doc/SKILL.md:28,30,31` concisely so non-Claude main harnesses (or explicit model/effort routes on Antigravity) invoke `gin-orchestrator dispatch` with `--stage discuss|plan|tech-doc` and `--agent agent-researcher|docs-writer` when native subagent spawn cannot set the catalog `model` and `effort`.
  - Update `docs/reference/orchestrator-contract.md`, `docs/reference/cli.md`, `docs/orchestrator/README.md`, and `docs/concepts/providers.md` to document `"copilot"` harness support and `gin-orchestrator dispatch` (strictly adhering to `workflow_core.docs_check`: no numbered headings, no bold-label list items, no en/em dashes, no emoji).

- [ ] **Step 5: Run Track 5 and full repository test suites and commit**
  - Run: `python3 -m unittest tests/gin_orchestrator/test_contract_v2.py tests/gin_orchestrator/test_contract_cli.py tests/workflow_core/test_skill_routing.py tests/workflow_core/test_token_budget.py tests/workflow_core/test_docs_coverage.py -v`
  - Run: `python3 tests/test_all.py`
  - Expected: All tests pass (`OK`).
  - Commit: `git add plugins/ docs/ tests/ && git commit -m "feat(dispatch): add gin-orchestrator dispatch CLI, skill routing, and docs"`

## Integration
- **Branch**: `feat/non-claude-dispatch`
- **Merge strategy**: parallel-then-merge

## Validation
- [ ] All unit and integration tests pass (`python3 tests/test_all.py`)
- [ ] Installer smoke tests pass (`bash tests/install_smoke_test.sh`)
- [ ] Stage token budgets (`<= 12,000` chars) and agent budgets (`<= 4,000` chars) pass (`python3 -m unittest tests/workflow_core/test_token_budget.py -v`)
- [ ] Documentation coverage and style checks pass (`python3 -m unittest tests/workflow_core/test_docs_coverage.py -v`)

## Notes
- `Model:` and `Effort:` are chosen from the main harness catalog (`claude`: `haiku`, `sonnet`, `opus`; efforts `low`, `medium`, `high`, `xhigh`, `max`) using the route rubric.
- Deliverable merge-holds apply exclusively to the Parent Bead (`gin-workflow-dura`). Individual track beads close upon passing tests and code review to unblock downstream dependent tracks.
