"""gin attach: images on beads, kept in a shared store and listed in metadata.attachments."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any

from . import team
from .attach_images import EXTENSIONS, clean, sniff
from .attach_store import LocalStore, Store, StoreError, blob_path
from .checkout import main_checkout
from .configuration import ConfigValidationError, resolve_effective_config
from .executables import tool

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


def _bd(repo: Path, argv: Sequence[str]) -> Any:
    from .tasks import backend

    try:
        name = backend(repo)
    except ConfigValidationError as error:
        raise AttachmentError(f"invalid configuration: {error}") from error
    if name == "markdown":
        raise AttachmentError("gin attach needs Beads (providers.task_tracking: beads)")
    executable = tool("bd", repo)
    if executable is None:
        raise AttachmentError("bd is not installed")
    completed = subprocess.run([executable, *argv], cwd=repo, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise AttachmentError(f"bd {' '.join(argv)} failed: {completed.stderr.strip()}")
    return json.loads(completed.stdout) if "--json" in argv else completed.stdout


def _show(repo: Path, bead: str) -> dict[str, Any]:
    if not bead or bead.startswith("-"):
        raise AttachmentError(f"invalid bead id: {bead!r}")
    data = _bd(repo, ["show", "--json", "--", bead])
    row = data[0] if isinstance(data, list) and data else data
    if not isinstance(row, dict) or not row:
        raise AttachmentError(f"{bead}: no such bead")
    return row


def _held(bead: str, row: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The bead's entries; corrupt `metadata.attachments` raises instead of reading as empty."""
    metadata = row.get("metadata")
    value = metadata.get("attachments") if isinstance(metadata, Mapping) else None
    if value is None:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            value = None
    if not isinstance(value, list):
        raise AttachmentError(f"{bead}: metadata.attachments is not a JSON list; "
                              "fix it with bd update before adding")
    return entries(row)


def entries(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    metadata = row.get("metadata")
    value = metadata.get("attachments") if isinstance(metadata, Mapping) else None
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return []
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def reference(entry: Mapping[str, Any]) -> str:
    return f"![{entry.get('caption') or entry['name']}]({SCHEME}{entry['sha256']})"


@dataclass
class Added:
    entries: list[dict[str, Any]]
    refused: list[dict[str, str]]
    warning: str | None


def add(repo: Path, bead: str, files: Sequence[Path], *, caption: str | None = None, case: str | None = None,
        step: int | None = None, now: datetime | None = None, store: Store | None = None) -> Added:
    repo = Path(repo)
    settings = load_settings(repo)
    store = store or open_store(repo, settings)
    held = _held(bead, _show(repo, bead))
    stamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    author = team.git_email(main_checkout(repo.resolve())) or None
    result: list[dict[str, Any]] = []
    refused: list[dict[str, str]] = []
    new: list[dict[str, Any]] = []
    for file in map(Path, files):
        try:
            data = file.read_bytes()
        except OSError as error:
            refused.append({"name": file.name, "reason": f"cannot read: {error.strerror or error}"})
            continue
        mime = sniff(data)
        if mime is None:
            refused.append({"name": file.name, "reason": "not a PNG, JPEG, WebP or GIF"})
            continue
        try:
            data = clean(data, mime)
        except ValueError as error:
            refused.append({"name": file.name, "reason": f"malformed {mime}: {error}"})
            continue
        if len(data) > settings.max_bytes:
            refused.append({"name": file.name, "reason": f"{len(data)} bytes exceeds the {settings.max_bytes} limit"})
            continue
        sha = hashlib.sha256(data).hexdigest()
        existing = next((e for e in [*held, *new] if e.get("sha256") == sha and not e.get("pruned_at")), None)
        if existing is not None:
            result.append(existing)
            continue
        path = store.put(sha, data)
        entry = {"sha256": sha, "name": file.name, "mime": mime, "bytes": len(data), "caption": caption,
                 "case": case, "step": step, "added_by": author, "added_at": stamp, "store": store.name,
                 "path": path}
        new.append(entry)
        result.append(entry)
    warning = None
    if new:
        _bd(repo, ["update", "--set-metadata", f"attachments={json.dumps([*held, *new], sort_keys=True)}", "--", bead])
        warning = store.push()
    return Added(result, refused, warning)


def list_entries(repo: Path, bead: str) -> list[dict[str, Any]]:
    return _held(bead, _show(Path(repo), bead))


def fetch(repo: Path, *, bead: str | None = None, out: Path | None = None, store: Store | None = None) -> list[Path]:
    repo = Path(repo)
    store = store or open_store(repo, load_settings(repo))
    store.fetch()
    if bead is None or out is None:
        return []
    out = Path(out)
    if out.exists() and not out.is_dir():
        raise AttachmentError(f"{out} is not a directory")
    try:
        out.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise AttachmentError(f"cannot create {out}: {error.strerror or error}") from error
    written = []
    for entry in list_entries(repo, bead):
        if entry.get("pruned_at"):
            continue
        label = f"{bead}: entry {entry.get('name') or entry.get('sha256')}"
        sha = entry.get("sha256")
        if not isinstance(sha, str) or entry.get("mime") not in EXTENSIONS:
            raise AttachmentError(f"{label} has no sha256 or an unknown mime")
        try:
            data = store.get(entry.get("path") or blob_path(sha))
        except StoreError as error:
            raise AttachmentError(f"{label}: {error}") from error
        if hashlib.sha256(data).hexdigest() != sha:
            raise AttachmentError(f"{label}: stored bytes do not match sha256 {sha}")
        target = out / f"{sha}.{EXTENSIONS[entry['mime']]}"
        try:
            target.write_bytes(data)
        except OSError as error:
            raise AttachmentError(f"cannot write {target}: {error.strerror or error}") from error
        written.append(target)
    return written


def push(repo: Path, *, store: Store | None = None) -> str | None:
    repo = Path(repo)
    return (store or open_store(repo, load_settings(repo))).push()
