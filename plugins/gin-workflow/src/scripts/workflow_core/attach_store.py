"""Blob stores for gin attach: the Store protocol and the local filesystem store."""

from __future__ import annotations

import os
import re
import tempfile
from collections.abc import Collection
from pathlib import Path
from typing import Protocol


class StoreError(Exception):
    """A store that cannot be read or written."""


_SHA = re.compile(r"[0-9a-f]{64}")
_PATH = re.compile(r"([0-9a-f]{2})/([0-9a-f]{64})")


def blob_path(sha256: str) -> str:
    if not _SHA.fullmatch(sha256):
        raise StoreError(f"{sha256!r} is not a sha256")
    return f"{sha256[:2]}/{sha256}"


def check_path(path: str) -> str:
    match = _PATH.fullmatch(path)
    if not match or not match.group(2).startswith(match.group(1)):
        raise StoreError(f"{path!r} is not a store path")
    return path


class Store(Protocol):
    name: str

    def put(self, sha256: str, data: bytes) -> str: ...

    def get(self, path: str) -> bytes: ...

    def paths(self) -> set[str]: ...

    def remove(self, paths: Collection[str]) -> None: ...

    def push(self) -> str | None: ...

    def fetch(self) -> None: ...


class LocalStore:
    name = "local"

    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)

    def put(self, sha256: str, data: bytes) -> str:
        path = blob_path(sha256)
        target = self.directory / path
        if target.is_file():
            return path
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary = tempfile.mkstemp(dir=target.parent, prefix=".tmp-")
            try:
                with os.fdopen(descriptor, "wb") as handle:
                    handle.write(data)
                os.replace(temporary, target)
            except BaseException:
                Path(temporary).unlink(missing_ok=True)
                raise
        except OSError as error:
            raise StoreError(f"cannot write {target}: {error}") from error
        return path

    def get(self, path: str) -> bytes:
        try:
            return (self.directory / check_path(path)).read_bytes()
        except OSError as error:
            raise StoreError(f"cannot read {path}: {error}") from error

    def paths(self) -> set[str]:
        if not self.directory.is_dir():
            return set()
        found = set()
        for folder in self.directory.iterdir():
            if folder.is_dir():
                for blob in folder.iterdir():
                    try:
                        found.add(check_path(f"{folder.name}/{blob.name}"))
                    except StoreError:
                        continue
        return found

    def remove(self, paths: Collection[str]) -> None:
        checked = [check_path(path) for path in paths]
        for path in checked:
            target = self.directory / path
            target.unlink(missing_ok=True)
            try:
                target.parent.rmdir()
            except OSError:
                pass

    def push(self) -> str | None:
        return None

    def fetch(self) -> None:
        return None
