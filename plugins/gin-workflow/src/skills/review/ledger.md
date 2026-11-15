# Review ledger

Follow this with `project.review_ledger: true` from `gin state --format json`, next to the `review` skill. Ledgers live in `.planning/reviews/<bead-id>/` (legacy fallback `.planning/<bead-id>/`); in a workspace, a child track's ledger lives in the parent's `.planning/reviews/`, which `review-ledger.py` finds from the track worktree (team mode: the `team` skill). All commands are `python3 review-ledger.py <cmd> --bead-id <bead-id> ...`; never hand-write or copy `review.json`. Write each ledger command with literal flags, never in shell variables (zsh does not split them); check its exit code and report only what its output shows.

## Requesting (implementer)
1. `init --repo-id <id> [--repo-path <worktree>] [--include <scope>] --max-cycles <project.max_cycles>` once (idempotent).
2. `checkpoint --repo-id <id> --commit-msg "<msg>" --actor-id <id>` snapshots the reviewed tree.
3. With `project.run_at: track`, `gin evidence run` in the worktree (fix any failure first).
4. `transition-requested --to review-requested --actor-role worker --actor-id <id>`; without it the reviewer cannot approve.
5. After `changes-requested`: fix (the `review-response` skill), `transition-requested --to implementation-in-progress`, `checkpoint`, and request review again.

## Reviewing (reviewer)
1. `start-review --actor-id <reviewer>` acquires the lease; the ledger refuses the init actor as reviewer (`--force-takeover --reason "<why>"` only when authorized; `resync-lease --lease-id <id>` after a stale revision). `validate` replays the ledger.
2. Record each issue with `add-finding --finding-id <id> --severity <sev> --actor-id <reviewer> --lease-id <lease>`.
3. For a claimed fix, check the tree. If confirmed, `verify-finding`; if absent, incomplete, or wrong, `reopen-finding --reason "<why>"`. `verified` is terminal, so never verify what you could not confirm. If sources changed, re-run `checkpoint` before approving.
4. When every finding is terminal, `approve --actor-id <reviewer> --lease-id <lease>`; otherwise request changes with `transition-requested --to changes-requested --actor-role reviewer --actor-id <reviewer> --lease-id <lease>` (`reject` only invalidates an existing approval). Then `render`, and `release-lease --actor-id <reviewer> --lease-id <lease>` so the implementer can write again.

## Cycles
`start-review` exits 1 at the maximum review cycles (`project.max_cycles`, passed as `init --max-cycles`) with `max review cycles (N) reached`; return `human_decision_required` instead of retrying. When the human allows another cycle, `record-human-decision --question "<q>" --decision "<d>" --reason "<why>" --actor-id <human>` without `--finding-id` lets `start-review` run once more.
