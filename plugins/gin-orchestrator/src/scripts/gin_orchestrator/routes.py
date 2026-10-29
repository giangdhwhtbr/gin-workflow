from __future__ import annotations

from collections.abc import Mapping, Sequence

from workflow_core.ext import (
    AssignmentManifest,
    AssignmentRequest,
    AssignmentResolutionError,
    DEFAULT_CATALOGS,
    EffectiveConfig,
    PROVIDER_DEFAULT,
    PROVIDER_DEFAULT_PROVIDERS,
    ProviderModelConfig,
    RouteCandidate,
    catalog_for,
    default_provider_model_config,
    map_route,
    route_diagnostics,
    tier_of,
    validate_plan_assignments,
)
from .config import roles


def resolve_assignment(
    request: AssignmentRequest,
    config: EffectiveConfig,
    local: Mapping[str, ProviderModelConfig],
    source_harness: str | None = None,
) -> tuple[RouteCandidate, ...]:
    """Resolve one role/tier without checking mutable provider availability.

    The request's model and effort are a route in `source_harness`'s catalog (default: the main
    harness); that harness keeps the route, and every other provider gets it mapped by rank.
    """
    all_roles = roles(config)
    role = all_roles.get(request.provider_role) if isinstance(all_roles, Mapping) else None
    if not isinstance(role, Mapping):
        raise AssignmentResolutionError(f"unknown provider role: {request.provider_role}")

    source_harness = source_harness or request.main_harness
    if source_harness not in DEFAULT_CATALOGS:
        raise AssignmentResolutionError(f"unknown provider: {source_harness}")
    source = catalog_for(config, source_harness)
    diagnostics = route_diagnostics(source, request.model, request.effort)
    if diagnostics:
        raise AssignmentResolutionError("; ".join(diagnostics))
    tier = tier_of(source, request.model)

    by_tier = role.get("by_tier") or {}
    preferred = tuple(by_tier.get(tier) or role.get("preferred", ()))
    fallback = tuple(role.get("fallback", ()))
    ordered: list[tuple[str, bool]] = []
    seen: set[str] = set()
    for alias, is_fallback in (
        *((name, False) for name in preferred),
        *((name, True) for name in fallback),
    ):
        provider = request.main_harness if alias == "main_harness" else str(alias)
        if provider in seen:
            continue
        seen.add(provider)
        ordered.append((provider, is_fallback))
    if not ordered:
        raise AssignmentResolutionError(f"provider role has no candidates: {request.provider_role}")

    candidates: list[RouteCandidate] = []
    errors: list[str] = []
    for provider, is_fallback in ordered:
        provider_config = local.get(provider)
        if provider_config is None:
            if config.get("provider_mode") == "single" and provider == request.main_harness and provider in DEFAULT_CATALOGS:
                provider_config = default_provider_model_config(provider)
            else:
                errors.append(f"missing local provider mapping: {provider}")
                continue
        if provider not in DEFAULT_CATALOGS:
            errors.append(f"unknown provider: {provider}")
            continue

        if provider == source_harness:
            model = request.model
            effort = request.effort
        else:
            target = catalog_for(config, provider)
            model, effort = map_route(source, target, request.model, request.effort)

        if model == PROVIDER_DEFAULT and provider not in PROVIDER_DEFAULT_PROVIDERS:
            errors.append("provider_default is only supported for antigravity and opencode")
            continue
        candidates.append(RouteCandidate(provider, str(model), is_fallback, effort=effort))
    if errors:
        raise AssignmentResolutionError("; ".join(errors))
    return tuple(candidates)


def resolve_all_assignments(
    requests: Sequence[AssignmentRequest],
    config: EffectiveConfig,
    local: Mapping[str, ProviderModelConfig],
) -> tuple[AssignmentManifest, ...]:
    """Resolve a complete workflow batch without performing durable writes."""
    errors = validate_plan_assignments(requests, config)
    if errors:
        raise AssignmentResolutionError("; ".join(errors))
    manifests: list[AssignmentManifest] = []
    resolution_errors: list[str] = []
    for request in requests:
        if not request.workflow_id.strip():
            resolution_errors.append(
                f"workflow_id is required for batch assignment: {request.task_id}"
            )
            continue
        try:
            candidates = resolve_assignment(request, config, local)
        except AssignmentResolutionError as error:
            resolution_errors.append(f"{request.task_id}: {error}")
        else:
            manifests.append(
                AssignmentManifest(request.workflow_id, request, candidates)
            )
    if resolution_errors:
        raise AssignmentResolutionError("; ".join(resolution_errors))
    return tuple(manifests)
