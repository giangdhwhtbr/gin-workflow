# Non-Claude Main Harness Dispatch & Cost-Control Wiring

Epic: gin-workflow-dura
Status: draft for user review.

## Goal and scope

When Codex, Antigravity, OpenCode, or Copilot is the main harness, tracks, reviews, and explorations run on workers at the catalog model and effort instead of in the main session.

### In scope
1. **Hybrid dispatch rule across stage skills (`execute`, `review`, `discuss`, `plan`, `tech-doc`)**:
   - Use native subagent spawn per harness when `route.provider == main_harness` **and** the harness's in-session subagent mechanism can express the resolved `route.model` and `route.effort`:
     - **Claude Code**: `Agent(subagent_type="gin-workflow:<role>", model=<route.model>)` (shipped in `gin-workflow-btt3`).
     - **Antigravity**: `invoke_subagent(TypeName="<role>", Model="inherit")` when `route.model == "provider_default"` and `route.effort is None`.
   - Hand tracks, reviews, and explorations to the target CLI worker through a unified `gin-orchestrator dispatch` CLI command whenever:
     - `route.provider != main_harness` (cross-provider route), or
     - `main_harness` is `codex`, `opencode`, or `copilot` (whose in-session subagent tools do not accept per-spawn catalog `model` and `effort` arguments), or
     - `main_harness` is `antigravity` with an explicit `route.model != "provider_default"` or `route.effort is not None`.
   - When `gin-orchestrator` is not installed, mismatched, or lacks the `"dispatch"` capability (`orchestrator_missing` / `orchestrator_contract_mismatch` / `orchestrator_failed`), skills fall back to the main harness's native subagent (`Antigravity` `invoke_subagent`, `OpenCode`/`Copilot` custom agent) or in-session execution with a warning, matching the existing no-bundled-fallback contract.
2. **GitHub Copilot (`copilot`) harness and CLI worker support**:
   - Add `"copilot"` to `SUPPORTED_HARNESSES`, `DEFAULT_CATALOGS` (`Catalog(("provider_default",), ())`), `DEFAULT_EXECUTABLES` (`"copilot": "copilot"`), `PROVIDER_DEFAULT_PROVIDERS`, `CONFIG_SCHEMA["properties"]["models"]["propertyNames"]["enum"]`, `cli.py`, `project_detect.py`, and `setup_service.py`.
   - Add `copilot_worker.py` (`CopilotWorkerAdapter`, `copilot_health`, `build_copilot_invocation`) in `gin_orchestrator` and register `"copilot"` in `registry.py`, `cli.py`, `doctor.py`, and `native_cli.py`, including JSONL parsing for Copilot's `{"type": "assistant.message", "data": {"content": "..."}}` records.
3. **Agent translation in `install.sh` and `install.ps1` for Codex, Antigravity, OpenCode, and Copilot**:
   - Keep `plugins/gin-workflow/src/agents/*.md` and `plugins/gin-qa/src/agents/e2e-tester.md` in their canonical Antigravity tool vocabulary (`view_file`, `grep_search`, `list_dir`, `search_web`, `run_command`, `replace_file_content`, `write_to_file`).
   - Package `agents/*.md` for `antigravity` (as-is), `codex` (stripping the `tools:` frontmatter line), `opencode` (with OpenCode frontmatter and `<plugin>-<agent>.md` filename prefix in `dist/opencode/agents/` and `~/.config/opencode/agents/`), and `copilot` (translating `tools:` to Copilot tool names in `plugins/<plugin>/dist/copilot/<plugin>/agents/*.md`), alongside `claude-code`.
