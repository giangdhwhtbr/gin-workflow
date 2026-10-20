# Split gin-orchestrator out of gin-workflow

Status: confirmed 2026-10-20.

## Goal and scope

gin-workflow has grown to hold two products: the lifecycle engine (gates, state,
specs, skills, review ledger) and multi-provider orchestration (routing, worker
dispatch, circuit breaker, cross-provider review). Split them so each can be
installed, versioned and changed on its own:

- **gin-workflow** controls the workflow and runs standalone with Python stdlib,
  PyYAML and git. It does not require Beads (`bd`).
- **gin-orchestrator** owns multi-agent orchestration and requires Beads.
- **gin-console** (already a separate repo) is unchanged by this epic; it reads
  both through their CLI JSON output and imports neither.
- **gin-harness** (`~/gin-harness`) is a meta-repo holding the shared Beads
  database, the cross-project roadmap, `versions.lock` and a sync script. It
  holds no product code.

In scope: the code boundary, the orchestrator CLI contract, the task-tracking
backend interface, the release sequence, and the harness layout.

Out of scope (separate epics on the harness roadmap, after the split): the
Orca-inspired improvements (gate-holding notifications, diff annotation as
human findings, console write actions, fan-out, quota-aware routing, starting
from an issue, `doctor --fix`), and any gin-console change.

## Requirements

### Boundary

- gin-workflow keeps `workflow_core/` except routing, plus the review ledger,
  evidence verification (`evidence.py`, `evidence_authority.py`), usage
  reporting (`usage*.py`, `/report`), specs/SDD, rules, hooks and team mode.
- `task_tracking.py` and `task_tracking_markdown.py` move from
  `workflow_providers/` into `workflow_core/` behind a `TaskBackend` interface
  with two implementations: `markdown` (default) and `beads`.
- `implementation_complete` and `shipped` are derived through `TaskBackend`,
  never by calling `bd` directly.
- gin-orchestrator receives `workflow_providers/` (minus task tracking),
  `router.py`, `worker_scheduler.py`, `review_coordinator.py`,
  `provider_config.py`, `providers.local.yaml` handling, and the `orchestrate`
  and `gin-parallel-agents` skills.
- gin-workflow imports nothing from gin-orchestrator and vice versa. The only
  link is the CLI contract below.

### Orchestrator CLI contract (v1)

gin-workflow owns the schema at `contracts/orchestrator-v1.schema.json`. Every
command reads JSON on stdin (where it takes input) and writes JSON on stdout.

| Command | Input | Output |
|---|---|---|
| `gin-orchestrator version --json` | none | `{contract_version, orchestrator_version}` |
| `gin-orchestrator health --json` | none | per-provider health, replacing the direct health imports in `setup_service.py` |
| `gin-orchestrator dispatch --json` | list of `WorkerRequest` | list of `WorkerResult` |
| `gin-orchestrator review --json` | review request | review result, which gin-workflow writes to its own ledger |

`WorkerRequest` and `WorkerResult` keep the fields of the existing dataclasses
in `worker_dispatch.py`; the contract serializes them, it does not redesign them.

gin-workflow finds the executable through `executable_resolver.py`.

### Execution flow

- With gin-orchestrator on PATH and a matching `contract_version`, `/execute`
  calls `dispatch`. The orchestrator owns route resolution, worktrees, retries
  and the circuit breaker.
- gin-workflow verifies every returned `WorkerResult` itself (commits,
  `source_tree_hash`, test results) before accepting it. An orchestrator claim
  is input, never evidence.
- Without gin-orchestrator, `/execute` runs the track in the current agent, as
  the sequential worker does today.

### Configuration

- `providers.task_tracking` defaults to `markdown`. `beads` is allowed only when
  `bd` is on PATH.
- Installing gin-orchestrator into a repo sets `providers.task_tracking: beads`.
- Team mode requires gin-orchestrator (and so Beads). The existing check at
  `configuration.py:187` changes its message to say so.

### gin-harness

- `.beads/` lives in the harness. Each child repo's `.beads` is a symlink to it,
  and each child keeps its own issue-id prefix.
- Child repos are cloned as siblings into gitignored directories inside the
  harness by `scripts/sync.sh`; no git submodules.
