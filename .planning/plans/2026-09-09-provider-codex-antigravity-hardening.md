# Plan: Provider Hardening, Codex Reasoning Effort, Antigravity CLI/Model Support, and Unified Health Probes

> **For agentic workers:** REQUIRED SKILL: Use `executing-plans` to implement this plan. Authoritative task state is tracked via task-tracking capability (Beads); checkboxes (`- [ ]`) provide visual step breakdown.

**Goal:** Implement reliable Antigravity model argument passing, Codex reasoning effort tier configuration, harness executable auto-discovery across user environments, and safe opt-in health probing.

**Architecture:** Extend machine-local provider schema with normalized `TierModelTarget` objects while maintaining strict backward compatibility for scalar strings. Implement symlink-preserving executable discovery in `executable_resolver.py`. Update Antigravity and Codex CLI adapters with exact argument positioning and JSON outputs. Synchronize health cache and circuit breaker keys across `(provider, model, effort)` triples. Provide fast default `doctor` checks alongside isolated opt-in model probing.

**Tech Stack:** Python 3.12, `unittest`, subprocess, YAML, JSON/JSONL, native process boundaries (`NativeCliRunner`).

## Global Constraints
- Target repository: `gin-workflow`
- Supported schema version: `2.3`
- Machine-local provider configuration remains gitignored at `.agent-workflow/providers.local.yaml`
- No external cloud SDKs or network dependencies; all worker communication stays within authenticated local CLI boundaries (`agy`, `codex`, `claude`)
- Invariant: `effort` configuration is strictly exclusive to `codex`; `provider_default` is strictly exclusive to `antigravity`
- Executable path resolution must preserve package manager symlinks using `os.path.abspath` instead of `Path.resolve()`
- Model probes during `doctor --probe` must run in isolated workspaces (`.agent-workflow/runtime/health-probe/<provider>`), never in the repository root

---

## Model Guidance
- `default_model_class`: `standard_impl`
- `phase_guidance`:
  - `brainstorm`: `high_reasoning`
  - `design`: `high_reasoning`
  - `plan`: `standard_impl`
  - `implement`: `standard_impl`
  - `verify`: `standard_impl`
  - `review`: `high_reasoning`
  - `docs`: `cheap_simple`
- `override_rule`: Use `high_reasoning` for planning only when execution boundaries, dependency sequencing, or major tradeoffs are still unresolved.

---

## Requirement Analysis
- **Problem statement**:
  1. `antigravity_worker.py` drops `--model` during invocation, preventing users from selecting specific Gemini models.
  2. Users configure `antigravity` instead of `agy`, resulting in executable lookup failures.
  3. `providers.local.example.yaml` contains dummy model placeholders for Codex (`fast`, `standard`, `reasoning`).
  4. Codex reasoning effort cannot be specified alongside the model ID per tier without breaking schema compatibility.
  5. Local binaries in `~/.npm-global/bin` are not found when subshells lack custom `PATH` configurations.
  6. `antigravity_health` does not probe model execution and would fail if output format is not JSON.
  7. `setup doctor` lacks provider executable and model health verification.
- **Success criteria**:
  - `agy` receives `--model <model>` before `--print` and `--output-format json`.
  - `antigravity` literal resolves to `agy` automatically.
  - Codex configuration supports scalar `model` or mapping `{model, effort}` with `CODEX_EFFORT_VALUES`.
  - Executable auto-resolver detects binaries in `~/.npm-global/bin`, `~/.local/bin`, and system paths while preserving symlinks.
  - `antigravity_health` accurately verifies models with `MODEL_PROBE_PROMPT`.
  - `gin-workflow setup doctor` verifies executables by default, and offers opt-in `--probe` in isolated workspaces.
  - All 493+ tests pass without regression.
- **Constraints**:
  - Full backward compatibility for scalar string tiers in `providers.local.yaml`.
  - Deliverable merge-holds apply exclusively to the Parent Bead; Track Beads close upon passing tests and review.
