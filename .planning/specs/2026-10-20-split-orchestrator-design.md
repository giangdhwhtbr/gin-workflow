# Split gin-orchestrator out of gin-workflow

Status: confirmed 2026-10-20 (revised after code review). Steps 2–3 are
superseded by `2026-10-21-orchestrator-extension-design.md`: gin-orchestrator
is an extension that depends on gin-workflow, starts as
`plugins/gin-orchestrator/` in this repository, and the `orchestrate` and
`gin-parallel-agents` skills stay in gin-workflow.

## Goal and scope

gin-workflow has grown to hold two products: the lifecycle engine (gates, state,
specs, skills, review ledger) and a multi-provider worker library (worker
dispatch, scheduler, circuit breaker, routed workers, provider registry). Split
them so each can be installed, versioned and changed on its own:

- **gin-workflow** controls the workflow and runs standalone with Python stdlib,
  PyYAML and git. It does not require Beads (`bd`).
- **gin-orchestrator** owns the multi-provider worker library and requires Beads.
- **gin-console** (already a separate repo) is unchanged by this epic; it reads
  both through their CLI JSON output and imports neither.
- **gin-harness** (`~/gin-harness`) is a meta-repo holding each repo's Beads
  database, a harness database for cross-project epics, the cross-project roadmap, `versions.lock` and a sync script. It
  holds no product code.

In scope: the code boundary, the orchestrator CLI contract, the release
sequence, and the harness layout.

Out of scope (separate epics on the harness roadmap, after the split): wiring
the worker library into `/execute` (a `dispatch`/`review` contract), the
Orca-inspired improvements (gate-holding notifications, diff annotation as
human findings, console write actions, fan-out, quota-aware routing, starting
from an issue, `doctor --fix`), and any gin-console change.

## Findings from the code (2026-10-20)

These replace assumptions in the first draft.

- **Dispatch today is done by the host agent, not by Python.** `/execute` and
  `/review` tell the agent to launch workers itself, using routes from
  `gin-workflow reviewer` (`reviewer.py`, `assignments.py`,
  `provider_config.py`, all in `workflow_core`). No CLI command, hook or skill
  reaches `worker_dispatch`, `worker_scheduler`, `review_coordinator`,
  `registry`, `circuit_breaker` or the `*_worker` adapters; only tests do.
- **The only runtime calls from `workflow_core` into `workflow_providers`** are
  `setup doctor --probe` (`setup_service.py:510`, provider health) and
  `setup models` (`setup_service.py:932`, `list_models`).
- **Task tracking already has a backend switch.** `workflow_core/tasks.py`
  routes every task query to Markdown or `bd`, and the delivery gates use it
  (`lifecycle_cli._beads_json`). The provider classes in
  `workflow_providers/task_tracking*.py` are used only by `registry.py`, so they
  belong to the orchestrator side.
- **`router.py` is lifecycle routing** (`route_next_stage`), and
  `provider_config.py`/`assignments.py` feed `gin-workflow reviewer`. All three
  stay in gin-workflow.
- **`workflow_providers` imports 12 `workflow_core` modules** (`identity`,
  `events`, `provider_config`, `models`, `router`, `executable_resolver`,
  `assignments`, `approvals`, `manifests`, `checkout`, `atomic`, and the
  package). The split (step 2) must resolve this reverse dependency.

## Requirements

### Boundary

- gin-workflow keeps all of `workflow_core/` except `worker_scheduler.py` and
  `review_coordinator.py`, plus the review ledger, `tasks.py`/`task_markdown.py`,
  usage reporting, specs/SDD, rules, hooks, team mode and `gin-workflow reviewer`.
- `worker_scheduler.py` and `review_coordinator.py` move into
  `workflow_providers/`, since only that package and its tests use them.
- gin-orchestrator receives `workflow_providers/` (including the task-tracking
  provider classes) and the `orchestrate` and `gin-parallel-agents` skills.
- `workflow_core` imports nothing from `workflow_providers`. The only link is
  the CLI contract below. A test enforces this.

### Orchestrator CLI contract (v1)

Every command prints one JSON document on stdout and exits 0 on success.
gin-workflow documents the contract in `docs/reference/orchestrator-contract.md`.

| Command | Output |
|---|---|
| `version --json` | `{"contract_version": 1, "orchestrator_version": "<str>"}` |
| `health --provider P --executable PATH [--model M] [--effort E] [--workspace DIR] --json` | `{"available": bool, "reason": "<str>"}` |
| `models --provider P --json` | list of `{"id", "label", "description", "reasoning_levels"}` |

Until the split, the commands run as `python -m workflow_providers <command>`.
After it, as `gin-orchestrator <command>`.

### Client in gin-workflow

- `workflow_core/orchestrator_client.py` runs the contract. It uses
  `gin-orchestrator` from PATH when present, else the bundled
  `python -m workflow_providers`.
