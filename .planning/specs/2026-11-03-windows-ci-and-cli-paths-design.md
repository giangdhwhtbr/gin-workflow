# Windows CI coverage and configured CLI paths

Workflow: windows-ci-and-cli-paths
Status: draft for user review.
Origin: bead `gin-workflow-myd7` (Windows CI follow-ups from the review of `gin-workflow-rm-windows-parity.5`) plus the request that every external CLI gin-workflow runs is configured at setup instead of looked up at each call.

## Goal and scope

Two outcomes, one epic because the user asked for them together and the second lets the first stop depending on how Windows resolves `.cmd` shims:

1. The machine-local paths of the external CLIs gin-workflow runs (`git`, `bd`, `gh`, `glab`, `npm`, `npx`, `gin-workflow`, `gin-orchestrator`, `codegraph`) are written once by `setup` into `.agent-workflow/executables.local.yaml`, read through one function, and checked by `setup doctor`. Motivation: the PATH of the harness process differs from the user's shell (GUI-launched Claude Code, git hooks, CI, Windows npm shims), which the code today papers over with guessed directories (`workflow_core/executable_resolver.py:14-25` `COMMON_INSTALL_DIRS`; `review_ledger/cleanup.py:34-46` probes `/home/linuxbrew/.linuxbrew/bin/bd`, `/usr/local/bin/bd`, `~/.cargo/bin/bd`) and with eight separate `shutil.which("bd")` lookups. This is about determinism and diagnostics, not speed: `shutil.which` costs nothing measurable.
2. The Windows CI job runs the platform-neutral part of tests that are skipped whole today, and the fake CLIs the tests put on PATH work on Windows. Measured on run 41408282963: Linux `skipped=51`, Windows `skipped=250`; about 146 of the Windows skips come from the three `#!`-script fixtures.

In scope:
- `executables.local.yaml`: schema, writer (`setup init`/`setup refresh`), reader, gitignore and bundle exclusion, docs.
- One resolver `tool(name)` replacing the per-call `shutil.which` for `bd`, `gh`, `glab`, `gin-workflow`, `gin-orchestrator`, `npm`, `npx`, `codegraph` (about 19 call sites, listed in R3).
- `setup doctor` reports on every configured tool, `git` included.
- The four items of `gin-workflow-myd7`: split five tests, move `PYTHONPATH` to the unittest step, `.cmd` wrappers for the fake CLIs, CI timeouts 20/30.

Out of scope:
- Rewriting the ~38 `git` call sites (`["git", ...]` literals and seven local wrappers such as `workflow_core/worktrees.py:16`, `review_ledger/git_adapter.py:53`, `gin_orchestrator/workspace.py:19-25`, plus `merge-integration.sh`). `git` is a system prerequisite for the repository itself: it is recorded in the file and checked by doctor, and the call sites keep the bare name. Decided with the user on 2026-11-03.
- Harness executables (`claude`, `codex`, `agy`, `opencode`): they stay in `orchestrator.local.yaml` and `resolve_harness_executable` (`workflow_core/executable_resolver.py:30`), unchanged.
- A `setup executables --set` command or an environment-variable override. The file is small YAML; the user edits it.
- A schema migration: the file is new and optional, so `setup update` has nothing to move.
- Tests that remain Windows-skipped for other reasons (`pty`, `fork`, `SIGINT`, `install.sh`, inline `#!` stubs in `tests/gin_orchestrator/test_worker_adapters.py`, `test_registry.py`, `test_setup_cli.py`, …). The acceptance `grep` in US-4 keeps their skip reasons honest.
- Any product fix a newly enabled Windows test reveals: it becomes its own bead; the test stays skipped with the bead id in the reason until then.

## Requirements

### R1. `.agent-workflow/executables.local.yaml`

```yaml
schema_version: "2.9"
executables:
  git: /usr/bin/git
  bd: /home/linuxbrew/.linuxbrew/bin/bd
  gh: /usr/bin/gh
  gin-workflow: /home/gin/.local/bin/gin-workflow
```

- Keys under `executables` are limited to `git`, `bd`, `gh`, `glab`, `npm`, `npx`, `gin-workflow`, `gin-orchestrator`, `codegraph` (the constant `KNOWN_TOOLS` in the new module `workflow_core/executables.py`). Values are absolute paths. Any other key, a relative path, or a non-string value is a configuration error reported by `setup doctor` and ignored by the resolver (it falls back as in R2).
- Only tools found at write time are listed; a missing tool is absent, not `null`.
- The file lives in the main checkout (`main_checkout(root)`), like `orchestrator.local.yaml` (`gin_orchestrator/local_config.py:16`).
- `executables.local.yaml` is added to `LOCAL_GITIGNORE_ENTRIES` (`workflow_core/setup_service.py:93-98`), to the bundle exclusion in `workflow_core/bundles.py:63`, and to `_gitignore_with_local` in `gin_orchestrator/cli.py:149`.

