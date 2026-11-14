# Plan: Learn comments: stages post findings on the bead, ship writes knowledge

Spec: .planning/specs/2026-11-14-learn-comments-design.md
Epic: gin-workflow-fgil

## Objective

Every stage records reusable findings as `[gin learn]` comments on the workflow's bead (or `## Learnings` lines in the spec or plan before a bead exists); `/gin:ship` turns them into `.planning/knowledge/` records before the options; the `gin state` reminder reads learn comments from the bead, so it works on every machine.

**Goal** (spec): Every lifecycle stage, on any machine, records reusable findings in one shared place: a `[gin learn]` comment on the workflow's bead, or, before a bead exists, a `## Learnings` line in the spec or plan. `/gin:ship` then turns them into `.planning/knowledge/` records, and its reminder works on every machine.

**Architecture**: no new module. `workflow_core/lifecycle_cli.py` `_knowledge_warning` gains an `epic` argument and, with the Beads backend, reads the epic's comments through `_beads_json(repo_path, ["comments", epic])`; the markdown backend keeps today's local-event check. `_state_command` passes the epic it already resolved (the shared epic in team mode, else the recorded one). Skill text carries the rest: the `learn` skill owns the format and both procedures; `discuss`, `plan`, `execute`, `ship`, the `gin:developer` agent, and the execute result contract get one short sentence each.

**Tech Stack**: Python 3 standard library; unittest/pytest (`tests/workflow_core/test_lifecycle_cli.py`, `test_skill_routing.py`, `test_epic_comments.py`, `test_token_budget.py`, `test_docs_coverage.py`); `gin docs check`.

**Global Constraints** (spec "Errors and compatibility", verbatim):
- Projects without `[gin learn]` comments see no change, except that the Beads-backend reminder no longer fires on an epic with no learn comments; ship still runs reconcile.
- A failed comment never blocks a stage (R2).
- In team mode a learning is visible on another machine only after both sides run `gin team sync`; ship syncs first (R7).
- `## Learnings` is a new optional section; `gin specs lint` must keep accepting a spec or plan that has it.
- Older gin ignores `[gin learn]` comments; a mixed team still gets the comments, and only the reminder differs.

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
- Problem statement: capture happens only in execute, discuss and plan forbid writing to the bead, and the ship reminder needs a local event that other machines lack.
- Success criteria: spec R1 to R9 and US-1 to US-4, as tests (code) or checked text (skills, docs); existing tests pass; budgets hold.
- Constraints: Global Constraints above; budgets left (`tests/workflow_core/test_token_budget.py`): plan chain 413 characters, execute 404, ship 878, discuss 1,317, agents 4,000 each (developer at 3,636), descriptions 158; `tests/workflow_core/test_epic_comments.py` needles stay on their lines; new stage-skill lines contain neither `project.team` nor `sdd`.
- Non-goals: the reviewer posting learnings; gin-console; creating the bead earlier for ad-hoc workflows.

## Approach Options
### Option 1: `[gin learn]` comments on the bead, ship synthesizes (confirmed)
- Summary: as the Architecture above.
- Pros: one shared channel across machines; no new CLI; skill conventions like `[gin question]`.
- Cons: learnings are not code-reviewed until ship writes the records.

### Option 2: every stage writes knowledge files directly
- Summary: today's capture extended to discuss and plan.
- Pros: records are reviewed with each track.
- Cons: files on unmerged branches and the local-event reminder keep the cross-machine gap; rejected in `/discuss`.

### Recommended Approach
- Selected option: Option 1 (confirmed in `/discuss` on 2026-11-14).
- Rationale: it closes the cross-machine gap with skill text and one function.