4. **Cost-control items moved from `gin-workflow-rm-cost-control` and wired into `gin-orchestrator dispatch`**:
   - Single constant `ORCHESTRATOR_DEFAULTS` in `gin_orchestrator/config.py` owning timeout (`timeout_seconds: 900.0`), retry (`max_retries: 2`), queue (`max_wait_seconds: 600`), and circuit breaker (`failure_threshold: 3`) defaults across `registry.py`, `worker_scheduler.py`, and worker adapters.
   - Circuit breaker opening immediately on the first `QUOTA` or `AUTH` failure in `gin_orchestrator/circuit_breaker.py`.
   - Retries in `gin_orchestrator/worker_scheduler.py` restricted strictly to transient provider failure blockers (`provider_failure:quota`, `provider_failure:rate_limit`, `provider_failure:service`), passing the prior attempt's `changed_files` (`prior_changed_files` on `WorkerRequest`) into the next attempt's payload.

### Out of scope
- Redesigning the schema 2.9 model catalog structure (`Catalog(models, efforts)` and rank-mapping rules from `gin-workflow-btt3`).
- Changing Claude Code same-harness `Agent` dispatch behavior (shipped in `gin-workflow-btt3`).
- Multi-process shared semaphore locking for `concurrency` or `CircuitBreakerStore` across separate OS processes.

## Requirements

### R1: Copilot Harness Registration and CLI Worker (`copilot_worker.py`)
1. `workflow_core/catalog.py`: Add `"copilot": Catalog(("provider_default",), ())` to `DEFAULT_CATALOGS`.
2. `workflow_core/provider_config.py`: Add `"copilot": "copilot"` to `DEFAULT_EXECUTABLES` and include `"copilot"` in `PROVIDER_DEFAULT_PROVIDERS`.
3. `workflow_core/configuration.py`, `workflow_core/schemas.py`, `workflow_core/cli.py`, `workflow_core/project_detect.py`, and `workflow_core/setup_service.py`:
   - Include `"copilot"` in `SUPPORTED_HARNESSES`, `CONFIG_SCHEMA["properties"]["models"]["propertyNames"]["enum"]`, CLI `--harness`/`--provider` choices, and `detect_project()` provider binary checks.
   - In `setup_service.py:detect()`, add `("copilot", ".github/agents")` marker detection.
   - Update `registry.py:226`, `assignments.py:48`, and `gin_orchestrator/routes.py:89` error messages from `"antigravity and opencode"` to `"antigravity, opencode, and copilot"`.
4. `gin_orchestrator/copilot_worker.py` and `native_cli.py`:
   - Follow the exact signature convention of existing worker bridges:
     `build_copilot_invocation(executable: str, model: str, workspace: Path, prompt: str, *, timeout_seconds: float = 900, effort: str | None = None, agent: str | None = None) -> NativeCliInvocation`.
   - Build argv: `[executable, "-p", prompt, "--allow-all-tools", "--no-ask-user", "--output-format", "json", "--add-dir", str(resolved_workspace)]`, appending `["--model", model]` when `model and model != PROVIDER_DEFAULT`, `["--reasoning-effort", effort]` when `effort` is set, and `["--agent", agent]` when `agent` is set.
   - Add `env_extra: Mapping[str, str] = field(default_factory=dict, repr=False)` to `NativeCliInvocation` (`native_cli.py`), frozen via `MappingProxyType(dict(self.env_extra))` in `__post_init__` and merged into `process` `env` in `NativeCliRunner.run`. `build_copilot_invocation` populates `env_extra` with any present keys from `("COPILOT_HOME", "GH_TOKEN", "GITHUB_TOKEN", "COPILOT_GITHUB_TOKEN", "GH_HOST", "COPILOT_GH_HOST")` so GitHub tokens are exposed only to `copilot` worker invocations, never to other providers or `probe_help`, and never appear in `repr(invocation)`.
   - In `native_cli.py:direct_worker_result()` and `_diagnostic_from_stdout()`, inspect nested `record.get("data")` mappings (specifically `data.get("content")` and `data.get("message")`) because `copilot --output-format json` emits JSONL records shaped `{"type": "assistant.message", "data": {"content": "...", "model": "..."}}` and `{"type": "result", "exitCode": 0, "usage": {...}}`.
   - `copilot_health(executable: str, *, help_text: str | None = None, model: str | None = None, native_runner: NativeCliRunner | None = None, workspace: Path | None = None, effort: str | None = None) -> NativeHealth`:
     - Verify `probe_help(executable, "--help")` contains `--prompt`, `--allow-all-tools`, and `--output-format` as required flags, and `--model` (plus `--reasoning-effort` when `effort is not None`) for `supports_model_selection`.
     - When `model` is set and `model != PROVIDER_DEFAULT` and `native_runner` and `workspace` are provided, run `MODEL_PROBE_PROMPT` and return `NativeHealth(False, "invalid_model", supported)` on `FailureKind.INVALID_MODEL`.
   - `CopilotWorkerAdapter(SynchronousWorkerAdapter)` with `provider_name = "copilot"` accepts `native_dispatch`, `native_runner`, `executable`, `model`, `workspace`, `timeout_seconds`, `effort`, and `agent`.
