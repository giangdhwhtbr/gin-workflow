"""Machine-local paths of the external CLIs gin-workflow runs, written by setup, with PATH fallback."""
from __future__ import annotations

import functools
import os
import shutil
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
    except (yaml.YAMLError, OSError, UnicodeDecodeError) as error:
        return {}, (f"{LOCAL_FILE}: invalid YAML: {error}",)
    entries = data.get("executables") if isinstance(data, dict) else None
    if not isinstance(entries, dict):
        return {}, ("executables: must be a mapping",)
    found: dict[str, str] = {}
    problems: list[str] = []
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
    """The configured path of `name` while it is an executable file, else the PATH lookup."""
    base = main_checkout((Path(root) if root else Path.cwd()).resolve())
    configured = _load(base)[0].get(name)
    if configured and _is_executable(configured):
        return configured
    return shutil.which(name)


def detect(names: Iterable[str] = KNOWN_TOOLS, root: Path | None = None) -> dict[str, str]:
    base = main_checkout((Path(root) if root else Path.cwd()).resolve())
    current = _load(base)[0]
    found: dict[str, str] = {}
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