## Scope
- In scope: R1 to R9.
- Out of scope: see Non-goals.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Track 2's docs describe Track 1's reminder; one lane.
```

## Tasks

### Track 1: Reminder reads learn comments from the bead
- **Dependencies**: none
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/lifecycle_cli.py:392-412` (`_knowledge_warning`, new helper `_learn_comment_warning`), `:414-503` (`_state_command`: the epic passed to the warning)
  - Test `tests/workflow_core/test_lifecycle_cli.py` (new cases next to the `_us6_warnings` helper, ~821-865)
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** one function and its caller, with every rule and message fixed by spec R8.
- **Interfaces**:
  - `_knowledge_warning(repo_path, config, events, workflow_id, gates, epic: str | None = None) -> str | None`:
    1. Return None unless `gates.get("implementation_complete")`.
    2. Resolve `knowledge` as today (None on `ArtifactResolutionError`).
    3. `name = tasks_backend(repo_path)`; on `ConfigValidationError` return None.
    4. `name == "beads"`: return `_learn_comment_warning(repo_path, knowledge, epic)`.
    5. Otherwise today's logic, unchanged (local `orchestration.ready`, `git log --since`), with its message unchanged.
  - `_learn_comment_warning(repo_path: Path, knowledge: Path, epic: str | None) -> str | None`:
    - None when `epic` is falsy.
    - `comments, cause = _beads_json(repo_path, ["comments", epic])`; None when `cause` or `comments` is not a list.
    - `learns` = the Mapping items whose `str(item.get("text") or "").lstrip()` starts with `[gin learn]`; None when empty.
    - `last` = the committer time of `git log -1 --format=%cI -- <knowledge>` (timeout 10 s) parsed with `datetime.fromisoformat`; None when the output is empty; return None (no warning) on `OSError`, `subprocess.SubprocessError`, a non-zero exit, or a `ValueError` from parsing.
    - `pending` = the learns whose `created_at` (parsed with `datetime.fromisoformat`, a trailing `Z` accepted) is later than `last`, or all learns when `last` is None; a learn whose `created_at` does not parse counts as pending.
    - None when `pending` is empty; else `f"{len(pending)} learn comments not yet in {shown}; reconcile knowledge (learn) before ship"`, `shown` relative to the repository as today.
  - `_state_command`: set `warn_epic: str | None = None` before the `if events is None` branch; in the `else` branch, after `shared_gates`, set `warn_epic = shared_epic or recorded or None`; pass `epic=warn_epic` to `_knowledge_warning`.
- **Steps**:
  1. Failing tests in `tests/workflow_core/test_lifecycle_cli.py`, through `lifecycle_main(["state", ..., "--format", "json"])` like `_us6_warnings`, with `workflow_core.lifecycle_cli._delivery_state` patched to `implementation_complete: True`, `workflow_core.lifecycle_cli.tasks_backend` patched to return `"beads"`, and `workflow_core.lifecycle_cli._beads_json` patched to return the comment list for `["comments", "epic"]`:
     - a `[gin learn]` comment created after the last knowledge commit warns `1 learn comments not yet in .planning/knowledge`;
     - a knowledge commit after the comment gives no warning;
     - comments without `[gin learn]` (for example `[gin question]`) give no warning;
     - a learn comment and no knowledge commit at all warns;
     - `_beads_json` returning `(None, "bd failed")` gives no warning;
     - `implementation_complete: False` gives no warning;
     - team mode with no local `orchestration.ready` event: patch `workflow_core.lifecycle_cli.load_team` (called at `_state_command` ~419) to return a team object and `workflow_core.team_beads.shared_gates` to return `("epic", {}, None)`; a learn comment warns.
     The five existing `test_us6_*` tests (markdown backend) stay unchanged and pass.
  2. Run `python3 -m pytest tests/workflow_core/test_lifecycle_cli.py -q` → the new tests fail.
  3. Implement per the interfaces.
  4. Run step 2 → pass; `python3 -m pytest tests/workflow_core -q -n auto -k "lifecycle or state"` → pass.
  5. Commit: `feat(state): the knowledge reminder reads learn comments from the bead (gin-workflow-fgil)`.
- **Acceptance criteria**: R8; US-1 criterion 3; US-4 criterion 2 (reminder side).
- **Estimated complexity**: medium

