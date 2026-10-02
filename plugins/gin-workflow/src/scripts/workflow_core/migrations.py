"""Explicit, versioned configuration migrations with validated backups."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .atomic import atomic_write_many, atomic_write_bytes
from .configuration import require_yaml, validate_portable_config


CURRENT_VERSION = "2.4"
BACKUP_SCHEMA_VERSION = "1"


class MigrationError(ValueError):
    """Raised when an update or rollback cannot be performed safely."""


def _read_config(path: Path) -> tuple[bytes, dict[str, Any]]:
    if not path.is_file():
        raise MigrationError(f"configuration does not exist: {path}")
    raw = path.read_bytes()
    yaml = require_yaml()
    try:
        loaded = yaml.safe_load(raw.decode("utf-8"))
    except (UnicodeDecodeError, yaml.YAMLError) as error:
        raise MigrationError(f"invalid configuration in {path}: {error}") from error
    if not isinstance(loaded, Mapping):
        raise MigrationError(f"configuration in {path} must be a YAML mapping")
    return raw, {str(key): value for key, value in loaded.items()}


def _migrate_2_0_to_2_1(config: dict[str, Any]) -> dict[str, Any]:
    migrated = dict(config)
    migrated["schema_version"] = "2.1"
    migrated["workflow_version"] = "2.1"
    migrated["setup_cli_version"] = "2.1"
    return migrated


def _migrate_2_1_to_2_2(config: dict[str, Any]) -> dict[str, Any]:
    migrated = dict(config)
    migrated["schema_version"] = "2.2"
    migrated["workflow_version"] = "2.2"
    migrated["setup_cli_version"] = "2.2"
    return migrated


def _migrate_2_2_to_2_3(config: dict[str, Any]) -> dict[str, Any]:
    migrated = dict(config)
    migrated["schema_version"] = "2.3"
    migrated["workflow_version"] = "2.3"
    migrated["setup_cli_version"] = "2.3"
    return migrated


def _migrate_2_3_to_2_4(config: dict[str, Any]) -> dict[str, Any]:
    migrated = dict(config)
    migrated["schema_version"] = "2.4"
    migrated["workflow_version"] = "2.4"
    migrated["setup_cli_version"] = "2.4"
    return migrated


_MIGRATIONS = {
    ("2.0", "2.1"): _migrate_2_0_to_2_1,
    ("2.1", "2.2"): _migrate_2_1_to_2_2,
    ("2.2", "2.3"): _migrate_2_2_to_2_3,
    ("2.3", "2.4"): _migrate_2_3_to_2_4,
}
_NEXT_STEP = {source: target for source, target in _MIGRATIONS}


_MIGRATION_TARGET_VERSIONS = frozenset(target for _, target in _MIGRATIONS)


def _require_migration_target(target_version: str) -> None:
    if target_version not in _MIGRATION_TARGET_VERSIONS:
        raise MigrationError(f"unsupported migration target: {target_version!r}")


def _migration_path(source_version: str, target_version: str) -> list[tuple[str, str]]:
    path: list[tuple[str, str]] = []
    current = source_version
    while current != target_version:
        step = _NEXT_STEP.get(current)
        if step is None:
            raise MigrationError(
                f"no migration is registered from {source_version!r} to {target_version!r}"
            )
        path.append((current, step))
        current = step
    return path


def migrate_config(config: Mapping[str, Any], target_version: str) -> dict[str, Any]:
    _require_migration_target(target_version)
    source_version = str(config.get("schema_version", ""))
    migrated = dict(config)
    for step in _migration_path(source_version, target_version):
        migrated = _MIGRATIONS[step](migrated)
    for field_name in ("schema_version", "workflow_version", "setup_cli_version"):
        if str(migrated.get(field_name, "")) != target_version:
            raise MigrationError(f"migration did not produce {field_name}={target_version!r}")
    validation_candidate = dict(migrated)
    validation_candidate.update(
        schema_version=CURRENT_VERSION,
        workflow_version=CURRENT_VERSION,
        setup_cli_version=CURRENT_VERSION,
    )
    validate_portable_config(validation_candidate)
    return migrated


def propose_migration(repository: Path, *, target_version: str = CURRENT_VERSION) -> dict[str, Any]:
    _require_migration_target(target_version)
    root = Path(repository).resolve()
    _, config = _read_config(root / ".agent-workflow/config.yaml")
    source_version = str(config.get("schema_version", ""))
    if source_version == target_version:
        return {
            "status": "up_to_date",
            "from_version": source_version,
            "to_version": target_version,
            "actions": [],
        }
    _migration_path(source_version, target_version)
    return {
        "status": "migration_available",
        "from_version": source_version,
        "to_version": target_version,
        "actions": ["create validated backup", f"migrate schema {source_version} to {target_version}"],
    }


def apply_migration(
    repository: Path,
    *,
    target_version: str = CURRENT_VERSION,
    dry_run: bool = False,
    prepared_config: Mapping[str, Any] | None = None,
    additional_writes: Mapping[Path, bytes] | None = None,
) -> dict[str, Any]:
    root = Path(repository).resolve()
    workflow = root / ".agent-workflow"
    config_path = workflow / "config.yaml"
    original, config = _read_config(config_path)
    source_version = str(config.get("schema_version", ""))
    proposal = propose_migration(root, target_version=target_version)
    if proposal["status"] == "up_to_date" or dry_run:
        return proposal

    migrated = (
        migrate_config(prepared_config, target_version)
        if prepared_config is not None
        else migrate_config(config, target_version)
    )
    yaml = require_yaml()
    migrated_bytes = yaml.safe_dump(
        migrated,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=True,
    ).encode("utf-8")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    backup = workflow / "backups" / f"{timestamp}-{source_version}-to-{target_version}"
    metadata = {
        "backup_schema_version": BACKUP_SCHEMA_VERSION,
        "from_version": source_version,
        "to_version": target_version,
        "config_sha256": hashlib.sha256(original).hexdigest(),
    }
    atomic_write_many(
        {
            backup / "config.yaml": original,
            backup / "metadata.json": (
                json.dumps(metadata, indent=2, sort_keys=True) + "\n"
            ).encode("utf-8"),
        }
    )
    atomic_write_many({config_path: migrated_bytes, **dict(additional_writes or {})})
    return {**proposal, "status": "migrated", "backup": str(backup)}


def _validated_backup(repository: Path, target: Path) -> tuple[Path, bytes, dict[str, Any]]:
    root = Path(repository).resolve()
    backup_root = (root / ".agent-workflow/backups").resolve()
    candidate = Path(target)
    if not candidate.is_absolute():
        candidate = backup_root / candidate
    candidate = candidate.resolve()
    if candidate == backup_root or not candidate.is_relative_to(backup_root):
        raise MigrationError("rollback target must be inside .agent-workflow/backups")
    if not candidate.is_dir() or candidate.is_symlink():
        raise MigrationError(f"rollback backup does not exist or is unsafe: {candidate}")

    metadata_path = candidate / "metadata.json"
    config_path = candidate / "config.yaml"
    if not metadata_path.is_file() or not config_path.is_file():
        raise MigrationError("rollback backup is incomplete")
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MigrationError(f"invalid rollback metadata: {error}") from error
    if metadata.get("backup_schema_version") != BACKUP_SCHEMA_VERSION:
        raise MigrationError("rollback backup schema version is unsupported")
    content = config_path.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    if digest != metadata.get("config_sha256"):
        raise MigrationError("rollback backup hash mismatch")
    _, parsed = _read_config(config_path)
    if str(parsed.get("schema_version", "")) != str(metadata.get("from_version", "")):
        raise MigrationError("rollback backup version does not match its metadata")
    return candidate, content, metadata


def rollback_migration(
    repository: Path,
    backup: Path,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    root = Path(repository).resolve()
    candidate, content, metadata = _validated_backup(root, Path(backup))
    result = {
        "status": "would_roll_back" if dry_run else "rolled_back",
        "backup": str(candidate),
        "restored_version": str(metadata["from_version"]),
        "actions": ["restore .agent-workflow/config.yaml from validated backup"],
    }
    if not dry_run:
        atomic_write_bytes(root / ".agent-workflow/config.yaml", content)
    return result
