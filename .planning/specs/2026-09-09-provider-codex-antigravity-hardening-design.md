# Provider Hardening, Codex Reasoning Effort, Antigravity CLI/Model Support, and Unified Health Probes

- **Status**: Draft (Under Review)
- **Date**: 2026-09-09
- **Target Components**: 
  - `plugins/gin-workflow/src/scripts/workflow_core/provider_config.py`
  - `plugins/gin-workflow/src/scripts/workflow_core/assignments.py`
  - `plugins/gin-workflow/src/scripts/workflow_core/setup_service.py`
  - `plugins/gin-workflow/src/scripts/workflow_providers/antigravity_worker.py`
  - `plugins/gin-workflow/src/scripts/workflow_providers/codex_worker.py`
  - `plugins/gin-workflow/src/scripts/workflow_providers/registry.py`
  - `plugins/gin-workflow/src/scripts/workflow_providers/routed_worker.py`
  - `plugins/gin-workflow/src/scripts/workflow_providers/circuit_breaker.py`
  - `plugins/gin-workflow/src/examples/providers.local.example.yaml`
  - `plugins/gin-workflow/src/skills/setup/SKILL.md`
  - `tests/workflow_core/` & `tests/workflow_providers/`

---

## 1. Context & Motivation

During cross-harness setup and execution, several critical issues were identified:
1. **Antigravity CLI Argument Omission**: `build_antigravity_invocation()` in `antigravity_worker.py` accepts a `model` parameter, but fails to inject `--model <model>` into the process arguments, leaving explicit model selection non-functional.
2. **Antigravity Executable Name Mismatch**: Users and agent harnesses commonly configure `antigravity` instead of `agy`, resulting in `command not found` errors since the installed binary is `agy`.
3. **Codex Placeholder Models**: `providers.local.example.yaml` contains invalid dummy aliases (`fast`, `standard`, `reasoning`) that fail when invoked against the OpenAI Codex CLI.
4. **Codex Reasoning Effort Configuration**: Codex models require configuring both `model` (e.g., `gpt-6-astra`) and `reasoning effort` (`low`, `medium`, `high`) per reasoning tier, while maintaining backward compatibility with scalar strings (`tier: "gpt-6-astra"`).
5. **CLI Executable Path Resolution**: Tools such as `claude` and `codex` are frequently installed under user-level paths (e.g. `~/.npm-global/bin`) which may not exist in non-login subshell `PATH` environments. Setup and runtime adapters need reliable, symlink-preserving executable path discovery.
6. **Unified Health Probing**:
   - `antigravity_worker.py` only probes `--help` rather than actively validating model viability with `MODEL_PROBE_PROMPT`.
   - `setup doctor` lacks machine-local provider health verification. Full model probing must be supported as a safe, isolated, opt-in operation (`doctor --probe`) without altering the lightweight default behavior of `doctor`.
7. **Outdated Example Models**: Examples in `providers.local.example.yaml` need updating to current, verified models such as Gemini 3.8 Flash for Antigravity.

---

## 2. Goals & Non-Goals

### Goals
- **Full Model Argument Support**: Ensure `agy` receives `--model <model>` positioned before `--print` whenever explicit model selection is active.
- **Structured Model Tier Targets**: Allow each reasoning tier in `providers.local.yaml` to specify either a scalar string or a mapping of `{model: str, effort: str}` (with `effort` restricted strictly to Codex).
- **Executable Auto-Discovery**: Reliably resolve harness paths (`claude`, `codex`, `agy`) across common user directories (`~/.npm-global/bin`, `~/.local/bin`, `/usr/local/bin`, Homebrew) without breaking versioned npm symlinks.
- **Robust Health Probing**: Align Antigravity model probing with Claude and Codex, using `--output-format json` to ensure valid responses pass `NativeCliRunner` parsing.
- **Safe Doctor Integration**: Provide an opt-in `--probe` capability in `doctor` that executes in isolated runtime directories, keeping default `doctor` fast, offline, and inexpensive.
- **100% Backward Compatibility**: Existing scalar string configurations must parse and execute unchanged.

