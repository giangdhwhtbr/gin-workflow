# Plan: gin-qa runs from the qa child, its worktrees, and a QA folder anywhere

Spec: .planning/specs/2026-11-11-qa-workspace-design.md
Epic: gin-workflow-qa-workspace
Workflow: gin-workflow-qa-workspace

## Objective

`gin specs reqs` reports the project root and the QA child; gin-qa reads config, specs, and Beads from the project root and passes every file operation the root of the git repository that holds the QA home, with defaults relative to the QA home and the Playwright project in `<QA home>/e2e`; existing root-level Playwright setups keep working.

**Goal** (spec): gin-qa reads config, specs, and Beads from the project root (the workspace parent, or the repository root), and keeps everything QA owns under one QA home: the `shape: qa` workspace child, or a configurable folder of a single repository. The Playwright project is a subfolder of the QA home. gin-qa then runs from the QA child, from a worktree of it, or from any directory of the project.

**Architecture**: every gin-qa function already takes `root` and uses paths relative to it. The change resolves, once per command, a *files root* (the git repository that holds the QA home: the QA child in a workspace, else the project root) and passes it as `root`; `Effective` gains `project_root` (for `gin task`/`gin state`) and `package_dir` (the Playwright project folder, relative to the files root). Defaults become relative to the QA home. The core adds two keys to `gin specs reqs`.

**Tech Stack**: Python 3 standard library; gin-qa calls `gin` by subprocess (no `workflow_core` import); unittest/pytest with `tests/gin_qa/qa_fixtures.py` and `tests/workflow_core` workspace fixtures.

**Global Constraints** (spec, verbatim):
- R2. gin-qa calls `gin specs reqs` without `--repository` when the user gave none, so the core resolves the project root from the current directory; with an explicit `--repository` it passes it on as today. It no longer requires `.agent-workflow/config.yaml` in the current directory. A `gin` whose payload lacks `root` is refused with "this gin is too old for gin-qa; reinstall gin-workflow".
- R6 (compatibility). When the project root already has `playwright.config.*`, or a `package.json` with an `e2e` script, and `qa.dir` is not set, gin-qa keeps using the project root as today.
- The `specs reqs` JSON only gains keys; gin-console does not read it.
- Out of scope: QA tracks in the lifecycle, acceptance cases in review and ship (`gin-workflow-qa-lifecycle`); moving files of existing projects.

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
- Problem statement: gin-qa treats the current directory as the only root, so it fails in a workspace child and writes Playwright files at the repository root.
- Success criteria: spec R1 to R7; US-1 to US-3 as tests; existing gin-qa tests unchanged.
- Constraints: Global Constraints above.
- Non-goals: see Global Constraints.

## Approach Options
### Option 1: roots from `gin specs reqs`, files root passed as `root`
- Summary: core payload adds `root`/`qa_root`; gin-qa resolves a files root and passes it where it passes `root` today.
- Pros: one resolution point; no new command; most gin-qa functions unchanged.
- Cons: gin-qa needs a matching core version.

### Option 2: gin-qa walks up directories itself
- Summary: re-implement workspace and worktree detection in gin-qa.
- Pros: no core change.
- Cons: duplicates `workspace.locate` and worktree logic; confirmed against in `/discuss`.

### Recommended Approach
- Selected option: Option 1 (confirmed in `/discuss` on 2026-11-11).
- Rationale: smallest change; keeps gin-qa's subprocess-only contract.

