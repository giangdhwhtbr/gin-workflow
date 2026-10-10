# Use Cases

Four common situations and the path through the workflow for each. Commands are shown as Claude Code slash commands (`/gin-workflow:<skill>`); Codex uses `$gin-workflow:<skill>`.

## Small change

A typo, a copy change, a one-file fix with an obvious test.

1. `/gin-workflow:quick <what to change>`: the agent restates the change in a few lines and waits for your confirmation.
2. It runs `gin-workflow quick-check` with its estimate of files and modules. `escalate` or `refused` means the full lifecycle (below) is needed.
3. It implements (test first when behavior changes), runs the verify commands for your rigor, reviews (self check under `easy`, independent otherwise), and records `quick-completed`.
4. You review the diff and commit.

If the change grows past the estimate, the agent re-runs `quick-check` and stops on `escalate`.

## Bounded defect

A reproducible bug whose fix should stay narrow.

1. `/gin-workflow:discuss`: confirm the symptom, the expected behavior, and what is out of scope.
2. Diagnose with the `gin-debugging` skill: reproduce, find the root cause, and stop if it is not isolated. Do not guess a plan.
3. `/gin-workflow:plan`: one track with a regression test that fails before the fix.
4. `/gin-workflow:orchestrate`, then `/gin-workflow:execute`: the regression goes red, the fix turns it green, review approves, the track closes.
5. `/gin-workflow:ship`.

If the diagnosis widens the scope, return to `discuss`; never broaden the patch silently. A small enough fix can use the quick path instead.

## Large multi-track change

A feature or migration that splits into dependent tracks, for example CSV export: (A) schema and permissions, (B) a streaming exporter that depends on A, (C) the download UI that depends on B.

1. `/gin-workflow:discuss` produces the confirmed spec.
2. `/gin-workflow:plan` gives each track its files, interfaces, test-first steps, a provider role (`backend` for A and B, `frontend` for C), and a reasoning tier.
3. `/gin-workflow:orchestrate` resolves every route before creating anything, then creates the epic, three track beads, their dependencies, and the worktree.
4. `/gin-workflow:execute` per ready track: A first; closing A makes B ready, and so on. Each track is reviewed independently before it closes.
5. `/gin-workflow:ship` checks every ledger and any changes after review (the quality gates already ran in the git hooks), then merges or opens the pull request with your approval.

If a route is unavailable the bead stays open; fallback never lowers the reasoning tier. If orchestration reports an unresolved role or tier, it creates nothing until the plan or `providers.local.yaml` is fixed.

## Resume in-progress work

A session, provider, or machine stopped before the work reached a terminal state.

1. `/gin-workflow:progress` reads the durable state: bead status, readiness, blockers, waivers, review state, and recent quick runs. A leftover worktree or branch is not evidence of progress.
2. If a track's review is pending, finish the review first (the `review` skill): the reviewer takes a fresh lease, checks the current snapshot, and records findings or approval.
3. `/gin-workflow:workflow` routes to exactly one stage. Once every track is closed it selects `ship`, which fails closed when a ledger lacks terminal approval.
4. Continue from the stage it names.

When the state is held, `gin-workflow state` lists the remedies: clear a blocker, waive a process gate with a reason, or fix the missing configuration through `/setup`. Never delete a worktree to mark work done, edit runtime caches, or bypass `bd`.