### Non-Goals
- Cloud API calling or SDK integration (all execution remains through authenticated local CLIs).
- Modifying portable workflow contracts or plan schemas (effort remains an implementation detail of machine-local route resolution).

---

## 3. Technical Design Specification

### 3.1 Data Model & Configuration Schema (`workflow_core/provider_config.py` & `assignments.py`)

#### 3.1.1 Target Model Definition
Define a normalized immutable representation:
```python
CODEX_EFFORT_VALUES = frozenset({"low", "medium", "high", "xhigh"})

@dataclass(frozen=True)
class TierModelTarget:
    model: str
    effort: str | None = None

    def __post_init__(self) -> None:
        if not str(self.model).strip():
            raise ProviderLocalConfigError("model must be a non-empty string")
        if self.effort is not None:
            if str(self.effort) not in CODEX_EFFORT_VALUES:
                raise ProviderLocalConfigError(
                    f"effort must be one of: {', '.join(sorted(CODEX_EFFORT_VALUES))}"
                )
```

#### 3.1.2 Normalization in `ProviderModelConfig`
To preserve compatibility with existing tests and raw YAML objects:
```python
@dataclass(frozen=True)
class ProviderModelConfig:
    provider: str
    executable: str
    models: Mapping[str, TierModelTarget]

    def __post_init__(self) -> None:
        normalized = {}
        for tier, raw_target in self.models.items():
            if isinstance(raw_target, TierModelTarget):
                normalized[tier] = raw_target
            elif isinstance(raw_target, str):
                normalized[tier] = TierModelTarget(model=raw_target, effort=None)
            elif isinstance(raw_target, Mapping):
                normalized[tier] = TierModelTarget(
                    model=str(raw_target.get("model", "")),
                    effort=raw_target.get("effort"),
                )
            else:
                raise ProviderLocalConfigError(f"invalid model target for tier: {tier}")
        object.__setattr__(self, "models", MappingProxyType(normalized))

    def selection_mode(self, tier: str) -> str:
        try:
            target = self.models[tier]
        except KeyError as error:
            raise ProviderLocalConfigError(f"missing model tier: {tier}") from error
        return "provider_default" if target.model == PROVIDER_DEFAULT else "explicit"
```

#### 3.1.3 Validation Invariants
In `validate_provider_local_config(value)`:
- If `tier` is a mapping:
  - Required key: `model` (non-empty string).
  - Optional key: `effort` (only permitted if `provider == "codex"`). Reject `effort` on `claude` and `antigravity`.
  - Reject any unexpected keys.
- If `target.model == PROVIDER_DEFAULT`:
  - Permitted only for `provider == "antigravity"`.
  - Must not declare an `effort`.

#### 3.1.4 Updates to Invariant Call Sites (Resolving B1)
Update all 4 sites in the codebase to check `target.model` rather than comparing `target == PROVIDER_DEFAULT`:
1. `registry.py:214`: `any(target.model == PROVIDER_DEFAULT for target in local_config.models.values())`
2. `provider_config.py:31-34`: `target.model == PROVIDER_DEFAULT`
3. `assignments.py:172-181`: extract `target.model` and `target.effort` to construct `RouteCandidate(provider, target.model, is_fallback, effort=target.effort)`
4. `routed_worker.py:239`: route affinity and route key matching.

---

### 3.2 Executable Path Resolution (`workflow_core/executable_resolver.py`)

