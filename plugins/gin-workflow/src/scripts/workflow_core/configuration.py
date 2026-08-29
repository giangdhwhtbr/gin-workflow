"""Portable configuration loading, validation, resolution, and provenance."""

from __future__ import annotations

from collections.abc import Mapping
import os
from pathlib import Path
import re
from typing import Any

from .atomic import atomic_write_many
from .models import (
    ConfigProvenance,
    DependencyUnavailableError,
    EffectiveConfig,
    ResolvedConfig,
    thaw,
)
from .schemas import SUPPORTED_SCHEMA_VERSION, validate_config_schema


class ConfigValidationError(ValueError):
    """Raised when configuration is invalid or contains nonportable values."""


SUPPORTED_WORKFLOW_VERSION = "2.3"
SUPPORTED_SETUP_CLI_VERSION = "2.3"


BUILT_IN_DEFAULTS: dict[str, Any] = {
    "schema_version": SUPPORTED_SCHEMA_VERSION,
    "workflow_version": SUPPORTED_WORKFLOW_VERSION,
    "setup_cli_version": SUPPORTED_SETUP_CLI_VERSION,
    "artifacts": {
        "plans": ".planning/plans",
        "beads": ".beads",
        "worktrees": ".planning/worktrees",
        "knowledge": ".planning/knowledge",
        "evidence": ".agent-workflow/runtime/evidence",
        "runtime": ".agent-workflow/runtime",
    },
    "model_tiers": {
        "brainstorm": "high_reasoning",
        "design": "high_reasoning",
        "plan": "high_reasoning",
        "implement": "standard_impl",
        "verify": "high_reasoning",
        "review": "high_reasoning",
        "docs": "cheap_simple",
    },
    "capabilities": {},
    "policy": {
        "approval": {
            "ttl_seconds": 86400,
            "bind_to_scope": True,
        },
    },
}

_COMMAND_KEYS = {
    "command",
    "commands",
    "cmd",
    "argv",
    "executable",
    "shell",
    "provider_command",
}
_MODEL_KEYS = {"model", "model_name", "model_id", "provider_model"}
_SECRET_KEY_PARTS = (
    "api_key",
    "apikey",
    "access_key",
    "password",
    "passwd",
    "credential",
    "private_key",
    "secret",
    "token",
)
_MODEL_VALUE = re.compile(
    r"(?:^|[/@:])(?:gpt-|claude-|gemini-|command-r|mistral-|llama-|o[134](?:-|$))",
    re.IGNORECASE,
)
_SECRET_VALUE = re.compile(
    r"(?:-----BEGIN [A-Z ]*PRIVATE KEY-----|\bsk-[A-Za-z0-9_-]{6,}|\bgh[pousr]_[A-Za-z0-9]{6,}|\bxox[baprs]-)",
    re.IGNORECASE,
)
_SECRET_REF_VALUE = re.compile(
    r"^(?:env|file|keyring|vault|op|aws-sm|gcp-sm|azure-kv):[A-Za-z0-9][A-Za-z0-9_.:/-]*$"
)


def require_yaml():
    try:
        import yaml
    except ImportError as error:  # pragma: no cover - exercised in dependency-isolated packaging tests
        raise DependencyUnavailableError(
            "The 'PyYAML' package is required to read and write gin-workflow configuration. "
            "Install it with: python3 -m pip install PyYAML"
        ) from error
    return yaml


def _normalize_key(key: object) -> str:
    return str(key).strip().lower().replace("-", "_")


def _is_secret_ref(value: object) -> bool:
    if isinstance(value, Mapping) and set(value) == {"secret_ref"}:
        return _is_secret_ref(value["secret_ref"])
    if not isinstance(value, str):
        return False
    candidate = value.strip()
    if candidate.startswith("${secret_ref:") and candidate.endswith("}"):
        candidate = candidate[len("${secret_ref:") : -1]
    elif candidate.startswith("secret_ref:"):
        candidate = candidate[len("secret_ref:") :]
    return bool(_SECRET_REF_VALUE.fullmatch(candidate))


