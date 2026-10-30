"""Resolve portable plan guidance into machine-local provider candidates."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

from .atomic import atomic_write_text
from .catalog import DEFAULT_CATALOGS, catalog_for, route_diagnostics
from .checkout import main_checkout
from .configuration import require_yaml
from .locking import file_lock
from .provider_config import PROVIDER_DEFAULT, PROVIDER_DEFAULT_PROVIDERS


class AssignmentResolutionError(ValueError):
    """Raised when approved plan guidance cannot resolve to configured routes."""


@dataclass(frozen=True)
class AssignmentRequest:
    task_id: str
    provider_role: str
    model: str
    effort: str | None
    main_harness: str
    workflow_id: str = ""

    def __post_init__(self) -> None:
        for field_name in ("task_id", "provider_role", "model", "main_harness"):
            if not str(getattr(self, field_name)).strip():
                raise AssignmentResolutionError(f"{field_name} is required")


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

        def route_payload(candidate: RouteCandidate) -> dict[str, Any]:
            payload: dict[str, Any] = {
                "provider": candidate.provider,
                "selection_mode": candidate.selection_mode,
            }
            if candidate.selection_mode == "explicit":
                payload["model"] = candidate.model
                payload["effort"] = candidate.effort
            return payload

        return {
            "task_id": self.request.task_id,
            "requested": {
                "provider_role": self.request.provider_role,
                "model": self.request.model,
                "effort": self.request.effort,
            },
            "resolved": route_payload(primary),
            "fallback": [route_payload(candidate) for candidate in fallbacks],
            "escalations": [],
        }


def validate_plan_assignments(
    tasks: Sequence[Mapping[str, Any] | AssignmentRequest],
    config: Mapping[str, Any],
    harness: str | None = None,
) -> list[str]:
    """Validate portable role, model, and effort guidance against the main harness's catalog."""
    config_dict = config.to_dict() if hasattr(config, "to_dict") else dict(config)
    routing = config_dict.get("routing", {}) if isinstance(config_dict, Mapping) else {}
    roles = routing.get("roles", {}) if isinstance(routing, Mapping) else {}
    orchestrator = config_dict.get("orchestrator", {}) if isinstance(config_dict, Mapping) else {}
    orchestrator_roles = orchestrator.get("roles", {}) if isinstance(orchestrator, Mapping) else {}
    configured_roles = set(roles.keys() if isinstance(roles, Mapping) else ()) | set(
        orchestrator_roles.keys() if isinstance(orchestrator_roles, Mapping) else ()
    )

    harness = harness or config_dict.get("harness") or "claude"
    try:
        catalog = catalog_for(config_dict, harness)
    except KeyError:
        return [f"unknown harness: {harness}"]

    errors: list[str] = []
    for index, task in enumerate(tasks):
        if isinstance(task, AssignmentRequest):
            task_id = task.task_id or f"task-{index + 1}"
            role = task.provider_role
            model = task.model
            effort = task.effort
            has_reasoning = False
        elif isinstance(task, Mapping):
            task_id = str(task.get("task_id", "")).strip() or f"task-{index + 1}"
            role = str(task.get("provider_role", "")).strip()
            model = task.get("model")
            effort = task.get("effort")
            has_reasoning = "reasoning" in task and model is None
        else:
            raise TypeError("plan assignment tasks must be mappings or AssignmentRequest values")

        if role not in configured_roles:
            errors.append(f"track {task_id}: unknown provider role: {role}")

        if has_reasoning:
            errors.append(f"track {task_id}: reasoning is replaced by model and effort")
        else:
            for diag in route_diagnostics(catalog, str(model or ""), effort):
                errors.append(f"track {task_id}: {diag}")

    return errors


def resolve_main_harness(request: AssignmentRequest) -> tuple[RouteCandidate, ...]:
    """Single-harness route: the main harness at the requested model and effort."""
    if request.main_harness not in DEFAULT_CATALOGS:
        raise AssignmentResolutionError(f"unknown main harness: {request.main_harness}")
    return (RouteCandidate(request.main_harness, request.model, False, effort=request.effort),)


_SAFE_WORKFLOW_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")


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
    with file_lock(lock_path):
        assignments: dict[str, dict[str, object]] = {}
        if path.is_file():
            try:
                current = yaml.safe_load(path.read_text(encoding="utf-8"))
            except (UnicodeDecodeError, yaml.YAMLError) as error:
                raise AssignmentResolutionError(
                    f"invalid existing assignment manifest: {error}"
                ) from error
            if not isinstance(current, Mapping):
                raise AssignmentResolutionError("existing assignment manifest must be a mapping")
            if "tracks" in current and isinstance(current["tracks"], Mapping):
                for tid, entry in current["tracks"].items():
                    if isinstance(entry, Mapping):
                        d = dict(entry)
                        d["task_id"] = tid
                        assignments[tid] = d
            if "assignments" in current and isinstance(current["assignments"], (list, tuple)):
                for assignment in current["assignments"]:
                    if isinstance(assignment, Mapping) and assignment.get("task_id"):
                        assignments[str(assignment["task_id"])] = dict(assignment)
        for entry in entries:
            task_id = str(entry.get("task_id") if isinstance(entry, Mapping) else "").strip()
            if not task_id:
                raise AssignmentResolutionError("assignment entry requires task_id")
            assignments[task_id] = dict(entry)
        tracks_map: dict[str, dict[str, object]] = {}
        assignments_list: list[dict[str, object]] = []
        for task_id in sorted(assignments):
            entry = assignments[task_id]
            entry.setdefault("escalations", [])
            assignments_list.append(entry)
            tracks_map[task_id] = {
                "requested": entry.get("requested", {}),
                "resolved": entry.get("resolved", {}),
                "fallback": entry.get("fallback", []),
                "escalations": entry.get("escalations", []),
            }
        payload = {
            "workflow_id": workflow_id,
            "assignments": assignments_list,
            "tracks": tracks_map,
        }
        content = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
        atomic_write_text(path, content)
    return path


def write_assignment_manifest(repository: Path, manifest: AssignmentManifest) -> Path:
    """Atomically write a deterministic, disposable assignment preview."""
    return write_assignments(repository, manifest.workflow_id, [manifest.to_dict()])
