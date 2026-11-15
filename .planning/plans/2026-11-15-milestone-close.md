# Plan: Guided milestone close

Epic: gin-workflow-milestone-close
Spec: `.planning/specs/2026-11-15-milestone-close-design.md`

## Objective

`/gin:milestone-close [<milestone-id>]` summarises a milestone, moves every open epic to the next milestone with a reason and a decision, writes a `[gin close]` comment, closes the milestone, and records the result, the way-of-working changes, and the lessons in the roadmap file and the knowledge records, applying the confirmed estimates.

Goal: a PM or tech lead closes a milestone in one guided run, and what it delivered and what the team learned are recorded where people, agents, and gin-console read them.

Architecture: one new skill file using existing commands (`gin milestone list/show/create/move/estimate/close`, `gin usage report`, `gin task show/comments/comment/remember`, `gin team sync`), a `Result:` line in the roadmap template, a keep-`Result:` rule in the roadmap manager-view reference, and a raised description budget. No Python change.

Tech stack: Markdown skill and template under `plugins/gin-workflow/src/`, `unittest` tests run by `pytest`.

Global constraints (from the spec):

- The `gin milestone` CLI and its `schema: 1` JSON do not change.
- Every open epic moves to the next milestone: the open milestone with the earliest `start` after the closing milestone's `start`.
- Retros are optional.
- Nothing is written before the person running the close confirms the table.
- The `[gin close]` labels are a contract that gin-console parses; they are never translated.

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
- Problem statement: closing a milestone with open epics needs manual moves, and nothing records what it delivered or what the team learned.
- Success criteria: US-1 to US-6 of the spec hold in the skill text; the tests in step 6 pass; `python3 -m pytest -n auto` passes.
- Constraints: the global constraints; `description_chars` is 3,968 today and the limit rises to 4,500.
- Non-goals: the out-of-scope list of the spec.

## Approach Options
### Option 1: One skill, existing commands
- Summary: the skill orchestrates existing CLI commands and writes text records.
- Pros: no code, no JSON contract change; gin-console reads the comment through its bead comments API.
- Cons: the comment format is enforced by the skill and its test only.

### Option 2: A `gin milestone close --move-open-to` flag plus the skill
- Summary: the CLI moves open epics and stores a structured result.
- Pros: one atomic CLI call.
- Cons: CLI and contract changes for behaviour the existing commands already cover; rejected in discuss.

### Recommended Approach
- Selected option: Option 1, as confirmed in discuss.
- Rationale: smallest change; matches `/retro`.

