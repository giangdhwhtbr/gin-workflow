---
name: providers
description: "Configure worker harnesses for gin-workflow: which harness runs each role and tier."
---

# Providers

`/gin-orchestrator:providers` sets up which harnesses may run work besides the main harness, and which one each role and reasoning tier prefers. Configuration is written by `gin-orchestrator configure`; never edit `.agent-workflow/config.yaml` or `.agent-workflow/orchestrator.local.yaml` by hand.

Preconditions: `gin-workflow` and `gin-orchestrator` are on `PATH` and `.agent-workflow/generated/effective-config.yaml` exists. Otherwise stop and name what to install or run: `./install.sh --plugin gin-orchestrator` from a gin-workflow clone, or `/setup`.

Ask one question at a time and wait for the answer. Collect answers as `--set` keys (portable, committed) and `--local-set` keys (machine-local, untracked).

1. **Harnesses.** Which installed harnesses may run work? For each candidate `<p>` (`claude`, `codex`, `antigravity`, `opencode`), run `gin-orchestrator models --provider <p> --json` and show what it lists. For each chosen harness, record its executable as `--local-set providers.<p>.executable=<path or name>`.
2. **Models.** For each chosen harness, which model runs each tier (`low`, `medium`, `high`)? Offer only models the previous step listed. Record `--local-set providers.<p>.models.<tier>=<model>`. A harness new to `orchestrator.local.yaml` needs its executable and all three tiers in this one run.
3. **Roles.** For each role the user wants to change (list the roles in `.agent-workflow/generated/effective-config.yaml`), which harnesses are preferred and which are fallbacks? `main_harness` stands for the main harness. Record `--set 'orchestrator.roles.<role>.preferred=[...]'` and `--set 'orchestrator.roles.<role>.fallback=[...]'`; add `orchestrator.roles.<role>.by_tier.<tier>=[...]` for a tier that differs.
4. **Concurrency.** How many workers may run at once on each harness? Record `--set orchestrator.concurrency.<p>=<n>`. Every harness a role names needs an entry.
5. **Limits.** Keep the defaults unless the user wants other values for the queue wait (`orchestrator.queue.max_wait_seconds`), worker timeout and retries (`orchestrator.worker.timeout_seconds`, `orchestrator.worker.max_retries`), or the circuit breaker (`orchestrator.circuit_breaker.failure_threshold`, `cooldown_seconds`, `half_open_max_probes`).

Then:

1. Run `gin-orchestrator configure <every --set and --local-set> --dry-run --json`. Show the actions and any validation error; fix the answers and rerun until it is clean. Get explicit approval.
2. Run the same command with `--approve` instead of `--dry-run`.
3. Turn multi-harness routing on: `gin-workflow setup configure --set provider_mode=multi --set routing.review.independence=provider --approve`.
4. Run `gin-workflow setup doctor --probe --format json`, report each provider tier that is unavailable and why, and stop. Do not start a lifecycle stage.

`configure` refuses `--set` keys outside `orchestrator.` and writes nothing on a validation error.
