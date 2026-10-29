from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping


@dataclass(frozen=True)
class Catalog:
    models: tuple[str, ...]   # weakest to strongest, non-empty
    efforts: tuple[str, ...]  # lowest to highest, may be empty


DEFAULT_CATALOGS: Mapping[str, Catalog] = MappingProxyType({
    "claude": Catalog(("haiku", "sonnet", "opus"), ("low", "medium", "high", "xhigh", "max")),
    "codex": Catalog(("gpt-6-astra",), ("low", "medium", "high", "xhigh")),
    "antigravity": Catalog(("provider_default",), ()),
    "opencode": Catalog(("provider_default",), ()),
})


def catalog_for(config: Mapping[str, Any], harness: str) -> Catalog:
    if harness not in DEFAULT_CATALOGS:
        raise KeyError(f"unknown harness: {harness}")
    models_config = config.get("models")
    if isinstance(models_config, Mapping) and harness in models_config:
        entry = models_config[harness]
        models = tuple(entry["models"])
        efforts = tuple(entry.get("efforts") or ())
        return Catalog(models, efforts)
    return DEFAULT_CATALOGS[harness]


def route_diagnostics(catalog: Catalog, model: str, effort: str | None) -> list[str]:
    diagnostics: list[str] = []
    if model not in catalog.models:
        diagnostics.append(
            f"model '{model}' is not in the catalog; allowed: {', '.join(catalog.models)}"
        )
    if effort is not None:
        if not catalog.efforts:
            diagnostics.append(f"effort '{effort}' given, but the catalog lists no efforts")
        elif effort not in catalog.efforts:
            diagnostics.append(
                f"effort '{effort}' is not in the catalog; allowed: {', '.join(catalog.efforts)}"
            )
    return diagnostics


def tier_of(catalog: Catalog, model: str) -> str:
    if len(catalog.models) == 1:
        return "medium"
    index = catalog.models.index(model)
    if index == 0:
        return "low"
    if index == len(catalog.models) - 1:
        return "high"
    return "medium"


def map_index(position: int, source_length: int, target_length: int) -> int:
    if source_length == 1:
        return (target_length - 1) // 2
    return (2 * position * (target_length - 1) + (source_length - 1)) // (2 * (source_length - 1))


def map_route(
    source: Catalog,
    target: Catalog,
    model: str,
    effort: str | None,
) -> tuple[str, str | None]:
    source_model_idx = source.models.index(model)
    target_model_idx = map_index(source_model_idx, len(source.models), len(target.models))
    target_model = target.models[target_model_idx]

    if not target.efforts or effort is None:
        target_effort = None
    elif effort in target.efforts:
        target_effort = effort
    else:
        source_effort_idx = source.efforts.index(effort)
        target_effort_idx = map_index(source_effort_idx, len(source.efforts), len(target.efforts))
        target_effort = target.efforts[target_effort_idx]

    return target_model, target_effort


def escalate(catalog: Catalog, model: str, effort: str | None) -> tuple[str, str | None] | None:
    model_idx = catalog.models.index(model)
    if model_idx < len(catalog.models) - 1:
        return (catalog.models[model_idx + 1], effort)
    if effort is None or not catalog.efforts:
        return None
    effort_idx = catalog.efforts.index(effort)
    if effort_idx < len(catalog.efforts) - 1:
        return (catalog.models[model_idx], catalog.efforts[effort_idx + 1])
    return None
