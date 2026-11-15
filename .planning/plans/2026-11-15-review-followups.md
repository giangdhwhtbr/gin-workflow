# Plan: Follow-ups from the legacy-inventory, sprint-retro, and milestone-close reviews

Epic: gin-workflow-4p75
Spec: `.planning/specs/2026-11-15-review-followups-design.md`

## Objective

Every review note listed in the spec is applied as exact text in the roadmap references, the tech-doc skill and its JVM data reference, the retro and milestone-close skills, and the docs pages, with test needles for the new rules and every existing asserted sentence kept.

Goal: make each skill rule and documentation sentence named by the reviews exact.

Architecture: text edits in instruction and documentation files, plus test needles. No Python change.

Tech stack: Markdown skills, references, and docs; `unittest` tests run by `pytest`.

Global constraints (from the spec):

- `plugins/gin-workflow/src/skills/roadmap/SKILL.md` is not edited.
- No command, format (`[gin retro]`, `[gin close]`), or gin-console change.
- `manager-view.md` and `milestone-plan.md` stay at or under 4,000 characters.
- A changed sentence that a test asserts changes with its test in the same commit; every other asserted sentence stays verbatim.

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
- Problem statement: review notes left rules ambiguous or docs inaccurate in four modules.
- Success criteria: each edit below is in place; the tests of step 6 pass; `python3 -m pytest -n auto` passes.
- Constraints: the global constraints.
- Non-goals: the spec's out-of-scope list.

## Approach Options
### Option 1: One track
- Summary: all edits in one track and one review.
- Pros: the edits are small and exact; one review reads them together; `docs/reference/skills.md` and `.vi.md` are touched by three modules and stay in one track.
- Cons: about 14 files in one diff.

### Option 2: One track per module
- Summary: four tracks (roadmap, tech-doc, retro, milestone-close).
- Pros: smaller diffs.
- Cons: four reviews for minor edits; the skills reference rows would be split across tracks or moved into one of them.

### Recommended Approach
- Selected option: Option 1.
- Rationale: the text is given verbatim below, so one review is enough and no file is shared between tracks.

