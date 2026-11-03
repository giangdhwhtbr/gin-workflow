"""Shared helpers for gin-qa tests: an SDD repository, a `gin-workflow` on PATH, and test case blocks."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests/workflow_core"))
sys.path.insert(0, str(ROOT / "plugins/gin-qa/src/scripts"))

from specs_fixtures import (ADDED_BLOCK, AUTH_SPEC, LAUNCHER, commit_all, delta, make_change,  # noqa: E402,F401
                            make_repo, write)

QA_LAUNCHER = ROOT / "plugins/gin-qa/src/scripts/gin-qa"


def python_stub(bin_dir: Path, name: str, body: str) -> Path:
    """`name` on `bin_dir` running the Python `body` (its first line is a `#!` shebang): on nt a .cmd wrapper."""
    bin_dir = Path(bin_dir)
    bin_dir.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        (bin_dir / f"{name}.py").write_text(body, encoding="utf-8")
        path = bin_dir / f"{name}.cmd"
        path.write_text(f'@"{sys.executable}" "%~dp0{name}.py" %*\r\n', encoding="utf-8", newline="")
        return path
    path = bin_dir / name
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)
    return path


def gin_workflow_bin(base: Path, body: str = "") -> Path:
    """A bin directory whose `gin-workflow` runs this checkout's launcher (or `body` when given)."""
    bin_dir = Path(base) / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        script = bin_dir / "gin-workflow.cmd"
        script.write_text(body or f'@"{sys.executable}" "{LAUNCHER}" %*\r\n', encoding="utf-8", newline="")
        return bin_dir
    script = bin_dir / "gin-workflow"
    script.write_text(body or f'#!/bin/sh\nexec "{sys.executable}" "{LAUNCHER}" "$@"\n', encoding="utf-8")
    script.chmod(0o755)
    return bin_dir


def failing_stub(stderr: str, code: int) -> str:
    """A `gin-workflow` stub body that prints `stderr` and exits `code`."""
    if os.name == "nt":
        return f'@echo {stderr} 1>&2\r\n@exit {code}\r\n'
    return f'#!/bin/sh\necho "{stderr}" >&2\nexit {code}\n'


def qa(root: Path, bin_dir: Path | None, *args: str, group: str = "cases",
       path: str = os.defpath) -> subprocess.CompletedProcess[str]:
    search = os.pathsep.join([*([str(bin_dir)] if bin_dir else []), path])
    return subprocess.run([sys.executable, str(QA_LAUNCHER), group, *args, "--repository", str(root)],
                          capture_output=True, text=True, env={**os.environ, "PATH": search})


def hash8(root: Path, bin_dir: Path, req: str) -> str:
    result = subprocess.run([shutil.which("gin-workflow", path=str(bin_dir)), "specs", "reqs", "--repository", str(root),
                             "--format", "json"], capture_output=True, text=True, check=True)
    rows = [row for row in json.loads(result.stdout)["requirements"] if row["id"] == req]
    return rows[-1]["hash"][:8]


def case(tc_id: str, ref: str, *, title: str = "Case", extra: str = "") -> str:
    """A well-formed block; `ref` is the whole REQ:/Source: line."""
    return (f"### {tc_id}: {title}\n{ref}\nType: e2e\nPriority: high\n{extra}\nPreconditions:\n- a user exists\n\n"
            f"Steps:\n1. Open /login\n2. Click \"Sign in\"\n\nExpected:\n- The dashboard is shown\n")


def cases_file(cap: str, *blocks: str) -> str:
    return f"# Test cases: {cap}\n\n" + "\n".join(blocks)
