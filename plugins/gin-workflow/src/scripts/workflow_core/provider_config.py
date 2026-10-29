"""Machine-local native provider configuration outside portable config."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


DEFAULT_EXECUTABLES: Mapping[str, str] = MappingProxyType({
    "claude": "claude",
    "codex": "codex",
    "antigravity": "agy",
    "opencode": "opencode",
})
PROVIDER_DEFAULT = "provider_default"
PROVIDER_DEFAULT_PROVIDERS = frozenset({"antigravity", "opencode"})


class ProviderLocalConfigError(ValueError):
    """Raised when native executable/model mappings are missing or unsafe."""


@dataclass(frozen=True)
class ProviderModelConfig:
    provider: str
    executable: str


def default_provider_model_config(harness: str) -> ProviderModelConfig:
    if harness not in DEFAULT_EXECUTABLES:
        raise ProviderLocalConfigError(f"unknown harness for default provider mapping: {harness}")
    return ProviderModelConfig(
        provider=harness,
        executable=DEFAULT_EXECUTABLES[harness],
    )
