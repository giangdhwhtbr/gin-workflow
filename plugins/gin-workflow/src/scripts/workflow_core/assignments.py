"""Resolve portable plan guidance into machine-local provider candidates."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any, Iterator, Sequence

from .atomic import atomic_write_text
from .checkout import main_checkout
from .configuration import require_yaml
from .models import EffectiveConfig
from .provider_config import (
    PROVIDER_DEFAULT,
    PROVIDER_DEFAULT_PROVIDERS,
    ProviderModelConfig,
    REASONING_TIERS,
)


class AssignmentResolutionError(ValueError):
    """Raised when approved plan guidance cannot resolve to configured routes."""


@dataclass(frozen=True)
class AssignmentValidationError:
    task_id: str
    field: str
    message: str


@dataclass(frozen=True)
class AssignmentRequest:
    task_id: str
    provider_role: str
    reasoning: str
    main_harness: str
    workflow_id: str = ""

    def __post_init__(self) -> None:
        for field_name in ("task_id", "provider_role", "main_harness"):
            if not str(getattr(self, field_name)).strip():
                raise AssignmentResolutionError(f"{field_name} is required")
        if self.reasoning not in REASONING_TIERS:
            raise AssignmentResolutionError(
                f"reasoning must be one of: {', '.join(REASONING_TIERS)}"
            )


@dataclass(frozen=True)
class RouteCandidate:
    provider: str
    model: str
    fallback: bool
    effort: str | None = None

    def __post_init__(self) -> None:
        if self.model == PROVIDER_DEFAULT and self.provider not in PROVIDER_DEFAULT_PROVIDERS:
            raise AssignmentResolutionError(
                "provider_default is only supported for antigravity and opencode"
            )
        if self.model == PROVIDER_DEFAULT and self.effort is not None:
            raise AssignmentResolutionError(
                "provider_default cannot declare an effort"
            )
        if self.effort is not None and self.provider != "codex":
            raise AssignmentResolutionError(
                "effort is only supported for codex"
            )

    @property
    def selection_mode(self) -> str:
        return "provider_default" if self.model == PROVIDER_DEFAULT else "explicit"


@dataclass(frozen=True)
class AssignmentManifest:
    workflow_id: str
    request: AssignmentRequest
    candidates: tuple[RouteCandidate, ...]

    def __post_init__(self) -> None:
        if not self.workflow_id.strip():
            raise AssignmentResolutionError("workflow_id is required")
        if not self.candidates:
            raise AssignmentResolutionError("assignment requires at least one route candidate")
        object.__setattr__(self, "candidates", tuple(self.candidates))

    def to_dict(self) -> dict[str, object]:
        primary, *fallbacks = self.candidates
        def route_payload(candidate: RouteCandidate) -> dict[str, str]:
            payload = {
                "provider": candidate.provider,
                "selection_mode": candidate.selection_mode,
            }
            if candidate.selection_mode == "explicit":
                payload["model"] = candidate.model
                if candidate.effort is not None:
                    payload["effort"] = candidate.effort
            return payload

        return {
            "task_id": self.request.task_id,
            "requested": {
                "provider_role": self.request.provider_role,
                "reasoning": self.request.reasoning,
            },
            "resolved": route_payload(primary),
            "fallback": [route_payload(candidate) for candidate in fallbacks],
        }


def _task_value(task: Mapping[str, Any] | AssignmentRequest, field: str) -> str:
    value = getattr(task, field) if isinstance(task, AssignmentRequest) else task.get(field, "")
    return str(value).strip()


def validate_plan_assignments(
    tasks: Sequence[Mapping[str, Any] | AssignmentRequest],
    config: EffectiveConfig,
) -> tuple[AssignmentValidationError, ...]:
    """Return every portable role/tier error without consulting machine-local state."""
    routing = config.get("routing", {})
    roles = routing.get("roles", {}) if isinstance(routing, Mapping) else {}
    if not isinstance(roles, Mapping):
        roles = {}
    errors: list[AssignmentValidationError] = []
    for index, task in enumerate(tasks):
        if not isinstance(task, (Mapping, AssignmentRequest)):
            raise TypeError("plan assignment tasks must be mappings or AssignmentRequest values")
        task_id = _task_value(task, "task_id") or f"task-{index + 1}"
        role = _task_value(task, "provider_role")
        reasoning = _task_value(task, "reasoning")
        if role not in roles:
            errors.append(
                AssignmentValidationError(task_id, "provider_role", f"unknown provider role: {role}")
            )
        if reasoning not in REASONING_TIERS:
            errors.append(
                AssignmentValidationError(
                    task_id,
                    "reasoning",
                    f"reasoning must be one of: {', '.join(REASONING_TIERS)}",
                )
            )
    return tuple(errors)


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

    preferred = tuple(role.get("preferred", ()))
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


_SAFE_WORKFLOW_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")


@contextmanager
def _manifest_lock(path: Path) -> Iterator[None]:
    import fcntl

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def write_assignment_manifest(repository: Path, manifest: AssignmentManifest) -> Path:
    """Atomically write a deterministic, disposable assignment preview."""
    if not _SAFE_WORKFLOW_ID.fullmatch(manifest.workflow_id):
        raise AssignmentResolutionError("workflow_id contains unsafe path characters")
    path = (
        main_checkout(Path(repository).resolve())
        / ".agent-workflow/runtime/assignments"
        / f"{manifest.workflow_id}.yaml"
    )
    yaml = require_yaml()
    lock_path = path.with_name(f".{path.name}.lock")
    with _manifest_lock(lock_path):
        assignments: dict[str, Mapping[str, object]] = {}
        if path.is_file():
            try:
                current = yaml.safe_load(path.read_text(encoding="utf-8"))
            except (UnicodeDecodeError, yaml.YAMLError) as error:
                raise AssignmentResolutionError(
                    f"invalid existing assignment manifest: {error}"
                ) from error
            if not isinstance(current, Mapping):
                raise AssignmentResolutionError("existing assignment manifest must be a mapping")
            for assignment in current.get("assignments", ()):
                if not isinstance(assignment, Mapping) or not assignment.get("task_id"):
                    raise AssignmentResolutionError("existing assignment entry is invalid")
                assignments[str(assignment["task_id"])] = assignment
        assignments[manifest.request.task_id] = manifest.to_dict()
        payload = {
            "workflow_id": manifest.workflow_id,
            "assignments": [assignments[task_id] for task_id in sorted(assignments)],
        }
        content = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
        atomic_write_text(path, content)
    return path
