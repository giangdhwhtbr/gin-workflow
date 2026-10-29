# Model and effort selection per track

Epic: gin-workflow-btt3
Status: draft for user review.

## Goal and scope

Each plan track recommends a concrete model and effort, chosen from a model catalog the team shares in configuration. The main session coordinates; implementation, review, and code exploration run in subagents spawned at the model and effort their work needs.

Measured on 2026-10-29 with `gin-workflow usage report --bead gin-workflow-9pl2`:
- `claude-opus-5-5`: 28.4M cache-read and 148K output tokens.
- `claude-sonnet-5-5`: 0.69M cache-read and 4K output tokens.
- By stage: execute 14.5M, discuss 12.3M, plan 2.3M, and 58.8M unattributed.

Most tokens come from the main session, not from workers. Three things cause this:
- `execute/SKILL.md` tells the main session to implement directly for three or fewer tasks.
- The resolved model in the assignment manifest is never applied when a subagent is spawned.
- Four agent files carry a tier name as `model:` (`solution-architect.md:5` has `high_reasoning`; `developer.md`, `bead-worker.md`, and `qa-agent.md` have `standard_impl`). Claude Code rejects these with `404 model_not_found`.

There are also two vocabularies, and only one of them is used. Tracks name `Reasoning: low|medium|high`, which drives routing. `model_tiers` (`configuration.py:42`) maps phases to `high_reasoning`/`standard_impl`/`cheap_simple`, but nothing reads it, and it disagrees with "Model Guidance" in `plan-schema.md` (plan: `high_reasoning` against `standard_impl`).

In scope:
- Claude Code as the main harness.
- The other harnesses get a catalog entry and clean agent files, but keep today's behavior otherwise.

Out of scope:
- Subagent dispatch on Codex, Antigravity, OpenCode, and Copilot.
- gin-orchestrator reading the catalog instead of `orchestrator.local.yaml`.
- Mapping a plan from one harness's catalog to another's.
- A team-shared override layer for configuration.
- `/quick`, which keeps implementing in the main session.
- The decks under `docs/presentations/`.

## Requirements

### R1. A model catalog in configuration

`.agent-workflow/config.yaml` accepts `models.<harness>` with two ordered lists:
- `models`: from weakest to strongest.
- `efforts`: from lowest to highest.

```yaml
models:
  claude:
    models: [haiku, sonnet, opus]
    efforts: [low, medium, high, xhigh, max]
```

Built-in defaults, so that a repository without the key still works:

| Harness | `models` | `efforts` |
|---|---|---|
| `claude` | `haiku`, `sonnet`, `opus` | `low`, `medium`, `high`, `xhigh`, `max` |
| `codex` | `gpt-6-astra` | `low`, `medium`, `high`, `xhigh` |
| `antigravity`, `opencode` | `provider_default` | none |

A configured harness entry replaces that harness's default entry as a whole.

Validation runs in every portable layer:
- Both lists hold unique, non-empty strings.
- `models` is not empty. `efforts` may be empty.
- Concrete model names are allowed only under `models.<harness>.models`. Everywhere else they stay forbidden (`configuration.py:161`), and executables and secrets stay forbidden everywhere.

`gin-workflow state --format json` exposes the effective catalog of the main harness.

### R2. Plan tracks recommend model and effort

Each implementation or review track carries three lines in place of `Reasoning:` and the "Model Guidance" section:

```
Model: sonnet
Effort: medium
Why: bounded change to one module with a clear spec; edge cases listed in the spec.
```

`Model` and `Effort` come from the main harness's catalog. `Effort` is omitted when the catalog lists no efforts. `Provider role` stays.

`plan-schema.md` and `plan/SKILL.md` give the planner this rubric:
- Choose the weakest model that can do the work.
- Raise the model for broad context or design judgement.
- Raise the effort for intrinsic difficulty: intricate logic, many edge cases, or long chains of steps.

