"""`gin specs trace --all`: every requirement with its changes, sign-off, beads, gin-qa cases, and tests (schema 1)."""

from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any, Mapping, Sequence

from . import signoff
from .events import WorkflowEvent
from .specs import (DELTA_SECTIONS, SpecsError, block_hash, cap_of, change_epic, change_file, changes_dir,
                    delta_blocks, line_value, living_blocks, open_changes, retired_blocks, shown)
from .specs_trace import _tests_md_rows, req_sources
from .tasks import backend, query_result

SCHEMA = 1
_DATED = re.compile(r"^(\d{4}-\d{2}-\d{2})-(.+)$")


def _gin_qa() -> str | None:
    return shutil.which("gin-qa")


def _changes(root: Path, cfg: Mapping[str, Any]) -> tuple[list[tuple[Path, str, str | None]], list[str]]:
    """(folder, change name, archive date or None): every archived change, oldest first, then every open one;
    plus a warning for each archive folder with a spec delta and no date prefix."""
    base = changes_dir(root, cfg) / "archive"
    archived, warnings = [], []
    for folder in (sorted(base.iterdir()) if base.is_dir() else []):
        if not folder.is_dir() or not change_file(folder, "spec-delta").is_file():
            continue
        named = _DATED.match(folder.name)
        if named:
            archived.append((folder, named.group(2), named.group(1)))
        else:
            warnings.append(f"{shown(root, folder)}: archive folder has no YYYY-MM-DD- prefix; skipped")
    return [*archived, *((folder, folder.name, None) for folder in open_changes(root, cfg))], warnings


def _beads(root: Path) -> tuple[list[Mapping[str, Any]] | None, str | None]:
    """Every bead row; (None, None) without Beads, (None, warning) when bd cannot answer."""
    try:
        if backend(root) != "beads":
            return None, None
    except ValueError as error:  # ConfigValidationError: an invalid effective config
        return None, f"beads: {error}"
    rows, cause = query_result(root, ["list", "--all", "--limit", "0"])
    if cause or not isinstance(rows, list):
        return None, f"beads: {cause or 'unexpected bd list output'}"
    return [row for row in rows if isinstance(row, Mapping)], None


def _cases(root: Path) -> tuple[dict[str, list[dict[str, Any]]] | None, str | None]:
    """REQ id -> `{id, effective_result}` of each gin-qa case that pins it; (None, warning) without gin-qa."""
    executable = _gin_qa()
    if executable is None:
        return None, "cases: gin-qa not found on PATH"
    try:
        done = subprocess.run([executable, "cases", "export", "--format", "json", "--repository", str(root)],
                              cwd=root, text=True, capture_output=True, check=False, timeout=300)
    except (OSError, subprocess.SubprocessError) as error:
        return None, f"cases: gin-qa failed: {error}"
    if done.returncode != 0:
        first = next((line.strip() for line in done.stderr.splitlines() if line.strip()), "")
        return None, f"cases: gin-qa exited {done.returncode}" + (f": {first}" if first else "")
    try:
        rows = json.loads(done.stdout)["cases"]
    except (ValueError, KeyError, TypeError) as error:
        return None, f"cases: unreadable gin-qa output: {error}"
    if not isinstance(rows, list):
        return None, "cases: unreadable gin-qa output: cases is not a list"
    found: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        for ref in row.get("reqs") or ():
            if not isinstance(ref, Mapping):
                continue
            found.setdefault(str(ref.get("id")), []).append(
                {"id": row.get("id"), "effective_result": row.get("effective_result")})
    return found, None


def _signoff(root: Path, folder: Path, archived: str | None, epic: str | None,
             beads_by_id: Mapping[str, Mapping[str, Any]], events: Sequence[WorkflowEvent],
             warnings: list[str]) -> signoff.Signoff | None:
    """A change's sign-off: its `06-signoff.md` when archived, else (or when that file is malformed) its epic's."""
    path = folder / signoff.SIGNOFF_FILE
    if archived is not None and path.is_file():
        try:
            return signoff.read_file(path)
        except (OSError, UnicodeDecodeError, ValueError) as error:
            warnings.append(f"{shown(root, path)}: {error}")
    if epic is None:
        return None
    return signoff.epic_signoff(signoff.bead_gates(beads_by_id.get(epic)), events, epic)


def _row(req_id: str, title: str, state: str, digest: str | None, source: str | None,
         reason: str | None = None) -> dict[str, Any]:
    return {"id": req_id, "title": title, "capability": cap_of(req_id), "state": state, "hash8": digest,
            "source": source, "reason": reason, "changes": []}


