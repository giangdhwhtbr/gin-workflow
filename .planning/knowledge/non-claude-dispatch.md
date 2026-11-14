# Non-Claude main harness: dispatch rule, worker agents, retries

**Context**
Epic `gin-workflow-dura` (shipped 2026-11-04) made tracks, reviews, and explorations run at the catalog model and effort when Codex, Antigravity, OpenCode, or Copilot is the main harness. Claude Code dispatch was already shipped in `gin-workflow-btt3`.

**Decision/Solution**
- Hybrid rule in the stage skills: spawn a native subagent only when the route stays on the main harness and that harness can set the resolved model and effort per spawn (Claude Code `Agent(..., model=...)`; Antigravity `invoke_subagent` only for `provider_default` with no effort). Everything else goes through `gin-orchestrator dispatch`: cross-provider routes, every route when the main harness is `codex`, `opencode`, or `copilot`, and Antigravity with an explicit model or effort. Without a usable gin-orchestrator (`dispatch` missing from `CAPABILITIES`), skills fall back to the native subagent or the main session with a warning.
- `gin-orchestrator dispatch` works without `.agent-workflow/orchestrator.local.yaml` or `orchestrator.concurrency`: `_dispatch` synthesizes both (concurrency 1 per provider). `ProviderRegistry.from_effective_config` itself still requires `orchestrator.concurrency`. With `--stage execute` the workspace must be inside the worktree root; read-only stages may use the repository root.
- Agent names differ per provider (`registry.py:_resolve_worker_agent`): Claude `<plugin>:<stem>`, OpenCode `<plugin>-<stem>`, Antigravity and Copilot `<stem>`, Codex none (`codex exec` has no `--agent`).
- Source agents in `plugins/*/src/agents/*.md` keep Antigravity tool names. `install.sh`/`install.ps1` translate them: Codex drops the `tools:` line; OpenCode writes `<plugin>-<stem>.md` with `mode: subagent` and also copies them to `~/.config/opencode/agents/` (the prefix avoids clobbering user agents; `--uninstall` removes only `<plugin>-*.md`); Copilot maps tool names (`view_file`→`view`, `grep_search`→`grep`, `list_dir`→`glob`, `search_web`→`web_fetch`, `run_command`→`bash`, edits→`edit`).
- Copilot worker: GitHub tokens (`GH_TOKEN`, `GITHUB_TOKEN`, `COPILOT_GITHUB_TOKEN`, `COPILOT_HOME`, host vars) are passed only to `copilot` invocations through `NativeCliInvocation.env_extra`, excluded from `repr`. Its JSONL output nests text under `data.content`.
- Cost control: `ORCHESTRATOR_DEFAULTS` in `gin_orchestrator/config.py` is the one owner of timeout (900 s), retries (2), queue wait (600 s), and breaker threshold (3); do not add fallback literals elsewhere. `QUOTA` and `AUTH` open the circuit on the first failure. `run_with_retries` (shared by `WorkerScheduler` and `dispatch`) retries only `provider_failure:quota|rate_limit|service` and passes `prior_changed_files`; a quota retry therefore fails over to the next candidate.

**Consequences**
- Behavior change: a `timeout` is no longer retried automatically.
- New providers need an entry in `_resolve_worker_agent`, the install translators, and `ORCHESTRATOR_DEFAULTS` users rather than local defaults.
- Stage skill text for dispatch must keep each stage chain within the 12,000-character budget (`tests/workflow_core/test_token_budget.py`).
- `--stage execute` rejects a workspace outside `.planning/worktrees/` with `worker.unavailable` reason `workspace_unavailable` and the dispatch result `worker_routes_unavailable` (seen 2026-11-12 with `.claude/worktrees/<name>`): create the track worktree with `gin worktree create` first.
- Antigravity workers (`gemini-3.8-flash-*`, 2026-11-12) often commit correct work and still return `invalid_result_contract` (status or `tests` objects outside the contract); check the worktree's commits before re-dispatching, then verify diff and tests in the main session. See [ba-workspace](ba-workspace.md).
- In `gin-workflow-ws-child-setup` (2026-11-14), all three Antigravity tracks finished within the 900 s timeout, but each needed one review fix cycle for exception handling: `except Exception` in `workspace clone`, an uncaught `ConfigValidationError`, and uncaught `OSError`/`CalledProcessError` in `team hooks --all-repos`. A brief for an Antigravity worker names the exact exception classes and the report line for each failure.
- A scheduler test that cancels a real child process must give the child time to start: `test_scheduler_timeout_cancels_started_native_process` flaked when a `python3` child was cancelled at 0.2s before writing its pid; it now uses a `/bin/sh` child with `exec sleep` and a 1.0s timeout (`gin-workflow-2o6e`).
- After the attempt deadline, `_attempt_with_deadline` waits for a missing dispatch receipt for one more `worker_timeout_seconds` only (`gin_orchestrator/worker_scheduler.py:264-284`). A receipt that arrives later is never cancelled, so that worker keeps running after the attempt reports `timeout`; `retry_safe` is False, so nothing reruns it. With the 900 s default this needs a dispatch slower than 1,800 s, and `worker_dispatch.py:914` waits on `dispatch_ready` without a timeout. A test of the late-receipt path must release the receipt inside that second window (`gin-workflow-el1d`).

**References**
- Spec `.planning/specs/2026-11-03-non-claude-dispatch-design.md`; plan `.planning/plans/2026-11-03-non-claude-dispatch.md`
- `plugins/gin-orchestrator/src/scripts/gin_orchestrator/{cli.py,registry.py,config.py,circuit_breaker.py,worker_scheduler.py,copilot_worker.py,native_cli.py}`; `install.sh`, `install.ps1`
- Docs: `docs/orchestrator/README.md`, `docs/reference/orchestrator-contract.md`, `docs/concepts/providers.md`
- Beads: `gin-workflow-dura`, `gin-workflow-dura.1`–`.5`, `gin-workflow-btt3`, `gin-workflow-rm-cost-control`

**Scope**
Worker dispatch for any non-Claude main harness or cross-provider route, gin-orchestrator retry and circuit-breaker policy, and agent packaging in the installers.
