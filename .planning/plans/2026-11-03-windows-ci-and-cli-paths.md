# Plan: Windows CI coverage and configured CLI paths

Spec: `.planning/specs/2026-11-03-windows-ci-and-cli-paths-design.md` (Workflow: `windows-ci-and-cli-paths`). Bead `gin-workflow-myd7` is folded in as Tracks 5 and 6.

## Objective
External CLIs (`git`, `bd`, `gh`, `glab`, `npm`, `npx`, `gin-workflow`, `gin-orchestrator`, `codegraph`) are recorded once by `setup` in `.agent-workflow/executables.local.yaml`, resolved through one function with PATH fallback, and checked by `setup doctor`; the Windows CI job runs the platform-neutral part of five tests and the fake-CLI tests, and `test.yml` scopes `PYTHONPATH` to the unittest steps with tighter timeouts.

## Architecture
- New module `workflow_core/executables.py`: constants, `tool()`, `detect()`, `read_local()`, `write_local()`, `clear_cache()`. Pure functions over one YAML file in the main checkout; `lru_cache` keyed by root.
- `setup_service.initialize`/`refresh` write the file; `doctor` reports on it.
- Call sites keep their error handling and swap `shutil.which("<name>")` for `tool("<name>", root)`.
- gin-orchestrator and gin-qa reach `tool` through `workflow_core.ext` (the only import path they are allowed).
- Tests put fakes on `PATH`; the resolver's fallback finds them. On Windows the fakes get a `.cmd` wrapper that `shutil.which` finds through `PATHEXT`.

## Tech Stack
Python 3.12 stdlib (`shutil`, `functools`, `pathlib`, `subprocess`, `unittest`), PyYAML (already a dependency via `workflow_core.configuration.require_yaml`), GitHub Actions.

## Global Constraints (from the spec)
- `git` call sites (~38) keep the bare name; `git` is only recorded and doctor-checked.
- Harness executables stay in `orchestrator.local.yaml` and `resolve_harness_executable`; `EXT_VERSION` stays 2.
- No `setup executables --set`, no environment override, no schema migration.
- A missing, stale, or invalid `executables.local.yaml` never fails a command: `tool` falls back to `shutil.which`.
- Any product bug a newly enabled Windows test reveals becomes its own bead; the test stays skipped with the bead id in its reason.
- Windows behaviour is verified by the Windows CI job; the Linux suite must stay green with the same skip count as before.

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
- Problem statement: the harness process PATH differs from the user's shell, so the code guesses directories (`executable_resolver.py:14-25`, `review_ledger/cleanup.py:34-46`) and repeats `shutil.which("bd")` eight times; on Windows CI 250 tests skip, ~146 of them only because three fixtures write `#!` scripts.
- Success criteria: US-1 to US-4 in the spec (file written by setup, one resolver, doctor report, Windows `skipped=` at least 140 lower, both jobs green, Linux skip count unchanged).
- Constraints: Global Constraints above.
- Non-goals: rewriting `git` call sites, harness executables, migrations, other Windows skips.

## Approach Options
### Option 1: One resolver module with PATH fallback, written by setup (selected)
- Summary: `executables.py` as in the spec; call sites swap one call; fixtures unchanged except `.cmd` wrappers.
- Pros: smallest diff per call site; old repositories need no action; tests keep using PATH.
- Cons: stale entries silently fall back until `setup refresh`; doctor is the only place that surfaces them.

### Option 2: Strict configured paths (no fallback)
- Summary: `tool` raises when the file lacks a tool.
- Pros: nothing is ever guessed.
- Cons: every existing repository breaks until `setup refresh`; every fixture must write the file; rejected with the user on 2026-11-03.

### Recommended Approach
- Selected option: Option 1.
- Rationale: user decision; same determinism where configured, zero migration cost.

## Scope
- In scope: R1-R9 of the spec.
- Out of scope: everything under the spec's "Out of scope".

## Execution Strategy

```yaml
execution_strategy:
  mode: worker
  workers:
    mode: parallel
  rationale: Tracks 1, 5, 6 share no files; Tracks 2, 3, 4 depend on Track 1 only and share no files with each other.
```

## Tasks

