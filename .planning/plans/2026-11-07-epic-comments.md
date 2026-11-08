# Plan: Epic comments: ship and roadmap annotate affected epics, discuss and plan read them

Spec: `.planning/specs/2026-11-07-epic-comments-design.md`
Workflow: epic-comments

## Objective

`/ship` and `/roadmap` write a `[gin ship]` or `[gin roadmap]` comment on every open epic their work affects; `/discuss <epic-id>` and `/plan` read the epic's comments, summarise the description and the comments in time order into one current understanding, and ask the user to confirm it before anything else. Skill text and docs only, through the existing `gin task` passthrough to `bd`; one new test file locks the skill text; every stage chain stays under its 12,000-character budget.

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
- Problem statement: when a blocker epic ships or the roadmap changes an epic already in progress, nothing tells the next `/discuss` or `/plan` of the affected epic. `/discuss <epic-id>` reads only `gin task show <id> --json` (`comment_count` only, no bodies); no skill reads or writes bead comments; `/ship` step 7 closes the parent epic without looking at its dependents; `/roadmap` step 6 only warns the PM about an `in_progress` or adopted epic whose entry changed.
- Success criteria: R1–R6 of the spec. Discuss asks to confirm a time-ordered summary first and writes `Comments considered:` into the spec; plan summarises only comments newer than that line; ship comments open dependent epics with the merge commit and design doc; roadmap comments changed `in_progress`/adopted epics idempotently; markdown backend skips; comment failures never block ship or roadmap; docs name it; `test_token_budget` stays green.
- Constraints: `gin task` forwards arguments to `bd` unchanged (`scripts/workflow_core/tasks.py:204-211`); `bd comments <id> --json` returns a list of `{id, issue_id, author, text, created_at}`; `bd show --json --include-dependents` lists tracks and bugs among `dependents` too. Stage chain budgets (`tests/workflow_core/test_token_budget.py`, 12,000 chars): discuss 8,343, plan 11,322, ship 9,283 today; roadmap is not in `STAGES`. Existing tests pin substrings: `test_role_aware_skills.py` needs `**Clarify**` and `` `team` skill `` on one line of discuss, and `## Open Technical Questions`, `Decision:`, `03-design.md`, `record plan-approved` in plan step 1.
- Non-goals: `external:` cross-repo dependencies; comment support for the markdown backend; the technical/business split of discuss and plan (another worktree); new gates, events, or notifications; a new CLI command; a template change.

## Architecture
Skill prose under `plugins/gin-workflow/src/skills/{discuss,plan,ship,roadmap}/SKILL.md`, calling `gin task comments <id> --json` (read) and `gin task comment <id> "<text>"` (write) through the Beads passthrough. No Python change.

## Tech Stack
Markdown skills, Python `unittest` tests under `tests/workflow_core/`, `bd` 1.0.5 through `gin task`.

## Global Constraints
- The confirmed summary goes into the spec's `## Goal and scope`, followed by one line `Comments considered: <count>, latest <created_at of the newest comment>`; omitted without comments (R1).
- Automatic comments carry the prefix `[gin ship]` or `[gin roadmap]` (spec decisions).
- Discuss and plan never ask which comments to keep and never write a comment (R1, R2).
- The markdown task backend has no comment commands: every stage skips the comment steps in one sentence (R5).
- A failing `gin task comment` never blocks closing the epic or the Beads sync; a failing `gin task comments` stops discuss or plan (R5).
- Every stage chain stays at or under 12,000 characters.

## Approach Options
### Option 1: Skill text only, `gin task` passthrough (chosen in the spec)
- Summary: edit four skills, add one test file, two doc paragraphs.
- Pros: no CLI code, fits the budgets, matches how every other bead annotation (notes) is driven.
- Cons: the markdown backend gets nothing; comment formats live in prose.

### Option 2: New `gin task` command wrapping dependents lookup and comment formatting
- Summary: Python command that finds dependents, formats the comment, and falls back to notes on markdown.
- Pros: one tested format, markdown support.
- Cons: more code and docs for what `bd` already does; rejected during discuss.

### Recommended Approach
- Selected option: Option 1.
- Rationale: confirmed by the user at discuss; YAGNI.

## Scope
- In scope: `skills/discuss`, `skills/plan`, `skills/ship`, `skills/roadmap` text; `tests/workflow_core/test_epic_comments.py`; `docs/concepts/lifecycle.md`; `docs/reference/cli.md`.
- Out of scope: anything under `scripts/`, templates, gin-console, the markdown backend.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Tracks 1–4 each edit one skill but all add methods to the same new test file and share the budget test, so one track at a time avoids conflicts on tests/workflow_core/test_epic_comments.py; Track 5 documents the four.
```

## Tasks

### Track 1: Discuss reads the epic's comments (R1, R5)
- **Dependencies**: none
- **Files**:
  - Modify `plugins/gin-workflow/src/skills/discuss/SKILL.md:14` (the `**Roadmap epic:**` paragraph) and `:25` (step 5, where the spec is written)
  - Create `tests/workflow_core/test_epic_comments.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** bounded prose change with exact text given below, but the wording must fit the discuss chain under 12,000 characters and keep existing pinned substrings.
