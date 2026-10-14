# Plan: AGENTS.md managed block rendered by setup

Spec: `.planning/specs/2026-10-14-agents-md-block-design.md`
Workflow id: `agents-md-block`

## Objective
`gin-workflow setup init` writes a managed block into `AGENTS.md` and an `@AGENTS.md` import into `CLAUDE.md`; `setup refresh` re-renders an existing block; `setup doctor` reports `ok | stale | absent | invalid`. `/roadmap` and `/tech-doc` remind the user to refresh.

**Goal (from spec):** Give every harness (Claude, Codex, Antigravity, opencode) the same short project context without a new skill or a new lifecycle step.

**Architecture:** one new pure module `workflow_core/agents_block.py` (render, locate, plan writes, status) called from `setup_service.initialize`, `refresh`, and `doctor`. No new CLI flags, no config key, no schema bump.

**Tech stack:** Python 3 stdlib, `unittest`.

**Global Constraints (verbatim from spec):**
- The block is written only by the setup CLI (`init`, `refresh`), never by an agent or another stage, so it has one owner and renders the same on every machine.
- The block is rendered from tracked data only: `.agent-workflow/config.yaml` and whether the roadmap and codebase-doc paths exist.
- Content outside the markers is preserved byte for byte, including line endings. Writes are atomic (temp file, then replace).
- No config key to disable the block; deleting the block disables it.

## Model Guidance
- `default_model_class`: `standard_impl`
- `phase_guidance`:
  - `implement`: `standard_impl`
  - `review`: `high_reasoning`
  - `docs`: `cheap_simple`
- `override_rule`: none needed; boundaries are settled.

## Requirement Analysis
- Problem statement: gin-workflow never writes `AGENTS.md`/`CLAUDE.md`, so a session in any harness starts without the workflow, checks, or doc links.
- Success criteria: spec US-1..US-3 acceptance criteria pass as tests.
- Constraints: Global Constraints above; existing `already_initialized` behavior of `init` is unchanged when the block is already current.
- Non-goals: a `/init` skill, rule bullets or product summaries in the block, a disable flag, CodeGraph or harness lines.

## Approach Options
### Option 1: New module + three call sites (selected)
- Pros: pure functions unit-testable without the CLI; setup_service changes stay small.
- Cons: one more module.

### Option 2: Inline everything in `setup_service.py`
- Pros: no new file.
- Cons: `setup_service.py` is already ~880 lines; render/locate logic would be tested only through the CLI.

### Recommended Approach
- Selected option: Option 1. Reasoning: the marker parsing has edge cases (CRLF, broken markers) that deserve direct unit tests.

