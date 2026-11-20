# Monorepo package checks in the hooks, /quick, and gin-qa install

**Context**
A user asked how to run a monorepo (`qa/` for cases, `newapp/{backend,frontend,e2e}`) with gin-workflow and gin-qa (2026-11-20). `project.packages[].verify.checks` already existed, but three gaps showed up: `gin quick-check` ignored package checks, the hooks ran every package on every commit and push, and `gin-qa e2e init --install` looked for the lockfile only in the Playwright folder, so a pnpm workspace got `npm install`.

**Decision/Solution**
- `gin quick-check` lists each package's allowed checks in `verify_commands` as `<package path>:<name>`, the hooks' naming, outside a workspace child; the rigor and `run_at: host` filters apply; `/quick` runs such an entry in the package directory (`gin-workflow-n0cs`).
- The hooks run root `verify.checks` always and package checks only for the packages a change touches: the staged files for `pre-commit`, `git diff <remote> <local>` of each pushed branch for `pre-push`. A changed file outside every package runs all packages; so does an unknown change set (new branch, remote commit missing locally, `gin evidence run`). A known empty set runs none. `gin hooks status` still lists every check (`gin-workflow-40tl`).
- A hook record (`checks.passed`) stores exactly the commands that ran, so it may cover only the touched packages; the "already passed on this tree" skip compares against the filtered set, so it never skips a package a record did not run.
- `_changed_files` keeps git's environment while the check commands strip `_GIT_ENV`: under `git commit -a` or `git commit <path>`, `GIT_INDEX_FILE` names the temporary index being committed, which `git diff --cached` must read.
- gin-qa picks the package manager from the nearest lockfile (`pnpm-lock.yaml`, `yarn.lock`, `package-lock.json`), from the Playwright folder up to the files root, npm when none; commands still run in the Playwright folder (`gin-workflow-gdch`).

**Consequences**
- Scoping is by path only: if `web` imports `api` and only `api` changes, `web:test` does not run. Root checks are the place for cross-package suites.
- During `commit --amend`, `pre-commit` sees only the newly staged changes against HEAD.
- A newer scoped record for a tree can hide an older full one; that costs a rerun, never a skipped package.
- `qa.e2e` is one path per repository; several apps with their own e2e folders need one Playwright project with several `projects`.
- In a turbo or nx root whose `package.json` has an `e2e` script, set `qa.dir` explicitly, or gin-qa treats the root as the Playwright project (`_root_playwright`).
- Tests for behavior that already works were proven able to fail by a mutation on a copy (strip `_GIT_ENV`, bare `startswith` in `_under`, drop the path normalization); each failed exactly its test.
- The safety hook blocks a shell command whose text holds the hook-skipping commit flag, even in a scratch repository or inside a quoted comment body; make a temp repository's setup commit before `gin hooks install`.

**References**
- `plugins/gin-workflow/src/scripts/workflow_core/hooks.py` (`_scoped`, `_changed_files`, `_pushed_files`, `run`, `verify`), `lifecycle_cli.py` (`_quick_check_command`), `plugins/gin-workflow/src/skills/quick/SKILL.md`
- `plugins/gin-qa/src/scripts/gin_qa/e2e.py` (`MANAGERS`, `_commands`), `reqs.py` (`_root_playwright`)
- Tests: `tests/workflow_core/test_hooks.py`, `tests/workflow_core/test_lifecycle_cli.py`, `tests/gin_qa/test_e2e_cli.py`
- Docs: `docs/reference/cli.md` (`gin quick-check`, `gin hooks`, `gin evidence`, gin-qa `--install`), `docs/reference/config.md` (`verify.checks`), `docs/guides/qa.md`
- Beads: `gin-workflow-n0cs`, `gin-workflow-40tl`, `gin-workflow-gdch`
- Related: [beads-metadata-and-package-detection](beads-metadata-and-package-detection.md), [gin-qa-qa-home](gin-qa-qa-home.md)

**Scope**
Single repositories with `project.packages`; workspace children keep their own `verify.checks` and are not scoped by package.
