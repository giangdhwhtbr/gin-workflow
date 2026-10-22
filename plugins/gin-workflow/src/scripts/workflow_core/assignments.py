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
    DEFAULT_HARNESS_MODELS,
    PROVIDER_DEFAULT,
    PROVIDER_DEFAULT_PROVIDERS,
    REASONING_TIERS,
    default_provider_model_config,
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


def resolve_main_harness(request: AssignmentRequest) -> tuple[RouteCandidate, ...]:
    """Single-harness route: the main harness at the tier's default model."""
    if request.main_harness not in DEFAULT_HARNESS_MODELS:
        raise AssignmentResolutionError(f"unknown main harness: {request.main_harness}")
    target = default_provider_model_config(request.main_harness).models[request.reasoning]
    return (RouteCandidate(request.main_harness, target.model, False, effort=target.effort),)


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


def write_assignments(
    repository: Path,
    workflow_id: str,
    entries: Sequence[Mapping[str, object]],
) -> Path:
    """Atomically write and merge assignment entries by task_id under runtime."""
    if not _SAFE_WORKFLOW_ID.fullmatch(workflow_id):
        raise AssignmentResolutionError("workflow_id contains unsafe path characters")
    path = (
        main_checkout(Path(repository).resolve())
        / ".agent-workflow/runtime/assignments"
        / f"{workflow_id}.yaml"
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
        for entry in entries:
            task_id = str(entry.get("task_id") if isinstance(entry, Mapping) else "").strip()
            if not task_id:
                raise AssignmentResolutionError("assignment entry requires task_id")
            assignments[task_id] = entry
        payload = {
            "workflow_id": workflow_id,
            "assignments": [assignments[task_id] for task_id in sorted(assignments)],
        }
        content = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
        atomic_write_text(path, content)
    return path


def write_assignment_manifest(repository: Path, manifest: AssignmentManifest) -> Path:
    """Atomically write a deterministic, disposable assignment preview."""
    return write_assignments(repository, manifest.workflow_id, [manifest.to_dict()])
