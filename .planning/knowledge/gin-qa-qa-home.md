# gin-qa QA home: workspace QA child, qa.dir, and the Playwright folder

**Context**
Epic `gin-workflow-qa-workspace` (2026-11-11), the last P1 of the process review (QA-1, QA-2). gin-qa used the current directory as the only root, required `.agent-workflow/config.yaml` there, wrote `package.json`/`playwright.config.ts` at the repository root, and read case-ID history from that root's git log, so it failed in a workspace `qa` child and could not keep Playwright in a subfolder of a monorepo.

**Decision/Solution**
- The core `gin specs reqs` JSON adds `root` (project root) and `qa_root` (`workspace.qa_root(root, cwd)`: the `shape: qa` child, or the checkout of it the command runs from, worktrees included; null without one; an error with several).
- gin-qa still calls `gin` by subprocess only. `reqs.locate(repository)` returns `(files_root, eff)`: the files root is `qa_root` (refused with `gin workspace clone <path>` when not cloned) or the project root; the QA home is `.` in the child or `qa.dir` (default `qa`, a non-empty path inside the repository, in the core schema; ignored with a qa child). `Effective` gained `project_root` (for `gin task`/`gin state` and `Source:` specs) and `package_dir`.
- Every existing gin-qa function keeps taking `root`; passing the files root moved cases, guidelines, evidence, report, and case-ID `git log` to the right repository without touching them.
- Defaults under the QA home: `cases`, `guidelines.md`, `e2e`, and `evidence` next to the e2e folder. Explicit `qa.cases`/`qa.e2e`/`qa.guidelines` are relative to the files root.
- Playwright lives in `<QA home>/e2e` (`package_dir`): `package.json` (created by `e2e init` as `{"name": "<home>-e2e", "private": true}`), lockfile, `playwright.config.ts` (`testDir: '.'`), `node_modules`, and the `npm`/`npx` cwd; spec arguments are relative to it and `--output` is absolute. A repository with a root `playwright.config.*` or a `package.json` `e2e` script, no `qa.dir`, and no `qa_root` keeps the root (`_root_playwright`).
- A `gin` whose payload lacks `root` is refused: "this gin is too old for gin-qa; reinstall gin-workflow".

**Consequences**
- gin-qa needs the gin-workflow version that ships this (docs say 3.1 or later; `plugin.meta.json` was still 3.0.0 at merge, so the release bump is pending).
- The user chose to follow spec R6 strictly, which changed 11 existing e2e tests: root scenarios gained a root config or `e2e` script (`root_setup()` writes `playwright.config.js`), new-setup scenarios expect `qa/e2e`.
- In a linked worktree of the QA child, `e2e init` names the package after the worktree folder (for example `wt-e2e`); cosmetic, the package is private.
- The track 1 developer returned only a placeholder report; the commit and tests were verified directly before review. Always check the tree when a worker report lacks the result contract.

**References**
- `plugins/gin-workflow/src/scripts/workflow_core/{workspace,specs_cli,schemas}.py`; `plugins/gin-qa/src/scripts/gin_qa/{reqs,cli,bugs,e2e}.py`
- Tests: `tests/workflow_core/test_workspace.py` (`QaRootTests`), `tests/workflow_core/test_specs_reqs.py`, `tests/gin_qa/test_workspace_root.py`, `tests/gin_qa/test_e2e_cli.py`
- Docs: `docs/guides/qa.md` (The QA home), `docs/guides/workspace.md`, `docs/reference/config.md`, `docs/reference/cli.md`, and their `.vi.md` pairs
- `.planning/specs/2026-11-11-qa-workspace-design.md`, `.planning/plans/2026-11-11-qa-workspace.md`
- Beads: `gin-workflow-qa-workspace`, `.1` to `.3`
- Related: [workspace](workspace.md), [process-review](process-review.md), [gin-qa-setup-and-types](gin-qa-setup-and-types.md)

**Scope**
Where gin-qa reads configuration and writes QA files in single repositories, monorepos, and workspaces.