## Scope
- In scope: R1 to R7.
- Out of scope: see Global Constraints.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: gin-qa depends on the core payload, and the docs describe the shipped behaviour; one lane.
```

## Tasks

`S` is `plugins/gin-workflow/src/scripts/workflow_core`; `Q` is `plugins/gin-qa/src/scripts/gin_qa`.

### Track 1: `gin specs reqs` reports the project root and the QA child
- **Dependencies**: none
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs_cli.py:91-95` (the `reqs` branch adds the keys)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/workspace.py` (new `qa_root(root, cwd)` helper)
  - Modify `docs/reference/cli.md` (`specs reqs` row: the two keys)
  - Test `tests/workflow_core/test_workspace.py` or the existing `specs reqs` test file (search `"reqs"` under `tests/workflow_core`)
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** a bounded helper over existing workspace and checkout functions, with clear cases.
- **Interfaces**:
  - `workspace.qa_root(root: Path, cwd: Path) -> Path | None`: `None` without a workspace or without a `shape: qa` entry; raises `WorkspaceError("more than one shape: qa entry: <paths>")` with several; the current directory's git top level when `main_checkout(cwd)` equals that entry's checkout (a linked worktree included), else `root / entry.path`.
  - `gin specs reqs --format json` payload adds `"root": str(root)` and `"qa_root": str(path) | None`.
- **Steps**:
  1. Failing tests: with the `make_workspace` fixture of `tests/workflow_core/test_workspace.py` (add a `{path: qa, url: ..., shape: qa}` entry and `git init` the `qa` checkout), assert `qa_root(root, root)` is `root/qa`; from `root/qa` it is `root/qa`; from a linked worktree of `qa` (`git -C root/qa worktree add <tmp>/wt -b t`) it is the worktree path; with no qa entry it is `None`; with two qa entries it raises `WorkspaceError` naming both. A CLI test runs `gin specs reqs --format json` from `root/qa` (no `--repository`) and asserts `root` and `qa_root`.
  2. Run the new tests → fail.
  3. Implement `qa_root` in `workspace.py` with `main_checkout` (from `.checkout`) and `git rev-parse --show-toplevel` for the worktree path; in the `reqs` branch of `specs_cli._run`, add `root` and `qa_root(args.repository, Path.cwd())` to the payload; turn a `WorkspaceError` into the command's existing error path (exit 2 with the message).
  4. Run → pass; `python3 -m pytest tests/workflow_core -q -n auto -k "workspace or specs"` → pass.
  5. `docs/reference/cli.md`: in the `specs` table row for `reqs`, add "the JSON also carries `root` (the project root) and `qa_root` (the `shape: qa` workspace child, or the worktree of it you run from; null without one)". `gin docs check docs/reference/cli.md` → ok.
  6. Commit: `feat(specs): reqs reports the project root and the QA child (gin-workflow-qa-workspace)`.
- **Acceptance criteria**: R1; tests above pass; existing tests pass.
- **Estimated complexity**: low

### Track 2: gin-qa resolves the files root, QA home defaults, and the Playwright folder
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-qa/src/scripts/gin_qa/reqs.py:14-16,23-57` (`specs_reqs`, `Effective`, `resolve`, new `locate`)
  - Modify `plugins/gin-qa/src/scripts/gin_qa/cli.py:20,59,76,316` (`--repository` default `None`), `:211-213,262-264,292-294,321-323` (each `_run*` uses `locate`)
  - Modify `plugins/gin-qa/src/scripts/gin_qa/bugs.py:21-26,51` (`gin task`/`gin state` use `eff.project_root`)
  - Modify `plugins/gin-qa/src/scripts/gin_qa/e2e.py:184-300` (package folder)
  - Test `tests/gin_qa/test_workspace_root.py` (new), `tests/gin_qa/qa_fixtures.py` (workspace fixture)
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `high`
- **Why:** cross-module inside gin-qa (cases, bugs, e2e, report, tests all receive the new root), with a compatibility rule for existing root-level Playwright setups and subprocess calls to a matching core.
- **Interfaces**:
  - `reqs.specs_reqs(repository: Path | None, change: str | None = None) -> dict`: runs `gin specs reqs [--repository R] --format json` with `cwd=Path.cwd()`; refuses a payload without `root` with "this gin is too old for gin-qa; reinstall gin-workflow"; no `.agent-workflow/config.yaml` check of its own.
  - `reqs.locate(repository: Path | None, change: str | None = None) -> tuple[Path, Effective]` returning `(files_root, eff)`.
  - `Effective` adds `project_root: Path` and `package_dir: str` ("" for the files root, else a files-root-relative path).
  - `resolve(payload, files_root: Path, qa_home: str)`: defaults `cases = <qa_home>/cases`, `guidelines = <qa_home>/guidelines.md`, `e2e = <qa_home>/e2e` (with `qa_home == "."` they are `cases`, `guidelines.md`, `e2e`); explicit `qa.*` keys are used as given (relative to the files root).