### Track 1: Resolver module, setup writer, doctor, docs
- **Dependencies**: none
- **Files**:
  - Create `plugins/gin-workflow/src/scripts/workflow_core/executables.py`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/setup_service.py:93-98` (gitignore entry), `:147-165` (`detect` uses `tool("bd")`), `:166-277` (`initialize` writes the file), `:359-387` (`refresh` rewrites it), `:406-480` (`doctor` adds the `executables` check)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/bundles.py:63` (exclude the new file)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/ext.py:24,44-80` (export `tool`, `KNOWN_TOOLS`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/project_detect.py:167-170` (`which` default becomes `tool`)
  - Modify `docs/reference/config.md:5-20,176-194` (Files table row, new section), `docs/reference/cli.md:22-30` (`init`, `refresh`, `doctor` rows), `docs/reference/troubleshooting.md` (new entry after line 77)
  - Test `tests/workflow_core/test_executables.py` (new)
  - Test `tests/workflow_core/test_setup_cli.py:101-131,437-481` (init writes file + gitignore; refresh; doctor cases)
  - Test `tests/workflow_core/test_ext.py:5-54` (add `tool`, `KNOWN_TOOLS` to `EXPECTED`)
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** one new module with a clear contract and listed edge cases; the setup/doctor edits follow the existing `harness` check pattern at `setup_service.py:444-453`.
- **Interfaces** (produced):
  ```python
  # workflow_core/executables.py
  KNOWN_TOOLS: tuple[str, ...] = ("git", "bd", "gh", "glab", "npm", "npx", "gin-workflow", "gin-orchestrator", "codegraph")
  LOCAL_FILE = ".agent-workflow/executables.local.yaml"
  def tool(name: str, root: Path | None = None) -> str | None
  def detect(names: Iterable[str] = KNOWN_TOOLS, root: Path | None = None) -> dict[str, str]
  def read_local(root: Path) -> tuple[dict[str, str], list[str]]
  def write_local(root: Path, found: Mapping[str, str]) -> Path
  def clear_cache() -> None
  def doctor_report(root: Path, *, require_bd: bool) -> tuple[bool, dict[str, Any], list[str]]  # (ok, details, actions)
  ```
