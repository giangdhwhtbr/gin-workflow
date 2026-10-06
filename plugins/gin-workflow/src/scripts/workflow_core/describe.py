"""`gin-workflow describe`: the graph of a bead or epic, collected from Beads (read-only)."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any, Iterable

from .specs import SpecsError, plugin_templates_dir

MAX_NODES = 300
PLACEHOLDER = "/*__DESCRIBE_DATA__*/"
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
            if row.get("id"):
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
        if "no issue found" not in str(error) and "not found" not in str(error).lower():
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
            if not source:
                continue
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


def layout(graph: dict[str, Any]) -> dict[str, Any]:
    """Tidy tree: root on row 0, ancestors above it, a bug under its smallest discoverer; leaves take next slots."""
    nodes = {node["id"]: node for node in graph["nodes"]}
    root = graph["meta"]["root"]
    tree_parent = {edge["to"]: edge["from"] for edge in graph["edges"] if edge["kind"] == "parent"}
    owner: dict[str, str] = {}
    for bead_id, node in nodes.items():
        if node["role"] == "descendant":
            owner[bead_id] = tree_parent.get(bead_id, root)
        elif node["role"] == "bug":
            found = sorted(edge["from"] for edge in graph["edges"]
                           if edge["kind"] == "discovered" and edge["to"] == bead_id
                           and nodes[edge["from"]]["role"] in ("root", "descendant"))
            owner[bead_id] = found[0] if found else root
    children: dict[str, list[str]] = {}
    for bead_id in sorted(owner, key=lambda key: (nodes[key]["role"] == "bug", key)):
        children.setdefault(owner[bead_id], []).append(bead_id)

    seen: set[str] = set()
    slot = 0

    def place(bead_id: str, row: int) -> None:
        nonlocal slot
        seen.add(bead_id)
        nodes[bead_id]["y"] = row
        placed = []
        for child in children.get(bead_id, []):
            if child not in seen:
                place(child, row + 1)
                placed.append(child)
        if placed:
            nodes[bead_id]["x"] = (nodes[placed[0]]["x"] + nodes[placed[-1]]["x"]) / 2
        else:
            nodes[bead_id]["x"] = float(slot)
            slot += 1

    place(root, 0)
    for bead_id in sorted(owner):  # corrupt data only: a parent cycle that never reaches the root
        if bead_id not in seen:
            place(bead_id, 1)
    row, current = -1, root
    while tree_parent.get(current) in nodes and nodes[tree_parent[current]]["role"] == "ancestor" and tree_parent[current] not in seen:
        current = tree_parent[current]
        seen.add(current)
        nodes[current]["y"], nodes[current]["x"] = row, nodes[root]["x"]
        row -= 1
    return graph


def template() -> str:
    try:
        return (plugin_templates_dir() / "describe.html").read_text(encoding="utf-8")
    except (SpecsError, OSError) as error:
        raise DescribeError(f"describe template unavailable: {error}") from error


def render(graph: dict[str, Any], template_text: str) -> str:
    """Embed the graph as JSON; `<`, `>`, `&` are escaped so bead text can never close the script element."""
    if template_text.count(PLACEHOLDER) != 1:
        raise DescribeError("describe template must contain the data placeholder once")
    payload = json.dumps(graph, ensure_ascii=False, sort_keys=True)
    for char, escaped in (("&", "\\u0026"), ("<", "\\u003c"), (">", "\\u003e"),
                          ("\u2028", "\\u2028"), ("\u2029", "\\u2029")):
        payload = payload.replace(char, escaped)
    return template_text.replace(PLACEHOLDER, payload)
