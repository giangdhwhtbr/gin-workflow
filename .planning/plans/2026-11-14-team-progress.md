# Plan: Progress views and usage totals for a team

Spec: .planning/specs/2026-11-14-team-progress-design.md
Epic: gin-workflow-team-progress

## Objective

`/gin:progress` adds a milestone section, grouping by area or repository, spec status, pending approvals, and QA state, in text; a new `gin team pending` lists open gate pull requests with what they still need; `gin usage report` marks partial totals with reasons.

**Goal** (spec): `/gin:progress` shows a team the milestone forecast, pending approvals, spec status, QA state, and grouping by area or repository, in text; `gin usage report` says when an epic's usage total is partial and why.

**Architecture**:
- A new module `workflow_core/team_pending.py` finds candidate branches (remote `spec/*` and `plan/*` heads, track and feature branches derived from track beads), looks each up with `team_host.pr_for_branch`, and checks gate pull requests with `team.verify_gate`. `team_cli.py` gains `pending`.
- `workflow_core/usage.py` `report` gains `partial` and `partial_reasons`; `usage_cli.py` prints them.
- Skill text carries the rest: `progress` gets the milestone, grouping, spec, approvals, and QA sections; `qa-track` gets `## QA state`; `report` shows the partial marker.

**Tech Stack**: Python 3 standard library; unittest/pytest (`tests/workflow_core/test_team_pending.py` new, `test_usage.py`, `test_usage_cli.py`, `test_skill_routing.py`, `test_token_budget.py`, `test_docs_coverage.py`, `tests/gin_qa/test_packaging.py`); host fakes `fake_cli`, `gh_pr`, `gitea_pr`, and `make_team_repo` in `tests/workflow_core/team_fixtures.py`; `gin docs check`.

**Global Constraints** (spec "Errors and compatibility", verbatim):
- Solo projects: progress prints no approvals section; everything else works from the Beads backend; with the markdown backend, the milestone and QA sections say they are unavailable in one sentence each.
- Host failures never stop progress; they become `approvals unknown: <cause>`.
- `gin team pending` makes one `git ls-remote` and one host call per candidate branch; on Gitea, `pr_for_branch` scans the newest 500 pull requests.
- `gin usage report` JSON gains two keys; consumers that ignore unknown keys (gin-console) are unaffected.
- No gin-qa text outside `skills/qa-track/SKILL.md`.

## Route Rubric
- Choose the weakest model that can do the work.
- Raise the model for broad context or design judgement.
- Raise the effort for intrinsic difficulty: intricate logic, many edge cases, or long chains of steps.

| Kind of work | Model | Effort |
|---|---|---|
| Mechanical edits, documentation, boilerplate | weakest | `low` |
| Bounded implementation with a clear spec | middle | `medium` |
| Cross-module change, security, migration, concurrency | strongest | `high` |

Unclear requirements never raise the model or effort.

## Requirement Analysis
- Problem statement: progress shows task status but no milestone, approvals, spec, QA, or grouping views; usage totals hide what they miss.
- Success criteria: spec R1 to R9 and US-1 to US-5, as tests (code) or checked text (skills, docs); existing tests pass; budgets hold.
- Constraints: Global Constraints above; `team.py`, `team_beads.py`, and `specs_trace.py` contain no host names (use `hosts.adapter` and `team_host`); tests use `fake_cli` host fakes; `tests/workflow_core/test_usage.py` pins the exact `bd` calls of `collect` (report is not pinned the same way, check before changing).
- Non-goals: pull request age; merging usage across machines; gin-console changes; the forecast computation.

## Approach Options
### Option 1: existing JSON plus one new command, a report marker, and skill sections (confirmed)
- Summary: as the Architecture above.
- Pros: each piece lives where its data already is; little new code.
- Cons: the progress skill orchestrates several commands.

### Option 2: one `gin progress --json` aggregator
- Summary: Python gathers every section in one call.
- Pros: one call, easy to test.
- Cons: core may not name gin-qa, so QA still needs the skill; much more code; rejected in `/discuss`.

### Recommended Approach
- Selected option: Option 1 (confirmed in `/discuss` on 2026-11-14).
- Rationale: smallest change that covers every section.