| Kind of work | Model | Effort |
|---|---|---|
| Mechanical edits, documentation, boilerplate | weakest | `low` |
| Bounded implementation with a clear spec | middle | `medium` |
| Cross-module change, security, migration, concurrency | strongest | `high` |

Unclear requirements never raise the model or effort. A track whose requirement is ambiguous, contradictory, or missing does not enter an approved plan; the planner asks the user or returns to `discuss`.

The user can change `Model` and `Effort` per track before approving the plan.

### R3. Routes resolve and validate model and effort

The tracks file for `gin-workflow routes resolve` changes:
- Before: `{"task_id", "provider_role", "reasoning"}`.
- After: `{"task_id", "provider_role", "model", "effort"}`.

Validation:
- A model not in the main harness's catalog is a diagnostic naming the track, the value, and the allowed values. So is an effort not in the catalog.
- An effort given for a harness with no efforts is a diagnostic.
- Exit 2 reports every diagnostic, as today.

The manifest at `.agent-workflow/runtime/assignments/<workflow>.yaml` stores `model` and `effort` for each track. Effort is no longer restricted to Codex (`assignments.py:71`): any harness whose catalog lists efforts accepts one.

Removed:
- `model_tiers`, from `BUILT_IN_DEFAULTS`, the schema, `config.full.yaml`, and `config.md`.
- The classes `high_reasoning`, `standard_impl`, and `cheap_simple`.
- The `reasoning` field of the tracks file.

Manifests already written for open workflows stay valid and are not rewritten.

### R4. Execute delegates every track

`execute/SKILL.md` drops the rule to execute directly for sequential work or three or fewer tasks. For each track, the main session does five things in order:
1. Claims the track.
2. Reads `model` and `effort` from the manifest.
3. Spawns `gin-workflow:developer` with those values and a bounded context: the track text, file scope, `gin-workflow rules` output, worktree path, and validation commands.
4. Checks the returned evidence: commits and command output.
5. Requests review.

The developer reports one status: `done`, `needs_clarification`, `failed`, or `blocked`.

| Status | Main session action |
|---|---|
| `done` | Check the evidence, then request review. |
| `needs_clarification`: ambiguous, contradictory, or missing requirement | No escalation. When the spec or plan answers the question, re-dispatch at the same route with that excerpt. Otherwise ask the user (`gin-workflow notify --event needs_input`) and leave the bead `in_progress` with a note. |
| `failed`: validation still fails after the developer's own retries, or the work cannot be finished | Escalate one step: the next model in the catalog at the same effort. At the strongest model, use the next effort instead. Keep the worktree and its commits. At the top of both lists, stop and ask the user. |
| `blocked`: missing access, credentials, or an external dependency | Ask the user. |

Each dispatch writes a runtime event with the track, model, effort, and escalation reason. A requested route is never lowered.

### R5. Review follows the implementer's route

`gin-workflow reviewer` replaces `--tier` with `--model` and `--effort`. The reviewer uses the implementer's final model and effort, which includes any escalation, and never a lower one. `review/SKILL.md` names the `gin-workflow:code-reviewer` agent and spawns it with that route. Fixes after `changes-requested` go to the developer at its current route, and `routing.review.max_cycles` still bounds the cycles.

### R6. Discuss and plan delegate code exploration

`discuss/SKILL.md` and `plan/SKILL.md` send code lookups and behavior checks to `gin-workflow:agent-researcher`. The route comes from the catalog by the R2 rubric:
- Locating code: weakest model at `low`.
- Verifying behavior across modules: middle model at `medium`.

The researcher returns findings with `file:line` evidence. The main session keeps the conversation with the user and the decisions, and writes the spec or plan. Before writing a claim into the spec, it reads only the lines it needs to confirm that claim.

### R7. Agent files