## Scope
- In scope: the files in Track 1's Files block.
- Out of scope: the spec's out-of-scope list; `plugins/*/dist/`.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: One track with exact text edits across four modules.
```

## Tasks

### Track 1: Review follow-ups
- **Dependencies**: none
- **Files**:
  - Modify `plugins/gin-workflow/src/skills/roadmap/references/manager-view.md:11-26`
  - Modify `plugins/gin-workflow/src/skills/roadmap/references/milestone-plan.md` (Write block)
  - Modify `plugins/gin-workflow/src/skills/tech-doc/SKILL.md:17` (roles table, Writer row)
  - Modify `plugins/gin-workflow/src/skills/tech-doc/references/jvm-data.md` (Schema files block)
  - Modify `plugins/gin-workflow/src/skills/retro/SKILL.md:16`
  - Modify `plugins/gin-workflow/src/skills/milestone-close/SKILL.md:58,73`
  - Modify `docs/starters/brownfield.md:225`, `docs/starters/brownfield.vi.md:225`
  - Modify `docs/guides/customizing-templates.md:133`, `docs/guides/customizing-templates.vi.md:133`
  - Modify `docs/reference/skills.md:50,52,53`, `docs/reference/skills.vi.md` (the `roadmap`, `retro`, `milestone-close` rows)
  - Test `tests/workflow_core/test_skill_routing.py`
  - Test `tests/workflow_core/test_tech_doc_skill.py:54,122-131`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** exact text edits across several files with tests that assert sentences; the care is in keeping asserted sentences and the character caps.
- **Acceptance criteria**: every edit below is in place verbatim; the tests of step 6 pass; `manager-view.md` and `milestone-plan.md` are at or under 4,000 characters.
- **Estimated complexity**: medium

Steps:

1. Failing tests first.
   - `tests/workflow_core/test_tech_doc_skill.py:54`: the asserted sentence becomes "`13-CAPABILITIES.md` starts after `02-FEATURES.md`, `05-API.md`, and `12-DATABASE.md` when written".
   - `tests/workflow_core/test_tech_doc_skill.py:130`: add `"R__"` to the `jvm-data.md` tuple.
   - `tests/workflow_core/test_skill_routing.py`:
     - In `test_roadmap_manager_view_and_milestone_plan`, add assertions on `manager-view.md`: "asks for, or proposes, both the `Outcome:` and the `Demo:`", "a name mapped to it", "the epics it set into each one".
     - In `test_retro_records_one_comment_on_an_open_milestone`, add the needle "When its `status` is `closed`".
     - In `test_milestone_close_moves_spillover_and_records_the_result`, add the needles "one `Action:` line per confirmed action" and "lists only the epics it moved itself".
   - Run `python3 -m pytest tests/workflow_core/test_skill_routing.py tests/workflow_core/test_tech_doc_skill.py -q`; expected: the new needles fail.

2. Roadmap references.
   - `manager-view.md`, end of the `## Outcome and Demo` paragraph, append: " `/roadmap --milestone <id>` asks for, or proposes, both the `Outcome:` and the `Demo:` of the milestone before it proposes the adoption."
   - `manager-view.md`, after the paragraph "When presenting, ask the PM about every `unplanned` capability once, ...", add a paragraph: "Rows use the names of the Capability Catalog. An epic covers a row when its `Capabilities:` names the catalog name or a name mapped to it. With `project.layout: sdd`, each name of `docs/specs/README.md` that matches no catalog name goes into the same question, for the PM to map to a catalog name; the report lists each name left unmapped."
   - `manager-view.md`, end of the `## Report` paragraph, append: " With a milestone plan, it also names each milestone the run created and the epics it set into each one."
   - `milestone-plan.md`, Write block, replace the first paragraph with:
     "In step 5, after the PM confirms and before the file is written, run the team permission check of `--milestone` step 1. Then run `gin milestone create "<title>" --start <date> --end <date>` for each milestone of the plan whose title `gin milestone list --json` lacks; it prints the new id. A failure stops before the file is written; report it as in `--milestone` step 5. A created milestone holds no epic until step 6: a rejected roadmap PR leaves empty milestones, reused by title next run. Step 5 then writes each milestone block as `--milestone` step 4 describes."
   - `milestone-plan.md`, replace the adopted-epic paragraph with:
     "The adopted-epic rule of step 6 covers only epics that existed before this run. An epic the sync creates gets its title, description, and `Depends on:` dependencies. An existing `open` epic the plan allocates keeps its bead unchanged, as with `--milestone`."
   - Check: `python3 -c "from pathlib import Path; [print(p, len(Path(p).read_text(encoding='utf-8'))) for p in ('plugins/gin-workflow/src/skills/roadmap/references/manager-view.md', 'plugins/gin-workflow/src/skills/roadmap/references/milestone-plan.md')]"`; expected: both at most 4000 (`milestone-plan.md` about 3,954).

3. Tech-doc.
   - `tech-doc/SKILL.md:17`, Writer row: "`13-CAPABILITIES.md` starts after `02-FEATURES.md`, `05-API.md`, and `12-DATABASE.md`" becomes "`13-CAPABILITIES.md` starts after `02-FEATURES.md`, `05-API.md`, and `12-DATABASE.md` when written".
   - `jvm-data.md`, Schema files block, after the bullet that searches DDL, Flyway, and Liquibase, add: "- Search Flyway repeatable migrations `R__*.sql`; they run again whenever their checksum changes and usually hold views, procedures, and functions. The latest version of each file wins."

4. Retro and milestone close.
   - `retro/SKILL.md:16`: "A closed milestone: write nothing and say its close already read the retros." becomes "When its `status` is `closed`, write nothing and say its close already read the retros."
   - `milestone-close/SKILL.md:58`, after "A re-run continues: moved epics are no longer in the milestone, and a closed milestone is refused, so after a stop past step 5 finish the rest by hand from the report." add: " A resumed run lists only the epics it moved itself in `Spillover:`; its report says that moves of the earlier run are not in the comment."
   - `milestone-close/SKILL.md:73`: "One `Spillover:` line per moved epic and one `Action:` line per action; none when there are none." becomes "One `Spillover:` line per moved epic and one `Action:` line per confirmed action, so a `remember` fact the PM did not choose gets none; none when there are none."

