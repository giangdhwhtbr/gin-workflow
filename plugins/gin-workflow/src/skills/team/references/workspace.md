# Team mode in a workspace

Read this when `gin state --format json` reports `workspace` and `project.team.enabled` is true. Facts of each command are in `docs/reference/cli.md` (`gin team`) and `docs/concepts/state-model.md`.

## Branches

- A lane branch `feat/<topic>-<lane>` starts from `origin/<default_branch>` of the lane's repository (the child its tracks' `Repo:` names, else (`Repo: .` or none) the parent). Its PR targets that branch and is approved by the `team.approvals.ship` roles.
- Orchestrate creates no child `feat/<topic>`. It creates the parent's `feat/<topic>` from the parent's default branch and pushes it. That branch holds the epic's knowledge records and, with `project.review_ledger: true`, its review ledgers.
- Spec and plan reach the default branch through their own PRs first; lanes start after both merge.

## Worktrees

- `gin team claim <bead>` creates the member's lane worktree at `.planning/worktrees/<epic>-<lane>` of the checkout where it runs. Run it from a parent checkout, or a worktree of it, on `feat/<topic>`.
- A repository not cloned stops the claim with `gin workspace clone <path>`. After a git failure the lease stays: run the claim again.

## Ledgers

This section applies with `project.review_ledger: true`.

- A child track's ledger is written to the parent's `.planning/reviews/<bead>/` on `feat/<topic>`; `review-ledger.py` finds it from the track worktree. Checkpoint commits and the review ref stay in the child.
- Every ledger session, implementer or reviewer, starts with `git pull --rebase` on `feat/<topic>` and ends with a commit of `.planning/reviews/<bead>/` and a push. This is a team convention; the tools do not do it.
- For a child track, `team handoff` pushes the parent's `feat/<topic>` when it has unpushed ledger commits (it refuses another branch with such commits), and `team takeover` pulls it when it has an upstream.

## Closing

- Ship opens the parent's `feat/<topic>` PR, targeting the parent's default branch.
- After the last PR has merged, an area lead runs `gin team complete <epic>`. Exit 1 lists what is missing: report it and wait.
