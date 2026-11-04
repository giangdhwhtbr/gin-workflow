# Non-Claude Main Harness Dispatches Tracks to Workers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `gin-workflow:execute` to implement one routed track at a time after `gin-workflow:orchestrate` prepares the manifest and workspace. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable all five supported harnesses (`claude`, `codex`, `antigravity`, `opencode`, `copilot`) to act as either the main harness or a dispatched worker across every lifecycle stage, with translated agent definitions, consistent retry/timeout/circuit-breaker defaults, and a single-track `gin-orchestrator dispatch` CLI entrypoint.

**Architecture:** Extend `workflow_core` and `gin_orchestrator` to register `copilot` as a first-class harness (`Catalog(("provider_default",), ())`) with `CopilotWorkerAdapter`, `copilot_health`, `list_models("copilot")`, and `--agent`/`--effort` pass-through across CLI workers; translate `agents/*.md` in `install.sh` and `install.ps1` for `codex`, `opencode`, and `copilot`; consolidate orchestrator defaults in `ORCHESTRATOR_DEFAULTS`, fail fast on quota/auth circuit-breaker errors, and wire `run_with_retries()` with `prior_changed_files`; and expose `gin-orchestrator dispatch` so non-Claude main harnesses can dispatch tracks and specialist roles (`developer`, `qa-agent`, `code-reviewer`, `agent-researcher`, `docs-writer`) without Claude's native `Agent` tool.

**Tech Stack:** Python 3.11+ (`unittest`, `dataclasses`, `subprocess`, `shutil`), Bash (`install.sh`), PowerShell (`install.ps1`), Markdown skills/docs.

**Source Spec:** `.planning/specs/2026-11-03-non-claude-dispatch-design.md`

## Execution Strategy

```yaml
mode: worker
workers:
  mode: parallel
```

- Tracks 1 and 2 have `Dependencies: none` and touch completely disjoint file scopes (`workflow_core` + `gin_orchestrator` worker adapters vs `install.sh` + `install.ps1` + packaging tests), so they can run in parallel.
- Track 3 depends on Track 1 (`copilot_worker.py` and `registry.py` worker adapter wiring) and consolidates `ORCHESTRATOR_DEFAULTS`, immediate circuit-breaker open on `QUOTA`/`AUTH`, and `run_with_retries()`.
- Track 4 depends on Track 3 (`run_with_retries()`, `ORCHESTRATOR_DEFAULTS`, and `WorkerRequest.agent`) and adds `gin-orchestrator dispatch`, updates stage skills within the 12,000-char token budget, and updates documentation.

## File Map

- Modify: `plugins/gin-workflow/src/scripts/workflow_core/catalog.py`
- Modify: `plugins/gin-workflow/src/scripts/workflow_core/provider_config.py`
- Modify: `plugins/gin-workflow/src/scripts/workflow_core/configuration.py`
- Modify: `plugins/gin-workflow/src/scripts/workflow_core/schemas.py`
- Modify: `plugins/gin-workflow/src/scripts/workflow_core/assignments.py`
- Modify: `plugins/gin-workflow/src/scripts/workflow_core/cli.py`
- Modify: `plugins/gin-workflow/src/scripts/workflow_core/project_detect.py`
- Modify: `plugins/gin-workflow/src/scripts/workflow_core/setup_service.py`
- Modify: `plugins/gin-orchestrator/src/scripts/gin_orchestrator/native_cli.py`
- Create: `plugins/gin-orchestrator/src/scripts/gin_orchestrator/copilot_worker.py`
- Modify: `plugins/gin-orchestrator/src/scripts/gin_orchestrator/antigravity_worker.py`
- Modify: `plugins/gin-orchestrator/src/scripts/gin_orchestrator/opencode_worker.py`
- Modify: `plugins/gin-orchestrator/src/scripts/gin_orchestrator/claude_worker.py`
- Modify: `plugins/gin-orchestrator/src/scripts/gin_orchestrator/routes.py`
- Modify: `plugins/gin-orchestrator/src/scripts/gin_orchestrator/registry.py`
- Modify: `plugins/gin-orchestrator/src/scripts/gin_orchestrator/cli.py`
- Modify: `plugins/gin-orchestrator/src/scripts/gin_orchestrator/doctor.py`
- Modify: `plugins/gin-orchestrator/src/scripts/gin_orchestrator/config.py`
- Modify: `plugins/gin-orchestrator/src/scripts/gin_orchestrator/circuit_breaker.py`
- Modify: `plugins/gin-orchestrator/src/scripts/gin_orchestrator/worker_dispatch.py`
- Modify: `plugins/gin-orchestrator/src/scripts/gin_orchestrator/worker_scheduler.py`
- Modify: `install.sh`
- Modify: `install.ps1`
- Modify: `plugins/gin-workflow/src/skills/execute/references/worker-lifecycle.md`
- Modify: `plugins/gin-workflow/src/skills/execute/SKILL.md`
- Modify: `plugins/gin-workflow/src/skills/review/SKILL.md`
- Modify: `plugins/gin-workflow/src/skills/discuss/SKILL.md`
- Modify: `plugins/gin-workflow/src/skills/plan/SKILL.md`
- Modify: `plugins/gin-workflow/src/skills/tech-doc/SKILL.md`
- Modify: `docs/reference/orchestrator-contract.md`
- Modify: `docs/reference/cli.md`
- Modify: `docs/orchestrator/README.md`
- Modify: `docs/concepts/providers.md`
- Modify: `tests/workflow_core/test_catalog.py`
- Modify: `tests/workflow_core/test_provider_config.py`
- Modify: `tests/workflow_core/test_project_detect.py`
- Create: `tests/gin_orchestrator/test_copilot_worker.py`
- Modify: `tests/gin_orchestrator/test_list_models.py`
- Modify: `tests/gin_orchestrator/test_harness_packaging.py`
- Modify: `tests/install_smoke_test.sh`
- Modify: `tests/install_smoke_test.ps1`
- Modify: `tests/gin_orchestrator/test_orchestrator_config.py`
- Modify: `tests/gin_orchestrator/test_circuit_breaker.py`
- Modify: `tests/gin_orchestrator/test_worker_scheduler.py`
- Modify: `tests/gin_orchestrator/test_contract_v2.py`
- Modify: `tests/gin_orchestrator/test_contract_cli.py`
- Modify: `tests/workflow_core/test_skill_routing.py`
- Modify: `tests/workflow_core/test_token_budget.py`
- Modify: `tests/workflow_core/test_docs_coverage.py`

