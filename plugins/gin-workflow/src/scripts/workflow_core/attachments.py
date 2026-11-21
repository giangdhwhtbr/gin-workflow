"""gin attach: images on beads, kept in a shared store and listed in metadata.attachments."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from .attach_store import LocalStore, Store
from .checkout import main_checkout
from .configuration import ConfigValidationError, resolve_effective_config

SCHEME = "attachment:"
DEFAULT_MAX_BYTES = 10 * 1024 * 1024


class AttachmentError(Exception):
    def __init__(self, message: str, code: int = 2) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Settings:
    store: str = "git-ref"
    max_bytes: int = DEFAULT_MAX_BYTES
    retention_days: int | None = None
    s3: Mapping[str, str] = field(default_factory=dict)


def load_settings(repo: Path) -> Settings:
    try:
        config = resolve_effective_config(main_checkout(Path(repo).resolve()), write=False).config.to_dict()
    except ConfigValidationError as error:
        raise AttachmentError(f"invalid configuration: {error}") from error
    section = config.get("attachments") or {}
    settings = Settings(store=section.get("store", "git-ref"),
                        max_bytes=int(section.get("max_bytes", DEFAULT_MAX_BYTES)),
                        retention_days=section.get("retention_days"), s3=dict(section.get("s3") or {}))
    if settings.store == "s3" and not settings.s3.get("bucket"):
        raise AttachmentError("attachments.store is s3 but attachments.s3.bucket is not set")
    return settings


def open_store(repo: Path, settings: Settings) -> Store:
    main = main_checkout(Path(repo).resolve())
    if settings.store == "local":
        return LocalStore(main / ".agent-workflow/attachments")
    if settings.store == "s3":
        from .attach_s3 import S3Store
        return S3Store(**settings.s3)
    from .attach_gitref import GitRefStore
    return GitRefStore(main)