def _validate_portable(value: object, path: tuple[str, ...] = ()) -> None:
    if isinstance(value, Mapping):
        for raw_key, item in value.items():
            key = _normalize_key(raw_key)
            field_path = path + (str(raw_key),)
            location = ".".join(field_path)
            if key in _COMMAND_KEYS or key.endswith("_command") or key.endswith("_commands"):
                raise ConfigValidationError(
                    f"portable configuration must not contain provider commands: {location}"
                )
            if key in _MODEL_KEYS or (
                key.endswith("_model") and key not in {"logical_model", "logical_model_tier"}
            ):
                raise ConfigValidationError(
                    f"portable configuration must use logical model tiers, not provider models: {location}"
                )
            if key == "secret_ref":
                if not _is_secret_ref(item):
                    raise ConfigValidationError(
                        f"invalid secret_ref at {location}; use a reference such as env:VARIABLE_NAME"
                    )
                continue
            if any(part in key for part in _SECRET_KEY_PARTS):
                if not _is_secret_ref(item):
                    raise ConfigValidationError(
                        f"literal secret-like value is forbidden at {location}; use secret_ref"
                    )
                continue
            _validate_portable(item, field_path)
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _validate_portable(item, path + (str(index),))
        return
    if isinstance(value, str):
        location = ".".join(path) or "<root>"
        if _MODEL_VALUE.search(value):
            raise ConfigValidationError(
                f"provider-model name is forbidden at {location}; use a logical model tier"
            )
        if _SECRET_VALUE.search(value) and not _is_secret_ref(value):
            raise ConfigValidationError(
                f"literal secret-like value is forbidden at {location}; use secret_ref"
            )


def validate_portable_config(config: Mapping[str, Any]) -> None:
    try:
        validate_config_schema(config)
    except DependencyUnavailableError:
        raise
    except ValueError as error:
        raise ConfigValidationError(str(error)) from error
    if str(config.get("schema_version", "")) != SUPPORTED_SCHEMA_VERSION:
        raise ConfigValidationError(
            f"unsupported schema_version {config.get('schema_version')!r}; "
            f"expected {SUPPORTED_SCHEMA_VERSION!r}"
        )
    for field, supported in (
        ("workflow_version", SUPPORTED_WORKFLOW_VERSION),
        ("setup_cli_version", SUPPORTED_SETUP_CLI_VERSION),
    ):
        if field in config and str(config[field]) != supported:
            raise ConfigValidationError(
                f"unsupported {field} {config[field]!r}; expected {supported!r}"
            )
    routing = config.get("routing", {})
    if isinstance(routing, Mapping):
        concurrency = routing.get("concurrency", {})
        known_providers = set(concurrency) if isinstance(concurrency, Mapping) else set()
        harness = config.get("harness")
        if isinstance(harness, str) and harness:
            known_providers.add(harness)
        roles = routing.get("roles", {})
        if isinstance(roles, Mapping):
            for role_name, role in roles.items():
                if not isinstance(role, Mapping):
                    continue
                for provider in (*role.get("preferred", ()), *role.get("fallback", ())):
                    if provider != "main_harness" and provider not in known_providers:
                        raise ConfigValidationError(
                            f"unknown routing provider {provider!r} in role {role_name!r}"
                        )
        review = routing.get("review", {})
        if isinstance(review, Mapping) and review.get("role") not in (None, ""):
            if not isinstance(roles, Mapping) or review["role"] not in roles:
                raise ConfigValidationError(f"unknown review role: {review['role']!r}")
    _validate_portable(config)


def load_effective_config(repository: Path) -> EffectiveConfig:
    """Load the generated lifecycle configuration after one-time setup."""
    root = Path(repository).resolve()
    path = root / ".agent-workflow/generated/effective-config.yaml"
    if not path.is_file():
        raise ConfigValidationError(
            "gin-workflow repository setup is required; run "
            "`gin-workflow setup init --repository <path>` once before lifecycle work"
        )
    config = _read_yaml(path, missing_ok=False)
    validate_portable_config(config)
    for field in ("workflow_version", "setup_cli_version"):
        if field not in config:
            raise ConfigValidationError(
                f"missing required lifecycle version channel: {field}"
            )
    return EffectiveConfig(config, root)


def _read_yaml(path: Path, *, missing_ok: bool) -> dict[str, Any]:
    if not path.exists():
        if missing_ok:
            return {}
        raise FileNotFoundError(path)
    yaml = require_yaml()
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise ConfigValidationError(f"invalid YAML in {path}: {error}") from error
    if loaded is None:
        return {}
    if not isinstance(loaded, Mapping):
        raise ConfigValidationError(f"configuration layer {path} must contain a YAML mapping")
    return {str(key): item for key, item in loaded.items()}


