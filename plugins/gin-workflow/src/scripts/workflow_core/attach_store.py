"""Blob stores for gin attach: the Store protocol and the local filesystem store."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Collection
from pathlib import Path
from typing import Protocol


class StoreError(Exception):
    """A store that cannot be read or written."""


def blob_path(sha256: str) -> str:
    return f"{sha256[:2]}/{sha256}"


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
            return (self.directory / path).read_bytes()
        except OSError as error:
            raise StoreError(f"cannot read {path}: {error}") from error

    def paths(self) -> set[str]:
        if not self.directory.is_dir():
            return set()
        return {
            f"{folder.name}/{blob.name}"
            for folder in self.directory.iterdir() if folder.is_dir()
            for blob in folder.iterdir() if blob.is_file() and not blob.name.startswith(".tmp-")
        }

    def remove(self, paths: Collection[str]) -> None:
        for path in paths:
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