def _current(signed: str | None, now: str | None) -> bool | None:
    return None if signed is None or now is None else signed == now


def trace_all(root: Path, cfg: Mapping[str, Any]) -> dict[str, Any]:
    """Every living, proposed, and removed requirement with its changes, sign-off, beads, cases, and tests."""
    if cfg["layout"] != "sdd":
        return {"schema": SCHEMA, "layout": cfg["layout"], "requirements": [], "warnings": [], "skipped": []}
    events, event_warning = signoff.load_events(root)
    beads, bead_warning = _beads(root)
    cases, case_warning = _cases(root)
    warnings = [warning for warning in (event_warning, bead_warning, case_warning) if warning]
    beads_by_id = {str(row.get("id")): row for row in beads or ()}
    changes = []
    listed, folder_warnings = _changes(root, cfg)
    warnings += folder_warnings
    for folder, name, archived in listed:
        blocks, errors = delta_blocks(root, folder)
        warnings += errors
        blocks = [block for block in blocks if block.section in DELTA_SECTIONS]
        try:
            epic: str | None = change_epic(folder)
        except SpecsError:  # a proposal without an `Epic:` line names no sign-off
            epic = None
        found = _signoff(root, folder, archived, epic, beads_by_id, events, warnings)
        changes.append((folder, name, archived, epic, blocks, found))
    rows = {req_id: _row(req_id, block.title, "living", block_hash(block.text)[:8],
                         f"{shown(root, path)}:{block.start + 1}")
            for req_id, (path, block) in living_blocks(root, cfg).items()}
    for folder, _, archived, _, blocks, _ in changes:
        for block in blocks:
            if archived is None and block.section == "ADDED" and block.id not in rows:
                rows[block.id] = _row(block.id, block.title, "proposed", block_hash(block.text)[:8],
                                      f"{shown(root, change_file(folder, 'spec-delta'))}:{block.start + 1}")
    for req_id, (_, block) in retired_blocks(root, cfg).items():
        if req_id not in rows:
            rows[req_id] = _row(req_id, block.title, "removed", None, None, line_value(block.text, "Reason") or None)
    for _, _, archived, _, blocks, _ in changes:
        for block in blocks:
            if archived is not None and block.section == "REMOVED" and block.id not in rows:
                rows[block.id] = _row(block.id, block.title, "removed", None, None,
                                      line_value(block.text, "Reason") or None)
    for _, name, archived, epic, blocks, found in changes:
        for block in blocks:
            if block.id in rows:
                rows[block.id]["changes"].append({"change": name, "epic": epic, "op": block.section.lower(),
                                                  "archived": archived,
                                                  "signoff": found.as_json(block.id) if found else None})
    tests, skipped = req_sources(root, cfg, rows)
    for folder, *_ in changes:
        tests_md = change_file(folder, "tests")
        for case, ids, evidence in _tests_md_rows(tests_md):
            if evidence and evidence != "-":
                for req_id in ids & rows.keys():
                    tests[req_id].append(f"{shown(root, tests_md)}#{case}")
    for req_id, row in rows.items():
        last = next((entry for entry in reversed(row["changes"]) if entry["signoff"]), None)
        row["signoff"] = None if last is None else {**last["signoff"], "change": last["change"],
                                                    "current": _current(last["signoff"]["hash8"], row["hash8"])}
        row["beads"] = None if beads is None else sorted(
            ({"id": str(bead.get("id")), "title": bead.get("title", ""), "status": bead.get("status", "")}
             for bead in beads if f"req:{req_id}" in (bead.get("labels") or ())), key=lambda bead: bead["id"])
        row["cases"] = None if cases is None else sorted(cases.get(req_id, []), key=lambda item: str(item["id"]))
        row["tests"] = sorted(tests[req_id])
    return {"schema": SCHEMA, "layout": "sdd", "requirements": [rows[req_id] for req_id in sorted(rows)],
            "warnings": warnings, "skipped": skipped}


def _count(items: list[Any] | None) -> str:
    return "-" if items is None else str(len(items))


def text_line(row: Mapping[str, Any]) -> str:
    """`<id> <state> signoff:<yes|stale|waived|no> beads:<n|-> cases:<n|-> tests:<n>`."""
    found = row["signoff"]
    state = ("no" if found is None else "waived" if found["waived"] else "stale" if found["current"] is False
             else "yes")
    return (f"{row['id']} {row['state']} signoff:{state} beads:{_count(row['beads'])} "
            f"cases:{_count(row['cases'])} tests:{len(row['tests'])}")
