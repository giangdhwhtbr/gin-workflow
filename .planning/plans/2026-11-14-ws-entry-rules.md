# Plan: Per-entry checks, rule packs, and shape in a workspace

Spec: .planning/specs/2026-11-14-ws-entry-rules-design.md
Epic: gin-workflow-ws-entry-rules
Workflow: gin-workflow-ws-entry-rules

## Objective

In a workspace child or its worktree, `gin evidence`, `gin rules`, `gin setup doctor`, and `gin state` use the current entry's checks, packs, checkout, and shape; the execute and worktrees skills read them from `gin state`; the parent and plain repositories behave as today.

**Goal** (spec): inside a workspace child, or a worktree of one, `gin evidence`, `gin rules`, `gin setup doctor`, `gin state`, and the execute and worktrees skills use the current entry's `verify.checks`, rule packs, and shape instead of the parent's.

**Architecture**: one helper in `workspace.py`, `current(cwd)`, returns the `Located` of `cwd` and, when it is a child, the git top level of `cwd` (the child checkout or its linked worktree). `Repo` gains `packs`. `gin state` adds `workspace.current` from `summary`. `verification.main`, `rules.main`, and the setup doctor call `current` when no `--repository` is given; hooks and `quick-check` already resolve the entry and are untouched.

**Tech Stack**: Python 3 standard library; unittest/pytest with the workspace fixtures of `tests/workflow_core/test_workspace_cli_resolution.py` (`self.root`, `self.child = services/api`, a track worktree) and `test_hooks.py`; Markdown skills under the budget tests.

**Global Constraints** (spec, verbatim):
- Out of scope: `java` and `spring` rule packs and tech-doc route scouting for Spring, JAX-RS, Struts, and JSP (split into a follow-up epic, added to the roadmap with `/gin:roadmap`); team init per child (`gin-workflow-ws-child-setup`); `project.packages` inside a child.
- `gin state` JSON only gains `workspace.current`; gin-console parses no removed or renamed key.
- The entry `rules` field is optional; existing workspace manifests stay valid without a schema version change.
- A command run with an explicit `--repository` behaves as before.

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
- Problem statement: evidence, rules, doctor, and state collapse a child to the parent, so a child is checked, ruled, and described with the parent's settings.
- Success criteria: spec requirements 1–7 and US-1 to US-3; `python3 -m pytest -n auto` passes.
- Constraints: Global Constraints above.
- Non-goals: JVM packs and route scouting; team init per child.

## Approach Options
### Option 1: one `current(cwd)` helper, additive state, entry `rules.packs` (selected in `/discuss`)
- Summary: as the spec.
- Pros: one resolution rule shared by every command; no change to `project.*`; packs explicit like the root config.
- Cons: a new optional manifest field.

### Option 2: change `repository_root` to return the child
- Summary: flip the default resolution for every CLI.
- Pros: one-line change.
- Cons: breaks commands that must run at the parent (task, state gates, specs); rejected.

### Recommended Approach
- Selected option: Option 1 (confirmed in `/discuss` on 2026-11-14).
- Rationale: targeted; matches how hooks and quick-check already resolve the entry.

