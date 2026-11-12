"""Epic kind classifier: capability, technical, parity."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Mapping, Sequence

KINDS = ("capability", "technical", "parity")
DEFAULT = "capability"

_KIND_LINE = re.compile(r"^Kind:\s*(\S+)")
_PARITY_LINE = re.compile(r"^Parity with:\s*(.*)$", re.MULTILINE)
_BACKTICKED = re.compile(r"`([^`]+)`")


def spec_kind_line(text: str) -> tuple[str, int] | None:
    r"""The (value, 1-based line number) of the first `^Kind:\s*(\S+)` line outside code fences, or None."""
    fenced = False
    for line_no, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue
        match = _KIND_LINE.match(line)
        if match:
            return match.group(1), line_no
    return None


def spec_kind(text: str) -> str | None:
    r"""The value of the first `^Kind:\s*(\S+)` line outside code fences, or None."""
    found = spec_kind_line(text)
    return found[0] if found else None


def label_kinds(labels: Sequence[str]) -> list[str]:
    """The distinct values of the `kind:<value>` labels, in label order."""
    return list(dict.fromkeys(label[len("kind:"):] for label in labels if label.startswith("kind:")))


def invalid(value: str | None) -> str | None:
    """An error `"Kind: <value> is not one of capability, technical, parity"` for a value outside KINDS, else None."""
    if value is not None and value not in KINDS:
        return f"Kind: {value} is not one of {', '.join(KINDS)}"
    return None


def parity_sources(text: str) -> list[str]:
    """Backticked paths on the `Parity with:` line (empty when absent)."""
    match = _PARITY_LINE.search(text)
    if not match:
        return []
    return _BACKTICKED.findall(match.group(1))


def parity_errors(root: Path, text: str, label: str) -> list[str]:
    """Validate parity sources named on `Parity with:`."""
    from . import specs_assets

    sources = parity_sources(text)
    if not sources:
        return [f"{label}: Kind: parity needs a 'Parity with:' line naming confirmed legacy asset folders"]

    errors: list[str] = []
    for rel_path in sources:
        folder = root / rel_path
        if not folder.is_dir():
            errors.append(f"{label}: Parity with: {rel_path} is missing")
            continue
        desc_file = folder / "description.md"
        if not desc_file.is_file():
            errors.append(f"{label}: Parity with: {rel_path} has no description.md")
            continue
        desc_text = desc_file.read_text(encoding="utf-8")
        kind_val = spec_kind(desc_text)
        if kind_val != "legacy":
            errors.append(f"{label}: Parity with: {rel_path} is not Kind: legacy")
            continue
        confirmed = specs_assets.confirmed_date(desc_text)
        if not confirmed:
            errors.append(f"{label}: Parity with: {rel_path} is not confirmed")
            continue

    return errors


def _kind_source(target: Path) -> Path:
    """The file holding a spec's `Kind:` line: the proposal of an SDD change folder or of a file in one."""
    from .specs import CHANGE_FILES, change_file

    if target.is_dir():
        return change_file(target, "proposal")
    in_change = {CHANGE_FILES["proposal"], CHANGE_FILES["spec-delta"], "proposal.md", "spec-delta.md"}
    return change_file(target.parent, "proposal") if target.name in in_change else target


# bd's message for an id no bead has: `Error fetching <id>: no issue found matching "<id>"`.
_BD_NOT_FOUND = "no issue found matching"
# bd's message in a project without a Beads database.
_BD_NO_DATABASE = "no beads database found"
# tasks.query_result's cause for any failing markdown query.
_MARKDOWN_FAILED = "markdown task query failed"


def _bead_labels(root: Path, workflow_id: str) -> tuple[list[str], str | None]:
    """(labels, None) of the `workflow_id` bead, ([], None) when no bead has that id, or ([], cause) when the tracker
    cannot answer. No bead means bd's not-found; outside team mode (which requires Beads) also bd's missing database;
    or a markdown `show` that fails while `list` still reads the task files (it then fails only on an unknown id)."""
    from . import tasks
    from .team import team_for_repo

    shown, cause = tasks.query_result(root, ["show", workflow_id])
    if cause is None:
        record = shown[0] if isinstance(shown, list) and len(shown) == 1 else shown
        if not isinstance(record, Mapping):
            return [], "unexpected show output"
        return list(record.get("labels") or ()), None
    if _BD_NOT_FOUND in cause or (_BD_NO_DATABASE in cause and team_for_repo(root) is None):
        return [], None
    if cause == _MARKDOWN_FAILED and tasks.query_result(root, ["list", "--limit", "1"])[1] is None:
        return [], None
    return [], cause


def _bead_kind(root: Path, workflow_id: str) -> tuple[str | None, str | None]:
    """(the bead's kind or None, None), or (None, error) when its kind cannot be read or its `kind:` labels are invalid
    or several."""
    labels, cause = _bead_labels(root, workflow_id)
    if cause:
        return None, f"cannot read the kind of epic {workflow_id}: {cause}"
    kinds = label_kinds(labels)
    if len(kinds) > 1:
        return None, f"epic {workflow_id} has several kind labels: {', '.join(kinds)}"
    kind = kinds[0] if kinds else None
    error = invalid(kind)
    return (None, f"epic {workflow_id}: {error}") if error else (kind, None)


def lookup(root: Path, workflow_id: str | None, spec_path: Path | str | None) -> tuple[str, str | None]:
    """(kind, error): the `kind:` label of the `workflow_id` bead, else the `Kind:` line of `spec_path`, else DEFAULT.

    A workflow id that names no bead gives no bead kind. A bead whose kind cannot be read (the tracker fails, or its
    `kind:` labels are invalid or several) gives DEFAULT and the error, never the spec's kind. A mismatch gives the
    bead's kind and an error naming both kinds and the file the spec's `Kind:` was read from."""
    bead = None
    if workflow_id:
        bead, error = _bead_kind(Path(root), workflow_id)
        if error:
            return DEFAULT, error
    spec = None
    source = _kind_source(Path(root) / spec_path) if spec_path else None
    if source is not None and source.is_file():
        spec = spec_kind(source.read_text(encoding="utf-8", errors="replace"))
    if bead and spec and bead != spec:
        shown = source.relative_to(root).as_posix() if source.is_relative_to(Path(root)) else str(source)
        return bead, f"kind mismatch: epic {workflow_id} is kind:{bead}, spec {shown} says Kind: {spec}"
    return bead or spec or DEFAULT, None
