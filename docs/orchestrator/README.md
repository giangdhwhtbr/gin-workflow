# gin-orchestrator

gin-workflow runs the whole lifecycle in the harness you open (the main harness) and needs nothing else. **gin-orchestrator** is the extension that adds worker harnesses: it lets Claude Code, Codex, Antigravity (`agy`), or OpenCode run implementation tracks and independent reviews next to your main harness. Install it only when you need that.

## What it adds

- Routing of roles to harnesses: a plan names a role and a model and effort from the main harness's catalog, never a harness. gin-orchestrator resolves each track to an ordered list of harnesses, each at that route mapped by rank into its own catalog ([Routing](routing.md)).
- Dispatch of workers on those harnesses, with health checks, fallback, a circuit breaker, and capacity limits.
- Provider independence for review: the reviewer runs on a different harness than the implementer.
- Provider health and model checks in `gin-workflow setup doctor --probe` and `setup models`.
- The `/gin-orchestrator:providers` skill, which configures all of it.

## Install

From a gin-workflow clone:

```bash
./install.sh --plugin gin-orchestrator
```

This installs gin-workflow too, when it is missing. On Windows use `.\install.ps1 -Plugin gin-orchestrator`. Then, in each repository, run `/gin-orchestrator:providers` once. It writes the `orchestrator:` section of `.agent-workflow/config.yaml` and `.agent-workflow/orchestrator.local.yaml`, turns on `provider_mode: multi`, and probes each harness ([Routing](routing.md#setting-it-up)). Details of the install and of the dependency on gin-workflow: the [plugin README](../../plugins/gin-orchestrator/src/README.md).

## Single and multi mode

| `provider_mode` | Behavior |
|---|---|
| `single` (default) | Every track and review runs on the main harness. gin-orchestrator is not consulted. Review independence is `session`. |
| `multi` | `gin-workflow` delegates `routes resolve`, `reviewer`, and the `setup doctor --probe` and `setup models` provider checks to gin-orchestrator. Review independence can be `provider`, which `/gin-orchestrator:providers` sets. |

In `multi` mode without gin-orchestrator, or when it fails, `gin-workflow` resolves every route to the main harness, warns, and never blocks the work ([troubleshooting](../reference/troubleshooting.md#orchestrator_missing-orchestrator_contract_mismatch-or-orchestrator_failed)). The delegation table is in the [CLI reference](../reference/cli.md#delegation-to-gin-orchestrator); the command contract is in the [orchestrator contract](../reference/orchestrator-contract.md).

## When to use workers

`execute` spawns a subagent for every track, on the main harness unless a role routes the track elsewhere. Worker harnesses suit parallel tracks, long-running or specialized work, and provider-independent review. Routes map by rank, so a track planned at the weakest of several main-harness models runs at the weakest model of its worker harness.

## Dispatch and fallback

At dispatch, `RoutedWorkerDispatcher` rechecks each candidate in order:

1. Health: the CLI starts and supports the flags the adapter needs (`claude -p`, `codex exec`, `agy --print --sandbox`, `opencode run --auto --format json`). Antigravity and OpenCode with an explicit model also need proven model selection.
2. Circuit breaker: infrastructure failures (quota, rate limit, authentication, service, timeout, crash, invalid model) count against a provider and model. At `circuit_breaker.failure_threshold` the circuit opens for `cooldown_seconds`, then allows `half_open_max_probes` trial runs. Task, test, review, and invalid-result failures do not count against the provider.
3. Capacity: at most `concurrency.<provider>` workers at once; a task waits up to `queue.max_wait_seconds`.

Fallback keeps the route's rank: every candidate runs the plan's model and effort mapped into its own catalog. Escalation (`gin-workflow routes dispatch --escalate`) moves up the catalog of the track's resolved harness. When no route is left before the queue deadline, the worker returns `worker_routes_unavailable` and the task stays open. A retry reuses the same identity, and a completed task is never dispatched again. The actual route, any fallback reason, and circuit transitions are recorded as runtime events.

For Antigravity and OpenCode, a catalog model may be `provider_default`, which is their built-in catalog: the manifest records the provider and omits a model, and the CLI uses its own default. An OpenCode catalog model is passed verbatim to `--model`, so it can be a `provider/model` or `provider/model#variant` string.

OpenCode has no sandbox. Its adapter runs `opencode run --standalone --auto --format json` in the track workspace (it has no `--cd`); `--auto` auto-approves permissions, so isolation relies on the worktree and working directory, the same trade-off as Codex's `--dangerously-bypass-approvals-and-sandbox`.

## Provider independence

With `routing.review.independence: provider` and gin-orchestrator, the reviewer's provider must differ from the implementer's. `gin-workflow reviewer` returns the ordered reviewer routes, each with an `actor_id`. When no other provider is left, the review needs a human decision, unless `allow_self_review_fallback` is set. Without gin-orchestrator independence is `session` ([Providers](../concepts/providers.md#independent-review)).

## Worker context and results

A worker receives only what its task needs: the task and its dependency state, the approved file scope, validation intent, objective, constraints, isolation policy, expected output, workflow and retry identities, provider role, and the requested `model` and `effort`, in a payload with `schema_version` `2.4`. It never receives the parent transcript, private reasoning, secrets, or the provider. The native adapter starts the CLI at the candidate's mapped model and effort; Claude gets the effort as `--effort <effort>` and Codex as `-c model_reasoning_effort=<effort>`. Missing required context fails as `context_unavailable` before dispatch.

A result reports `status`, `task_id`, `summary`, `changed_files`, `commits`, `tests`, `evidence`, `blockers`, and optional `knowledge_candidates`; a malformed or mismatched result fails as `invalid_result_contract`. Worker events run `worker.requested`, any `worker.unavailable` route decisions, `worker.assigned`, `worker.started`, `worker.context_loaded`, `worker.progress_updated`, then `worker.completed`, `worker.failed`, or `worker.cancelled`.

## Next

- [Routing and configuration](routing.md)
- [Orchestrator contract](../reference/orchestrator-contract.md)