## Scope
- In scope: `agents_block.py`, `setup_service.initialize|refresh|doctor`, two skill report lines, `docs/reference/cli.md`, `docs/reference/config.md`.
- Out of scope: everything in Non-goals; changes to `rules_checks.py`.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Three dependent tracks, each small; one agent in sequence is cheapest.
```

## Tasks

### Track 1: `agents_block` module
- **Dependencies**: none
- **Provider role**: `backend`
- **Reasoning**: `medium`
- **Estimated complexity**: medium
- **Files**:
  - Create: `plugins/gin-workflow/src/scripts/workflow_core/agents_block.py`
  - Test: `tests/workflow_core/test_agents_block.py`
- **Interfaces (produced)**:
  - `START: str`, `END: str`
  - `class AgentsBlockError(ValueError)`
  - `render(root: Path, config: Mapping[str, Any]) -> str` — block text, markers included, LF, no trailing newline.
  - `locate(text: str) -> tuple[int, int] | None` — `(start_offset, end_offset)` of the block (end offset after the END marker); `None` when absent; raises `AgentsBlockError` on broken markers.
  - `status(root: Path, config: Mapping[str, Any]) -> str` — `"ok" | "stale" | "absent" | "invalid"`.
  - `planned_writes(root: Path, config: Mapping[str, Any], *, create: bool) -> dict[Path, bytes]` — only files whose bytes would change; `create=True` (init) may create `AGENTS.md`, add a missing block, and add `@AGENTS.md` to `CLAUDE.md`; `create=False` (refresh) only replaces an existing block.
  - `write(writes: Mapping[Path, bytes]) -> None` — atomic per file, keeps an existing file's mode, new files `0o644`.
- **Interfaces (consumed)**: `project.VERIFY_KEYS`, `project.project_settings(config).verify_commands`, `specs.sdd_config(config)["layout"|"codebase"]`, `atomic.atomic_write_bytes(path, content, mode=)`.

Steps:
1. Write failing tests in `tests/workflow_core/test_agents_block.py` (sys.path setup as in `test_setup_cli.py`; build `config` dicts directly, e.g. `{"verify": {"checks": {"lint": "ruff check .", "test": "pytest"}}}`):
   - `test_render_lists_only_configured_checks_in_order`: lint and test set, typecheck empty → line is ``- Checks (git hooks): lint `ruff check .` · test `pytest` ``.
   - `test_render_without_checks_says_none_configured`.
   - `test_render_docs_links_only_existing_paths_legacy`: create `.planning/roadmap.md` only → ``- Roadmap: `.planning/roadmap.md` ``; no codebase link; with neither → no docs line.
   - `test_render_docs_links_sdd_layout`: `{"artifacts": {"layout": "sdd", "codebase": "docs/cb"}}`, create `docs/roadmap.md` and `docs/cb/` → ``- Roadmap: `docs/roadmap.md` · Codebase docs: `docs/cb/` ``.
   - `test_locate_broken_markers_raise`: missing END, duplicate START, END before START each raise `AgentsBlockError`.
   - `test_create_on_empty_repo_writes_agents_and_claude`: `planned_writes(create=True)` returns both paths; `CLAUDE.md` bytes are `b"@AGENTS.md\n"`.
   - `test_create_preserves_outside_bytes_crlf`: existing `AGENTS.md` `b"# Mine\r\nkeep\r\n"` and `CLAUDE.md` `b"# Notes\r\n"` → AGENTS output starts with the original bytes and the block uses `\r\n`; CLAUDE output is `b"@AGENTS.md\r\n\r\n# Notes\r\n"`.
   - `test_second_run_is_noop`: write, then `planned_writes(create=True)` and `(create=False)` both return `{}`.
   - `test_refresh_never_creates`: no block → `planned_writes(create=False) == {}` and `CLAUDE.md` untouched.
   - `test_status_states`: `absent` (no file / no block), `ok` after write, `stale` after creating `.planning/roadmap.md`, `invalid` with a lone START.
   - `test_new_file_mode_is_0644`.
2. Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.workflow_core.test_agents_block -v` → fails (module missing).
3. Implement:

