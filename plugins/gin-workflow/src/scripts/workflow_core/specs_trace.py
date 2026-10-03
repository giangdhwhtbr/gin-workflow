"""Requirement traceability (REQ -> tests) and spec-review PR status."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
from typing import Any, Mapping

from .specs import REQ_ID, SpecsError, delta_blocks, test_files


def _tracked(root: Path) -> list[str]:
    listed = subprocess.run(["git", "ls-files"], cwd=root, text=True, capture_output=True, check=False)
    if listed.returncode == 0:
        return listed.stdout.splitlines()
    return [path.relative_to(root).as_posix() for path in Path(root).rglob("*") if path.is_file()]


def _tests_md_rows(path: Path) -> list[tuple[str, set[str], str]]:
    rows = []
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) >= 4 and line.lstrip().startswith("|"):
            ids = {match.group(0) for match in REQ_ID.finditer(cells[1])}
            if ids:
                rows.append((cells[0], ids, cells[3]))
    return rows


def trace(root: Path, cfg: Mapping[str, Any], change: Path) -> dict[str, Any]:
    blocks, errors = delta_blocks(root, change)
    if errors:
        raise SpecsError("; ".join(errors))
    wanted = [block.id for block in blocks if block.section in ("ADDED", "MODIFIED")]
    sources: dict[str, list[str]] = {req: [] for req in wanted}
    for relative in test_files(root, cfg, _tracked(root)):
        try:
            text = (Path(root) / relative).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for req in {match.group(0) for match in REQ_ID.finditer(text)} & set(wanted):
            sources[req].append(relative)
    tests_md = change / "tests.md"
    for case, ids, evidence in _tests_md_rows(tests_md):
        if evidence and evidence != "-":
            for req in ids & set(wanted):
                sources[req].append(f"{tests_md.relative_to(root).as_posix()}#{case}")
    requirements = [{"id": req, "status": "covered" if sources[req] else "missing", "sources": sorted(sources[req])}
                    for req in wanted]
    return {"change": change.name, "requirements": requirements,
            "missing": [row["id"] for row in requirements if row["status"] == "missing"]}


def status(root: Path, change: Path) -> dict[str, Any]:
    branch = f"spec/{change.name}"
    record = "gin-workflow record requirement-confirmed --workflow-id <epic> --evidence <pr-url> --actor <id>"
    executable = shutil.which("gh")
    if executable is None:
        return {"change": change.name, "branch": branch, "status": "gh_unavailable",
                "message": f"gh unavailable; check the PR for {branch} by hand, then: {record}"}
    listed = subprocess.run([executable, "pr", "list", "--head", branch, "--state", "all",
                             "--json", "url,state,mergeCommit"], cwd=root, text=True, capture_output=True, check=False)
    if listed.returncode != 0:
        raise SpecsError(f"gh pr list failed: {listed.stderr.strip()}")
    prs = json.loads(listed.stdout or "[]")
    if not prs:
        return {"change": change.name, "branch": branch, "status": "none"}
    pr = prs[0]
    state = str(pr.get("state", "")).lower()
    payload = {"change": change.name, "branch": branch, "status": state, "url": pr.get("url", "")}
    if state == "merged":
        payload["merge_commit"] = (pr.get("mergeCommit") or {}).get("oid", "")
    return payload
