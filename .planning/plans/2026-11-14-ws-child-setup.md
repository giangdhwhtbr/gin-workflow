# Plan: Workspace onboarding, frozen legacy access, and team init per child

Spec: .planning/specs/2026-11-14-ws-child-setup-design.md
Epic: gin-workflow-ws-child-setup

## Objective

A lead registers workspace repositories with `gin workspace add`, a clone installs its hooks, `gin team init --all-repos` and `gin team hooks --all-repos` put the team files and the commit-msg hook into each workable child, ship checks every child's hooks, skills that read the frozen legacy print the clone command when it is missing, and the workspace guide says what each role clones.

**Goal** (spec): Each role knows what to clone in a workspace, skills that read the frozen legacy say how to clone it when it is missing, setup collects the repository entries through a new `gin workspace add`, a clone installs its hooks, and `gin team init --all-repos` writes the team files into each workable child.

**Architecture**:
- `workflow_core/workspace.py` gains a public `skip_reason(space, repo)` (moved from `hooks._skip_reason`), shared by `gin hooks`, `gin workspace clone`, and `gin team ... --all-repos`.
- `workflow_core/workspace_cli.py` gains `add` (validates with `workspace.repos_from`, writes through `setup_service.configure`) and installs hooks after each new clone (`hooks.install`, `team_init.install_hook`).
- `workflow_core/team_init.py` gains `reroot(glob, child)` and a `child` parameter for `codeowners`, `planned_files`, and `init`; `team_cli.py` gains `--all-repos` for `init` and `hooks`.
- Skill and docs text carries the rest: ship, setup, tech-doc, explain, discuss, gin-ba capture, the workspace guide, the brownfield starter, and the CLI reference.

**Tech Stack**: Python 3 standard library and PyYAML (already used); unittest/pytest (`tests/workflow_core/test_workspace_cli.py`, `test_hooks.py`, `test_team_init.py`, `test_skill_routing.py`, `test_token_budget.py`, `test_walkthrough_docs.py`, `test_docs_coverage.py`, `tests/gin_ba/test_ba_packaging.py`); fixtures `tests/workflow_core/test_workspace.py` (`git`, `init_repo`), `test_workspace_cli_resolution.run`, `tests/workflow_core/team_fixtures.py` (`make_team_repo`, `run_cli`, `TEAM`); `gin docs check`.

**Global Constraints** (spec "Errors and compatibility", verbatim):
- Single-repository projects: nothing changes; `--all-repos` outside a workspace exits 2 (`team init`, `team hooks`), and `gin workspace add` exits 1 with a hint.
- Every child uses `team.host`; a child on another host gets the file names of `team.host` (a known limit).
- In a child, the CI job checks commit messages only; its CODEOWNERS and specs step needs `.agent-workflow/config.yaml`, which children do not have.
- `gin workspace clone --json` rows gain `hooks`; existing keys are unchanged.
- `gin team init` and `gin team hooks` without `--all-repos` behave as before.

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
- Problem statement: a workspace lead edits `workspace.repos` by hand, each member installs hooks per clone by hand, team files land in the parent only, ship checks only the parent's hooks, no skill says how to clone a missing frozen legacy entry, and the guide tells a PM and a BA to clone the parent only.
- Success criteria: spec R1 to R9 and US-1 to US-5, as tests (code) or checked text (skills, docs); existing tests pass; budgets hold (discuss chain 10,790 and ship chain 11,214 of 12,000; gin-ba skills at most 6,000 characters each).
- Constraints: Global Constraints above; core files never name `gin-ba` (`tests/gin_ba/test_ba_packaging.py:74`), so only `plugins/gin-ba/...` and `tests/gin_ba/...` mention capture; `workspace.load` returns None for an empty `workspace.repos` (`workspace.py:132-133`), so `gin workspace add` reads the config itself; `gin workspace` errors print `error: <cause>` and exit 1 (`workspace_cli.py:105-107`); `gin team` maps `TeamError` to exit 2.
- Non-goals: rule packs or checks per entry; the branch model of children; committing or opening pull requests in children; a host per child.