```python
"""Managed gin-workflow block in AGENTS.md, plus the @AGENTS.md import in CLAUDE.md."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping

from .atomic import atomic_write_bytes
from .project import VERIFY_KEYS, project_settings
from .specs import sdd_config

START = "<!-- gin-workflow:start — generated by `gin-workflow setup refresh`; edit outside this block -->"
END = "<!-- gin-workflow:end -->"
_START_PREFIX = "<!-- gin-workflow:start"
IMPORT = "@AGENTS.md"


class AgentsBlockError(ValueError):
    """Broken gin-workflow markers in AGENTS.md."""


def render(root: Path, config: Mapping[str, Any]) -> str:
    commands = project_settings(config).verify_commands
    checks = " · ".join(f"{key} `{commands[key]}`" for key in VERIFY_KEYS if commands.get(key))
    sdd = sdd_config(config)
    if sdd["layout"] == "sdd":
        roadmap, codebase = "docs/roadmap.md", str(sdd["codebase"]).rstrip("/")
    else:
        roadmap, codebase = ".planning/roadmap.md", ".planning/codebase"
    docs = [f"{label}: `{shown}`" for label, path, shown in
            (("Roadmap", roadmap, roadmap), ("Codebase docs", codebase, f"{codebase}/"))
            if (Path(root) / path).exists()]
    lines = [
        START,
        "## gin-workflow",
        "",
        "- Track work in Beads (`bd`). Stages: `/discuss` → `/plan` → `/orchestrate` → `/execute` → `/ship`; "
        "`/workflow` runs the next one; small changes: `/quick`.",
        "- Never commit to `main`/`master`. Opening a PR, merging, or force-pushing needs user approval.",
        "- Before editing code, run `gin-workflow rules --files <paths>` and follow its output.",
        f"- Checks (git hooks): {checks}" if checks else
        "- Checks: none configured yet; `gin-workflow setup doctor` reports them once sources exist.",
    ]
    if docs:
        lines.append("- " + " · ".join(docs))
    return "\n".join([*lines, END])


def locate(text: str) -> tuple[int, int] | None:
    starts, ends = text.count(_START_PREFIX), text.count(END)
    if starts == 0 and ends == 0:
        return None
    start, end = text.find(_START_PREFIX), text.find(END)
    if starts != 1 or ends != 1 or end < start:
        raise AgentsBlockError("AGENTS.md has broken gin-workflow markers; fix or remove them by hand")
    return start, end + len(END)


def _read(path: Path) -> str | None:
    return path.read_bytes().decode("utf-8") if path.is_file() else None


def _newline(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def planned_writes(root: Path, config: Mapping[str, Any], *, create: bool) -> dict[Path, bytes]:
    root = Path(root)
    agents, claude = root / "AGENTS.md", root / "CLAUDE.md"
    writes: dict[Path, bytes] = {}
    current = _read(agents)
    span = locate(current) if current is not None else None
    if span is None and not create:
        return writes
    newline = _newline(current or "")
    block = render(root, config).replace("\n", newline)
    if current is None:
        updated = block + newline
    elif span is None:
        prefix = current if not current or current.endswith(("\n", "\r\n")) else current + newline
        updated = prefix + (newline if prefix else "") + block + newline
    else:
        updated = current[:span[0]] + block + current[span[1]:]
    if updated != current:
        writes[agents] = updated.encode("utf-8")
    if create:
        existing = _read(claude)
        if existing is None:
            writes[claude] = (IMPORT + "\n").encode("utf-8")
        elif IMPORT not in (line.strip() for line in existing.splitlines()):
            nl = _newline(existing)
            writes[claude] = (IMPORT + nl + nl + existing).encode("utf-8")
    return writes


def status(root: Path, config: Mapping[str, Any]) -> str:
    current = _read(Path(root) / "AGENTS.md")
    try:
        span = locate(current) if current is not None else None
    except AgentsBlockError:
        return "invalid"
    if span is None:
        return "absent"
    return "ok" if not planned_writes(root, config, create=False) else "stale"


def write(writes: Mapping[Path, bytes]) -> None:
    for path, content in writes.items():
        mode = (os.stat(path).st_mode & 0o777) if path.exists() else 0o644
        atomic_write_bytes(path, content, mode=mode)
```

4. Run the step-2 command → all pass.
5. Commit: `feat(setup): render the gin-workflow block for AGENTS.md`.
- **Acceptance criteria**: every step-1 test passes; module imports only stdlib and existing `workflow_core` modules.

### Track 2: Wire into `setup init`, `refresh`, `doctor`
- **Dependencies**: Track 1
- **Provider role**: `backend`
- **Reasoning**: `medium`
- **Estimated complexity**: medium
- **Files**:
  - Modify: `plugins/gin-workflow/src/scripts/workflow_core/setup_service.py` — `initialize` (lines 101–232), `refresh` (333–346), `doctor` (after the rules block, ~line 590)
  - Test: `tests/workflow_core/test_setup_cli.py` (new methods in `SetupCliTests`, using `run_cli`)
