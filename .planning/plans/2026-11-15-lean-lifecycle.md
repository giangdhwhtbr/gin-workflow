# Plan: Lean lifecycle: the host owns CI and approvals, tests run once, the ledger is optional

Spec: .planning/specs/2026-11-15-lean-lifecycle-design.md
Epic: gin-workflow-ws-ship-records

## Objective

`team.approvals.<gate>: host` trusts a merged pull request, `gin record shipped` takes one pull request per repository, `gin team deps` works for workspace children, `verify.run_at` decides where the full suite runs, and the skills follow `project.run_at`, `project.review_ledger`, `project.review`, and `project.worktree`.

**Goal** (spec): gin prefers the tools a project already has. A merged pull request counts as approved when the team says the host enforces approvals; the full test suite runs once per epic (or on the host) instead of before every review; the skills run no review ledger when it is off and follow `project.review` and `project.worktree`; `gin record shipped` takes one pull request per repository; and `gin team deps` finds the pull requests of a workspace child.

**Architecture**:
- Team policy (`workflow_core/team.py`, `schemas.py`): `host` is a fourth policy form next to a role list, `{all, any}`, and `area_lead`; `check_approval` skips every approver rule for it. `authorize_record` and `lifecycle_cli.py` accept several shipped URLs and add `pull_requests` to the proof.
- `workflow_core/team_beads.py`: `deps` resolves a blocking track's repository from the plan file and searches there; `deps_for` checks the merge commit in the right repository.
- Settings (`workflow_core/project.py`, `schemas.py`): `verify.run_at` with a rigor default, exposed as `project.run_at`; `hooks.py` skips the pre-push commands for `host`; `quick-check` reports `run_at` and takes `review` from the settings.
- Skills: the ledger procedure moves to `skills/review/ledger.md`, read on demand; review, execute, ship, worktrees, orchestrate, quick, setup, team-setup, and workflow branch on the four project settings.
- Docs follow.

**Tech Stack**: Python 3 standard library, PyYAML, jsonschema; unittest/pytest; fixtures in `tests/workflow_core/team_fixtures.py` (`make_team_repo`, `fake_cli`, `gh_pr`, `init_beads`, `run_cli`); `gin docs check`.

**Global Constraints** (spec "Errors and compatibility", verbatim):
- Existing configs stay valid: no key is removed, and `verify.run_at` and `host` are additions. The default behaviour changes for `easy` and `standard` projects (the suite at push instead of per track); `verify.run_at: track` restores it.
- `gin state --format json` gains `project.run_at`; the shipped proof gains `pull_requests`; `gin team pending` rows gain a note. Nothing is renamed or removed (gin-console reads only derived gates).
- With `host` approvals, a pull request merged without review passes; that is the host's branch protection to prevent.
- With `push`, a regression outside a track's own tests shows at ship, not after the track; with `host`, gin never sees test results.
- A failed `gin evidence run` at ship stops before any merge.
- `gin team deps` with a plan file that is missing in the checkout reports the placeholder as waiting with "pull the merged plan".

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
- Problem statement: gin repeats in-session what the host already enforces (approvals, the full suite) and its skills ignore the settings that would make a project lighter (`review_ledger`, `review`, `worktree`).
- Success criteria: spec R1 to R15 and US-1 to US-6, as tests (code) or checked text (skills, docs); existing tests pass; budgets hold.
- Constraints: Global Constraints above; optional schema keys need no `schema_version` bump (precedent: `workspace.repos[].rules.packs` in `f13dddb7`, the kind map in `6fe6ad1b`; `CURRENT_VERSION` stays `2.10`); stage chains are tight (discuss 11,014, plan 11,737, execute 11,914, ship 11,463, review 11,954 of 12,000), so skill text is paid for by moving the ledger procedure into a reference; each stage skill names `project.team` on one line only (`test_team_guidance_loads_on_demand`); core skills never name `gin-qa` or `gin-ba`.
- Non-goals: a host API for branch protection; reading CI status; review per epic; removing role policies; changing `gin team complete`.

