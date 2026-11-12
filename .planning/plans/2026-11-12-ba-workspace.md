# Plan: Capture and mockups in a workspace, and the BA during build

Spec: .planning/specs/2026-11-12-ba-workspace-design.md
Epic: gin-workflow-ba-workspace
Workflow: gin-workflow-ba-workspace

## Objective

`gin specs assets confirm` records who confirmed a folder and who agreed; `/gin-ba:mockup` uses the workspace's frontend child, skips a 1-1 copy, and asks for the area lead's agreement; execute posts `[gin question]` comments the BA answers with `[gin answer]`, progress lists open questions, the BA accepts each epic with `[gin accept]`, and ship warns when a team with a BA ships without it.

**Goal** (spec): Mockup reads the target app's design tokens, capture records who confirmed it, the area lead reviews mockups before confirm, business questions raised in execute reach the BA as epic comments, and each epic gets one BA acceptance point.

**Architecture**: one code change, `specs_assets.confirm` writes `Confirmed by:` (from `team.git_email`) and an optional `Agreed with:`, exposed as `--agreed-with`. Everything else is skill and doc text: execute, progress, and ship skills gain the epic-comment steps (execute's chain is offset by deleting text that restates execute in `delegation-policy.md`); the gin-ba mockup and capture skills gain the workspace source, the 1-1 rule, and the agreement question. `docs/concepts/lifecycle.md` stays the one home for epic comment kinds; the BA guide, git agreement, way of working, roles, workspace guide, and brownfield starter link to it.

**Tech Stack**: Python 3 standard library; unittest/pytest (`tests/workflow_core/test_specs_assets.py`, `tests/workflow_core/test_token_budget.py`, `tests/workflow_core/test_skill_routing.py`, `tests/gin_orchestrator/test_routed_worker.py`, `tests/gin_ba/test_ba_packaging.py`); Markdown checked by `gin docs check`.

**Global Constraints** (spec, verbatim):
- `assets confirm` without `--agreed-with` and with a git email keeps today's output keys and adds `confirmed_by` and `agreed_with`.
- A missing git `user.email` is a new refusal of `assets confirm` (exit 2); every other refusal is unchanged.
- `confirmed_value_errors` keeps matching only the `Confirmed:` line; `Confirmed by:` and `Agreed with:` are not parsed by lint.
- With the markdown task backend there are no comments: execute, progress, and ship skip the comment steps and say so.
- No new gate, event, or state JSON key; gin-console is unaffected.
- R9. The execute stage chain stays at most 12,000 characters, ship and progress chains at most 12,000, and each gin-ba skill at its packaging limit; text added to execute is offset by shortening other execute-chain text without dropping a rule.
- Out of scope: the SDD change flow; a new lifecycle gate for acceptance; lint rules for the new `description.md` lines.

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
- Problem statement: the BA's mockups ignore the workspace's frontend repository, confirmations carry no names, developer questions never reach the BA, and the BA has no acceptance point after the spec.
- Success criteria: spec R1 to R10; US-1 to US-4 as tests (code, budgets) or checked text (skills, docs); existing tests pass.
- Constraints: Global Constraints above.
- Non-goals: see Global Constraints.

## Approach Options
### Option 1: epic comments and a sign-off line (confirmed)
- Summary: `[gin question]`/`[gin answer]`/`[gin accept]` epic comments in skills, `Confirmed by:`/`Agreed with:` from `assets confirm`.
- Pros: follows the `[gin ship]`/`[gin roadmap]` pattern; one small code change; traces in Beads.
- Cons: acceptance is a convention with a warning, not a gate.

### Option 2: a new `accepted` gate
- Summary: `gin record accepted`, checked by ship.
- Pros: enforced.
- Cons: router, lifecycle CLI, team policy, state model, and gin-console changes; rejected in `/discuss`.

### Recommended Approach
- Selected option: Option 1 (confirmed in `/discuss` on 2026-11-11).
- Rationale: smallest change that gives the BA a question path and an acceptance point.

## Scope
- In scope: R1 to R10.
- Out of scope: see Global Constraints.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: The gin-ba skills call the new --agreed-with flag and the docs describe all shipped behaviour; one lane keeps the order.
```

## Tasks

`S` is `plugins/gin-workflow/src/scripts/workflow_core`; `K` is `plugins/gin-workflow/src/skills`.

### Track 1: `assets confirm` records who confirmed and who agreed
- **Dependencies**: none
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs_assets.py:109-122` (`confirm`), imports at `:11-12`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs_cli.py:58-60` (`--agreed-with`), `:122-124` (pass it)
  - Modify `plugins/gin-workflow/src/templates/iteration.md:3-8` (comment names the two lines)
  - Modify `docs/reference/cli.md:136` (`assets confirm` row)
  - Test `tests/workflow_core/test_specs_assets.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** bounded change to one function and its CLI flag, with every output and refusal fixed by the spec.
- **Interfaces**:
  - `specs_assets.confirm(root, cfg, cap, day, *, agreed_with: str | None = None, today: date | None = None) -> dict[str, str | None]` returning `{"description", "confirmed", "confirmed_by", "agreed_with"}`.
  - `confirmed_by` is `team.git_email(root)`; when it is `""`, raise `specs.SpecsError("set git user.email before confirming")` before any write.
  - Lines written with the existing `_set_field`: `Confirmed: <date>` (after `Previous`), then `Confirmed by: <email>` (after `Confirmed`), then, when `agreed_with` is truthy after `.strip()`, `Agreed with: <agreed_with>` (after `Confirmed by`).
  - CLI: `gin specs assets confirm CAP --date D [--agreed-with TEXT]`; text output unchanged (`<description>: Confirmed: <date>`); JSON gains the two keys.
- **Steps**:
  1. Failing tests in `tests/workflow_core/test_specs_assets.py`, class with the existing `confirm` helper (`:138`), which passes `today=date(2026, 11, 9)`; `make_repo` sets `user.email t@example.com`:
     - update `test_confirm_sets_today` to expect `{"description": f"{FOLDER}/description.md", "confirmed": "2026-11-09", "confirmed_by": "t@example.com", "agreed_with": None}` and assert `"Confirmed: 2026-11-09\nConfirmed by: t@example.com\n"` in the description;
     - `test_confirm_records_who_agreed`: `specs_assets.confirm(..., "orders", "2026-11-07", agreed_with="fe_lead Binh", today=date(2026, 11, 9))` writes `"Confirmed by: t@example.com\nAgreed with: fe_lead Binh\n"` and returns `agreed_with == "fe_lead Binh"`;
     - `test_confirm_needs_a_git_email`: with `unittest.mock.patch("workflow_core.specs_assets.git_email", return_value="")`, `confirm` raises `SpecsError` matching `set git user.email before confirming` and the description is byte-for-byte unchanged;
     - `test_lint_accepts_folders_without_sign_off_lines`: in `TestAssetLint`, a folder confirmed on main without `Confirmed by:` (the existing `confirm_on_main` helper) gives no `Confirmed:` finding from `specs_assets.lint(...)`; a folder with `Confirmed by: x@y` and `Agreed with: z` after `Confirmed: 2026-11-02` gives none either;
     - extend `test_cli_confirm`: `run_specs(self.root, "assets", "confirm", "orders", "--date", "2026-11-07", "--agreed-with", "pm An", "--format", "json")` on a fresh folder prints JSON with `"confirmed_by": "t@example.com"` and `"agreed_with": "pm An"` (use a second dated folder so the first confirm in the test stays as is).
     Run `python3 -m pytest tests/workflow_core/test_specs_assets.py -q` → the new and updated tests fail.
  2. `specs_assets.py`: `from .team import git_email`; change `confirm` per the interface (check the email right after the "already confirmed" check, before `atomic_write_many`).
  3. `specs_cli.py`: `item.add_argument("--agreed-with")` on the `confirm` parser; call `confirm(root, cfg, args.cap, args.date, agreed_with=args.agreed_with)`.
  4. `iteration.md` comment: replace "`gin specs assets confirm` sets Confirmed." with "`gin specs assets confirm` sets Confirmed, adds Confirmed by (the git user.email), and adds Agreed with when `--agreed-with` names who else agreed."
  5. `docs/reference/cli.md:136`: the row becomes `| `assets confirm CAP --date D [--agreed-with TEXT]` | Set `Confirmed:` to today in that folder's `description.md`, add `Confirmed by:` with the git `user.email`, and add `Agreed with: TEXT` when given; exit 2 when the file is missing, already confirmed, or git `user.email` is unset |`. Run `gin docs check docs/reference/cli.md` → ok.
  6. Run step 1 → pass; `python3 -m pytest tests/workflow_core -q -n auto -k "specs"` → pass.
  7. Commit: `feat(specs): assets confirm records Confirmed by and Agreed with (gin-workflow-ba-workspace)`.
- **Acceptance criteria**: R4 (code part); US-2 criteria 1 to 4 as the tests above.
- **Estimated complexity**: low

### Track 2: Questions, answers, and acceptance in execute, progress, and ship
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-workflow/src/skills/execute/SKILL.md:36` (step 5), `:43` (drop the parenthetical "(squash-merge checks fetch the refs)")
  - Modify `plugins/gin-workflow/src/skills/execute/references/delegation-policy.md:3` (first paragraph)
  - Modify `plugins/gin-workflow/src/skills/progress/SKILL.md:17-18` (new step after step 4)
  - Modify `plugins/gin-workflow/src/skills/ship/SKILL.md:16` (step 1 warning)
  - Test `tests/workflow_core/test_token_budget.py`, `tests/workflow_core/test_skill_routing.py`, `tests/gin_orchestrator/test_routed_worker.py` (existing; run, do not change unless a new assertion below)
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** skill text in three stage skills with exact wording, under a 12,000-character chain limit that leaves execute 50 characters of headroom.
- **Steps**:
  1. Baseline: `cd plugins/gin-workflow/src/scripts && python3 -c "from pathlib import Path; from workflow_core.budget import stage_chars; [print(s, stage_chars(Path('..').resolve(), s)) for s in ('execute','progress','ship')]"` → execute 11950, progress 4818, ship 10831.
  2. `execute/SKILL.md` step 5 becomes exactly:
     `5. On `needs_clarification`, answer from the spec or plan and re-dispatch at the same route with the excerpt; otherwise (Beads) `gin task comment <epic> "[gin question] <track>: <question>"`, `gin notify --event needs_input "<track>: <question>"`, and leave the bead `in_progress` with a note. On resume, a newer `[gin answer] <track>:` comment (`gin task comments <epic> --json`) answers it.`
     In section 4 step 3 delete " (squash-merge checks fetch the refs)".
  3. `delegation-policy.md` first paragraph becomes: "Tracks are dispatched with `gin routes dispatch`; the route comes from the assignment manifest." Keep the rest of the file unchanged (`test_skill_routing.py:126-136` and `test_routed_worker.py:523-530` check "routes dispatch", the four statuses, "never lowered", "one isolated worktree per worker", "A requested route is never lowered").
  4. `progress/SKILL.md`: insert after step 4 and renumber the rest: "5. With Beads, for each open epic in the report, list each `[gin question] <track>:` comment (`gin task comments <epic> --json`) that has no newer `[gin answer] <track>:` comment, with its date and text, as open questions for the BA. The markdown backend has no comments."
  5. `ship/SKILL.md` step 1, after the `review_waivers` sentence: "When `team.members` in `.agent-workflow/config.yaml` has a member with the role `ba` and `gin task comments <epic> --json` has no `[gin accept]` comment, warn `no BA acceptance ([gin accept]) on <epic>` and continue; skip this check with the markdown backend."
  6. Run step 1's command → execute ≤ 12000 (expected 11976: +172 in step 5, −37 in section 4, −109 in delegation-policy.md), progress ≤ 12000, ship ≤ 12000. If execute is over, shorten only the new step 5 text while keeping every instruction in it, and report what changed.
  7. `python3 -m pytest tests/workflow_core/test_token_budget.py tests/workflow_core/test_skill_routing.py tests/gin_orchestrator/test_routed_worker.py tests/gin_orchestrator/test_harness_packaging.py -q` → pass.
  8. Commit: `feat(skills): [gin question] and [gin answer] in execute and progress, [gin accept] warning in ship (gin-workflow-ba-workspace)`.
- **Acceptance criteria**: R5, R6, R8, R9; US-3 and US-4 criterion 3; budgets hold.
- **Estimated complexity**: low

### Track 3: gin-ba mockup and capture in a workspace, with sign-off
- **Dependencies**: Track 2
- **Files**:
  - Modify `plugins/gin-ba/src/skills/mockup/SKILL.md:18-19` (steps 3 and 4: workspace source), new rule for a 1-1 copy (before step 3), `:28-34` (steps 7 and 8: area lead and `--agreed-with`)
  - Modify `plugins/gin-ba/src/skills/capture/SKILL.md:29` (step 6: `--agreed-with`)
  - Test `tests/gin_ba/test_ba_packaging.py` (existing budget and link checks)
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `low`
- **Why:** skill text edits in two files with the wording fixed by the spec; packaging tests cover budgets and links.
- **Steps**:
  1. `mockup/SKILL.md`, before step 3, a new step (renumber after it): "When the BA says the new screens copy the legacy ones without change, write nothing: the confirmed capture folder is the input for `/gin:discuss`. Say so and stop."
  2. Step 3 (read the inputs): replace "the product's existing UI in the repository" with "the product's existing UI: in a workspace (`workspace` in `gin state --format json`), the cloned `shape: frontend` child of `workspace.repos` (ask the BA which one when there are several; when it is not cloned, name `gin workspace clone <path>` and use the next visual source); otherwise the repository". Step 4 keeps its order of visual sources and refers to "the existing UI" as found in step 3.
  3. Step 7 (confirm): before `gin specs assets confirm`, ask the BA who else agreed (business owner, PM, area lead). In team mode, when an area in `team.areas` of `.agent-workflow/config.yaml` has a `paths` glob matching the frontend child's path (or the UI path read in step 3), ask the BA to get that area's `lead` role's agreement first. Then run `gin specs assets confirm <cap> --date <date> --agreed-with "<names>"` (omit the flag when no one else agreed).
  4. `capture/SKILL.md` step 6: before running confirm, ask the BA who else agreed (business owner, PM) and pass it with `--agreed-with "<names>"`, omitted when no one.
  5. Keep every link of both files unchanged (the packaging test compares them). Check sizes: `python3 -c "import pathlib;[print(p, len(p.read_text(encoding='utf-8'))) for p in pathlib.Path('plugins/gin-ba/src/skills').glob('*/SKILL.md')]"` → each ≤ 6000.
  6. `python3 -m pytest tests/gin_ba -q` → pass.
  7. Commit: `feat(gin-ba): mockup uses the workspace frontend, skips a 1-1 copy, records who agreed (gin-workflow-ba-workspace)`.
- **Acceptance criteria**: R1, R2, R3, R4 (skill part); US-1; US-2 criterion 5.
- **Estimated complexity**: low

### Track 4: Docs for the BA during build
- **Dependencies**: Track 3
- **Files**:
  - Modify `docs/concepts/lifecycle.md:27` (epic comment kinds)
  - Modify `docs/guides/ba.md:57-72` (mockup and confirm sections), new section `### During the build` before `## Conventions` (`:91`), and `docs/guides/ba.vi.md` (same)
  - Modify `docs/guides/git-flow.md:93-110` (Review: BA not on track pull requests) and `docs/guides/git-flow.vi.md`
  - Modify `plugins/gin-workflow/src/skills/roadmap/references/way-of-working.md:18` (BA acceptance after the QA sign-off)
  - Modify `docs/roles.md:21` (BA row) and `docs/roles.vi.md`
  - Modify `docs/guides/workspace.md:65-77` (PM and BA table) and `docs/guides/workspace.vi.md`
  - Modify `docs/starters/brownfield.md` (Capture and mockup section: `--agreed-with`; Execute or Ship section: `[gin accept]`) and `docs/starters/brownfield.vi.md`
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** documentation of shipped behaviour across seven pages and five translations, with one home per fact (`lifecycle.md` for comment kinds, `ba.md` for BA practice) and a roadmap reference inside a skill folder.
- **Steps**:
  1. `lifecycle.md:27` (one home for comment kinds): add, after the `[gin roadmap]` sentence, "Execute adds a `[gin question] <track>: <question>` comment when the spec and plan do not answer a worker's question, and resumes the track when a newer `[gin answer] <track>: <answer>` comment exists; `/gin:progress` lists unanswered questions. The BA adds `[gin accept] <epic>: <what was checked>` once per epic, and ship warns when a team with a `ba` member ships an epic without it."
  2. `ba.md`:
     - `### Build the mockup`: in a workspace the mockup reuses the cloned frontend child's tokens and components; a 1-1 copy of the legacy screens needs no mockup.
     - `### Confirm the inputs`: confirm also writes `Confirmed by:` (your git `user.email`) and `Agreed with:` when you name who else agreed; in team mode the mockup skill asks for the frontend area lead's agreement first.
     - New `### During the build` (before `## Conventions`): answer each `[gin question]` with `gin task comment <epic> "[gin answer] <track>: <answer>"` (list them with `/gin:progress`); when an answer changes a requirement after plan approval, also follow [changing a requirement after plan approval](sdd.md#changing-a-requirement-after-plan-approval); after the epic's tracks close (at the milestone integration point for an epic behind a feature flag), review the `/gin-qa:report` output and add `gin task comment <epic> "[gin accept] <epic>: <what was checked>"`. Link [epic comments](../concepts/lifecycle.md#stages-and-gates). State that acceptance is a team convention that ship checks with a warning.
     - Same in `ba.vi.md` with the anchor `{ #during-the-build }`.
  3. `git-flow.md` Review section: after the BA checklist, "The BA does not review track pull requests. The BA accepts each epic once, against the QA report ([during the build](ba.md#during-the-build))." Same in `git-flow.vi.md`.
  4. `way-of-working.md:18`: after "QA signs off the integration point per milestone", add "and the BA then accepts each integrated epic with a `[gin accept]` comment".
  5. `roles.md:21` BA row: skills column adds "`gin task comment` (`[gin answer]`, `[gin accept]`)". Same in `roles.vi.md`.
  6. `workspace.md` PM and BA table: add rows `| Questions during build | answer `[gin question]` comments; see [during the build](ba.md#during-the-build) |` and `| Acceptance | `[gin accept]` per epic |`. Same in `workspace.vi.md`.
  7. `brownfield.md`: in `## Capture and mockup (BA)`, the confirm sentence names `--agreed-with` (link the BA guide, do not restate); in `## Ship` (or the milestone review section), one sentence: the BA accepts each epic with `[gin accept]` before ship (link `ba.md#during-the-build`). Same in `brownfield.vi.md`.
  8. `gin docs check` on every changed page → ok; check that every new link and anchor resolves; `python3 -m pytest tests/workflow_core/test_docs_coverage.py tests/workflow_core/test_walkthrough_docs.py tests/workflow_core/test_token_budget.py -q` → pass; `python3 -m pytest -n auto -q` → pass.
  9. Commit: `docs(ba): questions, answers, and acceptance during the build; sign-off lines (gin-workflow-ba-workspace)`.
- **Acceptance criteria**: R7, R10; US-4 criteria 1, 2, 4.
- **Estimated complexity**: medium

## Integration
- **Branch**: `feat/ba-workspace`
- **Merge strategy**: sequential

## Validation
- [ ] `python3 -m pytest -n auto -q` passes (pre-push runs it).
- [ ] `gin docs check` on the changed pages reports no findings.
- [ ] Manual: after `install.sh`, in a scratch SDD repository, `gin specs assets confirm <cap> --date <d> --agreed-with "pm An"` writes the three lines.

## Notes
- Omit `Effort:` when the catalog lists no efforts.
- The user may override `Model:` and `Effort:` before plan approval.
- Provider roles describe responsibility rather than filename patterns.
- Deliverable merge-holds (e.g. "remain open until human-confirmed merge") apply exclusively to the Parent Bead. Individual track beads must close upon passing tests and code review to unblock downstream dependent tracks.
- Test hygiene: new tests above any `__main__` guard, no duplicate names.
- `docs/concepts/lifecycle.md` has no Vietnamese translation.
