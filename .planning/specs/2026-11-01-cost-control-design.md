# Cost control: enforced budgets, no wasted test reruns

Epic: gin-workflow-rm-cost-control
Status: draft for user review.

## Goal and scope

AI spend per epic has an enforced ceiling when prices are known, usage is fresh after every dispatch, reviewers reuse passing hook runs instead of rerunning tests, and `routes resolve` flags a plan that routes every track to the strongest model.

In scope:
- `usage.budget_usd` per epic, with a budget status written by `usage collect`.
- `routes dispatch` refuses to dispatch when the epic is over its stop threshold.
- `execute` collects usage after every worker returns, not only at track close.
- Git hooks record a passing verify run against the commit tree; `gin-workflow evidence check` reports it; the reviewer reruns tests only when no matching record exists.
- `routes resolve` warns when every track routes to the top model of its harness catalog.

Out of scope:
- Model prices: no prices ship in code; the user writes `.agent-workflow/usage-prices.yaml`.
- Retry by failure kind, passing the prior attempt's `changed_files`, opening the circuit breaker on the first QUOTA or AUTH failure, and one constant for the timeout and retry defaults: moved to `gin-workflow-dura`, which wires the orchestrator dispatch path these rules act on.
- Process-group kill on timeout: already done on POSIX; the Windows gap belongs to `gin-workflow-rm-windows-parity`.
- Multi-track parallel dispatch inside `execute`.

Current behavior this changes (`S` = `plugins/gin-workflow/src`, `W` = `S/scripts/workflow_core`, `O` = `plugins/gin-orchestrator/src/scripts/gin_orchestrator`):
- `W/usage.py:43-66` prices tokens from `.agent-workflow/usage-prices.yaml`; with no file, every model is `unpriced` and `cost` is null. This repository has no price file, so every recorded epic shows `cost: null`. No budget key exists in `W/schemas.py`, and `O/budget.py` does not exist.
- `S/skills/execute/SKILL.md:44` runs `usage collect` only before closing a track; `S/skills/ship/SKILL.md:31,36` run it at merge and close-out. No running total exists during execution.
- `W/routes.py:160` `dispatch` checks only the manifest; it returns exit 2 for a missing track or route.
- `WorkerScheduler` (`O/worker_scheduler.py`, the retry loop) is built only by `O/registry.py:424` `build_worker_scheduler`, which only tests call. The circuit breaker threshold is 3 (`O/config.py:9`). On the Claude main-harness path, none of these run.
- `O/evidence.py:309` `find_verification` reads `verification.recorded` events, which only gin-orchestrator writes; no reviewer path calls it.
- `S/skills/review/SKILL.md:23` tells the reviewer to run the tests on every review.
- `W/hooks.py:109` `run` executes the verify commands and records nothing.
- `W/routes.py:34` `resolve` returns a `warnings` list; nothing compares routes with the catalog's strongest model (`W/catalog.py:10`, models ordered weakest to strongest).

## Requirements

### Budget
- `.agent-workflow/config.yaml` accepts an optional `usage.budget_usd`, a positive number. Configs without it validate as today.
- `usage collect --bead <epic>` writes `budget: {budget_usd, cost, status}` into the epic's `ai_usage` metadata and prints it (text and `--format json`). It is omitted when no budget is set.
- `status` is one of:
  - `ok`: cost below 80% of the budget;
  - `warn`: cost at or above 80% and below 120%;
  - `stop`: cost at or above 120%; the 20% margin covers the error of time-span attribution;
  - `unenforceable`: a model with usage has no price; the output names those models and `.agent-workflow/usage-prices.yaml`.
- The 80% and 120% thresholds are constants in `W/usage.py`, not configuration.
- `usage collect --bead <track>` on a child bead does not write a budget block; the budget belongs to the epic.

### Dispatch stop
- `gin-workflow routes dispatch --workflow-id <epic> --task-id <id>` reads the epic's stored `ai_usage.cost` and compares it with the current `usage.budget_usd`. When cost is at or above 120% of the budget, it prints `{"status": "over_budget", "cost": ..., "budget_usd": ...}` and exits 3, without changing the manifest.
- Raising `usage.budget_usd` in the config lets the next dispatch proceed without another collect.
- With no budget, no stored cost, or a null cost, dispatch behaves as today.
- `execute/SKILL.md` runs `gin-workflow usage collect --bead <epic> --best-effort` each time a worker returns, whatever its status. On dispatch exit 3 it runs `gin-workflow notify --event needs_input`, leaves the bead `in_progress` with a note, and asks the user to raise the budget or stop. The text replaces the track-close collect at `execute/SKILL.md:44`, and the execute stage chain stays within the 12,000-character budget.