### R2. Resolver `workflow_core/executables.py`

```python
KNOWN_TOOLS = ("git", "bd", "gh", "glab", "npm", "npx", "gin-workflow", "gin-orchestrator", "codegraph")

def tool(name: str, root: Path | None = None) -> str | None:
    """Absolute path of an external CLI: the configured path when it is still an executable file,
    else shutil.which(name); None when neither exists."""

def detect(names: Iterable[str] = KNOWN_TOOLS) -> dict[str, str]:
    """{name: absolute path} for every name shutil.which finds."""

def write_local(root: Path, found: Mapping[str, str]) -> Path: ...
def read_local(root: Path) -> tuple[dict[str, str], list[str]]:  # (entries, problems)
```

- `root` defaults to the current working directory's main checkout; a caller with a repository root passes it. When no file exists or the entry is missing or stale (not an executable file any more), `tool` returns `shutil.which(name)`; it never raises for a missing tool, so each call site keeps its own error message and exit code (for example `tasks.py:205-207` returns 127 with the Beads install hint).
- The file is read once per process and cached by `root` (`functools.lru_cache`), with a `clear_cache()` for tests, mirroring `orchestrator_client.status.cache_clear()`.
- `tool` is re-exported from `workflow_core/ext.py` next to `resolve_harness_executable` (`ext.py:24`) so gin-orchestrator and gin-qa import it through the facade; `EXT_VERSION` is not raised (a name is added, none removed).

### R3. Call sites that go through `tool()`

Each `shutil.which("<name>")` below becomes `tool("<name>")` (with the repository root where one is in hand); the surrounding error handling stays as it is:
- `bd`: `workflow_core/tasks.py:144` and `:204`, `workflow_core/specs.py:430`, `workflow_core/team_beads.py:27` and `:87`, `workflow_core/usage.py:131`, `workflow_core/milestone_cli.py:80`, `workflow_core/team_init.py:161`, `workflow_core/setup_service.py:161` (`beads_installed`), and `review_ledger/cleanup.py:34-46`, whose `_find_bd_executable` and its hard-coded paths are deleted.
- `gh`/`glab`: `workflow_core/team_host.py:36` (`_run`), `workflow_core/specs_trace.py:61`.
- `gin-workflow`: `gin_orchestrator/cli.py:187`, the `gin-orchestrator` launcher `main()`, `gin_qa/reqs.py:35`. `gin_orchestrator/task_tracking_cli.py:124` keeps its `executable="gin-workflow"` default but resolves it with `tool` when the caller passes none.
- `gin-orchestrator`: `workflow_core/orchestrator_client.py:26` and `:48`.
- `npm`: `gin_orchestrator/workspace.py:171`.
- Amended 2026-11-03 after CI: gin-qa (`gin_qa/reqs.py`, `gin_qa/e2e.py`) stays on `shutil.which`. Its launcher imports nothing from gin-workflow and the installed copy has no `workflow_core` on `sys.path`, so an import of `workflow_core.ext` broke the installed `gin-qa`. gin-qa needs the `gin-workflow` CLI on `PATH`, not its library.
- `codegraph`: `workflow_core/project_detect.py:167`. `detect_project` keeps its injectable `which` parameter (`project_detect.py:170`); its default becomes `tool`.

`git` call sites are unchanged (out of scope).

### R4. `setup init` and `setup refresh` write the file

- `initialize` (`setup_service.py:166`) and `refresh` (`setup_service.py:359`) call `executables.detect()` and `write_local`, and add `write .agent-workflow/executables.local.yaml` to `actions`. `--dry-run` lists the action and writes nothing. `refresh` rewrites the whole file from a fresh detection; a path the user edited by hand that still resolves is kept (detection prefers an existing valid entry over `which`), so `refresh` only fills gaps and drops dead entries.
- The result of `detect` (`setup_service.py:147`) replaces `beads_installed: shutil.which("bd") is not None` with `tool("bd") is not None`.

### R5. `setup doctor`

`doctor` (`setup_service.py:406`) gains `checks["executables"]` and `checks_details["executables"]`:

```json
{"configured": {"git": "/usr/bin/git", "bd": "/home/linuxbrew/.linuxbrew/bin/bd"},
 "stale": ["gh"], "unconfigured": ["glab", "npx"], "missing": ["glab"], "problems": []}
```