5. `gin_orchestrator/antigravity_worker.py`, `opencode_worker.py`, and `claude_worker.py`:
   - `build_antigravity_invocation`, `antigravity_health`, and `AntigravityWorkerAdapter` accept optional `effort: str | None = None` (`--effort <effort>`) and `agent: str | None = None` (`--agent <agent>`).
   - `build_opencode_invocation` and `OpenCodeWorkerAdapter` accept optional `agent: str | None = None` (`--agent <agent>`).
   - `build_claude_invocation` and `ClaudeWorkerAdapter` accept optional `agent: str | None = None` (`--agent <agent>`).
6. `gin_orchestrator/{registry.py,cli.py,doctor.py,native_cli.py}`:
   - Register `"copilot"` in `ProviderRegistry.factory`, `health_builders`, `health_for`, `cli.py:HEALTH`, and `doctor.py:HEALTH`.
   - Pass `effort` in `registry.py` and `cli.py:_health` when `effort is not None` for `("claude", "codex", "antigravity", "copilot")`.
   - Map `request.agent` (canonical agent stem such as `"developer"`, `"code-reviewer"`, `"agent-researcher"`, `"docs-writer"`, `"qa-agent"`, or `"gin-workflow:developer"`) per target provider inside `ProviderRegistry.factory`:
     - `claude`: `"gin-workflow:<stem>"` (preserving an explicit `"<plugin>:<stem>"` prefix if given)
     - `opencode`: `"gin-workflow-<stem>"` (preserving an explicit `"gin-qa-<stem>"` prefix if given)
     - `antigravity` and `copilot`: `"<stem>"`
     - `codex`: omitted (`codex exec` has no `--agent` flag).
   - In `native_cli.py:list_models("copilot")`, run `[executable, "help", "config"]` and parse the documented model IDs under the `model` configuration section.

### R2: Agent Translation in `install.sh` and `install.ps1`
1. **Antigravity (`antigravity`)**:
   - Keep `plugins/<plugin>/dist/antigravity/agents/*.md` as-is because source agent files in `plugins/*/src/agents/*.md` already use Antigravity's canonical tool names (`view_file`, `grep_search`, `list_dir`, `search_web`, `run_command`, `replace_file_content`, `write_to_file`).
2. **Codex (`codex`)**:
   - Add `template_agents_for_codex` (`install.sh`) and `Convert-CodexAgents` (`install.ps1`) to strip the `tools:` frontmatter line from `plugins/<plugin>/dist/codex/agents/*.md` while preserving `name:` and `description:`.
3. **OpenCode (`opencode`)**:
   - Add `template_agents_for_opencode` (`install.sh`) and `Convert-OpenCodeAgents` (`install.ps1`) inside `install_opencode_bundle` / `Install-OpenCodeBundle` to write `agents/<plugin>-<stem>.md` (e.g. `agents/gin-workflow-developer.md`, `agents/gin-qa-e2e-tester.md`) into the OpenCode bundle (`plugins/<plugin>/dist/opencode/agents/` for global builds, or `$PROJECT_DIR/.opencode/agents/` for `--project` installs) with OpenCode frontmatter (`description:` and `mode: subagent`, omitting `name:` and `tools:`).
   - During global OpenCode installation (`install_plugin` in `install.sh` and `Install-Plugin` in `install.ps1`), also copy `dist/opencode/agents/<plugin>-*.md` into `${HOME}/.config/opencode/agents/` (and remove `${HOME}/.config/opencode/agents/${p_name}-*.md` on `--uninstall`). The `<plugin>-` filename prefix prevents colliding with any user-created `.opencode/agents/*.md` or `~/.config/opencode/agents/*.md` files.
