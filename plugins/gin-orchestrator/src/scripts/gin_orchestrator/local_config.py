from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Any

from workflow_core.ext import (
    CODEX_EFFORT_VALUES,
    PROVIDER_DEFAULT,
    PROVIDER_DEFAULT_PROVIDERS,
    ProviderLocalConfigError,
    ProviderModelConfig,
    REASONING_TIERS,
    SUPPORTED_CONFIG_VERSIONS,
    TierModelTarget,
    main_checkout,
    require_yaml,
)

LOCAL_FILE = ".agent-workflow/orchestrator.local.yaml"


def validate_local_config(value: Mapping[str, Any]) -> None:
    if not isinstance(value, Mapping):
        raise ProviderLocalConfigError("provider local config must be a mapping")
    unknown_root = set(value) - {"schema_version", "providers"}
    if unknown_root:
        raise ProviderLocalConfigError(
            f"unsupported provider local fields: {', '.join(sorted(unknown_root))}"
        )
    if str(value.get("schema_version", "")) not in SUPPORTED_CONFIG_VERSIONS:
        raise ProviderLocalConfigError(
            f"provider local schema_version must be one of {SUPPORTED_CONFIG_VERSIONS!r}"
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
                if name not in PROVIDER_DEFAULT_PROVIDERS:
                    raise ProviderLocalConfigError(
                        "provider_default is only supported for antigravity and opencode"
                    )
        unknown_tiers = set(models) - set(REASONING_TIERS)
        if unknown_tiers:
            raise ProviderLocalConfigError(
                f"unsupported model tiers: {', '.join(sorted(unknown_tiers))}"
            )


def load_local_config(repository: Path) -> Mapping[str, ProviderModelConfig]:
    root = main_checkout(Path(repository).resolve())
    path = root / LOCAL_FILE
    if not path.is_file():
        raise ProviderLocalConfigError(f"provider local configuration does not exist: {path}")
    yaml = require_yaml()
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, yaml.YAMLError) as error:
        raise ProviderLocalConfigError(f"invalid provider local configuration: {error}") from error
    validate_local_config(loaded)
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
