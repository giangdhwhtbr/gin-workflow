"""Read the two roadmap lines `gin milestone list` uses: `- Deadline:` and the number that starts `- AI capacity:`."""

from __future__ import annotations

from pathlib import Path
import re

from .milestone import Roadmap, parse_date
from .team import ROADMAP

_DEADLINE = re.compile(r"^- Deadline:[ \t]*(\S+)", re.MULTILINE)
_CAPACITY = re.compile(r"^- AI capacity:[ \t]*(\d+)", re.MULTILINE)


def read_roadmap(root: Path, layout: str) -> Roadmap:
    """Never raises: a missing file or line gives None; a malformed deadline fills `error`."""
    path = Path(root) / ROADMAP.get(layout, ROADMAP["legacy"])
    if not path.is_file():
        return Roadmap()
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        return Roadmap(error=f"roadmap file unreadable: {error}")
    capacity = _CAPACITY.search(text)
    lanes = int(capacity.group(1)) if capacity and int(capacity.group(1)) > 0 else None
    deadline = _DEADLINE.search(text)
    if deadline is None:
        return Roadmap(None, lanes, None)
    try:
        return Roadmap(parse_date(deadline.group(1)), lanes, None)
    except ValueError:
        return Roadmap(None, lanes, f"Deadline: {deadline.group(1)} is not a date (YYYY-MM-DD)")
