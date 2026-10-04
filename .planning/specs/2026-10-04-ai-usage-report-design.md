# AI Usage Report — Design

Date: 2026-10-04
Status: confirmed 2026-10-04

## Goal

Show what AI-assisted work on each bead and epic cost and how well it went: tokens and estimated cost per model and per lifecycle stage, next to quality signals (reopens, bugs found later, review cycles, rejections, findings, gate waivers). Data is collected from the harness logs on the machine that did the work, summarized into the bead's metadata when the bead closes, and read back by `gin-workflow usage report` and the `/report` skill.

## Decisions

| Topic | Decision |
|---|---|
| Purpose | Cost and quality per bead and per epic, to improve the process and the choice of models. No per-member view. |
| Sources | Claude Code session logs and Codex session logs (which include `codex exec` reviewers). Antigravity is not measured: `agy` prints no token counts and its own logs are binary. The report names the sources it read. |
| Collection | After the fact, from local logs, at bead close. No telemetry infrastructure. |
| Attribution | Track bead: its worktree or branch. Repository root: the workflow of the next gate event, labelled with that stage. Anything else: `unattributed`. |
| Storage | A summary in the bead's metadata (`ai_usage`), synced with the bead. Raw records are never stored. |
| Cost | Estimated from a tracked price list, `.agent-workflow/usage-prices.yaml` (the portable config holds no concrete model names). A model without a price has no cost; it is never guessed. |
| Export | `usage report --format json`. Pushing to a metric collector is out of scope. |

## Global Constraints

- Adapters read only numeric and routing fields (`model`, token counts, `timestamp`, `cwd`, git branch, session id). They never read or copy prompt or response text.
- Bead metadata holds aggregates only: no session ids, log paths, or prompt text.
- Collection never blocks closing a bead or shipping.
- Users who never run `collect` or `report` see no change, apart from the `collect` call in the `execute` and `ship` skills.
- No new runtime dependency (standard-library Python only).

## Design

### 1. Usage records (`workflow_core/usage_logs.py`)

Every adapter yields the same record:

```python
UsageRecord(ts, harness, model, session_id, cwd, branch,
            input, output, cache_read, cache_write)
```

- `claude_code`: `~/.claude/projects/<slug>/**/*.jsonl` for every slug that starts with the repository's slug (sessions started inside a worktree get their own slug); records whose `cwd` is outside the repository are dropped. One record per assistant message with `message.usage`; sidechain (subagent) messages included. Duplicate message ids are counted once.
- `codex`: `~/.codex/sessions/**/rollout-*.jsonl` whose session `cwd` is the repository or one of its worktrees; one record per `token_count` event (per-turn usage, not the running total).

Codex counts cached tokens inside `input_tokens`; the adapter subtracts them so `input` is uncached input for every harness. A Codex `token_count` event is counted only when its running total changes, so repeated events are not counted twice.

`CLAUDE_CONFIG_DIR` and `CODEX_HOME` override the default log roots. A malformed or unknown line is skipped and counted in `skipped_lines`. A missing log root is reported as `not_found` for that source.

### 2. Attribution

Applied in order:

