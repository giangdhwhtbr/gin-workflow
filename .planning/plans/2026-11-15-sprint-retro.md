# Plan: Sprint retro before the milestone close

Epic: gin-workflow-sprint-retro
Spec: `.planning/specs/2026-11-15-sprint-retro-design.md`

## Objective

`/gin:retro [--milestone <id>]` shows a member their part of an open milestone, asks three questions, and after the member confirms writes one `[gin retro]` comment on the milestone bead, which the milestone close (`gin-workflow-milestone-close`) will read.

Goal: before a milestone closes, each member records what went well, what slowed the work, and what to change. This epic only collects the answers.

Architecture: one new skill file, `plugins/gin-workflow/src/skills/retro/SKILL.md`, using existing commands (`gin milestone list/show`, `gin task show/list/comment`, `gin team sync`, `gin state`). No Python change.

Tech stack: Markdown skill under `plugins/gin-workflow/src/skills/`, `unittest` tests run by `pytest`.

Global constraints (from the spec):

- The answers carry the member's name; a re-run adds a comment and the newest one per member counts.
- The comment format is the contract the close parses: first line `[gin retro] <milestone-id> <member>`, then `Went well:`, `Slowed us:`, `Change next:`, labels never translated.
- No `gin` CLI command, Beads field, scores, anonymity, summaries, or gin-console change.

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
- Problem statement: members have no place or guided way to record a retro before the milestone close reads it.
- Success criteria: US-1 to US-4 of the spec hold in the skill text; the tests below pass; `python3 -m pytest -n auto` passes.
- Constraints: the global constraints; the frontmatter descriptions of all skills stay within 4,000 characters (`tests/workflow_core/test_token_budget.py:209-210`, 3,842 used today), so the new description has at most 150 characters.
- Non-goals: the out-of-scope list of the spec.

## Approach Options
### Option 1: Skill only
- Summary: a skill that reads with existing commands and writes with `gin task comment`.
- Pros: no code; follows `[gin accept]`, `[gin roadmap]`, and `[gin answer]`; the close reads with `gin task comments --json`.
- Cons: the format is checked only by the skill's instructions and its test.

### Option 2: Skill plus a `gin milestone retro` command
- Summary: the CLI validates milestone, member, and format, then writes.
- Pros: stricter format.
- Cons: parser, CLI, and tests for a contract with one writer and no reader yet.

### Recommended Approach
- Selected option: Option 1, as confirmed in discuss.
- Rationale: smallest change; a CLI can come with the close if parsing needs it.