A pure helper to locate CLI binaries across user environments while preserving package symlinks:
```python
PROVIDER_EXE_ALIASES = {
    "antigravity": ("agy",),
}

COMMON_INSTALL_DIRS = (
    Path.home() / ".npm-global/bin",
    Path.home() / ".local/bin",
    Path.home() / ".local/share/pnpm",
    Path("/usr/local/bin"),
    Path("/home/linuxbrew/.linuxbrew/bin"),
)

def resolve_harness_executable(configured: str, provider: str | None = None) -> str | None:
    # 1. Reject relative paths containing slashes unless explicitly rooted
    candidate_path = Path(configured)
    if candidate_path.is_absolute():
        return os.path.abspath(str(candidate_path)) if os.access(candidate_path, os.X_OK) else None

    # 2. Check standard PATH via shutil.which
    found = shutil.which(configured)
    if found:
        return os.path.abspath(found)

    # 3. Check exact provider aliases (e.g. literal 'antigravity' -> 'agy')
    if provider in PROVIDER_EXE_ALIASES:
        for alias in PROVIDER_EXE_ALIASES[provider]:
            if configured == provider or configured == alias:
                found_alias = shutil.which(alias)
                if found_alias:
                    return os.path.abspath(found_alias)

    # 4. Search common installation directories
    names_to_check = [configured]
    if provider in PROVIDER_EXE_ALIASES and configured == provider:
        names_to_check.extend(PROVIDER_EXE_ALIASES[provider])

    for base_dir in COMMON_INSTALL_DIRS:
        for name in names_to_check:
            probe = base_dir / name
            if probe.is_file() and os.access(probe, os.X_OK):
                return os.path.abspath(str(probe))

    return None
```
*Key Rule*: We use `os.path.abspath` instead of `Path.resolve()` to avoid freezing versioned npm symlinks (`claude -> ../lib/node_modules/...`).

---

### 3.3 Worker Adapters & Invocations

#### 3.3.1 Antigravity Worker Adapter (`antigravity_worker.py`)
1. **Output Format & Flag Positioning (Resolving B2 & B3)**:
   ```python
   def build_antigravity_invocation(
       executable: str,
       model: str,
       workspace: Path,
       prompt: str,
       *,
       timeout_seconds: float = 900,
   ) -> NativeCliInvocation:
       resolved_workspace = Path(workspace).resolve()
       timeout_str = f"{int(timeout_seconds)}s"
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
       return NativeCliInvocation(tuple(argv), resolved_workspace, b"", timeout_seconds)
   ```
2. **Antigravity Health Probe**:
   ```python
   def antigravity_health(
       executable: str,
       *,
       help_text: str | None = None,
       model: str | None = None,
       native_runner: NativeCliRunner | None = None,
       workspace: Path | None = None,
   ) -> NativeHealth:
       help_text = probe_help(executable, "--help") if help_text is None else help_text
       if help_text is None:
           return NativeHealth(False, "executable_or_help_unavailable", False)
       options = frozenset(re.findall(r"--[A-Za-z0-9][A-Za-z0-9-]*", help_text))
       supported = "--model" in options and "--output-format" in options
       if "--print" not in options or "--sandbox" not in options:
           return NativeHealth(False, "required_flags_unverified", supported)
       health = NativeHealth(
           True,
           "ready" if supported else "explicit_model_selection_unverified",
           supported,
       )
       if not supported or model is None or model == PROVIDER_DEFAULT or native_runner is None or workspace is None:
           return health
       try:
           native_runner.run(
               build_antigravity_invocation(
                   executable,
                   model,
                   workspace,
                   MODEL_PROBE_PROMPT,
                   timeout_seconds=MODEL_PROBE_TIMEOUT_SECONDS,
               )
           )
       except NativeCliError as error:
           if error.kind is FailureKind.INVALID_MODEL:
               return NativeHealth(False, "invalid_model", supported)
       return health
   ```

#### 3.3.2 Codex Worker Adapter (`codex_worker.py`)
1. **Invocation with Effort**:
   ```python
   def build_codex_invocation(
       executable: str,
       model: str,
       workspace: Path,
       prompt: str,
       *,
       timeout_seconds: float = 900,
       effort: str | None = None,
   ) -> NativeCliInvocation:
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
       return NativeCliInvocation(tuple(argv), workspace, prompt.encode("utf-8"), timeout_seconds)
   ```
