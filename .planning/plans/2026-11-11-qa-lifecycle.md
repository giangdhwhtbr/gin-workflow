# Plan: QA tracks and acceptance cases in the lifecycle

Spec: .planning/specs/2026-11-11-qa-lifecycle-design.md
Epic: gin-workflow-qa-lifecycle
Workflow: gin-workflow-qa-lifecycle

## Objective

The `qa` provider role is a default preset; `/gin:execute` sends `qa` tracks through a new on-demand `qa-track` skill; `/gin:ship` runs `gin-qa cases check --change <epic>` under the SDD layout; the `sdd` skill gives the reviewer gin-qa coverage rows; the QA and git-flow checklists fit each pull request kind. Every stage chain stays within 12,000 characters.

**Goal** (spec): A plan can route a track to the `qa` provider role, and `/gin:execute` then runs it through the matching gin-qa skill, validates it with gin-qa, and commits it like any track; `/gin:ship` stops when gin-qa reports missing or stale acceptance cases; the reviewer sees gin-qa's coverage rows; and the QA and git-flow checklists cover testability per pull request kind.

**Architecture**: one preset change in `project.py`; one new shared skill `qa-track` named on demand from `execute` (named skills are budgeted on their own, `workflow_core/budget.py:39-62`); one bullet in `ship` step 1; one clause in the `sdd` skill; docs and templates.

**Tech Stack**: Markdown skills; Python 3 (`project.py`); unittest (`test_token_budget.py`, presets tests).

**Global Constraints** (spec, verbatim):
- R3. The execute stage chain stays within 12,000 characters; any characters added are cut elsewhere without dropping a rule.
- R4. The ship stage chain stays within 12,000 characters.
- R5. The review stage chain size does not grow.
- Configs with their own provider roles are not overwritten; the `qa` preset is only added where presets apply.
- Projects without gin-qa or with the legacy layout see no new failure, only a skipped-check line at ship.
- No JSON output or Beads metadata changes.

Measured on 2026-11-11: execute chain 11,970; review 11,971; ship 10,682; `sdd/SKILL.md` 5,989 of its 6,000 shared-skill limit (`tests/workflow_core/test_token_budget.py:169`).

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
- Problem statement: QA work has no lifecycle path; ship and review ignore acceptance cases; checklists ask for checks a pull request cannot have.
- Success criteria: spec R1 to R6; US-1 to US-4.
- Constraints: Global Constraints above.
- Non-goals: evidence publishing, bug beads from automated failures, legacy parity, `Result:` checks.

## Approach Options
### Option 1: on-demand `qa-track` skill named from execute
- Summary: execute names the skill in one sentence; the skill holds the QA-track rules.
- Pros: does not count toward the execute chain; one home for QA-track rules.
- Cons: a new shared skill to register.

### Option 2: `execute/references/qa-track.md`
- Summary: the spec's first wording.
- Pros: next to execute.
- Cons: every `references/` path a stage skill names counts toward its chain; execute has 30 characters left. The spec was updated to Option 1 at plan time.

### Recommended Approach
- Selected option: Option 1.
- Rationale: meets R2 and R3 within budget.

