"""Requirements from `gin-workflow specs reqs`, resolved to one effective block per REQ-ID."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any

DEFAULT_CASES = "qa/cases"
DEFAULT_GUIDELINES = "qa/guidelines.md"
DEFAULT_E2E = "qa/e2e"


class QaError(RuntimeError):
    """Usage or environment problem (exit 2)."""


@dataclass
class Effective:
    layout: str
    cases_dir: str
    guidelines: str
    test_globs: list[str]
    e2e_dir: str = DEFAULT_E2E
    reqs: dict[str, dict[str, Any]] = field(default_factory=dict)
    removed: dict[str, str] = field(default_factory=dict)
    conflicts: list[str] = field(default_factory=list)


def specs_reqs(root: Path, change: str | None = None) -> dict[str, Any]:
    executable = shutil.which("gin-workflow")
    if executable is None:
        raise QaError("gin-workflow is not on PATH; install gin-workflow first")
    if not (root / ".agent-workflow/config.yaml").is_file():
        raise QaError("gin-workflow setup is required; run /setup once")
    argv = [executable, "specs", "reqs", "--repository", str(root), "--format", "json"]
    result = subprocess.run(argv + (["--change", change] if change else []), capture_output=True, text=True)
    if result.returncode != 0:
        if "invalid choice: 'reqs'" in result.stderr:
            raise QaError("this gin-workflow has no `specs reqs`; reinstall a newer gin-workflow")
        raise QaError(result.stderr.strip() or f"gin-workflow specs reqs exited {result.returncode}")
    return json.loads(result.stdout)


def resolve(payload: dict[str, Any]) -> Effective:
    """An open change's ADDED/MODIFIED block wins over the living block; its REMOVED block removes the REQ."""
    qa = payload.get("qa") or {}
    effective = Effective(payload["layout"], qa.get("cases", DEFAULT_CASES), qa.get("guidelines", DEFAULT_GUIDELINES),
                          list(payload.get("test_globs", [])), qa.get("e2e", DEFAULT_E2E))
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