- It checks `contract_version` once per process. A different version raises
  `OrchestratorError("orchestrator_contract_mismatch")`.
- `setup doctor --probe` and `setup models` call the client instead of importing
  `workflow_providers`. Their JSON output does not change.

### Configuration

- `providers.task_tracking` keeps its current behavior in this epic (unset means
  `beads`; setup offers `markdown` when `bd` is missing). Making `markdown` the
  default moves to step 2, together with a migration that writes `beads`
  explicitly into existing configs.
- Team mode keeps requiring Beads. Its error message names gin-orchestrator once
  the split ships (step 2).

### gin-harness

- Each child repo's `.beads` is a symlink to `~/gin-beads/<repo>/`; every repo keeps its own database and issue-id prefix. A `gin-harness` database at `~/gin-beads/gin-harness` (linked from `~/gin-harness/.beads`) holds cross-project epics, and beads of different repos depend on each other through `external:<project>:<capability>` (see `2026-10-21-beads-harness-migration-design.md`).
- Child repos are cloned as siblings into gitignored directories inside the
  harness by `scripts/sync.sh`; no git submodules.
- `versions.lock` pins a known-good combination of child versions.

### Release sequence

Each step ships as its own release and leaves existing consumers working.
The first implementation plan covers step 1 only; steps 2 and 3 become separate
epics on the gin-harness roadmap.

1. **gin-workflow 1.7**: the bundled contract CLI, `orchestrator_client.py`,
   setup switched to it, `worker_scheduler.py` and `review_coordinator.py` moved
   into `workflow_providers/`, and the import-boundary test.
2. **Split**: resolve the reverse imports, then `git filter-repo`
   `workflow_providers/` and the two skills into `~/gin-orchestrator`, keeping
   history. gin-workflow **2.0** removes them and makes `markdown` the default.
3. **Harness**: add `sync.sh` and `versions.lock`. (The Beads move into the harness
   ships first, per `2026-10-21-beads-harness-migration-design.md`.)

## User Stories

### US-1: Use gin-workflow without Beads
As a solo developer, I want to install gin-workflow without `bd`, so that I can
use the gated lifecycle with the fewest dependencies.

Acceptance criteria:
- A fresh repo with only Python, PyYAML and git completes `/setup` with no Beads.
- `discuss → plan → execute → ship` completes with markdown task tracking.
- `implementation_complete` and `shipped` are reported from markdown tasks.

### US-2: Reach the worker library only through its CLI
As the maintainer, I want gin-workflow to talk to the worker library only
through a versioned CLI contract, so that the library can leave the repo
without breaking setup.

Acceptance criteria:
- No file under `workflow_core/` imports `workflow_providers`.
- `setup doctor --probe` and `setup models` print the same JSON as before.
- A `gin-orchestrator` on PATH reporting another `contract_version` makes
  `setup doctor --probe` report `orchestrator_contract_mismatch`.

### US-3: Change each project independently
As the maintainer, I want gin-workflow and gin-orchestrator in separate repos,
so that I can release one without the other.

Acceptance criteria:
- Neither repo imports code from the other.
- gin-orchestrator CI runs the contract tests against the gin-workflow version
  pinned in `versions.lock`.
- gin-orchestrator's git history includes the moved files' history.

### US-4: Track all projects from the harness
As the maintainer, I want every repo's Beads database kept in gin-harness, so that I can plan cross-project epics in one place.

Acceptance criteria:
- `scripts/sync.sh` clones or updates every child repo listed in `versions.lock`.
- Each child repo's `.beads` is a symlink into `~/gin-beads/`, and `bd` there reads and writes that repo's own database.
- Bead ids keep a distinct prefix per child repo; cross-repo order uses `external:` dependencies.
- `gin-workflow state` inside a child repo finds that repo's beads.

## Errors and compatibility

- **Contract version mismatch**: `doctor --probe` marks providers unavailable
  with reason `orchestrator_contract_mismatch`; `setup models` fails with that
  message. No silent fallback to the bundled copy.
- **Contract command fails** (non-zero exit or invalid JSON): `doctor` reports
  the provider unavailable with reason `orchestrator_failed`; `setup models`
  returns an empty list, as `list_models` does today on failure.
- **Existing consumers on 1.x**: 1.7 changes no command output. 2.0 release
  notes tell routed-worker users to install gin-orchestrator.
- **Beads data**: moving `.beads` to the harness keeps existing issues and ids,
  and each child `.beads` is backed up first (`2026-10-21-beads-harness-migration-design.md`).

## Testing

- Contract tests run each command through the bundled module and check its JSON.
- Client tests use a fake `gin-orchestrator` script on PATH for the mismatch and
  failure cases.
- The existing `test_doctor_offline_and_opt_in_probe_behavior` and
  `test_list_models` keep passing unchanged.
- An import-boundary test fails if any `workflow_core` file imports
  `workflow_providers`.
