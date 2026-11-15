# Plan: Track environment with read-only siblings and running services

Spec: .planning/specs/2026-11-15-ws-track-env-design.md
Epic: gin-workflow-ws-track-env

## Objective

A workspace plan track names the repositories it reads with `Reads:`; the plan gate checks the names; `gin workspace status --json` gives each checkout's absolute path and commit; orchestrate and execute check the clones and pass the read-only context to the developer; gin-qa writes `checkouts` into `run.json`; the workspace guide names one directory to open and the conventions for running a track's dependencies.

**Goal** (spec): In a workspace, a plan track names the sibling repositories it reads and never edits. The plan gate checks the names, and orchestrate and execute check the clones and give the developer each sibling's path, branch, and commit. The workspace guide names one directory to open per kind of work and says how a team runs the services a track is tested against. gin-qa records the checked-out commit of each repository in its run record.

**Architecture**:
- Plan parsing (`workflow_core/team.py`): `Track.reads` next to `Track.repo`; `plan_tracks` reads one `Reads:` line per track; `check_plan_repos` adds three findings, so `gin team check-plan` and `gin record plan-approved` refuse a bad line with no change of their own.
- Workspace status (`workflow_core/workspace_cli.py`): `status` rows gain `checkout` and `commit`. This one command serves the skills and gin-qa; no command is added.
- Skills: the plan schema and plan skill define the line; orchestrate copies it to the bead and checks clones outside team mode; the Workspace section of the `worktrees` skill holds the execute-time rule; the execute context names it; the developer agent treats those repositories as read-only.
- gin-qa (`gin_qa/reqs.py`, `e2e.py`, `tests.py`): one helper shells out to `gin workspace status --json` and both run commands store its rows as `checkouts`.
- Docs follow: the CLI reference with the code tracks, the guides in their own track.

**Tech Stack**: Python 3 standard library, PyYAML; unittest/pytest; fixtures in `tests/workflow_core/test_team_gates.py` (`PLAN`, `WORKSPACE`, `write`, `make_team_repo`, `run_cli`), `tests/workflow_core/test_workspace_cli.py` (`run`), and `tests/gin_qa/qa_fixtures.py` (`gin_workflow_bin`, `make_workspace_qa`, `failing_stub`, `qa`); `gin docs check`.

**Global Constraints** (spec "Errors and compatibility", verbatim):
- A plan without `Reads:` parses and checks as today. `Track.reads` is the last field and has a default, so existing callers keep working.
- A `Reads:` value that names no known path (`none`, a typo) is refused at plan approval and never ignored.
- A `Reads:` repository that is not cloned passes plan approval. Orchestrate (outside team mode) and execute stop with the clone command.
- `gin workspace status --json` adds keys only. gin-console reads `gin state` and `bd`, not this command.
- gin-qa copies the keys a row has; a key an older gin does not print is `null`. A failed status command never fails a test run.
- gin never writes to a sibling checkout: no branch switch, pull, hook, or worktree because of `Reads:`.

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
- Problem statement: a track worktree holds one repository, the developer receives no path outside it, no command prints a sibling's absolute path, the workspace guide names two different directories to open, no page covers running dependencies, and gin-qa's run record names no commit (spec "Problem", with `file:line` evidence).
- Success criteria: R1 to R11 and the acceptance criteria of US-1 to US-6.
- Constraints: stage chains at most 12,000 characters, shared skills 6,000, agents 4,000 (R8). Today: plan chain 11,770, execute chain 11,977, orchestrate chain 8,140, `worktrees` 3,853, `developer.md` 3,902. No rule is dropped to make room.
- Non-goals: a config key for services or environments; a worktree of a sibling at a ref; enforcing read-only access; repositories outside `workspace.repos`; `checkouts` in the report page, for manual runs, or for a remote environment.

## Approach Options
### Option 1: extend the commands that exist (confirmed)
- Summary: `check_plan_repos` checks the line, `gin workspace status --json` gains `checkout` and `commit`, the skills read that command, and gin-qa reuses it.
- Pros: no new command; one source for the skills and gin-qa; works on each member's machine in team mode.
- Cons: the clone check at orchestrate and execute is skill text, not code.