- **Steps**:
  1. `tests/workflow_core/test_executables.py`: build a temp root with `.agent-workflow/`, a temp `bin` with an executable `fake-bd` made like `test_executable_resolver.py:21-25` (on `nt`: write `fake-bd.cmd` with `@exit 0`). Cases:
     - `test_prefers_a_valid_configured_path`: write `executables.local.yaml` with `bd: <bin>/fake-bd`; `mock.patch("shutil.which", return_value=None)`; `tool("bd", root) == str(path)`.
     - `test_falls_back_to_path_when_entry_is_stale`: file points at a deleted path; `shutil.which` patched to `"/x/bd"`; result `"/x/bd"`.
     - `test_falls_back_when_file_is_missing_or_invalid`: no file → which result; file `executables: {bd: relative/bd}` → which result and `read_local` problems `["bd: path is not absolute"]`; unknown key `foo:` → problem `["foo: unknown tool"]`; non-mapping YAML → problem `["executables: must be a mapping"]`.
     - `test_detect_lists_only_found_tools`: `shutil.which` patched with a dict lookup; `detect(("bd", "gh"))` returns only the found one.
     - `test_write_then_read_round_trip`: `write_local` then `read_local` returns the same mapping and `[]`; file text starts with `schema_version: "2.9"`.
     - `test_cache_is_per_root_and_clearable`: write file, call `tool`, rewrite file, same result until `clear_cache()`.
     Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.workflow_core.test_executables` → `ImportError` (module missing).
  2. Create `executables.py`:
     ```python
     """Machine-local paths of the external CLIs gin-workflow runs, written by setup, with PATH fallback."""
     from __future__ import annotations
     import functools, os, shutil
     from pathlib import Path
     from typing import Any, Iterable, Mapping
     from .atomic import atomic_write_text
     from .checkout import main_checkout
     from .configuration import require_yaml

     KNOWN_TOOLS = ("git", "bd", "gh", "glab", "npm", "npx", "gin-workflow", "gin-orchestrator", "codegraph")
     OPTIONAL_TOOLS = frozenset({"glab", "npx", "codegraph", "gin-orchestrator"})
     LOCAL_FILE = ".agent-workflow/executables.local.yaml"

     def _is_executable(path: str) -> bool:
         return os.path.isfile(path) and os.access(path, os.X_OK)

     @functools.lru_cache(maxsize=None)
     def _load(root: Path) -> tuple[dict[str, str], tuple[str, ...]]:
         path = root / LOCAL_FILE
         if not path.is_file():
             return {}, ()
         yaml = require_yaml()
         try:
             data = yaml.safe_load(path.read_text(encoding="utf-8"))
         except yaml.YAMLError as error:
             return {}, (f"{LOCAL_FILE}: invalid YAML: {error}",)
         entries = data.get("executables") if isinstance(data, dict) else None
         if not isinstance(entries, dict):
             return {}, ("executables: must be a mapping",)
         found, problems = {}, []
         for name, value in entries.items():
             if name not in KNOWN_TOOLS:
                 problems.append(f"{name}: unknown tool")
             elif not isinstance(value, str) or not os.path.isabs(value):
                 problems.append(f"{name}: path is not absolute")
             else:
                 found[name] = value
         return found, tuple(problems)

     def clear_cache() -> None:
         _load.cache_clear()

     def read_local(root: Path) -> tuple[dict[str, str], list[str]]:
         found, problems = _load(main_checkout(Path(root).resolve()))
         return dict(found), list(problems)

     def tool(name: str, root: Path | None = None) -> str | None:
         base = main_checkout((root or Path.cwd()).resolve())
         configured = _load(base)[0].get(name)
         if configured and _is_executable(configured):
             return configured
         return shutil.which(name)

     def detect(names: Iterable[str] = KNOWN_TOOLS, root: Path | None = None) -> dict[str, str]:
         base = main_checkout((root or Path.cwd()).resolve())
         current = _load(base)[0]
         found = {}
         for name in names:
             keep = current.get(name)
             path = keep if keep and _is_executable(keep) else shutil.which(name)
             if path:
                 found[name] = os.path.abspath(path)
         return found

     def write_local(root: Path, found: Mapping[str, str]) -> Path:
         path = main_checkout(Path(root).resolve()) / LOCAL_FILE
         lines = ['schema_version: "2.9"', "executables:"] + [f"  {k}: {v}" for k, v in found.items()]
         atomic_write_text(path, "\n".join(lines) + "\n")
         clear_cache()
         return path

     def doctor_report(root: Path, *, require_bd: bool) -> tuple[bool, dict[str, Any], list[str]]:
         base = main_checkout(Path(root).resolve())
         configured, problems = read_local(base)
         stale = sorted(n for n, p in configured.items() if not _is_executable(p))
         unconfigured = [n for n in KNOWN_TOOLS if n not in configured]
         missing = [n for n in KNOWN_TOOLS if tool(n, base) is None]
         details = {"configured": configured, "stale": stale, "unconfigured": unconfigured,
                    "missing": missing, "problems": problems}
         actions = []
         if stale or problems:
             actions.append("executables: stale or invalid entries in executables.local.yaml; run gin-workflow setup refresh")
         if "git" in missing:
             actions.append("git: not found; install git")
         if require_bd and "bd" in missing:
             actions.append("bd: not found; install Beads or set providers.task_tracking=markdown")
         return not (stale or problems), details, actions
     ```
     Values are written unquoted; a Windows path with a backslash or a space is still valid plain YAML, and `safe_load` reads it back unchanged. Run the test file → pass.
  3. `setup_service.py`: add `"executables.local.yaml"` to `LOCAL_GITIGNORE_ENTRIES`; `from .executables import detect as detect_tools, doctor_report as executables_report, tool, write_local`; in `detect` replace `shutil.which("bd") is not None` with `tool("bd", root) is not None`; in `initialize`, after `atomic_write_many(writes)` call `write_local(root, detect_tools(root=root))` and add `"write .agent-workflow/executables.local.yaml"` to `INIT_ACTIONS`; in `refresh`, when not `dry_run`, `write_local(root, detect_tools(root=root))` and append the same action; in `doctor`, after the harness block:
     ```python
     require_bd = (effective_cfg.get("providers") or {}).get("task_tracking") == "beads"
     ok, details, exe_actions = executables_report(root, require_bd=require_bd)
     checks["executables"] = ok
     checks_details["executables"] = details
     backend_actions.extend(exe_actions)
     ```
     `bundles.py:63`: add `".agent-workflow/executables.local.yaml"` to the tuple. `ext.py`: `from .executables import KNOWN_TOOLS, tool` and both names in `__all__`. `project_detect.py:170`: `which: Callable[[str], str | None] = tool` with `from .executables import tool`.
  4. `test_setup_cli.py`: extend `test_init_writes_gitignore_with_local_entries` (line 101) to assert `executables.local.yaml` is in the gitignore and the file exists with `git:` in it; add `test_refresh_rewrites_executables_file` (write a stale `bd` entry, run `refresh`, assert it is gone); add `test_doctor_reports_stale_and_missing_executables` (file with `gh: <deleted>`; `checks["executables"]` false, `stale == ["gh"]`, action contains `setup refresh`; after `refresh`, true) and `test_doctor_lists_missing_optional_tools_without_failing` (PATH = temp dir with only python; `"glab" in missing`, `checks["executables"]` true). `test_ext.py`: add `"KNOWN_TOOLS"`, `"tool"` to `EXPECTED`. Run `python3 -m unittest tests.workflow_core.test_setup_cli tests.workflow_core.test_ext tests.workflow_core.test_project_detect` → pass.
  5. Docs: `config.md` Files table row `| .agent-workflow/executables.local.yaml | no | Machine-local paths of the external CLIs (git, bd, gh, glab, npm, npx, gin-workflow, gin-orchestrator, codegraph); written by setup init/refresh |`; update the gitignore sentence at line 18 to list six entries; new section `## executables.local.yaml` after line 194 with the spec R1 example, "only tools found are listed", "a configured path is used while it is an executable file; otherwise the command falls back to PATH", "`setup doctor` reports `stale`, `unconfigured`, `missing`, `problems`". `cli.md`: `init` row adds "and `executables.local.yaml`"; `refresh` row adds "and rewrites `executables.local.yaml`"; `doctor` row adds "external CLI paths". `troubleshooting.md`: `## A CLI works in your shell but gin-workflow reports it missing or uses an old copy` → run `gin-workflow setup refresh`, or edit `.agent-workflow/executables.local.yaml`.
  6. Full suite `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.test_all` → `OK (skipped=N)` with N equal to the baseline on `master`. Commit: `feat(executables): record external CLI paths at setup and resolve through one function`.