## Scope
- In scope: `skills/milestone-close/SKILL.md`, `templates/roadmap.md`, `skills/roadmap/references/manager-view.md`, the description budget limit, tests, packaging, and the two docs rows.
- Out of scope: the spec's out-of-scope list; `plugins/*/dist/`.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: One track; the skill, the template line it writes, the keep rule, and the tests change together.
```

## Tasks

### Track 1: Milestone close skill
- **Dependencies**: none
- **Files**:
  - Create `plugins/gin-workflow/src/skills/milestone-close/SKILL.md`
  - Modify `plugins/gin-workflow/src/templates/roadmap.md:49-52` (`Result:` after `Demo:`)
  - Modify `plugins/gin-workflow/src/skills/roadmap/references/manager-view.md:11-12` (keep-`Result:` sentence in the Outcome and Demo block)
  - Modify `docs/reference/skills.md:52` (new row after `retro`)
  - Modify `docs/reference/skills.vi.md` (the matching row after `retro`)
  - Test `tests/workflow_core/test_skill_routing.py` (new test after `test_retro_records_one_comment_on_an_open_milestone`; one assertion in `test_roadmap_manager_view_and_milestone_plan`)
  - Test `tests/workflow_core/test_specs.py:390` (`Result:` in the roadmap template)
  - Test `tests/workflow_core/test_roadmap_file.py:49-64` (new case with a `Result:` block)
  - Test `tests/workflow_core/test_token_budget.py:209-210` (limit 4,500)
  - Test `tests/gin_orchestrator/test_harness_packaging.py:41` (add the skill after `skills/retro/SKILL.md`)
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** a new instruction file with its exact text below, one template line, one reference sentence, and test edits; bounded by a clear spec.
- **Acceptance criteria**: US-1 to US-6 of the spec are in the skill; the template and reference carry `Result:`; the tests of step 6 pass; `description_chars` is at most 4,500.
- **Estimated complexity**: medium

Interfaces consumed: `gin state --format json` (`project.layout`, `project.team.enabled`, `project.team.me.roles`, `project.team.permissions.milestone`), `gin milestone list --json` (`id`, `title`, `status`, `start`, `end`), `gin milestone show <id> --json` (`status`, `start`, `end`, `lanes`, epic rows `id`, `title`, `status`, `estimate_days`, `remaining_days`, `warnings[]` with `open_bugs` `count`), `gin usage report --milestone <id> --format json`, `gin task show <epic> --json` (`started_at`, `closed_at`), `gin task comments <id> --json`, `gin milestone create/move/estimate/close`, `gin task comment`, `gin task remember`, `gin team sync`. Interfaces produced: the `[gin close]` comment and the `Result:` block of the spec.

Steps:

1. Failing tests first.
   - `tests/workflow_core/test_skill_routing.py`, after `test_retro_records_one_comment_on_an_open_milestone`:
     ```python
     def test_milestone_close_moves_spillover_and_records_the_result(self):
         text = (SRC / "skills/milestone-close/SKILL.md").read_text(encoding="utf-8")
         for needle in ("[gin close] <milestone-id>", "Delivered:", "Spillover:", "Outcome:", "Demo:", "Retros:",
                        "Action:", "earliest `start` after", "`status` is `closed`", "team.permissions.milestone",
                        "Write nothing until the person running the close confirms", "no retros",
                        "reason (retro|asked)", "Reconcile steps of the `learn` skill", "gin task remember",
                        "milestone-close/<milestone-id>", "Never translate the labels"):
             with self.subTest(needle=needle):
                 self.assertIn(needle, text)
         write = text[text.index("## Write"):]
         order = [write.index(step) for step in ("gin milestone create", "gin milestone move", "gin milestone estimate",
                                                 "gin task comment", "gin milestone close")]
         self.assertEqual(sorted(order), order)
         for banned in ("sonnet", "opus", "haiku"):
             self.assertNotIn(banned, text.lower())
     ```
   - In `test_roadmap_manager_view_and_milestone_plan`, add `self.assertIn("written by `/milestone-close`", (roadmap / "references/manager-view.md").read_text(encoding="utf-8"))`.
   - `tests/workflow_core/test_specs.py`: add `"Result:"` to the needle tuple at line 390.
   - `tests/workflow_core/test_roadmap_file.py`: after `test_manager_view_sections_change_neither_deadline_nor_lanes`, add `test_result_block_changes_neither_deadline_nor_lanes`, the same shape with `"## Milestone: M1\n\nOutcome: Shop live\nDemo: Browse and buy\nResult: closed 2027-01-29; delivered 2 of 3 epics; 1 moved to M2\n- Outcome: partial; checkout pending\n- Spillover: Checkout: payment API late; re-estimate\n\n"` as the extra text.
   - `tests/workflow_core/test_token_budget.py:210`: `4_000` becomes `4_500`.
   - `tests/gin_orchestrator/test_harness_packaging.py`: add `"skills/milestone-close/SKILL.md",` after `"skills/retro/SKILL.md",`.
   - Run `python3 -m pytest tests/workflow_core/test_skill_routing.py tests/workflow_core/test_specs.py tests/gin_orchestrator/test_harness_packaging.py -q`; expected: the new and changed assertions fail.

2. Create `plugins/gin-workflow/src/skills/milestone-close/SKILL.md` with exactly this content (the outer `~~~` fence is not part of the file):
   ~~~markdown
   ---
   name: milestone-close
   description: Close a milestone in one guided run: summarise it, move open epics to the next milestone with reasons, record the result, apply actions.
   ---

   # Milestone close

   On `/milestone-close` only. Outside the lifecycle: it records no gate. One question per message. Write nothing until the person running the close confirms the table.

   ## Before you start
   1. If `.agent-workflow/generated/effective-config.yaml` does not exist in the main checkout (the parent of `git rev-parse --path-format=absolute --git-common-dir`), stop: tell the user to run `/setup` once and do nothing else.
   2. Milestones need the Beads task backend. With another backend, say so in one sentence and stop.
   3. Read `gin state --format json`. In team mode, when `project.team.permissions.milestone` lists roles and none is in `project.team.me.roles`, or `project.team.me` is null, stop and name the roles (`team.permissions.milestone`). With `team.beads_sync` set in `.agent-workflow/config.yaml` of the main checkout, run `gin team sync` first.

   ## Milestone
   With an id, use it. Otherwise use the only milestone whose `status` is `active` in `gin milestone list --json`; with none or several, list the open milestones (id, title, period, status) and ask which one. Run `gin milestone show <id> --json`; on a non-zero exit report its message and stop. When its `status` is `closed`, write nothing and say so. Before its `end`, say the close is early and ask whether to continue.

   ## Summary
   Show, without writing:
   - Delivered: the closed epics of the milestone.
   - Open epics with `remaining_days`, and per epic the `count` of its `open_bugs` warning (0 without one).
   - Per epic, `estimate_days` against the working days, Monday to Friday, from `started_at` to `closed_at` of `gin task show <epic> --json` (to today when open; `not started` without `started_at`).
   - Cost and rework (reopens, bugs found later, review cycles) from `gin usage report --milestone <id> --format json`; on a non-zero exit, report it and continue without them.
   - The milestone's `Outcome:` and `Demo:` from the roadmap file (`.planning/roadmap.md`, or `docs/roadmap.md` with `project.layout: sdd`); propose `reached`, `partial`, or `missed` for each with a one-line note, or `not planned` when the file or the line is missing.
   - Retros: the newest `[gin retro]` comment per member from `gin task comments <id> --json`; with none, say `no retros`. Retros are optional.

   ## Next milestone
   The next milestone is the open milestone in `gin milestone list --json` with the earliest `start` after this milestone's `start`. With none, propose a new one starting the first working day after this milestone's `end`, with the same number of working days, and ask the PM for its title; it is created in Write, after confirmation.

   ## Spillover
   Every open epic moves to the next milestone. For each one:
   1. Reason. Quote the retro line (`Slowed us:` or `Went well:`) that names the epic id or title, marked `retro`. Without one, ask the person running the close for the reason, one epic per message, marked `asked`.
   2. Decision. Propose one: keep as is; re-estimate with new remaining days; split, done later with `/roadmap` or `/discuss <epic>`; or remove a named blocker.

   When the moved epics take the next milestone over its capacity (the bound of the Load block of the roadmap skill's way of working), still move them; report the overflow in working days and propose what to do.

   ## Actions
   From the summary, the retros, and the spillover, propose actions, each with a kind:
   - `way_of_working`: the exact new text of a line in `## Way of working` of the roadmap file.
   - `estimate`: an epic and its new days.
   - `lesson`: a topic and a summary for a knowledge record.
   - `remember`: a short fact every session needs; propose it, and keep it only when the PM chooses it.

   ## Confirm
   Present one table: delivered epics; each spillover epic with its target milestone, reason (retro|asked), and decision; the `Outcome:` and `Demo:` results; the actions. Revise it until the person running the close confirms.

   ## Write
   In this order, after confirmation. A failing step stops the run; report what was written. A re-run continues: moved epics are no longer in the milestone, and a closed milestone is refused, so after a stop past step 5 finish the rest by hand from the report.
   1. When proposed, `gin milestone create "<title>" --start <date> --end <date>`; it prints the new id.
   2. `gin milestone move <epic>... --to <next-id>` for the spillover epics.
   3. `gin milestone estimate <epic> <days>` for each `estimate` action.
   4. `gin task comment <milestone-id> "<text>"` with this text:
      ```
      [gin close] <milestone-id>
      Delivered: <epic-id>, <epic-id>
      Spillover: <epic-id> -> <milestone-id>; reason (retro|asked): <text>; decision: <text>
      Outcome: reached|partial|missed|not planned; <note>
      Demo: reached|partial|missed|not planned; <note>
      Retros: <count>
      Action: way_of_working|estimate|lesson|remember; <text>
      ```
      `Delivered:` is `none` when no epic closed. One `Spillover:` line per moved epic and one `Action:` line per action; none when there are none. Replace line breaks inside a value with `; `. Never translate the labels: gin-console and later runs parse them.
   5. `gin milestone close <milestone-id> --reason "Delivered <n> of <m> epics; <k> moved to <next-id>"`.
   6. On branch `milestone-close/<milestone-id>` of the main checkout's repository: in the roadmap file, write the milestone's `Result:` block and apply each `way_of_working` action to `## Way of working`; write or update each `lesson` as `.planning/knowledge/<topic>.md` following the Reconcile steps of the `learn` skill (search first, update instead of duplicating); commit. When `team.approvals.roadmap` in `.agent-workflow/config.yaml` lists roles, push and open the pull request as `/roadmap` step 5 does. Without a roadmap file, skip `Result:` and the way-of-working actions and say so; still write the lessons. The `Result:` block, in business words and without file paths:
      ```
      Result: closed <YYYY-MM-DD>; delivered <n> of <m> epics; <k> moved to <next milestone title>
      - Outcome: <reached|partial|missed|not planned>; <note>
      - Demo: <reached|partial|missed|not planned>; <note>
      - Spillover: <epic title>: <reason>; <decision>
      - Actions: <one line per action>
      ```
   7. `gin task remember "<fact>"` for each `remember` action the PM chose.
   8. With `team.beads_sync` set, `gin team sync`.

   ## Report
   The closed milestone, the next milestone and its load, each moved epic with its decision, the actions applied, the branch and commit (and pull request), and anything skipped. Next steps: `/progress --milestone <next-id>`, and `/roadmap` or `/discuss <epic>` for each epic to split.
   ~~~

