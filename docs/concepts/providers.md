# Providers

gin runs every stage in the harness you opened (the main harness): Claude Code, Codex, Antigravity, OpenCode, or GitHub Copilot CLI (`copilot`). It starts no process on any other harness. An Antigravity subagent runs the model of the agy session, so start agy on the model you want, for example `agy --model gemini-4-argon-high`. The [routing diagram](architecture.md#provider-routing) shows the flow.

## Capabilities

Skills work through the provider-neutral capabilities below.

| Capability | Covers |
|---|---|
| Task tracking | task identity, dependencies, readiness, claims, blockers, closure: through `gin task`, which serves local Markdown files under `.planning/tasks/` or, with `providers.task_tracking: beads`, runs Beads (`bd`); never by editing `.beads/` directly |
| Workspace | isolation (worktrees) and cleanup metadata |
| Review | request review, terminal review state, findings |
| Evidence | record and query evidence; decide whether acceptance evidence is complete |
| Knowledge | search and propose knowledge; subagents never write permanent knowledge |

Selecting a provider never authorizes a lifecycle transition; gates and approvals still apply.

## Roles, models, and efforts

Every implementation or review track in a plan names:

- a provider role: a responsibility such as `backend`, `frontend`, `docs`, `review`, or `general`, configured under `routing.roles`;
- a route: a `Model:` from the main harness's model catalog, an `Effort:` from the same catalog when it lists efforts, and a `Why:` line giving the reason.

The model catalog lists, per harness, its models from weakest to strongest and its efforts from lowest to highest ([`models`](../reference/config.md#models)). The `plan` skill picks the weakest model that can do the work, a stronger model for broad context or design judgement, and a higher effort for intricate logic. An unclear requirement never raises either; the planner asks you or returns to `discuss`. You can change the route of any track before you approve the plan.

A plan never names a concrete model outside the main harness's catalog, and never a provider. Every role resolves to the main harness at the track's model and effort. `gin routes resolve` writes the assignment manifest `.agent-workflow/runtime/assignments/<workflow>.yaml`, which is runtime metadata, not plan or task data.

`gin routes resolve` resolves the whole batch of tracks at once. A model or effort outside the main harness's catalog is a diagnostic that names the track, the value, and the allowed values. So is a track that still carries a reasoning tier in place of a model. If any track cannot be resolved, it reports every diagnostic, exits 2, and writes no manifest; the track beads `orchestrate` already created stay. `main_harness` means the configured `harness`, or the session override (`gin setup harness-override --harness <name>`, or `GIN_WORKFLOW_HARNESS_OVERRIDE`).

## Independent review

Review is independent when a fresh session or subagent of the main harness reviews with a clean context and its own actor id. The implementer's session never reviews its own work. Self-review is allowed only when `allow_self_review_fallback` is set; otherwise running out of routes needs a human decision. A review stops at `max_cycles` (`routing.review.max_cycles`) and returns `human_decision_required`. Only a terminal approval from the reviewer counts, recorded in the review ledger when `project.review_ledger` is on. The reviewer runs at the implementer's final model and effort, including any escalation. When the implementer used the weakest model of a catalog with more than one model and the diff changes more than documentation, the review uses the next model. `gin reviewer` computes that route, one fresh session of the main harness, for the `review` skill.

What runs where depends on the harness.

| Step | Claude Code, Antigravity | Codex, OpenCode, Copilot |
|---|---|---|
| Execute a track | native `gin:developer` subagent | the session implements the track and notes `in_session` on the bead |
| Review | native `gin:code-reviewer` subagent | stops for you to open a fresh session; self-review only with `allow_self_review_fallback` |
| Research in `discuss` and `plan`; scouts, writers, and reviewers in `tech-doc` | native subagent | one after another in the session |

A reviewer starts with a fresh, bounded context: the diff, the confirmed requirement, acceptance criteria, test evidence, and the `gin rules` output for the reviewed files. It excludes self-assessment, persuasive summaries, and unrelated history.

## Evidence and identity

Acceptance evidence is tied to an identity: workflow id, attempt id, task id, and the repository snapshots (repository id, source-scope hash, source-tree hash, checkpoint commit and ref). A subagent result, test record, or review approval from another task, attempt, or tree cannot satisfy acceptance; empty hashes, missing references, and stale approvals are rejected. Review evidence must be a terminal approval from the reviewer, not the implementer's own claim.

Where test evidence comes from follows `verify.run_at` ([config](../reference/config.md#verifyrun_at)). With `track`, a `gin evidence run` record backs each review request. With `push`, one record from `ship` on the feature branch backs the push, and the pre-push hook reuses it. With `host`, gin records none and the host CI owns the tests.

## Privacy

Portable configuration, plans, and bundles never contain executable paths, credentials, secrets, transcripts, or private reasoning. In portable configuration and plans, model names appear only in the model catalog (`models.<harness>.models`) and in the `Model:` lines of a plan. Configuration may hold references such as `secret_ref:NAME`; each CLI's own login owns credentials, and secret values are never written to configuration, manifests, events, results, evidence, bundles, or logs.
