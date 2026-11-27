"""`gin specs gaps`: requirement ids that were used and are gone without a `## Retired` entry."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from .atomic import atomic_write_many
from .specs import (_CAP, _FULL_ID, Block, SpecsError, _git, _local_ids, append_to_section, cap_of, change_file,
                    changes_dir, delta_blocks, history_ids, ids_at_ref, line_value, shown)

UNKNOWN_TITLE = "(title not found)"


def _present(root: Path, cfg: Mapping[str, Any]) -> set[str]:
    """Ids on a heading of a living spec or an open change, in this tree, every worktree, and every remote-tracking
    branch; archived changes are left out, so an id only they hold is gone."""
    ids = _local_ids(root, cfg, archived=False)
    for line in _git(root, "worktree", "list", "--porcelain").stdout.splitlines():
        if line.startswith("worktree "):
            ids |= _local_ids(Path(line[len("worktree "):]), cfg, archived=False)
    archive = Path(cfg["changes"]) / "archive"
    for ref in _git(root, "for-each-ref", "--format=%(refname)", "refs/remotes").stdout.split():
        if not ref.endswith("/HEAD"):
            ids |= ids_at_ref(root, cfg, ref, exclude=archive)
    return ids


def _archived_removals(root: Path, cfg: Mapping[str, Any]) -> dict[str, tuple[str, Block]]:
    """The REMOVED blocks of archived changes by id: (archived folder name, block); the newest folder wins."""
    archive = changes_dir(root, cfg) / "archive"
    found: dict[str, tuple[str, Block]] = {}
    for folder in sorted(p for p in archive.iterdir() if p.is_dir()) if archive.is_dir() else []:
        for block in delta_blocks(root, folder)[0]:
            if block.section == "REMOVED":
                found[block.id] = (folder.name, block)
    return found


def _last_commit(root: Path, cfg: Mapping[str, Any], req_id: str) -> dict[str, str] | None:
    """The newest commit that added or deleted the heading of `req_id`, with the title the heading had."""
    log = _git(root, "log", "--all", "-1", "-p", "--unified=0", "--format=%x00%h%x09%cs%x09%s",
               "-G", f"^### {re.escape(req_id)}:", "--", cfg["specs"], cfg["changes"])
    if log.returncode != 0 or "\x00" not in log.stdout:
        return None
    header, _, patch = log.stdout.split("\x00", 1)[1].partition("\n")
    commit, day, subject = (header.split("\t", 2) + ["", ""])[:3]
    title = re.search(rf"^[+-]### {re.escape(req_id)}: (\S.*)$", patch, re.MULTILINE)
    return {"commit": commit, "date": day, "subject": subject, "title": title.group(1).strip() if title else ""}


def _order(req_id: str) -> tuple[str, int]:
    prefix, number = _FULL_ID.match(req_id).groups()
    return prefix, int(number)


def gaps(root: Path, cfg: Mapping[str, Any], cap: str | None = None) -> dict[str, Any]:
    """Each id that history or an archived change used and that no living spec, open change, or retired entry
    holds now, per capability in id order, with a hint: the archived REMOVED block, or the last commit."""
    if cap is not None and not _CAP.match(cap):
        raise SpecsError(f"capability {cap!r} must match [a-z][a-z0-9-]*")
    found, warnings = history_ids(root, cfg)
    removals = _archived_removals(root, cfg)
    rows = []
    for req_id in sorted((_local_ids(root, cfg) | found) - _present(root, cfg), key=_order):
        if cap is not None and cap_of(req_id) != cap:
            continue
        if req_id in removals:
            name, block = removals[req_id]
            rows.append({"id": req_id, "title": block.title, "reason": line_value(block.text, "Reason"),
                         "change": name, "commit": None})
        else:
            commit = _last_commit(root, cfg, req_id)
            rows.append({"id": req_id, "title": (commit or {}).get("title") or UNKNOWN_TITLE, "reason": "",
                         "change": None, "commit": commit})
    return {"gaps": rows, "warnings": warnings}


def write_into(root: Path, change: Path, rows: Sequence[Mapping[str, Any]]) -> list[str]:
    """Append one `## RETIRED` block per row to the change's spec delta; an unknown reason leaves `Reason:` empty,
    which lint refuses until someone writes it. Returns the ids written."""
    path = change_file(change, "spec-delta")
    if not path.is_file():
        raise SpecsError(f"{shown(root, path)}: missing {path.name}")
    entries = [[f"### {row['id']}: {row['title']}", f"Reason: {row['reason']}".rstrip()] for row in rows]
    lines = append_to_section(path.read_text(encoding="utf-8").splitlines(), "RETIRED", entries)
    if entries:
        atomic_write_many({path: ("\n".join(lines).rstrip() + "\n").encode("utf-8")}, mode=0o644)
    return [row["id"] for row in rows]


def text_line(row: Mapping[str, Any]) -> str:
    """`<id> removed by <change>: <reason>` or `<id> deleted in <commit> <date> <subject>: <title>`."""
    if row["change"]:
        return f"{row['id']} removed by {row['change']}: {row['reason']}"
    commit = row["commit"]
    if commit is None:
        return f"{row['id']} not found in history: {row['title']}"
    return f"{row['id']} deleted in {commit['commit']} {commit['date']} {commit['subject']}: {row['title']}"