3. `plugins/gin-workflow/src/templates/roadmap.md`: in the milestone block, add a line `Result:` right after `Demo:`.

4. `plugins/gin-workflow/src/skills/roadmap/references/manager-view.md`, end of the `## Outcome and Demo` block, add: "`Result:` under a milestone heading is written by `/milestone-close` when the milestone closes; a `/roadmap` run keeps it and the lines under it unchanged." Keep the file at or under 4,000 characters.

5. Docs rows.
   - `docs/reference/skills.md`, after the `retro` row: `| \`milestone-close\` | Close a milestone in one guided run: summary of delivered and open epics, estimates, cost, Outcome and Demo, and retros; every open epic moves to the next milestone (by start date) with a reason from the retros or asked, and a decision; after confirmation it writes a \`[gin close]\` comment, closes the milestone, writes \`Result:\` and way-of-working changes to the roadmap file and lessons to knowledge records, and sets new estimates |`
   - `docs/reference/skills.vi.md`, after its `retro` row, the same in Vietnamese with code and labels verbatim: `| \`milestone-close\` | Đóng một milestone trong một lần chạy: tổng hợp epic đã giao và còn mở, estimate, chi phí, Outcome và Demo, và retro; mọi epic còn mở chuyển sang milestone kế tiếp (theo ngày bắt đầu) kèm lý do lấy từ retro hoặc hỏi người chạy, và một quyết định; sau khi xác nhận, ghi comment \`[gin close]\`, đóng milestone, ghi \`Result:\` và thay đổi way of working vào file roadmap, ghi bài học vào knowledge record, và đặt estimate mới |`