### Option 2: a new `gin workspace reads` command
- Summary: a command resolves a track's `Reads:` to paths and exits 1 with the clone command.
- Pros: the clone check is code.
- Cons: a new command, its docs and tests; gin-qa still needs another source for commits.

### Option 3: the route manifest
- Summary: `gin routes resolve` stores `reads` and `gin routes dispatch` returns the paths.
- Pros: execute needs no extra step.
- Cons: the manifest exists only on the machine that ran orchestrate, so it fails team mode.

### Recommended Approach
- Selected option: Option 1.
- Rationale: confirmed by the user on 2026-11-15; it adds the least surface and one command serves three readers.

## Scope
- In scope: `Track.reads`, `plan_tracks`, `check_plan_repos`; `status` rows; the plan schema, plan, orchestrate, worktrees, and execute skill text and the developer agent; gin-qa `checkouts`; the CLI reference, the workspace guide, the brownfield starter, and their Vietnamese twins.
- Out of scope: everything under "Out of scope" in the spec.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Four small tracks; tracks 2 to 4 use the names track 1 introduces, and tracks 1 and 3 both edit docs/reference/cli.md.
```

## Tasks

The tracks commit one after another on `feat/ws-track-env` in `.claude/worktrees/ws-track-env` (`project.worktree: parallel` with sequential tracks creates no track worktree). Run the CLI under test as `python3 plugins/gin-workflow/src/scripts/gin ...`; the installed `gin` is older.

### Track 1: `Reads:` in the plan parser and gate, `checkout` and `commit` in workspace status
- **Dependencies**: none
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team.py:220-290` (`Track`, a `_READS` pattern, `plan_tracks`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team.py:335-353` (`check_plan_repos`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/workspace_cli.py:104-116` (`status`)
  - Modify `docs/reference/cli.md` (`gin workspace status`, the `check-plan` row of `gin team`, the workspace sentence of `gin record plan-approved`)
  - Test `tests/workflow_core/test_team_gates.py`
  - Test `tests/workflow_core/test_specs_technical_questions.py`
  - Test `tests/workflow_core/test_workspace_cli.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** two functions in one module and one in another, with existing helpers (`space.repo`, `space.checkout`, `_run_git`) and a clear spec.
- **Interfaces**:
  - `team.Track` gains a last field `reads: tuple[str, ...] = ()`.
  - `team._READS = re.compile(r"^-\s*(?:\*\*)?Reads(?:\*\*)?:\s*(.*)$")`, matched on the stripped line before `_META` consumes nothing else. Its value splits on `,`; each token is stripped of whitespace and of one pair of backticks; empty tokens are dropped. `plan_tracks` stores them in the order written, without duplicates (`tuple(dict.fromkeys(...))`), and resets `files_indent` as a `_META` line does.
  - `check_plan_repos(space, path)`: for each path of `track.reads`, after that track's `Repo:` findings and also when its `Repo:` is missing or unknown:
    - `space.repo(path) is None` gives `Track N: Reads: <path> is not in workspace.repos`;
    - an entry with `shape == "beads"` gives `Track N: Reads: <path> is the beads repository`;
    - `path == track.repo` gives `Track N: Reads: <path> is the track's own Repo:`.
    A frozen entry gives no finding. Existing findings keep their text and order.
  - `workspace_cli.status(space)`: each row gains `"checkout": str(space.checkout(repo))` as an absolute path, also for a missing repository, and `"commit"`: the stdout of `git rev-parse HEAD` in the checkout when the repository is present and git exits 0, else `None`. `_text` is unchanged.
  - Error handling: a git failure is a `None` commit through `_run_git` (`check=False`), as `dirty` is today. No new exception class and no `except Exception`.
- **Steps**:
  1. Failing tests in `tests/workflow_core/test_team_gates.py`, next to `test_plan_tracks_reads_repo` and `test_check_plan_repos_findings`:
     - `plan_tracks` returns `("legacy/portal", "apps/web")` for ``- **Reads**: `legacy/portal`, `apps/web` `` and for `- Reads: legacy/portal, apps/web`; `()` for a track without the line; a path written twice appears once;
     - `check_plan_repos` on a plan where Track 1 (`Repo: services/api`) reads `legacy/portal` and `apps/web` gives no finding for it; Track 2 (`Repo: apps/web`) reads `services/billing`, `.beads`, and `apps/web` and gives the three findings of R3 in that order; Track 3 has no `Repo:` and reads `nope` and gives `Track 3: missing Repo:` then `Track 3: Reads: nope is not in workspace.repos`;
     - `test_check_plan_repos_findings` passes unchanged;
     - `gin team check-plan <plan> --format json` exits 1 and lists a `Reads:` finding (next to `test_check_plan_cli_adds_workspace_findings`);
     - in `tests/workflow_core/test_specs_technical_questions.py`, next to `test_bad_tracks_refuse_the_gate` and with its `record` helper: a plan whose track reads `services/billing` is refused with `plan-approved refused: workspace tracks` and `Track 1: Reads: services/billing is not in workspace.repos`.
  2. Failing tests in `tests/workflow_core/test_workspace_cli.py`, next to `test_clone_all_then_status`: for a cloned child, `checkout` equals the resolved `<root>/<path>` and `commit` equals `git -C <checkout> rev-parse HEAD`; for an entry that is not cloned, `commit` is `None` and `checkout` is still its absolute path; the text output of `gin workspace status` is unchanged.
  3. Run `timeout 600 python3 -m pytest tests/workflow_core/test_team_gates.py tests/workflow_core/test_specs_technical_questions.py tests/workflow_core/test_workspace_cli.py -q` → fail.
  4. Implement per the interfaces. Update `docs/reference/cli.md`: the JSON row of `gin workspace status` (`path`, `present`, `branch`, `dirty`, `frozen`, `checkout`, `commit`, with `commit: null` when missing), and the `Reads:` findings where `check-plan` and `record plan-approved` list the workspace findings.
  5. Run step 3 → pass; `timeout 900 python3 -m pytest tests/workflow_core -q -n auto -k "team or workspace or lifecycle"` → pass; `python3 plugins/gin-workflow/src/scripts/gin docs check docs/reference/cli.md` → ok.
  6. Commit: `feat(workspace): plan tracks name read-only repositories; status shows checkout and commit (gin-workflow-ws-track-env)`.
- **Acceptance criteria**: R2, R3, R4, the CLI reference part of R11; US-1; US-3 criterion 1.
- **Estimated complexity**: medium

### Track 2: Skills and the developer agent carry the read-only context
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-workflow/src/skills/plan/plan-schema.md:61` (a `Reads` line after `Repo`)
  - Modify `plugins/gin-workflow/src/skills/plan/SKILL.md:20` (the workspace sentence)
  - Modify `plugins/gin-workflow/src/skills/orchestrate/SKILL.md:24` (step 6: the bead line and the clone check)
  - Modify `plugins/gin-workflow/src/skills/worktrees/SKILL.md:36-42` (the Workspace section)
  - Modify `plugins/gin-workflow/src/skills/execute/SKILL.md:32` (the bounded context)
  - Modify `plugins/gin-workflow/src/skills/execute/references/delegation-policy.md:5` (the same list)
  - Modify `plugins/gin-workflow/src/agents/developer.md:25-33` (Guidelines)
  - Test `tests/workflow_core/test_skill_routing.py`
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** instruction text in seven files with the target sentences given; three of them sit within 100 characters of a tested budget, so every addition needs a counted cut.
- **Interfaces** (target text; adjust wording only to meet a budget, never the rule):
  - `plan-schema.md`, after the `Repo` line: ``- **Reads**: workspace only, optional: the `workspace.repos` paths this track reads and never edits, comma-separated``.
  - `plan/SKILL.md:20`, appended to the workspace sentence: `` `Reads: <paths>` names the entries it only reads.`` The two additions are 167 characters; the plan chain must stay at most 12,000 (11,770 today).
  - `orchestrate/SKILL.md` step 6, replacing the last sentence: ``Put `Repo: <path>` and the track's `Reads: <paths>` in each track bead's description. Outside team mode, each `Reads:` repository must be `present` in `gin workspace status --json`; a missing one stops with `gin workspace clone <path>`.``
  - `worktrees/SKILL.md`, a paragraph at the end of the Workspace section that applies in any workspace, not only inside a child: ``A track with `Reads:` (plan track or bead description): before the developer starts, take each named repository's row from `gin workspace status --json`. If it is not `present`, stop with `gin workspace clone <path>`. Give the developer its `checkout`, `branch`, and `commit` as read-only context. Never switch or pull that checkout.``
  - `execute/SKILL.md:32`: the bounded context becomes ``track text, file scope, `gin rules` output, worktree path, `Reads:` checkouts, validation commands, and `project.run_at` ``. That adds 20 characters; the execute chain has 23 left.
  - `delegation-policy.md:5`: the list gains `` `Reads:` checkouts`` after `worktree path`, paid for by dropping the parenthesis ``(`gin rules --files <scope>`)``, which repeats the command in `execute/SKILL.md` section 2. The execute chain must stay at most 12,000.
  - `developer.md`, a new guideline 8: ``A `Reads:` repository is read-only: never edit, commit, switch branch, or pull there.`` With its newline it adds 89 characters; the file must stay at most 4,000 (3,902 today). Guideline 7 already covers escalation.
- **Steps**:
  1. Failing tests in `tests/workflow_core/test_skill_routing.py` (use its `line_with` and file-reading helpers as `test_orchestrate_and_worktrees_follow_the_settings` does):
     - `plan-schema.md` has a `**Reads**` line that says `workspace only` and `never edits`; the plan skill's workspace line names `Reads:`;
     - the orchestrate line with `Put \`Repo: <path>\`` also names `Reads:`, `gin workspace status --json`, `gin workspace clone`, and `Outside team mode`;
     - the Workspace section of the worktrees skill (from `## 3. Workspace` to the end of the file) names `Reads:`, `gin workspace status --json`, `gin workspace clone <path>`, `checkout`, `commit`, `read-only`, and `Never switch or pull`;
     - the execute line with `bounded context` and the delegation policy both name `` `Reads:` checkouts``;
     - `developer.md` has a line with `Reads:` and `read-only`.
  2. Run `timeout 300 python3 -m pytest tests/workflow_core/test_skill_routing.py tests/workflow_core/test_token_budget.py -q` → the new tests fail, the budget tests pass.
  3. Edit the seven files per the interfaces.
  4. Run step 2 → pass. Print the sizes: `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -c "from pathlib import Path; from workflow_core.budget import stage_chars, STAGES; s=Path('plugins/gin-workflow/src'); print({x: stage_chars(s,x) for x in STAGES})"` and `wc -c plugins/gin-workflow/src/skills/worktrees/SKILL.md plugins/gin-workflow/src/agents/developer.md`.
  5. Run `timeout 600 python3 -m pytest tests/workflow_core -q -n auto -k "skill or budget or docs or packaging or routing or agents"` and `timeout 120 python3 -m pytest tests/gin_qa/test_packaging.py tests/gin_ba -q` → pass.
  6. Commit: `feat(skills): orchestrate, execute, and the developer agent carry a track's read-only repositories (gin-workflow-ws-track-env)`.
- **Acceptance criteria**: R1, R5, R6, R7, R8; US-2; US-3 criteria 2 to 4.
- **Estimated complexity**: medium

### Track 3: gin-qa records the checkouts of a run
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-qa/src/scripts/gin_qa/reqs.py:24-58,115-131` (`Effective.workspace`, `locate`, a new `workspace_checkouts`)
  - Modify `plugins/gin-qa/src/scripts/gin_qa/e2e.py:386-388` (the record of `run`)
  - Modify `plugins/gin-qa/src/scripts/gin_qa/tests.py:297-299` (the record of `run`)
  - Modify `docs/reference/cli.md` (the `gin-qa e2e run` and `gin-qa tests` sections)
  - Test `tests/gin_qa/test_workspace_root.py`
  - Test `tests/gin_qa/test_e2e_cli.py`
  - Test `tests/gin_qa/test_tests_cli.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** one helper and two call sites in a small package, with the workspace fixture and the gin launcher stub already in the tests.
- **Interfaces**:
  - `reqs.Effective` gains `workspace: bool = False`; `locate` sets it to `bool(payload.get("qa_root"))`.
  - `reqs.workspace_checkouts(eff: Effective) -> list[dict[str, Any]] | None`: `None` when `eff.workspace` is false. Otherwise it runs `gin workspace status --repository <eff.project_root> --json` (the `gin` of `shutil.which`, as `specs_reqs` does) and returns `[{"path", "branch", "commit", "dirty"}]` for each row with `present` true, reading each key with `row.get`. When `gin` is not on PATH, the command exits non-zero, the output is not JSON, or it has no `repos` list, it prints `gin-qa: checkouts not recorded: <reason>` on stderr and returns `None`.
  - `e2e.run` and `tests.run`: after building `record` and before the first write of `run.json`, `found = workspace_checkouts(eff)`; when it is not `None`, `record["checkouts"] = found`.
  - Error handling: catch `OSError` from `subprocess.run` and `ValueError` from `json.loads` by name; no `except Exception`; never raise `QaError` from the helper, because a failed status command must not fail a test run.
- **Steps**:
  1. Failing tests:
     - `tests/gin_qa/test_workspace_root.py` (it has `make_workspace_qa`, `FAKE_NPX`, and the real launcher from `gin_workflow_bin`): in a workspace, `run.json` of `gin-qa e2e run` and of `gin-qa tests run --type <T>` has `checkouts` with one row for the cloned `qa` child whose `commit` equals `git -C <child> rev-parse HEAD` and whose keys are exactly `path`, `branch`, `commit`, `dirty`; a `workspace.repos` entry that is not cloned has no row;
     - the same file, with a `gin` stub that answers `specs reqs` from the real launcher and fails `workspace status` (a shell stub that forwards every other command to the launcher): the run exits as it does without the failure, stderr has one line starting `gin-qa: checkouts not recorded:`, and `run.json` has no `checkouts`;
     - `tests/gin_qa/test_e2e_cli.py` (`test_run_records_the_selection_and_checks_the_evidence`) and `tests/gin_qa/test_tests_cli.py` (`test_without_files_the_whole_command_runs`): outside a workspace `run.json` has no `checkouts` key.
  2. Run `timeout 600 python3 -m pytest tests/gin_qa/test_workspace_root.py tests/gin_qa/test_e2e_cli.py tests/gin_qa/test_tests_cli.py -q` → fail.
  3. Implement per the interfaces. Update `docs/reference/cli.md`: in a workspace `run.json` of both commands has `checkouts`, what a row holds, that it states the checkout state of the machine that ran the tests, and that a failed status command prints a warning and leaves the key out.
  4. Run step 2 → pass; `timeout 900 python3 -m pytest tests/gin_qa -q -n auto` → pass; `python3 plugins/gin-workflow/src/scripts/gin docs check docs/reference/cli.md` → ok.
  5. Commit: `feat(qa): run.json records the checkout of each workspace repository (gin-workflow-ws-track-env)`.
- **Acceptance criteria**: R9, the gin-qa part of R11; US-6 criteria 1 to 3.
- **Estimated complexity**: medium

### Track 4: Workspace guide and starter
- **Dependencies**: Track 1, Track 2, Track 3
- **Files**:
  - Modify `docs/guides/workspace.md:57-65,88-125` (Onboarding, the Tech lead, engineers, and QA sections, a new section on running a track's dependencies)
  - Modify `docs/guides/workspace.vi.md` (the same sections)
  - Modify `docs/starters/brownfield.md:347` (the plan prompt)
  - Modify `docs/starters/brownfield.vi.md` (the same line)
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** two guide pages and their Vietnamese twins; every sentence about a command must match the code of Tracks 1 to 3, and team practices must read as conventions.
- **Interfaces** (the facts; check each against the code and `docs/reference/cli.md` before writing it):
  - Onboarding step 3 names the directory per kind of work: a track's worktree `<parent>/.planning/worktrees/<track-id>` for a track; the parent for setup, roadmap, discuss, plan, orchestrate, and ship; a child's main checkout for `/gin:quick` in that child, as the QA home for QA, and as what other tracks read. The phrase "never on the parent" goes. The `Open:` lines of the role sections stay and agree with it.
  - Tech lead table: the Plan row adds that a track may carry `Reads: <paths>` and that `gin record plan-approved` refuses a path that is not in `workspace.repos`, the beads entry, or the track's own `Repo:`; the Orchestrate row adds the `Reads:` clone check outside team mode.
  - Engineers' section: `Reads:` in the plan track; execute stops with `gin workspace clone <path>` when a named repository is not cloned on this machine; the developer receives each one's `checkout`, `branch`, and `commit` from `gin workspace status --json`; the checkout is read as it is and gin never switches or pulls it (pull it yourself for a newer state); a harness that limits reads to its working directory asks for access to the path; read-only is an instruction, gin does not block writes.
  - A new section on running a track's dependencies, written as team conventions: each repository documents its own run command; the combination of services and a database runs with the team's own tool, a compose file in the parent or the host's preview environment for a pull request; the plan track names the commands a track needs as validation commands; gin starts nothing and has no configuration for it.
  - QA section: QA checks out the track branches under test in each child and starts the combination with the team's tool, or uses the preview environment; in a workspace `run.json` of `gin-qa e2e run` and `gin-qa tests run` records `checkouts` (the checkout state of the machine that ran the tests, not what an environment deployed); by convention a tester who tests a preview environment names each repository's pull request URL in the approval comment.
  - `brownfield.md:347`: after "Each track names its repository", add that a track that reads the legacy names it with `Reads:`, for example `Reads: legacy/shop-portal`.
  - Vietnamese pages: read `~/.claude/plugins/marketplaces/vietnamese-language-skill/skills/vietnamese-tech-writing/SKILL.md` first; keep anchors, identifiers, commands, and paths verbatim; the same facts as the English page.
- **Steps**:
  1. Read the changed code and skills of Tracks 1 to 3 and the `gin workspace status`, `gin team`, and gin-qa sections of `docs/reference/cli.md`.
  2. Edit the four pages per the interfaces: sentence-case headings, no em or en dashes, sentences of at most 35 words, one home per fact (link to `docs/reference/cli.md` for fields and messages instead of restating them).
  3. Run `python3 plugins/gin-workflow/src/scripts/gin docs check docs/guides/workspace.md docs/guides/workspace.vi.md docs/starters/brownfield.md docs/starters/brownfield.vi.md` → ok.
  4. Run `timeout 300 python3 -m pytest tests/workflow_core/test_walkthrough_docs.py tests/workflow_core/test_docs_coverage.py tests/workflow_core/test_rename_sweep.py tests/workflow_core/test_config_examples.py -q` → pass. Move a pinned sentence in a test only when the text it pins moved; never weaken a test.
  5. Commit: `docs(workspace): one directory to open, read-only repositories, and running a track's dependencies (gin-workflow-ws-track-env)`.
- **Acceptance criteria**: R10, the starter part of R11; US-4; US-5; US-6 criterion 4.
- **Estimated complexity**: medium

## Integration
- **Branch**: `feat/ws-track-env`
- **Merge strategy**: sequential

## Validation
- [ ] Each track's targeted tests pass (the commands in its steps).
- [ ] `gin docs check` is ok on every changed page.
- [ ] The full suite passes once at ship (`gin evidence run` on `feat/ws-track-env`, `project.run_at: push`).
- [ ] `gin specs lint --spec .planning/specs/2026-11-15-ws-track-env-design.md` prints `ok`.

## Notes
- The user may override `Model:` and `Effort:` before plan approval.
- This epic runs with the project's settings: no track worktrees, no review ledger (`project.review_ledger: false`), an independent reviewer per track (`project.review: independent`), and the tests of the changed code per track.
- The workspace knowledge record (`.planning/knowledge/workspace.md`) is updated at ship (R11).
- Deliverable merge-holds apply only to the parent bead `gin-workflow-ws-track-env`; track beads close after their tests and review pass.