## Scope
- In scope: spec requirements 1–7.
- Out of scope: see Global Constraints.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Track 2 uses the helper and Repo.packs from Track 1, and Track 3 documents both; one lane.
```

## Tasks

`W` is `plugins/gin-workflow/src/scripts/workflow_core`. Run tests from the repository root.

### Track 1: resolver, entry packs field, `workspace.current`, and evidence in a child
- **Dependencies**: none
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/workspace.py:28-40,78-96,183-195` (`Repo.packs`, `_entry`, `current`, `summary`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/schemas.py:93-100` (entry `rules`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/verification.py:84-100` (`main`)
  - Test `tests/workflow_core/test_workspace.py`, `tests/workflow_core/test_workspace_cli_resolution.py`, `tests/workflow_core/test_hooks.py` (or a new `tests/workflow_core/test_evidence_workspace.py`)
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** bounded additions to one module family with an existing workspace fixture and the hooks pattern to copy.
- **Interfaces**:
  - `Repo.packs: tuple[str, ...] = ()`; `_entry` reads `raw.get("rules", {}).get("packs", [])`, each a non-empty string, else `WorkspaceError("workspace.repos: <path>: rules.packs must be a list of pack names")`.
  - Schema: entry property `"rules": {"type": "object", "properties": {"packs": {"type": "array", "items": {"type": "string", "minLength": 1}}}, "additionalProperties": False}`.
  - `workspace.Current` (frozen dataclass): `located: Located`, `checkout: Path | None` (git top level of `cwd` when `located.entry` is set, else None). `workspace.current(cwd: Path) -> Current` uses `locate(cwd)` and `git rev-parse --show-toplevel` in `cwd` (same call as `qa_root`).
  - `summary(located)` adds `"current": {"path": entry.path, "shape": entry.shape, "checks": dict(entry.checks)}` when `located.entry` is set, else `None`. No other key changes.
  - `verification.main`: when `--repository` is not given, `here = workspace.current(Path.cwd())`; with `here.checkout`, `run` uses `here.checkout` (the hook path then scopes to the entry and records at `here.located.root`), and `check(here.checkout, commit, events_root=here.located.root)`; otherwise behaviour is today's `repository_root` path. An explicit `--repository` is unchanged.
- **Steps**:
  1. Failing tests:
     - `test_workspace.py`: an entry with `rules: {packs: [react]}` parses to `Repo.packs == ("react",)`; `packs: [""]` raises `WorkspaceError`; a manifest without `rules` still parses; schema accepts the entry with `rules.packs`.
     - `test_workspace_cli_resolution.py`: extend `test_state_is_the_same_from_parent_child_and_track_worktree` (or add a sibling test) so the `services/api` entry has `shape: backend` and `verify: {checks: {test: "<cmd>"}}`; `gin state --format json` from the parent has `workspace.current` `None`; from the child and its track worktree `{"path": "services/api", "shape": "backend", "checks": {"test": "<cmd>"}}`; `project` is identical in all three.
     - Evidence (copy the workspace setup of `test_hooks.py:440-540`, where a child has a `test` check that touches a marker file): from the child, `gin evidence run` (no `--repository`, cwd the child) exits 0 and runs the child's check (marker exists in the child); `gin evidence check --json` from the child's linked worktree after a run there returns a record; from the parent, `run` behaves as before (uses the parent's `verify.commands`).
     Run them → fail.
  2. Implement per Interfaces.
  3. `python3 -m pytest tests/workflow_core/test_workspace.py tests/workflow_core/test_workspace_cli_resolution.py tests/workflow_core/test_hooks.py -q -n auto` → pass (plus the new evidence test file if created).
  4. Commit: `feat(workspace): current entry in gin state, entry rules.packs, evidence in a child (gin-workflow-ws-entry-rules)`.
- **Acceptance criteria**: spec requirements 1, 2, 3, and the schema part of 4; US-1; US-3 bullets 1–2.
- **Estimated complexity**: medium

### Track 2: rules and doctor per entry
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/rules.py:241-296` (`main`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/setup_service.py:422-575` (`doctor`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/cli.py:150-158` (pass the current checkout to doctor)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/workspace.py:214-247` (`doctor`: pack proposals)
  - Test `tests/workflow_core/test_rules.py`, `tests/workflow_core/test_workspace_cli.py`
- **Provider role**: `backend`
- **Model:** `opus`
- **Effort:** `high`
- **Why:** cross-module change (rules, setup doctor, workspace doctor, CLI plumbing) where the parent path must stay byte-for-byte unchanged.
- **Interfaces**:
  - `rules.main`: when `--repository` is not given and `workspace.current(Path.cwd()).checkout` is set: `config` is the parent's (`_load_config(located.root)`) with `rules.packs` replaced by the parent's packs plus `entry.packs` (order kept, duplicates dropped); project rules from `load_project_rules(checkout)`; each `--files` value made relative to `checkout` by `_relative(checkout, f)`; `--list` uses the same merged config. Otherwise today's path.
  - `setup_service.doctor(repository, *, probe=False, current: Path | None = None, **_)`: `current` is the child checkout (the CLI passes `workspace.current(Path.cwd()).checkout` when the user gave no `--repository` and the action is `doctor`). With `current` and its entry: `checks_details["verify_commands"]["missing"]` lists the lint/typecheck/test/build names absent from `entry.checks`; `hook_findings(current)`; `rules_doctor(current, <parent config with the merged packs>)`; a `checks_details["entry"] = {"path", "shape"}` names it. Without `current`, unchanged.
  - `workspace.doctor(root, space)`: for each present, workable entry, `repos[path]["proposed_packs"] = sorted(set(propose_packs(checkout, plugin)) - {"core"} - set(repo.packs))` and, when non-empty, an action `"<path>: rules.packs could add <a>, <b>"`. Load plugin packs once with `load_plugin_packs(plugin_rules_dir())`; a `RulesError` skips proposals.
- **Steps**:
  1. Failing tests:
     - `test_rules.py` (build a workspace like `test_workspace_cli_resolution.py`, entry `apps/web` with `rules: {packs: [react, nextjs]}` and the parent `rules.packs: [core]`): `gin rules --files app/page.tsx --format json` run with cwd `apps/web` selects `nextjs` and `react`; the same in an entry without packs selects only the parent's; an absolute path to `apps/web/app/page.tsx` from the child matches `nextjs`; from the parent with `--files apps/web/app/page.tsx` the output is unchanged from today.
     - `test_workspace_cli.py`: `gin setup doctor --format json` with cwd the child reports `checks_details.entry.path` and `verify_commands.missing` from the entry's checks; from the parent it is unchanged; the workspace section proposes `react` for a child whose `package.json` depends on `react` and whose entry lists no packs, and proposes nothing once the entry lists it.
     Run → fail.
  2. Implement per Interfaces. Keep the parent and non-workspace paths unchanged; extract the merged-config computation into one function in `rules.py` (`entry_config(parent_config, entry) -> dict`) used by both `rules.main` and `doctor`.
  3. `python3 -m pytest tests/workflow_core/test_rules.py tests/workflow_core/test_rules_checks.py tests/workflow_core/test_workspace_cli.py tests/workflow_core/test_setup_cli.py -q -n auto` → pass.
  4. Commit: `feat(rules): packs, project rules, and doctor per workspace entry (gin-workflow-ws-entry-rules)`.
- **Acceptance criteria**: spec requirements 4 and 5; US-2.
- **Estimated complexity**: high

### Track 3: skills and docs
- **Dependencies**: Track 2
- **Files**:
  - Modify `plugins/gin-workflow/src/skills/execute/SKILL.md:21`
  - Modify `plugins/gin-workflow/src/skills/worktrees/SKILL.md:30-31,36-39`
  - Modify `docs/reference/config.md` (workspace entry fields), `docs/reference/cli.md` (`state`, `evidence`, `rules`, `setup doctor`), `docs/guides/workspace.md`
  - Test `tests/workflow_core/test_token_budget.py`, `tests/workflow_core/test_skill_routing.py`, `tests/workflow_core/test_docs_coverage.py` (unchanged; must pass)
- **Provider role**: `docs`
- **Model:** `haiku`
- **Effort:** `low`
- **Why:** short text edits with exact wording, guarded by the budget and docs tests.
- **Steps**:
  1. `execute/SKILL.md:21`: "- Read the shape appendix (plugin `references/shape-<shape>.md`) for `workspace.current.shape` from `gin state --format json`, else `project.shape`, before editing." Keep the execute stage within its budget (`test_token_budget.py`).
  2. `worktrees/SKILL.md`: Baseline: "Run the project test command: `workspace.current.checks.test` from `gin state --format json` in a workspace child, else the configured `verify.commands`." Workspace section: "Read `references/shape-<shape>.md` for `workspace.current.shape`."
  3. `config.md`: in the workspace `repos` paragraph add "`rules` (`packs`: rule packs added to the root `rules.packs` inside that repository)". `cli.md`: `gin state` lists `workspace.current` (`{path, shape, checks}` or null); `gin evidence` from a child checks that checkout and records in the parent; `gin rules` in a child adds the entry's packs, reads its `.agent-workflow/rules`, and takes paths relative to the child; `gin setup doctor` in a child reports the entry's checks and rules, and the workspace section proposes packs per entry. `workspace.md`: one paragraph on per-entry checks, packs, and shape, linking to config and cli.
  4. `python3 -m pytest tests/workflow_core/test_token_budget.py tests/workflow_core/test_skill_routing.py tests/workflow_core/test_docs_coverage.py -q` → pass; `gin docs check docs/reference/config.md docs/reference/cli.md docs/guides/workspace.md` → ok; `python3 -m pytest -n auto` → pass.
  5. Commit: `docs(workspace): per-entry checks, packs, and shape in skills and reference (gin-workflow-ws-entry-rules)`.
- **Acceptance criteria**: spec requirements 6 and 7; US-3 bullet 3.
- **Estimated complexity**: low

## Integration
- **Branch**: `feat/ws-entry-rules`
- **Merge strategy**: sequential

## Validation
- [ ] `python3 -m pytest -n auto` passes
- [ ] `gin docs check` passes on the changed docs
- [ ] `gin state --format json` `project` is identical from parent, child, and worktree

## Notes
- The user may override `Model:` and `Effort:` before plan approval.
- Deliverable merge-holds apply only to the Parent Bead; track beads close once tests and review pass.
- Backend tracks route to antigravity by the repository's `by_tier` config; dispatch from the track worktree now resolves its repository.
