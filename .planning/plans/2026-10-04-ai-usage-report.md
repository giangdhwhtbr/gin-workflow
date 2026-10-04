# Plan: AI Usage Report

**Goal:** Show what AI-assisted work on each bead and epic cost and how well it went: tokens and estimated cost per model and per lifecycle stage, next to quality signals (reopens, bugs found later, review cycles, rejections, findings, gate waivers). Data is collected from the harness logs on the machine that did the work, summarized into the bead's metadata when the bead closes, and read back by `gin-workflow usage report` and the `/report` skill.

**Architecture:** Three new core modules, one per responsibility, following the flat `specs_*`/`team_*` pattern: `usage_logs.py` reads Claude Code and Codex logs into `UsageRecord`s; `usage_attribution.py` assigns each record to `(owner, stage)`; `usage.py` gathers quality signals and prices, builds the `ai_usage` summary, writes it with `bd`, and reads it back for reports. `usage_cli.py` is the `gin-workflow usage` command. The `execute` and `ship` skills call `collect`; a new `report` skill presents `usage report`.

**Tech Stack:** Python 3.12 stdlib plus the PyYAML the core already requires (`require_yaml`); `bd` CLI; `unittest`; Markdown skills; bash/PowerShell smoke tests.

**Spec:** `.planning/specs/2026-10-04-ai-usage-report-design.md` @ `fb85cbb` (workflow id `ai-usage-report`, `requirement_confirmed` recorded).

## Global Constraints

Copied verbatim from the spec:

- Adapters read only numeric and routing fields (`model`, token counts, `timestamp`, `cwd`, git branch, session id). They never read or copy prompt or response text.
- Bead metadata holds aggregates only: no session ids, log paths, or prompt text.
- Collection never blocks closing a bead or shipping.
- Users who never run `collect` or `report` see no change, apart from the `collect` call in the `execute` and `ship` skills.
- No new runtime dependency (standard-library Python only).

Repository constraints:
- Test command (repo root): `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests/test_all.py`. Baseline on `master` `967e07c`: `OK (skipped=3)` without the Playwright environment.
- Install smoke test: `bash tests/install_smoke_test.sh` exits 0 after every track. The PowerShell smoke test cannot run here (no `pwsh`); keep it consistent by reading.
- Core never names `gin-qa`. Skills ≤ 6,000 chars each.
- Git: commit/push on `feat/ai-usage-report` (worktree `.planning/worktrees/<epic>`); never commit to `master`.

## Deviations from the spec

None beyond the spec revision `fb85cbb`, which was made during planning with the user's decision (drop the dispatch source; prices in `usage-prices.yaml`; shared-worktree tracks attributed by time span and review intervals; unattributed usage stored on the epic). "No new runtime dependency" is kept: PyYAML is already required by the core.

## Model Guidance
- `default_model_class`: `standard_impl`
- `phase_guidance`: brainstorm `high_reasoning`; design `high_reasoning`; plan `standard_impl`; implement `standard_impl`; verify `standard_impl`; review `high_reasoning`; docs `cheap_simple`
- `override_rule`: Track 2 (attribution rules, time spans, overlaps) uses `high_reasoning`.

## Requirement Analysis
- Problem: nobody can see what AI work on a bead or epic cost, or relate it to rework (reopens, bugs, review rejections).
- Success: spec §Success criteria; the Validation list below.
- Constraints: local logs only, no infrastructure; never blocks closing; aggregates only in Beads.
- Non-goals (spec): per-member reports, Antigravity usage, OpenTelemetry/collectors, real-time tracking, budgets/alerts, sessions outside the repository.

## Approach Options
### Option 1: after-the-fact collection from local logs at bead close (selected in discuss)
- Pros: no infrastructure, offline, idempotent, backfills old beads.
- Cons: depends on harness log formats; adapters must tolerate change.
### Option 2: native OpenTelemetry from the harnesses
- Cons: needs a collector; sessions span beads, so attribution is weak.
### Recommended Approach
- Option 1, as confirmed.

