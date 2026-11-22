"""Run history: each recorded result as one JSON line in `<runs>/<yyyy-mm>/<actor>.jsonl`.

One file per tester and month, so two testers never write the same file; `.gitattributes` merges one tester's
appends on two branches by union.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
from typing import Any

KEYS = ("actor", "at", "bug", "capability", "case", "evidence", "hash8", "result", "run")
_UNSAFE = re.compile(r"[^a-z0-9._-]+")
_AT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def runs_dir(cases_dir: str) -> str:
    """The `runs` folder next to the cases folder: `qa/runs` for `qa/cases`."""
    return (PurePosixPath(cases_dir).parent / "runs").as_posix()


def default_actor(root: Path) -> str:
    """`git config user.email`, the identity gin team mode uses; `unknown` when it is unset."""
    done = subprocess.run(["git", "config", "user.email"], cwd=root, capture_output=True, text=True, check=False)
    return done.stdout.strip() or "unknown"


def now() -> str:
    """The UTC time of a record, to the second."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def file_for(cases_dir: str, actor: str, at: str) -> str:
    """`<runs>/<yyyy-mm of at>/<actor, lowercased, other characters as ->.jsonl`, repository-relative."""
    return f"{runs_dir(cases_dir)}/{at[:7]}/{_UNSAFE.sub('-', actor.lower())}.jsonl"


def append(root: Path, cases_dir: str, record: dict[str, Any]) -> str:
    """Appends `record` as one line and returns its file; the caller holds the cases lock."""
    relative = file_for(cases_dir, record["actor"], record["at"])
    try:
        _union(root, cases_dir)
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n")
    except OSError as error:
        raise ValueError(f"{relative}: run record not written: {error}") from error
    return relative


def _union(root: Path, cases_dir: str) -> None:
    """Adds `/<runs>/** merge=union` to `.gitattributes` once, the way `e2e.ignore_evidence` edits `.gitignore`."""
    path = root / ".gitattributes"
    entry = f"/{runs_dir(cases_dir)}/** merge=union"
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    if entry not in lines:
        path.write_text("\n".join([*lines, entry]) + "\n", encoding="utf-8")


def export(root: Path, cases_dir: str, *, capability: str | None = None, case: str | None = None,
           since: str | None = None) -> dict[str, list[Any]]:
    """Every record that passes the filters, by time, then file, then line; unreadable lines go to `problems`."""
    found: list[tuple[str, str, int, dict[str, Any]]] = []
    problems: list[str] = []
    for path in sorted((root / runs_dir(cases_dir)).glob("*/*.jsonl")):
        relative = path.relative_to(root).as_posix()
        for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            row, reason = _parse(line)
            if reason:
                problems.append(f"{relative}:{number}: {reason}")
            elif ((capability is None or row["capability"] == capability) and (case is None or row["case"] == case)
                  and (since is None or row["at"][:10] >= since)):
                found.append((row["at"], relative, number, row))
    return {"runs": [row for *_, row in sorted(found, key=lambda item: item[:3])], "problems": problems}


def _parse(line: str) -> tuple[dict[str, Any], str | None]:
    """A record and None, or the reason the line is not one."""
    try:
        row = json.loads(line)
    except ValueError:
        return {}, "not JSON"
    if not isinstance(row, dict):
        return {}, "not a JSON object"
    missing = [key for key in KEYS if key not in row]
    if missing:
        return row, f"missing {', '.join(missing)}"
    if not isinstance(row["at"], str) or not _AT.match(row["at"]):
        return row, "at is not YYYY-MM-DDTHH:MM:SSZ"
    return row, None