## Tracks

### Track 1: Copilot Harness Registration and CLI Worker Adapter

- **Track ID:** `track-1`
- **Provider Role:** `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Dependencies:** `none`
- **Files:**
  - Modify: `plugins/gin-workflow/src/scripts/workflow_core/catalog.py`
  - Modify: `plugins/gin-workflow/src/scripts/workflow_core/provider_config.py`
  - Modify: `plugins/gin-workflow/src/scripts/workflow_core/configuration.py`
  - Modify: `plugins/gin-workflow/src/scripts/workflow_core/schemas.py`
  - Modify: `plugins/gin-workflow/src/scripts/workflow_core/assignments.py`
  - Modify: `plugins/gin-workflow/src/scripts/workflow_core/cli.py`
  - Modify: `plugins/gin-workflow/src/scripts/workflow_core/project_detect.py`
  - Modify: `plugins/gin-workflow/src/scripts/workflow_core/setup_service.py`
  - Modify: `plugins/gin-orchestrator/src/scripts/gin_orchestrator/native_cli.py`
  - Create: `plugins/gin-orchestrator/src/scripts/gin_orchestrator/copilot_worker.py`
  - Modify: `plugins/gin-orchestrator/src/scripts/gin_orchestrator/antigravity_worker.py`
  - Modify: `plugins/gin-orchestrator/src/scripts/gin_orchestrator/opencode_worker.py`
  - Modify: `plugins/gin-orchestrator/src/scripts/gin_orchestrator/claude_worker.py`
  - Modify: `plugins/gin-orchestrator/src/scripts/gin_orchestrator/routes.py`
  - Modify: `plugins/gin-orchestrator/src/scripts/gin_orchestrator/registry.py`
  - Modify: `plugins/gin-orchestrator/src/scripts/gin_orchestrator/cli.py`
  - Modify: `plugins/gin-orchestrator/src/scripts/gin_orchestrator/doctor.py`
  - Modify: `tests/workflow_core/test_catalog.py`
  - Modify: `tests/workflow_core/test_provider_config.py`
  - Modify: `tests/workflow_core/test_project_detect.py`
  - Create: `tests/gin_orchestrator/test_copilot_worker.py`
  - Modify: `tests/gin_orchestrator/test_list_models.py`
- **Verify:** `python3 -m unittest tests/workflow_core/test_catalog.py tests/workflow_core/test_provider_config.py tests/workflow_core/test_project_detect.py tests/gin_orchestrator/test_copilot_worker.py tests/gin_orchestrator/test_list_models.py -v`

- [ ] **Step 1: Write failing unit tests for Copilot catalog, provider config, project detect, `copilot_worker.py`, and `list_models("copilot")`**
  - In `tests/workflow_core/test_catalog.py`, add test assertions that `"copilot"` is in `SUPPORTED_HARNESSES` and `DEFAULT_CATALOGS["copilot"]` equals `Catalog(("provider_default",), ())` (`supports_effort("copilot")` is `False`).
  - In `tests/workflow_core/test_provider_config.py`, add test assertions that `DEFAULT_EXECUTABLES["copilot"] == "copilot"`, `"copilot"` is in `PROVIDER_DEFAULT_PROVIDERS`, and `copilot` role entries with `model: "provider_default"` or explicit model names pass `validate_provider_local`.
  - In `tests/workflow_core/test_project_detect.py:82`, update the expected `result["providers"]` dictionary to include `"copilot": False` (and test `"copilot": True` when `which_map` has `"copilot"`).
  - Create `tests/gin_orchestrator/test_copilot_worker.py` covering:
    - `build_copilot_invocation(prompt="do work", workspace=Path("/tmp/ws"), model="claude-sonnet-4.5", effort="high", agent="developer")` produces `["copilot", "-p", "do work", "--allow-all-tools", "--no-ask-user", "--output-format", "json", "--add-dir", "/tmp/ws", "--model", "claude-sonnet-4.5", "--reasoning-effort", "high", "--agent", "developer"]`.
    - `build_copilot_invocation(prompt="do work", workspace=Path("/tmp/ws"), model="provider_default", effort=None, agent=None)` omits `--model`, `--reasoning-effort`, and `--agent`.
    - `build_copilot_invocation` maps `effort="max"` to `--reasoning-effort xhigh` and rejects unsupported efforts.
    - `copilot_health()` checks `--version` and reports `auth_ok=True` when `COPILOT_GITHUB_TOKEN`, `GH_TOKEN`, or `GITHUB_TOKEN` is set in env or `~/.copilot/config.json` exists, and `auth_ok=False` otherwise.
    - `CopilotWorkerAdapter` forwards `COPILOT_GITHUB_TOKEN`, `GH_TOKEN`, and `GITHUB_TOKEN` via `env_extra` and parses Copilot JSONL events (`{"type": "assistant.message", "data": {"content": "hello"}}`).
  - In `tests/gin_orchestrator/test_list_models.py`, add tests for `list_models("copilot")` parsing the `--model <model>` choices block from `copilot --help` output and returning `provider="copilot"`.

- [ ] **Step 2: Run the Track 1 test suite to verify the new tests fail**
  - Run: `python3 -m unittest tests/workflow_core/test_catalog.py tests/workflow_core/test_provider_config.py tests/workflow_core/test_project_detect.py tests/gin_orchestrator/test_copilot_worker.py tests/gin_orchestrator/test_list_models.py -v`
  - Expected: Failures due to missing `"copilot"` in `DEFAULT_CATALOGS`/`DEFAULT_EXECUTABLES` and missing `gin_orchestrator.copilot_worker`.

- [ ] **Step 3: Register `"copilot"` across `workflow_core`**
  - `plugins/gin-workflow/src/scripts/workflow_core/catalog.py`: add `"copilot": Catalog(("provider_default",), ())` to `DEFAULT_CATALOGS`.
  - `plugins/gin-workflow/src/scripts/workflow_core/provider_config.py`: add `"copilot": "copilot"` to `DEFAULT_EXECUTABLES` and add `"copilot"` to `PROVIDER_DEFAULT_PROVIDERS = frozenset({"antigravity", "opencode", "copilot"})`.
  - `plugins/gin-workflow/src/scripts/workflow_core/configuration.py:247` and `schemas.py:96`: add `"copilot"` to the `main.harness` allowed values tuples (`("claude", "codex", "antigravity", "opencode", "copilot")`).
  - `plugins/gin-workflow/src/scripts/workflow_core/assignments.py:48`: update `validate_plan_assignments` error hint to list `claude, codex, antigravity, opencode, copilot`.
  - `plugins/gin-workflow/src/scripts/workflow_core/cli.py:30,47`: add `"copilot"` to `_HARNESS_ENV_PATTERNS` (`("COPILOT_CLI", "GITHUB_COPILOT")`) and `--harness` choices in `catalog`.
  - `plugins/gin-workflow/src/scripts/workflow_core/project_detect.py:202`: add `"copilot"` to the provider detection loop `for name in ("claude", "codex", "antigravity", "opencode", "copilot"):`.
  - `plugins/gin-workflow/src/scripts/workflow_core/setup_service.py:152`: add `"copilot"` to the `for name in ("claude", "codex", "antigravity", "opencode", "copilot"):` setup detection loop.

- [ ] **Step 4: Implement `copilot_worker.py`, `native_cli.py` extensions, and worker `effort`/`agent` pass-through in `gin_orchestrator`**
  - In `plugins/gin-orchestrator/src/scripts/gin_orchestrator/native_cli.py`:
    - Add `env_extra: Mapping[str, str] | None = None` parameter to `build_worker_env(workspace, extra=None)` and `execute_native_cli_worker(..., env_extra=None)` so `CopilotWorkerAdapter` can forward `COPILOT_GITHUB_TOKEN`, `GH_TOKEN`, and `GITHUB_TOKEN` from `os.environ` without exposing them in `SAFE_ENV_KEYS` for all harnesses.
    - In `_extract_Message_text(record)` (around line 246), also inspect `record.get("data")` when `isinstance(record.get("data"), Mapping)` (for Copilot JSONL events like `{"type": "assistant.message", "data": {"content": "..."}}`).
    - In `list_models(provider)` (around line 558), add `"copilot"` support: run `[exe, "--help"]` via `_run_probe(cmd, timeout=probe_timeout)` and parse single-quoted model identifiers from the `--model <model>` option description (`re.findall(r"'([a-z0-9][a-z0-9._-]+)'", match.group(1))`).
  - Create `plugins/gin-orchestrator/src/scripts/gin_orchestrator/copilot_worker.py` with:
    - `COPILOT_EFFORT_VALUES = ("low", "medium", "high", "xhigh")` and `_EFFORT_FALLBACK = {"max": "xhigh"}`.
    - `build_copilot_invocation(*, prompt: str, workspace: Path, executable: str = "copilot", model: str | None = None, effort: str | None = None, agent: str | None = None) -> list[str]` constructing `[executable, "-p", prompt, "--allow-all-tools", "--no-ask-user", "--output-format", "json", "--add-dir", str(workspace)]`, appending `["--model", model]` when `model and model != "provider_default"`, `["--reasoning-effort", mapped_effort]` when `effort` is provided, and `["--agent", agent]` when `agent` is provided.
    - `copilot_health(executable: str = "copilot", *, runner: ProbeRunner | None = None, env: Mapping[str, str] | None = None, home: Path | None = None) -> ProviderHealth` checking `[executable, "--version"]` and verifying auth via `COPILOT_GITHUB_TOKEN`/`GH_TOKEN`/`GITHUB_TOKEN` in `env` (defaulting to `os.environ`) or `(home or Path.home()) / ".copilot" / "config.json"` existence (or running `copilot auth status`).
    - `CopilotWorkerAdapter` matching the `OpenCodeWorkerAdapter`/`AntigravityWorkerAdapter` interface (`executable`, `model`, `effort`, `agent`, `runner`, `timeout_seconds`, `stream_log_path`) and passing `env_extra={k: os.environ[k] for k in ("COPILOT_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN") if k in os.environ}` to `execute_native_cli_worker`.
  - Update `antigravity_worker.py`, `opencode_worker.py`, and `claude_worker.py`:
    - Add optional `effort: str | None = None` and `agent: str | None = None` to `AntigravityWorkerAdapter.__init__` and `OpenCodeWorkerAdapter.__init__`; in `build_opencode_invocation`, append `["--variant", effort]` when `effort` is set and `["--agent", agent]` when `agent` is set.
    - Add optional `agent: str | None = None` to `ClaudeWorkerAdapter.__init__` and `build_claude_invocation` (appending `["--agent", agent]` when `agent` is set).
  - Update `routes.py:31` (`PROVIDER_DEFAULT_PROVIDERS = frozenset({"antigravity", "opencode", "copilot"})`), `registry.py` (register `"copilot"` in `DEFAULT_ADAPTER_FACTORIES`, `HEALTH_CHECKERS`, `probe_all_providers`, and pass `effort` and translated `agent` name in `ProviderRegistry.factory` where `opencode` prefixes bare agent stems with `gin-workflow-`, `claude`/`copilot` pass the bare stem, and `codex`/`antigravity` pass `None`), `cli.py:36,204` (`_ALL_PROVIDERS` and `models --provider` choices), and `doctor.py:21` (`_CAPABILITY_PROBES["copilot"] = ("--allow-all-tools", "--output-format", "--reasoning-effort", "--agent")`).

- [ ] **Step 5: Re-run the Track 1 test suite and verify all tests pass**
  - Run: `python3 -m unittest tests/workflow_core/test_catalog.py tests/workflow_core/test_provider_config.py tests/workflow_core/test_project_detect.py tests/gin_orchestrator/test_copilot_worker.py tests/gin_orchestrator/test_list_models.py -v`
  - Expected: `OK` with zero failures.

---

### Track 2: Agent Translation Across All Five Harnesses in Installers

- **Track ID:** `track-2`
- **Provider Role:** `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Dependencies:** `none`
- **Files:**
  - Modify: `install.sh`
  - Modify: `install.ps1`
  - Modify: `tests/gin_orchestrator/test_harness_packaging.py`
  - Modify: `tests/install_smoke_test.sh`
  - Modify: `tests/install_smoke_test.ps1`