1. `cwd` inside a worktree under `.planning/worktrees/`, or `branch` equal to that worktree's branch → the track bead whose time span (first claim to close) holds the record, among the beads named by the worktree or whose parent it names; stage `review` inside the bead's review intervals from its ledger (`review-requested` to the next `changes-requested`, `review-approved`, or `review-approval-invalidated`), else `execute`. No such bead, or more than one → the bead the worktree is named after, stage `execute`. A worktree removed after ship is no longer listed by git; a path under `.planning/worktrees/<bead>` still names that bead.
2. `cwd` at the repository root → the workflow of the first gate event in `events.jsonl` after the record's timestamp. The workflow maps to its epic through `orchestration.ready`. The stage follows from that event: `requirement.confirmed` → `discuss`, `approval.recorded` for `plan_approved` → `plan`, `quick.completed` → `quick`, `orchestration.ready` → `orchestrate`, `verification.passed` → `verify`, `delivery.shipped` → `ship`.
3. `cwd` at the repository root after the last gate event in the repository, when that event is the collecting epic's `verification.passed` → that epic, stage `ship`, up to the epic's close (the epic's `delivery.shipped` does not exist yet when ship collects).
4. Otherwise `unattributed`. Collecting an epic also stores the `unattributed` usage inside the epic's span (its first gate event to its close, or now while it is open), so the report shows it without reading logs.

### 3. Quality signals

From Beads and the review ledger, at collect time (ledgers are removed after ship):

- `reopens`: status changes from closed to open in `bd history <bead>`.
- `bugs`: beads of type `bug` with a `discovered-from` dependency on the bead.
- `review_cycles`, `rejections`, `findings` by severity: from the bead's review ledger, when one exists.
- `waivers`: `gate.waived` events for the bead's workflow.

### 4. Prices

Optional `.agent-workflow/usage-prices.yaml`, tracked so the team shares one list, USD per million tokens:

```yaml
prices:
  claude-opus-5-5: {input: 15, output: 75, cache_read: 1.5, cache_write: 18.75}
```

A record whose model has no price gets `cost: null`; the summary lists the model under `unpriced`.

### 5. CLI

- `gin-workflow usage collect --bead <id> [--best-effort]` recomputes the bead's summary from scratch and writes it with `bd update <id> --set-metadata`. For an epic it also aggregates its children and its root-level stages. Running it again gives the same result. Exit 0 on success, 2 on a real error; with `--best-effort` it prints a warning and exits 0.
- `gin-workflow usage report [--bead <id> | --epic <id> | --since <date>] [--format text|json]` reads the summaries from bead metadata; it never reads logs. Beads without a summary are listed as `not collected`.

Summary written to `ai_usage`:

```json
{"version": 1, "collected_at": "2026-10-04T15:00:00Z",
 "models": {"claude-opus-5-5": {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "cost": 0.0}},
 "stages": {"execute": {"cost": 0.0}, "review": {"cost": 0.0}},
 "cost": 0.0, "unpriced": [],
 "quality": {"reopens": 0, "bugs": 0, "review_cycles": 0, "rejections": 0,
             "findings": {"critical": 0, "important": 0, "minor": 0, "suggestion": 0}, "waivers": 0},
 "sources": {"claude_code": "ok", "codex": "not_found"},
 "skipped_lines": 0}
```

`report --format json` prints a list of these summaries, each with `bead`, `title`, and `type`, plus totals and the `unattributed` usage stored in the epics of the period.

### 6. Skills

- `execute` (close step) and `ship` (close out): run `gin-workflow usage collect --bead <id> --best-effort` before `bd close`.
- New `report` skill (`/gin-workflow:report`): runs `usage report` with the user's scope and presents it: cost per model and stage, quality signals, unpriced models, and `unattributed` usage.

## Testing

- Adapters: fixture logs for Claude Code (sidechain, cache tokens, duplicate message ids, a worktree slug) and Codex (per-turn `token_count`, repeated totals, cached input), each with malformed lines; check records and `skipped_lines`; missing roots give `not_found`.
- Attribution: worktree path, branch, review intervals, overlapping track spans, root records mapped to the next gate event and its stage, records outside the bead's time span, `unattributed`.
- Cost: priced, unpriced, cache tokens priced separately.
- Quality: fake `bd` output for reopens and `discovered-from` bugs; sample review ledger; waiver events.
- CLI: `collect` twice gives identical metadata; `--best-effort` exits 0 on every failure; `report --format json` shape; `not collected` beads.
- Privacy: fixture logs with prompt text; the text appears nowhere in the output or metadata.
- Packaging: `execute` and `ship` call `collect`; the `report` skill ships on every harness.

## Success criteria

- Closing a track bead through `execute` writes `ai_usage` with per-model tokens, cost, and quality signals.
- `/gin-workflow:report --epic <id>` shows the epic's cost per model and per stage, including discuss and plan.
- Missing logs, unknown formats, and unpriced models are visible in the report, never silently counted as zero.

## Non-goals

- Per-member reports.
- Antigravity usage (`agy` reports no tokens).
- OpenTelemetry or pushing to a metric collector.
- Real-time tracking or budgets and alerts.
- Usage of sessions whose working directory is outside the repository and its worktrees.