### Track 2: Learn skill, stage sentences, worker output, and docs
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-workflow/src/skills/learn/SKILL.md` (sections Capture and Reconcile rewritten)
  - Modify `plugins/gin-workflow/src/skills/discuss/SKILL.md:14` (Roadmap epic paragraph)
  - Modify `plugins/gin-workflow/src/skills/plan/SKILL.md:16` (step 1)
  - Modify `plugins/gin-workflow/src/skills/execute/SKILL.md:28`
  - Modify `plugins/gin-workflow/src/skills/execute/references/result-contract.md:14`
  - Modify `plugins/gin-workflow/src/skills/ship/SKILL.md:17` (allowed paths), end of step 1 (reconcile), `:37` (step 7)
  - Modify `plugins/gin-workflow/src/agents/developer.md:42-46` (Output handoff details)
  - Modify `docs/concepts/lifecycle.md:103` and a short learnings paragraph next to it; `docs/guides/team.md`, `docs/guides/team.vi.md` (sync after posting a learning)
  - Test `tests/workflow_core/test_skill_routing.py`
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** skill text and docs with every rule fixed by spec R1 to R7 and R9, inside tight character budgets.
- **Interfaces** (text the files must carry; wording may be tighter, facts may not change):
  - `learn/SKILL.md`, `## Capture (any stage)`:
    1. Keep today's rule 1 (what counts as reusable knowledge).
    2. One line per fact: `[gin learn] <stage> <track-id|->: <fact>. Evidence: <file:line | command | bead>`, `<stage>` one of `discuss`, `plan`, `orchestrate`, `execute`, `review`, `ship`, `-` for no track.
    3. With the Beads backend and a bead for the workflow (a roadmap epic, an SDD epic once created, a standalone bead, or the epic orchestrate created), `gin task comment <bead> "<line>"`; a track's learning goes on its epic; in team mode run `gin team sync` after posting. A failed comment never blocks the stage: put the line under `## Learnings` of the spec or plan, else in the handoff.
    4. No bead yet (discuss or plan of an ad-hoc workflow): append the line under `## Learnings` at the end of the spec or plan.
    5. Markdown backend (no comments): write or update the record directly as in the Reconcile steps, and mention it in the bead notes.
    6. Workers never post: the dispatching session posts each `Learnings` item of `gin:developer` and each `knowledge_candidates` entry (`fact`, `evidence`) of an orchestrated worker as `[gin learn] execute <track-id>:`.
  - `learn/SKILL.md`, `## Reconcile (ship, before the options)`:
    1. In team mode run `gin team sync`. Collect every `[gin learn]` comment of the epic (`gin task comments <epic> --json`) and the `## Learnings` lines of the spec and plan; with none, say so in one sentence.
    2. Search first (`grep -ril "<topic>" .planning/knowledge`, `gin task memories <keyword>`); update an existing record instead of duplicating it; merge duplicate learnings.
    3. Write or update `.planning/knowledge/<topic>.md` with **Context**, **Decision/Solution**, **Consequences**, **References** (paths, beads), and **Scope**; for an architectural decision start from `gin specs template adr.md`.
    4. Update related records with an evidence-backed summary and correct contradictions or stale statements.
    5. Commit the records on the feature branch. Close beads only after the records are written, or after a skipped update is stated in the handoff.
    Keep the existing first paragraph about `.planning/knowledge/` and `gin task remember`.
  - `discuss/SKILL.md:14`: replace ", and never write a comment." with ", and write no comment except `[gin learn]` per `learn`. Leave `[gin learn]` comments out of the summary and of `Comments considered:`." Every `test_epic_comments.py` needle stays on this line.
  - `plan/SKILL.md:16`: "take the comments whose `created_at`" becomes "take the comments, other than `[gin learn]`, whose `created_at`"; "write nothing to the spec or the bead" becomes "write nothing to the spec or the bead except `[gin learn]` per `learn`". Needles stay on the line; the plan chain stays within 12,000.
  - `execute/SKILL.md:28`: "- Post your learnings and each worker's (`Learnings`, `knowledge_candidates`) as `[gin learn]` per `learn`."
  - `execute/references/result-contract.md:14`: "`knowledge_candidates` is an optional list of objects with `fact` and `evidence`, normalized to an empty list when omitted; execute posts each as `[gin learn]`."
  - `ship/SKILL.md`:
    - Line 17: the allowed paths become `.planning/specs/`, `.planning/reviews/`, `.planning/knowledge/`, and the SDD spec dirs.
    - End of step 1, a new line after the team-mode line: "Then reconcile knowledge per `learn` and commit the records on the feature branch, before the options."
    - Line 37 (step 7): "then reconcile knowledge per `learn`" is removed; step 7 still shows each `warnings` entry. Every `test_epic_comments.py` needle on lines 37 and 39 stays.
  - `agents/developer.md` Output handoff details, new item: "- `Learnings`: reusable facts with evidence for `[gin learn]` (see `learn`), or `none`." The file stays within 4,000 characters.
  - `docs/concepts/lifecycle.md:103`: "With the Beads backend, `state` warns when `implementation_complete` holds and the epic has `[gin learn]` comments newer than the last commit to the knowledge directory; with the markdown backend, when no commit has touched it since `orchestration.ready`. Committing the knowledge records (see `learn`) clears it." Plus a short paragraph next to it: every stage posts `[gin learn] <stage> <track-id|->: <fact>. Evidence: <ref>` on the bead, or writes it under `## Learnings` of the spec or plan before a bead exists; ship writes the records before the options.
  - `docs/guides/team.md` and `.vi.md`: in team mode a learning reaches other machines only after `gin team sync`; post, then sync. The `.vi.md` keeps English anchors.
