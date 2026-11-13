# Plan: Prep tasks: allocate pre-discuss work under an epic

Spec: .planning/specs/2026-11-13-prep-tasks-design.md
Workflow: prep-tasks

## Objective

A prep task is a child of an epic labelled `prep` and `prep:<type>`. gin keeps it out of every implementation check (close guard, delivery state, goal, milestone forecast, usage tracks, execute and ship selection) through one predicate, `is_prep`, and one helper, `tracks_of`. `gin team ready` lists prep tasks held only by their epic, sorted by priority, so the BA works across epics. A new skill, `/gin:allocate`, proposes, assigns, and creates prep tasks for one epic or a milestone. Skills and docs follow.

**Goal** (spec): After `/gin:roadmap`, members do not know what to do until `/gin:discuss` runs, and discuss itself waits for inputs that only the BA (a legacy capture, a mockup) or a lead (a technical spike) can produce. A tech lead runs a new skill, `/gin:allocate`, that creates these pre-discuss tasks ("prep tasks") as children of each epic and assigns them, so the BA works across epics in order without waiting for anyone, and gin never treats a prep task as implementation work.

**Architecture**: a new module `workflow_core/prep.py` owns the label names, `is_prep(record)`, and `tracks_of(children)`. Every Python site that enumerates an epic's children calls `tracks_of`: `lifecycle_cli` (`_delivery_state`, `_record_refusal`), `goal.main`, `milestone.remaining_days`. `close_guard.check` skips a prep task without a review ledger. `lifecycle_cli._record_command` refuses `orchestration-ready --epic <prep>`. `usage` marks spans with `BeadSpan.prep`, and `usage_attribution` keeps prep spans out of tracks and holders. The markdown backend gains `--exclude-label` and `--no-inherit-labels`; `team_beads.ready` gains `exclude`, prep tasks held by their epic, and priority order. Skills: a new `allocate` skill with a `references/prep-catalog.md`, and short edits to `discuss`, `execute`, `ship`, `orchestrate`, `progress`, `parallel-agents`, the roadmap way-of-working reference, and the stage contract.

**Tech Stack**: Python 3 standard library; unittest/pytest (`tests/workflow_core/test_close_guard.py`, `test_lifecycle_cli.py`, `test_goal.py`, `test_milestone.py`, `test_usage.py`, `test_usage_attribution.py`, `test_task_markdown.py`, `test_team_beads.py`, `test_skill_routing.py`, `test_token_budget.py`, `test_docs_coverage.py`); `gin docs check`.

**Global Constraints** (spec "Errors and compatibility", verbatim):
- No `prep` label anywhere: no behaviour changes. A project that already uses a `prep` label for something else sees those children leave the track checks; the docs name the label as reserved.
- An older gin treats a prep task as a track (it needs a review ledger to close and blocks `implementation_complete`), so every member updates gin before the lead runs `/allocate`. Docs say so.
- Removing the `prep` label turns the bead into a track. Adding `prep` to a track that has a `track:` or `req:` label changes nothing; adding it to another track removes it from `implementation_complete`, but its review ledger, if any, still guards the close, and ship lists it as closed without review.
- A bead labelled `prep` that also has a `track:` or `req:` label is a track for gin, so it blocks `implementation_complete`, but the skills' `--exclude-label prep` hides it from `/gin:execute`; remove the `prep` label. The docs state the exception to "every child not labelled `prep`".
- `gin team ready` now sorts by priority within each group, so its order changes for every team project, with or without prep tasks. Docs say so.
- Closing an epic outside `/gin:ship` fails while a prep task is open: close or reopen-and-close the prep task first.
- A tracker failure keeps today's behaviour at each site: close guard refuses, delivery state reports `unknown`, the R4 check is skipped, and `gin team ready` raises `TeamError`.
- bd needs `--no-inherit-labels` to keep `roadmap` and `kind:` off prep tasks; the markdown backend accepts the flag and ignores it.

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
- Problem statement: gin treats every child of an epic as an implementation track, so pre-discuss work cannot live under the epic; nothing assigns pre-discuss work; bd hides children of a blocked epic from `ready`.
- Success criteria: spec R1 to R11 and US-1 to US-4, as tests (code) or checked text (skills, docs); existing tests pass; budgets hold.
- Constraints: Global Constraints above; skill budgets (`tests/workflow_core/test_token_budget.py`): execute chain 555 characters left, review chain 424, plan chain 433, discuss chain 1,532, descriptions 351; new stage-skill lines contain neither `project.team` nor `sdd`; core skills never name gin-ba; skills call `gin task`, never `bd` (`tests/test_no_direct_bd.py`).
- Non-goals: gin-console views (follow-up bead, R12); checking a capture or mockup folder at close; assigning implementation tracks; a permission key for `/allocate`.