- **Interfaces (consumed)**: Track 1 `planned_writes`, `write`, `status`, `AgentsBlockError`.
- **Interfaces (produced)**: JSON fields — `init` actions include `"write AGENTS.md gin-workflow block"` and/or `"add @AGENTS.md to CLAUDE.md"`; `refresh` payload gains `"agents_block": "updated" | "unchanged" | "absent"`; `doctor` `checks_details["agents_block"]` is one of `ok|stale|absent|invalid`, and `stale`/`invalid` add an `actions` entry.

Steps:
1. Failing CLI tests (each in a `tempfile.TemporaryDirectory()`; init with `"init", "--approve", "--harness", "claude", "--set", 'verify.checks.test="pytest"'`):
   - `test_init_writes_agents_block_and_claude_import`: both files exist; `AGENTS.md` contains ``test `pytest` ``; `CLAUDE.md` first line `@AGENTS.md`; payload actions include both strings.
   - `test_init_dry_run_lists_agents_actions_without_writing`.
   - `test_init_on_initialized_repo_adds_missing_block`: init, delete `AGENTS.md`, `init --dry-run` → `would_update` with the AGENTS action; `init` without `--approve` → nonzero, `approval_required`; `init --approve` → `updated`, file restored; a further `init --approve` → `already_initialized`.
   - `test_refresh_updates_existing_block_only`: init, create `.planning/roadmap.md`, `refresh` → `agents_block: updated` and the link appears; remove the block text from `AGENTS.md`, `refresh` → `absent`, file unchanged.
   - `test_refresh_and_init_fail_on_broken_markers`: append a second START to `AGENTS.md`; `refresh` → nonzero exit, file bytes unchanged.
   - `test_doctor_reports_agents_block_state`: `ok` after init; `stale` after creating `.planning/roadmap.md` with an action mentioning `gin-workflow setup refresh`; `absent` after removing the block, with `checks` health unchanged.
2. Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.workflow_core.test_setup_cli -v` → new tests fail.
3. Implement in `setup_service.py`:
   - `from . import agents_block` at the top; helper:
     ```python
     def _agents_writes(root: Path, config: Mapping[str, Any], *, create: bool) -> dict[Path, bytes]:
         try:
             return agents_block.planned_writes(root, config, create=create)
         except agents_block.AgentsBlockError as error:
             raise SetupError(str(error)) from error

     def _agents_actions(root: Path, writes: Mapping[Path, bytes]) -> list[str]:
         names = {root / "AGENTS.md": "write AGENTS.md gin-workflow block", root / "CLAUDE.md": "add @AGENTS.md to CLAUDE.md"}
         return [names[path] for path in writes]
     ```
   - `initialize`, fresh path: after `resolved = ...`, `agents_writes = _agents_writes(root, resolved.config.to_dict(), create=True)`; dry-run payload `actions` extended with `_agents_actions`; after `atomic_write_many(writes)` call `agents_block.write(agents_writes)`; returned `actions` extended likewise.
   - `initialize`, already-initialized and not-repair path (replace `return {"status": "already_initialized", ...}`): compute `agents_writes` from `resolve_effective_config(root, write=False).config.to_dict()`; empty → unchanged `already_initialized` return; else dry-run → `{"status": "would_update", "actions": _agents_actions(...)}`; no `--approve` → `SetupError(..., status="approval_required")`; else `agents_block.write(...)` and return `{"status": "updated", "actions": ...}`. The repair path also calls `agents_block.write(_agents_writes(..., create=True))` after `resolve_effective_config(root)` and appends its actions.
   - `refresh`: after resolving, `writes = _agents_writes(root, result.config.to_dict(), create=False)`; `agents_state = "updated" if writes else ("unchanged" if agents_block.status(...) == "ok" else "absent")` (compute status before writing); write unless `dry_run`; add `"agents_block": agents_state` and, when writes, the action `"update AGENTS.md gin-workflow block"`.
   - `doctor`: inside `if checks["configuration"]:` after the rules block: `state = agents_block.status(root, effective)`; `checks_details["agents_block"] = state`; `stale` → `actions.append("agents: AGENTS.md block is stale; run gin-workflow setup refresh")`; `invalid` → `actions.append("agents: AGENTS.md has broken gin-workflow markers; fix or remove them")`. Do not add a `checks` key.
4. Run the step-2 command, then the full suite `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests/test_all.py` → all pass (existing `init` tests that assert exact `actions` lists are updated to include the two new actions).
5. Commit: `feat(setup): init, refresh, and doctor manage the AGENTS.md block`.
- **Acceptance criteria**: spec US-1, US-2 (refresh/doctor parts), US-3 pass as CLI tests; full suite green.

### Track 3: Skill reminders and docs
- **Dependencies**: Track 2
- **Provider role**: `docs`
- **Reasoning**: `low`
- **Estimated complexity**: low
- **Files**:
  - Modify: `plugins/gin-workflow/src/skills/roadmap/SKILL.md` (step 8 Report)
  - Modify: `plugins/gin-workflow/src/skills/tech-doc/SKILL.md` (Flow, new final step after step 5)
  - Modify: `docs/reference/cli.md` (setup table rows `init` line 27, `refresh` line 29, `doctor` line 31)
  - Modify: `docs/reference/config.md` (`## Files`, line 5)
  - Test: `tests/workflow_core/test_agents_block.py` (one more test)
