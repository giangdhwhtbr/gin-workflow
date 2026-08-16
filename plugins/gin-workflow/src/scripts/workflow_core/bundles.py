"""Deterministic, secret-safe setup bundle export and verification."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping

from .atomic import atomic_write_text
from .configuration import require_yaml
from .schemas import require_jsonschema, validate_config_schema, validate_config_provenance


BUNDLE_SCHEMA_VERSION = "1"
_GENERATED_PATHS = (
    ".agent-workflow/generated/effective-config.yaml",
    ".agent-workflow/generated/config-provenance.yaml",
)
_ARCHIVE_SUFFIXES = {".7z", ".bz2", ".gz", ".rar", ".tar", ".tgz", ".xz", ".zip"}
_LITERAL_SECRET = re.compile(
    r"(?:-----BEGIN [A-Z ]*PRIVATE KEY-----|\bsk-[A-Za-z0-9_-]{6,}|\bgh[pousr]_[A-Za-z0-9]{6,}|\bxox[baprs]-)",
    re.IGNORECASE,
)
_CREDENTIAL_ASSIGNMENT = re.compile(
    r"^[ \t]*(?:export[ \t]+)?"
    r"(?P<key>[A-Za-z0-9_.-]*(?:password|passwd|api[_-]?key|access[_-]?key|secret|token|credential|private[_-]?key)[A-Za-z0-9_.-]*)"
    r"[ \t]*(?:=|:)[ \t]*(?P<value>[^\r\n#]*\S)[ \t]*(?:#.*)?$",
    re.IGNORECASE | re.MULTILINE,
)
_SECRET_REFERENCE = re.compile(
    r"^(?:env|file|keyring|vault|op|aws-sm|gcp-sm|azure-kv):"
    r"[A-Za-z0-9][A-Za-z0-9_.:/-]*$",
    re.IGNORECASE,
)
_ENV_REFERENCE = re.compile(r"^\$(?:[A-Za-z_][A-Za-z0-9_]*|\{[A-Za-z_][A-Za-z0-9_]*\})$")


class BundleError(ValueError):
    """Raised when bundle inputs or integrity checks are unsafe."""


def _declared_references(config: Mapping[str, Any]) -> Iterable[str]:
    references = config.get("references", ())
    if isinstance(references, str):
        yield references
    elif isinstance(references, Mapping):
        for value in references.values():
            if isinstance(value, str):
                yield value
            elif isinstance(value, (list, tuple)):
                yield from (item for item in value if isinstance(item, str))
    elif isinstance(references, (list, tuple)):
        yield from (item for item in references if isinstance(item, str))


def _safe_reference(root: Path, declared: str) -> tuple[str, Path] | None:
    relative = Path(declared)
    if relative.is_absolute() or ".." in relative.parts:
        raise BundleError(f"declared reference must be repository-relative: {declared}")
    normalized = relative.as_posix()
    if normalized == ".agent-workflow/providers.local.yaml":
        return None
    if normalized.startswith(".agent-workflow/runtime/") or normalized.startswith(
        ".agent-workflow/backups/"
    ):
        return None
    if any(normalized.lower().endswith(suffix) for suffix in _ARCHIVE_SUFFIXES):
        return None
    resolved = (root / relative).resolve()
    if not resolved.is_relative_to(root) or resolved.is_symlink():
        raise BundleError(f"declared reference escapes the repository: {declared}")
    if not resolved.is_file():
        raise BundleError(f"declared reference does not exist: {declared}")
    return normalized, resolved


def _is_secret_reference(value: str) -> bool:
    candidate = value.strip().strip("'\"")
    if candidate.lower() in {"<redacted>", "[redacted]", "redacted", "***"}:
        return True
    if _ENV_REFERENCE.fullmatch(candidate):
        return True
    if candidate.startswith("${secret_ref:") and candidate.endswith("}"):
        candidate = candidate[len("${secret_ref:") : -1]
    elif candidate.startswith("secret_ref:"):
        candidate = candidate[len("secret_ref:") :].strip()
    return bool(_SECRET_REFERENCE.fullmatch(candidate))


def _literal_credential(content: str) -> str | None:
    for match in _CREDENTIAL_ASSIGNMENT.finditer(content):
        if not _is_secret_reference(match.group("value")):
            return match.group("key")
    return None


def _read_portable_text(path: Path, label: str) -> str:
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise BundleError(f"bundle input must be UTF-8 text: {label}") from error
    if _LITERAL_SECRET.search(content):
        raise BundleError(f"bundle input contains a literal secret: {label}")
    credential = _literal_credential(content)
    if credential is not None:
        raise BundleError(f"bundle input contains a literal credential ({credential}): {label}")
    return content


def _payload_digest(files: Mapping[str, Any]) -> str:
    canonical = json.dumps(files, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _parse_generated_yaml(content: str, relative: str) -> Mapping[str, Any]:
    yaml = require_yaml()
    try:
        parsed = yaml.safe_load(content)
    except yaml.YAMLError as error:
        raise BundleError(f"invalid embedded generated YAML in {relative}: {error}") from error
    if not isinstance(parsed, Mapping):
        raise BundleError(f"embedded generated file must contain a mapping: {relative}")
    return parsed


def _validate_generated(files: Mapping[str, Any]) -> None:
    parsed = {
        relative: _parse_generated_yaml(files[relative]["content"], relative)
        for relative in _GENERATED_PATHS
    }
    try:
        validate_config_schema(parsed[_GENERATED_PATHS[0]])
        validate_config_provenance(parsed[_GENERATED_PATHS[1]])
    except ValueError as error:
        raise BundleError(f"embedded generated schema validation failed: {error}") from error


def export_bundle(repository: Path, output: Path, *, dry_run: bool = False) -> dict[str, Any]:
    require_jsonschema()
    yaml = require_yaml()
    root = Path(repository).resolve()
    output_path = Path(output)
    if not output_path.is_absolute():
        output_path = root / output_path

    generated: dict[str, Mapping[str, Any]] = {}
    for relative in _GENERATED_PATHS:
        path = root / relative
        if not path.is_file():
            raise BundleError(f"required generated file does not exist: {relative}")
        try:
            value = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, yaml.YAMLError) as error:
            raise BundleError(f"invalid generated YAML in {relative}: {error}") from error
        if not isinstance(value, Mapping):
            raise BundleError(f"generated file must contain a mapping: {relative}")
        generated[relative] = value
    validate_config_schema(generated[_GENERATED_PATHS[0]])
    validate_config_provenance(generated[_GENERATED_PATHS[1]])

    inputs: dict[str, Path] = {relative: root / relative for relative in _GENERATED_PATHS}
    for declared in _declared_references(generated[_GENERATED_PATHS[0]]):
        safe = _safe_reference(root, declared)
        if safe is not None:
            relative, path = safe
            inputs[relative] = path

    files: dict[str, dict[str, str]] = {}
    for relative in sorted(inputs):
        content = _read_portable_text(inputs[relative], relative)
        files[relative] = {
            "content": content,
            "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        }
    payload = {
        "bundle_schema_version": BUNDLE_SCHEMA_VERSION,
        "files": files,
        "bundle_sha256": _payload_digest(files),
    }
    actions = [f"write bundle {output_path}"]
    if dry_run:
        return {"status": "would_export", "output": str(output_path), "actions": actions}
    atomic_write_text(output_path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return {
        "status": "exported",
        "output": str(output_path),
        "files": sorted(files),
        "actions": actions,
    }


def verify_bundle(bundle: Path) -> dict[str, Any]:
    require_jsonschema()
    path = Path(bundle)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BundleError(f"invalid bundle: {error}") from error
    if not isinstance(payload, Mapping):
        raise BundleError("bundle must contain a JSON object")
    if payload.get("bundle_schema_version") != BUNDLE_SCHEMA_VERSION:
        raise BundleError("bundle schema version is unsupported")
    files = payload.get("files")
    if not isinstance(files, Mapping):
        raise BundleError("bundle files must be an object")
    if payload.get("bundle_sha256") != _payload_digest(files):
        raise BundleError("bundle hash mismatch")
    for relative, entry in files.items():
        if not isinstance(relative, str) or not isinstance(entry, Mapping):
            raise BundleError("bundle file entry is malformed")
        content = entry.get("content")
        digest = entry.get("sha256")
        if not isinstance(content, str) or digest != hashlib.sha256(content.encode("utf-8")).hexdigest():
            raise BundleError(f"bundle file hash mismatch: {relative}")
        if _LITERAL_SECRET.search(content):
            raise BundleError(f"bundle contains a literal secret: {relative}")
        credential = _literal_credential(content)
        if credential is not None:
            raise BundleError(f"bundle contains a literal credential ({credential}): {relative}")
    for required in _GENERATED_PATHS:
        if required not in files:
            raise BundleError(f"bundle is missing required generated file: {required}")
    _validate_generated(files)
    return {"status": "valid", "bundle": str(path), "files": sorted(files)}