- **Steps**:
  1. Fixtures in `tests/gin_qa/qa_fixtures.py`: `make_workspace_qa(base) -> (parent, child)` builds a parent with `.agent-workflow/config.yaml` (via the same setup the existing `make_repo` uses) plus a `workspace.repos` manifest entry `{path: qa, url: "git@example.com:org/qa.git", shape: qa}`, and a `qa` git repository with one commit at `parent/qa`.
  2. Failing tests in `tests/gin_qa/test_workspace_root.py` (above any `__main__` guard; unique class name `TestQaWorkspaceRoot`), using the existing `qa(...)` runner with `cwd` support (add a `cwd` parameter if missing, default unchanged) and `gin_workflow_bin`:
     - `test_next_id_from_the_child_uses_child_history`: commit a case file with `TC-CAT-001` in the child; from `parent/qa`, `gin-qa cases next-id catalog` prints `TC-CAT-002` and creates nothing in the parent.
     - `test_next_id_from_a_child_worktree`: from a linked worktree of the child, the same works and reads the worktree's files.
     - `test_e2e_init_writes_into_the_child_e2e_folder`: from `parent/qa`, `gin-qa e2e init --base-url http://localhost:3000` writes `qa/e2e/playwright.config.ts` and the evidence line `/evidence/` in `qa/.gitignore`; `parent/playwright.config.ts`, `parent/package.json`, and `parent/.gitignore` are unchanged.
     - `test_single_repo_qa_dir`: a single repository with `qa: {dir: new-app/testing}`; `cases new` writes under `new-app/testing/cases/` and `e2e init` writes `new-app/testing/e2e/playwright.config.ts`.
     - `test_qa_dir_outside_is_refused`: `qa: {dir: ../x}` exits 2 with "must be a path inside the repository".
     - `test_root_playwright_kept`: a single repository with `playwright.config.ts` at the root and no `qa.dir`; `e2e init` writes nothing new at `qa/e2e/playwright.config.ts` and `e2e run` (with the Playwright stub the existing e2e tests use) runs from the root.
     - `test_old_gin_is_refused`: a `gin` stub whose `specs reqs` payload lacks `root` → exit 2 with "this gin is too old for gin-qa".
     Run `python3 -m pytest tests/gin_qa/test_workspace_root.py -q` → fails.
  3. `reqs.py`: change `specs_reqs` per the interface (keep its other refusals); add
     ```python
     def locate(repository: Path | None, change: str | None = None) -> tuple[Path, "Effective"]:
         payload = specs_reqs(repository, change)
         project = Path(payload["root"])
         qa = payload.get("qa") or {}
         if payload.get("qa_root"):
             files_root, home = Path(payload["qa_root"]), "."
         else:
             files_root, home = project, _inside("dir", qa.get("dir", "qa"))
         eff = resolve(payload, files_root, home)
         eff.project_root = project
         return files_root, eff
     ```
     `resolve` computes defaults from `home` (`posixpath.join(home, "cases")` normalised so `.` gives `cases`), keeps explicit keys, and sets `package_dir`: `""` when `qa.dir` is absent, there is no `qa_root`, and the files root has `playwright.config.*` or a `package.json` whose `scripts` has `e2e`; otherwise `e2e_dir`. Keep `DEFAULT_*` constants for callers that import them.
  4. `cli.py`: `--repository` defaults to `None` in all four parsers; each `_run*` replaces `root = args.repository.resolve()` / `eff = resolve(specs_reqs(root))` with `root, eff = locate(args.repository)` (`_scope` keeps calling `specs_reqs(eff.project_root, change)` for the change rows).
  5. `bugs.py`: `_gin_workflow` and `_workflow_epic` use `eff.project_root` (pass `eff` or the path through `file_bug`); case paths stay relative to `root`.
  6. `e2e.py`: introduce `pkg = root / eff.package_dir` and use it in `_has_e2e_script`, `_commands`, `_read_package` (message "no package.json in <package_dir or the repository root>"), `_install` (cwd), the `CONFIG_NAMES` check and the `CONFIG` write in `init`, `_playwright` (search `pkg` and its parents), and the `npx playwright test` call (cwd `pkg`, spec paths made relative to `pkg`, evidence and output paths absolute). When `package_dir == eff.e2e_dir`, the config template's `__E2E_DIR__` becomes `.`. `ignore_evidence` stays on `root`.
  7. Run step 2 → pass. Run `python3 -m pytest tests/gin_qa -q -n auto` → every existing gin-qa test passes unchanged.
  8. Commit: `feat(gin-qa): files root and QA home from gin, Playwright in the QA e2e folder (gin-workflow-qa-workspace)`.
