"""Requirement sign-off of a change: the requirement list a gate records, where a sign-off is read from, and the
`06-signoff.md` file that archive writes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from .checkout import main_checkout
from .events import EventPersistenceError, WorkflowEvent, WorkflowEventStore
from .specs import (DELTA_SECTIONS, Block, SpecsError, block_hash, change_epic, delta_blocks, line_value, load_config,
                    open_changes, sdd_config)
from .waivers import WAIVER_EVENT_TYPE

SIGNOFF_FILE = "06-signoff.md"
_ROW = re.compile(r"^\|\s*(REQ-[A-Z][A-Z0-9-]*-\d{3,})\s*\|\s*([0-9a-f]{8})\s*\|\s*(added|modified|removed)\s*\|\s*$")


@dataclass(frozen=True)
class Signoff:
    """A change's sign-off: when, by whom, on what evidence, and the requirement hashes it covered."""

    at: str
    actor: str
    evidence: str
    source: str  # git, beads, or events
    requirements: tuple[tuple[str, str, str], ...] | None  # (id, hash8, op); None when the record lists none
    waived: bool = False

    def hash_of(self, req_id: str) -> str | None:
        return next((pinned for item, pinned, _ in self.requirements or () if item == req_id), None)

    def as_json(self, req_id: str) -> dict[str, Any]:
        return {"at": self.at, "actor": self.actor, "evidence": self.evidence, "hash8": self.hash_of(req_id),
                "source": self.source, "waived": self.waived}


def hash8(block: Block) -> str:
    """The hash a sign-off pins, 8 hex: the living block's base for a REMOVED block, else the block's own hash."""
    return (block.base if block.section == "REMOVED" and block.base else block_hash(block.text))[:8]


def change_requirements(root: Path, change: Path) -> list[dict[str, str]]:
    """`{id, hash8, op}` for each block of the change's spec delta, in file order."""
    blocks, _ = delta_blocks(root, change)  # malformed blocks are findings of `specs lint`; they are left out here
    return [{"id": block.id, "hash8": hash8(block), "op": block.section.lower()}
            for block in blocks if block.section in DELTA_SECTIONS]


def requirements_of(root: Path, workflow_id: str) -> list[dict[str, str]] | None:
    """The requirement list of a `requirement.confirmed` event: the delta rows of each open change whose proposal
    says `Epic: <workflow_id>`, with the SDD layout; None without setup, the SDD layout, or such a change."""
    try:
        cfg = sdd_config(load_config(root))
    except ValueError:  # SpecsError (no setup) and ConfigValidationError (invalid config) both derive from it
        return None
    if cfg["layout"] != "sdd":
        return None
    found: list[dict[str, str]] | None = None
    for change in open_changes(root, cfg):
        try:
            rows = change_requirements(root, change) if change_epic(change) == workflow_id else None
        except (SpecsError, OSError, UnicodeDecodeError):  # no `Epic:` line, or an unreadable proposal or delta
            continue
        if rows is not None:
            found = [*(found or []), *rows]
    return found


def _requirements(value: Any) -> tuple[tuple[str, str, str], ...] | None:
    """A stored `requirements` list (an event payload is frozen into a tuple); None when absent."""
    if not isinstance(value, (list, tuple)):
        return None
    return tuple((str(item["id"]), str(item["hash8"]), str(item["op"])) for item in value
                 if isinstance(item, Mapping) and item.get("id") and item.get("hash8") and item.get("op"))


def from_gates(gates: Mapping[str, Any]) -> Signoff | None:
    """The `requirement_confirmed` proof of an epic bead's `gates` metadata; a shared waiver is a waived sign-off."""
    proof = gates.get("requirement_confirmed")
    if not isinstance(proof, Mapping):
        return None
    if proof.get("waived"):
        return Signoff(at=str(proof.get("at") or ""), actor=str(proof.get("waived_by") or ""),
                       evidence=str(proof.get("reason") or ""), source="beads", requirements=None, waived=True)
    return Signoff(at=str(proof.get("at") or ""), actor=str(proof.get("actor") or ""),
                   evidence=str(proof.get("pr_url") or ""), source="beads",
                   requirements=_requirements(proof.get("requirements")))


