"""Portable configuration loading, validation, resolution, and provenance."""

from __future__ import annotations

from collections.abc import Mapping
import os
from pathlib import Path
import re
from typing import Any

from .atomic import atomic_write_many
from .checkout import main_checkout
from .models import (
    ConfigProvenance,
    DependencyUnavailableError,
    EffectiveConfig,
    ResolvedConfig,
    thaw,
)
from .schemas import SUPPORTED_CONFIG_VERSIONS, SUPPORTED_SCHEMA_VERSION, validate_config_schema


class ConfigValidationError(ValueError):
    """Raised when configuration is invalid or contains nonportable values."""


SUPPORTED_WORKFLOW_VERSION = "2.9"
SUPPORTED_SETUP_CLI_VERSION = "2.9"


BUILT_IN_DEFAULTS: dict[str, Any] = {
    "schema_version": SUPPORTED_SCHEMA_VERSION,
    "workflow_version": SUPPORTED_WORKFLOW_VERSION,
    "setup_cli_version": SUPPORTED_SETUP_CLI_VERSION,
    "artifacts": {
        "plans": ".planning/plans",
        "beads": ".beads",
        "knowledge": ".planning/knowledge",
        "evidence": ".agent-workflow/runtime/evidence",
        "runtime": ".agent-workflow/runtime",
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
    # team: holds emails, logins, globs, and URLs, which are not provider models or secret keys.
    in_team = path[:1] == ("team",)
    in_catalog_models = len(path) == 4 and path[0] == "models" and path[2] == "models"
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
            if not in_team and any(part in key for part in _SECRET_KEY_PARTS):
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
        if not in_team and not in_catalog_models and _MODEL_VALUE.search(value):
            raise ConfigValidationError(
                f"provider-model name is forbidden at {location}; use a logical model tier"
            )
        if _SECRET_VALUE.search(value) and not _is_secret_ref(value):
            raise ConfigValidationError(
                f"literal secret-like value is forbidden at {location}; use secret_ref"
            )


WORKER_ROUTING_KEYS = ("concurrency", "circuit_breaker", "queue", "worker")


def role_providers(role: Mapping[str, Any]) -> list[str]:
    """Every provider a routing role names: preferred, fallback, then by_tier."""
    tiers = role.get("by_tier") or {}
    return [*role.get("preferred", ()), *role.get("fallback", ()), *(p for tier in tiers.values() for p in tier)]


def legacy_worker_routing(config: Mapping[str, Any]) -> bool:
    """Whether `routing:` still holds worker routing that schema 2.8 keeps under `orchestrator:`."""
    routing = config.get("routing")
    if not isinstance(routing, Mapping):
        return False
    if any(key in routing for key in WORKER_ROUTING_KEYS):
        return True
    roles = routing.get("roles")
    return isinstance(roles, Mapping) and any(
        provider != "main_harness"
        for role in roles.values() if isinstance(role, Mapping) for provider in role_providers(role)
    )


def validate_portable_config(config: Mapping[str, Any]) -> None:
    providers = config.get("providers", {})
    task_tracking = providers.get("task_tracking") if isinstance(providers, Mapping) else None
    if "team" in config and (
        task_tracking.get("name") if isinstance(task_tracking, Mapping) else task_tracking
    ) == "markdown":
        raise ConfigValidationError("team mode requires Beads; providers.task_tracking: markdown is not supported")
    try:
        validate_config_schema(config)
    except DependencyUnavailableError:
        raise
    except ValueError as error:
        raise ConfigValidationError(str(error)) from error
    if str(config.get("schema_version", "")) not in SUPPORTED_CONFIG_VERSIONS:
        raise ConfigValidationError(
            f"unsupported schema_version {config.get('schema_version')!r}; "
            f"expected one of {SUPPORTED_CONFIG_VERSIONS!r}"
        )
    for field in ("workflow_version", "setup_cli_version"):
        if field in config and str(config[field]) not in SUPPORTED_CONFIG_VERSIONS:
            raise ConfigValidationError(
                f"unsupported {field} {config[field]!r}; expected one of {SUPPORTED_CONFIG_VERSIONS!r}"
            )
    if str(config.get("schema_version")) == "2.9" and "model_tiers" in config:
        raise ConfigValidationError("model_tiers was removed in schema 2.9; list models per harness under models:")
    routing = config.get("routing", {})
    if isinstance(routing, Mapping):
        roles = routing.get("roles", {})
        if str(config.get("schema_version")) in ("2.8", "2.9"):
            if legacy_worker_routing(config):
                raise ConfigValidationError(
                    "worker routing (routing.concurrency, queue, worker, circuit_breaker, or a role naming a "
                    "provider other than main_harness) belongs under orchestrator:; "
                    "run gin-workflow setup update --to-version 2.8 --approve"
                )
        elif isinstance(roles, Mapping):
            concurrency = routing.get("concurrency", {})
            known_providers = set(concurrency) if isinstance(concurrency, Mapping) else set()
            harness = config.get("harness")
            if isinstance(harness, str) and harness:
                known_providers.add(harness)
            for role_name, role in roles.items():
                if not isinstance(role, Mapping):
                    continue
                for provider in role_providers(role):
                    if provider != "main_harness" and provider not in known_providers:
                        raise ConfigValidationError(
                            f"unknown routing provider {provider!r} in role {role_name!r}"
                        )
        review = routing.get("review", {})
        if isinstance(review, Mapping) and review.get("role") not in (None, ""):
            if not isinstance(roles, Mapping) or review["role"] not in roles:
                raise ConfigValidationError(f"unknown review role: {review['role']!r}")
    if isinstance(config.get("team"), Mapping):
        from .team import validate_team

        team_errors = validate_team(config["team"])
        if team_errors:
            raise ConfigValidationError("; ".join(team_errors))
    _validate_portable(config)


SUPPORTED_HARNESSES = ("claude", "codex", "antigravity", "opencode")


def get_session_harness_override(repository: Path) -> str | None:
    """Return active in-session main harness override if configured, else None."""
    env_override = os.environ.get("GIN_WORKFLOW_HARNESS_OVERRIDE") or os.environ.get("GIN_WORKFLOW_HARNESS")
    if env_override and env_override.strip():
        override = env_override.strip().lower()
    else:
        override_file = main_checkout(Path(repository).resolve()) / ".agent-workflow/runtime/session-harness.override"
        if override_file.is_file():
            try:
                override = override_file.read_text(encoding="utf-8").strip().lower()
            except Exception as error:
                raise ConfigValidationError(
                    f"failed to read session harness override file {override_file}: {error}"
                ) from error
        else:
            return None

    if not override:
        return None

    if override not in SUPPORTED_HARNESSES:
        raise ConfigValidationError(
            f"invalid session harness override {override!r}; must be one of: {', '.join(SUPPORTED_HARNESSES)}"
        )
    return override


def load_effective_config(repository: Path) -> EffectiveConfig:
    """Load the generated lifecycle configuration after one-time setup."""
    root = Path(repository).resolve()
    path = main_checkout(root) / ".agent-workflow/generated/effective-config.yaml"
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

    override = get_session_harness_override(root)
    if override:
        config["_original_harness"] = config.get("harness")
        config["harness"] = override
        config["_session_harness_override"] = override

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

    override = get_session_harness_override(root)
    if override:
        resolved["_original_harness"] = resolved.get("harness")
        resolved["harness"] = override
        resolved["_session_harness_override"] = override
        effective_config = EffectiveConfig(resolved, root)

    return ResolvedConfig(
        config=effective_config,
        provenance=provenance,
        effective_config_path=effective_path,
        provenance_path=provenance_path,
    )

