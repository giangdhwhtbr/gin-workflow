from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Any

from workflow_core.ext import (
    ProviderLocalConfigError,
    ProviderModelConfig,
    SUPPORTED_CONFIG_VERSIONS,
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
        if "models" in raw_entry:
            raise ProviderLocalConfigError(
                "orchestrator.local.yaml models moved to models: in config.yaml; run gin-workflow setup update --to-version 2.9 --approve"
            )
        unknown = set(raw_entry) - {"executable"}
        if unknown:
            raise ProviderLocalConfigError(
                f"unsupported provider fields for {name}: {', '.join(sorted(unknown))}"
            )
        executable = raw_entry.get("executable")
        if not isinstance(executable, str) or not executable.strip():
            raise ProviderLocalConfigError(f"provider {name} requires executable")


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
            provider=str(name),
            executable=str(entry["executable"]).strip(),
        )
        for name, entry in loaded["providers"].items()
    }
    return MappingProxyType(providers)