## Approach Options
### Option 1: extend the existing commands and skills (confirmed)
- Summary: as the Architecture above.
- Pros: each command keeps one job; the `--all-repos` commands share the skip rules of `gin hooks install --all-repos`.
- Cons: a new member still runs one clone command per repository (or `--all`).

### Option 2: one `gin workspace onboard` command
- Summary: clone, hooks, and team files in one command.
- Pros: fewer commands to remember.
- Cons: mixes the lead's one-time work (team files, then commits) with each member's clone; duplicates `gin hooks install --all-repos`; rejected in `/discuss`.

### Recommended Approach
- Selected option: Option 1 (confirmed in `/discuss` on 2026-11-14).
- Rationale: the smallest change that covers every requirement and reuses `hooks.install`, `team_init.install_hook`, `workspace.repos_from`, and `setup_service.configure`.

## Scope
- In scope: R1 to R9.
- Out of scope: see Non-goals.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Tracks 1 and 2 both edit workspace_cli.py, Tracks 1 to 3 all edit docs/reference/cli.md, and Track 4's skill and guide text names the commands of Tracks 1 to 3. One lane.
```

## Tasks

`S` is `plugins/gin-workflow/src/scripts/workflow_core`. Every track's tests run from the epic worktree with `python3 -m pytest <files> -q`.

### Track 1: `gin workspace add`
- **Dependencies**: none
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/workspace_cli.py:73-107` (parser: `add`; dispatch; a new `add` function)
  - Modify `docs/reference/cli.md` (the `gin workspace` section: `add`)
  - Test `tests/workflow_core/test_workspace_cli.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** one new subcommand in one module with its validation already written (`repos_from`) and a writer to reuse (`configure`); bounded, clear spec.
- **Interfaces**:
  - `workspace_cli.add(root: Path, path: str, *, url: str, shape: str = "", frozen: bool = False, default_branch: str | None = None, checks: Sequence[str] = ()) -> dict[str, Any]`:
    - `root` is the top level of the current checkout: `git rev-parse --show-toplevel` run in `--repository` or the current directory (a failure raises `WorkspaceError("not a git repository: <dir>")`).
    - Reads `<root>/.agent-workflow/config.yaml` with `yaml.safe_load`; a missing file, or a config whose `workspace` is not a mapping with a `repos` list, raises `WorkspaceError("not a workspace parent: run /gin:setup and answer workspace")`.
    - Each `checks` item must be `<name>=<command>` with a non-empty name and command, else `WorkspaceError("--check must be NAME=COMMAND: <item>")`.
    - Builds `raw = {"path": path, "url": url}` plus `shape` when given, `frozen: true` when set, `default_branch` when given, and `verify: {checks: {...}}` when any check is given; then `workspace.repos_from({"workspace": {"repos": [*existing, raw]}})`, which raises `WorkspaceError` for a bad path, url, shape, check name, a duplicate, or a nested path.
    - Writes with `setup_service.configure(root, assignments=[f"workspace.repos={json.dumps([*existing, raw])}"], approve=True)` (JSON is valid YAML for `_parse_assignment`, `setup_service.py:291-303`; `configure` also refreshes the generated effective config); a `SetupError` is re-raised as `WorkspaceError(str(error))`. The test parents' minimal configs (`schema_version`, `harness`, `workspace`) must pass `configure`'s validation; if they do not, add the keys `configure` needs to the test config, never relax the validation.
    - Returns `{"path": path, "added": True, "next": f"gin workspace clone {path}"}`.
  - CLI: `gin workspace add <path> --url <url> [--shape {frontend,backend,library,qa,beads}] [--frozen] [--default-branch <branch>] [--check NAME=COMMAND]... [--repository <dir>] [--json]`. Text output: `added <path>; next: gin workspace clone <path>`. `add` does not call `ws.locate` (an empty `workspace.repos` gives no `Workspace`, `workspace.py:132-133`). Errors go through the existing `except (ws.WorkspaceError, OSError)` (exit 1).
- **Steps**:
  1. Failing tests in `tests/workflow_core/test_workspace_cli.py` (a new class with a parent whose config has `workspace:\n  repos: []\n`, and the existing `WorkspaceCliTests` parent for the duplicate case), through `run(...)`:
     - `workspace add services/order-api --url file:///x --shape backend --check test=true` exits 0; `workspace status --json` then lists `services/order-api` with `present: false`; the config holds `verify: {checks: {test: 'true'}}`;
     - `--frozen` without `--shape` is accepted;
     - adding `services/api` again (existing parent) exits 1 with `duplicate path` and leaves the config bytes unchanged;
     - `--shape web` exits 1 and leaves the config unchanged;
     - `--check test` (no `=`) exits 1 with `--check must be NAME=COMMAND` and leaves the config unchanged;
     - a repository whose config has no `workspace` exits 1 with `run /gin:setup and answer workspace`;
     - `workspace add --help` describes the flags.
  2. Run `python3 -m pytest tests/workflow_core/test_workspace_cli.py -q` → fail.
  3. Implement per the interfaces.
  4. Run step 2 → pass; `python3 -m pytest tests/workflow_core -q -n auto -k "workspace or setup"` → pass; `gin docs check docs/reference/cli.md` → ok.
  5. Commit: `feat(workspace): gin workspace add records a repository entry (gin-workflow-ws-child-setup)`.
