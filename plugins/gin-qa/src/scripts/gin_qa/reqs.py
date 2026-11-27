"""Requirements from `gin specs reqs`, resolved to one effective block per REQ-ID."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import posixpath
import subprocess
import sys
from typing import Any

import shutil

DEFAULT_CASES = "qa/cases"
DEFAULT_GUIDELINES = "qa/guidelines.md"
DEFAULT_E2E = "qa/e2e"
DEFAULT_EVIDENCE = "qa/evidence"


class QaError(RuntimeError):
    """Usage or environment problem (exit 2)."""


@dataclass
class Effective:
    layout: str
    cases_dir: str
    guidelines: str
    test_globs: list[str]
    e2e_dir: str = DEFAULT_E2E
    evidence_dir: str = DEFAULT_EVIDENCE
    project_root: Path = field(default_factory=Path)
    package_dir: str = ""
    e2e_home: str = ""         # the configured `e2e_dir` when `locate` moved it onto a child worktree
    reqs: dict[str, dict[str, Any]] = field(default_factory=dict)
    removed: dict[str, str] = field(default_factory=dict)
    conflicts: list[str] = field(default_factory=list)
    workspace: bool = False


def specs_reqs(repository: Path | None, change: str | None = None) -> dict[str, Any]:
    """`gin specs reqs` for `repository`, or for the project the current directory belongs to when it is None."""
    executable = shutil.which("gin")  # gin-qa shells out to gin; it imports none of it
    if executable is None:
        raise QaError("gin is not on PATH; install gin-workflow first")
    argv = [executable, "specs", "reqs", *(["--repository", str(repository)] if repository else []),
            "--format", "json"]
    result = subprocess.run(argv + (["--change", change] if change else []), capture_output=True, text=True,
                            cwd=Path.cwd())
    if result.returncode != 0:
        if "invalid choice: 'reqs'" in result.stderr:
            raise QaError("this gin has no `specs reqs`; reinstall a newer gin-workflow")
        raise QaError(result.stderr.strip() or f"gin specs reqs exited {result.returncode}")
    try:
        payload = json.loads(result.stdout)
    except ValueError as error:
        raise QaError(f"gin specs reqs printed no JSON: {error}") from error
    if not isinstance(payload, dict) or not isinstance(payload.get("root"), str) or not payload["root"]:
        raise QaError("this gin is too old for gin-qa; reinstall gin-workflow")
    return payload


def current_hashes(eff: Effective) -> dict[str, str] | None:
    """REQ-ID to its current hash8 in the SDD layout; None in the legacy layout."""
    return {req: row["hash"][:8] for req, row in eff.reqs.items()} if eff.layout == "sdd" else None


def workspace_checkouts(eff: Effective) -> list[dict[str, Any]] | None:
    """The checkout of each cloned workspace repository from `gin workspace status`, or None outside a workspace.

    A failed status command is a warning on stderr and None: it must not fail a test run.
    """
    if not eff.workspace:
        return None
    executable = shutil.which("gin")
    if executable is None:
        print("gin-qa: checkouts not recorded: gin is not on PATH", file=sys.stderr)
        return None
    try:
        result = subprocess.run([executable, "workspace", "status", "--repository", str(eff.project_root), "--json"],
                                capture_output=True, text=True, cwd=Path.cwd())
    except OSError as error:
        print(f"gin-qa: checkouts not recorded: {error}", file=sys.stderr)
        return None
    if result.returncode != 0:
        reason = result.stderr.strip().splitlines()[-1:] or [f"gin workspace status exited {result.returncode}"]
        print(f"gin-qa: checkouts not recorded: {reason[0]}", file=sys.stderr)
        return None
    try:
        rows = json.loads(result.stdout).get("repos")
    except (ValueError, AttributeError):
        rows = None
    if not isinstance(rows, list):
        print("gin-qa: checkouts not recorded: gin workspace status printed no repos list", file=sys.stderr)
        return None
    return [{key: row.get(key) for key in ("path", "branch", "commit", "dirty")}
            for row in rows if isinstance(row, dict) and row.get("present")]


def _inside(key: str, value: str) -> str:
    """One spelling per path (`./qa/e2e/` is `qa/e2e`), so paths built from config compare equal to found ones."""
    path = posixpath.normpath(value.replace("\\", "/"))
    if path.startswith(("/", "../")) or path in ("..", ".") or ":" in path.split("/")[0]:
        raise QaError(f"qa.{key} must be a path inside the repository, got {value!r}")
    return path


def _under(home: str, name: str) -> str:
    """`name` inside the QA home; the home `.` (a QA repository) is the repository itself."""
    return posixpath.normpath(posixpath.join(home, name))


def _root_playwright(root: Path) -> bool:
    """Whether `root` already holds a Playwright project: a `playwright.config.*`, or a package.json with an `e2e` script."""
    if any(root.glob("playwright.config.*")):
        return True
    try:
        scripts = json.loads((root / "package.json").read_text(encoding="utf-8")).get("scripts")
    except (OSError, ValueError, AttributeError):
        return False
    return isinstance(scripts, dict) and "e2e" in scripts


def resolve(payload: dict[str, Any], qa_home: str = "qa") -> Effective:
    """An open change's ADDED/MODIFIED block wins over the living block; its REMOVED block removes the REQ.

    `qa_home` is the QA home relative to the files root (`.` for a QA repository); the default paths are under it and
    an explicit `qa.*` key is relative to the files root.
    """
    qa = payload.get("qa") or {}
    e2e_dir = _inside("e2e", qa["e2e"]) if "e2e" in qa else _under(qa_home, "e2e")
    effective = Effective(payload["layout"],
                          _inside("cases", qa["cases"]) if "cases" in qa else _under(qa_home, "cases"),
                          _inside("guidelines", qa["guidelines"]) if "guidelines" in qa
                          else _under(qa_home, "guidelines.md"),
                          list(payload.get("test_globs", [])), e2e_dir, _under(qa_home, "evidence"))
    effective.package_dir = e2e_dir  # `locate` keeps the files root for an existing root setup
    owner: dict[str, str] = {}
    for row in payload["requirements"]:
        req, change = row["id"], row["change"]
        if change is None:
            effective.reqs.setdefault(req, row)
            continue
        if req in owner and owner[req] != change:
            effective.conflicts.append(f"{row['source']}: {req} is changed by both {owner[req]} and {change}")
            continue
        owner[req] = change
        if row["section"] == "REMOVED":
            effective.reqs.pop(req, None)
            effective.removed[req] = change
        else:
            effective.reqs[req] = row
    return effective


def locate(repository: Path | None, change: str | None = None) -> tuple[Path, Effective]:
    """(the files root, the effective settings): the QA repository in a workspace, else the project root."""
    payload = specs_reqs(repository, change)
    project = Path(payload["root"])
    qa = payload.get("qa") or {}
    if payload.get("qa_root"):
        files_root, home = Path(payload["qa_root"]), "."
        if not files_root.is_dir():
            raise QaError(f"the QA repository {files_root} is not cloned; run `gin workspace clone "
                          f"{files_root.relative_to(project).as_posix() if project in files_root.parents else files_root}`")
    else:
        files_root, home = project, _inside("dir", qa.get("dir", "qa"))
    eff = resolve(payload, home)
    eff.project_root = project
    eff.workspace = bool(payload.get("qa_root"))
    if not payload.get("qa_root") and "dir" not in qa and _root_playwright(files_root):
        eff.package_dir = ""  # R6: an existing root setup keeps the root
    moved = payload.get("e2e_checkout")
    if moved and not payload.get("qa_root") and "e2e" in qa:
        _follow(files_root, eff, moved)
    return files_root, eff


def _follow(files_root: Path, eff: Effective, moved: Any) -> None:
    """Moves `e2e_dir` and `package_dir` from the child at `moved["repo"]` onto its worktree at `moved["path"]`."""
    if not isinstance(moved, dict) or not all(isinstance(moved.get(key), str) for key in ("repo", "path")):
        raise QaError("gin returned an unexpected e2e_checkout; update gin")
    if not eff.package_dir:
        raise QaError(f"Playwright is set up at the root of {files_root}; run gin-qa from the main checkout of "
                      f"{moved['repo']} or move the Playwright setup under {eff.e2e_dir}")
    try:
        lane = Path(moved["path"]).resolve().relative_to(files_root.resolve()).as_posix()
    except ValueError:
        raise QaError(f"{moved['path']} is outside {files_root}; run from "
                      "<parent>/.planning/worktrees/<track>") from None
    eff.e2e_home = eff.e2e_dir
    eff.e2e_dir = eff.package_dir = posixpath.normpath(
        posixpath.join(lane, posixpath.relpath(eff.e2e_dir, moved["repo"])))