## Scope
- In: `plugins/gin-workflow/src/scripts/workflow_core/usage*.py`, `workflow_core/cli.py`, `skills/report/`, `skills/execute/SKILL.md`, `skills/ship/SKILL.md`, `tests/workflow_core/test_usage*.py`, `tests/workflow_providers/test_harness_packaging.py`, `tests/install_smoke_test.*`, `README.md` (skill table and optional commands rows only).
- Out: worker dispatch layer, config schema, gates, `gin-qa`, version bump (done at ship), the wider docs refresh (separate discuss).

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Four tracks in a strict chain (records -> attribution -> summary/CLI -> skills); each consumes the previous track's interfaces.
```

## Tasks

### Track 1: Log adapters (`usage_logs.py`)
- **Dependencies**: none
- **Provider role**: `backend`
- **Reasoning**: `medium`
- **Estimated complexity**: medium
- **Files**:
  - Create: `plugins/gin-workflow/src/scripts/workflow_core/usage_logs.py`
  - Test: `tests/workflow_core/test_usage_logs.py`
- **Interfaces (produced)**:
  ```python
  @dataclass(frozen=True)
  class UsageRecord:
      ts: datetime            # timezone-aware UTC
      harness: str            # "claude_code" | "codex"
      model: str
      session_id: str
      cwd: str                # resolved absolute path
      branch: str             # "" when unknown
      input: int              # uncached input tokens
      output: int
      cache_read: int
      cache_write: int

  @dataclass(frozen=True)
  class SourceScan:
      records: tuple[UsageRecord, ...]
      status: str             # "ok" | "not_found"
      skipped_lines: int

  def parse_ts(value: str) -> datetime                       # "...Z" -> aware UTC
  def inside(path: str | Path, base: Path) -> bool           # base itself or below it
  def claude_code_records(repo: Path, root: Path | None = None) -> SourceScan
  def codex_records(repo: Path, root: Path | None = None) -> SourceScan
  ```
- **Steps**:
  1. Tests first, with fixture logs written into a temp dir:
     - Claude: project dirs `<slug>` and `<slug>--planning-worktrees-ep1` (slug = `re.sub(r"[^A-Za-z0-9]", "-", str(repo))`) plus an unrelated `<slug>-other` dir whose records have a `cwd` outside the repo (dropped). Lines: assistant message with `usage` (`input_tokens`, `output_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens`), the same `message.id`+`requestId` repeated (counted once), an `isSidechain: true` line in `<session>/subagents/agent-1.jsonl` (counted), a `model: "<synthetic>"` line (ignored), a user line containing the text `SECRET PROMPT` (ignored), a broken JSON line and an assistant line whose `usage.output_tokens` is a string (both counted in `skipped_lines`).
     - Codex: `sessions/2026/10/04/rollout-x.jsonl` with `session_meta` (`payload.id`, `payload.cwd`, `payload.git.branch`), `turn_context` (`payload.model`), three `event_msg`/`token_count` events where the second repeats the first's `info.total_token_usage.total_tokens` (not counted), `last_token_usage` with `input_tokens: 1000, cached_input_tokens: 800` (record `input == 200, cache_read == 800`), a `token_count` with `info: null` (ignored), a `token_count` before any `turn_context` (skipped), a broken line (skipped). A second rollout whose `cwd` is outside the repo yields nothing.
     - Missing roots give `status == "not_found"` and no records; `CLAUDE_CONFIG_DIR` (`<dir>/projects`) and `CODEX_HOME` (`<dir>/sessions`) are honoured when `root` is None.
     - No `UsageRecord` field and no `repr` of the scan contains `SECRET PROMPT`.
  2. Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests/workflow_core/test_usage_logs.py` → fails (module missing).
  3. Implement. Claude root: `root or Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude")) / "projects"`; scan dirs whose name equals the slug or starts with `slug + "-"`, `rglob("*.jsonl")` sorted. Read each line with `json.loads`; non-dict → ignore; `type == "assistant"` and `message.usage` is a dict → build a record from `message.model`, `timestamp`, `sessionId`, `cwd`, `gitBranch`; drop when `not inside(cwd, repo)`; dedupe on `(message.id, requestId)`; non-int token fields or a bad timestamp → `skipped_lines += 1`. Codex root: `root or Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "sessions"`; `rglob("rollout-*.jsonl")`; per file keep `session_id`, `cwd`, `branch` from `session_meta`, `model` (and `cwd` when present) from the latest `turn_context`; count a `token_count` only when `info.total_token_usage.total_tokens` differs from the previous one in that file; `input = input_tokens - cached_input_tokens`, `cache_read = cached_input_tokens`, `cache_write = cache_write_input_tokens or 0`, `output = output_tokens`. Never keep any other field.
  4. Run the test → passes; run the full suite and the smoke test → OK, exit 0. Commit `feat(usage): read token usage from Claude Code and Codex logs`.
