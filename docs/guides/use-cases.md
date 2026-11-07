# Use cases

Four common situations and the path through the workflow for each. Commands are shown as Claude Code slash commands (`/gin:<skill>`); Codex uses `$gin:<skill>`.

## Small change

A typo, a copy change, a one-file fix with an obvious test.

1. `/gin:quick <what to change>`: the agent restates the change in a few lines and waits for your confirmation.
2. It runs `gin quick-check` with its estimate of files and modules. `escalate` means the change exceeds the quick limits; use the full lifecycle (below). `refused` comes only under `strict` rigor: use the full lifecycle, or waive `requirement_confirmed` with `gin unblock` to use `/quick`.
3. It implements (test first when behavior changes), runs the verify commands for your rigor, and reviews (self check under `easy`, independent otherwise).
4. It commits on the current feature branch, or on a new `quick/<slug>` when started on `main`/`master`, and records `quick-completed`. It does not push.
5. You review the diff, then push or open a pull request.

If the change grows past the estimate, the agent re-runs `quick-check` and stops on `escalate`.

## Bounded defect

A reproducible bug whose fix should stay narrow.

1. `/gin:discuss`: confirm the symptom, the expected behavior, and what is out of scope.
2. Diagnose with the `debugging` skill: reproduce, find the root cause, and stop if it is not isolated. Do not guess a plan.
3. `/gin:plan`: one track with a regression test that fails before the fix.
4. `/gin:orchestrate`, then `/gin:execute`: the regression goes red, the fix turns it green, review approves, the track closes.
5. `/gin:ship`.

If the diagnosis widens the scope, return to `discuss`; never broaden the patch silently. A small enough fix can use the quick path instead.

## Large multi-track change

A feature or migration that splits into dependent tracks, for example CSV export: (A) schema and permissions, (B) a streaming exporter that depends on A, (C) the download UI that depends on B.

1. `/gin:discuss` produces the confirmed spec.
2. `/gin:plan` gives each track its files, interfaces, test-first steps, a provider role (`backend` for A and B, `frontend` for C), and a model and effort from the model catalog with the reason for the choice.
3. `/gin:orchestrate` creates the epic and three track tasks, then resolves every route and writes the assignment manifest only when all tracks resolve. It then adds the dependencies and creates the worktree.
4. `/gin:execute` per ready track, each in a `gin:developer` subagent at the track's model and effort: A first; closing A makes B ready, and so on. Each track is reviewed independently before it closes.
5. `/gin:ship` checks every ledger and any changes after review (the quality gates already ran in the git hooks), then merges or opens the pull request with your approval.

Routes to other harnesses need the [gin-orchestrator](../orchestrator/README.md) extension; without it every track runs on the main harness. If a route is unavailable the task stays open; a fallback harness runs the route mapped by rank into its own catalog. If route resolution reports an unresolved role, or a model or effort outside the catalog, it writes no manifest until the plan or the configuration is fixed; the beads stay.

## Resume in-progress work

A session, provider, or machine stopped before the work reached a terminal state.

1. `/gin:progress` reads the durable state: bead status, readiness, blockers, waivers, review state, and recent quick runs. A leftover worktree or branch is not evidence of progress.
2. If a track's review is pending, finish the review first (the `review` skill): the reviewer takes a fresh lease, checks the current snapshot, and records findings or approval.
3. `/gin:workflow` routes to exactly one stage. Once every track is closed it selects `ship`, which fails closed when a ledger lacks terminal approval.
4. Continue from the stage it names.

When the state is held, `gin state` lists the remedies: clear a blocker, waive a process gate with a reason, or fix the missing configuration through `/setup`. A leftover worktree or runtime cache is [runtime metadata](../concepts/state-model.md#runtime-metadata), not state, so do not use either to mark work done.
