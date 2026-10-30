# Providers

The harness you open (the main harness) plans, coordinates, and does the work: Claude Code, Codex, Antigravity, or OpenCode. gin-workflow runs the whole lifecycle in it with no other tool. Running bounded work, such as an implementation track or an independent review, on a different installed harness is the job of the gin-orchestrator extension: see [Orchestrator](../orchestrator/README.md). The [routing diagram](architecture.md#provider-routing) shows the flow.

## Capabilities

Skills work through the provider-neutral capabilities below.

| Capability | Covers |
|---|---|
| Task tracking | task identity, dependencies, readiness, claims, blockers, closure: through `gin-workflow task`, which serves local Markdown files under `.planning/tasks/` or, with `providers.task_tracking: beads`, runs Beads (`bd`); never by editing `.beads/` directly |
| Workspace | isolation (worktrees) and cleanup metadata |
| Worker dispatch | other harnesses only, through gin-orchestrator: resolve role, model, and effort, dispatch, cancel, report status, collect results ([Orchestrator](../orchestrator/README.md)) |
| Review | request review, terminal review state, findings |
| Evidence | record and query evidence; decide whether acceptance evidence is complete |
| Knowledge | search and propose knowledge; workers never write permanent knowledge |
| Notifications | optional delivery only (`gin-workflow notify`, behind `notifications.telegram`) |

Selecting a provider never authorizes a lifecycle transition; gates and approvals still apply.

## Roles, models, and efforts

Every implementation or review track in a plan names:

- a provider role: a responsibility such as `backend`, `frontend`, `docs`, `review`, or `general`, configured under `routing.roles`;
- a route: a `Model:` from the main harness's model catalog, an `Effort:` from the same catalog when it lists efforts, and a `Why:` line giving the reason.

The model catalog lists, per harness, its models from weakest to strongest and its efforts from lowest to highest ([`models`](../reference/config.md#models)). The `plan` skill picks the weakest model that can do the work, a stronger model for broad context or design judgement, and a higher effort for intricate logic. An unclear requirement never raises either; the planner asks you or returns to `discuss`. You can change the route of any track before you approve the plan.

A plan never names a concrete model outside the main harness's catalog, and never a provider. Without gin-orchestrator every role resolves to the main harness (`preferred: [main_harness]`) at the track's model and effort. `gin-workflow routes resolve` writes the assignment manifest `.agent-workflow/runtime/assignments/<workflow>.yaml`, which is runtime metadata, not plan or task data. Executables for other harnesses live only in `.agent-workflow/orchestrator.local.yaml` ([Configuration](../reference/config.md#orchestratorlocalyaml)).

`gin-workflow routes resolve` resolves the whole batch of tracks at once. A model or effort outside the main harness's catalog is a diagnostic that names the track, the value, and the allowed values. So is a track that still carries a reasoning tier in place of a model. If any track cannot be resolved, it reports every diagnostic, exits 2, and writes no manifest; the track beads `orchestrate` already created stay. `main_harness` means the configured `harness`, or the session override (`gin-workflow setup harness-override --harness <name>`, or `GIN_WORKFLOW_HARNESS_OVERRIDE`).

## Independent review

Review goes through `routing.review`. In single-harness mode (`provider_mode: single`, the default) `independence` is `session`. A fresh session of the main harness reviews with a clean context and a different actor id, and the implementer's session never reviews its own work. `independence: provider`, which sends the review to a different harness than the implementer's, needs gin-orchestrator; without it review falls back to `session` with a warning. Self-review is allowed only when `allow_self_review_fallback` is set; otherwise running out of routes needs a human decision. A review stops at `max_cycles` and returns `human_decision_required`. A generic worker result is never treated as approval; only a terminal ledger approval counts. The reviewer runs at the implementer's final model and effort, including any escalation, read in the implementer's catalog. A reviewer on the implementer's provider keeps that route; any other provider gets it mapped by rank from the implementer's catalog ([rank mapping](../orchestrator/routing.md#rank-mapping)). When the implementer used the weakest model of a catalog with more than one model and the diff changes more than documentation, the review uses the next model. `gin-workflow reviewer` computes the route and the route order for the `review` skill.

A reviewer starts with a fresh, bounded context: the diff, the confirmed requirement, acceptance criteria, test evidence, and the `gin-workflow rules` output for the reviewed files. It excludes self-assessment, persuasive summaries, and unrelated history.

## Evidence and identity

Acceptance evidence is tied to an identity: workflow id, attempt id, task id, and the repository snapshots (repository id, source-scope hash, source-tree hash, checkpoint commit and ref). A worker result, test record, or review approval from another task, attempt, or tree cannot satisfy acceptance; empty hashes, missing references, and stale approvals are rejected. Review evidence must be a terminal ledger approval, not a worker's own claim.

## Privacy

Portable configuration, plans, and bundles never contain executable paths, credentials, secrets, transcripts, or private reasoning. In portable configuration and plans, model names appear only in the model catalog (`models.<harness>.models`) and in the `Model:` lines of a plan. Configuration may hold references such as `secret_ref:NAME`; each CLI's own login owns credentials, and secret values are never written to configuration, manifests, events, results, evidence, bundles, or logs.