## Scope
- In scope: R1 to R6.
- Out of scope: see Non-goals.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Small tracks on shared skill budgets; the docs track describes the shipped skill text.
```

## Tasks

`S` is `plugins/gin-workflow/src`.

### Track 1: The `qa` role preset and the `qa-track` skill
- **Dependencies**: none
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/project.py:80-85` (`ROLES_BY_SHAPE`)
  - Create `plugins/gin-workflow/src/skills/qa-track/SKILL.md`
  - Modify `plugins/gin-workflow/src/skills/execute/SKILL.md:35` (one sentence; an equal cut)
  - Modify `tests/workflow_core/test_token_budget.py:13` (`SHARED_SKILLS` adds `qa-track`)
  - Modify `docs/reference/skills.md` and `docs/reference/skills.vi.md` (a `qa-track` row next to `sdd`)
  - Test `tests/workflow_core/test_token_budget.py`, the presets test file (search `ROLES_BY_SHAPE` or `preset_assignments` under `tests/`)
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** a small preset change plus a new skill whose text must stay true to gin-qa commands and keep the execute chain within its limit.
- **Interfaces**: provider role `qa` in every `ROLES_BY_SHAPE` tuple; skill name `qa-track` with front matter `name: qa-track` and a `description:` line like the other shared skills.
- **Steps**:
  1. Failing tests: a presets test asserting `"qa"` is in `ROLES_BY_SHAPE[shape]` for every shape and that `preset_assignments(...)` emits a `routing.roles.qa` (or the equivalent preset key used for `docs`) entry; in `test_token_budget.py`, add `"qa-track"` to `SHARED_SKILLS` (so its 6,000 limit applies) and a test `test_execute_names_qa_track_on_demand` asserting `"qa-track"` appears in `skills/execute/SKILL.md` and `skills/qa-track/SKILL.md` is not in `stage_chain(SRC, "execute")`. Run → fail.
  2. `project.py`: add `"qa"` to each tuple after `"docs"`. Check how `gin setup refresh` applies presets to an existing effective config (search `preset_assignments` callers); if refresh already adds missing preset roles, note it; if not, leave refresh unchanged and record that existing projects add `qa` by rerunning setup (spec R1 says refresh adds it "the way other preset roles are": match the existing behaviour, do not invent a new path).
  3. Create `skills/qa-track/SKILL.md` (front matter like `skills/sdd/SKILL.md`; at most 6,000 characters):
     ```markdown
     ---
     name: qa-track
     description: Use in /execute for a track routed to the `qa` provider role: write or update gin-qa cases, automated tests, or e2e specs, validate them with gin-qa, and commit them like any track.
     ---

     # QA track

     A track whose plan entry has `Provider role: qa` changes QA files in the QA home (gin-qa's `cases/`, test globs, or `e2e/`). Execute dispatches it like any track; these rules add to execute, they do not replace it.

     1. Dispatch `gin:developer` at the track's route. Its instructions are the gin-qa skill that matches the track's files: `gin-qa:cases` for case files, `gin-qa:tests` for automated tests, `gin-qa:e2e` for Playwright specs. Pass `gin rules --files <case and test files>` as for any track.
     2. The track runs in its worktree: the `qa` child's worktree in a workspace, else the feature worktree. gin-qa finds the QA home from there.
     3. Validate before review: `gin-qa cases check --change <epic>`; add `gin-qa tests check` when the track changed tests and `gin-qa e2e check` when it changed e2e specs. Exit 1 lists findings: fix them before review.
     4. gin-qa skills never commit. The developer commits the track's files on the track branch with the track's bead in the message, as execute requires.
     5. Review, close, and push follow execute's Complete steps.
     ```
     Adjust wording only to match the gin-qa commands' real names and flags (`plugins/gin-qa/src/scripts/gin_qa/cli.py`).
  4. `execute/SKILL.md` step 2 of the dispatch loop: add the sentence "A track routed to `qa` also follows the `qa-track` skill." Pay for its characters with a cut in `execute/SKILL.md` that drops no rule; quote the cut before/after in the commit message. Run `cd plugins/gin-workflow/src/scripts && python3 -m workflow_core.budget --report --src ../ && cd -`: execute at most 12,000.
  5. `docs/reference/skills.md` (and `.vi.md`): add a row `| \`qa-track\` | Rules for a track routed to the \`qa\` provider role: the matching gin-qa skill, gin-qa validation, and the commit |` next to the `sdd` row. `gin docs check docs/reference/skills.md` → ok.
  6. Run step 1 tests → pass; `python3 -m pytest tests/workflow_core -q -n auto` → pass. Also run the packaging and install tests that list skills (`python3 -m pytest tests -q -n auto -k "packag or install or skill"`) and register the new skill wherever they require it (for example a skill list in `install.sh` or a manifest), within this track.
  7. Commit: `feat(execute): qa provider role and the qa-track skill (gin-workflow-qa-lifecycle)`.
- **Acceptance criteria**: R1, R2, R3; US-1; budgets hold.
- **Estimated complexity**: low

### Track 2: Ship gate and reviewer coverage
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-workflow/src/skills/ship/SKILL.md:16-18` (one bullet in step 1)
  - Modify `plugins/gin-workflow/src/skills/sdd/SKILL.md:26` (one clause; an equal cut)
  - Test `tests/workflow_core/test_token_budget.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `low`
