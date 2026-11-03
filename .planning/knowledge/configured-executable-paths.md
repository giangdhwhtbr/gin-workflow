# Configured executable paths: executables.local.yaml

**Context**
Epic `gin-workflow-rrui` (2026-11-03, spec `.planning/specs/2026-11-03-windows-ci-and-cli-paths-design.md`). The harness process often has a different `PATH` from the user's shell (GUI launch, git hooks, CI, Windows npm shims), and the code had grown guesses for it: `COMMON_INSTALL_DIRS` in `executable_resolver.py` and a hard-coded `/home/linuxbrew/.linuxbrew/bin/bd` probe in `review_ledger/cleanup.py`, plus eight separate `shutil.which("bd")` calls.

**Decision/Solution**
- `setup init` and `setup refresh` record the absolute path of every external CLI they find (`git`, `bd`, `gh`, `glab`, `npm`, `npx`, `gin-workflow`, `gin-orchestrator`, `codegraph`) in `.agent-workflow/executables.local.yaml` (gitignored, excluded from bundles). `workflow_core/executables.py:tool(name, root)` returns the configured path while it is still an executable file, else `shutil.which(name)`; it never raises, so an old repository without the file behaves as before. `setup doctor` reports `stale`, `unconfigured`, `missing`, `problems` under `checks_details.executables`.
- The motivation is determinism and diagnostics, not speed: `shutil.which` costs nothing measurable, and the file does not save tokens; what it removes is the guessing and the "command not found" loop inside a stage.
- `git` is recorded and doctor-checked but its ~38 call sites keep the bare name (a repository without `git` on `PATH` does not work anyway). Harness CLIs stay in `orchestrator.local.yaml` and `resolve_harness_executable`.
- gin-qa does not read the file. It imports nothing from gin-workflow (its launcher is `from gin_qa.cli import main`, and the installed copy has no `workflow_core` on `sys.path`), so an import of `workflow_core.ext` broke the installed `gin-qa` in the smoke test. gin-qa needs the `gin-workflow` CLI on `PATH`, not its library; `reqs.py` and `e2e.py` keep `shutil.which`.
- A call site must run the path `tool()` returns, not use it as a guard and then run the bare name (`team_init._ok` did that and failed on Windows, where the bare name does not reach a `.cmd`).

**Consequences**
- A test that runs `setup init`/`refresh` and then puts a fake `bd` (or other tool) on `PATH` must either run setup with a narrowed `PATH` (as `test_setup_cli` does for `codegraph`) or delete `.agent-workflow/executables.local.yaml` afterwards: the recorded real path wins over the fake.
- Tests patch `workflow_core.<module>.tool` (or `workflow_core.executables.shutil.which`), not `<module>.shutil.which`: the modules no longer import `shutil`.
- The `gin-orchestrator` launcher keeps `shutil.which("gin-workflow")`: it runs before `workflow_core` is importable.

**References**
- `plugins/gin-workflow/src/scripts/workflow_core/executables.py`, `setup_service.py` (`initialize`, `refresh`, `doctor`), `docs/reference/config.md` (`executables.local.yaml`)
- Beads: `gin-workflow-rrui.1` to `.6`, `gin-workflow-myd7`; follow-up `gin-workflow-gscr`

**Scope**
gin-workflow core and add-ons; any new code that starts an external CLI.
