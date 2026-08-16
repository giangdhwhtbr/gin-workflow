"""Bounded stage context manifests with safe serialization."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from types import MappingProxyType
from typing import Any, Mapping

from .models import freeze, thaw


CONTEXT_CATEGORIES = (
    "required",
    "conditional",
    "discoverable",
    "reference",
    "prohibited",
)

_EXCLUDED_KEYS = {
    "parent_context",
    "private_reasoning",
    "reasoning",
    "chain_of_thought",
    "history",
    "conversation_history",
    "unrelated_task",
    "unrelated_tasks",
}
_SECRET_PARTS = (
    "api_key",
    "apikey",
    "password",
    "passwd",
    "credential",
    "private_key",
    "secret",
    "token",
)
_PROHIBITED_CLASSIFICATIONS = {
    "secret",
    "private_reasoning",
    "chain_of_thought",
    "unrelated_task",
    "history",
    "parent_context",
}
_SECRET_LIKE_SCALAR = re.compile(
    r"(?:-----BEGIN [A-Z ]*PRIVATE KEY-----|\bsk-[A-Za-z0-9_-]{6,}|"
    r"\bgh[pousr]_[A-Za-z0-9]{6,}|\bxox[baprs]-)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ContextRequest:
    required: tuple[Any, ...] = ()
    conditional: tuple[Any, ...] = ()
    discoverable: tuple[Any, ...] = ()
    reference: tuple[Any, ...] = ()
    prohibited: tuple[Any, ...] = ()
    # Accepted at the boundary so callers can pass a broad request object, but
    # deliberately never transferred to ContextManifest.
    parent_context: Any = None

    def __post_init__(self) -> None:
        for category in CONTEXT_CATEGORIES:
            object.__setattr__(self, category, tuple(freeze(item) for item in getattr(self, category)))
        object.__setattr__(self, "parent_context", None)


def _redacted_entry(value: object) -> dict[str, Any]:
    result: dict[str, Any] = {"redacted": True}
    if isinstance(value, Mapping):
        for key in ("name", "type", "source", "path"):
            item = value.get(key)
            if isinstance(item, (str, int, float, bool)):
                result[key] = item
    return result


def _sanitize(value: object) -> object:
    if isinstance(value, Mapping):
        classification = str(
            value.get("classification", value.get("kind", value.get("type", "")))
        ).lower()
        if classification in _PROHIBITED_CLASSIFICATIONS:
            return _redacted_entry(value)
        result: dict[str, Any] = {}
        for raw_key, item in value.items():
            key = str(raw_key)
            normalized = key.lower().replace("-", "_")
            if normalized in _EXCLUDED_KEYS:
                continue
            if any(part in normalized for part in _SECRET_PARTS):
                result[key] = "[REDACTED]"
            else:
                result[key] = _sanitize(item)
        return result
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_sanitize(item) for item in value]
    if isinstance(value, str) and _SECRET_LIKE_SCALAR.search(value):
        return "[REDACTED]"
    return thaw(value)


@dataclass(frozen=True)
class ContextManifest:
    stage: str
    categories: Mapping[str, tuple[Any, ...]]
    schema_version: str = "2.2"

    def __post_init__(self) -> None:
        if not self.stage:
            raise ValueError("manifest stage is required")
        unknown = set(self.categories).difference(CONTEXT_CATEGORIES)
        if unknown:
            raise ValueError(f"unknown context categories: {', '.join(sorted(unknown))}")
        normalized = {
            category: tuple(freeze(item) for item in self.categories.get(category, ()))
            for category in CONTEXT_CATEGORIES
        }
        object.__setattr__(self, "categories", MappingProxyType(normalized))

    def to_dict(self) -> dict[str, Any]:
        serialized_categories: dict[str, list[Any]] = {}
        for category in CONTEXT_CATEGORIES:
            if category == "prohibited":
                serialized_categories[category] = [
                    _redacted_entry(item) for item in self.categories[category]
                ]
            else:
                serialized_categories[category] = [
                    _sanitize(item) for item in self.categories[category]
                ]
        return {
            "schema_version": self.schema_version,
            "stage": self.stage,
            "categories": serialized_categories,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)


def _coerce_request(request: ContextRequest | Mapping[str, Any]) -> ContextRequest:
    if isinstance(request, ContextRequest):
        return request
    if not isinstance(request, Mapping):
        raise TypeError("context request must be ContextRequest or a mapping")
    return ContextRequest(
        **{category: tuple(request.get(category, ())) for category in CONTEXT_CATEGORIES},
        parent_context=request.get("parent_context"),
    )


def create_context_manifest(
    stage: str, request: ContextRequest | Mapping[str, Any]
) -> ContextManifest:
    bounded = _coerce_request(request)
    return ContextManifest(
        stage=stage,
        categories={category: getattr(bounded, category) for category in CONTEXT_CATEGORIES},
    )
