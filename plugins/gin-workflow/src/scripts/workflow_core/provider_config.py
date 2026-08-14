"""Machine-local native provider configuration outside portable config."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

from .configuration import require_yaml
from .schemas import SUPPORTED_SCHEMA_VERSION


REASONING_TIERS = ("low", "medium", "high")


class ProviderLocalConfigError(ValueError):
    """Raised when native executable/model mappings are missing or unsafe."""


@dataclass(frozen=True)
class ProviderModelConfig:
    provider: str
    executable: str
    models: Mapping[str, str]


def validate_provider_local_config(value: Mapping[str, Any]) -> None:
    if not isinstance(value, Mapping):
        raise ProviderLocalConfigError("provider local config must be a mapping")
    unknown_root = set(value) - {"schema_version", "providers"}
    if unknown_root:
        raise ProviderLocalConfigError(
            f"unsupported provider local fields: {', '.join(sorted(unknown_root))}"
        )
    if str(value.get("schema_version", "")) != SUPPORTED_SCHEMA_VERSION:
        raise ProviderLocalConfigError(
            f"provider local schema_version must be {SUPPORTED_SCHEMA_VERSION!r}"
        )
    providers = value.get("providers")
    if not isinstance(providers, Mapping) or not providers:
        raise ProviderLocalConfigError("providers must be a non-empty mapping")
    for raw_name, raw_entry in providers.items():
        name = str(raw_name).strip()
        if not name or not isinstance(raw_entry, Mapping):
            raise ProviderLocalConfigError("provider entries must be named mappings")
        unknown = set(raw_entry) - {"executable", "models"}
        if unknown:
            raise ProviderLocalConfigError(
                f"unsupported provider fields for {name}: {', '.join(sorted(unknown))}"
            )
        executable = raw_entry.get("executable")
        if not isinstance(executable, str) or not executable.strip():
            raise ProviderLocalConfigError(f"provider {name} requires executable")
        models = raw_entry.get("models")
        if not isinstance(models, Mapping):
            raise ProviderLocalConfigError(f"provider {name} requires models mapping")
        for tier in REASONING_TIERS:
            if tier not in models:
                raise ProviderLocalConfigError(f"missing model tier: {tier}")
            model = models[tier]
            if not isinstance(model, str) or not model.strip():
                raise ProviderLocalConfigError(f"model tier {tier} must be a non-empty string")
        unknown_tiers = set(models) - set(REASONING_TIERS)
        if unknown_tiers:
            raise ProviderLocalConfigError(
                f"unsupported model tiers: {', '.join(sorted(unknown_tiers))}"
            )


def load_provider_local_config(repository: Path) -> Mapping[str, ProviderModelConfig]:
    path = Path(repository).resolve() / ".agent-workflow/providers.local.yaml"
    if not path.is_file():
        raise ProviderLocalConfigError(f"provider local configuration does not exist: {path}")
    yaml = require_yaml()
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, yaml.YAMLError) as error:
        raise ProviderLocalConfigError(f"invalid provider local configuration: {error}") from error
    validate_provider_local_config(loaded)
    providers = {
        str(name): ProviderModelConfig(
            str(name),
            str(entry["executable"]),
            MappingProxyType({str(tier): str(model) for tier, model in entry["models"].items()}),
        )
        for name, entry in loaded["providers"].items()
    }
    return MappingProxyType(providers)