- `stale`: configured path that is no longer an executable file. `unconfigured`: known tool absent from the file. `missing`: tool that neither the file nor PATH provides. `problems`: the validation errors from R1.
- `checks["executables"]` is false only for `stale` entries or `problems`; both are fixed by `gin-workflow setup refresh`, which `actions` names. An `unconfigured` or `missing` optional tool (`glab`, `npx`, `codegraph`, `gin-orchestrator`) is informational. `git` missing is an action (`git: not found; install git`). `bd` missing is an action only when `providers.task_tracking` is `beads`.
- The harness check (`setup_service.py:444-453`) is unchanged.

### R6. Docs

- `docs/reference/config.md`: the `## Files` table gets the new file; a new section `## executables.local.yaml` after `orchestrator.local.yaml` (line 176) with the R1 example, the key list, "written by `setup init`/`setup refresh`, machine-local, gitignored", and the fallback rule from R2.
- `docs/reference/cli.md`: `setup doctor` lists the `executables` check; `setup refresh` mentions the rewrite.
- `docs/reference/troubleshooting.md`: one entry "a CLI works in my shell but gin-workflow says it is not installed" → `setup refresh`, or edit the file.

### R7. Windows CI: split five tests

Each test keeps the neutral assertions unconditional and moves the single POSIX assertion behind `if os.name != "nt":` with the existing reason as a comment, or into a sibling test carrying the existing `skipIf` (the implementer picks per test; a sibling test is preferred when the POSIX part needs its own setup):
- `tests/workflow_core/test_task_markdown.py:186-193`: the five rejected ids run everywhere; `repo:a.b-1` acceptance is POSIX-only (Windows already has `test_colon_id_is_rejected_on_windows`).
- `tests/workflow_core/test_hooks.py:94-103`: idempotence runs everywhere; `0o755` is POSIX-only.
- `tests/workflow_core/test_team_init.py:29-41`: rerun, CODEOWNERS lines, and `--check` run everywhere; `0o755` is POSIX-only.
- `tests/workflow_core/test_artifacts.py:16-31`: `/shared/knowledge` is replaced by an absolute path built for the platform (`Path(directory).anchor + "shared/knowledge"` style) so the test runs everywhere; no POSIX remainder.
- `tests/workflow_core/test_usage_logs.py:156-166`: every assertion runs everywhere; the `cwd` assertion compares `Path(first.cwd).parts[-3:]` with `(".planning", "worktrees", "ep1")`.

### R8. Windows CI: `test.yml`

`.github/workflows/test.yml`: delete the workflow-level `env: PYTHONPATH` (lines 7-8); add `env: PYTHONPATH: plugins/gin-workflow/src/scripts` to the `python3 -m unittest` step of the `linux` job and to the existing `env:` of the `Unit tests` step of the `windows` job. The install smoke steps then import only the installed copy. `timeout-minutes`: `linux` 40 → 20, `windows` 60 → 30 (measured 2m40s and 9m48s).

### R9. Windows CI: `.cmd` wrappers for the fake CLIs

- `tests/workflow_core/team_fixtures.py:fake_cli` (line 109): on `nt`, write the Python body to `<name>.py` and a wrapper `<name>.cmd` containing `@"<sys.executable>" "%~dp0<name>.py" %*`; the `SkipTest` at lines 111-112 is removed. The fake's `sys.argv[0]` is then `<name>.py`, so the rule-file lookup `Path(sys.argv[0]).name + ".json"` (FAKE line 7) uses `Path(sys.argv[0]).stem` instead, on every platform.
- `tests/workflow_core/orchestrator_fakes.py:fake_orchestrator` (line 16): same wrapper for `gin-orchestrator`; the `SkipTest` at lines 25-26 is removed.
- `tests/gin_qa/qa_fixtures.py:gin_workflow_bin` (line 22): on `nt`, `gin-workflow.cmd` containing `@"<sys.executable>" "<LAUNCHER>" %*` (or, when `body` is given, `body` written as the `.cmd`, since the one caller that passes `body` writes a `#!/bin/sh` script; that caller is adapted to pass a platform-appropriate body). The `SkipTest` at lines 24-25 is removed. `qa()`'s default `path="/usr/bin:/bin"` becomes `os.defpath` so `.cmd` resolution works on Windows.
- Tests keep putting the fake on `PATH` (`path_with`, `on_path`, `qa()`); no fixture writes `executables.local.yaml`. This works because R2 falls back to `shutil.which`, which honours `PATHEXT`, and test repositories are fresh temp dirs without the file. Tests that pass `env={"PATH": ...}` to a child must keep `PATHEXT` and `SystemRoot` from `os.environ` (they do today via `{**os.environ, ...}`).

## User Stories

### US-1: Tools resolve from setup, not from guesses
As a gin-workflow user on a machine where the harness PATH lacks my tool directories, I want `setup init` to record where `bd`, `gh`, and the others live, so that every later command finds them without hard-coded directories.

