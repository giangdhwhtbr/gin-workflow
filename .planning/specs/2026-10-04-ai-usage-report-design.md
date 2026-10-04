# AI Usage Report — Design

Date: 2026-10-04
Status: confirmed 2026-10-04

## Goal

Show what AI-assisted work on each bead and epic cost and how well it went: tokens and estimated cost per model and per lifecycle stage, next to quality signals (reopens, bugs found later, review cycles, rejections, findings, gate waivers). Data is collected from the harness logs on the machine that did the work, summarized into the bead's metadata when the bead closes, and read back by `gin-workflow usage report` and the `/report` skill.

## Decisions

| Topic | Decision |
|---|---|
| Purpose | Cost and quality per bead and per epic, to improve the process and the choice of models. No per-member view. |
| Sources | Claude Code session logs, Codex session logs, and workers that gin-workflow dispatches itself. Antigravity session logs are out of scope. |
| Collection | After the fact, from local logs, at bead close. No telemetry infrastructure. |
| Attribution | Track bead: its worktree or branch. Repository root: the workflow of the next gate event, labelled with that stage. Anything else: `unattributed`. |
| Storage | A summary in the bead's metadata (`ai_usage`), synced with the bead. Raw records are never stored. |
| Cost | Estimated from a price table in the project config. A model without a price has no cost; it is never guessed. |
| Export | `usage report --format json`. Pushing to a metric collector is out of scope. |

## Global Constraints

- Adapters read only numeric and routing fields (`model`, token counts, `timestamp`, `cwd`, git branch, session id). They never read or copy prompt or response text.
- Bead metadata holds aggregates only: no session ids, log paths, or prompt text.
- Collection never blocks closing a bead or shipping.
- Users who never run `collect` or `report` see no change, apart from the `collect` call in the `execute` and `ship` skills.
- No new runtime dependency (standard-library Python only).

## Design

### 1. Usage records (`workflow_core/usage/`)

Every adapter yields the same record:

```python
UsageRecord(ts, harness, model, session_id, cwd, branch,
            input, output, cache_read, cache_write)
```

- `claude_code`: `~/.claude/projects/<slug>/*.jsonl` for every slug that starts with the repository's slug (sessions started inside a worktree get their own slug). One record per assistant message with `message.usage`; sidechain (subagent) messages included. Duplicate message ids are counted once.
- `codex`: `~/.codex/sessions/**/rollout-*.jsonl` whose session `cwd` is the repository or one of its worktrees; one record per `token_count` event (per-turn usage, not the running total).
- `dispatch`: when gin-workflow dispatches a worker or reviewer and the result reports usage, it appends a `worker.usage` event to `.agent-workflow/runtime/events.jsonl` (`task_id`, `harness`, `model`, the four token counts). The adapter reads those events.

`CLAUDE_CONFIG_DIR` and `CODEX_HOME` override the default log roots. A malformed or unknown line is skipped and counted in `skipped_lines`. A missing log root is reported as `not_found` for that source.

### 2. Attribution

Applied in order:

1. `cwd` inside `.planning/worktrees/<bead>` or `branch` equal to that worktree's branch → the bead, stage `execute`.
2. `dispatch` record with a `task_id` → that bead, stage `review` when the worker was a reviewer, else `execute`.
3. `cwd` at the repository root → the workflow of the first gate event in `events.jsonl` after the record's timestamp. The stage follows from that event: `requirement.confirmed` → `discuss`, `plan.approved` → `plan`, `orchestration.ready` → `orchestrate`, `verification.passed` → `verify`, `delivery.shipped` → `ship`.
4. `cwd` at the repository root after the last gate event, while collecting an epic whose latest gate event is `verification.passed` → that epic, stage `ship` (the epic's `delivery.shipped` does not exist yet when ship collects).
5. Otherwise `unattributed`.

Records outside the bead's time span (first claim to close) are not attributed to it by rule 1.

### 3. Quality signals

From Beads and the review ledger, at collect time (ledgers are removed after ship):

- `reopens`: status changes from closed to open in `bd history <bead>`.
- `bugs`: beads of type `bug` with a `discovered-from` dependency on the bead.
- `review_cycles`, `rejections`, `findings` by severity: from the bead's review ledger, when one exists.
- `waivers`: `gate.waived` events for the bead's workflow.

### 4. Prices

Optional `usage.prices` in `.agent-workflow/config.yaml`, USD per million tokens:

```yaml
usage:
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
             "findings": {"critical": 0, "important": 0, "minor": 0}, "waivers": 0},
 "sources": {"claude_code": "ok", "codex": "not_found", "dispatch": "ok"},
 "skipped_lines": 0}
```

`report --format json` prints a list of these summaries, each with `bead`, `title`, and `type`, plus totals and the `unattributed` usage for the period.

### 6. Skills

- `execute` (close step) and `ship` (close out): run `gin-workflow usage collect --bead <id> --best-effort` before `bd close`.
- New `report` skill (`/gin-workflow:report`): runs `usage report` with the user's scope and presents it: cost per model and stage, quality signals, unpriced models, and `unattributed` usage.

## Testing

- Adapters: fixture logs for Claude Code (sidechain, cache tokens, duplicate message ids, a worktree slug) and Codex (per-turn `token_count`), each with malformed lines; check records and `skipped_lines`; missing roots give `not_found`.
- Attribution: worktree path, branch, dispatch `task_id`, root records mapped to the next gate event and its stage, records outside the bead's time span, `unattributed`.
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
- Antigravity session logs.
- OpenTelemetry or pushing to a metric collector.
- Real-time tracking or budgets and alerts.
- Usage of ad-hoc scripts that call providers outside gin-workflow dispatch.