- **Acceptance criteria**: spec US-1 (file written, gitignored, configured path used, stale falls back), US-3 (doctor JSON), `tests/workflow_core/test_executables.py` and the new `test_setup_cli.py` cases pass, docs updated.
- **Estimated complexity**: medium

### Track 2: workflow_core and review_ledger call sites
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/tasks.py:144,204`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs.py:430`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team_beads.py:27,87`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/usage.py:131`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/milestone_cli.py:80`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team_init.py:130-131,159-161`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team_host.py:36`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs_trace.py:61`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/orchestrator_client.py:26,48`
  - Modify `plugins/gin-workflow/src/scripts/review_ledger/cleanup.py:34-46,72`
  - Test `tests/workflow_core/test_tasks.py`, `tests/workflow_core/test_team_gates.py` (covers `team_host`), `tests/workflow_core/test_orchestrator_client.py`, `tests/review_ledger/test_cleanup.py`
- **Provider role**: `backend`
- **Model:** `haiku`
- **Effort:** `low`
- **Why:** mechanical one-line swaps with a fixed list of lines; the error handling around each stays.
- **Interfaces** (consumed): `workflow_core.executables.tool(name, root)`.
- **Steps**:
  1. Failing test first in `tests/workflow_core/test_tasks.py`: `with mock.patch("workflow_core.tasks.tool", return_value=str(fake_bd)), mock.patch("shutil.which", return_value=None): tasks.query(root, ["ready"])` runs the fake (use `fake_cli` from `team_fixtures` with a `ready` rule). Fails with `AttributeError: tasks has no attribute tool`.
  2. In each listed file: `from .executables import tool` (review_ledger: `from workflow_core.executables import tool`, matching how `cleanup.py` already imports `workflow_core`); replace `shutil.which("bd")` → `tool("bd", root)` where `root` is in scope, else `tool("bd")`; `team_host.py:36` → `tool(_EXECUTABLE[host], cwd)`; `specs_trace.py:61` → `tool("gh", root)`; `orchestrator_client.py:26,48` → `tool("gin-orchestrator")`; `team_init.py:130` `_ok` → `if tool(argv[0], root) is None`, and line 161 `if tool("bd", root)`; `cleanup.py`: delete `_find_bd_executable` (lines 34-46) and at line 72 `bd_bin = tool("bd", repo_path)` (the variable holding the repository path in that function). Remove `import shutil` where it becomes unused.
  3. Add the configured-path test to `test_team_gates.py` (patch `workflow_core.team_host.tool`), `test_orchestrator_client.py` (patch `workflow_core.orchestrator_client.tool`, call `status.cache_clear()` first), `tests/review_ledger/test_cleanup.py` (assert `_find_bd_executable` no longer exists: `self.assertFalse(hasattr(cleanup, "_find_bd_executable"))`).
  4. `grep -rn 'shutil.which("bd")\|shutil.which("gh")\|shutil.which("glab")\|shutil.which("gin-orchestrator")\|linuxbrew' plugins/gin-workflow/src/scripts` → no output. Full suite → `OK`, skip count unchanged. Commit: `refactor(core): resolve bd, gh, glab and gin-orchestrator through executables.tool`.
- **Acceptance criteria**: spec US-2 for the gin-workflow plugin paths; all existing tests pass with fakes on PATH.
- **Estimated complexity**: low

### Track 3: gin-orchestrator and gin-qa call sites
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-orchestrator/src/scripts/gin_orchestrator/cli.py:187`
  - Modify `plugins/gin-orchestrator/src/scripts/gin_orchestrator/workspace.py:171`
  - Modify `plugins/gin-orchestrator/src/scripts/gin_orchestrator/task_tracking_cli.py:124-127`
  - Modify `plugins/gin-qa/src/scripts/gin_qa/reqs.py:35`
  - Modify `plugins/gin-qa/src/scripts/gin_qa/e2e.py:175`
  - Test `tests/gin_orchestrator/test_task_tracking_cli.py`, `tests/gin_orchestrator/test_contract_v2.py` (covers `configure`), `tests/gin_qa/test_cases_cli.py` (covers `specs_reqs`)
