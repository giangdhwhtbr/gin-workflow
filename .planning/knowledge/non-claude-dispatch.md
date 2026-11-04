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

**References**
- Spec `.planning/specs/2026-11-03-non-claude-dispatch-design.md`; plan `.planning/plans/2026-11-03-non-claude-dispatch.md`
- `plugins/gin-orchestrator/src/scripts/gin_orchestrator/{cli.py,registry.py,config.py,circuit_breaker.py,worker_scheduler.py,copilot_worker.py,native_cli.py}`; `install.sh`, `install.ps1`
- Docs: `docs/orchestrator/README.md`, `docs/reference/orchestrator-contract.md`, `docs/concepts/providers.md`
- Beads: `gin-workflow-dura`, `gin-workflow-dura.1`–`.5`, `gin-workflow-btt3`, `gin-workflow-rm-cost-control`

**Scope**
Worker dispatch for any non-Claude main harness or cross-provider route, gin-orchestrator retry and circuit-breaker policy, and agent packaging in the installers.
