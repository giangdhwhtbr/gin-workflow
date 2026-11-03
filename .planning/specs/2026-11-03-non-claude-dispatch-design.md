# Non-Claude Main Harness Dispatch & Cost-Control Wiring

Epic: gin-workflow-dura
Status: draft for user review.

## Goal and scope

When Codex, Antigravity, OpenCode, or Copilot is the main harness, tracks, reviews, and explorations run on workers at the catalog model and effort instead of in the main session.

### In scope
1. **Hybrid dispatch rule across stage skills (`execute`, `review`, `discuss`, `plan`, `tech-doc`)**:
   - Use native subagent spawn per harness when `route.provider == main_harness` **and** the harness's in-session subagent mechanism can express the resolved `route.model` and `route.effort`:
     - **Claude Code**: `Agent(subagent_type="gin-workflow:<role>", model=<route.model>)` (shipped in `gin-workflow-btt3`).
     - **Antigravity**: `invoke_subagent(TypeName="<role>", Model=<tier>)` when `route.model == "provider_default"` and `route.effort is None` (mapping tier/rank `weakest -> "flash_lite"`, `middle -> "flash"`, `strongest -> "pro"`).
   - Hand tracks, reviews, and explorations to the target CLI worker through a unified `gin-orchestrator dispatch` CLI command whenever:
     - `route.provider != main_harness` (cross-provider route), or
     - `main_harness` is `codex`, `opencode`, or `copilot` (whose in-session subagent tools do not accept per-spawn catalog model and effort arguments), or
     - `main_harness` is `antigravity` with an explicit `route.model != "provider_default"` or `route.effort is not None`.
2. **GitHub Copilot (`copilot`) harness and CLI worker support**:
   - Add `"copilot"` to `SUPPORTED_HARNESSES`, `DEFAULT_CATALOGS` (`Catalog(("provider_default",), ())`), `DEFAULT_EXECUTABLES` (`"copilot": "copilot"`), `PROVIDER_DEFAULT_PROVIDERS`, `CONFIG_SCHEMA["properties"]["models"]["propertyNames"]["enum"]`, `cli.py`, `project_detect.py`, and `setup_service.py`.
   - Add `copilot_worker.py` (`CopilotWorkerAdapter`, `copilot_health`, `build_copilot_invocation`) in `gin_orchestrator` and register `"copilot"` in `registry.py`, `cli.py`, `doctor.py`, and `native_cli.py`.
3. **Agent translation in `install.sh` and `install.ps1` for Codex, Antigravity, OpenCode, and Copilot**:
   - Keep `plugins/gin-workflow/src/agents/*.md` and `plugins/gin-qa/src/agents/e2e-tester.md` as the single canonical source.
   - Translate and package `agents/*.md` for `antigravity`, `codex`, `opencode`, and `copilot` alongside `claude`.
4. **Cost-control items moved from `gin-workflow-rm-cost-control` and wired into `gin-orchestrator dispatch`**:
   - Single constant `ORCHESTRATOR_DEFAULTS` in `gin_orchestrator/config.py` owning timeout (`timeout_seconds: 600.0`), retry (`max_retries: 2`), queue (`max_wait_seconds: 600`), and circuit breaker (`failure_threshold: 3`) defaults across `registry.py` and `worker_scheduler.py`.
   - Circuit breaker opening immediately on the first `QUOTA` or `AUTH` failure in `gin_orchestrator/circuit_breaker.py`.
   - Retries in `gin_orchestrator/worker_scheduler.py` restricted strictly to transient failure kinds (`quota`, `rate_limit`, `service`), passing the prior attempt's `changed_files` (`prior_changed_files`) into the next attempt's task prompt.

### Out of scope
- Redesigning the schema 2.9 model catalog structure (`Catalog(models, efforts)` and rank-mapping rules from `gin-workflow-btt3`).
- Changing Claude Code same-harness `Agent` dispatch behavior (shipped in `gin-workflow-btt3`).

## Requirements

