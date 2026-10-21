# gin-orchestrator as an extension of gin-workflow

Workflow: orchestrator-extension
Status: draft for user review.

Supersedes step 2 of `2026-10-20-split-orchestrator-design.md` (see "Changes to
the split spec" below).

## Goal and scope

gin-workflow maintains the workflow. It runs with one main harness and no
external tools: Python stdlib, PyYAML and git. gin-orchestrator is an extension
of gin-workflow: installing it installs gin-workflow, and it is what lets a
project use several harnesses (one main harness plus other harnesses as
workers). gin-console requires both.

"One harness" means one agent harness. Subagents of that harness running the
model of a reasoning tier are part of gin-workflow, as they are today.

In scope:

- gin-orchestrator as a second plugin in this repository,
  `plugins/gin-orchestrator/`, built like `plugins/gin-qa/` (own launcher,
  version and marketplace entry).
- The one-way boundary: gin-orchestrator may import gin-workflow through a
  public facade, `workflow_core.ext`; gin-workflow never imports
  gin-orchestrator.
- gin-workflow as the single front door: its commands delegate multi-harness
  work to `gin-orchestrator` when a project runs `provider_mode: multi` and the
  orchestrator is installed, and handle everything for one harness otherwise.
- Orchestrator CLI contract v2 with capabilities.
- Config ownership, a schema migration, and `markdown` as the default task
  backend.
- One release when every track is complete: gin-workflow 2.0.0 and
  gin-orchestrator 0.1.0.

Out of scope:

- Moving gin-orchestrator to its own repository (`~/gin-orchestrator` stays
  empty). That is a later `git filter-repo` of `plugins/gin-orchestrator/` and
  its tests, once `workflow_core.ext` and contract v2 are stable.
- A Beads database for gin-orchestrator (it shares this repository's database
  until it has its own repository).
- Wiring the worker library to actually run workers (`gin-orchestrator
  dispatch`); today the host agent launches workers from the skills. This is
  the next epic.
- `versions.lock`, `scripts/sync.sh`, gin-console changes.

## Findings (2026-10-21)

- `provider_mode: single|multi` already exists (`project.py`,
  `assignments.py`, `provider_config.py`, `setup --provider-mode`); single mode
  routes every role to `main_harness` and picks the tier model from
  `DEFAULT_HARNESS_MODELS`.
- `workflow_providers/` (8.3k lines, 23 test files) imports 12 `workflow_core`
  modules (about 2.4k lines): `identity`, `events`, `provider_config`,
  `assignments`, `router`, `models`, `manifests`, `approvals`,
  `executable_resolver`, `checkout`, `atomic`, `task_markdown`.
- `task_tracking*.py` in `workflow_providers` is used only by `registry.py`;
  `workflow_core/tasks.py` already switches between `markdown` and `bd`.
- No command, hook or skill reaches `worker_dispatch`, `worker_scheduler` or
  `circuit_breaker`; only tests do. Runtime calls into `workflow_providers` are
  `setup doctor --probe` and `setup models`, through `orchestrator_client.py`.
- The installed launcher lives in `~/.local/lib/gin-workflow/<launcher
  version>/` next to `workflow_core/`; gin-qa and gin-console reach
  gin-workflow only through its CLI JSON.
- Config migrations are chained functions in `migrations.py`
  (`CURRENT_VERSION = "2.7"`), applied by `gin-workflow setup update`.

## Requirements

### Boundary

- `plugins/gin-orchestrator/src/scripts/gin_orchestrator/` holds what is
  today `plugins/gin-workflow/src/scripts/workflow_providers/`, renamed, minus
  `task_tracking.py` and `task_tracking_markdown.py`, which are deleted; the
  orchestrator calls `gin-workflow task ... --json` for task tracking instead.
- `tests/workflow_providers/` moves to `tests/gin_orchestrator/`.
- Multi-harness code moves from `workflow_core` to `gin_orchestrator`:
  - from `provider_config.py`: `providers.local.yaml` parsing and the
    per-provider model, tier and executable mapping for workers;
  - from `assignments.py`: multi-provider route resolution (preferred,
    `by_tier`, fallback chains, circuit and capacity checks) and the worker
    assignment manifest.
- `workflow_core` keeps single-harness resolution: every role resolves to the
  main harness, the tier picks that harness's model from
  `DEFAULT_HARNESS_MODELS`, and the result is written to the same assignment
  manifest path (`.agent-workflow/runtime/assignments/<workflow>.yaml`) so
  `/execute` reads one format in both modes.
- The `orchestrate` and `gin-parallel-agents` skills stay in gin-workflow.
- `workflow_core/ext.py` is the public facade. It re-exports the functions and
  types the orchestrator uses from `identity`, `events`, `models`
  (`freeze`, `thaw`), `manifests`, `atomic`, `checkout`, `executable_resolver`,
  `router.authorize_protected_action` and `approvals`, and declares
  `EXT_VERSION = 1`. Removing or changing a re-exported signature raises
  `EXT_VERSION`.
- No file under `workflow_core/` imports `gin_orchestrator` or
  `workflow_providers`. No file under `gin_orchestrator/` imports a
  `workflow_core` module other than `workflow_core.ext`.
- `workflow_providers/` no longer exists in gin-workflow.

### Front door and delegation

- gin-workflow commands are the only entry points skills use. With
  `provider_mode: multi` and an available orchestrator they delegate:

  | gin-workflow command | Delegates to |
  |---|---|
  | `gin-workflow routes resolve` (new, replaces the Python call in `/orchestrate`) | `gin-orchestrator routes resolve` |
  | `gin-workflow reviewer` | `gin-orchestrator reviewer` |
  | `gin-workflow setup doctor --probe` | `gin-orchestrator doctor` |
  | `gin-workflow setup models` | `gin-orchestrator models` |

  Otherwise they resolve for the main harness only. Their JSON output keeps
  one shape in both modes.
- `gin-workflow routes resolve --workflow-id W --tracks FILE --json` reads a
  JSON list of `{"task_id", "provider_role", "reasoning"}`, resolves every
  track before writing anything, writes the assignment manifest, and prints
  the resolved routes; on any unresolved track it writes nothing and prints
  every diagnostic.
- `gin-workflow state --format json` gains
  `extensions.orchestrator: {"available", "version", "contract",
  "capabilities", "reason"}`, computed once per invocation through
  `orchestrator_client`.
- `gin-workflow paths --json` (new) prints `{"lib_dir": "<dir holding
  workflow_core>"}` for the orchestrator launcher.
- Skills: `/setup` asks only for the main harness. Sentences about running a
  worker on another provider, provider independence and worker capacity say
  they apply with gin-orchestrator. `/orchestrate` calls
  `gin-workflow routes resolve` instead of importing `workflow_core`.

### Orchestrator CLI contract v2

Every command prints one JSON document on stdout and exits 0 on success.
`docs/reference/orchestrator-contract.md` documents it.

| Command | Output |
|---|---|
| `version --json` | `{"contract": 2, "orchestrator_version", "requires_gin_workflow": ">=2.0,<3", "capabilities": [...]}` |
| `health --provider P --executable PATH [--model M] [--effort E] [--workspace DIR] --json` | `{"available": bool, "reason": str}` (unchanged) |
| `models --provider P --json` | list of `{"id", "label", "description", "reasoning_levels"}` (unchanged) |
| `routes resolve --workflow-id W --tracks FILE --main-harness H --json` | same shape as `gin-workflow routes resolve` |
| `reviewer --base B --implementer P --tier T --json` | ordered list of reviewer routes `{"provider", "model", "actor_id"}` |
| `doctor --json` | `{"providers": {"<provider>.<tier>": {"available", "reason"}}}` |

- The capabilities in 0.1.0 are `health`, `models`, `routes`, `reviewer`,
  `doctor`.
- `orchestrator_client` reads `version` once per process. A `contract` other
  than 2 makes the orchestrator unavailable with reason
  `orchestrator_contract_mismatch`. A missing capability makes only the
  matching command fall back to the main harness.
- The client runs only `gin-orchestrator` from `PATH`; the bundled
  `python -m workflow_providers` fallback is removed.

### Configuration

- `.agent-workflow/config.yaml` stays one file. A top-level `orchestrator:`
  mapping belongs to gin-orchestrator: gin-workflow keeps it unchanged and does
  not validate its contents; gin-orchestrator validates it.
- Keys under `orchestrator:`: `roles` (the multi-provider form of today's
  `routing.roles`), `concurrency`, `circuit_breaker`, `queue`, `worker`.
- gin-workflow keeps `provider_mode`, `routing.review.max_cycles`,
  `routing.review.independence`, `routing.review.require_independent`,
  `routing.review.allow_self_review_fallback`, `routing.review.role`, and
  `routing.roles` entries whose only route is `main_harness`.
- `.agent-workflow/providers.local.yaml` becomes
  `.agent-workflow/orchestrator.local.yaml` (git-ignored, gin-orchestrator's).
- `providers.task_tracking` defaults to `markdown` when unset.
- `routing.review.independence: provider` requires the orchestrator.
- Schema 2.8 migration `_migrate_2_7_to_2_8`, applied by `gin-workflow setup
  update --to-version 2.8 --approve`:
  - moves `routing.roles` entries that name a provider other than
    `main_harness`, and `routing.concurrency`, `routing.circuit_breaker`,
    `routing.queue`, `routing.worker` under `orchestrator:`;
  - writes `providers.task_tracking: beads` when the key is unset, so an
    existing project keeps its backend;
  - renames `providers.local.yaml` to `orchestrator.local.yaml` when present;
  - is idempotent and backed up like the earlier migrations.
- `/setup` on a new project writes `provider_mode: single`,
  `routing.review.independence: session`, and `providers.task_tracking:
  markdown` unless the user picks `beads`.

### gin-orchestrator plugin and install

- `plugins/gin-orchestrator/src/` holds `.claude-plugin/`, `.codex-plugin/`,
  `scripts/gin-orchestrator` (launcher), `scripts/gin_orchestrator/`, and a
  skill `providers` (`/gin-orchestrator:providers`) that configures worker
  harnesses, roles and tiers through `gin-orchestrator configure --set`,
  writes `orchestrator:`, sets `provider_mode: multi` and
  `routing.review.independence: provider`, and runs `gin-orchestrator doctor`.
- The launcher runs `gin-workflow paths --json`, puts `lib_dir` on `sys.path`,
  checks `workflow_core.ext.EXT_VERSION`, then runs `gin_orchestrator.cli`.
  Without `gin-workflow` on PATH it exits 1 with an install hint.
- `./install.sh --plugin gin-orchestrator` installs the gin-workflow plugin
  first when `gin-workflow` is missing or older than the required version,
  then installs the orchestrator launcher in
  `~/.local/lib/gin-orchestrator/<version>/` linked from `~/.local/bin`.
  `--plugin all` installs gin-workflow, gin-qa and gin-orchestrator.
- `.claude-plugin/marketplace.json` lists `gin-orchestrator` with
  `path: plugins/gin-orchestrator/src`.
- The build that produces `plugins/*/dist/` builds gin-orchestrator like
  gin-qa.

### Release

- Tracks land on one feature branch, or merge to `master` without a version
  change. The last track bumps gin-workflow to 2.0.0, sets gin-orchestrator
  to 0.1.0, and writes release notes: run `setup update --to-version 2.8`,
  then install gin-orchestrator to keep multi-harness routing.

## Changes to the split spec

`2026-10-20-split-orchestrator-design.md` steps 2–3 change as follows:

- gin-orchestrator depends on gin-workflow (through `workflow_core.ext`); only
  gin-workflow importing gin-orchestrator is forbidden. US-3's "Neither repo
  imports code from the other" no longer holds.
- The `orchestrate` and `gin-parallel-agents` skills stay in gin-workflow.
- gin-orchestrator starts as `plugins/gin-orchestrator/` in this repository;
  the separate repository comes later.
- Team mode keeps working with Beads in gin-workflow; Beads stays an optional
  backend of gin-workflow, not an orchestrator feature.

## User Stories

### US-1: Use gin-workflow with one harness and no extra tools
As a solo developer, I want gin-workflow to work with only my main harness and
no Beads, so that I can start with the fewest moving parts.

Acceptance criteria:
- `/setup` on a fresh repository with Python, PyYAML and git, and no `bd` or
  `gin-orchestrator`, asks only for the main harness and writes
  `provider_mode: single` and `providers.task_tracking: markdown`.
- `discuss → plan → orchestrate → execute → ship` completes with markdown
  tasks, and `implementation_complete` and `shipped` are reported.
- `gin-workflow routes resolve` routes every role to the main harness with the
  tier's model, and `gin-workflow reviewer` returns a session-independent
  reviewer on the main harness.
- `gin-workflow state` reports `extensions.orchestrator.available: false`.

### US-2: Add workers by installing gin-orchestrator
As a developer who wants several harnesses, I want installing gin-orchestrator
to bring gin-workflow along and unlock worker configuration, so that I can add
workers without changing how I run the lifecycle.

Acceptance criteria:
- `./install.sh --plugin gin-orchestrator` on a host without gin-workflow
  installs both; `gin-orchestrator version --json` reports contract 2.
- `/gin-orchestrator:providers` writes `orchestrator:` and
  `provider_mode: multi`, and `gin-workflow setup doctor --probe` reports the
  configured workers' availability.
- With a worker configured for a role and tier, `gin-workflow routes resolve`
  returns that worker, and `gin-workflow reviewer` returns routes on another
  provider than the implementer.

### US-3: Keep the dependency one-way
As the maintainer, I want gin-workflow never to import gin-orchestrator and
gin-orchestrator to use only a declared facade, so that each can change
without breaking the other.

Acceptance criteria:
- A test fails if any `workflow_core` file imports `gin_orchestrator` or
  `workflow_providers`.
- A test fails if any `gin_orchestrator` file imports a `workflow_core` module
  other than `workflow_core.ext`.
- A test pins the names `workflow_core.ext` exports and its `EXT_VERSION`.

### US-4: Upgrade an existing project
As a user of gin-workflow 1.x, I want one migration to move my settings, so
that my project keeps its tasks and, with gin-orchestrator, its workers.

Acceptance criteria:
- `setup update --to-version 2.8 --approve` on this repository moves the
  worker routing under `orchestrator:`, writes `providers.task_tracking:
  beads`, and keeps `gin-workflow task ready` listing the same beads.
- After the migration and with gin-orchestrator installed, `routes resolve`
  returns the same routes as before the migration.
- With `provider_mode: multi` and no gin-orchestrator, the lifecycle runs on
  the main harness, and `state` and `setup doctor` show a warning naming the
  install command.

### US-5: See whether the orchestrator is active
As a gin-console user, I want `gin-workflow state` to report the orchestrator,
so that the console shows whether a project runs with workers.

Acceptance criteria:
- `gin-workflow state --format json` includes
  `extensions.orchestrator` with `available`, `version`, `contract`,
  `capabilities` and, when unavailable, `reason`.

## Errors and compatibility

| Situation | Behavior |
|---|---|
| `provider_mode: multi`, no `gin-orchestrator` on PATH | Routes and reviewer resolve to the main harness; `state` and `doctor` warn with reason `orchestrator_missing` and the install command. Work is not blocked. |
| `contract` other than 2 | Orchestrator unavailable, reason `orchestrator_contract_mismatch`; same fallback and warning. No bundled fallback exists. |
| A delegated command exits non-zero or prints invalid JSON | `doctor` reports `orchestrator_failed`; `routes resolve` and `reviewer` fall back to the main harness with a warning; `setup models` returns an empty list. |
| Missing capability | Only that command falls back to the main harness. |
| `independence: provider` without the orchestrator | Treated as `session` with a warning; self-review stays forbidden. |
| `gin-orchestrator` without `gin-workflow` | Exits 1 with the install command. |
| `EXT_VERSION` the launcher does not support | Exits 1 naming both versions. |
| Unset `providers.task_tracking` after the 2.0 upgrade without migrating | `markdown` is used; `setup doctor` warns when a `.beads` directory exists and the key is unset. |

## Testing

- gin-workflow:
  - import-boundary tests (US-3), and a pinned export list for `ext`;
  - fresh-repository lifecycle with markdown and no `bd` (US-1);
  - single-harness `routes resolve` and `reviewer`;
  - delegation with a fake `gin-orchestrator` on PATH for available,
    missing, contract mismatch, missing capability, and failing command;
  - `state` `extensions.orchestrator`;
  - the 2.7 → 2.8 migration on a copy of this repository's config, run
    twice (idempotent), plus rollback;
  - `install_smoke_test.sh` and `.ps1` cover `--plugin gin-orchestrator`
    installing gin-workflow first.
- gin-orchestrator:
  - the moved provider tests under `tests/gin_orchestrator/`, importing only
    `workflow_core.ext`;
  - contract v2 tests for every command against the in-repo gin-workflow;
  - multi-provider `routes resolve` and `reviewer` produce the routes the
    current `resolve_all_assignments` and `gin-workflow reviewer` produce for
    this repository's config.