5. Docs.
   - `docs/starters/brownfield.md:225`: "The roadmap file then shows the outcome and demo of each milestone and, when `13-CAPABILITIES.md` exists, the legacy coverage." becomes "When you give a milestone plan, the roadmap file then shows the outcome and demo of each milestone. When `13-CAPABILITIES.md` exists, it also shows the legacy coverage."
   - `docs/starters/brownfield.vi.md:225`: "File roadmap sau đó hiển thị outcome và demo của từng milestone và, khi có `13-CAPABILITIES.md`, phần legacy coverage." becomes "Khi bạn đưa kế hoạch milestone, file roadmap sau đó hiển thị outcome và demo của từng milestone. Khi có `13-CAPABILITIES.md`, file còn hiển thị phần legacy coverage."
   - `docs/guides/customizing-templates.md:133`: "the `Outcome:` and `Demo:` lines of each milestone," becomes "the `Outcome:` and `Demo:` lines of each milestone when a milestone plan is given,". `.vi.md:133`: "các dòng `Outcome:` và `Demo:` của mỗi milestone," becomes "các dòng `Outcome:` và `Demo:` của mỗi milestone khi có kế hoạch milestone,".
   - `docs/reference/skills.md`, `roadmap` row, second cell becomes: "Turn the tech-doc set or a product brief into a confirmed roadmap and dependent Beads epics, with a project deadline and an estimate per epic. Re-runs reconcile both. It proposes the team's way of working (Foundation, Spec cadence, Build, Integration, Quality, Load) for the PM to confirm, rates each epic's complexity, and reports the `gin milestone list` forecast. The file has a `## Summary` table, `Features:` and `Legacy:` per epic, and a `## Legacy coverage` table when `13-CAPABILITIES.md` exists; with the SDD layout each epic carries `Capabilities:`. A plain run proposes the milestone plan and the `Outcome:` and `Demo:` of each milestone. `--milestone <id>` plans one dated milestone with its own lanes, a `Spec ready by:` date, and an integration point."
   - `docs/reference/skills.vi.md`, `roadmap` row, second cell becomes: "Biến bộ tech-doc hoặc một product brief thành roadmap đã xác nhận cùng các epic Beads phụ thuộc nhau, kèm hạn chót dự án và ước lượng cho mỗi epic. Khi chạy lại, skill đối chiếu cả hai. Skill đề xuất cách làm việc của team (Foundation, Spec cadence, Build, Integration, Quality, Load) để PM xác nhận, đánh giá độ phức tạp của từng epic và báo cáo dự báo của `gin milestone list`. File có bảng `## Summary`, `Features:` và `Legacy:` cho mỗi epic, và bảng `## Legacy coverage` khi có `13-CAPABILITIES.md`; với layout SDD mỗi epic mang dòng `Capabilities:`. Lần chạy không kèm tham số đề xuất kế hoạch milestone cùng `Outcome:` và `Demo:` của từng milestone. `--milestone <id>` lập kế hoạch cho một milestone có ngày với lane riêng, ngày `Spec ready by:` và integration point."
   - `retro` and `milestone-close` rows of both files: append to the second cell " A milestone is `active` only after `gin milestone kickstart`; without it, the skill asks which milestone." (English) and " Milestone chỉ `active` sau `gin milestone kickstart`; nếu chưa kickstart, skill hỏi chọn milestone." (Vietnamese), before the closing `|`.

6. Run `python3 -m pytest tests/workflow_core/test_skill_routing.py tests/workflow_core/test_tech_doc_skill.py tests/workflow_core/test_token_budget.py tests/workflow_core/test_specs.py tests/workflow_core/test_docs_coverage.py tests/workflow_core/test_docs_check.py tests/workflow_core/test_walkthrough_docs.py tests/gin_orchestrator/test_harness_packaging.py -q`; expected: all pass. Commit: `docs(skills): apply the legacy-inventory, retro, and milestone-close review notes (gin-workflow-4p75)`.

## Integration
- **Branch**: feat/review-followups
- **Merge strategy**: sequential

## Validation
- [ ] `python3 -m pytest -n auto` passes (the pre-push hook runs it at ship)
- [ ] `manager-view.md` and `milestone-plan.md` at or under 4,000 characters

## Notes
- Parent Bead: `gin-workflow-4p75` stays open until the human-confirmed merge; the track bead closes after tests and review pass.
- Solo work: no push before the epic is complete; ship merges locally and pushes once.