## Scope
- In scope: `plugins/gin-workflow/src/skills/retro/SKILL.md`, its tests, the packaging list, and one row in `docs/reference/skills.md` and `docs/reference/skills.vi.md`.
- Out of scope: everything the spec lists as out of scope; `plugins/*/dist/` (built by `install.sh`).

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: One track; the skill, its tests, and its docs row change together.
```

## Tasks

### Track 1: Retro skill
- **Dependencies**: none
- **Files**:
  - Create `plugins/gin-workflow/src/skills/retro/SKILL.md`
  - Modify `docs/reference/skills.md:51` (new row after `allocate`)
  - Modify `docs/reference/skills.vi.md` (the matching row after `allocate`)
  - Test `tests/workflow_core/test_skill_routing.py` (new test next to the allocate tests, around line 189)
  - Test `tests/gin_orchestrator/test_harness_packaging.py:23-90` (add the skill to `REQUIRED_ARTIFACTS`)
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** one new instruction file with its exact text given below, plus tests and a docs row; bounded by a clear spec.
- **Acceptance criteria**: US-1 to US-4 of the spec are in the skill; the tests named in step 5 pass; `description_chars` stays at or under 4,000.
- **Estimated complexity**: low

Interfaces consumed: `gin state --format json` (`project.team.enabled`, `project.team.me`), `gin milestone list --json` (`status`), `gin milestone show <id> --json` (epic rows: `id`, `title`, `status`, `estimate_days`, `warnings[].code == "open_bugs"` with `count`), `gin task show <epic> --json` (`started_at`, `closed_at`), `gin task list --parent <epic> --all --json` (`assignee`), `gin task comment <id> "<text>"`, `gin team sync`. Interface produced: the comment format of the spec.

Steps:

1. Failing tests first.
   - In `tests/workflow_core/test_skill_routing.py`, after `test_prep_catalog_lists_the_five_types`, add:
     ```python
     def test_retro_records_one_comment_on_an_open_milestone(self):
         text = (SRC / "skills/retro/SKILL.md").read_text(encoding="utf-8")
         for needle in ("[gin retro] <milestone-id> <member>", "Went well:", "Slowed us:", "Change next:",
                        "gin task comment <milestone-id>", "gin milestone show <id> --json",
                        "`status` is `active`", "project.team.me", "gin team sync",
                        "Write nothing until the member confirms", "the newest one counts",
                        "its close already read the retros", "Never translate the labels"):
             with self.subTest(needle=needle):
                 self.assertIn(needle, text)
         self.assertLess(text.index("Went well:"), text.index("Slowed us:"))
         self.assertLess(text.index("Slowed us:"), text.index("Change next:"))
         for banned in ("sonnet", "opus", "haiku"):
             self.assertNotIn(banned, text.lower())
     ```
   - In `tests/gin_orchestrator/test_harness_packaging.py`, add `"skills/retro/SKILL.md",` to `REQUIRED_ARTIFACTS` after `"skills/review/SKILL.md",` (line 40).
   - Run `python3 -m pytest tests/workflow_core/test_skill_routing.py tests/gin_orchestrator/test_harness_packaging.py tests/workflow_core/test_docs_coverage.py -q`; expected: the new routing test, the packaging test, and `test_every_skill_is_in_the_skills_reference` fail once the skill directory exists (step 2), the first two fail now.

2. Create `plugins/gin-workflow/src/skills/retro/SKILL.md` with exactly this content (the outer `~~~` fence is not part of the file):
   ~~~markdown
   ---
   name: retro
   description: Record one member's retro on an open milestone (went well, slowed the work, change next) as a comment for the milestone close.
   ---

   # Retro

   On `/retro` only. Outside the lifecycle: it records no gate. One question per message. Write nothing until the member confirms the comment.

   ## Before you start
   1. If `.agent-workflow/generated/effective-config.yaml` does not exist in the main checkout (the parent of `git rev-parse --path-format=absolute --git-common-dir`), stop: tell the user to run `/setup` once and do nothing else.
   2. Milestones and comments need the Beads task backend. With another backend, say so in one sentence and stop.

   ## Steps
   1. Member. Read `gin state --format json`. With `project.team.enabled`, the member is the email of `project.team.me`; when it is null, stop and name the git email (`git config user.email`) that is not a member. Without team mode, the member is `git config user.name`. In team mode with `team.beads_sync` set in `.agent-workflow/config.yaml` of the main checkout, run `gin team sync` first.
   2. Milestone. With `--milestone <id>`, use it. Otherwise use the only milestone whose `status` is `active` in `gin milestone list --json`; with none or several, list the open milestones (id, title, period, status) and ask which one. Run `gin milestone show <id> --json`; on a non-zero exit, report its message and stop. A closed milestone: write nothing and say its close already read the retros.
   3. The member's part. From the epic rows of `gin milestone show <id> --json`, list each epic with `title`, `status`, `estimate_days`, and the `count` of its `open_bugs` warning (0 without one). Add the working days, Monday to Friday, from `started_at` to `closed_at` of `gin task show <epic> --json`, or to today when the epic is open; `not started` without `started_at`. In team mode keep only the epics with a track whose `assignee` is the member (`gin task list --parent <epic> --all --json`) and say how many other epics the milestone has. This list helps the member remember; it never goes into the comment.
   4. Questions, one per message, in this order: what went well; what slowed the work; what to change in the next milestone. Ask nothing else and suggest no answer. The member may skip a question; write `-` for it.
   5. Comment. Show the exact text and ask the member to confirm or edit it:
      ```
      [gin retro] <milestone-id> <member>
      Went well: <answer>
      Slowed us: <answer>
      Change next: <answer>
      ```
      Replace line breaks inside an answer with `; `. Never translate the labels, whatever language the answers use: the milestone close parses them.
   6. Write. After the member confirms, run `gin task comment <milestone-id> "<text>"`. On a non-zero exit, report the error, show the text again so the member can retry, and write nothing else. In team mode with `team.beads_sync` set, run `gin team sync`; without it, say that other members see the comment only on this runner's database.
   7. Report the milestone, the member, and that the comment was written. A member who runs `/retro` again adds a new comment, and the newest one counts.
   ~~~

3. Docs rows.
   - `docs/reference/skills.md`, after the `allocate` row (line 51):
     `| \`retro\` | Record one member's retro on an open milestone as a \`[gin retro]\` comment on the milestone bead: the member sees their epics with estimates and actual days, answers what went well, what slowed the work, and what to change, and confirms the text; a re-run adds a comment and the newest one counts |`
   - `docs/reference/skills.vi.md`, after its `allocate` row, the same row in Vietnamese with code and labels verbatim:
     `| \`retro\` | Ghi retro của một member trên một milestone đang mở thành comment \`[gin retro]\` trên bead milestone: member xem các epic của mình kèm estimate và số ngày thực tế, trả lời điều gì làm tốt, điều gì làm chậm, nên đổi gì, rồi xác nhận nội dung; chạy lại thì thêm comment mới và comment mới nhất có hiệu lực |`
   - Match the column layout of the neighbouring rows exactly.

4. Check the description budget: `cd plugins/gin-workflow/src/scripts && python3 -c "from pathlib import Path; from workflow_core.budget import description_chars; print(description_chars(Path('..')))"`; expected: at most 4000.

5. Run `python3 -m pytest tests/workflow_core/test_skill_routing.py tests/gin_orchestrator/test_harness_packaging.py tests/workflow_core/test_docs_coverage.py tests/workflow_core/test_docs_check.py tests/workflow_core/test_token_budget.py -q`; expected: all pass. Commit: `feat(skills): /retro records one member's milestone retro as a [gin retro] comment (gin-workflow-sprint-retro)`.

## Integration
- **Branch**: feat/sprint-retro
- **Merge strategy**: sequential

## Validation
- [ ] `python3 -m pytest -n auto` passes (the pre-push hook runs it at ship)
- [ ] `description_chars` at most 4,000
- [ ] After `./install.sh`, `/gin:retro` appears in Claude Code and, run against an active milestone, writes one `[gin retro]` comment after confirmation (manual, by the user)

## Notes
- Parent Bead: `gin-workflow-sprint-retro` stays open until the human-confirmed merge. The track bead closes after tests and review pass.
- `gin team sync` exits non-zero when `team.beads_sync.remote` is not set (`plugins/gin-workflow/src/scripts/workflow_core/team_cli.py:302`), so the skill runs it only when `team.beads_sync` is set, as `/allocate` does.
- Solo work: no push before the epic is complete; ship merges locally and pushes once.