## Scope
- In scope: R1 to R9.
- Out of scope: see Non-goals.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Track 3's skill text calls Track 1's command and Track 2's marker; Tracks 1 and 2 both edit docs/reference/cli.md. One lane.
```

## Tasks

`S` is `plugins/gin-workflow/src/scripts/workflow_core`.

### Track 1: `gin team pending`
- **Dependencies**: none
- **Files**:
  - Create `plugins/gin-workflow/src/scripts/workflow_core/team_pending.py`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team_cli.py:21-49` (parser: `pending`), `:182-194` and the command dispatch (call `team_pending.pending`, text and JSON output)
  - Modify `docs/reference/cli.md` (`gin team` section: `pending`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team.py` (`check_approval`, `verify_gate`)
  - Test `tests/workflow_core/test_team_pending.py` (new)
  - Test `tests/workflow_core/test_team_gates.py`
- **Provider role**: `backend`
- **Model:** `opus`
- **Effort:** `medium`
- **Why:** a new command across team policy, epic kinds, host adapters, git, and Beads; broad context, bounded logic.
- **Interfaces**:
  - Scope change (user, 2026-11-14): open-PR checks and artifact text from the PR branch.
  - `team_pending.topic_of(plan_path: str) -> str`: the plan file stem without a leading `YYYY-MM-DD-` (`.planning/plans/2026-11-14-team-progress.md` gives `team-progress`).
  - `team_pending.candidates(root: Path, team: TeamConfig) -> list[tuple[str, str, str | None]]`: `(branch, kind, epic)` with `kind` one of `spec`, `plan`, `ship`, `track`:
    - `git ls-remote --heads origin` (timeout 30 s): every `refs/heads/spec/*` as `spec` and `refs/heads/plan/*` as `plan`, epic None (resolved from the file later);
    - every open or in-progress bead with a parent whose description has `Plan: <path>, Track <N>`: `feat/<topic>-t<N>` as `track` with the parent as epic;
    - when `team.approvals.get("ship")` has roles: `feat/<topic>` once per epic seen on those track beads, as `ship`;
    - a failed `git ls-remote` raises `TeamError("git ls-remote failed: <stderr>")`.
  - `team_pending.branch_documents(root: Path, branch: str, files: Sequence[str]) -> dict[str, str]`: the text of each changed `.md` file under `.planning/specs/`, `.planning/plans/`, or an SDD change folder, from one `git fetch --quiet origin refs/heads/<branch>` and `git show FETCH_HEAD:<file>`; the row's epic is the value of the first `Epic:` or `Workflow:` line, None when none is found.
  - `team_pending.pending(root: Path, team: TeamConfig, *, workflow_id: str | None = None, milestone: str | None = None) -> list[dict[str, Any]]`:
    - for each candidate, `team_host.pr_for_branch(team.host, branch, root)`; skip None and any state other than `open`;
    - row: `{"gate": "requirement_confirmed" | "plan_approved" | "ship" | None, "branch", "url", "author", "epic", "approvals": [login, ...], "missing": [...], "notes": [...]}`;
    - for `spec`, `plan`, and `ship` rows: `notes = []`; `_, _, reasons, _ = team.verify_gate(root, team, gate, pr.url, notes=notes, workflow_id=epic, before_merge=True, artifact_text=<the artifact's text from branch_documents>)`; `missing = reasons`;
    - for `track` rows: `gate` None, `missing` `[]`, approvals only;
    - a `HostUnavailable` or `TeamError` on one candidate gives that row with `"error": str(error)` and the other fields it has; `HostCliMissing` aborts the whole call (raised);
    - `workflow_id` keeps rows whose epic equals it; `milestone` keeps rows whose epic is a child epic of that milestone (`bd list --parent <milestone> --type epic --json`).
  - `gin team pending [--workflow-id <epic> | --milestone <id>] [--format json]`: team mode off gives exit 2 and `team mode is off`; `HostCliMissing`, `HostUnavailable`, and a failed `git ls-remote` give exit 2 with the cause (the existing `except` at `team_cli.py:192`); JSON `{"pending": rows}`; text groups rows by gate, then the track pull requests, one line each: `<gate or track> <url> <epic> missing: <reasons or ->`.
- **Steps**:
  1. Failing tests in `tests/workflow_core/test_team_pending.py` with `team_fixtures.make_team_repo` (a temporary team repository with an `origin` remote) and the host fakes `fake_cli` and `gh_pr`:
     - `topic_of` strips the date;
     - an open `spec/<topic>` pull request whose spec has `Epic: e-1` gives a `requirement_confirmed` row with epic `e-1` and the reasons of `verify_gate` (fake approvals that miss a role give a non-empty `missing`);
     - an open `plan/<topic>` pull request gives `plan_approved`;
     - a merged or closed pull request gives no row;
     - an open track bead `Plan: .planning/plans/2026-11-14-x.md, Track 2` with an open `feat/x-t2` pull request gives a track row with approvals and no gate;
     - with `team.approvals.ship` roles, an open `feat/x` pull request gives a `ship` row;
     - `--workflow-id` and `--milestone` filters;
     - team mode off exits 2 with `team mode is off`;
     - the host CLI missing exits 2 naming it;
     - one candidate raising `HostUnavailable` gives a row with `error` and the others still appear.
  2. Run `python3 -m pytest tests/workflow_core/test_team_pending.py -q` → fail.
  3. Implement per the interfaces; reuse `team_host.pr_for_branch`, `team.verify_gate`, `tasks.query_result` for Beads reads.
  4. Run step 2 → pass; `python3 -m pytest tests/workflow_core -q -n auto -k "team"` → pass; `gin docs check docs/reference/cli.md` → ok.
  5. Commit: `feat(team): gin team pending lists open gate pull requests and what they still need (gin-workflow-team-progress)`.
- **Acceptance criteria**: R4; US-2 criteria 1 to 4.
- **Estimated complexity**: medium

### Track 2: Partial marker in `gin usage report`
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/usage.py:389-436` (`report`: `partial`, `partial_reasons`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/usage_cli.py:40-50` (`_report_text`: `partial:` line)
  - Modify `plugins/gin-workflow/src/skills/report/SKILL.md` (one sentence: show `partial` and its reasons next to the totals)
  - Modify `docs/guides/usage-report.md`, `docs/guides/usage-report.vi.md`, `docs/reference/cli.md` (`gin usage report` fields)
  - Test `tests/workflow_core/test_usage.py`, `tests/workflow_core/test_usage_cli.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** one function and its text form with every reason fixed by spec R7.
- **Interfaces**:
  - `report(...)` returns two new keys: `partial: bool` and `partial_reasons: list[str]` (sorted, unique), computed from `selected` rows and their docs:
    - `children_not_merged`: a selected row with a doc and a selected direct child (`parent` equals its id) with its own doc;
    - `not_collected`: `not_collected` is non-empty;
    - `unattributed`: the returned `unattributed.tokens` is above 0;
    - `log_sources`: any doc's `sources` value is not `"ok"`, or any doc's `skipped_lines` is above 0;
    - `stale`: a doc whose `collected_at` is older than the latest `closed_at` of its selected direct children (`_ts` parses both; unparseable values are ignored);
    - `unpriced`: the returned `unpriced` is non-empty.
    `partial` is `bool(partial_reasons)`. `totals` and every existing key are unchanged.
  - `_report_text`: after the `total:` line, `partial: <comma-joined reasons>` when `partial`.
  - `report/SKILL.md`: show `partial` and its reasons next to the totals; keep the existing local-logs sentence.
  - Docs: `usage-report.md` and `.vi.md` explain each reason in one line; `cli.md` lists the two keys.
- **Steps**:
  1. Failing tests: one per reason with fake `bd list` rows (`test_usage.py` style), a case with no reason (`partial` false), a check that `report` makes no `bd update` call (stored `ai_usage` unchanged), and the text line (`test_usage_cli.py`).
  2. Run `python3 -m pytest tests/workflow_core/test_usage.py tests/workflow_core/test_usage_cli.py -q` → fail.
  3. Implement.
  4. Run step 2 → pass; `python3 -m pytest tests/workflow_core -q -n auto -k "usage or report"` → pass; `gin docs check docs/guides/usage-report.md docs/guides/usage-report.vi.md docs/reference/cli.md` → ok.
  5. Commit: `feat(usage): gin usage report marks partial totals with reasons (gin-workflow-team-progress)`.
- **Acceptance criteria**: R7; US-5.
- **Estimated complexity**: low

### Track 3: Progress sections, QA state, and docs
- **Dependencies**: Track 2
- **Files**:
  - Modify `plugins/gin-workflow/src/skills/progress/SKILL.md` (new steps for milestone, grouping and filters, spec status, approvals, QA state; existing steps kept)
  - Modify `plugins/gin-workflow/src/skills/qa-track/SKILL.md` (new `## QA state` section)
  - Modify `docs/concepts/lifecycle.md` (where it describes progress), `docs/guides/team.md`, `docs/guides/team.vi.md` (pending approvals)
  - Test `tests/workflow_core/test_skill_routing.py`
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** skill text and docs with every rule fixed by spec R1 to R3, R5, R6, R8, R9.
- **Interfaces** (text the skills must carry; wording may be tighter, facts may not change):
  - `progress/SKILL.md`, after step 1:
    - Milestone: with `--milestone <id>`, else the single `active` milestone, run `gin milestone show <id> --json`; start with two or three plain-language sentences (on track, or how many working days late, and what blocks it); then `deadline`, `finish`, `overflow_days`, `lanes`; one line per epic with `status`, `spec_confirmed`, `remaining_days`, and `warnings`. Without a milestone, the `forecast` line of `gin milestone list --json`. Markdown backend: say milestone data is unavailable.
    - Grouping: with `team.areas`, group tracks by their `area:` label; in a workspace, by the `Repo:` line of the track description; `--area <name>` or `--repo <path>` keeps only matching tracks and their epics; list epics whose `depends_on` names an open epic of another area under "waiting on another area".
    - Spec: per epic, `spec_confirmed`, its open spec pull request from the approvals step, and, with the SDD layout, `gin specs status --change <epic>` and any confirmed asset folder not committed.
    - Approvals (team mode): `gin team pending --format json` with the report's scope (`--workflow-id` or `--milestone`); list gate pull requests (gate, epic, author, approvals, `missing`), then track pull requests; exit 2 prints `approvals unknown: <cause>`.
    - QA: run the QA state check of the `qa-track` skill when it applies (same conditional wording ship uses, so qa-track stays out of the chain).
    - Keep steps 2 to 7 (grouping by status, review and gates, waivers, open questions, derived metadata, read-only). The skill never contains `gin-qa`.
  - `qa-track/SKILL.md`, `## QA state`: with gin-qa on PATH and `project.layout: sdd`, from the QA home, per epic of the report: `gin-qa cases plan --change <epic> --format json` gives the `missing` and `stale` counts; `gin-qa cases export --format json` gives the `failed` and `blocked` counts of the cases whose REQ-IDs belong to the change; show the latest run folder only when a gin-qa command returns it; without gin-qa, without the SDD layout, or on exit 2, report `QA state skipped: <reason>`. Stays within 6,000 characters.
  - Docs: `lifecycle.md` adds the new progress sections to its progress description; `team.md` and `.vi.md` add `gin team pending` to the team commands and progress. `.vi.md` keeps English anchors.
- **Steps**:
  1. Failing tests in `test_skill_routing.py`: progress contains `gin milestone show <id> --json`, `plain-language`, `--area <name>`, `waiting on another area`, `gin team pending`, `approvals unknown:`, `QA state`, and still contains `--exclude-label prep`, `[gin question]`, and `waived(`; progress contains no `gin-qa`; qa-track contains `## QA state`, `gin-qa cases plan --change <epic> --format json`, and `QA state skipped:`.
  2. Run `python3 -m pytest tests/workflow_core/test_skill_routing.py tests/workflow_core/test_token_budget.py tests/workflow_core/test_docs_coverage.py tests/gin_qa/test_packaging.py -q` → fail.
  3. Edit the skills and docs.
  4. Run step 2 → pass; `gin docs check docs/concepts/lifecycle.md docs/guides/team.md docs/guides/team.vi.md` → ok; record the progress chain size with `workflow_core.budget.stage_chars`.
  5. Commit: `feat(skills): progress shows milestone, approvals, spec, QA, and area views (gin-workflow-team-progress)`.
- **Acceptance criteria**: R1, R2, R3, R5, R6, R8, R9; US-1; US-2 criterion 3 (progress side); US-3; US-4.
- **Estimated complexity**: medium

## Integration
- **Branch**: `feat/team-progress`; track branches `feat/team-progress-t1` to `-t3` stacked in order.
- **Merge strategy**: sequential

## Validation
- [ ] All tests pass (`python3 -m pytest -n auto`, run by the pre-push hook)
- [ ] `gin docs check` on changed pages
- [ ] Budgets hold (`tests/workflow_core/test_token_budget.py`); `tests/gin_qa/test_packaging.py` passes

## Notes
- Track 1 calls `team.verify_gate` once per open gate pull request, which fetches the pull request again by URL; this keeps one source for the approval logic at the cost of a second host call.
- Deliverable merge-holds apply only to the Parent Bead; track beads close after tests and review pass.
- The user may override `Model:` and `Effort:` before plan approval.
