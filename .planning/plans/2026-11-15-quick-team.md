# Plan: Quick in team mode

Epic: gin-workflow-quick-team
Spec: `.planning/specs/2026-11-15-quick-team-design.md`

## Objective

In team mode, `/gin:quick` started on the base branch pushes `quick/<slug>`, opens a pull request with the covering cases and the ship approval line, writes a `[gin quick]` comment on an epic or the active milestone, and syncs Beads; `gin team pending` lists open `quick/*` pull requests; `/gin:progress` and `/gin:milestone-close` read the comments.

Goal: a quick change in a team reaches the protected base branch through the team's approval, QA knows its covering cases, leads see it pending, and the PM sees it in progress.

Architecture: one candidate kind added to `workflow_core/team_pending.py`; the rest is skill and documentation text.

Tech stack: Python 3 (`workflow_core`), Markdown skills and docs, `unittest` tests run by `pytest`.

Global constraints (from the spec):

- Solo mode, and quick runs on an existing feature branch, behave as today.
- No bead per quick run; `[gin quick]` is a comment with English labels.
- Merging stays with the person who runs `gin team check --gate ship <pr-url>`.
- `team/SKILL.md` (5,984 of 6,000) is not changed.

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
- Problem statement: in team mode a quick change has no push, no pull request, no approval, no covering cases, and no shared record.
- Success criteria: US-1 to US-4 of the spec; the tests of each track pass; `python3 -m pytest -n auto` passes.
- Constraints: the global constraints; `stage-contract.md` is in every stage chain and the execute and ship chains are at 11,977 and 11,978 of 12,000 characters (`tests/workflow_core/test_token_budget.py`), so its edit must not grow the file.
- Non-goals: the spec's out-of-scope list.

## Approach Options
### Option 1: Skill text plus one `team pending` candidate kind
- Summary: the quick skill holds the team-mode end; `team_pending.candidates` adds `quick/*` heads.
- Pros: reuses the host commands of the team skill and the existing ship check; one small code change for visibility.
- Cons: the comment format is enforced only by the skill and its test.

### Option 2: A `gin quick ship` command
- Summary: the CLI pushes, opens the pull request per host, and writes the comment.
- Pros: one checked call.
- Cons: per-host code duplicating `team/references/hosts.md`; rejected in discuss.

### Recommended Approach
- Selected option: Option 1, as confirmed in discuss.
- Rationale: smallest change that meets every story.