| Agent | Change |
|---|---|
| all | No `model:` line. The model is always passed at spawn. |
| `developer` | Gains file edit and file write tools. `install.sh` and `install.ps1` map their source names per harness, as they map `view_file` to `Read` today. |
| `agent-researcher` | Gains `run_command`. Its prompt allows only read-only commands (`git log`, `--help`, `codegraph`). |
| `code-reviewer` | Gains `list_dir`. |
| `bead-worker` | Deleted. It duplicates `developer`, and no skill names it. |
| `solution-architect` | Deleted. No skill names it, and design belongs to the main session. |
| `qa-agent`, `docs-writer` | Only the `model:` line is removed. |

The bead notes of gin-workflow-btt3 record this table as the tool-list review.

### R8. Usage separates the main session from subagents

`UsageRecord` gains a role: `main` or `subagent`. A Claude Code record is a subagent record when its line has `"isSidechain": true`; subagent transcripts live under `<session>/subagents/` and are already scanned by `usage_logs.py`. `gin-workflow usage report` shows tokens and cost per role and model. No percentage target is set: this epic produces the first clean baseline.

### R9. Schema 2.9

`schema_version`, `workflow_version`, and `setup_cli_version` become `2.9`. The 2.8 → 2.9 migration:
- removes `model_tiers`;
- keeps every other key;
- writes the usual validated backup.

`gin-workflow setup doctor` reports a `model_tiers` key in any layer as unsupported and names the replacement, `models`.

## User Stories

### US-1: Plan recommends a route per track
As the user approving a plan, I want each track to name a concrete model and effort with a reason, so that I can check and change the cost and capability before any work starts.

Acceptance criteria:
- Every implementation or review track in a new plan has `Model:`, `Effort:` (when the catalog has efforts), and `Why:` lines.
- The values come from the main harness's catalog.
- No plan written by `/plan` contains `Reasoning:`, "Model Guidance", or an abstract model class.

### US-2: The team shares one model catalog
As a team member, I want the list of models and efforts in the committed configuration, so that everyone plans and runs against the same choices.

Acceptance criteria:
- `models.claude.models: [sonnet, opus]` in `config.yaml` passes validation and replaces the built-in Claude list.
- A model name anywhere outside `models.<harness>.models` is rejected, as today.
- A duplicate or empty entry in either list is rejected with its location.
- Without a `models` key, the built-in catalog applies.

### US-3: Invalid routes stop before dispatch
As the user, I want an unknown model or effort caught when routes resolve, so that no subagent fails at spawn with `model_not_found`.

Acceptance criteria:
- `gin-workflow routes resolve` exits 2 and names the track, the value, and the allowed values for a model or effort outside the catalog.
- No manifest is written when any track has a diagnostic.
- A valid tracks file writes `model` and `effort` per track into the manifest.

### US-4: Implementation runs in a subagent at the planned route
As the user, I want every track implemented by a subagent at its planned model and effort, so that the expensive main session only coordinates.

Acceptance criteria:
- `execute/SKILL.md` no longer allows direct execution for small or sequential work; `/quick` is unchanged.
- The skill spawns `gin-workflow:developer` with the manifest's `model` and `effort`.
- A runtime event records the route of each dispatch.

### US-5: Unclear requirements reach a human, failures escalate
As the user, I want an unclear requirement to come back to me and a capability failure to move up one step, so that no agent guesses and no failure loops forever.

Acceptance criteria:
- A `needs_clarification` result never changes the route. It is either answered from the spec or plan, or it raises `needs_input` with the bead left `in_progress`.
- A `failed` result re-dispatches at the next model, or at the next effort when already at the strongest model, and records the reason.
- At the strongest model and highest effort, a `failed` result stops and asks the user.

### US-6: Review matches the implementer
As the user, I want the reviewer to run at least at the implementer's final route, so that a cheap implementation is not checked by a cheaper review.

Acceptance criteria:
- `gin-workflow reviewer --model <m> --effort <e>` returns routes at that model and effort; `--tier` is gone.
- After an escalation, the review uses the escalated route.

### US-7: Exploration in discuss and plan runs in subagents
As the user, I want code lookups during discuss and plan to run in a cheaper subagent, so that the main session's context grows less.

