"""Shared helpers for gin-qa tests: an SDD repository, a `gin-workflow` on PATH, and test case blocks."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests/workflow_core"))
sys.path.insert(0, str(ROOT / "plugins/gin-qa/src/scripts"))

from specs_fixtures import (ADDED_BLOCK, AUTH_SPEC, LAUNCHER, commit_all, delta, make_change,  # noqa: E402,F401
                            make_repo, write)

QA_LAUNCHER = ROOT / "plugins/gin-qa/src/scripts/gin-qa"


def gin_workflow_bin(base: Path, body: str = "") -> Path:
    """A bin directory whose `gin-workflow` runs this checkout's launcher (or `body` when given)."""
    bin_dir = Path(base) / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    script = bin_dir / "gin-workflow"
    script.write_text(body or f'#!/bin/sh\nexec "{sys.executable}" "{LAUNCHER}" "$@"\n', encoding="utf-8")
    script.chmod(0o755)
    return bin_dir


def qa(root: Path, bin_dir: Path | None, *args: str) -> subprocess.CompletedProcess[str]:
    path = os.pathsep.join([*([str(bin_dir)] if bin_dir else []), "/usr/bin", "/bin"])
    return subprocess.run([sys.executable, str(QA_LAUNCHER), "cases", *args, "--repository", str(root)],
                          capture_output=True, text=True, env={**os.environ, "PATH": path})


def hash8(root: Path, bin_dir: Path, req: str) -> str:
    result = subprocess.run([str(bin_dir / "gin-workflow"), "specs", "reqs", "--repository", str(root),
                             "--format", "json"], capture_output=True, text=True, check=True)
    rows = [row for row in json.loads(result.stdout)["requirements"] if row["id"] == req]
    return rows[-1]["hash"][:8]


def case(tc_id: str, ref: str, *, title: str = "Case", extra: str = "") -> str:
    """A well-formed block; `ref` is the whole REQ:/Source: line."""
    return (f"### {tc_id}: {title}\n{ref}\nType: e2e\nPriority: high\n{extra}\nPreconditions:\n- a user exists\n\n"
            f"Steps:\n1. Open /login\n2. Click \"Sign in\"\n\nExpected:\n- The dashboard is shown\n")


def cases_file(cap: str, *blocks: str) -> str:
    return f"# Test cases: {cap}\n\n" + "\n".join(blocks)
