"""Print one release section of the changelog, for the GitHub release notes.

Usage: python3 scripts/release_notes.py X.Y.Z [--file PATH]

The version has no leading "v". The default file is docs/changelog.md.
"""

from __future__ import annotations

from pathlib import Path
import re
import sys

VERSION_RE = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")
FENCE_RE = re.compile(r"^ {0,3}(```|~~~)")
DEFAULT_FILE = Path(__file__).resolve().parents[1] / "docs" / "changelog.md"


def section(text: str, version: str) -> str:
    """The lines after the heading `## [version]` up to the next `## [` heading, stripped."""
    if not VERSION_RE.fullmatch(version):
        raise ValueError(f"not a version X.Y.Z: {version!r}")
    heading = re.compile(rf"^## \[{re.escape(version)}\](?:\s|$)")
    body: list[str] = []
    found = False
    fenced = False
    for line in text.splitlines():
        if FENCE_RE.match(line):
            fenced = not fenced
        elif not fenced and line.startswith("## ["):
            if found:
                break
            found = bool(heading.match(line))
            continue
        if found:
            body.append(line)
    notes = "\n".join(body).strip()
    if not notes:
        raise ValueError(f"docs/changelog.md has no section for {version}")
    return notes


def main(argv: list[str]) -> int:
    path = DEFAULT_FILE
    args = list(argv)
    if len(args) == 3 and args[1] == "--file":
        path = Path(args[2])
        args = args[:1]
    try:
        if len(args) != 1:
            raise ValueError("usage: release_notes.py X.Y.Z [--file PATH]")
        notes = section(path.read_text(encoding="utf-8"), args[0])
    except (ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(notes)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
