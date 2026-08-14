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
    backups: dict[Path, Path | None] = {}
    replaced: list[Path] = []
    preserve_backups = False
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

        for _, path in staged:
            if path.is_symlink():
                raise OSError(f"refusing to replace symbolic link: {path}")
            if not path.exists():
                backups[path] = None
                continue
            descriptor, backup_name = tempfile.mkstemp(
                prefix=f".{path.name}.", suffix=".rollback", dir=path.parent
            )
            backup = Path(backup_name)
            try:
                os.fchmod(descriptor, path.stat().st_mode & 0o777)
                with path.open("rb") as source, os.fdopen(descriptor, "wb") as destination:
                    while chunk := source.read(1024 * 1024):
                        destination.write(chunk)
                    destination.flush()
                    os.fsync(destination.fileno())
            except BaseException:
                backup.unlink(missing_ok=True)
                raise
            backups[path] = backup

        touched_directories: set[Path] = set()
        try:
            for temporary, path in staged:
                os.replace(temporary, path)
                replaced.append(path)
                touched_directories.add(path.parent)
            for directory in touched_directories:
                _fsync_directory(directory)
        except BaseException:
            rollback_error = None
            for path in reversed(replaced):
                backup = backups[path]
                try:
                    if backup is None:
                        path.unlink(missing_ok=True)
                    else:
                        os.replace(backup, path)
                except BaseException as error:
                    rollback_error = rollback_error or error
            for directory in touched_directories:
                try:
                    _fsync_directory(directory)
                except BaseException as error:
                    rollback_error = rollback_error or error
            if rollback_error is not None:
                preserve_backups = True
                recovery = ", ".join(
                    str(backup)
                    for backup in backups.values()
                    if backup is not None and backup.exists()
                )
                raise RuntimeError(
                    f"atomic write failed and rollback was incomplete; recovery backups: {recovery}"
                ) from rollback_error
            raise
    finally:
        for temporary, _ in staged:
            temporary.unlink(missing_ok=True)
        for backup in backups.values():
            if backup is not None and not preserve_backups:
                backup.unlink(missing_ok=True)