4. **Copilot (`copilot`)**:
   - Update `install_platform "copilot"` (`install.sh` and `install.ps1`) to copy and translate `agents/*.md` into `plugins/<plugin>/dist/copilot/<plugin>/agents/*.md`.
   - Add `template_agents_for_copilot` (`install.sh`) and `Convert-CopilotAgents` (`install.ps1`) to map canonical tool names in `tools:` to deduplicated Copilot tool names (`view_file -> view`, `grep_search -> grep`, `list_dir -> glob`, `search_web -> web_fetch`, `run_command -> bash`, `replace_file_content`/`write_to_file` -> `edit`).

### R3: Single Timeout/Retry Default Constant, Immediate QUOTA/AUTH Circuit Breaker, and Transient Retries with `changed_files`
1. **Single constant for timeout and retry defaults (`ORCHESTRATOR_DEFAULTS`)**:
   - In `gin_orchestrator/config.py`, update `ORCHESTRATOR_DEFAULTS` to include `timeout_seconds`:
     ```python
     ORCHESTRATOR_DEFAULTS: Mapping[str, Mapping[str, Any]] = {
         "circuit_breaker": {"failure_threshold": 3},
         "queue": {"max_wait_seconds": 600},
         "worker": {"max_retries": 2, "timeout_seconds": 900.0},
     }
     ```
   - Remove hardcoded duplicate fallback literals in `gin_orchestrator/registry.py` (`ProviderRegistry` defaults at lines 107–108, `from_effective_config` at lines 215–216, 244, 250–252, 374), `gin_orchestrator/worker_scheduler.py` (`WorkerScheduler.__init__` defaults at lines 91–92), and worker adapters (`claude_worker.py`, `codex_worker.py`, `antigravity_worker.py`, `opencode_worker.py`, `copilot_worker.py`), referencing `ORCHESTRATOR_DEFAULTS` instead.
2. **Circuit breaker opens on first `QUOTA` or `AUTH` failure**:
   - In `gin_orchestrator/circuit_breaker.py`, define `IMMEDIATE_OPEN_FAILURE_KINDS = frozenset({FailureKind.QUOTA, FailureKind.AUTH})`.
   - In `CircuitBreakerStore.record_failure()`, transition `state` to `CircuitState.OPEN` when `state is CircuitState.HALF_OPEN or kind in IMMEDIATE_OPEN_FAILURE_KINDS or failures >= self.failure_threshold`.
3. **Transient-only retries (`quota`, `rate_limit`, `service`) with `prior_changed_files`**:
   - In `gin_orchestrator/worker_dispatch.py`, add optional fields `prior_changed_files: tuple[str, ...] = ()` and `agent: str | None = None` to `WorkerRequest`, and include `"prior_changed_files": list(self.prior_changed_files)` (when non-empty) and `"agent": self.agent` (when set) in `WorkerRequest.to_payload()`.
   - In `gin_orchestrator/worker_scheduler.py`, define:
     `TRANSIENT_FAILURE_BLOCKERS = frozenset({"provider_failure:quota", "provider_failure:rate_limit", "provider_failure:service"})`.
   - Extract a reusable retry helper `run_with_retries(dispatcher, request: WorkerRequest, *, max_retries: int, worker_timeout_seconds: float) -> WorkerResult` used by both `WorkerScheduler._run()` and `gin-orchestrator dispatch`.
   - In `run_with_retries()`, after an attempt returns `(result, retry_safe)` with `result.status != "completed"`, retry only when `attempt < max_retries`, `retry_safe` is `True`, and `any(b in TRANSIENT_FAILURE_BLOCKERS for b in result.blockers)`. Note: because `FailureKind.QUOTA` immediately opens that candidate's circuit breaker in `RoutedWorkerDispatcher`, retrying after `provider_failure:quota` automatically fails over to the next healthy fallback candidate (or returns `worker_routes_unavailable` immediately if no fallback exists). Non-transient blockers (`timeout`, `invalid_result_contract`, `provider_failure:auth`, `provider_failure:crash`, `provider_failure:invalid_model`, task/test failures) are not retried.
   - When constructing the retry request via `WorkerScheduler._retry_request(request, attempt, prior_changed_files=result.changed_files)`, set `prior_changed_files=tuple(result.changed_files)` on the new `WorkerRequest`.