- **Why:** two short skill edits with exact text and budget checks.
- **Steps**:
  1. Failing test in `test_token_budget.py`: `test_ship_runs_the_gin_qa_check` asserts `ship/SKILL.md` contains `gin-qa cases check --change <epic>` and the word `skipped`; `test_sdd_reviewer_reads_gin_qa_plan` asserts `sdd/SKILL.md` contains `gin-qa cases plan --change <epic>`. Run → fail.
  2. `ship/SKILL.md` step 1, after the SDD bullet, add: "   - With `gin-qa` on PATH and `project.layout: sdd`: `gin-qa cases check --change <epic> --format json`; exit 1 stops ship with its findings (missing or stale cases). Otherwise say the QA check was skipped." The ship chain stays at most 12,000.
  3. `sdd/SKILL.md` line 26: extend "The reviewer checks that each scenario of the track's REQs has a test." with " and, with gin-qa installed, treats `missing` or `stale` rows of `gin-qa cases plan --change <epic> --format json` for those REQs as missing tests." Cut the same number of characters elsewhere in `sdd/SKILL.md` without dropping a rule (quote before/after); the file stays at most 6,000 and the `test_sdd_guidance_loads_on_demand` rules still pass.
  4. Run → pass; budget report: review chain does not grow, ship at most 12,000.
  5. Commit: `feat(ship): gin-qa acceptance check; reviewer reads gin-qa coverage (gin-workflow-qa-lifecycle)`.
- **Acceptance criteria**: R4, R5; US-2, US-3; budgets hold.
- **Estimated complexity**: low

### Track 3: Checklists, lifecycle, and templates
- **Dependencies**: Track 2
- **Files**:
  - Modify `docs/guides/qa.md` ("Ship approval checklist"), `docs/guides/git-flow.md` (BA and tester checklists), `docs/concepts/lifecycle.md` (execute and ship), `plugins/gin-workflow/src/skills/roadmap/references/way-of-working.md` (Integration or Quality block)
  - Modify `plugins/gin-workflow/src/templates/team/pull_request_template.md` (Checklist), `plugins/gin-workflow/src/templates/design-spec.md`
  - Modify the `.vi.md` pairs of the changed docs pages
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `low`
- **Why:** documentation of shipped behaviour; small template lines.
- **Steps**:
  1. `qa.md`: replace the single ship checklist with three: contract pull request (contract or schema tests green, `gin-qa cases check --change <epic>` clean), service pull request (`api` cases green against the service), app pull request (e2e green against mocks, `e2e check --run`); then an integration sign-off at the milestone integration point (e2e green against the real API for the flags turned on, no open bug bead on the integrated epics). Mention that `/gin:ship` runs `gin-qa cases check` itself under the SDD layout.
  2. `git-flow.md`: add to the BA spec review checklist "every requirement can be tested: each acceptance criterion names an observable outcome"; add a note that the team may request a non-gating `qe` review on spec pull requests (CODEOWNERS on the spec folders is the host's mechanism).
  3. `lifecycle.md`: in execute, one sentence that a `qa` track follows the `qa-track` skill; in ship, one sentence on the gin-qa check.
  4. `way-of-working.md`: in Quality, "QA signs off the integration point per milestone"; keep at most 6,000 characters.
  5. Templates: PR Checklist adds "- [ ] Acceptance cases for the changed REQs exist and pass (`gin-qa cases check`)"; `design-spec.md` adds under Testing a comment line "<!-- Each acceptance criterion names an observable outcome a tester can check. -->". Run the template tests (`python3 -m pytest tests -q -n auto -k "template or team_init or specs"`) and update exact-template expectations only where a test pins the full text (list them).
  6. `.vi.md` pairs: mirror the changes in the existing Vietnamese style; code and paths verbatim.
  7. `gin docs check` on every changed page → ok; `python3 -m pytest -n auto -q` → pass.
  8. Commit: `docs(qa): checklists per pull request kind, spec testability, QA track and ship check (gin-workflow-qa-lifecycle)`.
- **Acceptance criteria**: R6; US-4; docs check clean; full suite passes.
- **Estimated complexity**: low

## Integration
- **Branch**: `feat/qa-lifecycle`
- **Merge strategy**: sequential

## Validation
- [ ] `python3 -m pytest -n auto -q` passes (pre-push runs it).
- [ ] Budget report: execute, review, ship at most 12,000; `qa-track` and `sdd` at most 6,000.
- [ ] `gin docs check` on the changed docs reports no findings.

## Notes
- Omit `Effort:` when the catalog lists no efforts.
- The user may override `Model:` and `Effort:` before plan approval.
- Provider roles describe responsibility rather than filename patterns.
- Deliverable merge-holds (e.g. "remain open until human-confirmed merge") apply exclusively to the Parent Bead. Individual track beads must close upon passing tests and code review to unblock downstream dependent tracks.
- Budget lesson: every cut in a skill is quoted before/after and checked for a dropped rule.
- Roadmap follow-up (not this epic): add epics for cluster B (evidence publishing, bug beads from automated failures) and C (legacy parity) at the next `/gin:roadmap`.