- **Acceptance criteria**: tests above pass; full suite OK; smoke exit 0; independent review approved.

### Track 2: Attribution (`usage_attribution.py`)
- **Dependencies**: Track 1
- **Provider role**: `backend`
- **Reasoning**: `high`
- **Estimated complexity**: high
- **Files**:
  - Create: `plugins/gin-workflow/src/scripts/workflow_core/usage_attribution.py`
  - Test: `tests/workflow_core/test_usage_attribution.py`
- **Interfaces (consumed)**: `UsageRecord`, `inside`, `parse_ts` (Track 1).
- **Interfaces (produced)**:
  ```python
  STAGES = ("discuss", "plan", "orchestrate", "execute", "review", "verify", "ship", "quick")
  UNATTRIBUTED = "unattributed"

  @dataclass(frozen=True)
  class BeadSpan:
      bead: str
      parent: str | None
      start: datetime | None          # first claim; None = never claimed
      end: datetime | None            # closed_at; None = still open
      review: tuple[tuple[datetime, datetime], ...] = ()

  @dataclass(frozen=True)
  class Gate:
      ts: datetime
      workflow_id: str
      stage: str                      # one of STAGES

  @dataclass(frozen=True)
  class Worktree:
      path: Path
      branch: str

  def gates_from_events(events: Iterable[WorkflowEvent]) -> tuple[list[Gate], dict[str, str]]
      # (gates sorted by ts, workflow_id -> epic from orchestration.ready payload "epic")
  def worktrees(repo: Path) -> list[Worktree]          # `git worktree list --porcelain`, only paths under repo/.planning/worktrees
  def review_intervals(ledger: Mapping) -> tuple[tuple[datetime, datetime], ...]
  def attribute(records: Iterable[UsageRecord], *, repo: Path, spans: Mapping[str, BeadSpan],
                trees: Sequence[Worktree], gates: Sequence[Gate], epic_of: Mapping[str, str],
                collecting: str | None = None, now: datetime | None = None
                ) -> dict[tuple[str, str], list[UsageRecord]]   # (owner, stage) -> records
  ```
- **Steps**:
  1. Tests first (pure data, plus one real `git worktree add` for `worktrees()`):
     - `gates_from_events`: `requirement.confirmed`→discuss, `approval.recorded` with `payload.action == "plan_approved"` and `payload.decision.status == "approved"`→plan, other `approval.recorded`→ignored, `quick.completed`→quick, `orchestration.ready`→orchestrate (and fills `epic_of`), `verification.passed`→verify, `delivery.shipped`→ship, `worker.*`/`gate.waived`/`review.approved`→not gates.
     - Worktree rule: worktree `ep1` holds tracks `ep1.1` (09:00–10:00) and `ep1.2` (10:30–11:00): a record at 09:30 in the worktree → (`ep1.1`, execute); at 09:30 inside `ep1.1`'s review interval → (`ep1.1`, review); at 10:15 → (`ep1`, execute); spans overlapping at a record's time → (`ep1`, execute); a record with root `cwd` but `branch` equal to the worktree's branch → treated as in the worktree; an open bead (`end None`) holds records up to `now`.
     - Root rule: records before `requirement.confirmed` of `wf` → (epic of `wf`, discuss); a workflow without `orchestration.ready` → owner is the workflow id; records after the last gate with `collecting="ep1"` whose latest gate is verify → (`ep1`, ship); same without `collecting` → (`unattributed`, `""`).
     - `review_intervals`: `review-requested` 1 → `changes-requested`, `review-requested` 2 → `review-approved` gives two intervals; an unterminated request ends at `now`.
  2. Run → fails.
  3. Implement `attribute` in the spec's rule order: (1) worktree match by `inside(rec.cwd, tree.path)` or (`rec.branch` and `rec.branch == tree.branch`); candidates are spans whose `bead == tree.path.name` or `parent == tree.path.name`, have a `start`, and hold `rec.ts` in `[start, end or now]`; exactly one → that bead with `review` if `rec.ts` is in one of its intervals else `execute`; otherwise `(tree.path.name, "execute")`. (2) `inside(rec.cwd, repo)`: first gate with `ts > rec.ts` → `(epic_of.get(g.workflow_id, g.workflow_id), g.stage)`. (3) no later gate and `collecting` whose last gate (by ts, its workflow mapped through `epic_of`) has stage verify and `rec.ts` after it → `(collecting, "ship")`. (4) `(UNATTRIBUTED, "")`.
  4. Run → passes; full suite OK; smoke 0. Commit `feat(usage): attribute usage to beads and lifecycle stages`.