## Approach Options
### Option 1: label `prep` with one predicate in code (confirmed)
- Summary: as the Architecture above.
- Pros: no bd configuration; works on both backends; `--exclude-label` exists in bd; follows the `human-gate` label pattern.
- Cons: every child enumeration must call `tracks_of`; a mislabelled track is a risk (mitigated by the `track:`/`req:` rule, the review-ledger rule, and the ship listing).

### Option 2: custom bd issue type `prep`
- Summary: `types.custom` in bd, filtered by `--exclude-type`.
- Pros: a type is harder to add by accident.
- Cons: bd configuration in every clone; type support in the markdown backend; rejected in `/discuss`.

### Recommended Approach
- Selected option: Option 1 (confirmed in `/discuss` on 2026-11-13).
- Rationale: smallest change, no setup, both backends.

## Scope
- In scope: R1 to R11.
- Out of scope: R12 is a follow-up bead created at ship; see Non-goals.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Track 2 uses Track 1's prep module; Track 3's skills name Track 2's flags; Track 4 documents all three. One lane.
```

## Tasks

`S` is `plugins/gin-workflow/src/scripts/workflow_core`. `K` is `plugins/gin-workflow/src`.

### Track 1: Prep predicate and its use in delivery state, close guard, goal, forecast, and usage
- **Dependencies**: none
- **Files**:
  - Create `plugins/gin-workflow/src/scripts/workflow_core/prep.py`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/close_guard.py:88-97` (`check`: skip a prep task without a review ledger)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/lifecycle_cli.py:114-144` (`_delivery_state`), `:165-181` (`_record_refusal`), `:292-296` (`_record_command`: R4 refusal)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/goal.py:52-70` (`main`: `tracks_of`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/milestone.py:183-192` (`remaining_days`: `tracks_of`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/usage_attribution.py:26-33` (`BeadSpan.prep`), `:126-160` (`attribute` tracks, `_key` holders)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/usage.py:292-299` (`_span` sets `prep`), `:343-347` (`collect`: no quality from prep children)
  - Test `tests/workflow_core/test_prep.py` (new), `tests/workflow_core/test_close_guard.py`, `tests/workflow_core/test_lifecycle_cli.py`, `tests/workflow_core/test_goal.py`, `tests/workflow_core/test_milestone.py`, `tests/workflow_core/test_usage.py`, `tests/workflow_core/test_usage_attribution.py`
- **Provider role**: `backend`
- **Model:** `opus`
- **Effort:** `high`
- **Why:** cross-module change to delivery state and the review close guard, where a wrong exemption lets work ship without review; many edge cases (tracker failure, standalone beads, team-mode shared epics, prep-only epics, worktree ledgers).
- **Interfaces**:
  - `prep.PREP = "prep"`; `prep.TYPES = ("capture", "mockup", "spike", "question", "other")`.
  - `prep.is_prep(record: Mapping[str, Any]) -> bool`: `labels = record.get("labels") or []`; true when `"prep" in labels` and no label starts with `track:` or `req:`.
  - `prep.tracks_of(children: Sequence[Any]) -> list[Any]`: every child except a Mapping for which `is_prep` is true (non-Mapping items are kept, so callers' existing type checks still fail closed).
  - `close_guard.check`: inside the loop over `ids`, after reading `record`, when `isinstance(record, Mapping) and is_prep(record)` and `usage._ledger(root, bead) is None` (lazy import; it searches the main checkout and every worktree), `continue`. Otherwise today's rule, so a prep task with a ledger still needs an approved one or `--waive-review`.
  - `lifecycle_cli._delivery_state`: right after the `if cause:` check, `if isinstance(children, list): children = tracks_of(children)`; the rest unchanged (an epic with only prep children takes the `children == []` branch).
  - `lifecycle_cli._record_refusal`: the same filter before `if children != []`.
  - `lifecycle_cli._record_command`: when `args.gate == "orchestration-ready" and args.epic`, `shown, cause = _beads_json(root, ["show", args.epic])`; `record = shown[0] if isinstance(shown, list) and len(shown) == 1 else shown`; when `cause is None and isinstance(record, Mapping) and is_prep(record)`, return `({"status": "rejected", "message": f"orchestration-ready refused: {args.epic} is a prep task, not implementation work"}, 1)`. A `cause` skips the check.
  - `goal.main`: after `tracks = query(...)`, `if isinstance(tracks, list): tracks = tracks_of(tracks)` before `if tracks == []`.
  - `milestone.remaining_days`: `tracks = tracks_of([bead for bead in beads.values() if bead.get("parent") == epic["id"] and bead.get("issue_type") != "epic"])`.
  - `usage_attribution.BeadSpan` gains the last field `prep: bool = False`. `attribute`: `tracks = [span for span in spans.values() if span.parent == collecting and not span.prep]`. `_key`: `holders` adds `not span.prep and`.
  - `usage._span`: `BeadSpan(..., prep=is_prep(shown))`. `usage.collect`: in the `for child in children:` quality loop, `if is_prep(_row(by_id, child)): continue`. Prep children stay in `children` and `members`, so their cost counts toward the epic.
- **Steps**:
  1. Failing tests:
     - `test_prep.py`: `is_prep` for `["prep", "prep:capture"]` (true), `["prep", "track:2"]` (false), `["prep", "req:CAT-001"]` (false), `[]` and a missing `labels` key (false); `tracks_of` drops prep Mappings and keeps tracks and non-Mapping items.
     - `test_close_guard.py`: with `project.review_ledger` on, closing a prep task with no ledger anywhere succeeds and writes no `review.waived` event; a prep task whose ledger exists only in a worktree and is not approved is refused like a track; a plain track without a ledger is still refused; a tracker failure is still refused.
     - `test_lifecycle_cli.py`: an orchestrated epic whose tracks are closed and whose prep task is open reads `implementation_complete` satisfied; the same after a prep task is reopened; team mode with Beads, an epic not yet orchestrated whose prep tasks are all closed, does not read `implementation_complete` satisfied; `record shipped` for a standalone bead with only prep children is not refused for having children; `record orchestration-ready --epic <prep>` is rejected with the R4 message; with the tracker failing, `orchestration-ready` records as today; every existing case without prep children is unchanged.
     - `test_goal.py`: `gin goal` lists no prep task; an epic with only prep children prints the line for an epic without children.
     - `test_milestone.py`: `remaining_days` of an in-progress epic with 2 tracks (1 open) and 3 closed prep tasks is `ceil(days * 1 / 2)`.
     - `test_usage_attribution.py`: an open prep span does not stop the ship window; a prep span overlapping a track's worktree time is not a holder, so the track's review record keeps its `review` stage.
     - `test_usage.py`: `collect` on an epic with a reopened prep child adds no reopen to the epic's quality, keeps the prep child in `children`, and sets `BeadSpan.prep`.
     - A test that `lifecycle_cli`, `goal`, and `milestone` take their track lists from `prep.tracks_of` (patch `prep.tracks_of` with a recording stub or assert on a prep-only fixture per module).
  2. Run `python3 -m pytest tests/workflow_core/test_prep.py tests/workflow_core/test_close_guard.py tests/workflow_core/test_lifecycle_cli.py tests/workflow_core/test_goal.py tests/workflow_core/test_milestone.py tests/workflow_core/test_usage.py tests/workflow_core/test_usage_attribution.py -q` → new tests fail.
  3. Implement per the interfaces.
  4. Run step 2 → pass; `python3 -m pytest tests/workflow_core -q -n auto -k "close or lifecycle or goal or milestone or usage or prep or state"` → pass.
  5. Commit: `feat(prep): prep tasks leave delivery state, close guard, goal, forecast, and usage tracks (prep-tasks)`.
- **Acceptance criteria**: R1 to R7; US-2 criterion 3; US-3 criteria 1, 2, 3, 5, 7; US-4 criterion 1.
- **Estimated complexity**: high

### Track 2: CLI filters and prep tasks in team ready
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/task_markdown.py:196-245` (parsers: `create --no-inherit-labels`, `list`/`ready --exclude-label`), `:296-308` (`list` and `ready` filters)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team_beads.py:87-111` (`ready`: `exclude`, prep tasks held by their epic, priority order, `priority` field)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team_cli.py:34` (`ready --exclude-label`), `:132-136` (pass it)
  - Test `tests/workflow_core/test_task_markdown.py`, `tests/workflow_core/test_team_beads.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** bounded changes to two modules with the rules, queries, and order fixed by the spec.
- **Interfaces**:
  - Markdown `create` accepts `--no-inherit-labels` (`store_true`, unused). `list` and `ready` accept `--exclude-label` (`action="append"`, comma-separated values split with `_csv`) and drop tasks carrying any listed label.
  - `team_beads.ready(root, team, member, exclude: Sequence[str] = ()) -> list[dict[str, Any]]`. Each row gains `"priority"` (the bead's priority, `None` when absent).
    - Ready group: today's `bd ready --exclude-type milestone` rows, plus prep tasks held by their epic: `blocked = _bd_json(root, ["blocked"])`; `preps = {row["id"]: row for row in _bd_json(root, ["list", "--label", "prep", "--status", "open", "--limit", "0"])}`; a blocked row qualifies when its id is in `preps`, `blocked_by == [preps[id]["parent"]]`, `is_prep(preps[id])`, and no entry of `preps[id]["dependencies"]` has `type == "blocks"`. Qualifying rows pass the same assignee, area, and `released` test as the ready rows.
    - Expired-claim group: today's rows, unchanged.
    - Rows with any label in `exclude` are dropped from both groups (read labels from the bd row).
    - Each group is sorted by `(priority if priority is not None else 99, id)`; the ready group comes first.
    - A failure of `bd blocked` or `bd list` raises `TeamError` with the bd message, like the existing `bd ready --explain` failure.
  - `gin team ready --exclude-label <label>` (repeatable, comma-separated allowed) passes `exclude` to `team_beads.ready`.
- **Steps**:
  1. Failing tests:
     - `test_task_markdown.py`: `create --no-inherit-labels` succeeds and stores only `--labels`; `list --exclude-label prep` and `ready --exclude-label prep` drop a `prep` task and keep others; `--exclude-label a,b` drops both labels.
     - `test_team_beads.py` (fake bd as in the existing tests): a BA's prep task under an epic blocked by another open epic is listed; a prep task with its own `blocks` dependency is not; a prep task assigned to someone else is not; `exclude=["prep"]` drops prep rows from both groups; rows are sorted by priority then id within each group, and expired-claim rows stay after ready rows; every row has `priority`; a failing `bd blocked` raises `TeamError`; a project with no prep tasks returns the same rows as before, now ordered by priority.
  2. Run `python3 -m pytest tests/workflow_core/test_task_markdown.py tests/workflow_core/test_team_beads.py -q` → new tests fail.
  3. Implement per the interfaces.
  4. Run step 2 → pass; `python3 -m pytest tests/workflow_core -q -n auto -k "task or team"` → pass.
  5. Commit: `feat(tasks): --exclude-label on the markdown backend; team ready lists prep tasks held by their epic, by priority (prep-tasks)`.
- **Acceptance criteria**: R8; US-2 criteria 1, 2; US-3 criterion 4; US-4 criterion 2.
- **Estimated complexity**: medium

### Track 3: The allocate skill and prep tasks in existing skills
- **Dependencies**: Track 2
- **Files**:
  - Create `plugins/gin-workflow/src/skills/allocate/SKILL.md`, `plugins/gin-workflow/src/skills/allocate/references/prep-catalog.md`
  - Modify `plugins/gin-workflow/src/skills/execute/SKILL.md:14-15`
  - Modify `plugins/gin-workflow/src/skills/ship/SKILL.md:17` (step 1 ledger loop), `:32` (merge cleanup loop), `:37` (close-out), `:39` (handoff)
  - Modify `plugins/gin-workflow/src/skills/discuss/SKILL.md:14` (Roadmap epic paragraph)
  - Modify `plugins/gin-workflow/src/skills/orchestrate/SKILL.md:23`, `plugins/gin-workflow/src/skills/progress/SKILL.md:14`, `plugins/gin-workflow/src/skills/parallel-agents/SKILL.md:18`
  - Modify `plugins/gin-workflow/src/skills/roadmap/references/way-of-working.md:9`
  - Modify `plugins/gin-workflow/src/references/stage-contract.md:9`
  - Modify `docs/reference/skills.md`, `docs/reference/skills.vi.md` (the `allocate` row, needed by `test_docs_coverage.py`)
  - Test `tests/workflow_core/test_skill_routing.py`, `tests/workflow_core/test_token_budget.py`
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** skill text with every rule fixed by spec R9 and R10, inside tight character budgets.
- **Interfaces** (text the skills must carry; wording may be tighter, facts may not change):
  - `allocate/SKILL.md` frontmatter: `name: allocate`; `description:` at most 160 characters, e.g. `Propose, assign, and create pre-discuss prep tasks (capture, mockup, spike, question) under roadmap epics, for one epic or a milestone.` Body follows `roadmap/SKILL.md`'s shape: "On `/allocate` only. Outside the lifecycle: it records no gate. Never create or change a bead before the lead confirms the table."; `## Before you start` with the setup guard copied from `roadmap/SKILL.md` step 1; `## Steps` covering spec R9 in order: epics (`--milestone`: `gin milestone show <id> --json`, skip closed and `spec_confirmed`, `null` counts as not confirmed; one epic: `gin task show`, `gin state --workflow-id <epic> --format json`, stop when closed or confirmed), team mode (read `team.members`, `team.areas`, `team.beads_sync` from `.agent-workflow/config.yaml` of the main checkout; stop without `team.beads_sync`; `gin team sync` before and after writing), inputs per epic (skip missing lines; the confirmed-folder definition), proposals from the catalog, assignment (fewest open or in-progress prep tasks via `gin task list --label prep --status open,in_progress --assignee <email> --json`; ask when no member holds the role; no assignee in solo mode), order and priority (layer 0 → 1, layer 1 → 2, deeper → 3; one epic → the epic's priority), identity (`Capture: <capability>`, `Mockup: <capability>`; one open task per epic, type, capability; the lead matches spike, question, other), the confirmation table (epic, type, title, assignee, priority, done when, existing match), the create command of R9 verbatim, re-run (differences only, `gin task update <id> --assignee` and `-p`, never delete, close `not needed` only on confirmation), and the report (per member in priority order; `gin team ready` or `gin task list --label prep --status open,in_progress`; for spike and question `gin task comment <epic> "[gin answer] <prep-id>: <text>"` first; then `gin task close <id> --reason "<output>"`; then `gin team sync` in team mode). It never names another plugin's skills.
  - `allocate/references/prep-catalog.md`: the catalog table of spec R9 (type, default role, proposed when, done when), the confirmed-folder definition, and the `track:`/`req:` exception.
  - `execute` line 14: both commands gain `--exclude-label prep`, plus one sentence: a bead labelled `prep` is pre-discuss work, not a track: refuse it. Line 15: `team ready --exclude-label prep`. No new line contains `project.team` or `sdd`; line 15 stays the single `project.team` line.
  - `ship` line 17: the loop runs for closed track beads not listed in `review_waivers` and not labelled `prep`; then list each closed `prep` bead of the epic (id, title, close reason) as closed without review. Line 32: the `cleanup` loop skips `prep` beads. Line 37: before closing the parent bead, list each open `prep` bead and close it with `--reason "not needed: <epic> shipped"`, because bd refuses to close an epic with an open child. Line 39: `gin task ready --exclude-label prep`.
  - `discuss` line 14 (Roadmap epic paragraph), one added sentence: run `gin task list --parent <id> --label prep --all --json`; warn about each open prep task (title, assignee) and continue; use the outputs closed prep tasks name in their close reason.
  - `orchestrate` line 23, `parallel-agents` line 18, `progress` line 14: `gin task ready --exclude-label prep`. `progress` line 14 also: an epic's children labelled `prep` are prep tasks, reported apart from its tracks with assignee and status.
  - `way-of-working.md` line 9 ends: "Name those epics and the BA work due before kickoff, and run `/allocate --milestone <id>` to create that work as prep tasks."
  - `stage-contract.md` line 9: "`implementation_complete` is derived: every child of the recorded epic not labelled `prep` is closed in Beads."
  - `test_token_budget.py`: a test that `skills/allocate/SKILL.md` is at most 6,000 characters.
- **Steps**:
  1. Failing tests in `test_skill_routing.py`: `allocate/SKILL.md` contains `--no-inherit-labels --labels prep,prep:<type>`, `team.beads_sync`, `gin milestone show <id> --json`, `[gin answer] <prep-id>:`, and does not contain `gin-ba`; `prep-catalog.md` lists the five types; `execute` line 14 contains `--exclude-label prep` twice and line 15 contains `team ready --exclude-label prep`, with still exactly one line containing `project.team`; `ship` step 1 names `prep` in the ledger loop and lists closed prep beads as closed without review, and `ship` contains `not needed: <epic> shipped` and `gin task ready --exclude-label prep`; `discuss` contains `--label prep --all --json`; `orchestrate`, `progress`, `parallel-agents` contain `gin task ready --exclude-label prep`; `way-of-working.md` contains `/allocate --milestone <id>`; `stage-contract.md` contains `not labelled \`prep\``. In `test_token_budget.py`: the 6,000-character test for `allocate`.
  2. Run `python3 -m pytest tests/workflow_core/test_skill_routing.py tests/workflow_core/test_token_budget.py tests/workflow_core/test_docs_coverage.py tests/test_no_direct_bd.py tests/gin_ba/test_ba_packaging.py -q` → new tests fail.
  3. Write the skill, the catalog, the edits, and the `skills.md`/`skills.vi.md` rows.
  4. Run step 2 → pass, and `python3 -c "import pathlib;[print(p, len(p.read_text(encoding='utf-8'))) for p in map(pathlib.Path, ('plugins/gin-workflow/src/skills/allocate/SKILL.md','plugins/gin-workflow/src/skills/execute/SKILL.md','plugins/gin-workflow/src/skills/ship/SKILL.md','plugins/gin-workflow/src/skills/discuss/SKILL.md'))]"` for the record; `gin docs check docs/reference/skills.md docs/reference/skills.vi.md` → ok.
  5. Commit: `feat(skills): /allocate for prep tasks; execute, ship, progress, discuss skip or report them (prep-tasks)`.
- **Acceptance criteria**: R9, R10; US-1; US-2 criterion 4; US-3 criteria 4 (skills side), 6.
- **Estimated complexity**: medium

### Track 4: Docs for prep tasks and /allocate
- **Dependencies**: Track 3
- **Files**:
  - Modify `docs/concepts/lifecycle.md` (a "Prep tasks" section; `implementation_complete` excludes prep tasks)
  - Modify `docs/concepts/state-model.md` (`implementation_complete`)
  - Modify `docs/roles.md`, `docs/roles.vi.md` (tech lead runs `/allocate`; the assignee closes prep tasks)
  - Modify `docs/reference/cli.md` (`gin task list|ready --exclude-label` on both backends, markdown `create --no-inherit-labels`, `gin team ready --exclude-label`, prep tasks held by their epic, priority order, the `orchestration-ready` refusal)
  - Modify `docs/guides/team.md`, `docs/guides/team.vi.md` (prep tasks need `team.beads_sync`; `team ready` order)
  - Modify `docs/guides/ba.md`, `docs/guides/ba.vi.md` (find and close prep tasks)
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** documentation across many pages and translations, checked against the code of Tracks 1 to 3.
- **Interfaces**: every page states only what Tracks 1 to 3 implement; the reserved `prep` label, the `track:`/`req:` exception, the update-gin-first note, and the `team ready` order change appear once each in their home page and are linked elsewhere. Translations keep English anchors `{ #... }`. Sentences at most 35 words; no em or en dashes.
- **Steps**:
  1. Read the Track 1 to 3 diffs (`git diff master...HEAD -- plugins tests`) and the spec R11.
  2. Edit the pages; for each `.vi.md` page, mirror the English change.
  3. Run `gin docs check` on every changed page → ok; `python3 -m pytest tests/workflow_core/test_docs_coverage.py -q` → pass.
  4. Commit: `docs: prep tasks and /allocate (prep-tasks)`.
- **Acceptance criteria**: R11.
- **Estimated complexity**: medium

## Integration
- **Branch**: `feat/prep-tasks`; track branches `feat/prep-tasks-t1` … `-t4` stacked in order.
- **Merge strategy**: sequential

## Validation
- [ ] All tests pass (`python3 -m pytest -n auto`, run by the pre-push hook)
- [ ] `gin docs check` on changed pages
- [ ] Budgets hold (`tests/workflow_core/test_token_budget.py`)
- [ ] Manual: in a scratch bd project, an epic B, an epic A depending on B, and a prep child of A created with `--no-inherit-labels --labels prep,prep:capture --assignee <ba>`: `gin team ready` for the BA lists it; `gin task close` on it with `review_ledger` on needs no waiver.

## Notes
- R12: at ship, create the follow-up bead in gin-console (`bd -C /home/gin/gin-fam/gin-console create ...`): show prep tasks apart from tracks in the epic progress bar, the Gantt view, report child counts (`reports/service.py`), and the ready list (`projects/source.py`).
- Deliverable merge-holds apply only to the Parent Bead; track beads close after tests and review pass.
- The user may override `Model:` and `Effort:` before plan approval.