- **Provider role**: `backend`
- **Model:** `haiku`
- **Effort:** `low`
- **Why:** five one-line swaps behind the facade; the only judgement (the launcher exception) is decided below.
- **Interfaces** (consumed): `from workflow_core.ext import tool` (gin-orchestrator and gin-qa import only `workflow_core.ext`).
- **Steps**:
  1. Failing test: in `tests/gin_orchestrator/test_task_tracking_cli.py`, construct the provider with no `executable` and a recording runner; with `mock.patch("gin_orchestrator.task_tracking_cli.tool", return_value="/cfg/gin-workflow")`, assert the runner receives `["/cfg/gin-workflow", "task", ...]`. Fails: `tool` not defined.
  2. `task_tracking_cli.py:124`: signature `executable: str | None = None`; body `self.executable = executable or tool("gin-workflow", self.repository_root) or "gin-workflow"`. `cli.py:187`: `gin_workflow = tool("gin-workflow", root)`. `workspace.py:171`: `[tool("npm", path) or "npm", *install_argv]` (drop the PATHEXT comment: `tool` falls back to `shutil.which`, which handles it). `reqs.py:35`: `tool("gin-workflow", root)`. `e2e.py:175`: `tool("npx", root)`. Each with `from workflow_core.ext import tool` next to the existing `ext` imports.
  3. Launcher exception: `plugins/gin-orchestrator/src/scripts/gin-orchestrator:15` keeps `shutil.which("gin-workflow")` because it runs before `workflow_core` is importable (it uses `gin-workflow paths --json` to locate `lib_dir`). Add a one-line comment saying so. This is the one deviation from spec R3, recorded here for approval.
  4. `grep -rn 'shutil.which' plugins/gin-orchestrator/src/scripts plugins/gin-qa/src/scripts` → only the launcher line and `native_cli.py` (harness lookups, out of scope). Full suite → `OK`. Commit: `refactor(orchestrator,qa): resolve gin-workflow, npm and npx through executables.tool`.
- **Acceptance criteria**: spec US-2 for the two add-ons, with the launcher exception documented in the plan and the commit message.
- **Estimated complexity**: low