- **Acceptance criteria**: every rule and edge above tested; full suite OK; smoke 0; independent review approved.

### Track 3: Summary, collect, report, CLI (`usage.py`, `usage_cli.py`)
- **Dependencies**: Track 2
- **Provider role**: `backend`
- **Reasoning**: `medium`
- **Estimated complexity**: medium
- **Files**:
  - Create: `plugins/gin-workflow/src/scripts/workflow_core/usage.py`, `plugins/gin-workflow/src/scripts/workflow_core/usage_cli.py`
  - Modify: `plugins/gin-workflow/src/scripts/workflow_core/cli.py:66-80` (add `usage` to the accepted commands, the usage line, and the dispatch)
  - Test: `tests/workflow_core/test_usage.py`, `tests/workflow_core/test_usage_cli.py` (fake `bd` via `team_fixtures.fake_cli`)
- **Interfaces (consumed)**: Track 1 and Track 2; `workflow_core.events.WorkflowEventStore(path).read_all()`; `workflow_core.models.require_yaml()`.
- **Interfaces (produced)**:
  ```python
  class UsageError(Exception): ...                     # exit 2
  PRICES_FILE = ".agent-workflow/usage-prices.yaml"
  @dataclass(frozen=True)
  class Price: input: float; output: float; cache_read: float; cache_write: float   # USD per 1M tokens
  def load_prices(repo: Path) -> dict[str, Price]       # missing file -> {}; malformed -> UsageError
  def cost(record_totals: Mapping[str, int], price: Price | None) -> float | None
  def quality(repo: Path, bead: str, *, events: Sequence[WorkflowEvent]) -> dict
  def summarize(groups: Mapping[tuple[str, str], list[UsageRecord]], owners: set[str], prices: Mapping[str, Price],
                quality: dict, sources: dict[str, str], skipped: int, now: datetime) -> dict   # the ai_usage document
  def collect(repo: Path, bead: str, *, now: datetime | None = None, claude_root: Path | None = None,
              codex_root: Path | None = None) -> dict      # computes, writes metadata, returns the summary
  def report(repo: Path, *, bead: str | None = None, epic: str | None = None, since: date | None = None) -> dict
  ```
  `gin-workflow usage collect --bead ID [--best-effort] [--repository P] [--format text|json]`; `gin-workflow usage report [--bead ID | --epic ID | --since YYYY-MM-DD] [--repository P] [--format text|json]`. Exit 0 ok, 2 usage/real error; `--best-effort` turns every error into a `warning:` line on stderr and exit 0.
- **Steps**:
  1. Tests first:
     - `load_prices`: missing file → `{}`; valid YAML; a non-number price → `UsageError`.
     - `cost`: `(input*p.input + output*p.output + cache_read*p.cache_read + cache_write*p.cache_write)/1e6`, rounded to 4 decimals; `None` price → `None`.
     - `quality` with fake `bd`: `history <id> --json` (newest first; statuses `closed, open, closed, open` → 1 reopen), `dep list <id> --direction=up --type discovered-from --json` (one `bug`, one `task` → bugs 1), ledger `.planning/reviews/<id>/review.json` found in the repo root or in a worktree (`review-started` ×2 → cycles 2, `changes-requested` + `review-approval-invalidated` → rejections 2, findings by lower-cased severity), `gate.waived` events whose `workflow_id` is the bead → waivers; no ledger → cycles/rejections 0 and findings zeros.
     - `summarize`: exact document of the spec (`version`, `collected_at`, `models`, `stages`, `cost`, `unpriced`, `quality`, `sources`, `skipped_lines`, plus `unattributed` on epics); a priced and an unpriced model → `cost` sums priced only and `unpriced == ["m2"]`; `cost` is `null` when nothing is priced.
     - `collect` on a track: writes `bd update <id> --set-metadata ai_usage=<compact json>` (checked in `calls.log`); twice with the same inputs → identical argument; an epic (`issue_type == "epic"`) owns its own records plus every child's (children from `dep list <epic> --direction=up --type parent-child --json`), sums children's quality, and stores `unattributed` limited to its span.
     - `report`: from `bd list --all --json -n 0` rows whose `metadata.ai_usage` is a JSON string; `--epic` returns the epic and its children; beads without `ai_usage` are listed under `not_collected`; `--since` filters on `closed_at`.
     - CLI: `collect` with `bd` missing → exit 2; with `--best-effort` → exit 0 and a `warning:` line; `report --format json` shape; `gin-workflow` with no args lists `usage`.
     - Privacy: a fixture log line containing `SECRET PROMPT` never appears in the metadata argument or report output.
  2. Run → fails.
  3. Implement; spans come from `bd show <id> --json` (`parent`, `started_at`, `closed_at`, `issue_type`) and the earliest `started_at` across `bd history`; `bd` is called through a small `_bd(repo, argv)` like `team_beads._bd` (raise `UsageError` when missing or failing). Text output of `report`: one line per bead `<id>  <cost or ->  <title>`, then per-model and per-stage totals, `unpriced`, `unattributed`, `not collected`.
  4. Run → passes; full suite OK; smoke 0. Commit `feat(usage): collect usage summaries into bead metadata and report them`.