### Verification evidence
- When the `pre-commit` or `pre-push` hook's verify commands all exit 0 and `git status --porcelain --untracked-files=no` is empty, the hook appends a `verification.passed` event to the runtime event log with the tree hash it tested, the hook name, the verify command names, and the time. For `pre-push` the tree is `HEAD^{tree}`; for `pre-commit` it is the staged tree (`git write-tree`). A failure to record prints a warning and never changes the hook's exit code.
- `gin-workflow evidence check --commit <sha> [--json]` exits 0 and prints the newest matching record when a `verification.passed` event has the commit's tree hash and includes the `test` verify command; otherwise it exits 1 and says why (no record, or no `test` command in it).
- `review/SKILL.md` Reviewing step 3: the reviewer runs `gin-workflow evidence check --commit <reviewed commit>`, cites the record and skips rerunning the tests when it exits 0, and runs the tests when it exits 1.

### Top-model warning
- `routes resolve` adds `every track routes to <model>, the strongest <harness> model; check the plan's tiers` to `warnings` when the manifest has two or more tracks and every resolved route uses the last model of its harness catalog. The check runs in `W/routes.py` after the routes are known, so it covers both the orchestrator and the main-harness paths. The exit code does not change.

### Roadmap and epics
- Done during discuss: `gin-workflow-dura` and its `.planning/roadmap.md` entry carry the four moved items; this epic's entry drops them and names the move.

## User Stories

### US-1: Spend stops at a ceiling
As a maintainer, I want dispatch to stop once an epic spends well past its budget, so that a runaway epic cannot keep spending without my decision.

Acceptance criteria:
- With `usage.budget_usd: 10` and a stored epic cost of 12, `routes dispatch` exits 3 with `over_budget` and the manifest is unchanged.
- After raising `usage.budget_usd` to 20, the same command dispatches.
- With no `usage.budget_usd`, dispatch behaves as today.

### US-2: Budget status is visible and honest
As a maintainer, I want `usage collect` to report the budget status, including when it cannot be enforced, so that a missing price file never looks like a safe budget.

Acceptance criteria:
- Costs at 50%, 80%, and 120% of the budget produce `ok`, `warn`, and `stop`.
- A used model without a price produces `unenforceable`, names the model, and dispatch is never refused for it.
- A child bead's collect writes no budget block.

### US-3: Usage is fresh during execution
As a maintainer, I want usage collected after every worker returns, so that the budget check sees spend from the track still running.

Acceptance criteria:
- `execute/SKILL.md` runs `usage collect --bead <epic> --best-effort` after each worker result and handles dispatch exit 3 by asking the user.
- The execute stage chain is at most 12,000 characters (`tests/workflow_core/test_token_budget.py`).

### US-4: Reviewers reuse passing hook runs
As a maintainer, I want the reviewer to skip rerunning tests that a hook already passed on the same tree, so that each review does not pay for a full suite twice.

Acceptance criteria:
- A passing `pre-push` on a clean tree writes a `verification.passed` event with `HEAD^{tree}`.
- A failing hook, or a hook run with uncommitted tracked changes, writes no event.
- `evidence check --commit <sha>` exits 0 for a commit whose tree has a record including `test`, and 1 otherwise.
- `review/SKILL.md` tells the reviewer to run `evidence check` and to run the tests only on exit 1.

### US-5: Over-strong plans are flagged
As a plan author, I want `routes resolve` to warn when every track uses the strongest model, so that I notice a plan with no cheaper tiers.

Acceptance criteria:
- Two tracks both resolved to the last catalog model produce the warning.
- One track, or tracks with mixed models, produce no warning.

## Errors and compatibility

- `usage.budget_usd` is optional and additive; existing configs validate unchanged. Whether the schema needs a config version bump is decided in the plan from `W/schemas.py` and `docs/reference/config.md`.
- The `budget` block in `ai_usage` is additive; gin-console reads `ai_usage` fields it knows and ignores the rest.
- `verification.passed` is a new event type in the runtime log; readers that ignore unknown types are unaffected. The plan confirms that `state` and the event schema validation accept it.
- Exit 3 from `routes dispatch` is new. Before the skill change installs, a harness running the old `execute` text treats it as an unknown failure and stops, which is safe.
- The budget stop depends on time-span attribution, so it can be off; the 20% margin and the `warn` status come first. The user can always raise the budget.
- Hooks run inside track worktrees; the event goes to the runtime log the hook resolves for its repository root, and `evidence check` reads the same log. The plan confirms the path from a linked worktree.

## Testing

- `tests/workflow_core/test_usage*.py`: budget statuses at the thresholds, `unenforceable`, no budget block for a child bead.
- `routes dispatch` tests: exit 3 over budget, proceeds after raising the budget, unchanged with no budget or null cost.
- `tests/workflow_core/test_hooks.py`: event written on a clean passing run, not on failure or with uncommitted changes, warning when recording fails.
- `evidence check` tests: matching tree with `test`, matching tree without `test`, no record.
- `routes resolve` tests for the top-model warning.
- `tests/workflow_core/test_token_budget.py` keeps every stage chain within 12,000 characters.
- Full suite: `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests/test_all.py`.