### Track 4: `.cmd` wrappers for the fake CLIs
- **Dependencies**: Track 3 (shares `orchestrator_client` expectations through `on_path`; avoids a merge on `tests/gin_qa`)
- **Files**:
  - Modify `tests/workflow_core/team_fixtures.py:62-80,109-118` (`FAKE` rule lookup, `fake_cli`)
  - Modify `tests/workflow_core/orchestrator_fakes.py:16-86`
  - Modify `tests/gin_qa/qa_fixtures.py:22-39`
  - Modify `tests/gin_qa/test_cases_cli.py:247` (the one caller that passes a `#!/bin/sh` `body`)
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** small files, but the Windows path (argv[0] under a `.cmd`, `%~dp0`, `PATHEXT`) cannot be run locally; the implementer must reason about it from the spec and CI output.
- **Interfaces** (produced): unchanged signatures `fake_cli(bin_dir, name, rules) -> Path`, `fake_orchestrator(dir, ...) -> Path`, `gin_workflow_bin(base, body="") -> Path`; on `nt` each returns the `.cmd` path.
- **Steps**:
  1. `team_fixtures.py`: in `FAKE`, `Path(sys.argv[0]).name` → `Path(sys.argv[0]).stem` (both uses, lines 66 and 68, so the log and the rule file use the bare name on every platform). In `fake_cli`: remove the `SkipTest`; 
     ```python
     if os.name == "nt":
         script = bin_dir / f"{name}.py"
         script.write_text(FAKE.format(python=sys.executable), encoding="utf-8")
         path = bin_dir / f"{name}.cmd"
         path.write_text(f'@"{sys.executable}" "%~dp0{name}.py" %*\r\n', encoding="utf-8")
         return path
     ```
     POSIX branch unchanged. Run `python3 -m unittest tests.workflow_core.test_team_gates` on Linux → pass (stem == name there).
  2. `orchestrator_fakes.py`: same shape: on `nt` write `gin-orchestrator.py` and `gin-orchestrator.cmd`; remove the `SkipTest`. The script's `#!/usr/bin/env python3` line stays (harmless on Windows).
  3. `qa_fixtures.py`: remove the `SkipTest`; on `nt` write `gin-workflow.cmd` with `@"{sys.executable}" "{LAUNCHER}" %*` when `body` is empty, else `body`; `qa()` default `path` → `os.defpath`. The one caller passing `body`, `test_cases_cli.py:247`, needs a stub that prints `error: argument command: invalid choice: 'reqs'` to stderr and exits 2: add `def failing_stub(stderr: str, code: int) -> str` to `qa_fixtures.py` returning `f'@echo {stderr} 1>&2\r\n@exit {code}\r\n'` on `nt` and `f'#!/bin/sh\necho "{stderr}" >&2\nexit {code}\n'` on POSIX, and call it there.
  4. Push the branch and read the Windows job log: record `skipped=` before/after in the bead notes (`gin-workflow task update <track-bead> --notes`). A test that fails on Windows for a product reason: skip it with `@unittest.skipIf(os.name == "nt", "<reason>; see gin-workflow-<new bead>")` and create the bead. Linux suite → `OK`, skip count unchanged. Commit: `test(fixtures): run the fake CLIs on Windows through .cmd wrappers`.
- **Acceptance criteria**: spec US-4 second and fourth bullets; Windows job green; `skipped=` drop recorded.
- **Estimated complexity**: medium

### Track 5: Split five Windows-skipped tests
- **Dependencies**: none
- **Files**:
  - Modify `tests/workflow_core/test_task_markdown.py:186-193`
  - Modify `tests/workflow_core/test_hooks.py:94-103`
  - Modify `tests/workflow_core/test_team_init.py:29-41`
  - Modify `tests/workflow_core/test_artifacts.py:16-31`
  - Modify `tests/workflow_core/test_usage_logs.py:156-166`
