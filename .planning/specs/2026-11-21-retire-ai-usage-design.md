# Retire AI usage tracking

Epic: gin-workflow-wkwb
Kind: technical
Status: confirmed by the user on 2026-11-21.

## Goal and scope

gin-workflow stops measuring AI usage. `gin usage collect|report`, the price catalog, the per-epic budget, the `report` skill and every usage step in the lifecycle skills are removed. The next release (assumed 3.4.0) ships without them.

Why (measured on `master` `103dcbbe`, 2026-11-21, decision taken while discussing `gin-workflow-04wv`):

- `gin usage collect` takes about 36 s for one bead and 57 s for a 6-track epic on the build machine: Claude Code logs about 9 s, Codex logs about 5 s, and about 20 s in `usage_logs.inside()`, called about 400k times. `execute` collects the epic after every worker result and each track before its close, and `ship` collects the epic once or twice, so a 6-track epic spends about 10 minutes waiting on it.
- The numbers miss most of the work. `gin-workflow-u5mt` (6 tracks) stored $0.48 with only the `discuss` stage; collected again it gives $2.09 with `discuss`, `plan` and `orchestrate`, still no `execute` or `ship`. `/quick` records `quick.completed` under `default-workflow` (42 of 54 events), so a `/quick` bead such as `gin-workflow-jqwb` collects 0 tokens.
- The code is 953 lines of source and 1448 lines of tests.

gin-console can compute the quality signals itself from files it already reads (reopens from `interactions.jsonl`, bugs from `discovered-from` dependencies, waivers from `events.jsonl`); that work is `gin-console-5c4`. The parent epic `gin-harness-1u3` orders the two.

In scope:

- Delete `workflow_core/usage.py`, `usage_cli.py`, `usage_logs.py`, `usage_attribution.py` and `usage_prices_default.yaml`.
- Remove the `gin usage` command and the budget check of `gin routes dispatch`.
- Keep `usage:` valid in config schema 2.11, ignored, with a warning.
- Skills, installers and docs follow.

Out of scope:

- gin-console: `gin-console-5c4` removes AI usage from Reports.
- The `ai_usage` metadata already stored on beads stays; nothing writes it any more.
- No replacement for the quality signals (reopens, bugs, review cycles, rejections, findings, waivers) in gin-workflow.
- No config schema bump and no migration.

## Approach

**A. CLI and modules.** Delete the four `usage*` modules and the default price catalog. `cli.py` drops `usage` from `TOP_COMMANDS` and its dispatch, so `gin usage ...` fails like any unknown command (exit 2 with the usage line). `close_guard._has_review_ledger` keeps working: `Worktree` and `worktrees()` move unchanged from `usage_attribution.py` to `checkout.py`, beside `main_checkout()`. Apart from `routes.py` (B), nothing else imports the deleted modules.

**B. Dispatch.** `routes.dispatch` drops the `usage.over_budget` call and the `warning: budget not checked` path, so exit 3 (`over_budget`) no longer exists. Every other exit code and the JSON result are unchanged.

**C. Config.** `schemas.py` keeps `usage: {budget_usd}` so an existing config still validates. No code reads it. `gin state --format json` adds to `warnings`, and `gin setup doctor` adds to its actions, the line `usage is ignored since gin 3.4.0; delete it from .agent-workflow/config.yaml` when the effective config holds `usage`, as doctor already does for `model_tiers` and `notifications`.

**D. Skills.**

- `execute`: step 3.3 loses the collect and the `over_budget` sentence; step 4.2 closes the track without collecting.
- `ship`: the merge step and the close-out step lose `gin usage collect`. Ledger cleanup, `gin evidence run` and the dependent comments are unchanged.
- `milestone-close`: drops the `gin usage report --milestone` source and the `cost_per_epic` and `rework` metrics, from the computation, the `Metrics:` line and the summary sentence. The other metrics keep their order.
- The `report` skill is deleted. `install.sh` and `install.ps1` drop it from the OpenCode rename list. A global install rebuilds its folders from scratch, so no stale copy stays there. A project install (`--project`) removes `.opencode/skills/gin-report`, and removes `skills/report` under `.claude`, `.agents` and `.codex` only when its `SKILL.md` is gin's (it contains `Report AI usage`). gin-qa's `report` skill is untouched.

**E. Docs.** Delete `docs/guides/usage-report.md` and `.vi.md` and their `mkdocs.yml` nav entries. Remove usage tracking from `docs/reference/cli.md` (the `gin usage` section and the dispatch exit 3), `docs/reference/config.md` (`usage.budget_usd` becomes ignored), `docs/reference/skills.md`, `docs/concepts/lifecycle.md`, `state-model.md`, `architecture.md` (the usage flow diagram), `docs/guides/ai-strategy.md` and `.vi.md`, `docs/guides/qa.md` and `.vi.md`, `docs/roles.md` and `.vi.md`, and `README.md`. `docs/changelog.md` gets one entry naming what was removed and that `usage:` is ignored.

## Risks and rollback

- **Lost data.** Existing `ai_usage` metadata stays readable; only new beads go without it. gin-console Reports keep showing old figures until `gin-console-5c4` ships, and its data coverage lists new beads with a `gin usage collect` hint that no longer works. Mitigation: ship `gin-console-5c4` first or together (`gin-harness-1u3`).
- **Hidden imports.** A module other than `close_guard.py` importing the deleted modules would break at import time. Mitigation: the full suite and a grep for `usage`, `usage_logs` and `usage_attribution` in the plan's final track.
- **Stale installed skill.** An upgrade that kept an old `report` skill would call a removed command. Mitigation: the installer removal in D, covered by the packaging test.
- **Rollback.** `git revert` of the merge restores everything; no config or stored data changed.

## Testing

- Delete `tests/workflow_core/test_usage.py`, `test_usage_attribution.py`, `test_usage_cli.py`, `test_usage_logs.py` and `test_routes_budget.py`; the new `test_usage_retired.py` holds the command and dispatch cases below. `test_token_budget.py` measures prompt size and stays; its ship-order assertion drops `usage collect`. `test_skill_routing.py`, `test_tasks.py` and `test_no_verify_stage.py` drop their usage pins.
- `test_harness_packaging.py` and the install smoke tests: drop the pins of the deleted skill and modules; assert no harness layout ships a `report` or `gin-report` skill of the gin plugin, and that a project install removes gin's stale copy and keeps gin-qa's `report`.
- New or updated tests:
  - `gin usage collect --bead x` exits 2 as an unknown command.
  - A config with `usage: {budget_usd: 5}` validates; `gin state --format json` and `gin setup doctor` each show the ignored-key line once; without `usage` neither shows it.
  - `gin routes dispatch` returns the route with exit 0, without calling `bd`, when `usage.budget_usd` is 1 and the epic's stored `ai_usage` cost is 5.
  - `close_guard` still finds a review ledger in a linked worktree through `checkout.worktrees()`.
- `gin docs check` passes; `grep -rnE 'gin usage|ai_usage|budget_usd|usage-prices' plugins/*/src docs README.md install.sh install.ps1` finds matches only in `docs/changelog.md` and in `schemas.py`, which keeps the ignored key.
- The full suite passes once, at the push of the merged epic.

## Open Technical Questions