2. **Codex Health Probe Flag Check**:
   Validate that `-c` or `--config` exists in `codex exec --help` whenever effort is requested.

---

### 3.4 Registry & Dispatcher Synchronization (`registry.py`, `routed_worker.py`, `circuit_breaker.py`)

1. **Triple Key Caching (S1 & S2)**:
   - Synchronize the health cache key, circuit breaker key, and affinity key:
     `key = (candidate.provider, candidate.model, candidate.effort or "")`
   - In `routed_worker.py`:
     `route_key = f"{candidate.provider}:{candidate.selection_mode}:{candidate.model}:{candidate.effort or 'none'}"`
   - Ensure `effort` is included in worker event payloads (`worker.requested`, `worker.started`, `worker.result`).
2. **Factory Dispatch**:
   - `factory()` in `registry.py` passes `candidate.effort` to `CodexWorkerAdapter`.

---

### 3.5 Setup & Doctor Service Enhancements (`setup_service.py`)

1. **Upgrade Path Support in `_set_nested` (S10)**:
   - When setting a nested path (e.g. `providers.codex.models.low.model`), if the intermediate node is a scalar string instead of a mapping, convert it gracefully into `{"model": current_scalar}` before descending.
2. **Opt-In Health Probing in Doctor (B4, S7, S8)**:
   - Default `gin-workflow setup doctor`: Checks repository, config validity, and verifies executable existence via `resolve_harness_executable` (fast, free, offline).
   - Opt-in `gin-workflow setup doctor --probe`:
     - Reads `providers.local.yaml`.
     - Uses isolated probe workspaces: `.agent-workflow/runtime/health-probe/<provider>` (never repository root).
     - Probes each configured model tier.
     - Sets `checks["providers"] = all_healthy` (boolean root) and populates `checks_details["providers"]` with per-tier status.

---

### 3.6 Configuration Template (`providers.local.example.yaml`)

```yaml
schema_version: "2.3"
providers:
  claude:
    executable: claude
    models:
      low: haiku
      medium: sonnet
      high: opus
  antigravity:
    executable: agy
    models:
      low: gemini-3.8-flash
      medium: gemini-3.8-flash
      high: gemini-3.8-pro
  codex:
    executable: codex
    models:
      low:
        model: gpt-6-astra
        effort: low
      medium:
        model: gpt-6-astra
        effort: medium
      high:
        model: gpt-6-astra
        effort: high
```

---

## 4. Test Strategy & Verification Plan

1. **Unit Tests (`tests/workflow_core/test_provider_config.py`)**:
   - Parse scalar string tier vs mapping `{model, effort}`.
   - Reject invalid `effort` values.
   - Reject `effort` on `claude` and `antigravity`.
   - Reject `effort` combined with `provider_default`.
   - Validate post-init normalization with existing raw test dictionaries.
2. **Executable Resolution Tests**:
   - Absolute paths, PATH lookup, `antigravity` -> `agy` alias, fallback paths (`~/.npm-global/bin`), and symlink preservation.
3. **Adapter Tests (`tests/workflow_providers/test_worker_adapters.py`)**:
   - `build_antigravity_invocation`: `--model` placed before `--print`; `--output-format json` included.
   - `build_codex_invocation`: `-c model_reasoning_effort=...` placed before `-`.
4. **Health Probe Tests (`tests/workflow_providers/test_registry.py`)**:
   - `antigravity_health` returns `available=True` on non-JSON probe output or valid model output.
   - Only `INVALID_MODEL` produces `available=False`.
   - Health caching respects `(provider, model, effort)` triples.
5. **CLI & Setup Tests (`tests/workflow_core/test_setup_cli.py`)**:
   - `_set_nested` overriding scalar to mapping.
   - `doctor` returns boolean in `checks["providers"]`.
   - Package builds via `install.sh --platform all` match generated distributions.