6. Check `description_chars` (`cd plugins/gin-workflow/src/scripts && python3 -c "from pathlib import Path; from workflow_core.budget import description_chars; print(description_chars(Path('..')))"`; expected at most 4500). Run `python3 -m pytest tests/workflow_core/test_skill_routing.py tests/workflow_core/test_specs.py tests/workflow_core/test_roadmap_file.py tests/workflow_core/test_token_budget.py tests/workflow_core/test_docs_coverage.py tests/workflow_core/test_docs_check.py tests/gin_orchestrator/test_harness_packaging.py -q`; expected: all pass. Commit: `feat(skills): /milestone-close moves spillover to the next milestone and records the result (gin-workflow-milestone-close)`.

## Integration
- **Branch**: feat/milestone-close
- **Merge strategy**: sequential

## Validation
- [ ] `python3 -m pytest -n auto` passes (the pre-push hook runs it at ship)
- [ ] `description_chars` at most 4,500
- [ ] After `./install.sh`, `/gin:milestone-close` on a test milestone with one open epic moves it, writes the comment, and closes the milestone (manual, by the user)

## Notes
- Parent Bead: `gin-workflow-milestone-close` stays open until the human-confirmed merge. The track bead closes after tests and review pass.
- `gin milestone move` refuses to move out of a closed milestone, so the skill moves before it closes (`milestone_cli.py:322-323`).
- Solo work: no push before the epic is complete; ship merges locally and pushes once.