- **Acceptance criteria**: tests above pass; full suite OK; smoke 0; independent review approved.

### Track 4: Skills, packaging, README
- **Dependencies**: Track 3
- **Provider role**: `docs`
- **Reasoning**: `low`
- **Estimated complexity**: low
- **Files**:
  - Create: `plugins/gin-workflow/src/skills/report/SKILL.md`
  - Modify: `plugins/gin-workflow/src/skills/execute/SKILL.md:42` (step 4.2), `plugins/gin-workflow/src/skills/ship/SKILL.md:34` (step 7), `tests/workflow_providers/test_harness_packaging.py:110-135` (`REQUIRED_ARTIFACTS` adds `skills/report/SKILL.md`, `scripts/workflow_core/usage.py`, `usage_logs.py`, `usage_attribution.py`, `usage_cli.py`), `tests/install_smoke_test.sh:145` and `tests/install_smoke_test.ps1` (assert `skills/report/SKILL.md` exists in the built Claude and Codex dist), `README.md:14-31` (skill table row) and `README.md:84-108` (optional commands: `gin-workflow usage`, the prices file).
- **Steps**:
  1. Add the packaging and smoke assertions; run them → fail.
  2. `report/SKILL.md` (frontmatter `name: report`, a description ≤ 1,000 chars, the shared "Before you start" block, read-only): parse the user's scope (bead, epic, `--since`), run `gin-workflow usage report <scope> --format json`, present cost per model and per stage, quality signals, `unpriced` models, `unattributed` usage, and `not collected` beads (offer `gin-workflow usage collect --bead <id>` for those); say estimates come from `.agent-workflow/usage-prices.yaml` and that Antigravity usage is not measured. Never mutate anything else.
  3. execute step 4.2 becomes: run `gin-workflow usage collect --bead <id> --best-effort`, then close the track bead (unchanged text). ship step 7: before closing the parent bead, run `gin-workflow usage collect --bead <epic> --best-effort` (before the ledger cleanup).
  4. Run packaging tests, the full suite, and the smoke test → OK, exit 0. Commit `feat(usage): report skill and collect at bead close`.
- **Acceptance criteria**: skill within limits; packaging and smoke assertions pass on every harness layout; full suite OK; independent review approved.

## Integration
- **Branch**: `feat/ai-usage-report`
- **Merge strategy**: sequential

## Validation
- [ ] Full suite OK and smoke test exit 0 at the final track.
- [ ] Manual: in this repository, `gin-workflow usage collect --bead gin-workflow-9he.1` reads the real logs and writes `ai_usage` with Claude and Codex models (its ledger was cleaned up after ship, so review counts are zero, not an error); after `collect --bead gin-workflow-9he`, `gin-workflow usage report --epic gin-workflow-9he` lists the epic and its children, with the epic's root stages present.
- [ ] Manual: `--best-effort` with `CODEX_HOME` pointing to an empty dir prints `codex: not_found` in `sources`, exit 0.
- [ ] Spec success criteria 1–3 checked line by line.

## Notes
- The Parent Bead (epic) remains open until the human-confirmed merge; track beads close after tests and review pass.
- Version bump (`gin-workflow` minor) happens at ship, as in previous releases.
