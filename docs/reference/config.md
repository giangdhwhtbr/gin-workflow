# Configuration Reference

Installing the plugin never changes a repository. Run `/setup` once per repository; it asks one question at a time, previews both configuration layers, and writes them only after you approve (see [`gin-workflow setup`](cli.md#gin-workflow-setup)). Lifecycle skills read only the generated effective configuration and stop with setup guidance when it is missing; they never run setup themselves.

## Files

| File | Tracked | Contents |
|---|---|---|
| `.agent-workflow/config.yaml` | yes | Portable settings: project profile, verify commands, artifact paths, routing roles, rules, team, QA. No commands, model names, or secrets |
| `.agent-workflow/providers.local.yaml` | no (gitignored) | Machine-local provider executables and the model for each reasoning tier |
| `.agent-workflow/generated/effective-config.yaml` | no (gitignored) | The resolved configuration every skill reads |
| `.agent-workflow/generated/config-provenance.yaml` | no (gitignored) | Which layer set each value |
| `.agent-workflow/usage-prices.yaml` | your choice | Model prices for `gin-workflow usage` |
| `.agent-workflow/runtime/` | no | Gate events (`events.jsonl`), assignment manifests, session harness override, evidence |
| `.agent-workflow/backups/` | no | Backups taken before a migration |

Full examples ship with the plugin: `plugins/gin-workflow/src/examples/config.full.yaml` and `providers.local.example.yaml`.

## Precedence

Later layers override earlier ones; `config-provenance.yaml` records the winner for each field.

1. Built-in defaults
2. User profile (`GIN_WORKFLOW_USER_PROFILE`, a YAML path)
3. Organization profile (`GIN_WORKFLOW_ORGANIZATION_PROFILE`)
4. `.agent-workflow/config.yaml`
5. `.agent-workflow/harness-override.yaml`
6. `.agent-workflow/local.yaml`
7. Command overrides

Portable layers are validated before anything is written; a value that looks like a command or a concrete model name is rejected there and belongs in `providers.local.yaml`.

## Versions and migration

`schema_version`, `workflow_version`, and `setup_cli_version` are separate compatibility channels; the current value of each is `2.7`. When the installed CLI is newer, `gin-workflow setup update` proposes the registered migration and applies it with `--approve`, after writing a validated backup to `.agent-workflow/backups/`. `rollback --backup PATH` restores one. Migrations change configuration only; they never move plans, Beads data, review ledgers, worktrees, or other artifacts.

## Keys

### Top level

| Key | Values | Default |
|---|---|---|
| `harness` | `claude`, `codex`, `antigravity`, `opencode`: the main harness that coordinates the workflow | set by setup |
| `provider_mode` | `single` (the main harness does everything) or `multi` (routed providers) | `multi` |

### `project`

| Key | Values | Default |
|---|---|---|
| `stage` | `greenfield`, `brownfield`, `legacy` | `brownfield` |
| `shape` | `frontend`, `backend`, `fullstack`, `library`; selects the `references/shape-<shape>.md` appendix the developer reads | `fullstack` |
| `monorepo`, `packages` | monorepo flag and detected packages | `false` |
| `stack_intent` | free text for a greenfield project | `""` |
| `rigor` | `easy`, `standard`, `strict` | `standard` |
| `worktree` | `never`, `parallel`, `always` | from rigor |
| `review` | `self_check`, `independent` | from rigor |
| `review_ledger` | require a review ledger | from rigor |

Rigor presets:

| Rigor | Worktree | Review | Ledger | `/quick` |
|---|---|---|---|---|
| `easy` | never | self check | no | allowed |
| `standard` | for parallel work | independent | no | allowed |
| `strict` | always | independent | yes | needs a `requirement_confirmed` waiver |

### `verify.checks`

`lint`, `typecheck`, `test`, `build`, `e2e`: shell commands. `verify` and `/quick` run the ones the rigor requires (easy: lint, typecheck, test; standard: + build; strict: + e2e). Empty commands are skipped. `gin-workflow setup doctor` reports missing ones.

### `quick`

`max_files` (default 5): the largest change `/quick` accepts; it also accepts only one module.

### `artifacts`

| Key | Default | Meaning |
|---|---|---|
| `plans` | `.planning/plans` | approved plans |
| `worktrees` | `.planning/worktrees` | git-fallback worktrees |
| `knowledge` | `.planning/knowledge` | durable project knowledge |
| `beads` | `.beads` | Beads database |
| `runtime`, `evidence` | `.agent-workflow/runtime`, `.agent-workflow/runtime/evidence` | runtime state |
| `layout` | `legacy` | `sdd` turns on living specs |
| `specs`, `changes`, `adr`, `codebase` | — | SDD folders, for example `docs/specs` and `docs/changes` |
| `spec_review` | `chat` | SDD spec review: `chat` or `pr` |
| `test_globs` | — | globs that identify test files for `specs trace` |

### `routing`

| Key | Meaning |
|---|---|
| `roles.<role>.preferred`, `.fallback` | ordered providers for a role (`claude`, `codex`, `antigravity`, `opencode`, or `main_harness`) |
| `roles.<role>.require_independent` | the role must use a different provider from the implementer |
| `concurrency.<provider>` | maximum concurrent workers |
| `queue.max_wait_seconds` | how long a task waits for capacity (default 600) |
| `worker.timeout_seconds`, `worker.max_retries` | worker limits (retries default 2) |
| `circuit_breaker.failure_threshold`, `cooldown_seconds`, `half_open_max_probes` | when a failing provider is skipped and how it recovers |
| `review.role`, `require_independent`, `allow_self_review_fallback`, `max_cycles`, `independence` | independent review policy; `independence` is `provider` or `session` |

Plans name roles and a reasoning tier (`low`, `medium`, `high`), never providers or models.

### `model_tiers`

Maps lifecycle phases (`brainstorm`, `design`, `plan`, `implement`, `verify`, `review`, `docs`) to abstract model classes (`high_reasoning`, `standard_impl`, `cheap_simple`).

### `policy.approval`

`ttl_seconds` (default 86400) and `bind_to_scope` (default `true`): how long a recorded approval stays valid and whether it is tied to the source tree it approved.

### `rules`

| Key | Meaning |
|---|---|
| `packs` | extra rule packs to enable, for example `[typescript, react]` |
| `disabled` | packs to turn off, including the defaults |

`core` and `lean` are always enabled unless disabled. Project packs live in `.agent-workflow/rules/`. Inspect the result with `gin-workflow rules --list`. See [Rule packs](../guides/rules.md).

### `team`

Present only in team mode ([guide](../guides/team.md)): `host` (`github` or `gitlab`), `commit_convention`, `members` (email → `roles`, `login`), `areas` (name → `paths`, `lead`, `roles`), `approvals` (per gate: a role list or `area_lead`; `roadmap` takes a role list and gates the `/roadmap` pull request), and `beads_sync.remote`.

### `qa`

Used by the `gin-qa` add-on: `cases` (default `qa/cases`), `guidelines` (default `qa/guidelines.md`), `e2e` (default `qa/e2e`).

## `providers.local.yaml`

```yaml
schema_version: "2.3"
providers:
  claude:
    executable: claude
    models: {low: haiku, medium: sonnet, high: opus}
  antigravity:
    executable: agy
    models: {low: <model>, medium: <model>, high: <model>}
  opencode:
    executable: opencode
    models: {low: provider_default, medium: provider_default, high: <provider/model>}
  codex:
    executable: codex
    models:
      high: {model: <model>, effort: high}
```

Each provider names its executable and a model per reasoning tier; Codex tiers may add a reasoning `effort`; Antigravity and OpenCode tiers may be `provider_default`. `gin-workflow setup models --provider <name>` lists the models a CLI reports. Credentials stay with each CLI's own login.

## `usage-prices.yaml`

```yaml
prices:
  <model id>: {input: 3.0, output: 15.0, cache_read: 0.3, cache_write: 3.75}
```

USD per million tokens. Models without a price show `-` and are listed as `unpriced`.
