"""Crash-resistant atomic file replacement helpers."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
from typing import Mapping


def _fsync_directory(directory: Path) -> None:
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def atomic_write_bytes(path: Path, content: bytes, *, mode: int = 0o600) -> None:
    """Write bytes using temp-file, fsync, and same-directory replace semantics."""
    atomic_write_many({Path(path): content}, mode=mode)


def atomic_write_text(
    path: Path,
    content: str,
    *,
    encoding: str = "utf-8",
    mode: int = 0o600,
) -> None:
    atomic_write_bytes(Path(path), content.encode(encoding), mode=mode)


def atomic_write_many(files: Mapping[Path, bytes], *, mode: int = 0o600) -> None:
    """Stage every file before replacing any destination.

    This guarantees serialization/staging failures leave all previous outputs
    unchanged. Each final destination is then replaced atomically.
    """
    staged: list[tuple[Path, Path]] = []
    try:
        for raw_path, content in files.items():
            path = Path(raw_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
            )
            temporary = Path(temporary_name)
            try:
                os.fchmod(descriptor, mode)
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
            except BaseException:
                temporary.unlink(missing_ok=True)
                raise
            staged.append((temporary, path))

        touched_directories: set[Path] = set()
        for temporary, path in staged:
            os.replace(temporary, path)
            touched_directories.add(path.parent)
        for directory in touched_directories:
            _fsync_directory(directory)
    finally:
        for temporary, _ in staged:
            temporary.unlink(missing_ok=True)
