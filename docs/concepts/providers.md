# Providers

The harness you open (the main harness) plans, coordinates, and does the work: Claude Code, Codex, Antigravity, or OpenCode. gin-workflow runs the whole lifecycle in it with no other tool. Running bounded work, such as an implementation track or an independent review, on a different installed harness is the job of the gin-orchestrator extension: see [Orchestrator](../orchestrator/README.md). The [routing diagram](architecture.md#provider-routing) shows the flow.

## Capabilities

Skills work through provider-neutral capabilities, each with health and capability metadata. A disabled capability holds the workflow at `progress` instead of being bypassed.

| Capability | Covers |
|---|---|
| Task tracking | task identity, dependencies, readiness, claims, blockers, closure: through `gin-workflow task`, which runs Beads (`bd`) or, with `providers.task_tracking: markdown`, local Markdown files under `.planning/tasks/`; never by editing `.beads/` directly |
| Workspace | isolation (worktrees) and cleanup metadata |
| Worker dispatch | other harnesses only, through gin-orchestrator: resolve role and reasoning, dispatch, cancel, report status, collect results ([Orchestrator](../orchestrator/README.md)) |
| Review | request review, terminal review state, findings |
| Evidence | record and query evidence; decide whether acceptance evidence is complete |
| Knowledge | search and propose knowledge; workers never write permanent knowledge |
| Notifications | optional delivery only (for example `telegram-notify`) |

Selecting a provider never authorizes a lifecycle transition; gates and approvals still apply.

## Roles, reasoning, and model classes

Every implementation or review track in a plan names:

- a **provider role**: a responsibility such as `backend`, `frontend`, `docs`, `review`, or `general`, configured under `routing.roles`;
- a **reasoning tier**: `low` (mechanical edits, simple docs), `medium` (normal implementation), or `high` (architecture, security, migration, concurrency).

Plans may also give model guidance as abstract classes: `high_reasoning`, `standard_impl` (the default), `cheap_simple`. A plan never names a concrete model. Without gin-orchestrator every role resolves to the main harness (`preferred: [main_harness]`), which uses its own models, and `gin-workflow routes resolve` writes the assignment manifest `.agent-workflow/runtime/assignments/<workflow>.yaml`, which is runtime metadata, not plan or task data. Concrete executables and a model per tier for other harnesses live only in `.agent-workflow/orchestrator.local.yaml` ([Configuration](../reference/config.md#orchestratorlocalyaml)).

`orchestrate` resolves the whole batch of tracks before it writes anything durable; if any track cannot be resolved, every diagnostic is reported and nothing is created. `main_harness` means the harness that opened the workflow, or the session override (`gin-workflow setup harness-override --harness <name>`, or `GIN_WORKFLOW_HARNESS_OVERRIDE`).

## Independent review

Review goes through `routing.review`. In single-harness mode (`provider_mode: single`, the default) `independence` is `session`: a fresh session of the main harness reviews with a clean context and a different actor id, and the implementer's session never reviews its own work. `independence: provider`, which sends the review to a different harness than the implementer's, needs gin-orchestrator; without it review falls back to `session` with a warning. Self-review is allowed only when `allow_self_review_fallback` is set; otherwise running out of routes needs a human decision. A review stops at `max_cycles` and returns `human_decision_required`. A generic worker result is never treated as approval; only a terminal ledger approval counts. The reviewer's tier follows the track's reasoning; a `low` track whose diff changes more than documentation is reviewed at `medium`. `gin-workflow reviewer` computes the tier and the route order for the `review` skill.

A reviewer starts with a fresh, bounded context: the diff, the confirmed requirement, acceptance criteria, test evidence, and the `gin-workflow rules` output for the reviewed files. It excludes self-assessment, persuasive summaries, and unrelated history.

## Evidence and identity

Acceptance evidence is tied to an identity: workflow id, attempt id, task id, and the repository snapshots (repository id, source-scope hash, source-tree hash, checkpoint commit and ref). A worker result, test record, or review approval from another task, attempt, or tree cannot satisfy acceptance; empty hashes, missing references, and stale approvals are rejected. Review evidence must be a terminal ledger approval, not a worker's own claim.

## Privacy

Portable configuration, plans, and bundles never contain executable paths, concrete models, credentials, secrets, transcripts, or private reasoning. Configuration may hold references such as `secret_ref:NAME`; each CLI's own login owns credentials, and secret values are never written to configuration, manifests, events, results, evidence, bundles, or logs.
