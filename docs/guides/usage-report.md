# AI Usage Report

What did the AI work on a bead or an epic cost, and how well did it go? `gin-workflow usage` answers from the harness logs already on the machine that did the work: tokens and estimated cost per model and per lifecycle stage, next to quality signals. No telemetry service is involved.

## What is measured

| Source | Read from | Notes |
|---|---|---|
| Claude Code | `~/.claude/projects/<repo slug>*/**/*.jsonl` | includes subagents; each message counted once |
| Codex | `~/.codex/sessions/**/rollout-*.jsonl` | includes `codex exec` reviewers; per-turn usage |
| Antigravity | not measured | `agy` reports no token counts |

`CLAUDE_CONFIG_DIR` and `CODEX_HOME` override the log locations. Only numbers and routing fields are read (model, token counts, time, working directory, branch); prompt and response text is never read or stored. A missing log directory shows as `not_found`, and unreadable lines are counted in `skipped_lines`.

Quality signals come from Beads and the review ledger:

- `reopens`: times the bead went from closed back to open;
- `bugs`: bugs filed with a `discovered-from` link to the bead;
- `review_cycles`, `rejections`, and `findings` by severity, from the bead's review ledger;
- `waivers`: gates waived in the bead's workflow.

## When it runs

`execute` runs `gin-workflow usage collect --bead <track> --best-effort` before closing each track, and `ship` runs it for the epic before closing it. You can run it yourself at any time, from the main checkout or any of its worktrees; it recomputes the summary from scratch, so running it twice gives the same result. With `--best-effort` an error becomes a warning and never blocks closing a bead.

## How usage is attributed

1. Work inside a worktree of the repository goes to the track bead whose claim-to-close span contains it: stage `review` while the bead's review ledger shows a review in progress, `execute` otherwise.
2. Work at the repository root goes to the workflow of the next gate recorded after it, with that gate's stage: `discuss` before `requirement-confirmed`, `plan` before `plan-approved`, `orchestrate`, `verify`, `quick`, or `ship`.
3. Root work after an epic's `verification-passed` and before the epic closes counts as that epic's `ship`.
4. Anything else is `unattributed`; collecting an epic also stores the unattributed usage inside its span so the report shows it.

The summary is stored in the bead's metadata as `ai_usage` (aggregates only), and an epic's summary also aggregates its tracks.

## Prices

Costs are estimates from `.agent-workflow/usage-prices.yaml`, which you track so the team shares one list (USD per million tokens):

```yaml
prices:
  <model id>: {input: 3.0, output: 15.0, cache_read: 0.3, cache_write: 3.75}
```

A model without a price is never guessed: its cost shows `-` and it is listed under `unpriced`.

## Reading it

```bash
gin-workflow usage report --epic <epic>
gin-workflow usage report --since 2026-10-01 --format json
```

Or ask `/report`. The text report lists each bead's cost, totals per model (tokens by type) and per stage, unpriced models, unattributed usage, and closed beads that were never collected (`not collected`). `--format json` returns the full summaries for your own tooling.

## Limits

- Antigravity work is not counted.
- Two sessions working at the repository root at the same time cannot be told apart: root work is attributed to the next gate, even if the other session recorded it.
- The `review` stage covers the whole time a review was open, including time the implementer spent on something else while waiting.
- Sessions whose working directory is outside the repository and its worktrees are not counted.

See [`gin-workflow usage`](../reference/cli.md#gin-workflow-usage) for options and exit codes.
