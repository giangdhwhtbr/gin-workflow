"""`gin-workflow describe`: the graph of a bead or epic, collected from Beads (read-only)."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any, Iterable

MAX_NODES = 300
DETAIL_FIELDS = ("description", "design", "acceptance_criteria", "notes", "close_reason", "assignee", "owner",
                 "labels", "created_at", "updated_at", "closed_at", "metadata")


class DescribeError(Exception):
    """A real failure: missing bd, a failing bd call, or an unknown bead."""


class GraphTooLarge(DescribeError):
    def __init__(self, count: int, limit: int) -> None:
        self.count, self.limit = count, limit
        super().__init__(f"graph has more than {limit} nodes (reached {count}); describe a child bead instead")


def _bd(repo: Path, argv: list[str]) -> Any:
    executable = shutil.which("bd")
    if executable is None:
        raise DescribeError("bd is not installed")
    try:
        done = subprocess.run([executable, *argv], cwd=repo, text=True, capture_output=True, check=False,
                              timeout=120)
    except (OSError, subprocess.SubprocessError) as error:
        raise DescribeError(f"bd {argv[0]} failed: {error}") from error
    if done.returncode != 0:
        raise DescribeError(f"bd {' '.join(argv[:2])} failed: {(done.stderr or done.stdout).strip()}")
    try:
        return json.loads(done.stdout or "null")
    except json.JSONDecodeError as error:
        raise DescribeError(f"bd {argv[0]} printed invalid JSON") from error


def _rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        value = [value]
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def _node(row: dict[str, Any], role: str, blockers: list[dict[str, Any]]) -> dict[str, Any]:
    detail: dict[str, Any] = {name: row[name] for name in DETAIL_FIELDS if row.get(name) not in (None, "", [], {})}
    comments = [{"author": item.get("author"), "text": item.get("text"), "created_at": item.get("created_at")}
                for item in _rows(row.get("comments"))]
    if comments:
        detail["comments"] = comments
    if blockers:
        detail["external_blockers"] = sorted(blockers, key=lambda item: item["id"])
    return {"id": row["id"], "title": row.get("title", ""), "type": row.get("issue_type"),
            "status": row.get("status"), "priority": row.get("priority"), "role": role, "detail": detail}


def collect(repo: Path, root_id: str, *, max_nodes: int = MAX_NODES, now: datetime | None = None) -> dict[str, Any]:
    """The root, its parent chain, every descendant, and bugs one `discovered-from` hop away; `blocks` between them."""
    repo = Path(repo)
    issues: dict[str, dict[str, Any]] = {}
    roles: dict[str, str] = {}

    def fetch(ids: Iterable[str], role: str) -> None:
        wanted = sorted(ids)
        if len(issues) + len(wanted) > max_nodes:
            raise GraphTooLarge(len(issues) + len(wanted), max_nodes)
        for row in _rows(_bd(repo, ["show", *wanted, "--json", "--include-comments"])):
            issues[row["id"]] = row
            roles[row["id"]] = role

    def dependents(ids: Iterable[str], kind: str) -> set[str]:
        argv = ["dep", "list", *sorted(ids), "--direction=up", "--type", kind, "--json"]
        return {row["id"] for row in _rows(_bd(repo, argv)) if "id" in row} - set(issues)

    try:
        fetch([root_id], "root")
    except GraphTooLarge:
        raise
    except DescribeError as error:
        if "no issue found" not in str(error):
            raise
    if root_id not in issues:
        raise DescribeError(f"bd show {root_id}: no such bead")

    parent = issues[root_id].get("parent")
    while parent and parent not in issues:
        fetch([parent], "ancestor")
        parent = issues[parent].get("parent") if parent in issues else None

    tree, level = [root_id], [root_id]
    while level:
        level = sorted(dependents(level, "parent-child"))
        if level:
            fetch(level, "descendant")
            tree.extend(level)
    bugs = dependents(tree, "discovered-from")
    if bugs:
        fetch(bugs, "bug")

    edges: set[tuple[str, str, str]] = set()
    outside: dict[str, list[dict[str, Any]]] = {}
    for bead_id, row in issues.items():
        if row.get("parent") in issues:
            edges.add(("parent", row["parent"], bead_id))
        for dep in _rows(row.get("dependencies")):
            kind, source = dep.get("dependency_type"), dep.get("id")
            if kind == "blocks" and source in issues:
                edges.add(("blocks", source, bead_id))
            elif kind == "blocks":
                outside.setdefault(bead_id, []).append(
                    {"id": source, "title": dep.get("title", ""), "status": dep.get("status")})
            elif kind == "discovered-from" and source in issues:
                edges.add(("discovered", source, bead_id))

    stamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"meta": {"root": root_id, "generated_at": stamp, "repo": repo.resolve().name},
            "nodes": [_node(issues[key], roles[key], outside.get(key, [])) for key in sorted(issues)],
            "edges": [{"from": source, "to": target, "kind": kind} for kind, source, target in sorted(edges)]}