- **Non-goals**:
  - Replacing the core routing architecture or changing portable workflow plan schemas.
  - Calling provider cloud APIs directly.

---

## Approach Options
### Option 1: Inline String Encoding
- Encode effort in model string (e.g. `gpt-6-astra:effort=low`).
- Pros: Minimal schema changes.
- Cons: Brittle parsing, poor user readability, error-prone string concatenation.

### Option 2: Structured Mapping with Backward Compatibility (Selected)
- Support both scalar string (`low: "model"`) and mapping (`low: {model: "model", effort: "low"}`).
- Pros: Clean, type-safe, human-readable, validates effort against allowed set, preserves 100% existing configs.
- Cons: Requires normalization in constructor and updates across router/cache keys.

### Recommended Approach
- Selected Option 2 as detailed in spec `.planning/specs/2026-09-09-provider-codex-antigravity-hardening-design.md`.

---

## Scope
- **In scope**:
  - `workflow_core/executable_resolver.py` (new)
  - `workflow_core/provider_config.py`
  - `workflow_core/assignments.py`
  - `workflow_core/setup_service.py`
  - `workflow_providers/antigravity_worker.py`
  - `workflow_providers/codex_worker.py`
  - `workflow_providers/registry.py`
  - `workflow_providers/routed_worker.py`
  - `workflow_providers/circuit_breaker.py`
  - `plugins/gin-workflow/src/examples/providers.local.example.yaml`
  - `plugins/gin-workflow/src/skills/setup/SKILL.md`
  - Associated unit and integration tests.
- **Out of scope**:
  - Portable workflow contracts (`EffectiveConfig` portable schema).
  - External package distribution outside `install.sh`.

---

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Bounded internal plugin refactoring with sequential track dependencies and immediate test verification.
```

---

## Tasks

### Track 1: Executable Path Resolution & Harness Discovery

**Metadata:**
- Task ID: `track-1`
- Dependencies: []
- Provider role: `backend`
- Reasoning: `medium`
- Model guidance: `standard_impl`

**Files:**
- Create: `plugins/gin-workflow/src/scripts/workflow_core/executable_resolver.py`
- Test: `tests/workflow_core/test_executable_resolver.py`

**Interfaces:**
- Produces: `resolve_harness_executable(configured: str, provider: str | None = None) -> str | None`
- Consumes: Standard library `os`, `shutil`, `pathlib.Path`

- [ ] **Step 1: Write failing unit tests for executable resolution**
Create `tests/workflow_core/test_executable_resolver.py` with tests for:
  - Absolute path resolution with executable check
  - Standard PATH lookup via `shutil.which`
  - Literal alias `antigravity` -> `agy`
  - Common install directory searches (`~/.npm-global/bin`, `~/.local/bin`, `/usr/local/bin`)
  - Symlink preservation (verify `os.path.islink()` remains true and target isn't resolved to versioned file)
  - Rejection of non-existent binaries (returns `None`)

- [ ] **Step 2: Run test to verify failure**
Run: `python3 -m unittest tests/workflow_core/test_executable_resolver.py`
Expected: FAIL (ModuleNotFoundError: No module named 'workflow_core.executable_resolver')

- [ ] **Step 3: Implement `resolve_harness_executable`**
Implement `plugins/gin-workflow/src/scripts/workflow_core/executable_resolver.py`:
```python
"""Safe harness executable discovery preserving package manager symlinks."""
from __future__ import annotations

import os
from pathlib import Path
import shutil

PROVIDER_EXE_ALIASES: dict[str, tuple[str, ...]] = {
    "antigravity": ("agy",),
}

COMMON_INSTALL_DIRS: tuple[Path, ...] = (
    Path.home() / ".npm-global/bin",
    Path.home() / ".local/bin",
    Path.home() / ".local/share/pnpm",
    Path("/usr/local/bin"),
    Path("/home/linuxbrew/.linuxbrew/bin"),
)

