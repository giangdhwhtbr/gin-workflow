"""SRS document matter as data: revision history, glossary, actor catalogue, traceability matrix."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Mapping

from . import specs
from .specs_trace import req_sources

_DATED = re.compile(r"^(\d{4}-\d{2}-\d{2})-(.+)$")
_TITLE = re.compile(r"^# (\S.*)$", re.MULTILINE)
_TERMS = re.compile(r"^## Terms[ \t]*\n(.*?)(?=^## |\Z)", re.MULTILINE | re.DOTALL)
_CASE_ID = re.compile(r"^(TC-[A-Z][A-Z0-9-]*?-\d{3,})")


def revisions(root: Path, cfg: Mapping[str, Any], cap: str | None = None) -> list[dict[str, Any]]:
    """One row per archived change folder `<date>-<name>`, newest first; with `cap`, only changes touching it."""
    archive = specs.changes_dir(root, cfg) / "archive"
    rows = []
    for folder in sorted((p for p in archive.iterdir() if p.is_dir()), reverse=True) if archive.is_dir() else []:
        dated = _DATED.match(folder.name)
        if not dated:
            continue
        proposal = specs.change_file(folder, "proposal")
        text = specs._COMMENT.sub("", specs.read_text_or_none(proposal) or "")
        epic, title = specs._EPIC_LINE.search(text), _TITLE.search(text)
        delta = specs.change_file(folder, "spec-delta")
        blocks = specs.parse_blocks(specs.read_text_or_none(delta) or "")[0]
        caps = sorted({block.cap for block in blocks})
        if cap and cap not in caps:
            continue
        rows.append({"date": dated.group(1), "epic": epic.group(1) if epic else "",
                     "title": title.group(1).strip() if title else dated.group(2), "capabilities": caps,
                     **{section.lower(): sorted(b.id for b in blocks if b.section == section)
                        for section in specs.DELTA_SECTIONS}})
    return rows


def glossary(root: Path, cfg: Mapping[str, Any]) -> list[dict[str, str]]:
    """The `confirmed` rows of `## Terms` in `<codebase>/11-GLOSSARY.md`, sorted by English."""
    path = Path(root) / cfg["codebase"] / "11-GLOSSARY.md"
    section = _TERMS.search(specs.read_text_or_none(path) or "")
    table = specs.table_rows(section.group(1)) if section else None
    rows = [{"english": row.get("English", ""), "term": row.get("Term", ""), "lang": row.get("Lang", ""),
             "meaning": row.get("Meaning", "")}
            for _, row in (table[1] if table else []) if row.get("Status", "").lower() == "confirmed"]
    return sorted(rows, key=lambda row: row["english"].casefold())


def actors(root: Path, cfg: Mapping[str, Any], cap: str | None = None) -> list[dict[str, Any]]:
    """Each actor of the use cases with its description from `<specs>/actors.md` and its use cases."""
    base = specs.specs_dir(root, cfg)
    found: dict[str, dict[str, Any]] = {}
    for path in sorted(base.glob(f"*/{specs.USE_CASES_DIR}/*.md")):
        owner = path.parent.parent.name
        if cap and owner != cap:
            continue
        text = specs.read_text_or_none(path)
        if text is None:
            continue
        primary = specs.line_value(text, "Actor")
        names = ([(primary, False)] if primary else []) + [(n, True) for n in specs.line_values(text, "Secondary actors")]
        counted: set[str] = set()
        for name, secondary in names:
            key = specs.actor_key(name)
            if key in counted:
                continue
            counted.add(key)
            row = found.setdefault(key, {"actor": " ".join(name.split()), "description": "", "use_cases": []})
            row["use_cases"].append({"ref": f"{owner}/{path.stem}", "secondary": secondary})
    listed = base / specs.ACTORS_FILE
    table = specs.table_rows(specs.read_text_or_none(listed) or "")
    for _, row in (table[1] if table else []):
        if row.get("Actor") and specs.actor_key(row["Actor"]) in found:
            found[specs.actor_key(row["Actor"])]["description"] = row.get("Description", "")
    return sorted(found.values(), key=lambda row: row["actor"].casefold())


def qa_cases_dir(root: Path) -> Path | None:
    """`qa.cases` when set, else `<qa.dir or qa>/cases`, under the project root; None when it leaves the repository.
    It loads the config again because `sdd_config` drops `qa`."""
    qa = specs.load_config(root).get("qa") or {}
    folder = (Path(root) / (qa["cases"] if "cases" in qa else f"{qa.get('dir', 'qa')}/cases")).resolve()
    return folder if folder.is_relative_to(Path(root).resolve()) else None


def _id_order(req_id: str) -> tuple[str, int]:
    prefix, number = specs._FULL_ID.match(req_id).groups()
    return prefix, int(number)


def _living(root: Path, cfg: Mapping[str, Any], cap: str | None, kind: str) -> list[specs.Block]:
    return sorted((block for _, block in specs.living_blocks(root, cfg).values()
                   if specs.type_of(block) == kind and (cap is None or block.cap == cap)),
                  key=lambda block: (block.cap, _id_order(block.id)))


def nonfunctional(root: Path, cfg: Mapping[str, Any], cap: str | None = None) -> list[dict[str, str]]:
    """Non-functional living requirements by category order, then capability and number."""
    rank = {name: index for index, name in enumerate(specs.NFR_CATEGORIES)}
    blocks = sorted(_living(root, cfg, cap, "non-functional"),
                    key=lambda block: rank.get(block.category, len(rank)))
    return [{"id": b.id, "title": b.title, "capability": b.cap, "category": b.category, "measure": b.measure}
            for b in blocks]


def business_rules(root: Path, cfg: Mapping[str, Any], cap: str | None = None) -> list[dict[str, Any]]:
    """Business-rule living requirements with their statement and the use cases citing them."""
    blocks = _living(root, cfg, cap, "business-rule")
    ids = {block.id for block in blocks}
    citing: dict[str, list[str]] = {req: [] for req in ids}
    for path in sorted(specs.specs_dir(root, cfg).glob(f"*/{specs.USE_CASES_DIR}/*.md")):
        text = specs.read_text_or_none(path)
        for req in set(specs.line_values(text or "", "Requirements")) & ids:
            citing[req].append(f"{path.parent.parent.name}/{path.stem}")
    return [{"id": b.id, "title": b.title, "capability": b.cap, "statement": specs.statement(b),
             "use_cases": citing[b.id]} for b in blocks]


def traceability(root: Path, cfg: Mapping[str, Any], cap: str | None = None) -> list[dict[str, Any]]:
    """One row per living requirement: its use cases, the test files and QA cases citing it, and coverage."""
    blocks = sorted((block for _, block in specs.living_blocks(root, cfg).values() if cap is None or block.cap == cap),
                    key=lambda block: (block.cap, _id_order(block.id)))
    ids = {block.id for block in blocks}
    use_cases: dict[str, list[str]] = {req: [] for req in ids}
    for path in sorted(specs.specs_dir(root, cfg).glob(f"*/{specs.USE_CASES_DIR}/*.md")):
        for req in set(specs.line_values(specs.read_text_or_none(path) or "", "Requirements")) & ids:
            use_cases[req].append(f"{path.parent.parent.name}/{path.stem}")
    tests = req_sources(root, cfg, ids)[0]
    qa: dict[str, list[str]] = {req: [] for req in ids}
    folder = qa_cases_dir(root)
    for path in sorted(folder.rglob("*.md")) if folder and folder.is_dir() else []:
        case = _CASE_ID.match(path.name)
        text = specs.read_text_or_none(path) if case else None
        if text is None:
            continue
        for req in {match.group(0) for match in specs.REQ_ID.finditer(text)} & ids:
            qa[req].append(case.group(1))
    return [{"id": block.id, "title": block.title, "capability": block.cap,
             "type": specs.type_of(block), "use_cases": use_cases[block.id],
             "tests": tests[block.id], "qa_cases": sorted(set(qa[block.id])),
             "status": "covered" if tests[block.id] or qa[block.id] else "missing"} for block in blocks]
