# State Model

Each kind of workflow state has exactly one owner. When two sources disagree, the owner wins; everything else is derived or disposable.

| Question | Owner |
|---|---|
| What work exists, what depends on what, what is ready, who claimed it, is it done? | Beads |
| What was agreed to build? | the confirmed spec in `.planning/specs/` (SDD: the change folder and living specs) |
| What files and tests belong to a track? | the approved plan in `.planning/plans/` (a standalone bead: its description and acceptance criteria) |
| Was a gate confirmed, approved, waived, or recorded? | the event store, `.agent-workflow/runtime/events.jsonl` |
| What did review find, and is the current tree approved? | the review ledger, `.planning/reviews/<bead>/` |
| Which worktree, branch, or provider route did a track use? | runtime metadata (derived, disposable) |
| What did AI work on a bead cost? | the bead's `ai_usage` metadata |

## Beads

Beads (`bd`) owns task identity, priority, status (`open`, `in_progress`, `closed`), claims, dependencies, blockers, follow-ups, and closure. "What is active, blocked, or ready?" is answered from Beads (`bd ready`, `bd show`, or the `progress` skill), never from local files.

`orchestrate` creates two kinds of beads:

- **Parent bead (epic)**: the deliverable. It stays open until a human-confirmed merge; closing it is what marks the workflow `shipped`. Merge holds belong only here.
- **Track beads**: one per plan track (`bd create --parent <epic>`), with technical acceptance criteria only: code in scope, tests passing, review approved. A track closes as soon as those hold, which unblocks its dependents. It never waits for the parent's merge.

`implementation_complete` is derived from Beads: every child of the epic recorded at `orchestration-ready` is closed.

## Plans and specs

Specs (`.planning/specs/<date>-<topic>-design.md`) record the confirmed design; plans (`.planning/plans/<date>-<feature>.md`) record the approved decomposition: tracks, file scope, interfaces, validation intent, provider roles, and reasoning tiers. They are durable inputs, not status: a plan checkbox never proves progress. With `artifacts.layout: sdd` the spec and plan live in a change folder under `artifacts.changes` and requirements carry REQ-IDs.

## Event store

`gin-workflow record` and `unblock` append to `.agent-workflow/runtime/events.jsonl`: `requirement.confirmed`, `approval.recorded` (plan approval), `orchestration.ready` (with the epic), `verification.passed`, `quick.completed`, `delivery.shipped`, `gate.waived`, and `blocker.cleared`. Events are append-only and idempotent: recording the same gate with the same evidence twice adds nothing. `gin-workflow state` replays them per workflow id, together with Beads, to derive the gates. The store is local to the machine; team mode proves gates with pull requests instead. All untracked workflow state — this store, the rest of `.agent-workflow/runtime/`, `generated/effective-config.yaml`, and `providers.local.yaml` — lives in the main checkout: commands run inside a linked worktree read and write the main checkout's copy, so a gate recorded in either place is one state.

## Review ledger

`review-ledger.py` keeps one ledger per bead in `.planning/reviews/<bead>/`: `review.json` (the event log, never edited by hand) and `review.md` (rendered). It owns:

- the reviewed source snapshot: a checkpoint commit on `refs/gin/review/<bead>` with scope and tree hashes, taken without touching your branch or index;
- the review lease: one active reviewer at a time;
- findings, each moving to a terminal state (`verified`, `withdrawn`, `deferred-verified`, `human-waived`);
- approval, which holds only while the tree still matches the approved snapshot; `change-scope` or new commits invalidate it.

The ledger moves through `implementation-in-progress`, `review-requested`, `review-in-progress`, then `changes-requested`, `blocked-human`, or `review-approved`. Approval needs every finding terminal. After a bead is closed and merged, `review-ledger.py cleanup --bead-id <bead>` (or `--all-closed`) removes its ledger and its `refs/gin/review/` checkpoint refs; `--all-closed` also deletes leftover refs of closed beads whose ledger is already gone.

## The `.planning/` and `.agent-workflow/` trees

```
.planning/
  specs/        confirmed designs
  plans/        approved plans
  reviews/      review ledgers, one folder per bead
  worktrees/    git-fallback worktrees, one per track or epic (gitignored)
  knowledge/    durable project knowledge
.agent-workflow/
  config.yaml              portable configuration (tracked)
  providers.local.yaml     machine-local providers (gitignored)
  generated/               resolved configuration (gitignored)
  runtime/                 events.jsonl, assignment manifests, harness override, evidence (gitignored)
  backups/                 migration backups (gitignored)
```

Paths come from `artifacts.*` ([Configuration](../reference/config.md#artifacts)); migrations never move these artifacts.

## Runtime metadata

Worktree paths, branch names, assignment manifests (`runtime/assignments/<workflow>.yaml`), worker receipts, circuit-breaker state, and evidence indexes are runtime metadata. They must be reconstructible from Beads and the plan, or safe to delete. They support audit and verification but never decide whether work is pending or done:

- never infer closure from a deleted worktree or branch;
- never let a local cache override Beads;
- repair or discard stale runtime files rather than trusting them.

## Usage summaries

`gin-workflow usage collect` stores a summary in the bead's metadata under `ai_usage`: tokens and estimated cost per model and per lifecycle stage, and quality signals (reopens, bugs found later, review cycles, rejections, findings by severity, waivers). It holds aggregates only, never prompts, session ids, or log paths.