Steps:
1. Failing test `test_roadmap_and_tech_doc_skills_remind_refresh`: both SKILL.md files contain `gin-workflow setup refresh`.
2. Run it → fails.
3. Edits:
   - roadmap step 8: append `; and \`gin-workflow setup refresh\` to update the links in \`AGENTS.md\``  before the final period.
   - tech-doc: `6. **Report**: the files written, and \`gin-workflow setup refresh\` to update the links in \`AGENTS.md\`.`
   - cli.md `init`: add "; also writes the gin-workflow block in `AGENTS.md` and `@AGENTS.md` in `CLAUDE.md`, and adds a missing block on an initialized repository (with `--approve`)". `refresh`: add "and re-renders an existing `AGENTS.md` block (never creates one)". `doctor`: add "the `AGENTS.md` block (`ok`, `stale`, `absent`, `invalid`)".
   - config.md `## Files`: one bullet — "`AGENTS.md`: the block between `<!-- gin-workflow:start … -->` and `<!-- gin-workflow:end -->` is generated from this configuration; edit outside it, delete it to opt out. `CLAUDE.md` imports it with `@AGENTS.md`."
4. Run the test plus `tests/workflow_core/test_token_budget.py` and `tests/workflow_core/test_docs_coverage.py` → pass. Run the full suite.
5. Commit: `docs(setup): document the AGENTS.md block; roadmap and tech-doc remind refresh`.
- **Acceptance criteria**: spec US-2 third criterion; docs describe all three commands' behavior; token-budget and docs-coverage tests pass.

## Integration
- **Branch**: `feat/agents-md-block` (from `discuss/agents-md-block`, which holds the spec and this plan)
- **Merge strategy**: sequential

## Validation
- [ ] `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests/test_all.py` passes
- [ ] `bash tests/install_smoke_test.sh` exits 0
- [ ] Manual: in a temp repo, `gin-workflow setup init --approve --harness claude`, then `cat AGENTS.md CLAUDE.md`; create `.planning/roadmap.md`, `setup doctor` shows `stale`, `setup refresh` adds the link.

## Notes
- Parent Bead (epic) stays open until the human-confirmed merge; track beads close once tests and review pass.
- Spec detail made concrete here: "running `setup init` again" on an initialized repository writes a missing block only with `--approve`, status `updated`; a current block keeps the old `already_initialized` result.