## Approach Options
### Option 1: settings the skills follow, plus one new policy value (confirmed)
- Summary: as the Architecture above.
- Pros: every change is an addition; `strict` projects and role policies behave as today.
- Cons: three modes for the suite and two for review must stay documented and tested.

### Option 2: remove the per-track suite, the ledger, and role policies outright
- Summary: one fixed lean flow.
- Pros: least text and code.
- Cons: breaks teams that rely on `{all, any}` policies and the ledger audit trail; needs a config migration; rejected in `/discuss`.

### Recommended Approach
- Selected option: Option 1 (confirmed in `/discuss` on 2026-11-15).
- Rationale: the lean flow becomes the default for `easy` and `standard` without taking anything from `strict`.

## Scope
- In scope: R1 to R15.
- Out of scope: see Non-goals.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Tracks 1 and 3 both change schemas.py and lifecycle_cli.py, Tracks 1 to 3 all edit docs/reference/cli.md and config.md, and Tracks 4 and 5 describe the behaviour of Tracks 1 to 3. One lane.
```

## Tasks

`W` is `plugins/gin-workflow/src/scripts/workflow_core`; `S` is `plugins/gin-workflow/src/skills`.

### Track 1: Host-trusted approvals and several shipped pull requests
- **Dependencies**: none
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/schemas.py:20-28,58-66` (the `host` policy form)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team.py:90-150` (`validate_team`), `:465-531` (`check_approval`), `:543-588` (policy helpers), `:619-663` (`verify_gate`, `authorize_record`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team_pending.py` (the `approvals: host` note)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/lifecycle_cli.py:195-198` (`_proof`), `:340-365` (record), `:799` (`--evidence`)
  - Modify `docs/reference/cli.md`, `docs/reference/config.md`
  - Test `tests/workflow_core/test_team_gates.py`, `tests/workflow_core/test_team_pending.py`, `tests/workflow_core/test_lifecycle_cli.py`
- **Provider role**: `backend`
- **Model:** `opus`
- **Effort:** `medium`
- **Why:** the approval policy runs through kind maps, waivers, pending, CODEOWNERS, and record; broad context, bounded logic.
- **Interfaces**:
  - Schema: `host` (the constant string) is valid wherever a gate policy is: `team.approvals.requirement_confirmed` (also as a value of its kind map), `plan_approved`, `ship`, `roadmap`.
  - `team.HOST = "host"`. `team._has_policy(policy, areas)` is True for `HOST`; `policy_parts(HOST)` and `policy_roles(HOST, team)` stay empty (no approver roles), so `can_waive` allows any member and CODEOWNERS gets no approver owners from it. `validate_team` must not read `host` as a role list (a string iterated per character); `single_holder_notes` and `gate_policy_gap` treat it as a policy without roles.
  - `team.check_approval(...)`: when `policy_for(team, gate, kind) == HOST`, the reasons are only: the repository mismatch; the merged state (`shipped`: must be merged; `ship`: `open` or `merged`; other gates: merged unless `before_merge`); for spec and plan gates, "PR does not change <artifact>"; for `plan_approved`, the `check_plan` reasons. No `local_head` comparison, no `approval_note`, no role, author, or sole-holder logic.
  - `team.verify_gate(...)`: no `_head` lookup when the ship policy is `HOST`.
  - `team.authorize_record(root, team, gate, evidence, ...)`: `evidence` may be a string or a sequence of strings. For `shipped` with a ship policy, every item must be an `http(s)` URL; each is verified with `verify_gate`; reasons are prefixed `<url>: `; two URLs with the same `repo_id` add `<url>: <repository> is already covered by <other url>`; any reason raises `TeamRejected`. The payload keeps `pr_url`, `merge_commit`, `approvers`, and `repository` of the first URL and adds `pull_requests: [{"pr_url", "merge_commit", "repository"}, ...]` for all. Other gates with more than one item raise `TeamError("only shipped takes several --evidence values")`.
  - `gin record <gate> --evidence <value> [--evidence <value>]...`: `--evidence` is repeatable; the event's `evidence` and the idempotency key use the values joined by `, `; outside team mode several values are recorded as that joined string. `_proof` copies `pull_requests` into the bead's gate metadata when the payload has it.
  - `team_pending.pending`: a gate row whose policy (for the row's epic kind) is `HOST` gets `approvals: host` in `notes`; its `missing` holds only non-approval reasons.
  - `gin team check --gate <gate> <url>` with a `HOST` policy prints `ok (approvals are enforced by the host)` when no reason remains.
- **Steps**:
  1. Failing tests:
     - `test_team_gates.py`: with `ship: host`, `record shipped` of a merged pull request with no review succeeds; an open one is refused with `PR is open, not merged`; `team check --gate ship` of an open, unapproved pull request exits 0 with the host line and does not compare HEAD; `requirement_confirmed: host` and a kind map `{capability: host, technical: [be_lead]}` (host for one kind, roles for the other); `plan_approved: host` still reports `check-plan` errors; any member may `gin unblock` a host gate; `team init` prints no "gates without a role policy" warning; a team with `ship: [be_lead]` still gets `missing approval from one of be_lead`; `team.approvals.ship: hosted` is a config error.
     - `test_team_gates.py` (shipped): two URLs (parent and child) record `pull_requests` with two entries and `pr_url` of the first; two URLs of one repository are refused and nothing is recorded; one unmerged URL refuses both with a reason that starts with that URL.
     - `test_team_pending.py`: an open `spec/` pull request under `requirement_confirmed: host` has `missing == []` and `approvals: host` in `notes`.
     - `test_lifecycle_cli.py`: `record plan-approved --evidence a --evidence b` exits 2; outside team mode `record shipped --evidence a --evidence b` records `a, b`.
  2. Run `timeout 600 python3 -m pytest tests/workflow_core/test_team_gates.py tests/workflow_core/test_team_pending.py tests/workflow_core/test_lifecycle_cli.py -q` → fail.
  3. Implement per the interfaces.
  4. Run step 2 → pass; `timeout 900 python3 -m pytest tests/workflow_core -q -n auto -k "team or lifecycle or schema"` → pass; `gin docs check docs/reference/cli.md docs/reference/config.md` → ok.
  5. Commit: `feat(team): host-trusted approvals and several pull requests in record shipped (gin-workflow-ws-ship-records)`.
- **Acceptance criteria**: R1, R3, R4; US-1; US-2.
- **Estimated complexity**: medium

### Track 2: `gin team deps` for workspace children
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team_beads.py:579-626` (`deps`, `_has_commit`, `deps_for`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team_cli.py` (the `deps` output and the `deps --bead` call)
  - Modify `docs/reference/cli.md`
  - Test `tests/workflow_core/test_team_beads.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** two functions in one module with helpers that exist (`plan_tracks`, `_track_repo`, `default_branch`); clear spec.
- **Interfaces**:
  - `team_beads._blocking_repo(root: Path, plan: str, number: int) -> tuple[Path, str | None]`: the repository of track `number` in `root / plan` (`team.plan_tracks`; its `repo` field): `(root, None)` without a `Repo:`; else `_track_repo(root, repo)[0]` and the path. A missing plan file raises `SyncConflict(f"{plan} is not in this checkout; pull the merged plan")`; an unknown track number means no `Repo:`.
  - `deps(root, team)`: per placeholder, `_blocking_repo`; its `SyncConflict` puts the placeholder in `waiting` and its message in a new `reasons: {<id>: <message>}` key; else `merged_with_text(team.host, plan, repo_dir)`; on close, `--set-metadata merge_commit=<sha>` and, with a repository path, `--set-metadata repo=<path>`. The existing keys `closed`, `waiting`, `unresolved` keep their shapes.
  - `deps_for(root, bead, cwd: Path | None = None)`: `cwd` (default `Path.cwd()`) names the current repository: `workspace.locate(cwd).entry.path`, or None for the parent. For a closed placeholder with a merge commit: when its metadata `repo` equals the current repository (both None, or the same path), the commit must be an ancestor of HEAD in `git -C <cwd> rev-parse --show-toplevel`; otherwise, in the placeholder's repository checkout (`_track_repo(root, repo)`, or `root` for None), `git merge-base --is-ancestor <commit> origin/<default_branch>` (`default_branch(repo_dir, entry)`), and a miss gives the reason `<commit> is not on origin/<default_branch> of <path>; run git -C <path> fetch origin`. A `SyncConflict` from `_track_repo` (not cloned) becomes that dependency's reason.
  - CLI text: `waiting <id> (<reason>)` when a reason exists; `team deps --bead` passes the current directory.
- **Steps**:
  1. Failing tests in `tests/workflow_core/test_team_beads.py` (reuse the child workspace fixture of `TestTeamClaimWorktree`; a plan file in the parent with `- **Repo**: services/order-api` on track 2; a `gh` fake that answers `pr list --state merged --search` only when run in the child directory):
     - `deps` closes `external: <plan>#2` with `repo: services/order-api` and `merge_commit` in its metadata;
     - with the child not cloned, the placeholder stays in `waiting`, `reasons` names `gin workspace clone services/order-api`, and the text shows it;
     - with the plan file missing, `reasons` says to pull the merged plan;
     - `deps --bead` from the child worktree of the same repository passes when HEAD contains the commit and fails with the fetch/rebase message when it does not (today's behaviour, now in the child);
     - `deps --bead` from the parent passes when the commit is on the child's `origin/main` and fails with `run git -C ... fetch origin` when it is not;
     - the existing single-repository `deps` tests pass unchanged.
  2. Run `timeout 600 python3 -m pytest tests/workflow_core/test_team_beads.py -q` → fail.
  3. Implement per the interfaces.
  4. Run step 2 → pass; `timeout 900 python3 -m pytest tests/workflow_core -q -n auto -k "team or workspace"` → pass; `gin docs check docs/reference/cli.md` → ok.
  5. Commit: `feat(team): team deps finds and checks pull requests of workspace children (gin-workflow-ws-ship-records)`.
- **Acceptance criteria**: R5, R6; US-3.
- **Estimated complexity**: medium

### Track 3: `verify.run_at` in settings, hooks, and quick-check
- **Dependencies**: Track 2
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/schemas.py:262` (`verify.run_at`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/project.py:11-17,21-38,52-75` (`RIGOR_PRESETS`, `ProjectSettings.run_at`, `project_settings`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/hooks.py:100-127,166-205` (`_scoped`, `status_report`, `verify`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/lifecycle_cli.py:664-692` (`_quick_check_command`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/setup_service.py` (doctor reports `run_at`)
  - Modify `docs/reference/config.md`, `docs/reference/cli.md`
  - Test `tests/workflow_core/test_project_settings.py`, `tests/workflow_core/test_hooks.py`, `tests/workflow_core/test_lifecycle_cli.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `high`
- **Why:** bounded change with a clear spec, but the hook, the evidence record, and quick-check each have their own edge cases.
- **Interfaces**:
  - Schema: `verify.run_at` in `track`, `push`, `host`; optional.
  - `project.RIGOR_PRESETS[rigor]["run_at"]`: `easy` and `standard` → `push`; `strict` → `track`. `ProjectSettings.run_at: str = "push"`; `project_settings` reads `verify.run_at`, else the preset. `ProjectSettings.to_dict()` then puts `run_at` into `gin state --format json` under `project`.
  - `hooks.verify(root, "pre-push")` with `run_at == "host"`: prints `gin pre-push: the host CI runs the tests (verify.run_at: host); nothing to run` to stderr, runs no command, records nothing, returns 0. `gin evidence run` goes through the same code and so does the same. `track` and `push` are unchanged, including the "already passed on this tree" skip. The pre-commit hook is unchanged in every mode.
  - `hooks.status_report(root)`: with `host`, a project whose only missing commands are the pre-push ones still reports `ok` when the hooks are installed; the report gains `run_at`.
  - `_quick_check_command`: the result gains `run_at`; `review` is `settings.review` (was derived from the rigor); with `host`, `verify_commands` holds only `lint` and `typecheck`.
  - `gin setup doctor --format json`: `checks_details.verify_commands` gains `run_at`.
- **Steps**:
  1. Failing tests:
     - `test_project_settings.py`: defaults `push`, `push`, `track` for `easy`, `standard`, `strict`; an explicit `verify.run_at: host`; `verify.run_at: nightly` is a config validation error; `to_dict()` has `run_at`.
     - `test_hooks.py`: with `host`, `gin hooks run pre-push` runs no command (a `verify.checks.test` that would fail), prints the host line, exits 0, and records no `checks.passed`; `gin evidence run` likewise; `gin hooks status` is ok; with `push`, a second pre-push on the same tree prints "already passed" (existing behaviour, asserted for the mode); pre-commit still runs `lint`.
     - `test_lifecycle_cli.py`: `quick-check` reports `run_at`; `host` drops `test` and `build`; `project.review: self_check` on `standard` rigor gives `review: self_check`.
  2. Run `timeout 600 python3 -m pytest tests/workflow_core/test_project_settings.py tests/workflow_core/test_hooks.py tests/workflow_core/test_lifecycle_cli.py -q` → fail.
  3. Implement per the interfaces.
  4. Run step 2 → pass; `timeout 900 python3 -m pytest tests/workflow_core -q -n auto -k "project or hooks or lifecycle or setup or schema or evidence or verification"` → pass; `gin docs check docs/reference/config.md docs/reference/cli.md` → ok.
  5. Commit: `feat(verify): verify.run_at decides where the full suite runs (gin-workflow-ws-ship-records)`.
- **Acceptance criteria**: R7, R8, R10 (doctor), R12 (quick-check); US-4 criteria 1 and 3.
- **Estimated complexity**: medium

### Track 4: Skills follow run_at, review_ledger, review, and worktree
- **Dependencies**: Track 3
- **Files**:
  - Create `plugins/gin-workflow/src/skills/review/ledger.md`
  - Modify `plugins/gin-workflow/src/skills/review/SKILL.md`, `plugins/gin-workflow/src/skills/review-response/SKILL.md`, `plugins/gin-workflow/src/agents/code-reviewer.md`
  - Modify `plugins/gin-workflow/src/skills/execute/SKILL.md`, `plugins/gin-workflow/src/skills/ship/SKILL.md`, `plugins/gin-workflow/src/skills/worktrees/SKILL.md`, `plugins/gin-workflow/src/skills/orchestrate/SKILL.md`, `plugins/gin-workflow/src/skills/quick/SKILL.md`
  - Modify `plugins/gin-workflow/src/skills/setup/SKILL.md`, `plugins/gin-workflow/src/skills/team-setup/SKILL.md`, `plugins/gin-workflow/src/skills/workflow/SKILL.md`, `plugins/gin-workflow/src/skills/team/references/workspace.md`, `plugins/gin-workflow/src/references/stage-contract.md`
  - Test `tests/workflow_core/test_skill_routing.py`, `tests/workflow_core/test_token_budget.py`
- **Provider role**: `docs`
- **Model:** `opus`
- **Effort:** `high`
- **Why:** rewrites the review procedure and branches five stage skills on four settings under budgets with under 100 characters of headroom; needs the whole lifecycle in view.
- **Interfaces** (facts the text must carry; wording may be tighter; every setting is read from `project` in `gin state --format json`):
  - `review/SKILL.md`: keeps what holds in both modes (when to review, picking the reviewer with `gin reviewer`, the fresh context, independence, what the reviewer inspects, findings graded by rule, cycles bounded by `project.max_cycles`, never manufacture approval). `project.review: self_check`: no reviewer; the implementer re-reads the diff for debug leftovers, secrets, and test coverage. `project.review_ledger: false`: no `review-ledger.py` command and nothing under `.planning/reviews/`; the reviewer returns a verdict (`approved` or `changes requested`) and each finding with id, severity, file and line, and fix in its report; the implementer fixes through `review-response` and asks the same reviewer again; after `project.max_cycles` cycles without approval, ask the user. `project.review_ledger: true`: read `ledger.md` in this skill's folder and follow it. Tests: with `project.run_at: track`, `gin evidence run` before the request and the reviewer cites `gin evidence check`; with `push` or `host`, no evidence run, and the reviewer runs the tests of the changed code only.
  - `review/ledger.md`: today's ledger procedure moved verbatim in substance (init, checkpoint, `transition-requested`, `start-review` and the lease, `add-finding`, `verify-finding`, `reopen-finding`, `approve`, `render`, `release-lease`, literal flags, the cycle limit and `record-human-decision`, the workspace ledger location).
  - `review-response/SKILL.md` and `agents/code-reviewer.md`: ledger commands only "with the ledger on (the `review` skill)"; otherwise findings and fixes travel in the reports.
  - `execute/SKILL.md` step 4: request review through the `review` skill; close the track with a reason that names the reviewer, the cycle count, and the finding count; `push-refs` only with the ledger on. Step 1 or 2: a track gets its own worktree only for `project.worktree: always`, or `parallel` when the plan's execution strategy is parallel; otherwise it commits on `feat/<topic>` in the current checkout.
  - `orchestrate/SKILL.md` step 6: the same worktree rule (team mode unchanged: `gin team claim`); step 8 evidence names the branch when no worktree is created.
  - `worktrees/SKILL.md`: the baseline run only for `project.run_at: track`.
  - `ship/SKILL.md` step 1: with `project.run_at: push`, run `gin evidence run` once on the feature branch before the options' action and stop on a failure; `host`: no tests; `track`: as today ("Do not run tests" stays true for it). The ledger steps stay conditional on `project.review_ledger`.
  - `quick/SKILL.md`: scope tests to the changed files when `run_at` is `push`; `review` comes from `quick-check`.
  - `setup/SKILL.md`: one question, "does the host run CI on pull requests?", and on yes `--set verify.run_at=host`.
  - `team-setup/SKILL.md`: propose `host` for `requirement_confirmed`, `plan_approved`, `ship`, and `roadmap`; role policies stay available; the branch protection reminder names required status checks.
  - `workflow/SKILL.md:15`: drop "and approval TTL (`policy.approval.ttl_seconds`, ...)" from what `gin state` applies.
  - `team/references/workspace.md` and `references/stage-contract.md`: ledger and evidence sentences say when they apply.
  - Budgets after the change: every stage chain at most 12,000 (`workflow_core.budget.stage_chars`); shared skills at most 6,000; agents at most 4,000. `workflow_core/budget.py` puts a file into a stage chain when the skill links it (`](x.md)`) or mentions a `references/<name>.md` path (`_REFERENCE`, `_LINK`, `budget.py:12-13`), so the review skill names `ledger.md` in backticks, with no link and no `references/` path; it then loads on demand and stays out of the review chain. `test_token_budget.py` gains a limit of 6,000 characters for `skills/review/ledger.md`.
- **Steps**:
  1. Failing tests in `tests/workflow_core/test_skill_routing.py`: the review skill has no `init --repo-id`, `checkpoint --repo-id`, or `transition-requested`, names `ledger.md` with `project.review_ledger`, and `ledger.md` is not in `stage_chain(SRC, "review")`; `ledger.md` has those commands; review, execute, ship, worktrees, and quick name `project.run_at`; ship has `gin evidence run` with `push`; execute and orchestrate name `project.worktree`; the review skill names `self_check`; execute has `push-refs` on a line that names the ledger setting; the workflow skill has no `ttl_seconds`; setup has `verify.run_at=host`; team-setup has `host`. Update the existing assertions that pin ledger text in the review skill (`test_skill_routing.py:317`) to the new home.
  2. Run `timeout 300 python3 -m pytest tests/workflow_core/test_skill_routing.py tests/workflow_core/test_token_budget.py -q` → fail.
  3. Edit the skills.
  4. Run step 2 → pass; `timeout 600 python3 -m pytest tests/workflow_core -q -n auto -k "skill or budget or docs or packaging or routing"` and `timeout 120 python3 -m pytest tests/gin_qa/test_packaging.py tests/gin_ba -q` → pass; print every stage chain size.
  5. Commit: `feat(skills): skills follow run_at, review_ledger, review, and worktree; the ledger procedure moves to a reference (gin-workflow-ws-ship-records)`.
- **Acceptance criteria**: R2, R9, R10 (setup question), R11, R12, R13, R14 (skill text), R15; US-4 criterion 2; US-5; US-6.
- **Estimated complexity**: high

### Track 5: Guides and concepts for the lean lifecycle
- **Dependencies**: Track 4
- **Files**:
  - Modify `docs/concepts/lifecycle.md`, `docs/concepts/providers.md`
  - Modify `docs/guides/team.md`, `docs/guides/team.vi.md`, `docs/guides/git-flow.md`, `docs/guides/git-flow.vi.md`, `docs/guides/workspace.md`, `docs/guides/workspace.vi.md`
  - Modify `docs/starters/brownfield.md`, `docs/starters/brownfield.vi.md`
  - Test `tests/workflow_core/test_walkthrough_docs.py`, `tests/workflow_core/test_docs_coverage.py` (run only; change only if a pinned sentence moved)
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** guide text with every rule fixed by the spec and by Tracks 1 to 4; several pages in two languages.
- **Interfaces** (facts; link to `docs/reference/config.md` and `cli.md` for keys and flags instead of restating them):
  - `lifecycle.md`: where tests run by `verify.run_at` and its rigor defaults; review with and without the ledger; `project.review` and `project.worktree`; the approval TTL is not applied by `gin state` (remove the claim at `:133`).
  - `providers.md`: the evidence policy by `verify.run_at`.
  - `team.md`, `git-flow.md`: `team.approvals.<gate>: host` (a merged pull request is the proof; the host's branch protection enforces approvals and required status checks), role policies as the alternative; `record shipped` with one URL per repository; `team deps` across repositories.
  - `workspace.md`: `record shipped` with several URLs replaces the unchecked `"<repo>:<sha>; ..."` form in team mode with a ship policy; `team deps` finds a child's pull request.
  - `brownfield.md`: the walkthrough uses `host` approvals and names where the suite runs.
  - `.vi.md` pages: read `~/.claude/plugins/marketplaces/vietnamese-language-skill/skills/vietnamese-tech-writing/SKILL.md` first; keep English anchors, identifiers, commands, and paths.
- **Steps**:
  1. Edit the pages; check each claim against the code and the reference pages of Tracks 1 to 3 and the skills of Track 4.
  2. Run `timeout 300 python3 -m pytest tests/workflow_core/test_walkthrough_docs.py tests/workflow_core/test_docs_coverage.py tests/workflow_core/test_rename_sweep.py -q` → pass; `gin docs check` on every changed page → ok.
  3. Commit: `docs: lean lifecycle in the lifecycle, team, git-flow, workspace, and brownfield pages (gin-workflow-ws-ship-records)`.
- **Acceptance criteria**: R14.
- **Estimated complexity**: medium

## Integration
- **Branch**: `feat/lean-lifecycle`; tracks commit on it one after another (this project is `standard` with `project.worktree: parallel` and a sequential strategy).
- **Merge strategy**: sequential

## Validation
- [ ] Each track's targeted tests pass
- [ ] `gin evidence run` once on `feat/lean-lifecycle` before the merge (the full suite)
- [ ] `gin docs check` on changed pages
- [ ] Budgets hold (`tests/workflow_core/test_token_budget.py`)

## Notes
- This epic is executed the way it specifies for this project (`standard` rigor, `review_ledger: false`, sequential tracks): no track worktrees, no ledger commands, one independent reviewer run per track with findings in its report, the tests named in each track, and the full suite once at ship. The installed skills still describe the old flow, so this needs the user's approval with the plan.
- `gin evidence run` at ship uses the installed `gin`, which still records a pass for the tree; the pre-push hook then reuses it.
- Deliverable merge-holds apply only to the Parent Bead; track beads close after tests and review pass.
- The user may override `Model:` and `Effort:` before plan approval.