Acceptance criteria:
- After `gin-workflow setup init` in a repository with `bd` and `gh` on PATH, `.agent-workflow/executables.local.yaml` lists `git`, `bd`, `gh` with absolute paths and omits tools not found.
- `git status` in that repository does not show the file (gitignored).
- With `bd` removed from `PATH` but listed in the file, `gin-workflow task ready` still runs `bd`.
- With a stale path in the file and `bd` on PATH, `gin-workflow task ready` runs the PATH `bd`.

### US-2: One resolver, no duplicated probing
As a maintainer, I want every non-git CLI lookup to go through `workflow_core.executables.tool`, so that there is one place to change and no per-module path guessing.

Acceptance criteria:
- `grep -rn 'shutil.which(' plugins/*/src/scripts --include='*.py'` prints no match for `"bd"`, `"gh"`, `"glab"`, `"gin-workflow"`, `"gin-orchestrator"`, `"npm"`, `"npx"`, `"codegraph"` outside `workflow_core/executables.py`.
- `review_ledger/cleanup.py` no longer contains `/home/linuxbrew` or `_find_bd_executable`.
- `python3 -c "from workflow_core.ext import tool"` succeeds.

### US-3: Doctor explains tool problems
As a user whose `gh` was reinstalled elsewhere, I want `gin-workflow setup doctor` to tell me which configured tool path is stale and how to fix it, so that I do not debug a `command not found` inside a stage.

Acceptance criteria:
- `setup doctor --format json` reports `checks.executables: false`, `checks_details.executables.stale == ["gh"]`, and an action naming `gin-workflow setup refresh`.
- After `setup refresh`, the file holds the new `gh` path and `checks.executables` is true.
- A missing optional tool (`glab`) appears under `missing` without failing the check.

### US-4: Windows CI runs the neutral assertions and the fake CLIs
As a maintainer reading the Windows job, I want the skipped count to reflect only genuinely POSIX behaviour, so that a Windows regression in task ids, hooks, team init, artifacts, usage logs, or any test using a fake CLI is caught by CI.

Acceptance criteria:
- Both CI jobs are green on the epic branch, and the Windows job's `skipped=` is at least 140 lower than 250 on the same test count.
- `grep -rn 'skipIf(os.name == "nt"' tests | grep -v '"nt", "'` prints nothing (every skip keeps a reason).
- `grep -n 'PYTHONPATH' .github/workflows/test.yml` shows it only inside the two unittest steps; `timeout-minutes` reads 20 and 30.
- On Linux, `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.test_all` passes with the same count of skips as before this epic.

## Errors and compatibility

- Missing file: every call behaves exactly as today (PATH lookup). Repositories set up before this epic need no action; `setup refresh` creates the file when run.
- Invalid file (unknown key, relative path, bad YAML): the resolver ignores the whole file and falls back to PATH; `setup doctor` lists the problem. No stage fails because of the file.
- Stale path: silent fallback to PATH at call time, reported by doctor. A tool removed from the machine entirely gives the call site's existing error.
- `orchestrator.local.yaml`, the `models` catalog, and `resolve_harness_executable` are untouched; gin-orchestrator's `validate_local_config` still rejects any key besides `executable` there.
- `EXT_VERSION` is unchanged because the facade only gains a name.
- Windows-only behaviour (R7-R9, and `tool` with `PATHEXT`) is verified by the Windows CI job; this epic cannot be fully verified on the Linux development machine.

## Testing

- `tests/workflow_core/test_executables.py` (new): `tool` prefers a valid configured path; falls back on stale path, missing file, invalid file; `detect` lists only found tools; `write_local`/`read_local` round-trip and report each problem class; cache cleared between cases. Uses temp dirs and fake executables created with `fake_cli` (POSIX) or a `.cmd` (nt).
- `tests/workflow_core/test_setup_cli.py`: `setup init` writes the file and gitignore entry; `setup refresh` fills gaps and drops stale entries; `setup doctor` JSON for the `stale`, `unconfigured`, `missing`, and `problems` cases.
- Existing tests for the touched call sites (`test_tasks.py`, `test_team_host*.py`, `test_specs_trace*.py`, `tests/gin_orchestrator/test_cli*.py`, `tests/gin_qa/*`) keep passing with the fakes on PATH; one test per module patches `tool` to a configured path to prove the configured branch is used.
- `tests/test_docs_coverage.py` style check: `docs/reference/config.md` mentions `executables.local.yaml`.
- R7-R9: the Linux suite stays green locally; the Windows job on the branch is the evidence, and the implementer records the before/after `skipped=` counts from the CI log in the bead notes.