def from_events(events: Sequence[WorkflowEvent], epic: str) -> Signoff | None:
    """The epic's newest local `requirement.confirmed` event, else its newest `requirement_confirmed` waiver."""
    mine = [event for event in events if event.workflow_id == epic and isinstance(event.payload, Mapping)]
    confirmed = [event for event in mine if event.event_type == "requirement.confirmed"]
    if confirmed:
        event = confirmed[-1]
        return Signoff(at=event.timestamp, actor=event.actor or "", evidence=str(event.payload.get("evidence") or ""),
                       source="events", requirements=_requirements(event.payload.get("requirements")))
    waived = [event for event in mine
              if event.event_type == WAIVER_EVENT_TYPE and event.payload.get("gate") == "requirement_confirmed"]
    if waived:
        event = waived[-1]
        return Signoff(at=event.timestamp, actor=str(event.payload.get("waived_by") or event.actor or ""),
                       evidence=str(event.payload.get("reason") or ""), source="events", requirements=None,
                       waived=True)
    return None


def epic_signoff(gates: Mapping[str, Any], events: Sequence[WorkflowEvent], epic: str) -> Signoff | None:
    """An epic's sign-off: its bead's `gates`, then its newest local event, then its waiver."""
    return from_gates(gates) or from_events(events, epic)


def bead_gates(row: Mapping[str, Any] | None) -> dict[str, Any]:
    """The `gates` metadata of a bead row; {} without a row."""
    from .team_beads import gates_of

    return gates_of(row) if isinstance(row, Mapping) else {}


def load_gates(root: Path, epic: str) -> tuple[dict[str, Any], str | None]:
    """The epic bead's `gates`: ({}, None) without Beads, ({}, warning) when the tracker cannot answer."""
    from .tasks import backend, query_result

    try:
        if backend(root) != "beads":
            return {}, None
    except ValueError as error:  # ConfigValidationError: an invalid effective config
        return {}, f"bead {epic} unreadable: {error}"
    shown, cause = query_result(root, ["show", epic])
    if cause:
        return {}, f"bead {epic} unreadable: {cause}"
    return bead_gates(shown[0] if isinstance(shown, list) and shown else shown), None


def load_events(root: Path) -> tuple[list[WorkflowEvent], str | None]:
    """The main checkout's event log: ([], None) without one, ([], warning) when it cannot be read."""
    path = main_checkout(Path(root)) / ".agent-workflow" / "runtime" / "events.jsonl"
    if not path.is_file():
        return [], None
    try:
        return WorkflowEventStore(path).read_all(), None
    except (EventPersistenceError, OSError, ValueError) as error:
        return [], f"event log unreadable: {error}"


def render(found: Signoff, epic: str, rows: Sequence[Mapping[str, str]], *, hashes_at_archive: bool = False) -> str:
    """The text of `06-signoff.md`."""
    if found.waived:
        head = [f"Waived: {found.evidence}", f"By: {found.actor}", f"At: {found.at}"]
    else:
        head = [f"Signed off: {found.at}", f"By: {found.actor}", f"Evidence: {found.evidence}"]
    lines = ["# Sign-off", "", f"Epic: {epic}", *head, f"Source: {found.source}"]
    if hashes_at_archive:
        lines.append("Hashes: at archive")
    lines += ["", "| Requirement | hash8 | op |", "|---|---|---|",
              *(f"| {row['id']} | {row['hash8']} | {row['op']} |" for row in rows)]
    return "\n".join(lines) + "\n"


def read_file(path: Path) -> Signoff:
    """A `06-signoff.md` as a sign-off from git; ValueError when a required line or every row is missing."""
    text = Path(path).read_text(encoding="utf-8")
    rows = tuple((found.group(1), found.group(2), found.group(3))
                 for found in map(_ROW.match, text.splitlines()) if found)
    waived, signed, actor = line_value(text, "Waived"), line_value(text, "Signed off"), line_value(text, "By")
    if not actor or not (waived or signed) or not rows:
        raise ValueError("needs a By: line, a Signed off: or Waived: line, and at least one requirement row")
    if waived:
        return Signoff(at=line_value(text, "At"), actor=actor, evidence=waived, source="git", requirements=rows,
                       waived=True)
    return Signoff(at=signed, actor=actor, evidence=line_value(text, "Evidence"), source="git", requirements=rows)