- **Verify:** `python3 -m unittest tests/gin_orchestrator/test_harness_packaging.py -v && bash tests/install_smoke_test.sh`

- [ ] **Step 1: Update packaging tests in `test_harness_packaging.py` and `install_smoke_test.{sh,ps1}` to assert translated agent files**
  - In `tests/gin_orchestrator/test_harness_packaging.py`:
    - Update `test_build_dist_ matches_source_for_every_plugin_and_target` (around lines 118-170):
      - For `copilot`: `copilot_removed = set()` (since `agents/*.md` are now kept and translated in `dist/copilot/<plugin>/agents/*.md`); assert `(root / "agents/developer.md").is_file()` and verify its `tools:` frontmatter line uses Copilot tool names (`view, grep, glob, web_fetch` or `view, grep, glob, web_fetch, bash, edit`) and contains no `Read`, `Grep`, `Glob`, `WebFetch`, `Bash`, `Edit`, `Write`.
      - For `codex`: assert `(root / "agents/developer.md").is_file()` and verify its YAML frontmatter does not contain a `tools:` line.
      - For `opencode`: `agents/<stem>.md` is replaced by `agents/<plugin>-<stem>.md` (`opencode_added` includes `agents/<plugin>-<stem>.md` for every source agent file); assert `(root / "agents/gin-workflow-developer.md").is_file()`, verify its frontmatter has `description:` and `mode: subagent` and no `name:` or `tools:` keys, and verify body references to ` gin-workflow:` or `/gin-workflow:` are rewritten to ` gin-workflow-` / `/gin-workflow-`.
    - In `test_project_scope_install_for_opencode_and_antigravity` (around line 206): assert `(project_dir / ".opencode/agents/gin-workflow-developer.md").is_file()`.
  - In `tests/install_smoke_test.sh` (lines 268, 287, 358) and `tests/install_smoke_test.ps1` (lines 100, 299, 323):
    - Replace `assert_not_exists "$REPO_ROOT/dist/opencode/agents"` with `assert_exists "$REPO_ROOT/dist/opencode/agents/gin-workflow-developer.md"`.
    - Keep `assert_not_exists "$FAKE_HOME/.config/opencode/skills/gin-workflow/agents"` and add `assert_exists "$FAKE_HOME/.config/opencode/agents/gin-workflow-developer.md"`.
    - Replace `assert_not_exists "$REPO_ROOT/dist/copilot/gin-workflow/agents"` with `assert_exists "$REPO_ROOT/dist/copilot/gin-workflow/agents/developer.md"`.