### R1: Copilot Harness Registration and CLI Worker (`copilot_worker.py`)
1. `workflow_core/catalog.py`: Add `"copilot": Catalog(("provider_default",), ())` to `DEFAULT_CATALOGS`.
2. `workflow_core/provider_config.py`: Add `"copilot": "copilot"` to `DEFAULT_EXECUTABLES` and include `"copilot"` in `PROVIDER_DEFAULT_PROVIDERS`.
3. `workflow_core/configuration.py`, `workflow_core/schemas.py`, `workflow_core/cli.py`, `workflow_core/project_detect.py`, and `workflow_core/setup_service.py`: Include `"copilot"` in `SUPPORTED_HARNESSES`, `CONFIG_SCHEMA["properties"]["models"]["propertyNames"]["enum"]`, CLI `--harness`/`--provider` choices, provider binary detection, and repo/home marker detection (`.github/agents` or `~/.copilot`).
4. `gin_orchestrator/copilot_worker.py`:
   - `build_copilot_invocation(prompt, workspace, *, model=PROVIDER_DEFAULT, effort=None, agent=None, executable="copilot")` builds:
     `[executable, "-p", prompt, "--allow-all-tools", "--no-ask-user", "--output-format", "json", "--add-dir", str(resolved_workspace)]`, appending `["--model", model]` when `model != PROVIDER_DEFAULT`, `["--reasoning-effort", effort]` when `effort` is set, and `["--agent", agent]` when `agent` is set.
   - `copilot_health(executable="copilot", model=PROVIDER_DEFAULT, effort=None)` verifies `probe_help(executable, "--help")` contains `--prompt`, `--model`, `--reasoning-effort`, `--output-format`, and `--allow-all-tools`.
   - `CopilotWorkerAdapter` implements `WorkerProviderAdapter` using `NativeCliRunner` and records usage logs via `record_invocation_from_records(provider="copilot", ...)`.
5. `gin_orchestrator/antigravity_worker.py` and `gin_orchestrator/opencode_worker.py`:
   - `build_antigravity_invocation` and `AntigravityWorkerAdapter` accept optional `effort: str | None = None` (`--effort <effort>`) and `agent: str | None = None` (`--agent <agent>`).
   - `build_opencode_invocation` and `OpenCodeWorkerAdapter` accept optional `agent: str | None = None` (`--agent <agent>`).
   - `ClaudeWorkerAdapter` accepts optional `agent: str | None = None` (`--agent <agent>`).
6. `gin_orchestrator/{registry.py,cli.py,doctor.py,native_cli.py}`:
   - Register `"copilot"` in `ProviderRegistry.factory`, `health_builders`, `health_for`, `cli.py:HEALTH`, and `doctor.py:HEALTH`.
   - Pass `effort` in `registry.py` and `cli.py:_health` whenever `candidate.effort is not None` for providers that support effort (`claude`, `codex`, `antigravity`, `copilot`).
   - In `native_cli.py`, allowlist `COPILOT_HOME`, `GH_TOKEN`, `GITHUB_TOKEN`, `COPILOT_GITHUB_TOKEN`, `GH_HOST`, and `COPILOT_GH_HOST` in `sanitized_environment()`, and support `list_models("copilot")` by parsing model identifiers from `copilot help config`.

### R2: Agent Translation in `install.sh` and `install.ps1`
1. **Antigravity (`antigravity`)**:
   - Add `template_agents_for_antigravity` (`install.sh`) and `Convert-AntigravityAgents` (`install.ps1`) to rewrite canonical frontmatter tool names in `dist/antigravity/<plugin>/agents/*.md` to Antigravity's runtime tool names:
     - `view_file -> read_file`
     - `replace_file_content -> edit_file`
     - `write_to_file -> write_file`
     - Keep `grep_search`, `list_dir`, `search_web`, `run_command`.
2. **Codex (`codex`)**:
   - Add `template_agents_for_codex` (`install.sh`) and `Convert-CodexAgents` (`install.ps1`) to strip the Antigravity-specific `tools:` frontmatter line from `dist/codex/<plugin>/agents/*.md` while preserving `name:` and `description:`.
3. **OpenCode (`opencode`)**:
   - Add `template_agents_for_opencode` (`install.sh`) and `Convert-OpenCodeAgents` (`install.ps1`) to generate `dist/opencode/<plugin>/agents/*.md` with OpenCode frontmatter (`description:` and `mode: subagent`, stripping `name:` and `tools:`).
   - Update `install_opencode_bundle` (`install.sh` and `install.ps1`) to copy `dist/opencode/<plugin>/agents/*.md` into `${OPENCODE_CONFIG_DIR}/agents/` and track installed agent filenames in the OpenCode manifest for clean uninstall.
4. **Copilot (`copilot`)**:
   - Stop dropping `agents/` in `install_platform "copilot"` (`install.sh` and `install.ps1`).
   - Add `template_agents_for_copilot` (`install.sh`) and `Convert-CopilotAgents` (`install.ps1`) to translate `tools:` in `dist/copilot/<plugin>/agents/*.md` to deduplicated Copilot tool aliases (`view_file -> read`, `grep_search`/`list_dir` -> `search`, `search_web -> fetch`, `run_command -> bash`, `replace_file_content`/`write_to_file` -> `edit`).

