"""Machine-local native provider configuration outside portable config."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any


REASONING_TIERS = ("low", "medium", "high")
PROVIDER_DEFAULT = "provider_default"
PROVIDER_DEFAULT_PROVIDERS = frozenset({"antigravity", "opencode"})
CODEX_EFFORT_VALUES = frozenset({"low", "medium", "high", "xhigh"})

DEFAULT_HARNESS_MODELS: Mapping[str, Mapping[str, Any]] = MappingProxyType({
    "claude": {
        "executable": "claude",
        "models": {"low": "haiku", "medium": "sonnet", "high": "opus"},
    },
    "antigravity": {
        "executable": "agy",
        "models": {
            "low": PROVIDER_DEFAULT,
            "medium": PROVIDER_DEFAULT,
            "high": PROVIDER_DEFAULT,
        },
    },
    "opencode": {
        "executable": "opencode",
        "models": {
            "low": PROVIDER_DEFAULT,
            "medium": PROVIDER_DEFAULT,
            "high": PROVIDER_DEFAULT,
        },
    },
    "codex": {
        "executable": "codex",
        "models": {
            "low": {"model": "gpt-6-astra", "effort": "low"},
            "medium": {"model": "gpt-6-astra", "effort": "medium"},
            "high": {"model": "gpt-6-astra", "effort": "high"},
        },
    },
})


def default_provider_config(harness: str) -> dict[str, Any]:
    if harness not in DEFAULT_HARNESS_MODELS:
        raise ProviderLocalConfigError(f"unknown harness for default provider mapping: {harness}")
    return {
        "executable": DEFAULT_HARNESS_MODELS[harness]["executable"],
        "models": dict(DEFAULT_HARNESS_MODELS[harness]["models"]),
    }


def default_provider_model_config(harness: str) -> ProviderModelConfig:
    data = default_provider_config(harness)
    return ProviderModelConfig(
        provider=harness,
        executable=data["executable"],
        models=data["models"],
    )


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