- **Acceptance criteria**: R2 to R6; US-1 to US-3 as the tests above; existing gin-qa tests unchanged.
- **Estimated complexity**: high

### Track 3: Docs and skills for the QA home
- **Dependencies**: Track 2
- **Files**:
  - Modify `docs/guides/qa.md`, `docs/guides/workspace.md:104-115`, `docs/starters/brownfield.md` (QA paths, lines ~18, 124, 173, 370, 391, 434)
  - Modify `plugins/gin-qa/src/skills/e2e/SKILL.md:10`, `plugins/gin-qa/src/skills/setup/SKILL.md:11`, `plugins/gin-qa/src/skills/tests/SKILL.md:18`, and any other gin-qa skill that says "repository root" for QA files
  - Modify `docs/reference/config.md` (`qa.dir`)
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `low`
- **Why:** documentation of shipped behaviour with exact paths; skill budgets apply.
- **Steps**:
  1. `qa.md`: a "QA home" section: the QA home is the `shape: qa` workspace child, else `qa.dir` (default `qa`); `cases`, `guidelines.md`, `evidence`, and the Playwright project `e2e/` live under it; run gin-qa from the QA child, a worktree of it, or anywhere in the project; existing root-level Playwright setups keep working. Update path examples so they read as QA-home relative.
  2. `workspace.md` QA section: the `qa` child holds cases, evidence, and the Playwright project at its root (`cases/`, `e2e/`, `evidence/`); specs and config stay in the parent; gin-qa finds the child by `shape: qa`, so its path and name are free.
  3. `brownfield.md`: make the QA paths consistent with the child layout (`qa/cases/...` from the parent means `cases/...` in the child).
  4. `config.md`: document `qa.dir` (single repository only; ignored with a `shape: qa` child) and that explicit `qa.cases`/`qa.e2e`/`qa.guidelines` are relative to the repository that holds the QA home.
  5. Skills: `e2e/SKILL.md` precondition becomes "`gin specs reqs` works from here (gin-workflow set up in the project root)" instead of `effective-config.yaml` at the repository root, and the Playwright config lives in the QA `e2e` folder (or the root for existing setups); `setup/SKILL.md` names the project skill after the project root folder and writes it there; `tests/SKILL.md` globs are relative to the repository that holds the QA home. Check `wc -m` of each skill against its budget and run the token budget test.
  6. `gin docs check` on the changed docs → ok; `python3 -m pytest tests/workflow_core/test_token_budget.py tests/gin_qa -q -n auto` → pass; `python3 -m pytest -n auto -q` → pass.
  7. Commit: `docs(gin-qa): QA home, qa.dir, and the workspace QA child (gin-workflow-qa-workspace)`.
- **Acceptance criteria**: R7; budgets hold; docs check clean.
- **Estimated complexity**: low

## Integration
- **Branch**: `feat/qa-workspace`
- **Merge strategy**: sequential

## Validation
- [ ] `python3 -m pytest -n auto -q` passes (pre-push runs it).
- [ ] `gin docs check` on the changed docs reports no findings.
- [ ] Manual: after `install.sh`, from a scratch workspace's `qa` child, `gin-qa cases next-id <cap>` works.

## Notes
- Omit `Effort:` when the catalog lists no efforts.
- The user may override `Model:` and `Effort:` before plan approval.
- Provider roles describe responsibility rather than filename patterns.
- Deliverable merge-holds (e.g. "remain open until human-confirmed merge") apply exclusively to the Parent Bead. Individual track beads must close upon passing tests and code review to unblock downstream dependent tracks.
- Test hygiene from earlier reviews: new classes above any `__main__` guard, never between a decorator and its class, no duplicate class names; check `--collect-only` counts.
- gin-qa and gin-workflow ship together from this repository; `install.sh` installs both, so the core payload change and the gin-qa change land in one release.
