from __future__ import annotations

from collections.abc import Mapping, Sequence

from workflow_core.ext import (
    AssignmentManifest,
    AssignmentRequest,
    AssignmentResolutionError,
    DEFAULT_HARNESS_MODELS,
    EffectiveConfig,
    PROVIDER_DEFAULT,
    PROVIDER_DEFAULT_PROVIDERS,
    ProviderModelConfig,
    RouteCandidate,
    default_provider_model_config,
    validate_plan_assignments,
)


def resolve_assignment(
    request: AssignmentRequest,
    config: EffectiveConfig,
    local: Mapping[str, ProviderModelConfig],
) -> tuple[RouteCandidate, ...]:
    """Resolve one role/tier without checking mutable provider availability."""
    routing = config.get("routing", {})
    roles = routing.get("roles", {}) if isinstance(routing, Mapping) else {}
    role = roles.get(request.provider_role) if isinstance(roles, Mapping) else None
    if not isinstance(role, Mapping):
        raise AssignmentResolutionError(f"unknown provider role: {request.provider_role}")

    by_tier = role.get("by_tier") or {}
    preferred = tuple(by_tier.get(request.reasoning) or role.get("preferred", ()))
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
            if config.get("provider_mode") == "single" and provider == request.main_harness and provider in DEFAULT_HARNESS_MODELS:
                provider_config = default_provider_model_config(provider)
            else:
                errors.append(f"missing local provider mapping: {provider}")
                continue
        try:
            target = provider_config.models[request.reasoning]
        except KeyError:
            errors.append(
                f"missing {request.reasoning} reasoning model for provider: {provider}"
            )
            continue
        model = getattr(target, "model", str(target))
        effort = getattr(target, "effort", None)
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
        raise AssignmentResolutionError(
            "; ".join(f"{error.task_id}.{error.field}: {error.message}" for error in errors)
        )
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