### R4: `gin-orchestrator dispatch` CLI Subcommand and Stage Skill Wiring
1. **`gin-orchestrator dispatch` subcommand (`gin_orchestrator/cli.py`)**:
   - Add `"dispatch"` to `CAPABILITIES` in `gin_orchestrator/cli.py`.
   - Add subcommand `gin-orchestrator dispatch` accepting:
     `--workflow-id <id>`, `--task-id <id>`, `--role <provider_role>`, `--model <model>`, `[--effort <effort>]`, `--workspace <path>`, `--objective <text>` (or `--objective-file <path>`), repeatable `--constraint <text>`, `--stage <stage>` (default `"execute"`), `--agent <stem>`, `--provider <provider>` (optional route affinity), and `[--repository <dir>] [--json]`.
   - `_dispatch(args)` handles both `provider_mode: multi` (with `.agent-workflow/orchestrator.local.yaml`) and single-harness default configurations (where `.agent-workflow/orchestrator.local.yaml` or `orchestrator.concurrency` may not exist yet):
     - Load `config = load_effective_config(root)`.
     - Load `local = load_local_config(root)` if `.agent-workflow/orchestrator.local.yaml` exists; otherwise synthesize `local = default_provider_model_config((args.provider or config.harness or "claude",))` from `DEFAULT_EXECUTABLES` so single-harness Codex, Antigravity, OpenCode, and Copilot users can run `gin-orchestrator dispatch` without manually creating `orchestrator.local.yaml`.
     - If `config.get("orchestrator", {}).get("concurrency")` is not set, inject a synthetic `orchestrator.concurrency = {p: 1 for p in local}` into the `EffectiveConfig` passed to `ProviderRegistry.from_effective_config` inside `_dispatch()` (keeping `ProviderRegistry.from_effective_config`'s strict `orchestrator.concurrency is required` check intact for direct library callers).
     - Extend `workspace_for(request)` in `registry.py` so that when `request.isolation_policy.get("mode") == "direct"`, `workspace_path` is validated by stage/role:
       - For implementation (`request.provider_role not in ("review", "research", "docs")` and `stage == "execute"`), `workspace_path` must resolve to an existing directory inside `worktree_root` (`.planning/worktrees/<id>`), preventing an implementation worker from mutating the main checkout.
       - For read-only or non-worktree roles (`review`, `research`, `docs`, or stages `review`, `discuss`, `plan`, `tech-doc`), `workspace_path` may resolve to `root` or `worktree_root`.
     - Build `WorkerRequest` with `create_context_manifest(args.stage, ContextRequest())`, `isolation_policy={"mode": "direct", "workspace_path": str(args.workspace.resolve())}`, `route_affinity=(args.provider, args.model, args.effort or "")` when `--provider` is given, and `agent=args.agent`.
     - Run `run_with_retries(registry.worker, worker_request, max_retries=registry.worker_max_retries, worker_timeout_seconds=registry.worker_timeout_seconds)`.
     - Print the `WorkerResult` dictionary as JSON (`status`, `task_id`, `summary`, `changed_files`, `commits`, `tests`, `evidence`, `blockers`, `knowledge_candidates`) and exit `0` when `result.status == "completed"` (or `1` when `result.status in {"failed", "cancelled"}`).
2. **Stage skill, reference, and docs updates within token budget**:
   - Update `plugins/gin-workflow/src/skills/execute/references/worker-lifecycle.md` to replace the manual `<provider>_worker.py` argv instruction with `gin-orchestrator dispatch`, while trimming prose in `worker-lifecycle.md` (~250 chars) and `review/SKILL.md` (~150 chars) so both `execute` (`11,994` chars today) and `review` (`11,824` chars today) stay well below the `12,000`-character ceiling.
   - Update `execute/SKILL.md`, `review/SKILL.md`, `discuss/SKILL.md`, `plan/SKILL.md`, and `tech-doc/SKILL.md` concisely so non-Claude main harnesses and cross-provider routes use `gin-orchestrator dispatch` when native subagent spawn cannot set the catalog `model` and `effort`, keeping every stage in `STAGES` `<= 12,000` characters (`tests/workflow_core/test_token_budget.py`).
   - Document `gin-orchestrator dispatch` and `"copilot"` in `docs/reference/orchestrator-contract.md`, `docs/reference/cli.md`, `docs/orchestrator/README.md`, and `docs/concepts/providers.md`.

## User Stories

### US-1: Non-Claude Main Harness Dispatches Work at Catalog Model and Effort
As a developer running `gin-workflow` on Codex, Antigravity, OpenCode, or Copilot, I want tracks, reviews, and explorations to run on workers at the resolved catalog model and effort instead of in the main session, so that model/effort routing is honored across all supported harnesses.

Acceptance criteria:
- When `main_harness` is `antigravity` and the resolved route uses `model: "provider_default"` with `effort: null`, the stage can spawn `invoke_subagent(TypeName="<role>", Model="inherit")`.
- When `main_harness` is `codex`, `opencode`, or `copilot`, or when `route.provider != main_harness`, or when `antigravity` has an explicit model/effort, the stage dispatches the work via `gin-orchestrator dispatch` at the resolved `provider`, `model`, and `effort`, even in `provider_mode: single` without `.agent-workflow/orchestrator.local.yaml`.
- `gin-orchestrator dispatch` returns a structured JSON `WorkerResult` with `status` in `{"completed", "failed", "cancelled"}` and exits `0` on `"completed"`.

### US-2: Full Copilot Harness and Translated Agents Across All Platforms
As a user installing `gin-workflow` for Claude, Codex, Antigravity, OpenCode, or Copilot, I want `install.sh` and `install.ps1` to package translated agent files for every platform and support `copilot` as a first-class harness and worker provider, so that custom agents and routes work out of the box on all 5 platforms.

Acceptance criteria:
- `install.sh` and `install.ps1` produce platform-appropriate `agents/*.md` in `plugins/<plugin>/dist/{claude-code,antigravity,codex,opencode}` and `plugins/<plugin>/dist/copilot/<plugin>/agents/`, and install prefixed OpenCode agents (`gin-workflow-*.md`, `gin-qa-*.md`) into `~/.config/opencode/agents/`.
- `gin-workflow routes resolve --harness copilot` and `gin-orchestrator health --provider copilot` succeed without `unknown harness` or `unknown provider` errors.
- `build_copilot_invocation` passes `-p <prompt> --allow-all-tools --no-ask-user --output-format json --add-dir <workspace>` along with optional `--model`, `--reasoning-effort`, and `--agent`, and `direct_worker_result` parses Copilot's `{"type": "assistant.message", "data": {"content": "..."}}` JSONL output.

### US-3: Cost-Controlled Retries, Circuit Breaker, and Unified Defaults
As a workflow operator, I want worker dispatch to use one constant for timeout/retry defaults, open the circuit breaker on the first `QUOTA` or `AUTH` failure, and retry only transient failures (`quota`, `rate_limit`, `service`) with the prior attempt's `changed_files` passed to the next attempt, so that permanent failures do not waste tokens or corrupt worktrees.

Acceptance criteria:
- `ORCHESTRATOR_DEFAULTS` in `gin_orchestrator/config.py` is the single source of default values for `worker.timeout_seconds` (`900.0`), `worker.max_retries` (`2`), `queue.max_wait_seconds` (`600`), and `circuit_breaker.failure_threshold` (`3`).
- A single `QUOTA` or `AUTH` failure transitions the provider's circuit breaker to `OPEN` immediately even when `failure_threshold > 1`.
- `run_with_retries()` / `WorkerScheduler._run()` retries only when `result.blockers` contains `"provider_failure:quota"`, `"provider_failure:rate_limit"`, or `"provider_failure:service"`, and does not retry `"timeout"`, `"invalid_result_contract"`, `"provider_failure:auth"`, `"provider_failure:crash"`, `"provider_failure:invalid_model"`, or task/test failures.
- When a transient failure is retried, `result.changed_files` from attempt `N` is injected into attempt `N+1`'s `WorkerRequest.prior_changed_files` and included in `WorkerRequest.to_payload()`.

## Errors and compatibility

- **Backward compatibility with existing `config.yaml`**: Adding `"copilot"` to `SUPPORTED_HARNESSES`, `DEFAULT_CATALOGS`, and `CONFIG_SCHEMA` is purely additive; existing v2.9 configs for `claude`, `codex`, `antigravity`, and `opencode` continue to validate without migration.
- **Default worker timeout preserved at `900.0` seconds**: `ORCHESTRATOR_DEFAULTS["worker"]["timeout_seconds"]` is set to `900.0` to match the existing runtime default in `registry.py:250` and all worker adapters.
- **Behavior change on `timeout` retries**: Previously `WorkerScheduler._run()` retried any failure where `retry_safe=True` (including `timeout` when cancellation succeeded quiescently). Per epic `gin-workflow-dura`, retries are now restricted to `quota`, `rate_limit`, and `service` failures; `timeout` is no longer retried automatically.
- **Circuit breaker state compatibility**: Existing `.agent-workflow/runtime/circuit-breakers.json` files remain compatible; only the transition condition for `QUOTA` and `AUTH` changes to immediate `OPEN`.
- **Token budget enforcement**: All edits to `SKILL.md` and `references/*.md` must keep every stage chain in `STAGES` `<= 12,000` characters and every agent file `<= 4,000` characters.

## Testing

- **Unit tests for `copilot` harness & worker**:
  - Test `DEFAULT_CATALOGS["copilot"]`, `routes resolve`, and `CONFIG_SCHEMA` validation with `models.copilot`.
  - Test `build_copilot_invocation`, `copilot_health`, `CopilotWorkerAdapter`, `direct_worker_result` with a real Copilot JSONL fixture (`assistant.message` -> `data.content`), and `list_models("copilot")` in `tests/gin_orchestrator/`.
- **Packaging & installer tests**:
  - Update `tests/gin_orchestrator/test_harness_packaging.py` (updating `opencode_removed` and `copilot_removed` assertions) and `tests/install_smoke_test.{sh,ps1}` to verify translated `agents/*.md` across `claude-code`, `antigravity`, `codex`, `opencode`, and `copilot`.
- **Cost-control & dispatch tests**:
  - Test `ORCHESTRATOR_DEFAULTS` propagation to `ProviderRegistry` and `WorkerScheduler`.
  - Test `CircuitBreakerStore.record_failure()` opening immediately on the first `QUOTA` or `AUTH` failure when `failure_threshold=3`, while requiring 3 failures for `RATE_LIMIT` / `SERVICE` / `TIMEOUT`.
  - Update `tests/gin_orchestrator/test_worker_scheduler.py` to verify `WorkerScheduler` retries only `provider_failure:quota`, `provider_failure:rate_limit`, and `provider_failure:service` and passes `prior_changed_files` into the next attempt's `WorkerRequest` payload.
  - Test `gin-orchestrator dispatch` CLI end-to-end with direct workspace mode (both with and without `orchestrator.local.yaml`, enforcing worktree safety for `execute` and allowing `root` for `review`/`discuss`/`plan`).
- **Token budget and docs tests**:
  - Run `python3 tests/test_all.py` including `tests/workflow_core/test_token_budget.py` and CLI reference heading checks.