- **Steps**:
  1. Create `tests/workflow_core/test_epic_comments.py`:
     ```python
     """Skill text for epic comments (workflow epic-comments)."""

     from __future__ import annotations

     from pathlib import Path
     import unittest

     SRC = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src"


     def skill(name: str) -> str:
         return (SRC / f"skills/{name}/SKILL.md").read_text(encoding="utf-8")


     def line_with(text: str, needle: str) -> str:
         return next(line for line in text.splitlines() if needle in line)


     class TestDiscussReadsComments(unittest.TestCase):
         def test_roadmap_epic_reads_comments_in_time_order(self):
             line = line_with(skill("discuss"), "**Roadmap epic:**")
             for needle in (
                 "`gin task comments <id> --json`",
                 "`created_at` order",
                 "confirm or correct",
                 "`project.max_questions`",
                 "which comments to keep",
                 "markdown task backend",
             ):
                 self.assertIn(needle, line)

         def test_spec_records_comments_considered(self):
             line = line_with(skill("discuss"), "**Write the spec**")
             self.assertIn("Comments considered: <count>, latest <created_at", line)


     if __name__ == "__main__":
         unittest.main()
     ```
     Run `python3 -m pytest tests/workflow_core/test_epic_comments.py`: both tests fail (`AssertionError`).
  2. Replace line 14 of `skills/discuss/SKILL.md` with this single line:
     ```
     **Roadmap epic:** `/discuss <epic-id>` starts from `gin task show <id> --json`, `gin task comments <id> --json`, and its roadmap entry. Stop if the id is missing, not an epic, or closed; warn if its dependencies are still open. With comments, before any clarifying question: read the description, then each comment in `created_at` order (`author`, `created_at`, `text`); summarise the current understanding (goal, scope, what the comments changed, dependencies that shipped or changed); ask the user to confirm or correct that summary. This confirmation does not count against `project.max_questions`. Never ask which comments to keep, and never write a comment. With the markdown task backend there are no comments: say so in one sentence and continue. Pass `--workflow-id <epic-id>` to every `state` and `record` call and never create another epic.
     ```
  3. In line 25 (step 5), replace `(`Epic: <id>` for a roadmap epic)` with `(`Epic: <id>` for a roadmap epic; when it had comments, end `## Goal and scope` with the confirmed summary and the line `Comments considered: <count>, latest <created_at of the newest comment>`)`.
  4. Run `python3 -m pytest tests/workflow_core/test_epic_comments.py tests/workflow_core/test_role_aware_skills.py tests/workflow_core/test_token_budget.py`: all pass; `stage_chars(SRC, "discuss")` stays under 12,000 (about 9,060).
  5. Commit on `feat/epic-comments`: `feat(discuss): read epic comments in time order and record them in the spec (epic-comments)`.
- **Interfaces**: consumes `gin task comments <id> --json` (list of `{id, issue_id, author, text, created_at}`); produces the spec line `Comments considered: <count>, latest <created_at>` read by Track 2.
- **Acceptance criteria**: US-1; the two tests pass; `test_role_aware_skills.py` and `test_token_budget.py` pass.
- **Estimated complexity**: low