- `versions.lock` pins a known-good combination of child versions.

### Release sequence

Each step ships as its own release and leaves existing consumers working.
The first implementation plan covers steps 1 and 2 only; steps 3 and 4 become
separate epics on the gin-harness roadmap.

1. **gin-workflow 1.7**: move task tracking into `workflow_core`, add
   `TaskBackend`, derive gates through it.
2. **gin-workflow 1.8**: replace the three direct `workflow_providers` imports
   (`review_coordinator.py`, `setup_service.py`, `worker_scheduler.py`) with
   `orchestrator_client.py`, which calls `python -m workflow_providers ...` as a
   subprocess inside this repo. This proves the contract before any repo split.
3. **Split**: `git filter-repo` the orchestrator files and skills into
   `~/gin-orchestrator`, keeping history. gin-workflow **2.0** removes them.
4. **Harness**: add `sync.sh` and `versions.lock`, and consolidate child `.beads`
   into the harness via symlinks.

## User Stories

### US-1: Use gin-workflow without Beads
As a solo developer, I want to install gin-workflow without `bd`, so that I can
use the gated lifecycle with the fewest dependencies.

Acceptance criteria:
- A fresh repo with only Python, PyYAML and git completes `/setup` with no Beads.
- `discuss → plan → execute → ship` completes with markdown task tracking.
- `implementation_complete` and `shipped` are reported from markdown tasks.
- `/execute` runs tracks in the current agent when gin-orchestrator is absent.

### US-2: Add orchestration by installing gin-orchestrator
As a developer running several providers, I want installing gin-orchestrator to
switch on routed workers and Beads, so that orchestration is opt-in.

Acceptance criteria:
- After installing gin-orchestrator, `providers.task_tracking` is `beads`.
- `/execute` sends tracks through `gin-orchestrator dispatch` and records the
  returned results only after gin-workflow verifies their evidence.
- `setup`/`doctor` report provider health from `gin-orchestrator health`.
- Team mode cannot be enabled without gin-orchestrator, and the error says so.

### US-3: Change each project independently
As the maintainer, I want gin-workflow and gin-orchestrator in separate repos
joined by a versioned contract, so that I can release one without the other.

Acceptance criteria:
- Neither repo imports code from the other.
- A contract-version mismatch holds `state` with `orchestrator_contract_mismatch`.
- gin-orchestrator CI runs the contract tests against the gin-workflow version
  pinned in `versions.lock`.
- gin-orchestrator's git history includes the moved files' history.

### US-4: Track all projects from the harness
As the maintainer, I want one Beads database in gin-harness, so that I can plan
cross-project epics in one place.

Acceptance criteria:
- `scripts/sync.sh` clones or updates every child repo listed in `versions.lock`.
- Running `bd` inside any child repo reads and writes the harness database.
- Bead ids keep a distinct prefix per child repo.
- `gin-workflow state` inside a child repo finds that repo's beads.

## Errors and compatibility

- **Orchestrator missing**: run inline. If the config declares provider routing,
  `doctor` warns that routing needs gin-orchestrator.
- **Contract version mismatch**: `state` holds with
  `orchestrator_contract_mismatch`. No silent fallback to inline, because that
  would change the execution strategy without approval.
- **Non-zero exit or output that fails the schema**: treated as a worker failure
  and handled by the existing retry and hold path.
- **`task_tracking: beads` without `bd`**: config validation fails with a message
  naming the missing executable.
- **Existing consumers on 1.x**: 1.7 and 1.8 keep behavior unchanged. 2.0
  release notes tell routed-worker users to install gin-orchestrator; `doctor`
  detects routing config without the orchestrator.
- **Beads data**: moving `.beads` to the harness keeps existing issues and ids;
  the consolidation step backs up each child `.beads` first.

## Testing

- gin-workflow: a fake orchestrator built on the existing `fakes.py`, plus JSON
  schema tests for every contract command.
- Both `TaskBackend` implementations pass the same gate-derivation tests.
- Smoke tests run the lifecycle twice: inline with markdown, and through the
  orchestrator with Beads.
- gin-orchestrator CI pins gin-workflow from `versions.lock` and runs the
  contract tests.
- An import-boundary check fails if either repo imports the other.
