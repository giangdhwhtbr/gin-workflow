"""Epic kind classifier: capability, technical, parity."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Sequence

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


def label_kind(labels: Sequence[str]) -> str | None:
    """The value of the first `kind:<value>` label, or None."""
    for label in labels:
        if label.startswith("kind:"):
            return label[len("kind:"):]
    return None


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