### Track 2: Plan reads comments newer than the spec (R2, R5)
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-workflow/src/skills/plan/SKILL.md:16` (step 1)
  - Modify `tests/workflow_core/test_epic_comments.py` (add a test class)
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** one sentence, but the plan chain has about 680 characters of budget left and step 1 carries four pinned substrings.
- **Steps**:
  1. Add to `tests/workflow_core/test_epic_comments.py`, before `if __name__`:
     ```python
     class TestPlanReadsNewerComments(unittest.TestCase):
         def test_step_one_reads_comments_newer_than_the_spec(self):
             step = line_with(skill("plan"), "1. Require `requirement_confirmed`")
             for needle in (
                 "`gin task comments <epic> --json`",
                 "Comments considered:",
                 "return to `/discuss <epic>`",
                 "markdown",
             ):
                 self.assertIn(needle, step)
     ```
     Run the file: the new test fails.
  2. Append to the end of line 16 of `skills/plan/SKILL.md` (after `refuses while a question is open.`), on the same line:
     ```
      With an `Epic:` line, run `gin task comments <epic> --json`; take the comments whose `created_at` is later than the timestamp on the spec's `Comments considered:` line (all of them without that line); with any, summarise the description and those comments in time order and ask whether to continue or return to `/discuss <epic>`; write nothing to the spec or the bead (markdown backend: no comments, say so).
     ```
     That is 409 characters; the plan chain lands near 11,730.
  3. Run `python3 -m pytest tests/workflow_core/test_epic_comments.py tests/workflow_core/test_role_aware_skills.py tests/workflow_core/test_token_budget.py`: all pass. If `test_token_budget` fails for `plan`, shorten the sentence (drop the parenthetical about the markdown backend to `(markdown backend: skip)`) rather than any other text.
  4. Commit: `feat(plan): read epic comments newer than the spec before planning (epic-comments)`.
- **Interfaces**: consumes the `Comments considered:` line from Track 1 and `gin task comments <epic> --json`.
- **Acceptance criteria**: US-2; the test passes; `test_role_aware_skills.py::test_plan_resolves_open_questions_first` and `test_token_budget.py` pass.
- **Estimated complexity**: low

### Track 3: Ship comments the dependent epics (R3, R5)
- **Dependencies**: Track 2
- **Files**:
  - Modify `plugins/gin-workflow/src/skills/ship/SKILL.md:36` (step 7) and `:38` (step 9, handoff)
  - Modify `tests/workflow_core/test_epic_comments.py` (add a test class)
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** bounded prose with exact text; the dependents filter and the design-doc lookup are the only logic.
- **Steps**:
  1. Add to the test file:
     ```python
     class TestShipCommentsDependents(unittest.TestCase):
         def test_close_out_comments_open_dependent_epics(self):
             step = line_with(skill("ship"), "7. Close out:")
             for needle in (
                 "`gin task show <epic> --json --include-dependents`",
                 "`issue_type: epic`",
                 "`open` or `in_progress`",
                 "[gin ship]",
                 "`requirement.confirmed`",
                 "never blocks",
                 "markdown",
             ):
                 self.assertIn(needle, step)

         def test_handoff_lists_commented_epics(self):
             self.assertIn("[gin ship]", line_with(skill("ship"), "9. Handoff:"))
     ```
     Run the file: both new tests fail.
  2. In line 36 of `skills/ship/SKILL.md`, insert after `and closing it is what marks `shipped`.` (same line):
     ```
      Then, also for a standalone bead, run `gin task show <epic> --json --include-dependents`; for each dependent with `issue_type: epic` and status `open` or `in_progress` (the list also holds the epic's own tracks and bugs: skip them), run `gin task comment <dependent> "[gin ship] <epic-id> <title> shipped (merge <sha>). Spec: <design doc>. Its outcome may change what this epic needs; the next /discuss <dependent> reads this comment."` with `<sha>` the merge commit and `<design doc>` the `evidence` of the epic's latest `requirement.confirmed` event in `.agent-workflow/runtime/events.jsonl` of the main checkout (`none` without one). A failed comment never blocks the close: report it. With the markdown task backend there are no comments: say so in one sentence.
     ```
  3. In line 38 (step 9), replace `and end with `Next commands:`` with `then the dependent epics that received a `[gin ship]` comment, and end with `Next commands:``.
  4. Run `python3 -m pytest tests/workflow_core/test_epic_comments.py tests/workflow_core/test_token_budget.py`: all pass; the ship chain lands near 10,100.
  5. Commit: `feat(ship): comment open dependent epics when the epic closes (epic-comments)`.
- **Interfaces**: consumes `gin task show <epic> --json --include-dependents` (`dependents[].issue_type`, `dependents[].status`), `events.jsonl` (`event_type: requirement.confirmed`, `workflow_id`, `payload.evidence`); produces `[gin ship]` comments read by Track 1's discuss text.
- **Acceptance criteria**: US-3; the two tests pass; `test_token_budget.py` passes.
- **Estimated complexity**: low

### Track 4: Roadmap comments the epics it leaves unchanged (R4, R5)
- **Dependencies**: Track 3
- **Files**:
  - Modify `plugins/gin-workflow/src/skills/roadmap/SKILL.md:35` (step 6 bullet) and `:38` (step 7, report)
  - Modify `tests/workflow_core/test_epic_comments.py` (add a test class)
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** bounded prose; the idempotency rule is the one edge case. Roadmap is outside the stage budget.
- **Steps**:
  1. Add to the test file:
     ```python
     class TestRoadmapCommentsChangedEpics(unittest.TestCase):
         def test_unchanged_epic_gets_a_comment_once(self):
             bullet = line_with(skill("roadmap"), "warn and leave its title, description, and dependencies unchanged")
             for needle in (
                 "[gin roadmap]",
                 "`Depends on:`",
                 "most recent `[gin roadmap]` comment",
                 "closed epic gets no comment",
                 "sync continues",
                 "markdown",
             ):
                 self.assertIn(needle, bullet)

         def test_report_lists_commented_epics(self):
             self.assertIn("[gin roadmap]", line_with(skill("roadmap"), "7. **Report**"))
     ```
     Run the file: both new tests fail.
  2. Replace line 35 of `skills/roadmap/SKILL.md` with this single line (keep the three-space indent):
     ```
        - an epic that is `in_progress` or closed, or `open` and adopted into a milestone (in Beads, or in the confirmed roadmap: `milestone move` runs after this sync): warn and leave its title, description, and dependencies unchanged; when it is not closed and its title, description, or `Depends on:` list differs from the file, also run `gin task comment <epic> "[gin roadmap] <roadmap path> now says: <one line per difference: title, description, dependencies added or removed>. Bead left unchanged; the next /discuss <epic> reads this comment."`, unless the epic's most recent `[gin roadmap]` comment (`gin task comments <epic> --json`) has the same text; a closed epic gets no comment; a failed comment is reported and the sync continues; with the markdown task backend there are no comments: say so in one sentence;
     ```
  3. In line 38 (step 7), replace `dependency changes,` with `dependency changes, epics that received a `[gin roadmap]` comment,`.
  4. Run `python3 -m pytest tests/workflow_core/test_epic_comments.py`: all pass.
  5. Commit: `feat(roadmap): comment in-progress epics whose roadmap entry changed (epic-comments)`.
- **Interfaces**: consumes `gin task comments <epic> --json` (`text` of the newest `[gin roadmap]` comment); produces `[gin roadmap]` comments.
- **Acceptance criteria**: US-4; the two tests pass.
- **Estimated complexity**: low

### Track 5: Documentation (R6)
- **Dependencies**: Track 4
- **Files**:
  - Modify `docs/concepts/lifecycle.md:21` (after the `/roadmap` paragraph)
  - Modify `docs/reference/cli.md:329-335` (the `gin task` paragraph)
- **Provider role**: `docs`
- **Model:** `haiku`
- **Effort:** `low`
- **Why:** two short paragraphs with the content fixed by the spec.
- **Steps**:
  1. In `docs/concepts/lifecycle.md`, add after the paragraph at line 21 (the one starting `` `/roadmap` runs before the stages ``):
     ```
     Epic comments carry change across epics. When `ship` closes an epic, it adds a `[gin ship]` comment (merge commit, design doc) to every open epic that depends on it; when `/roadmap` re-runs and an `in_progress` or adopted epic's entry changed, it adds a `[gin roadmap]` comment listing the differences and leaves the bead unchanged. `/discuss <epic-id>` reads the description and then the comments in time order, summarises the current understanding, and asks you to confirm it first; the spec ends `## Goal and scope` with `Comments considered: <count>, latest <timestamp>`. `plan` summarises the comments newer than that line and asks whether to return to discuss. Comments are advisory: no gate reads them, and the markdown task backend has none.
     ```
  2. In `docs/reference/cli.md`, in the `gin task` paragraph after the sentence that lists the markdown subset (`... with `bd`-shaped `--json` output.`), add:
     ```
      `comments <id> --json` and `comment <id> "<text>"` reach `bd` with the Beads backend and do not exist with `markdown`; `discuss`, `plan`, `ship`, and `/roadmap` use them for epic comments (see `docs/concepts/lifecycle.md`).
     ```
  3. Run `python3 -m pytest tests/workflow_core/test_epic_comments.py tests/workflow_core/test_token_budget.py` (docs are outside the chains; the run confirms nothing regressed).
  4. Commit: `docs: epic comments across ship, roadmap, discuss, and plan (epic-comments)`.
- **Interfaces**: none.
- **Acceptance criteria**: both files name the four stages, the two prefixes, `Comments considered:`, and the markdown-backend gap.
- **Estimated complexity**: low

## Integration
- **Branch**: `feat/epic-comments`
- **Merge strategy**: sequential

## Validation
- [ ] `python3 -m pytest tests/workflow_core/test_epic_comments.py tests/workflow_core/test_role_aware_skills.py tests/workflow_core/test_token_budget.py` passes
- [ ] `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -c "from pathlib import Path; from workflow_core.budget import stage_chars; src=Path('plugins/gin-workflow/src'); print({s: stage_chars(src, s) for s in ('discuss','plan','ship')})"` prints every value at or under 12000
- [ ] Manual: on the Beads backend, `gin task comment <open epic> "test comment"`, run `/discuss <epic>`, confirm the summary is asked first and the spec gets `Comments considered: 1, latest <timestamp>`; then `gin task comments <epic>` and remove the test comment

## Notes
- `Model:` and `Effort:` are chosen from the main harness catalog (`haiku`, `sonnet`, `opus`; `low`…`max`) using the route rubric.
- The user may override `Model:` and `Effort:` before plan approval.
- Deliverable merge-holds apply exclusively to the Parent Bead. Individual track beads close upon passing tests and code review.
