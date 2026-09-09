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
PROVIDER_DEFAULT = "provider_default"
CODEX_EFFORT_VALUES = frozenset({"low", "medium", "high", "xhigh"})


class ProviderLocalConfigError(ValueError):
    """Raised when native executable/model mappings are missing or unsafe."""


@dataclass(frozen=True)
class TierModelTarget:
    model: str
    effort: str | None = None

    def __post_init__(self) -> None:
        if not str(self.model).strip():
            raise ProviderLocalConfigError("model must be a non-empty string")
        if self.effort is not None:
            if str(self.effort) not in CODEX_EFFORT_VALUES:
                raise ProviderLocalConfigError(
                    f"effort must be one of: {', '.join(sorted(CODEX_EFFORT_VALUES))}"
                )

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return self.model == other and self.effort is None
        if isinstance(other, TierModelTarget):
            return self.model == other.model and self.effort == other.effort
        return False

    def __str__(self) -> str:
        return self.model


@dataclass(frozen=True)
class ProviderModelConfig:
    provider: str
    executable: str
    models: Mapping[str, TierModelTarget]

    def __post_init__(self) -> None:
        normalized: dict[str, TierModelTarget] = {}
        for tier, raw_target in self.models.items():
            if isinstance(raw_target, TierModelTarget):
                normalized[str(tier)] = raw_target
            elif isinstance(raw_target, str):
                normalized[str(tier)] = TierModelTarget(model=str(raw_target).strip(), effort=None)
            elif isinstance(raw_target, Mapping):
                effort_val = raw_target.get("effort")
                normalized[str(tier)] = TierModelTarget(
                    model=str(raw_target.get("model", "")).strip(),
                    effort=str(effort_val).strip() if effort_val is not None else None,
                )
            else:
                raise ProviderLocalConfigError(f"invalid model target for tier: {tier}")
        object.__setattr__(self, "models", MappingProxyType(normalized))

    def selection_mode(self, tier: str) -> str:
        try:
            target = self.models[tier]
        except KeyError as error:
            raise ProviderLocalConfigError(f"missing model tier: {tier}") from error
        return "provider_default" if target.model == PROVIDER_DEFAULT else "explicit"


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
            raw_target = models[tier]
            if isinstance(raw_target, str):
                model_str = raw_target.strip()
                effort_str = None
                if not model_str:
                    raise ProviderLocalConfigError(f"model tier {tier} must be a non-empty string")
            elif isinstance(raw_target, Mapping):
                unknown_tier_keys = set(raw_target) - {"model", "effort"}
                if unknown_tier_keys:
                    raise ProviderLocalConfigError(
                        f"unsupported keys in tier {tier}: {', '.join(sorted(unknown_tier_keys))}"
                    )
                model_raw = raw_target.get("model")
                if not isinstance(model_raw, str) or not model_raw.strip():
                    raise ProviderLocalConfigError(f"model tier {tier} requires non-empty model")
                model_str = model_raw.strip()
                effort_raw = raw_target.get("effort")
                if effort_raw is not None:
                    if not isinstance(effort_raw, str) or not effort_raw.strip():
                        raise ProviderLocalConfigError(f"effort in tier {tier} must be a string")
                    effort_str = effort_raw.strip()
                    if model_str == PROVIDER_DEFAULT:
                        raise ProviderLocalConfigError(
                            "provider_default cannot declare an effort"
                        )
                    if name != "codex":
                        raise ProviderLocalConfigError(
                            "effort is only supported for codex"
                        )
                    if effort_str not in CODEX_EFFORT_VALUES:
                        raise ProviderLocalConfigError(
                            f"effort must be one of: {', '.join(sorted(CODEX_EFFORT_VALUES))}"
                        )
                else:
                    effort_str = None
            else:
                raise ProviderLocalConfigError(
                    f"model tier {tier} must be a string or mapping"
                )

            if model_str == PROVIDER_DEFAULT:
                if effort_str is not None:
                    raise ProviderLocalConfigError(
                        "provider_default cannot declare an effort"
                    )
                if name != "antigravity":
                    raise ProviderLocalConfigError(
                        "provider_default is only supported for antigravity"
                    )
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
            {
                str(tier): (
                    TierModelTarget(
                        model=str(raw["model"]).strip(),
                        effort=str(raw["effort"]).strip() if raw.get("effort") is not None else None,
                    )
                    if isinstance(raw, Mapping)
                    else TierModelTarget(model=str(raw).strip(), effort=None)
                )
                for tier, raw in entry["models"].items()
            },
        )
        for name, entry in loaded["providers"].items()
    }
    return MappingProxyType(providers)