- **Acceptance criteria**: R1; US-1.
- **Estimated complexity**: low

### Track 2: Hooks installed by `gin workspace clone`
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/workspace.py` (a public `skip_reason`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/hooks.py:204-245` (use `workspace.skip_reason`; delete `_skip_reason`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/workspace_cli.py:19-44,98-104` (install hooks after a new clone; text output)
  - Modify `docs/reference/cli.md` (the `gin workspace clone` entry)
  - Test `tests/workflow_core/test_workspace_cli.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** wiring two existing installers into one command plus a move of one helper; bounded, with the statuses already defined.
- **Interfaces**:
  - `workspace.skip_reason(space: Workspace, repo: Repo) -> str | None`: the body of `hooks._skip_reason` (`frozen`, the shape of a non-workable entry, `not cloned`, else None); `hooks._install_all` and `hooks._status_all` call it.
  - `workspace_cli.clone(space, paths, all_repos) -> list[dict]`: after a successful `git clone` of a workable entry, the row gains `hooks: dict[str, str]`:
    - when `repo.checks` is non-empty: `hooks.install(target)`; `pre-commit` and `pre-push` get the states it reports (`installed`, `unchanged`, `chained`, `occupied`), or `missing` when it returns `status: missing`;
    - when `team.team_for_repo(space.root)` is not None and `target / ".githooks/commit-msg"` is a file: `team_init.install_hook(target)`; `commit-msg` gets its `status` (`installed`, `active`, `occupied`, `missing`);
    - rows of frozen or `beads` entries, and rows with status `present`, get no `hooks` key;
    - hook results never raise and never change the exit code.
  - Text output: `<path>: cloned` and, per hook, `<path>: <hook>: <state>`; for `occupied`, also on stderr the chain line of `hooks._install_all` (`add \`exec gin hooks run <hook> "$@"\` to <file> to chain it`) or, for `commit-msg`, `add \`exec "$(git rev-parse --show-toplevel)/.githooks/commit-msg" "$@"\` to <file> to chain it`.
- **Steps**:
  1. Failing tests in `tests/workflow_core/test_workspace_cli.py` (`WorkspaceCliTests` parent):
     - `workspace clone services/api --json` gives `hooks` with `pre-commit` and `pre-push` `installed`, and `services/api/.git/hooks/pre-commit` exists;
     - `workspace clone apps/web --json` (no checks) gives no `pre-commit` key;
     - `legacy/portal` and `.beads` rows have no `hooks` key; a second clone reports `present` with no `hooks` key;
     - with a `team:` block in the parent config (copy `team_fixtures.TEAM`) and a child remote whose `main` commits `.githooks/commit-msg`, the clone row has `commit-msg: installed`;
     - an occupied hook: run the clone with `GIT_TEMPLATE_DIR` set to a folder whose `hooks/pre-commit` is a plain script (git copies template hooks into a new clone); the row says `pre-commit: occupied`, stderr has the chain line, and the exit code is 0.
  2. Run `python3 -m pytest tests/workflow_core/test_workspace_cli.py tests/workflow_core/test_hooks.py -q` → fail.
  3. Implement per the interfaces.
  4. Run step 2 → pass; `python3 -m pytest tests/workflow_core -q -n auto -k "workspace or hooks or team_init"` → pass; `gin docs check docs/reference/cli.md` → ok.
  5. Commit: `feat(workspace): gin workspace clone installs the hooks of a new clone (gin-workflow-ws-child-setup)`.
- **Acceptance criteria**: R2; US-2.
- **Estimated complexity**: medium

### Track 3: `gin team init --all-repos` and `gin team hooks --all-repos`
- **Dependencies**: Track 2
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team_init.py:35-91` (`reroot`; `child` for `codeowners`, `planned_files`, `init`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team_cli.py:17-25,78-95` (`--all-repos` for `init` and `hooks`; per-repository output and exit codes)
  - Modify `docs/reference/cli.md` (the `gin team` section: `init --all-repos`, `hooks --all-repos`)
  - Test `tests/workflow_core/test_team_init.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `high`
- **Why:** bounded change to two modules with a clear spec, but the glob re-rooting and the per-repository results have many edge cases.
- **Interfaces**:
  - `team_init.reroot(glob: str, child: str) -> str | None`, segments split on `/`, `fnmatch.fnmatchcase` per segment:
    - walk the glob's segments against the child's; a `**` segment reached while every earlier segment matched returns `/**`;
    - when every child segment matched: the remaining glob segments joined with `/` and prefixed with `/`, or `/**` when none remain;
    - a mismatch, or a glob with fewer segments than the child and no `**`, returns None.
    - Cases: (`services/order-api/src/**`, `services/order-api`) → `/src/**`; (`services/*/src/**`, `services/order-api`) → `/src/**`; (`services/**`, `services/order-api`) → `/**`; (`**`, `apps/web`) → `/**`; (`services/order-api`, `services/order-api`) → `/**`; (`web/**`, `services/order-api`) → None; (`services`, `services/order-api`) → None; (`tests/services/**`, `services/order-api`) → None.
  - `team_init.codeowners(team, config, child: str | None = None) -> str | None`: `child=None` returns today's text unchanged; with `child`, only area lines, `<rerooted> <owners>` for each glob whose `reroot` is not None, no plan or spec folder lines, and None when no line was produced.
  - `team_init.planned_files(root, team, config, *, ci, child: str | None = None)`: with `child`, CODEOWNERS is included only when `codeowners(..., child)` is not None.
  - `team_init.init(root, team, config, *, ci=False, force=False, child: str | None = None)`: unchanged result keys; `child` passes through.
  - `gin team init --all-repos [--ci] [--force] [--format json]`:
    - `workspace.locate(root).workspace` None raises `TeamError("not in a workspace")` (exit 2);
    - the parent first (`init(root, ...)`), then each entry in `space.repos` order: `workspace.skip_reason` not None gives a row `{"path", "skipped_repo": <reason>}`; otherwise `init(space.checkout(repo), ..., child=repo.path)`; an `OSError` gives `{"path", "error": str(error)}` and the loop continues;
    - a child without CODEOWNERS adds `"note": "no area covers <path>"`;
    - JSON `{"repos": [{"path": ".", ...}, ...], "warnings": [...]}`; text: one block per repository with the lines of today's output prefixed by `<path>: `, then `commit and open a pull request in: <paths with written files>` when any child has written files;
    - exit 0, or 1 when any row has `error`.
  - `gin team hooks --all-repos`: `install_hook` in the parent and in each workable cloned child (`skip_reason` None); a child `missing` adds `run gin team init --all-repos`; exit code is the worst of today's per-repository mapping (`active`/`installed` 0, `occupied` 1, `missing` 2).
- **Steps**:
  1. Failing tests in `tests/workflow_core/test_team_init.py`:
     - `reroot` on every case listed above;
     - a parent from `make_team_repo` plus a `workspace:` block with `services/order-api` (cloned: `init_repo` at that path), `web/shop` (cloned), `docs/wiki` (cloned, no area covers it), `legacy/portal` (frozen, cloned), `.beads` (shape beads), and `services/billing` (not cloned):
       - `team init --all-repos` exits 0; `services/order-api/.github/CODEOWNERS` has `/** @binh-dev` and no `/.planning/` line; `web/shop/.github/CODEOWNERS` has `/** @chi-fe`; `docs/wiki` has the template and the hook but no CODEOWNERS, and its row has `no area covers docs/wiki`; `legacy/portal`, `.beads`, and `services/billing` rows say `frozen`, `beads`, and `not cloned`; the parent's files are as `team init` writes them today;
       - a child CODEOWNERS without the marker is kept and listed under `skipped`; with `--force` it is rewritten;
       - the text output ends with `commit and open a pull request in: services/order-api, web/shop, docs/wiki`;
     - `team init --all-repos` outside a workspace exits 2 with `not in a workspace`;
     - `team hooks --all-repos` after `team init --all-repos` reports `installed` for each workable cloned child; a child without `.githooks/commit-msg` reports `missing` with `run gin team init --all-repos` and exit 2;
     - `team init` without `--all-repos` gives today's output (the existing tests stay green).
  2. Run `python3 -m pytest tests/workflow_core/test_team_init.py -q` → fail.
  3. Implement per the interfaces.
  4. Run step 2 → pass; `python3 -m pytest tests/workflow_core -q -n auto -k "team or workspace or hooks"` → pass; `gin docs check docs/reference/cli.md` → ok.
  5. Commit: `feat(team): gin team init and hooks write into each workspace child with --all-repos (gin-workflow-ws-child-setup)`.
- **Acceptance criteria**: R3, R4, R5; US-3.
- **Estimated complexity**: medium

### Track 4: Skills and docs for workspace roles
- **Dependencies**: Track 3
- **Files**:
  - Modify `plugins/gin-workflow/src/skills/ship/SKILL.md:16` (step 1: `gin hooks status --all-repos` in a workspace)
  - Modify `plugins/gin-workflow/src/skills/setup/SKILL.md:21` (step 6: `gin workspace add` per repository, then `gin workspace clone --all`; team mode: `gin team init --all-repos`)
  - Modify `plugins/gin-workflow/src/skills/tech-doc/SKILL.md:26-27` (frozen legacy hint)
  - Modify `plugins/gin-workflow/src/skills/explain/SKILL.md:13` (`--legacy` skips an uncloned app and names the command)
  - Modify `plugins/gin-workflow/src/skills/discuss/SKILL.md:20` (one sentence in step 1)
  - Modify `plugins/gin-ba/src/skills/capture/SKILL.md:18` (step 3: frozen legacy hint)
  - Modify `docs/guides/workspace.md`, `docs/guides/workspace.vi.md` (setup once, onboarding per role, PM and BA)
  - Modify `docs/starters/brownfield.md`, `docs/starters/brownfield.vi.md` (workspace entries through setup or `gin workspace add`; team init for the children)
  - Test `tests/workflow_core/test_skill_routing.py`
  - Test `tests/gin_ba/test_ba_packaging.py`
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** skill and guide text with every rule fixed by spec R6 to R9; several files and budget limits, no logic.
- **Interfaces** (facts the text must carry; wording may be tighter):
  - Frozen legacy hint (tech-doc, explain, discuss, capture): in a workspace, run `gin workspace status --json`; for each row with `frozen: true` and `present: false`, print `gin workspace clone <path>` and continue without it; when the command fails, say the frozen entries' state is unknown, give the error, and continue. `explain --legacy` skips that app and names it with the command. Discuss gets one sentence only (chain 10,790 of 12,000).
  - Ship step 1: "Run `gin hooks status` (in a workspace, `gin hooks status --all-repos`)"; the rest of the step is unchanged (chain 11,214 of 12,000).
  - Setup step 6: on `workspace`, ask for each repository its path, url, shape, whether it is frozen, its default branch, and its checks, run `gin workspace add` for each, then `gin workspace clone --all` (which installs the hooks); with team mode, `gin team init --all-repos` after `/gin:team-setup`, then a commit and pull request in each child. Remove "The lead then fills one entry per repository" and the separate `gin hooks install --all-repos`.
  - `workspace.md` and `.vi.md`:
    - Setup once: step 3 becomes `gin workspace add` per repository (or setup asks); step 5 (`gin hooks install --all-repos`) goes, since the clone installs the hooks; step 6 adds `gin team init --all-repos`, then a commit and pull request in each child.
    - Onboarding: the step "Run `gin hooks install` inside each clone" goes; per role: a developer clones the children they work on; QA clones the `shape: qa` entry; a PM clones the parent and, when the workspace has a `shape: beads` entry, `.beads`; a BA clones what the PM clones plus the frozen legacy entries, which tech-doc, capture, and explain read.
    - PM and BA: "Open: the parent checkout"; `/gin:roadmap` creates its `roadmap/<topic>` branch itself; the tech-doc row says it prints `gin workspace clone <path>` when the frozen legacy is not cloned.
  - `brownfield.md` and `.vi.md`: the `workspace.repos` YAML step says setup asks for the entries (or `gin workspace add`); the team setup step adds `gin team init --all-repos` and a pull request per child.
  - Core files never name `gin-ba`; `.vi.md` pages keep English anchors and identifiers.
- **Steps**:
  1. Failing tests:
     - `tests/workflow_core/test_skill_routing.py`: ship has `gin hooks status --all-repos`; setup has `gin workspace add` and `gin team init --all-repos` and no longer has `gin hooks install --all-repos`; tech-doc, explain, and discuss have `gin workspace clone <path>` and `gin workspace status --json`;
     - `tests/gin_ba/test_ba_packaging.py`: capture has `gin workspace clone <path>`.
  2. Run `python3 -m pytest tests/workflow_core/test_skill_routing.py tests/workflow_core/test_token_budget.py tests/workflow_core/test_walkthrough_docs.py tests/workflow_core/test_docs_coverage.py tests/gin_ba/test_ba_packaging.py -q` → fail.
  3. Edit the skills and docs.
  4. Run step 2 → pass; `gin docs check docs/guides/workspace.md docs/guides/workspace.vi.md docs/starters/brownfield.md docs/starters/brownfield.vi.md` → ok; print the discuss and ship chain sizes with `workflow_core.budget.stage_chars`.
  5. Commit: `docs(workspace): role onboarding, frozen legacy hints, and child hooks in ship and setup (gin-workflow-ws-child-setup)`.
- **Acceptance criteria**: R6, R7, R8, R9; US-4, US-5; US-1 (setup side).
- **Estimated complexity**: medium

## Integration
- **Branch**: `feat/ws-child-setup`; track branches `feat/ws-child-setup-t1` to `-t4` stacked in order.
- **Merge strategy**: sequential

## Validation
- [ ] All tests pass (`python3 -m pytest -n auto`, run by the pre-push hook)
- [ ] `gin docs check` on changed pages
- [ ] Budgets hold (`tests/workflow_core/test_token_budget.py`, `tests/gin_ba/test_ba_packaging.py`)

## Notes
- `setup_service.configure` rewrites `.agent-workflow/config.yaml` with `yaml.safe_dump`, as `gin setup configure --set` already does; comments in the file are not kept.
- `workspace.load` returns None for an empty `workspace.repos`, so `gin workspace status` and `clone` keep saying `not in a workspace` until the first `gin workspace add`.
- Deliverable merge-holds apply only to the Parent Bead; track beads close after tests and review pass.
- The user may override `Model:` and `Effort:` before plan approval.