- [ ] **Step 2: Run `test_harness_packaging.py` to confirm it fails before installer changes**
  - Run: `python3 -m unittest tests/gin_orchestrator/test_harness_packaging.py -v`
  - Expected: Fails because `install.sh` currently deletes `agents/` for `opencode` and `copilot` and leaves `tools:` in `codex`.

- [ ] **Step 3: Implement agent translation in `install.sh` and `install.ps1`**
  - In `install.sh`:
    - Add helper functions:
      - `translate_codex_agents "$plugin_dist"`: strip `^tools:.*$` inside YAML frontmatter of `$plugin_dist/agents/*.md`.
      - `translate_copilot_agents "$plugin_dist"`: rewrite `^tools:.*$` inside YAML frontmatter of `$plugin_dist/agents/*.md` — if the source `tools:` line contains `Edit`, `Write`, or `Bash`, replace with `tools: view, grep, glob, web_fetch, bash, edit`; otherwise replace with `tools: view, grep, glob, web_fetch`.
      - `translate_opencode_agents "$src_dir" "$dest_agents_dir" "$plugin"`: for each `$src_dir/agents/*.md`, extract `description:` from frontmatter, extract the markdown body after the closing `---` and apply the same `sed` body rewrites as `flatten_opencode_Commands` (`s|/${plugin}:|/${plugin}-|g` and `s| ${plugin}:| ${plugin}-|g`), and write `$dest_agents_dir/${plugin}-${stem}.md` with frontmatter `description: <desc>` and `mode: subagent`.
    - Update `build_plugin_target`:
      - For `codex`: call `translate_codex_agents "$plugin_dist"`.
      - For `opencode`: instead of `rm -rf "$plugin_dist/agents"`, remove the raw `$plugin_dist/agents` and call `translate_opencode_agents "$src" "$plugin_dist/agents" "$plugin"`.
      - For `copilot`: instead of `rm -rf "$plugin_dist/agents"`, call `translate_copilot_agents "$plugin_dist"`.
    - Update `install_opencode` (around line 662) and `install_project_opencode` (around line 714) to also install `dist/opencode/agents/${plugin}-*.md` into `$OPENCODE_CONFIG_DIR/agents/` (global) and `$target_dir/agents/` (project), and remove `${plugin}-*.md` from those `agents/` directories on `--uninstall` (`uninstall_all` and `uninstall_project`).
  - Mirror the exact same translation and install/uninstall logic in `install.ps1` (`Build-PluginTarget`, `Install-OpenCode`, `Install-ProjectOpenCode`, `Uninstall-All`, `Uninstall-Project`).