- **Provider role**: `backend`
- **Model:** `haiku`
- **Effort:** `low`
- **Why:** five mechanical edits with the exact assertion to move named per file.
- **Interfaces**: none.
- **Steps**:
  1. `test_task_markdown.py`: drop the decorator on `test_unsafe_explicit_ids_are_rejected`; move the last line into `@unittest.skipIf(os.name == "nt", "':' is valid only in POSIX file names, so repo:a.b-1 is a POSIX-only id") def test_colon_id_is_accepted_on_posix(self)`.
  2. `test_hooks.py`: drop the decorator; wrap the `0o755` assertion in `if os.name != "nt":  # POSIX permission bits`.
  3. `test_team_init.py`: same for its `0o755` line.
  4. `test_artifacts.py`: drop the decorator; `shared = str(Path(directory).anchor) + "shared/knowledge"` (anchor is `/` on POSIX, `C:\` on Windows) and use `shared` in `configured` and the assertion (`resolve_artifact(config, "knowledge") == Path(shared)`).
  5. `test_usage_logs.py`: drop the decorator; `self.assertEqual(Path(first.cwd).parts[-3:], (".planning", "worktrees", "ep1"))`.
  6. `grep -rn 'skipIf(os.name == "nt"' tests | grep -v '"nt", "'` → nothing. `python3 -m unittest tests.workflow_core.test_task_markdown tests.workflow_core.test_hooks tests.workflow_core.test_team_init tests.workflow_core.test_artifacts tests.workflow_core.test_usage_logs` → `OK`. Commit: `test: run the platform-neutral part of five POSIX-skipped tests on Windows`.
- **Acceptance criteria**: spec R7; the five tests have no whole-test `nt` skip; Linux passes.
- **Estimated complexity**: low

### Track 6: `test.yml` PYTHONPATH scope and timeouts
- **Dependencies**: none
- **Files**:
  - Modify `.github/workflows/test.yml:7-8,12,27,30-31,47-51`
- **Provider role**: `backend`
- **Model:** `haiku`
- **Effort:** `low`
- **Why:** YAML edit with exact lines.
- **Interfaces**: none.
- **Steps**:
  1. Delete lines 7-8 (`env:` / `PYTHONPATH: ...`) at workflow level.
  2. `linux` job: `timeout-minutes: 20`; the step `- run: python3 -m unittest tests/test_all.py -v` becomes
     ```yaml
     - run: python3 -m unittest tests/test_all.py -v
       env:
         PYTHONPATH: plugins/gin-workflow/src/scripts
     ```
  3. `windows` job: `timeout-minutes: 30`; add `PYTHONPATH: plugins/gin-workflow/src/scripts` under the existing `env:` of the `Unit tests` step (next to `TEMP`/`TMP`).
  4. `grep -n 'PYTHONPATH\|timeout-minutes' .github/workflows/test.yml` → four lines: two `PYTHONPATH` inside steps, `20`, `30`. `python3 -c "import yaml,sys; yaml.safe_load(open('.github/workflows/test.yml'))"` → no error. Commit: `ci: scope PYTHONPATH to the unittest steps and tighten timeouts`.
- **Acceptance criteria**: spec R8 and US-4 third bullet; both jobs green on the branch (the install smoke steps still pass without the workflow-level `PYTHONPATH`).
- **Estimated complexity**: low

## Integration
- **Branch**: `feat/windows-ci-and-cli-paths`
- **Merge strategy**: parallel-then-merge (Tracks 1, 5, 6 first; 2 and 3 after 1; 4 after 3)

## Validation
- [ ] `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.test_all` → `OK (skipped=N)` with N equal to the `master` baseline.
- [ ] GitHub Actions `linux` and `windows` jobs green on the branch; Windows `skipped=` ≤ 110 (from 250), recorded in bead notes.
- [ ] `gin-workflow setup refresh` in this repository writes `.agent-workflow/executables.local.yaml` and `git status` stays clean.
- [ ] `gin-workflow setup doctor --format json` shows `checks.executables: true`.
- [ ] `grep -rn 'skipIf(os.name == "nt"' tests | grep -v '"nt", "'` → nothing.

## Notes
- `Model:` and `Effort:` come from the main harness catalog (`haiku`, `sonnet`, `opus`; `low`…`max`).
- Parent Bead: a new epic for `windows-ci-and-cli-paths`; it remains open until the human-confirmed merge. `gin-workflow-myd7` is closed when Tracks 4, 5, 6 close, with their evidence; its items map to Track 5 (item 1), Track 6 (items 2 and 4), Track 4 (item 3).
- Track beads close after tests and review pass.
- Deviation from spec R3 recorded for approval: the `gin-orchestrator` launcher keeps `shutil.which("gin-workflow")` (Track 3 step 3).
