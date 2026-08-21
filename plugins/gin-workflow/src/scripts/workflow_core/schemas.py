"""Versioned JSON schemas and dependency-aware validation."""

from __future__ import annotations

from typing import Any, Mapping

from .models import DependencyUnavailableError


SUPPORTED_SCHEMA_VERSION = "2.3"

CONFIG_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["schema_version"],
    "properties": {
        "schema_version": {"const": SUPPORTED_SCHEMA_VERSION},
        "workflow_version": {"type": "string"},
        "setup_cli_version": {"type": "string"},
        "artifacts": {
            "type": "object",
            "propertyNames": {
                "enum": ["plans", "beads", "worktrees", "knowledge", "evidence", "runtime"]
            },
            "additionalProperties": {"type": "string", "minLength": 1},
        },
        "model_tiers": {
            "type": "object",
            "additionalProperties": {"type": "string", "minLength": 1},
        },
        "capabilities": {"type": "object"},
        "policy": {"type": "object"},
        "routing": {
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
                "review": {
                    "type": "object",
                    "properties": {
                        "role": {"type": "string", "minLength": 1},
                        "require_independent": {"type": "boolean"},
                        "allow_self_review_fallback": {"type": "boolean"},
                        "max_cycles": {"type": "integer", "minimum": 1},
                    },
                    "additionalProperties": False,
                },
            },
            "additionalProperties": False,
        },
    },
    "additionalProperties": True,
}

CONFIG_PROVENANCE_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["schema_version", "fields"],
    "properties": {
        "schema_version": {"const": SUPPORTED_SCHEMA_VERSION},
        "fields": {
            "type": "object",
            "additionalProperties": {"type": "string", "minLength": 1},
        },
    },
    "additionalProperties": False,
}

WORKFLOW_EVENT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["event_id", "event_type", "workflow_id", "timestamp", "task_id", "payload"],
    "properties": {
        "event_id": {"type": "string", "pattern": "^evt-[0-9a-f]{64}$"},
        "event_type": {"type": "string", "minLength": 1},
        "workflow_id": {"type": "string", "minLength": 1},
        "timestamp": {"type": "string", "minLength": 1},
        "task_id": {"type": ["string", "null"]},
        "payload": {"type": "object"},
        "actor": {"type": "string", "minLength": 1},
        "idempotency_key": {"type": "string", "minLength": 1},
    },
    "additionalProperties": False,
}

_CONTEXT_CATEGORY_SCHEMA = {"type": "array", "items": {}}
CONTEXT_MANIFEST_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["schema_version", "stage", "categories"],
    "properties": {
        "schema_version": {"const": SUPPORTED_SCHEMA_VERSION},
        "stage": {"type": "string", "minLength": 1},
        "categories": {
            "type": "object",
            "required": [
                "required",
                "conditional",
                "discoverable",
                "reference",
                "prohibited",
            ],
            "properties": {
                "required": _CONTEXT_CATEGORY_SCHEMA,
                "conditional": _CONTEXT_CATEGORY_SCHEMA,
                "discoverable": _CONTEXT_CATEGORY_SCHEMA,
                "reference": _CONTEXT_CATEGORY_SCHEMA,
                "prohibited": _CONTEXT_CATEGORY_SCHEMA,
            },
            "additionalProperties": False,
        },
    },
    "additionalProperties": False,
}

_APPROVAL_ACTIONS = [
    "commit",
    "push",
    "upgrade",
    "data_move",
    "disable_isolation",
    "current_branch_execution",
    "scope_change",
    "execution_strategy_change",
    "production_parallel_work",
]
APPROVAL_REQUEST_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["request_id", "action", "workflow_id", "reason", "details"],
    "properties": {
        "request_id": {"type": "string", "minLength": 1},
        "action": {"enum": _APPROVAL_ACTIONS},
        "workflow_id": {"type": "string", "minLength": 1},
        "reason": {"type": "string", "minLength": 1},
        "details": {"type": "object"},
    },
    "additionalProperties": False,
}

APPROVAL_DECISION_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["request_id", "status", "decided_by", "decided_at"],
    "properties": {
        "request_id": {"type": "string", "minLength": 1},
        "status": {"enum": ["approved", "denied"]},
        "decided_by": {"type": "string", "minLength": 1},
        "decided_at": {"type": "string", "minLength": 1},
        "rationale": {"type": "string"},
    },
    "additionalProperties": False,
}


def require_jsonschema():
    try:
        import jsonschema
    except ImportError as error:  # pragma: no cover - exercised in dependency-isolated packaging tests
        raise DependencyUnavailableError(
            "The 'jsonschema' package is required to validate gin-workflow configuration. "
            "Install it with: python3 -m pip install jsonschema"
        ) from error
    return jsonschema


def validate_instance(instance: Mapping[str, Any], schema: Mapping[str, Any], *, label: str) -> None:
    jsonschema = require_jsonschema()
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda item: list(item.absolute_path))
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        raise ValueError(f"{label} validation failed at {location}: {error.message}")


def validate_config_schema(config: Mapping[str, Any]) -> None:
    validate_instance(config, CONFIG_SCHEMA, label="configuration")


def validate_config_provenance(provenance: Mapping[str, Any]) -> None:
    validate_instance(provenance, CONFIG_PROVENANCE_SCHEMA, label="config provenance")


def validate_workflow_event(event: Mapping[str, Any]) -> None:
    validate_instance(event, WORKFLOW_EVENT_SCHEMA, label="workflow event")


def validate_context_manifest(manifest: Mapping[str, Any]) -> None:
    validate_instance(manifest, CONTEXT_MANIFEST_SCHEMA, label="context manifest")


def validate_approval_request(request: Mapping[str, Any]) -> None:
    validate_instance(request, APPROVAL_REQUEST_SCHEMA, label="approval request")


def validate_approval_decision(decision: Mapping[str, Any]) -> None:
    validate_instance(decision, APPROVAL_DECISION_SCHEMA, label="approval decision")