- [ ] **Step 4: Run `test_harness_packaging.py` and `install_smoke_test.sh` to verify**
  - Run: `python3 -m unittest tests/gin_orchestrator/test_harness_packaging.py -v && bash tests/install_smoke_test.sh`
  - Expected: All tests in `test_harness_packaging.py` and `install_smoke_test.sh` pass.

---

### Track 3: Resilience Defaults, Immediate Circuit Breaker on Quota/Auth, and Retry Wiring

- **Track ID:** `track-3`
- **Provider Role:** `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Dependencies:** `track-1`
- **Files:**
  - Modify: `plugins/gin-orchestrator/src/scripts/gin_orchestrator/config.py`
  - Modify: `plugins/gin-orchestrator/src/scripts/gin_orchestrator/circuit_breaker.py`
  - Modify: `plugins/gin-orchestrator/src/scripts/gin_orchestrator/worker_dispatch.py`
  - Modify: `plugins/gin-orchestrator/src/scripts/gin_orchestrator/worker_scheduler.py`
  - Modify: `plugins/gin-orchestrator/src/scripts/gin_orchestrator/registry.py`
  - Modify: `plugins/gin-orchestrator/src/scripts/gin_orchestrator/claude_worker.py`
  - Modify: `plugins/gin-orchestrator/src/scripts/gin_orchestrator/codex_worker.py`
  - Modify: `plugins/gin-orchestrator/src/scripts/gin_orchestrator/antigravity_worker.py`
  - Modify: `plugins/gin-orchestrator/src/scripts/gin_orchestrator/opencode_worker.py`
  - Modify: `plugins/gin-orchestrator/src/scripts/gin_orchestrator/copilot_worker.py`
  - Modify: `tests/gin_orchestrator/test_orchestrator_config.py`
  - Modify: `tests/gin_orchestrator/test_circuit_breaker.py`
  - Modify: `tests/gin_orchestrator/test_worker_scheduler.py`
- **Verify:** `python3 -m unittest tests/gin_orchestrator/test_orchestrator_config.py tests/gin_orchestrator/test_circuit_breaker.py tests/gin_orchestrator/test_worker_scheduler.py -v`

- [ ] **Step 1: Write failing tests for `ORCHESTRATOR_DEFAULTS`, immediate circuit-breaker open on `QUOTA`/`AUTH`, and `run_with_retries()`**
  - In `tests/gin_orchestrator/test_orchestrator_config.py`:
    - Update `test_returns_defaults_when_orchestrator_section_absent` (`section["worker"]` equals `{"max_retries": 2, "timeout_seconds": 900.0}`).
    - Add a test verifying `ORCHESTRATOR_DEFAULTS` contains `worker.timeout_seconds == 900.0`, `worker.max_retries == 2`, `queue.max_wait_seconds == 600`, and `circuit_breaker.failure_threshold == 3`, and validating custom overrides for `worker.timeout_seconds`.
  - In `tests/gin_orchestrator/test_circuit_breaker.py`:
    - Add tests verifying that a single `FailureKind.QUOTA` or `FailureKind.AUTH` transitions the circuit breaker from `CLOSED` directly to `OPEN` on the first failure (`failure_count == 1`), whereas `FailureKind.RATE_LIMIT`, `FailureKind.SERVICE`, and `FailureKind.TRANSIENT` still require `failure_threshold` (default 3) consecutive failures before opening.
  - In `tests/gin_orchestrator/test_worker_scheduler.py`:
    - Update existing retry tests at lines 216, 255, and 352 to use `blockers=["provider_failure:rate_limit"]` or `blockers=["provider_failure:service"]` when testing retry behavior.
    - Add tests verifying:
      - `blockers=["timeout"]` or `blockers=["provider_failure:auth"]` is NOT retried (`attempts == 1`).
      - `blockers=["provider_failure:quota"]`, `blockers=["provider_failure:rate_limit"]`, or `blockers=["provider_failure:service"]` triggers retry up to `max_retries`.
      - When attempt 1 fails with `changed_files=("src/foo.py",)` and a transient blocker, attempt 2 receives `request.prior_changed_files == ("src/foo.py",)`.
      - `run_with_retries(track, manifest_path=..., repo_root=...)` executes the full retry loop using `ORCHESTRATOR_DEFAULTS` when config overrides are absent.

- [ ] **Step 2: Run the Track 3 test suite to confirm the new tests fail**
  - Run: `python3 -m unittest tests/gin_orchestrator/test_orchestrator_config.py tests/gin_orchestrator/test_circuit_breaker.py tests/gin_orchestrator/test_worker_scheduler.py -v`
  - Expected: Failures on missing `timeout_seconds`, `IMMEDIATE_OPEN_FAILURE_KINDS`, `prior_changed_files`, and `run_with_retries`.

- [ ] **Step 3: Implement `ORCHESTRATOR_DEFAULTS`, circuit-breaker fast-open, and `run_with_retries()`**
  - In `plugins/gin-orchestrator/src/scripts/gin_orchestrator/config.py`:
    - Add `"timeout_seconds": 900.0` to `ORCHESTRATOR_DEFAULTS["worker"]` and validate `worker.timeout_seconds` as a positive number (`int | float`, `> 0`) in `validate_orchestrator_config`.
  - In `plugins/gin-orchestrator/src/scripts/gin_orchestrator/circuit_breaker.py`:
    - Define `IMMEDIATE_OPEN_FAILURE_KINDS = frozenset({FailureKind.QUOTA, FailureKind.AUTH})`.
    - In `CircuitBreakerRegistry.record_failure` (around line 246), open the circuit immediately when `kind in IMMEDIATE_OPEN_FAILURE_KINDS` (`should_open = current.state == CircuitState.HALF_OPEN or kind in IMMEDIATE_OPEN_FAILURE_KINDS or failure_count >= self._failure_threshold`).
  - In `plugins/gin-orchestrator/src/scripts/gin_orchestrator/worker_dispatch.py`:
    - Add `prior_changed_files: tuple[str, ...] = ()` and `agent: str | None = None` to `WorkerRequest`.
    - In `build_worker_prompt(request)`, when `request.prior_changed_files` is non-empty, append a section listing those files and instructing the worker to inspect `git status` / `git diff` and continue from existing changes rather than redoing completed edits.
  - In `plugins/gin-orchestrator/src/scripts/gin_orchestrator/worker_scheduler.py`:
    - Define `TRANSIENT_FAILURE_BLOCKERS = frozenset({"provider_failure:quota", "provider_failure:rate_limit", "provider_failure:service"})`.
    - Change default parameters on `ParallelTrackScheduler.__init__`, `execute_track_with_retry`, and `execute_tracks` to pull from `ORCHESTRATOR_DEFAULTS` (`max_wait_seconds = int(ORCHESTRATOR_DEFAULTS["queue"]["max_wait_seconds"])`, `max_retries = int(ORCHESTRATOR_DEFAULTS["worker"]["max_retries"])`, `attempt_timeout_seconds = float(ORCHESTRATOR_DEFAULTS["worker"]["timeout_seconds"])`).
    - In `execute_track_with_retry`, only retry when `attempt <= max_retries` and `bool(set(outcome.result.blockers) & TRANSIENT_FAILURE_BLOCKERS)`. Track accumulated `changed_files` across failed attempts and pass `prior_changed_files=tuple(prior_changed_files)` on subsequent `WorkerRequest` instances (via ` dataclasses.replace(request, prior_changed_files=...)`).
    - Add `run_with_retries(track_or_request, *, registry: ProviderRegistry, breakers: CircuitBreakerRegistry | None = None, max_retries: int | None = None, attempt_timeout_seconds: float | None = None, max_wait_seconds: float | None = None) -> ScheduledAttemptOutcome` as the top-level helper that wires `ParallelTrackScheduler` + `execute_track_with_retry`.
  - In `registry.py` and the 5 worker adapters (`claude_worker.py`, `codex_worker.py`, `antigravity_worker.py`, `opencode_worker.py`, `copilot_worker.py`), set the default `timeout_seconds` to `float(ORCHESTRATOR_DEFAULTS["worker"]["timeout_seconds"])` (`900.0`).

- [ ] **Step 4: Re-run the Track 3 test suite and verify all tests pass**
  - Run: `python3 -m unittest tests/gin_orchestrator/test_orchestrator_config.py tests/gin_orchestrator/test_circuit_breaker.py tests/gin_orchestrator/test_worker_scheduler.py -v`
  - Expected: `OK` with zero failures.

---

### Track 4: `gin-orchestrator dispatch` CLI, Stage Skill Updates, and Documentation

- **Track ID:** `track-4`
- **Provider Role:** `backend`
- **Model:** `opus`
- **Effort:** `high`
- **Dependencies:** `track-3`
- **Files:**
  - Modify: `plugins/gin-orchestrator/src/scripts/gin_orchestrator/cli.py`
  - Modify: `plugins/gin-orchestrator/src/scripts/gin_orchestrator/registry.py`
  - Modify: `plugins/gin-workflow/src/skills/execute/references/worker-lifecycle.md`
  - Modify: `plugins/gin-workflow/src/skills/execute/SKILL.md`
  - Modify: `plugins/gin-workflow/src/skills/review/SKILL.md`
  - Modify: `plugins/gin-workflow/src/skills/discuss/SKILL.md`
  - Modify: `plugins/gin-workflow/src/skills/plan/SKILL.md`
  - Modify: `plugins/gin-workflow/src/skills/tech-doc/SKILL.md`
  - Modify: `docs/reference/orchestrator-contract.md`
  - Modify: `docs/reference/cli.md`
  - Modify: `docs/orchestrator/README.md`
  - Modify: `docs/concepts/providers.md`
  - Modify: `tests/gin_orchestrator/test_contract_v2.py`
  - Modify: `tests/gin_orchestrator/test_contract_cli.py`
  - Modify: `tests/workflow_core/test_skill_routing.py`
  - Modify: `tests/workflow_core/test_token_budget.py`
  - Modify: `tests/workflow_core/test_docs_coverage.py`
- **Verify:** `python3 -m unittest tests/gin_orchestrator/test_contract_v2.py tests/gin_orchestrator/test_contract_cli.py tests/workflow_core/test_skill_routing.py tests/workflow_core/test_token_budget.py tests/workflow_core/test_docs_coverage.py -v`

- [ ] **Step 1: Write failing tests for `gin-orchestrator dispatch`, skill routing, token budget, and docs coverage**
  - In `tests/gin_orchestrator/test_contract_v2.py` and `tests/gin_orchestrator/test_contract_cli.py`:
    - Update `CAPABILITIES` assertions to `["health", "models", "routes", "reviewer", "doctor", "dispatch"]`.
    - Add CLI tests for `gin-orchestrator dispatch`:
      - Mode 1 (`--manifest` + `--track-id`): loads track from manifest, runs through `ProviderRegistry` and `run_with_retries`, and prints JSON with `status`, `summary`, `changed_files`, `verification_run`, `blockers`, `provider_used`, `model_used`, `attempts`, `fallback_chain`, and `evidence_path`.
      - Mode 2 (`--role` + `--prompt` + `--workspace`): constructs a direct `WorkerRequest`, runs without requiring an isolated git worktree when `manifest_path is None`, and returns exit code `0` on `completed` or `1` on `blocked`/`failed`.
      - Single-harness fallback: when `.agent-workflow/orchestrator.local.yaml` or `orchestrator.concurrency` is absent, synthesizes in-memory concurrency `{p: 1 for p in SUPPORTED_HARNESSES}` and `worker.max_retries = 2` so `dispatch` succeeds without setup edits.
      - Direct-mode `--provider <p> --model <m> --effort <e>`: `ProviderRegistry.resolver(request)` resolves `route_affinity` using `source_harness = request.route_affinity[0]` so model/effort already in `<p>`'s catalog are not rejected by `main.harness` catalog validation.
  - In `tests/workflow_core/test_skill_routing.py`, add assertions that `execute/references/worker-lifecycle.md`, `review/SKILL.md`, `discuss/SKILL.md`, `plan/SKILL.md`, and `tech-doc/SKILL.md` document the `gin-orchestrator dispatch` fallback for non-Claude main harnesses.

- [ ] **Step 2: Run the Track 4 test suite to confirm the new tests fail**
  - Run: `python3 -m unittest tests/gin_orchestrator/test_contract_v2.py tests/gin_orchestrator/test_contract_cli.py tests/workflow_core/test_skill_routing.py -v`
  - Expected: Fails because `"dispatch"` is not in `CAPABILITIES` and `gin-orchestrator dispatch` is not yet implemented.

- [ ] **Step 3: Implement `gin-orchestrator dispatch` in `cli.py` and direct-mode workspace/route resolution in `registry.py`**
  - In `plugins/gin-orchestrator/src/scripts/gin_orchestrator/registry.py`:
    - Update `ProviderRegistry.workspace_for(request)` (around line 213) so that when `request.manifest_path is None`, it resolves `Path(request.workspace).resolve()` and verifies the directory exists without requiring a distinct git worktree (`_assert_isolated_worktree` continues to run when `request.manifest_path is not None`).
    - Update `ProviderRegistry.resolver(request)` (around line 255) so that when `request.route_affinity is not None`, `source_harness = request.route_affinity[0]` is passed to `resolve_assignment(...)`, and if `request.route_affinity[0]` is not already in `candidates` (e.g., when `.agent-workflow/providers.local.yaml` is absent or only configured for another role), `RouteCandidate(request.route_affinity[0], request.model, False, effort=request.effort)` is prepended.
    - When `orchestrator` config or `orchestrator.concurrency` is absent in `ProviderRegistry.from_repo`, fall back to `{p: 1 for p in SUPPORTED_HARNESSES}` instead of failing.
  - In `plugins/gin-orchestrator/src/scripts/gin_orchestrator/cli.py`:
    - Add `"dispatch"` to `CAPABILITIES`.
    - Register the `dispatch` subparser supporting Mode 1 (`--manifest <path> --track-id <id>`) and Mode 2 (`--role <role> --prompt <text> | --prompt-file <path> --workspace <dir>`) plus optional `--workflow-id <id>`, `--agent <name>`, `--provider <harness>`, `--model <model>`, `--effort <effort>`, `--write-scope <glob>...`, `--verification <cmd>...`, `--timeout <seconds>`, and `--max-retries <n>`.
    - Implement `_cmd_dispatch(args, root)` wiring `ProviderRegistry.from_repo(root)` and `run_with_retries(...)`, printing the JSON result object to stdout, and returning `0` if `status == "completed"` else `1`.

- [ ] **Step 4: Update stage skills and documentation within token budget and doc style rules**
  - Update `plugins/gin-workflow/src/skills/execute/references/worker-lifecycle.md`, `execute/SKILL.md`, `review/SKILL.md`, `discuss/SKILL.md`, `plan/SKILL.md`, and `tech-doc/SKILL.md` so each skill branches cleanly between `main.harness == "claude"` (with `provider == "claude"`) using Claude's `Agent` tool vs any non-Claude main harness (or non-Claude target provider) invoking `gin-orchestrator dispatch`. Keep every stage's combined skill + reference character count under `STAGE_CHAR_BUDGET = 12_000`.
  - Update `docs/reference/orchestrator-contract.md`, `docs/reference/cli.md`, `docs/orchestrator/README.md`, and `docs/concepts/providers.md` to document `copilot` harness support and `gin-orchestrator dispatch`. Follow `workflow_core.docs_check` style rules strictly (no numbered headings, no bold-label list items `- **Label:**`, no en/em dashes `–`/`—`, no emoji).

- [ ] **Step 5: Run the Track 4 and full repository test suites**
  - Run: `python3 -m unittest tests/gin_orchestrator/test_contract_v2.py tests/gin_orchestrator/test_contract_cli.py tests/workflow_core/test_skill_routing.py tests/workflow_core/test_token_budget.py tests/workflow_core/test_docs_coverage.py -v`
  - Run: `python3 -m unittest discover -s tests -v`
  - Expected: All unit, token budget, and documentation coverage tests pass (`OK`).
