# AI usage report

`gin usage` reports what the AI work on a bead or an epic cost and how it went. It reads the harness logs already on the machine that did the work and shows tokens and estimated cost per model and per lifecycle stage, next to quality signals. It reads only local files and needs Beads.

## What is measured

| Source | Read from | Notes |
|---|---|---|
| Claude Code | `~/.claude/projects/<repo slug>*/**/*.jsonl` | includes subagents; each message counted once |
| Codex | `~/.codex/sessions/**/rollout-*.jsonl` | per-turn usage |
| Antigravity | not measured | no reader exists |
| OpenCode | not measured | no reader exists |

`CLAUDE_CONFIG_DIR` and `CODEX_HOME` override the log locations. Only numbers and routing fields are read (model, token counts, time, working directory, branch); prompt and response text is never read or stored. A missing log directory shows as `not_found`, and unreadable lines are counted in `skipped_lines`.

Quality signals come from Beads and the review ledger:

- `reopens`: times the bead went from closed back to open;
- `bugs`: bugs filed with a `discovered-from` link to the bead;
- `review_cycles`, `rejections`, and `findings` by severity, from the bead's review ledger;
- `waivers`: gates waived in the bead's workflow.

## When it runs

`execute` runs `gin usage collect --bead <epic> --best-effort` after each worker returns and `--bead <track>` before closing each track, and `ship` runs it for the epic before closing it. You can run it yourself at any time, from the main checkout or any of its worktrees; it recomputes the summary from scratch, so running it twice gives the same result. With `--best-effort` an error becomes a warning and never blocks closing a bead.

## How usage is attributed

1. Work inside a worktree of the repository goes to the track bead whose claim-to-close span contains it: stage `review` while the bead's review ledger shows a review in progress, `execute` otherwise.
2. Work at the repository root goes to the workflow of the next gate recorded after it, with that gate's stage: `discuss` before `requirement-confirmed`, `plan` before `plan-approved`, `orchestrate`, `verify`, `quick`, or `ship`.
3. When you collect an epic, root work after its last track closes and before the epic closes counts as that epic's `ship`, as long as no other workflow recorded a gate after that track closed.
4. Anything else is `unattributed`; collecting an epic also stores the unattributed usage inside its span so the report shows it.

The summary is stored in the bead's metadata as `ai_usage` (aggregates only), and an epic's summary also aggregates its tracks.

## Prices

Costs are estimates in USD per million tokens. The plugin ships a catalog, `workflow_core/usage_prices_default.yaml`, checked on 2026-11-01 against the vendor pages named in each row. It uses standard-tier prices, Anthropic 5-minute cache writes, OpenAI cache writes at 1.25x input, and Google cache writes at 0 (Google bills cache storage per hour).

`.agent-workflow/usage-prices.yaml` overrides a catalog row by model id and adds models the catalog lacks. Committing the file so the team shares one list is a team convention, not tool behavior:

```yaml
prices:
  <model id>: {input: 3.0, output: 15.0, cache_read: 0.3, cache_write: 3.75}
```

A model id with no exact row takes the longest row whose key it extends with `-`: `claude-sonnet-4-5-20250929` prices as `claude-sonnet-4-5`. No other fuzzy matching applies.

Each model in the report carries a `price_source`: `default` (catalog), `repo` (your file) or `none`. A model with `none` is never guessed: its cost shows `-` and it is listed under `unpriced`.

Prices change and the catalog is a convenience, not a billing source.

## Budget

Set `usage.budget_usd` in `.agent-workflow/config.yaml` to give each epic a spend ceiling in USD:

```yaml
usage:
  budget_usd: 25
```

`usage collect --bead <epic>` then stores `budget: {budget_usd, cost, status}` in the epic's summary and prints the status:

| Status | When |
|---|---|
| `ok` | cost below 80% of the budget |
| `warn` | cost from 80% up to 120% |
| `stop` | cost at or above 120%; the margin covers the error of time-span attribution |
| `unenforceable` | a used model has no price; the output names the models and `.agent-workflow/usage-prices.yaml` |

A track's summary has no budget block; the budget belongs to the epic.

At `stop`, `gin routes dispatch` for the epic prints `{"status": "over_budget", ...}`, dispatches nothing, and exits 3. Raising `usage.budget_usd` lets the next dispatch proceed without another collect. `unenforceable` never stops a dispatch.

## Reading it

```bash
gin usage report --epic <epic>
gin usage report --since 2026-10-01 --format json
```

Or ask `/report`. The text report lists each bead's cost, totals per model (tokens by type) and per stage, unpriced models, unattributed usage, and closed beads that were never collected (`not collected`). `--format json` returns the full summaries for your own tooling.

## Limits

- Antigravity and OpenCode work is not counted.
- Two sessions working at the repository root at the same time cannot be told apart: root work is attributed to the next gate, even if the other session recorded it.
- The `review` stage covers the whole time a review was open, including time the implementer spent on something else while waiting.
- Sessions whose working directory is outside the repository and its worktrees are not counted.

See [`gin usage`](../reference/cli.md#gin-usage) for options and exit codes.
