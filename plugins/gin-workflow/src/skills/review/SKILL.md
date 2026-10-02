---
name: review
description: Request or perform an independent bead review recorded in the review ledger, with bounded cycles.
---

## Before you start
1. If `.agent-workflow/generated/effective-config.yaml` does not exist in the repository, stop: tell the user to run `/setup` once and do nothing else. (`capabilities: {}` is a valid config.)
2. Read [references/stage-contract.md](../../references/stage-contract.md) now: it defines the gate CLI, valid evidence, approval, and git rules this stage relies on.

# Review

Review after every track, after a major feature, and before merge; never skip because "it's simple". A completed implementation starts review; it is not evidence that the task may close. Ledgers live in `.planning/reviews/<bead-id>/` (legacy fallback `.planning/<bead-id>/`). All commands are `python3 review-ledger.py <cmd> --bead-id <bead-id> ...`; never hand-write or copy `review.json`.

## Requesting (implementer)
1. `init --repo-id <id> [--repo-path <worktree>] [--include <scope>]` once (idempotent), then `checkpoint --repo-id <id> --commit-msg "<msg>" --actor-id <id>` to snapshot the reviewed tree.
2. Dispatch an independent reviewer with a fresh context: reviewed diff, confirmed requirement, acceptance criteria, and test evidence only. Exclude private reasoning, self-assessment, persuasive summaries, unrelated history, and secrets.
3. Record the implementation's original provider/model route as runtime affinity only; never put concrete aliases in the plan or Beads.
4. Handle findings with the `gin-review-response` skill: fix Critical immediately and Important before proceeding, note Minor ones, and push back with evidence when the reviewer is wrong.

## Reviewing (reviewer)
1. Independence follows `project.independence` from `gin-workflow state --format json`: `provider` — the reviewer provider must differ from the implementation provider; `session` — a fresh session/subagent of the same provider with a clean context and a different actor id (`reviewer:<provider>:session-<id>`), never the implementer's session. Self-review only under the explicit `allow_self_review_fallback` policy; otherwise route exhaustion needs a human decision.
2. `start-review --actor-id <reviewer>` acquires the lease (`--force-takeover --reason "<why>"` only when authorized; `resync-lease --lease-id <id>` after a stale revision). `validate` replays the ledger.
3. Inspect the in-scope files for correctness, edge cases, error handling, security, performance, and plan alignment; run the tests in isolation. Never modify implementation files.
4. Record each issue with `add-finding --finding-id <id> --severity <sev> --actor-id <reviewer> --lease-id <lease>`.
5. For a claimed fix, check the tree. If confirmed, `verify-finding`; if absent, incomplete, or wrong, `reopen-finding --reason "<why>"`. `verified` is terminal, so never verify what you could not confirm. If sources changed, re-run `checkpoint` before approving.
6. When every finding is terminal, `approve --actor-id <reviewer> --lease-id <lease>`; otherwise request changes. Then `render`.

## Cycles
Each unresolved revision is a new review cycle. Stop at the maximum review cycles (`routing.review.max_cycles`) and return `human_decision_required`; never loop unbounded. Never manufacture approval or close work on a notification.