def resolve_harness_executable(configured: str, provider: str | None = None) -> str | None:
    if not configured or not str(configured).strip():
        return None
    raw = str(configured).strip()
    candidate = Path(raw)
    if candidate.is_absolute():
        return os.path.abspath(raw) if os.access(raw, os.X_OK) else None

    # Check current PATH
    found = shutil.which(raw)
    if found:
        return os.path.abspath(found)

    # Check exact provider aliases
    alias_matches: list[str] = []
    if provider and provider in PROVIDER_EXE_ALIASES:
        if raw == provider:
            alias_matches.extend(PROVIDER_EXE_ALIASES[provider])

    for alias in alias_matches:
        found_alias = shutil.which(alias)
        if found_alias:
            return os.path.abspath(found_alias)

    # Search common install directories
    candidates_to_probe = [raw, *alias_matches]
    for directory in COMMON_INSTALL_DIRS:
        for name in candidates_to_probe:
            probe = directory / name
            if probe.is_file() and os.access(probe, os.X_OK):
                return os.path.abspath(str(probe))

    return None
```

- [ ] **Step 4: Run test to verify pass**
Run: `python3 -m unittest tests/workflow_core/test_executable_resolver.py`
Expected: PASS

---

### Track 2: Schema Normalization & Model Tier Target

**Metadata:**
- Task ID: `track-2`
- Dependencies: [`track-1`]
- Provider role: `backend`
- Reasoning: `medium`
- Model guidance: `standard_impl`

**Files:**
- Modify: `plugins/gin-workflow/src/scripts/workflow_core/provider_config.py`
- Modify: `plugins/gin-workflow/src/scripts/workflow_core/assignments.py`
- Modify: `plugins/gin-workflow/src/scripts/workflow_providers/registry.py:214`
- Modify: `plugins/gin-workflow/src/scripts/workflow_providers/routed_worker.py:239`
- Test: `tests/workflow_core/test_provider_config.py`
- Test: `tests/workflow_core/test_assignments.py`

**Interfaces:**
- Produces: `TierModelTarget(model: str, effort: str | None = None)`, `CODEX_EFFORT_VALUES`, `RouteCandidate.effort`
- Consumes: `workflow_core.executable_resolver`

- [ ] **Step 1: Write failing tests for TierModelTarget and validation invariants**
In `tests/workflow_core/test_provider_config.py`:
  - Test scalar string tier loads as `TierModelTarget(model="haiku", effort=None)`
  - Test mapping tier `{model: "gpt-6-astra", effort: "low"}` loads successfully
  - Test mapping on provider other than `codex` with `effort` raises `ProviderLocalConfigError`
  - Test invalid effort raises `ProviderLocalConfigError`
  - Test `provider_default` with `effort` raises `ProviderLocalConfigError`
  - Test `ProviderModelConfig` initialized with raw strings/dicts normalizes in `__post_init__`
In `tests/workflow_core/test_assignments.py`:
  - Test `resolve_assignment` passes `target.model` and `target.effort` to `RouteCandidate`
  - Test `AssignmentManifest.to_dict()` includes `"effort"` when set.

- [ ] **Step 2: Run tests to verify failure**
Run: `python3 -m unittest tests/workflow_core/test_provider_config.py tests/workflow_core/test_assignments.py`
Expected: FAIL on new test cases.

- [ ] **Step 3: Implement TierModelTarget and update call sites**
In `provider_config.py`:
  - Define `CODEX_EFFORT_VALUES = frozenset({"low", "medium", "high", "xhigh"})`
  - Define `TierModelTarget` dataclass
  - Update `ProviderModelConfig.__post_init__` to normalize `models` values
  - Update `selection_mode()` to inspect `target.model == PROVIDER_DEFAULT`
  - Update `validate_provider_local_config()` to enforce provider constraints (effort only for codex)
In `assignments.py`:
  - Add `effort: str | None = None` to `RouteCandidate`
  - Update `resolve_assignment` to unpack `target.model` and `target.effort`
  - Update `AssignmentManifest.to_dict()` to include `effort` when present
In `registry.py:214`:
  - Update guard to: `any(target.model == PROVIDER_DEFAULT for target in local_config.models.values())`
In `routed_worker.py:239`:
  - Update affinity check to match `(candidate.provider, candidate.model, candidate.effort)`

- [ ] **Step 4: Run tests to verify pass**
Run: `python3 -m unittest tests/workflow_core/test_provider_config.py tests/workflow_core/test_assignments.py`
Expected: PASS

---

### Track 3: Antigravity & Codex Adapter Process Invocations

**Metadata:**
- Task ID: `track-3`
- Dependencies: [`track-2`]
- Provider role: `backend`
- Reasoning: `medium`
- Model guidance: `standard_impl`

**Files:**
- Modify: `plugins/gin-workflow/src/scripts/workflow_providers/antigravity_worker.py`
- Modify: `plugins/gin-workflow/src/scripts/workflow_providers/codex_worker.py`
- Test: `tests/workflow_providers/test_worker_adapters.py`

**Interfaces:**
- Produces: `build_antigravity_invocation` with `--model` before `--print` and `--output-format json`
- Produces: `antigravity_health` with model probing
- Produces: `build_codex_invocation` with `-c model_reasoning_effort=...`
- Consumes: `workflow_core.executable_resolver.resolve_harness_executable`

- [ ] **Step 1: Write failing tests for adapter invocations and health probes**
In `tests/workflow_providers/test_worker_adapters.py`:
  - Test `AntigravityWorkerAdapter` builds argv with `["--output-format", "json"]`
  - Test `AntigravityWorkerAdapter` includes `["--model", "gemini-3.8-flash"]` positioned immediately before `["--print", prompt]`
  - Test `AntigravityWorkerAdapter` omits `--model` when `model == "provider_default"`
  - Test `CodexWorkerAdapter` includes `["-c", "model_reasoning_effort=high"]` positioned before `"-"`
  - Test `antigravity_health` runs probe with `MODEL_PROBE_PROMPT` and returns `available=True` on valid non-JSON text or JSON output
  - Test `antigravity_health` returns `available=False` only on `FailureKind.INVALID_MODEL`

- [ ] **Step 2: Run tests to verify failure**
Run: `python3 -m unittest tests/workflow_providers/test_worker_adapters.py`
Expected: FAIL on argument assertions.

- [ ] **Step 3: Update `antigravity_worker.py` and `codex_worker.py`**
In `antigravity_worker.py`:
  - Update `build_antigravity_invocation`:
    ```python
    argv = [
        executable,
        "--add-dir",
        str(resolved_workspace),
        "--sandbox",
        "--output-format",
        "json",
        "--print-timeout",
        timeout_str,
    ]
    if model and model != PROVIDER_DEFAULT:
        argv.extend(["--model", model])
    argv.extend(["--print", prompt])
    ```
  - Update `antigravity_health` to take `model`, `native_runner`, `workspace`, invoke probe when `model != PROVIDER_DEFAULT`, and handle `INVALID_MODEL`.
In `codex_worker.py`:
  - Update `build_codex_invocation(..., effort=None)`:
    ```python
    argv = [
        executable,
        "exec",
        "--model",
        model,
        "--json",
        "--ephemeral",
        "--dangerously-bypass-approvals-and-sandbox",
        "--cd",
        str(Path(workspace).resolve()),
    ]
    if effort is not None:
        argv.extend(["-c", f"model_reasoning_effort={effort}"])
    argv.append("-")
    ```
  - Pass `effort` through `CodexWorkerAdapter`.

- [ ] **Step 4: Run tests to verify pass**
Run: `python3 -m unittest tests/workflow_providers/test_worker_adapters.py`
Expected: PASS

---

### Track 4: Router, Circuit Breaker & Health Cache Synchronization

**Metadata:**
- Task ID: `track-4`
- Dependencies: [`track-3`]
- Provider role: `backend`
- Reasoning: `medium`
- Model guidance: `standard_impl`

**Files:**
- Modify: `plugins/gin-workflow/src/scripts/workflow_providers/registry.py`
- Modify: `plugins/gin-workflow/src/scripts/workflow_providers/routed_worker.py`
- Modify: `plugins/gin-workflow/src/scripts/workflow_providers/circuit_breaker.py`
- Test: `tests/workflow_providers/test_registry.py`
- Test: `tests/workflow_providers/test_routed_worker.py`
- Test: `tests/workflow_providers/test_circuit_breaker.py`

**Interfaces:**
- Produces: Triple-key caching for health and circuit breaker `(provider, model, effort or "none")`
- Consumes: `RouteCandidate.effort`

- [ ] **Step 1: Write failing tests for triple-key health, breaker, and audit events**
In `test_registry.py`:
  - Test that different efforts for the same provider and model ID trigger distinct health probes.
  - Test that Antigravity model probe runs via `registry.worker.health["antigravity"]`.
In `test_circuit_breaker.py`:
  - Test breaker records failures per `(provider, model, effort)`.
In `test_routed_worker.py`:
  - Test that `route_key` and audit event payload include `effort`.

- [ ] **Step 2: Run tests to verify failure**
Run: `python3 -m unittest tests/workflow_providers/test_registry.py tests/workflow_providers/test_circuit_breaker.py tests/workflow_providers/test_routed_worker.py`
Expected: FAIL on new triple-key assertions.

- [ ] **Step 3: Update `registry.py`, `routed_worker.py`, and `circuit_breaker.py`**
In `registry.py`:
  - Include `antigravity` in runtime model probing (`if provider in ("claude", "codex", "antigravity"):`).
  - Cache key: `(provider, _candidate.model, _candidate.effort or "")`.
  - Pass `candidate.effort` to `CodexWorkerAdapter` in `factory()`.
  - Resolve executable via `resolve_harness_executable` in `factory()`.
In `circuit_breaker.py`:
  - Support `effort` in `record_failure`, `can_attempt`, `acquire` (defaulting to `""` for backward-compatible storage).
In `routed_worker.py`:
  - Update `_emit` to record `effort` in audit payloads.
  - Update `route_key = f"{candidate.provider}:{candidate.selection_mode}:{candidate.model}:{candidate.effort or 'none'}"`.

- [ ] **Step 4: Run tests to verify pass**
Run: `python3 -m unittest tests/workflow_providers/test_registry.py tests/workflow_providers/test_circuit_breaker.py tests/workflow_providers/test_routed_worker.py`
Expected: PASS

---

### Track 5: Doctor Opt-in Probing, Upgrade Path, and Example Configurations

**Metadata:**
- Task ID: `track-5`
- Dependencies: [`track-4`]
- Provider role: `general`
- Reasoning: `medium`
- Model guidance: `standard_impl`

**Files:**
- Modify: `plugins/gin-workflow/src/scripts/workflow_core/setup_service.py`
- Modify: `plugins/gin-workflow/src/examples/providers.local.example.yaml`
- Modify: `plugins/gin-workflow/src/skills/setup/SKILL.md`
- Test: `tests/workflow_core/test_setup_cli.py`
- Test: `tests/workflow_core/test_config_examples.py`

**Interfaces:**
- Produces: `gin-workflow setup doctor [--probe]`, updated `_set_nested` with scalar-to-mapping promotion
- Consumes: `workflow_core.executable_resolver.resolve_harness_executable`

- [ ] **Step 1: Write failing tests for `_set_nested` scalar promotion and doctor provider checks**
In `test_setup_cli.py`:
  - Test `_set_nested` when path encounters a scalar and promotes it to a dict:
    Setting `providers.codex.models.low.model=gpt-6-astra` on `low: fast` converts `low` to `{"model": "gpt-6-astra"}` without raising `SetupError`.
  - Test `doctor()` default returns `checks["providers"] = True` (boolean) based on executable presence.
  - Test `doctor(probe=True)` runs in `.agent-workflow/runtime/health-probe/` and populates detailed status.
In `test_config_examples.py`:
  - Test `providers.local.example.yaml` validates cleanly against new schema.

- [ ] **Step 2: Run tests to verify failure**
Run: `python3 -m unittest tests/workflow_core/test_setup_cli.py tests/workflow_core/test_config_examples.py`
Expected: FAIL.

- [ ] **Step 3: Update `setup_service.py`, examples, and documentation**
In `setup_service.py`:
  - Update `_set_nested(config, path, value)`: if `current[component]` is not a dict, promote it to `{"model": current[component]}` if converting to model target.
  - Update `doctor(repository, probe=False, **_)`:
    - If `providers.local.yaml` exists, check executables with `resolve_harness_executable`.
    - If `probe=True`, run probe invocations using isolated workspace `.agent-workflow/runtime/health-probe/<provider>`.
    - Store `checks["providers"] = all_healthy` (bool) and `details["providers"] = {...}`.
  - In `initialize` and `configure`: auto-resolve executable path via `resolve_harness_executable`.
Update `plugins/gin-workflow/src/examples/providers.local.example.yaml`:
  - Antigravity: `gemini-3.8-flash` (low/medium), `gemini-3.8-pro` (high).
  - Codex: `gpt-6-astra` with `effort: low`, `medium`, `high`.
Update `plugins/gin-workflow/src/skills/setup/SKILL.md`:
  - Mention reasoning effort specification in Question 4.
Rebuild distributions:
  - Run `./install.sh --platform all` outside sandbox to update `plugins/gin-workflow/dist/`.

- [ ] **Step 4: Run tests to verify pass**
Run: `python3 -m unittest tests/workflow_core/test_setup_cli.py tests/workflow_core/test_config_examples.py`
Expected: PASS

---

### Track 6: Verification & End-to-End Test Suite Execution

**Metadata:**
- Task ID: `track-6`
- Dependencies: [`track-1`, `track-2`, `track-3`, `track-4`, `track-5`]
- Provider role: `review`
- Reasoning: `medium`
- Model guidance: `standard_impl`

**Files:**
- Test: All tests under `tests/`
- Test: `tests/workflow_providers/test_harness_packaging.py`

**Interfaces:**
- Consumes: Complete repository test suite

- [ ] **Step 1: Execute full test discovery suite**
Run: `python3 -m unittest discover tests`
Expected: PASS (all 493+ tests pass).

- [ ] **Step 2: Execute packaging and distribution tests**
Run: `python3 -m unittest tests/workflow_providers/test_harness_packaging.py`
Expected: PASS (all dist artifacts are up to date and verified).

- [ ] **Step 3: Verification gate checklist**
Confirm compliance with `docs/verification-and-handoff-workflow.md`:
  - [ ] No regression on existing provider default behavior
  - [ ] Backward compatibility verified for legacy scalar configurations
  - [ ] Executable auto-resolver preserves symlinks and handles aliases
  - [ ] Doctor health probing is opt-in, non-blocking, and isolated

---

## Integration
- **Branch**: `feature/provider-codex-antigravity-hardening`
- **Merge strategy**: sequential

## Validation
- [ ] All unit tests pass (`python3 -m unittest discover tests`)
- [ ] Package validation passes (`tests/workflow_providers/test_harness_packaging.py`)
- [ ] `validate_plan_assignments` returns 0 diagnostics
- [ ] `providers.local.example.yaml` validates against updated schema