- **Steps**:
  1. Failing tests in `tests/workflow_core/test_skill_routing.py`: `learn` contains `[gin learn] <stage> <track-id|->:`, `## Learnings`, `knowledge_candidates`, and `Reconcile (ship, before the options)`; `discuss` contains `write no comment except \`[gin learn]\``; `plan` line `1. Require` contains `other than \`[gin learn]\``; `execute` contains `as \`[gin learn]\` per \`learn\``; `ship` contains `.planning/knowledge/` on the line with `may touch only`, and `reconcile knowledge per \`learn\`` on a line before `4. Present`; `agents/developer.md` contains `` `Learnings` ``; `result-contract.md` contains `fact` and `evidence`.
  2. Run `python3 -m pytest tests/workflow_core/test_skill_routing.py tests/workflow_core/test_epic_comments.py tests/workflow_core/test_token_budget.py tests/workflow_core/test_docs_coverage.py -q` → the new tests fail.
  3. Edit the files per the interfaces.
  4. Run step 2 → pass; `gin docs check docs/concepts/lifecycle.md docs/guides/team.md docs/guides/team.vi.md` → ok; `python3 -c "import sys; sys.path.insert(0, 'plugins/gin-workflow/src/scripts'); from workflow_core.budget import stage_chars; from pathlib import Path; [print(s, stage_chars(Path('plugins/gin-workflow/src'), s)) for s in ('discuss','plan','execute','ship')]"` for the record.
  5. Commit: `feat(skills): [gin learn] comments from every stage; ship writes knowledge before the options (gin-workflow-fgil)`.
- **Acceptance criteria**: R1 to R7, R9; US-1 criteria 1 and 2; US-2; US-3; US-4 criterion 1 and criterion 2 (capture side).
- **Estimated complexity**: medium

## Integration
- **Branch**: `feat/learn-comments`; track branches `feat/learn-comments-t1`, `feat/learn-comments-t2` stacked in order.
- **Merge strategy**: sequential

## Validation
- [ ] All tests pass (`python3 -m pytest -n auto`, run by the pre-push hook)
- [ ] `gin docs check` on changed pages
- [ ] Budgets hold (`tests/workflow_core/test_token_budget.py`)

## Notes
- Spec R7 places reconcile at the end of ship step 1, before the options, so the records land with either merge or pull request.
- Deliverable merge-holds apply only to the Parent Bead; track beads close after tests and review pass.
- The user may override `Model:` and `Effort:` before plan approval.