## Scope
- In scope: the files of the two tracks.
- Out of scope: the spec's out-of-scope list; `plugins/*/dist/`.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Two small tracks with disjoint files; sequential keeps one review at a time.
```

## Tasks

### Track 1: `gin team pending` lists quick pull requests
- **Dependencies**: none
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team_pending.py:16,42-69,84-118`
  - Modify `docs/reference/cli.md` (the `pending` row of `gin team`)
  - Test `tests/workflow_core/test_team_pending.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** one new candidate kind in an existing function with established tests and fakes.
- **Acceptance criteria**: US-3 of the spec; the tests of step 4 pass.
- **Estimated complexity**: low

Interfaces: `candidates(root, team) -> list[tuple[str, str, str | None]]` gains kind `"quick"` for each remote head starting with `quick/`, epic `None`. `_GATES` maps `"quick"` to `"ship"`. In `pending()`, a `"quick"` row gets gate `"ship"` when `team_core.has_policy("ship", team)` is true, else gate `None` (approvers only, like a track row). Rows keep the existing keys.

Steps:

1. Failing tests in `tests/workflow_core/test_team_pending.py`, in `TestGateRows` (use the existing fakes; add `PR_QUICK = "https://github.com/org/app/pull/5"`):
   - `test_open_quick_pr_is_a_ship_row_without_an_epic`: `self.branches["quick/fix-typo"] = {}`; `self.gh(("quick/fix-typo", gh_pr(PR_QUICK, state="OPEN", author="em-dev", files=["web/login.tsx"])))`; expect one row `("ship", "quick/fix-typo", None, ["missing approval from one of qe"])` for `(gate, branch, epic, missing)`.
   - `test_quick_pr_without_ship_roles_lists_approvers_and_no_gate`: `self.configure("    ship: [qe]\n", "")`; same branch and PR with `reviews=[("binh-dev", "APPROVED", "c1")]`; expect `gate` None, `approvals` `["binh-dev"]`, `missing` `[]`.
   - `test_closed_or_absent_quick_pr_gives_no_row`: a `quick/old` head whose PR state is `MERGED`, and a `quick/none` head with no PR; expect `[]`.
   In `TestFiltersAndErrors`, `test_filters_leave_quick_rows_out`: a `quick/fix-typo` open PR and `self.bd(milestone_epics=("e-1",))`; `self.pending("--workflow-id", "e-1")` and `self.pending("--milestone", "m-1")` give no quick row; `self.pending()` gives it.
   Run `python3 -m pytest tests/workflow_core/test_team_pending.py -q`; expected: the new tests fail.

2. `team_pending.py`:
   - `_GATES`: add `"quick": "ship"`.
   - `candidates`: after the `plan/` line, add `found += [(head, "quick", None) for head in heads if head.startswith("quick/")]`; update the docstring to name remote `quick/*` heads.
   - `pending`: where the row is built, set `"gate": None if kind == "quick" and not team_core.has_policy("ship", team) else _GATES[kind]`. When `keep` is set, skip a `"quick"` candidate before the host lookup (`if keep is not None and kind == "quick": continue`), so a filtered run makes no host call for it; otherwise the existing filter would drop the row anyway, since `row["epic"]` stays `None`.
   - Update the `pending` docstring: quick rows are ship rows without an epic.

3. `docs/reference/cli.md`, `pending` row of `gin team`: add that it lists the open pull requests of remote `quick/*` branches as `ship` rows with `epic` null (no gate when `team.approvals.ship` has no policy), and that `--workflow-id` and `--milestone` leave them out.

4. Run `python3 -m pytest tests/workflow_core/test_team_pending.py tests/workflow_core/test_docs_coverage.py tests/workflow_core/test_docs_check.py -q`; expected: all pass. Commit: `feat(team): gin team pending lists open quick pull requests (gin-workflow-quick-team)`.

### Track 2: Quick skill team-mode end, readers, and docs
- **Dependencies**: none (disjoint files; runs after Track 1 by the sequential strategy)
- **Files**:
  - Modify `plugins/gin-workflow/src/skills/quick/SKILL.md` (step 7 and the opening line)
  - Modify `plugins/gin-workflow/src/references/stage-contract.md:34`
  - Modify `plugins/gin-workflow/src/skills/progress/SKILL.md:15` (Milestone bullet)
  - Modify `plugins/gin-workflow/src/skills/milestone-close/SKILL.md:25` (Summary list)
  - Modify `docs/concepts/lifecycle.md:125`
  - Modify `docs/guides/team.md` (a short "Quick in team mode" paragraph)
  - Modify `docs/reference/skills.md:23`, `docs/reference/skills.vi.md:23` (the `quick` row)
  - Test `tests/workflow_core/test_skill_routing.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** instruction and docs text with exact wording below; the care is the stage-contract budget and keeping solo behaviour.
- **Acceptance criteria**: US-1, US-2, US-4 of the spec; the tests of step 6 pass; every stage chain stays at or under its budget and `stage-contract.md` does not grow.
- **Estimated complexity**: medium

Steps:

1. Failing test in `tests/workflow_core/test_skill_routing.py`:
   ```python
   def test_quick_in_team_mode_pushes_opens_a_pr_and_records_a_comment(self):
       text = (SRC / "skills/quick/SKILL.md").read_text(encoding="utf-8")
       for needle in ("project.team.enabled", "--epic <id> | --milestone <id>", "[gin quick] <branch> <pr-url>",
                      "Summary:", "Files:", "Author:", "Cases:", "gin-qa cases plan <capability>",
                      "no covering cases found", "Needs ship approval: run gin team check --gate ship <pr-url> before merging.",
                      "team/references/hosts.md", "gin team sync", "In solo mode", "existing feature branch"):
           with self.subTest(needle=needle):
               self.assertIn(needle, text)
       self.assertIn("pushed only in team mode", (SRC / "references/stage-contract.md").read_text(encoding="utf-8"))
       self.assertIn("[gin quick]", (SRC / "skills/progress/SKILL.md").read_text(encoding="utf-8"))
       self.assertIn("[gin quick]", (SRC / "skills/milestone-close/SKILL.md").read_text(encoding="utf-8"))
   ```
   Run it; expected: fails.

2. `quick/SKILL.md`:
   - Opening line "A fast path for a small, low-risk change. No plan, no beads, no lifecycle gates." stays; add the sentence: "Usage: `/gin:quick [--epic <id> | --milestone <id>]`; the option only names where team mode records the run."
   - Replace step 7 with:
     ~~~markdown
     7. Commit per stage-contract Git: on `main`/`master`, first `git switch -c quick/<slug>`. In solo mode, or on an existing feature branch, do not push. With `project.team.enabled` on a new `quick/<slug>`:
        1. Propose the capabilities the changed files touch (the Capability Map of `13-CAPABILITIES.md`, else the folders of `docs/specs/`) and let the member confirm them. With `gin-qa` on `PATH`, run `gin-qa cases plan <capability> --format json` from the QA home for each and keep case ids and titles; otherwise, or on a non-zero exit, write `no covering cases found` and why.
        2. Push `quick/<slug>` to `origin`, then open the pull request with the `team.host` command of `team/references/hosts.md` (in a workspace child, against its default branch). The description holds the summary, each verify command with its result, the covering cases, and `Needs ship approval: run gin team check --gate ship <pr-url> before merging.` A failed push or pull request stops here: report it; the commit stays.
        3. Record the run with `gin task comment <id> "<text>"` on the `--epic` or `--milestone` id, else the only milestone whose `status` is `active` in `gin milestone list --json` (none or several: no comment; say so). A failed comment is reported and the run continues. The text, labels never translated:
           ```
           [gin quick] <branch> <pr-url>
           Summary: <one line>
           Files: <count>
           Author: <git email>
           Cases: <case-id>, <case-id> | none
           ```
        4. With `team.beads_sync` set, `gin team sync`.
     ~~~
   - Step 8: "`gin record quick-completed --evidence "<files>; <verify results>[; <pr-url>]" --actor <id>`".
   - Step 9: add "and, in team mode, the pull request URL and where the run was recorded".
   - Keep the last line "Never create plans, beads, or gates."
   - Check the quick chain: `cd plugins/gin-workflow/src/scripts && python3 -c "from pathlib import Path; from workflow_core.budget import stage_chars; print(stage_chars(Path('..'), 'quick'))"`; expected at most 8000.

3. `references/stage-contract.md:34`: replace "`quick` commits on the current feature branch, or on a new `quick/<slug>` when started on `main`/`master`, and does not push." with "`quick` commits on the current feature branch, or on a new `quick/<slug>` from `main`/`master`, pushed only in team mode." (4 characters shorter). Check with the stage_chars loop over `STAGES` that every chain stays at or under 12,000 and quick at or under 8,000.

4. Readers.
   - `progress/SKILL.md`, the Milestone bullet of step 1: after "one line per epic with `status`, `spec_confirmed`, `remaining_days`, and `warnings`." add " List the `[gin quick]` comments of the milestone and its epics (`gin task comments <id> --json`): branch, pull request, author, date."
   - `milestone-close/SKILL.md`, `## Summary` list, after the Retros bullet, add: "- Quick runs: the number of `[gin quick]` comments on the milestone and its epics."

5. Docs.
   - `docs/concepts/lifecycle.md:125`: "It never pushes." becomes "In solo mode it never pushes. In team mode, on a new `quick/<slug>`, it pushes, opens a pull request that needs ship approval, and records the run on the epic or the active milestone (see [Team mode](../guides/team.md))."
   - `docs/guides/team.md`: add a paragraph under the section that covers pull requests and approvals, titled by the existing heading style, saying: in team mode `/gin:quick` started on the base branch pushes `quick/<slug>`, opens a pull request whose description lists the covering QA cases by capability and the ship approval line, records a `[gin quick]` comment on `--epic`, `--milestone`, or the active milestone, and runs `gin team sync`; `gin team pending` lists the open quick pull requests; the person who merges runs `gin team check --gate ship <pr-url>`.
   - `docs/reference/skills.md:23`, `quick` row second cell: "Small, low-risk change without plan or beads: confirm, implement, verify per rigor, report. In team mode, started on the base branch, it pushes `quick/<slug>`, opens a pull request with the covering cases and the ship approval line, and records a `[gin quick]` comment on an epic or the active milestone".
   - `docs/reference/skills.vi.md:23`, same in Vietnamese: "Thay đổi nhỏ, rủi ro thấp không cần plan hay bead: xác nhận, triển khai, kiểm chứng theo rigor, báo cáo. Trong team mode, khi bắt đầu từ nhánh base, skill push `quick/<slug>`, mở pull request kèm các case bao phủ và dòng nhắc ship approval, rồi ghi comment `[gin quick]` lên một epic hoặc milestone đang active".

6. Run `python3 -m pytest tests/workflow_core/test_skill_routing.py tests/workflow_core/test_token_budget.py tests/workflow_core/test_docs_coverage.py tests/workflow_core/test_docs_check.py tests/workflow_core/test_walkthrough_docs.py tests/gin_orchestrator/test_harness_packaging.py -q`; expected: all pass. Commit: `feat(skills): /quick in team mode pushes, opens a pull request, and records the run (gin-workflow-quick-team)`.

## Integration
- **Branch**: feat/quick-team
- **Merge strategy**: sequential

## Validation
- [ ] `python3 -m pytest -n auto` passes (the pre-push hook runs it at ship)
- [ ] Every stage chain within budget; `stage-contract.md` not longer than before
- [ ] In a team-mode test project, a quick run on the base branch opens a pull request and writes the comment (manual, by the user)

## Notes
- Parent Bead: `gin-workflow-quick-team` stays open until the human-confirmed merge; track beads close after tests and review pass.
- Solo work: no push before the epic is complete; ship merges locally and pushes once.