def _load_layer(source: object, *, default_path: Path | None = None) -> dict[str, Any]:
    if source is None:
        if default_path is None:
            return {}
        return _read_yaml(default_path, missing_ok=True)
    if isinstance(source, Mapping):
        return thaw(source)
    if isinstance(source, (str, os.PathLike)):
        return _read_yaml(Path(source), missing_ok=False)
    raise TypeError("configuration layers must be mappings, filesystem paths, or None")


def _remove_provenance_branch(provenance: dict[str, str], dotted_path: str) -> None:
    prefix = f"{dotted_path}." if dotted_path else ""
    for key in tuple(provenance):
        if key == dotted_path or (prefix and key.startswith(prefix)):
            del provenance[key]


def _provenance_identifier(path: tuple[str, ...]) -> str:
    def escape(component: str) -> str:
        return component.replace("\\", "\\\\").replace(".", "\\.")

    return ".".join(escape(component) for component in path)


def _merge_layer(
    target: dict[str, Any],
    layer: Mapping[str, Any],
    provenance: dict[str, str],
    source_name: str,
    prefix: tuple[str, ...] = (),
) -> None:
    for raw_key, raw_value in layer.items():
        key = str(raw_key)
        path = prefix + (key,)
        dotted = _provenance_identifier(path)
        if isinstance(raw_value, Mapping):
            if not isinstance(target.get(key), Mapping):
                target[key] = {}
                _remove_provenance_branch(provenance, dotted)
            _merge_layer(target[key], raw_value, provenance, source_name, path)
        else:
            target[key] = thaw(raw_value)
            _remove_provenance_branch(provenance, dotted)
            provenance[dotted] = source_name


def _yaml_bytes(value: Mapping[str, Any]) -> bytes:
    yaml = require_yaml()
    return yaml.safe_dump(
        thaw(value),
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=True,
    ).encode("utf-8")


def resolve_effective_config(
    repository: Path,
    overrides: Mapping[str, Any] | None = None,
    *,
    built_in_defaults: Mapping[str, Any] | None = None,
    user_profile: Mapping[str, Any] | os.PathLike[str] | str | None = None,
    organization_profile: Mapping[str, Any] | os.PathLike[str] | str | None = None,
    repository_config: Mapping[str, Any] | os.PathLike[str] | str | None = None,
    harness_override: Mapping[str, Any] | os.PathLike[str] | str | None = None,
    local_override: Mapping[str, Any] | os.PathLike[str] | str | None = None,
    command_override: Mapping[str, Any] | None = None,
    write: bool = True,
) -> ResolvedConfig:
    """Resolve portable configuration in the documented precedence order."""
    root = Path(repository).resolve()
    workflow_dir = root / ".agent-workflow"

    user_default = os.environ.get("GIN_WORKFLOW_USER_PROFILE")
    organization_default = os.environ.get("GIN_WORKFLOW_ORGANIZATION_PROFILE")
    layers = (
        ("built-in defaults", thaw(built_in_defaults or BUILT_IN_DEFAULTS)),
        (
            "user profile",
            _load_layer(
                user_profile,
                default_path=Path(user_default).expanduser() if user_default else None,
            ),
        ),
        (
            "organization profile",
            _load_layer(
                organization_profile,
                default_path=Path(organization_default).expanduser()
                if organization_default
                else None,
            ),
        ),
        (
            "repository config",
            _load_layer(repository_config, default_path=workflow_dir / "config.yaml"),
        ),
        (
            "harness override",
            _load_layer(harness_override, default_path=workflow_dir / "harness-override.yaml"),
        ),
        (
            "local override",
            _load_layer(local_override, default_path=workflow_dir / "local.yaml"),
        ),
        ("command override", {**thaw(overrides or {}), **thaw(command_override or {})}),
    )

    resolved: dict[str, Any] = {}
    source_by_field: dict[str, str] = {}
    for source_name, layer in layers:
        _merge_layer(resolved, layer, source_by_field, source_name)

    validate_portable_config(resolved)
    effective_config = EffectiveConfig(resolved, root)
    provenance = ConfigProvenance(source_by_field)
    generated = workflow_dir / "generated"
    effective_path = generated / "effective-config.yaml"
    provenance_path = generated / "config-provenance.yaml"

    # Serialization and validation complete before the first filesystem mutation.
    if write:
        effective_content = _yaml_bytes(effective_config.to_dict())
        provenance_content = _yaml_bytes(provenance.to_dict())
        atomic_write_many(
            {
                effective_path: effective_content,
                provenance_path: provenance_content,
            }
        )

    return ResolvedConfig(
        config=effective_config,
        provenance=provenance,
        effective_config_path=effective_path,
        provenance_path=provenance_path,
    )