### R3: Single Timeout/Retry Default Constant, Immediate QUOTA/AUTH Circuit Breaker, and Transient Retries with `changed_files`
1. **Single constant for timeout and retry defaults (`ORCHESTRATOR_DEFAULTS`)**:
   - In `gin_orchestrator/config.py`, define:
     ```python
     ORCHESTRATOR_DEFAULTS: dict[str, Any] = {
         "circuit_breaker": {"failure_threshold": 3},
         "queue": {"max_wait_seconds": 600},
         "worker": {"max_retries": 2, "timeout_seconds": 600.0},
     }
     ```
   - Update `gin_orchestrator/registry.py` (`ProviderRegistry` fields, `from_effective_config`, `build_worker_scheduler`) and `gin_orchestrator/worker_scheduler.py` (`WorkerScheduler.__init__`) to read their default values from `ORCHESTRATOR_DEFAULTS`.
2. **Circuit breaker opens on first `QUOTA` or `AUTH` failure**:
   - In `gin_orchestrator/circuit_breaker.py`, define `IMMEDIATE_OPEN_FAILURE_KINDS = frozenset({FailureKind.QUOTA, FailureKind.AUTH})`.
   - In `CircuitBreakerStore.record_failure()`, if `normalized_kind in IMMEDIATE_OPEN_FAILURE_KINDS`, transition `state` to `CircuitState.OPEN` immediately on the first failure (`failures >= 1`), regardless of `self.failure_threshold`.
3. **Transient-only retries (`quota`, `rate_limit`, `service`) with `prior_changed_files`**:
   - In `gin_orchestrator/worker_scheduler.py`, define `TRANSIENT_RETRY_FAILURE_KINDS = frozenset({"quota", "rate_limit", "service"})`.
   - Retry in `WorkerScheduler.execute()` only when `attempt < max_retries`, `result.retry_safe` is `True`, and `result.failure_kind in TRANSIENT_RETRY_FAILURE_KINDS`.
   - Add `prior_changed_files: tuple[str, ...] = ()` to `WorkerTaskSpec` (`gin_orchestrator/worker_dispatch.py`). When `prior_changed_files` is non-empty, `render_task_packet()` includes a `Prior attempt modified files:` section listing those paths.
   - Before each retry attempt in `WorkerScheduler.execute()`, replace `spec.prior_changed_files` with `tuple(result.changed_files)` from the failed attempt.

### R4: `gin-orchestrator dispatch` CLI Subcommand and Stage Skill Wiring
1. **`gin-orchestrator dispatch` subcommand (`gin_orchestrator/cli.py`)**:
   - Accept `--role <role>`, `--tier <tier>`, `--workspace <path>`, `--task-id <id>`, `--summary <text>` (or `--prompt-file <path>`), repeatable `--acceptance <item>`, `--allowed-path <glob>`, `--context-file <path>`, `--verification-cmd <cmd>`, optional `--agent <agent-name>`, `--workflow-id <id>`, and `--stage <stage>`.
   - Construct `ProviderRegistry.from_effective_config(repo_root)` and `registry.build_worker_scheduler(dispatcher)`.
   - Run the task through `WorkerScheduler.execute()` -> `RoutedWorkerDispatcher.dispatch()` so health checks, circuit breaker, fallback candidates, transient retries with `prior_changed_files`, and single-source timeouts/retries are enforced on every CLI worker invocation.
   - Output the serialized `WorkerResult` JSON payload and exit `0` on `status == "succeeded"` (or `1` otherwise).
2. **Stage skill and reference updates**:
   - Update `plugins/gin-workflow/src/skills/execute/references/worker-lifecycle.md`, `execute/SKILL.md`, `review/SKILL.md`, `discuss/SKILL.md`, `plan/SKILL.md`, and `tech-doc/SKILL.md` so non-Claude main harnesses and cross-provider routes invoke `gin-orchestrator dispatch` when native subagent spawn cannot set the catalog `model` and `effort`, while keeping all stage chains within the 12,000-character token budget.

## User Stories

### US-1: Non-Claude Main Harness Dispatches Work at Catalog Model and Effort
As a developer running `gin-workflow` on Codex, Antigravity, OpenCode, or Copilot, I want tracks, reviews, and explorations to run on workers at the resolved catalog model and effort instead of in the main session, so that model/effort routing is honored across all supported harnesses.

Acceptance criteria:
- When `main_harness` is `antigravity` and the resolved route uses `model: "provider_default"` with `effort: null`, the stage spawns `invoke_subagent` with `Model` mapped from the route tier (`flash_lite`, `flash`, `pro`).
- When `main_harness` is `codex`, `opencode`, or `copilot`, or when `route.provider != main_harness`, or when `antigravity` has an explicit model/effort, the stage dispatches the work via `gin-orchestrator dispatch` at the resolved `provider`, `model`, and `effort`.
- `gin-orchestrator dispatch` returns a structured JSON `WorkerResult` and records token/cost telemetry in `usage_logs`.

