# Providers

The harness you open (the main harness) plans and coordinates. Bounded work, such as an implementation track or an independent review, can run on another installed CLI: Claude Code (`claude`), Codex (`codex`), or Antigravity (`agy`). Routing decides which one, without ever writing a provider or model name into the plan or Beads. The [routing diagram](architecture.md#provider-routing) shows the flow.

## Capabilities

Skills work through provider-neutral capabilities, each with health and capability metadata. A disabled capability holds the workflow at `progress` instead of being bypassed.

| Capability | Covers |
|---|---|
| Task tracking | task identity, dependencies, readiness, claims, blockers, closure: Beads through `bd` (or `br`) commands, never by editing `.beads/` directly |
| Workspace | isolation (worktrees) and cleanup metadata |
| Worker dispatch | resolve role and reasoning, recheck health, circuit and capacity, dispatch, cancel, report status, collect normalized results |
| Review | request review, terminal review state, findings |
| Evidence | record and query evidence; decide whether acceptance evidence is complete |
| Knowledge | search and propose knowledge; workers never write permanent knowledge |
| Notifications | optional delivery only (for example `telegram-notify`) |

Selecting a provider never authorizes a lifecycle transition; gates and approvals still apply.

## Roles, reasoning, and model classes

Every implementation or review track in a plan names:

- a **provider role**: a responsibility such as `backend`, `frontend`, `docs`, `review`, or `general`, configured under `routing.roles`;
- a **reasoning tier**: `low` (mechanical edits, simple docs), `medium` (normal implementation), or `high` (architecture, security, migration, concurrency).

Plans may also give model guidance as abstract classes: `high_reasoning`, `standard_impl` (the default), `cheap_simple`. Concrete models come only from `.agent-workflow/providers.local.yaml`, which maps each provider's `low`, `medium`, and `high` to a model ([Configuration](../reference/config.md#providerslocalyaml)).

## Resolution at orchestration

`orchestrate` builds an `AssignmentRequest` (task, role, reasoning, main harness, workflow id) for every track and resolves the whole batch with `resolve_all_assignments` before writing anything durable:

- the role expands to its ordered `preferred` then `fallback` providers; `main_harness` means the harness that opened the workflow, or the session override (`gin-workflow setup harness-override --harness <name>`, or `GIN_WORKFLOW_HARNESS_OVERRIDE`);
- each candidate needs an executable and a model for the requested tier in `providers.local.yaml`;
- if any track cannot be resolved, every diagnostic is reported and nothing is created.

The result is written with `write_assignment_manifest` to `.agent-workflow/runtime/assignments/<workflow>.yaml`, which is runtime metadata, not plan or Beads data.

For Antigravity only, a tier may be `provider_default`: the manifest records the provider and omits a model, and `agy` uses its own default.

## Dispatch and fallback

At dispatch, `RoutedWorkerDispatcher` rechecks each candidate in order:

1. **Health**: the CLI starts and supports the flags the adapter needs (`claude -p`, `codex exec`, `agy --print --sandbox`). Antigravity with an explicit model also needs proven model selection.
2. **Circuit breaker**: infrastructure failures (quota, rate limit, authentication, service, timeout, crash, invalid model) count against a provider and model; at `circuit_breaker.failure_threshold` the circuit opens for `cooldown_seconds`, then allows `half_open_max_probes` trial runs. Task, test, review, and invalid-result failures do not count against the provider.
3. **Capacity**: at most `concurrency.<provider>` workers at once; a task waits up to `queue.max_wait_seconds`.

Fallback keeps the requested reasoning tier; it never downgrades. When no route is left before the queue deadline, the worker returns `worker_routes_unavailable` and the bead stays open. A retry reuses the same identity, and a completed task is never dispatched again. The actual route, any fallback reason, and circuit transitions are recorded as runtime events.

Execution runs directly in the session for sequential plans and three or fewer tasks; workers are for more than three parallel tasks, long-running or specialized work, or independent review.

## Independent review

Review goes through the same routing under `routing.review`. With `independence: provider` (multi-provider mode) the reviewer's provider must differ from the implementer's; with `independence: session` (single-provider mode) a fresh session of the same provider reviews with a clean context and a different actor id. Self-review is allowed only when `allow_self_review_fallback` is set; otherwise running out of routes needs a human decision. A review stops at `max_cycles` and returns `human_decision_required`. A generic worker result is never treated as approval; only a terminal ledger approval counts.

## Worker context and results

A worker receives only what its task needs: the bead and its dependency state, the approved file scope, validation intent, objective, constraints, isolation policy, expected output, workflow and retry identities, provider role, and reasoning tier. It never receives the parent transcript, private reasoning, secrets, or the concrete provider and model (the native adapter adds those at the process boundary). Missing required context fails as `context_unavailable` before dispatch.

A result reports `status`, `task_id`, `summary`, `changed_files`, `commits`, `tests`, `evidence`, `blockers`, and optional `knowledge_candidates`; a malformed or mismatched result fails as `invalid_result_contract`. Worker events run `worker.requested`, any `worker.unavailable` route decisions, `worker.assigned`, `worker.started`, `worker.context_loaded`, `worker.progress_updated`, then `worker.completed`, `worker.failed`, or `worker.cancelled`.

A reviewer starts with a fresh, bounded context: the diff, the confirmed requirement, acceptance criteria, test evidence, and the `gin-workflow rules` output for the reviewed files. It excludes self-assessment, persuasive summaries, and unrelated history.

## Evidence and identity

Acceptance evidence is tied to an identity: workflow id, attempt id, task id, and the repository snapshots (repository id, source-scope hash, source-tree hash, checkpoint commit and ref). A worker result, test record, or review approval from another task, attempt, or tree cannot satisfy acceptance; empty hashes, missing references, and stale approvals are rejected. Review evidence must be a terminal ledger approval, not a worker's own claim.

## Privacy

Portable configuration, plans, bundles, and worker requests never contain executable paths, concrete models, credentials, secrets, transcripts, or private reasoning. Configuration may hold references such as `secret_ref:NAME`; each CLI's own login owns credentials, and secret values are never written to configuration, manifests, events, results, evidence, bundles, or logs.