Acceptance criteria:
- `discuss/SKILL.md` and `plan/SKILL.md` direct code lookups to `gin-workflow:agent-researcher` at a catalog route chosen by the R2 rubric.
- The researcher can run read-only shell commands.

### US-8: Every agent spawns on Claude Code
As the user, I want each remaining gin-workflow agent to spawn on Claude Code, so that dispatch never fails on a model name.

Acceptance criteria:
- No file under `plugins/*/src/agents/` has a `model:` line, and a test fails if one is added.
- `bead-worker` and `solution-architect` no longer exist in source or in a fresh install.
- Spawning `developer`, `agent-researcher`, `code-reviewer`, `qa-agent`, and `docs-writer` from Claude Code with an explicit catalog model starts without `model_not_found`. This is checked by hand after `./install.sh --platform all`.

### US-9: Usage shows where tokens go
As the user, I want the usage report split by main session and subagent per model, so that I can see whether delegation saves tokens.

Acceptance criteria:
- A Claude Code record with `"isSidechain": true` is counted as `subagent`, and any other record as `main`.
- `gin-workflow usage report` prints tokens and cost per role and model.

## Errors and compatibility

- **Old configuration.**
  - A 2.8 config with `model_tiers` keeps loading until migrated; doctor reports the key.
  - `gin-workflow setup update --to-version 2.9 --approve` removes it.
- **Old plans and manifests.** Approved plans and manifests already written keep working. A tracks file with `reasoning` and no `model` is a diagnostic that asks for `model` and `effort`.
- **gin-orchestrator.** When `routes` is delegated (`provider_mode: multi` with gin-orchestrator installed), gin-orchestrator still expects `reasoning`. `routes resolve` derives it from the model's position in the main harness's catalog, adds a warning that names the derivation, and does not forward the effort. The rule:
  - The weakest model gives `low`.
  - The strongest model gives `high`.
  - Any other model, or the only model in a one-entry catalog, gives `medium`.
- **Catalog drift.** A harness renames or retires a model. The user edits `models.<harness>.models`; `routes resolve` then rejects plans that still name the old model, before any spawn.
- **Documentation.** These pages change with the code:
  - `docs/concepts/providers.md`, `architecture.md`, `lifecycle.md`, `state-model.md`;
  - `docs/reference/config.md`, `cli.md`, `orchestrator-contract.md`;
  - `docs/guides/use-cases.md`;
  - `docs/orchestrator/README.md`, `routing.md`.

  Each page drops `Reasoning`, `model_tiers`, and the abstract classes, and describes the catalog where it describes routing.
- **gin-console.** It does not read `reasoning`, `model_tiers`, or the manifest, so it needs no change.

## Testing

- `tests/workflow_core/test_configuration.py`:
  - the catalog defaults;
  - a configured entry replacing the default;
  - duplicate and empty entries;
  - a model name outside the catalog rejected.
- `tests/workflow_core/test_routes_cli.py` and `test_assignments.py`:
  - valid model and effort written to the manifest;
  - every diagnostic case in R3;
  - effort accepted for `claude`;
  - the gin-orchestrator `reasoning` derivation and its warning.
- `tests/workflow_core/test_reviewer.py`: `--model` and `--effort`, and no `--tier`.
- `tests/workflow_core/test_migrations.py`: 2.8 → 2.9 removes `model_tiers`, keeps the other keys, and writes a backup. Doctor reports `model_tiers`.
- An agent-file test:
  - no `model:` line under `plugins/*/src/agents/`;
  - `bead-worker` and `solution-architect` absent;
  - the Claude build maps the new tool names.
- `tests/workflow_core/test_usage_logs.py` and `test_usage.py`: the sidechain record counted as `subagent`, and the report split by role.
- The full suite passes: `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.test_all`.
- By hand, after `./install.sh --platform all`: each agent in US-8 spawns on Claude Code with an explicit catalog model.
