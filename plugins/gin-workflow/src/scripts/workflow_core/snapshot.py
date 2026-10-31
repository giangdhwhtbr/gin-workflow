"""Installed-snapshot stamp: the plugin src tree hash taken at install time, checked by setup doctor."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

STAMP = ".gin-workflow-src.json"


def tree_hash(src: Path) -> str:
    digest = hashlib.sha256()
    files = [p for p in src.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"]
    for path in sorted(files, key=lambda p: p.relative_to(src).as_posix()):
        digest.update(path.relative_to(src).as_posix().encode() + b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def write_stamp(src: Path, install_dir: Path) -> None:
    src = src.resolve()
    (install_dir / STAMP).write_text(json.dumps({"src": str(src), "sha256": tree_hash(src)}) + "\n", encoding="utf-8")


def check(install_dir: Path) -> str | None:
    """A warning when the stamped src tree changed since install; None when it matches or cannot be checked."""
    try:
        data = json.loads((install_dir / STAMP).read_text(encoding="utf-8"))
        src = Path(data["src"])
        if not src.is_dir() or tree_hash(src) == data.get("sha256"):
            return None
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return f"installed snapshot differs from src ({src}); run ./install.sh"


if __name__ == "__main__":
    write_stamp(Path(sys.argv[1]), Path(sys.argv[2]))
