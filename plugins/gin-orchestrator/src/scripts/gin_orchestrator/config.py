from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from workflow_core.ext import validate_instance

ORCHESTRATOR_DEFAULTS: Mapping[str, Mapping[str, Any]] = {
    "circuit_breaker": {"failure_threshold": 3},
    "queue": {"max_wait_seconds": 600},
    "worker": {"max_retries": 2},
}

ORCHESTRATOR_SCHEMA: Mapping[str, Any] = {
    "type": "object",
    "properties": {
        "roles": {
            "type": "object",
            "additionalProperties": {
                "type": "object",
                "required": ["preferred"],
                "properties": {
                    "preferred": {
                        "type": "array",
                        "minItems": 1,
                        "items": {"type": "string", "minLength": 1},
                    },
                    "fallback": {
                        "type": "array",
                        "items": {"type": "string", "minLength": 1},
                    },
                    "by_tier": {
                        "type": "object",
                        "properties": {
                            tier: {
                                "type": "array",
                                "minItems": 1,
                                "items": {"type": "string", "minLength": 1},
                            }
                            for tier in ("low", "medium", "high")
                        },
                        "additionalProperties": False,
                    },
                    "require_independent": {"type": "boolean"},
                },
                "additionalProperties": False,
            },
        },
        "concurrency": {
            "type": "object",
            "additionalProperties": {"type": "integer", "minimum": 1},
        },
        "queue": {
            "type": "object",
            "properties": {
                "max_wait_seconds": {"type": "number", "minimum": 0},
            },
            "additionalProperties": False,
        },
        "worker": {
            "type": "object",
            "properties": {
                "timeout_seconds": {"type": "number", "exclusiveMinimum": 0},
                "max_retries": {"type": "integer", "minimum": 0},
            },
            "additionalProperties": False,
        },
        "circuit_breaker": {
            "type": "object",
            "properties": {
                "failure_threshold": {"type": "integer", "minimum": 1},
                "cooldown_seconds": {"type": "number", "minimum": 0},
                "half_open_max_probes": {"type": "integer", "minimum": 1},
            },
            "additionalProperties": False,
        },
    },
    "additionalProperties": False,
}


def orchestrator_section(config: Mapping[str, Any]) -> dict[str, Any]:
    """Return defaults merged under config['orchestrator']."""
    raw = config.get("orchestrator")
    section = dict(raw) if isinstance(raw, Mapping) else {}
    for key, defaults in ORCHESTRATOR_DEFAULTS.items():
        if key not in section:
            section[key] = dict(defaults)
        elif isinstance(section[key], Mapping):
            section[key] = {**defaults, **section[key]}
    return section


def roles(config: Mapping[str, Any]) -> dict[str, Any]:
    """Return {**routing.roles, **orchestrator.roles}."""
    routing = config.get("routing")
    routing_roles = dict(routing.get("roles") or {}) if isinstance(routing, Mapping) else {}
    orchestrator = config.get("orchestrator")
    orchestrator_roles = dict(orchestrator.get("roles") or {}) if isinstance(orchestrator, Mapping) else {}
    return {**routing_roles, **orchestrator_roles}


def validate_orchestrator_config(config: Mapping[str, Any]) -> None:
    """Raise ValueError naming the first schema error and every unknown role provider."""
    orchestrator = config.get("orchestrator")
    if orchestrator is None:
        return
    if not isinstance(orchestrator, Mapping):
        raise ValueError("orchestrator must be a mapping")

    problems: list[str] = []
    try:
        validate_instance(orchestrator, ORCHESTRATOR_SCHEMA, label="orchestrator")
    except ValueError as error:
        problems.append(str(error))

    concurrency = orchestrator.get("concurrency")
    known_providers = set(concurrency) if isinstance(concurrency, Mapping) else set()
    harness = config.get("harness")
    if isinstance(harness, str) and harness:
        known_providers.add(harness)
    known_providers.add("main_harness")

    roles_map = orchestrator.get("roles")
    if isinstance(roles_map, Mapping):
        for role_name, role_def in roles_map.items():
            if not isinstance(role_def, Mapping):
                continue
            tiers = role_def.get("by_tier")
            lists = [role_def.get("preferred"), role_def.get("fallback"),
                     *(tiers.values() if isinstance(tiers, Mapping) else ())]
            all_providers = [p for items in lists if isinstance(items, list) for p in items]
            for provider in all_providers:
                if provider not in known_providers:
                    problems.append(
                        f"role '{role_name}' references unknown provider '{provider}'"
                    )

    if problems:
        raise ValueError("; ".join(problems))