### US-2: Full Copilot Harness and Translated Agents Across All Platforms
As a user installing `gin-workflow` for Claude, Codex, Antigravity, OpenCode, or Copilot, I want `install.sh` and `install.ps1` to package translated agent files for every platform and support `copilot` as a first-class harness and worker provider, so that custom agents and routes work out of the box on all 5 platforms.

Acceptance criteria:
- `install.sh` and `install.ps1` produce platform-translated `agents/*.md` in `dist/claude`, `dist/antigravity`, `dist/codex`, `dist/opencode`, and `dist/copilot`, and install OpenCode agents into `${OPENCODE_CONFIG_DIR}/agents/`.
- `gin-workflow routes resolve --harness copilot` and `gin-orchestrator health --provider copilot` succeed without `unknown harness` or `unknown provider` errors.
- `build_copilot_invocation` passes `-p <prompt> --allow-all-tools --no-ask-user --output-format json --add-dir <workspace>` along with optional `--model`, `--reasoning-effort`, and `--agent`.

### US-3: Cost-Controlled Retries, Circuit Breaker, and Unified Defaults
As a workflow operator, I want worker dispatch to use one constant for timeout/retry defaults, open the circuit breaker on the first `QUOTA` or `AUTH` failure, and retry only transient failures (`quota`, `rate_limit`, `service`) with the prior attempt's `changed_files` passed to the next attempt, so that permanent failures do not waste tokens or corrupt worktrees.

Acceptance criteria:
- `ORCHESTRATOR_DEFAULTS` in `gin_orchestrator/config.py` is the single source of default values for `worker.timeout_seconds` (`600.0`), `worker.max_retries` (`2`), `queue.max_wait_seconds` (`600`), and `circuit_breaker.failure_threshold` (`3`).
- A single `QUOTA` or `AUTH` failure transitions the provider's circuit breaker to `OPEN` immediately even when `failure_threshold > 1`.
- `WorkerScheduler.execute()` retries only when `failure_kind` is `"quota"`, `"rate_limit"`, or `"service"`, and does not retry `"task"`, `"test"`, `"invalid_result_contract"`, `"auth"`, `"crash"`, `"invalid_model"`, or `"timeout"`.
- When a transient failure is retried, `result.changed_files` from attempt `N` is injected into attempt `N+1`'s `WorkerTaskSpec.prior_changed_files` and rendered in the prompt packet.

## Errors and compatibility

- **Backward compatibility with existing `config.yaml`**: Adding `"copilot"` to `SUPPORTED_HARNESSES`, `DEFAULT_CATALOGS`, and `CONFIG_SCHEMA` is purely additive; existing v2.9 configs for `claude`, `codex`, `antigravity`, and `opencode` continue to validate without migration.
- **Unconfigured `provider_default` routes**: For `antigravity`, `opencode`, and `copilot`, `DEFAULT_CATALOGS` uses `Catalog(("provider_default",), ())`, which resolves `model="provider_default", effort=None` out of the box when `models.<harness>` is omitted.
- **Circuit breaker state compatibility**: Existing `.agent-workflow/runtime/circuit-breaker.json` files remain compatible; only the transition condition for `QUOTA` and `AUTH` changes to immediate `OPEN`.
- **Token budget enforcement**: All edits to `SKILL.md` and `references/*.md` must keep every stage chain `<= 12,000` characters and every agent file `<= 4,000` characters.

## Testing

- **Unit tests for `copilot` harness & worker**:
  - Test `DEFAULT_CATALOGS["copilot"]`, `routes resolve --harness copilot`, and `CONFIG_SCHEMA` validation with `models.copilot`.
  - Test `build_copilot_invocation`, `copilot_health`, and `CopilotWorkerAdapter` in `tests/gin_orchestrator/`.
- **Packaging & installer tests**:
  - Update `tests/gin_orchestrator/test_harness_packaging.py` and `tests/install_smoke_test.{sh,ps1}` to verify translated `agents/*.md` for `claude`, `antigravity`, `codex`, `opencode`, and `copilot`.
- **Cost-control & dispatch tests**:
  - Test `ORCHESTRATOR_DEFAULTS` propagation to `ProviderRegistry` and `WorkerScheduler`.
  - Test `CircuitBreakerStore.record_failure()` opening immediately on the first `QUOTA` or `AUTH` failure while respecting `failure_threshold` for `RATE_LIMIT` / `SERVICE` / `TIMEOUT`.
  - Test `WorkerScheduler.execute()` retrying only `quota`, `rate_limit`, and `service` failures and passing `prior_changed_files` into the next attempt's `WorkerTaskSpec` and rendered prompt.
  - Test `gin-orchestrator dispatch` CLI end-to-end with stubbed runner.
- **Token budget test**:
  - Run `python3 tests/test_all.py` including `tests/workflow_core/test_token_budget.py`.
