"""Beads task-tracking adapter. No other module shells out to ``bd``."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
from typing import Any, Callable, Mapping, Sequence

from .contracts import (
    ProviderBase,
    ProviderResult,
    SUPPORTED_TASK_ATTRIBUTES,
    TaskCreateRequest,
    TaskRecord,
    normalize_task_changes,
    validate_task_attributes,
    validate_task_status,
)


Runner = Callable[[Sequence[str], Path], subprocess.CompletedProcess[str]]


def _default_runner(argv: Sequence[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=cwd, text=True, capture_output=True, check=False)


class BeadsTaskTrackingProvider(ProviderBase):
    provider_name = "beads"
    provider_type = "task_tracking"
    capabilities = frozenset({"task.create", "task.read", "task.update"})

    def __init__(self, repository_root: Path, *, runner: Runner | None = None) -> None:
        available = runner is not None or shutil.which("bd") is not None
        super().__init__(available=available, health_detail="bd executable was not found" if not available else "")
        self.repository_root = Path(repository_root).resolve()
        self._runner = runner or _default_runner

    def _invoke(self, argv: Sequence[str]) -> ProviderResult[Any]:
        try:
            completed = self._runner(argv, self.repository_root)
        except (OSError, subprocess.SubprocessError) as error:
            return ProviderResult.unavailable(f"beads unavailable: {error}")
        if completed.returncode:
            detail = completed.stderr.strip() or completed.stdout.strip() or "unknown bd error"
            return ProviderResult.unavailable(f"beads unavailable: {detail}")
        try:
            return ProviderResult.success(json.loads(completed.stdout))
        except json.JSONDecodeError as error:
            return ProviderResult.unavailable(f"beads returned invalid JSON: {error}")

    @staticmethod
    def _task(raw: Any) -> ProviderResult[TaskRecord]:
        if isinstance(raw, list) and len(raw) == 1:
            raw = raw[0]
        if isinstance(raw, dict) and isinstance(raw.get("issue"), dict):
            raw = raw["issue"]
        if not isinstance(raw, dict):
            return ProviderResult.unavailable("beads response did not contain a task object")
        task_id = raw.get("id") or raw.get("task_id")
        title = raw.get("title") or raw.get("name")
        if not task_id or not title:
            return ProviderResult.unavailable("beads task response is missing id or title")
        known = {"id", "task_id", "title", "name", "description", "status"}
        return ProviderResult.success(
            TaskRecord(
                str(task_id),
                str(title),
                str(raw.get("description", "")),
                str(raw.get("status", "open")),
                {key: value for key, value in raw.items() if key not in known},
            )
        )

    def create_task(self, request: TaskCreateRequest, *, idempotency_key: str) -> ProviderResult[TaskRecord]:
        if guarded := self._guard():
            return guarded
        if replay := self._replay("create_task", idempotency_key, request):
            return replay
        if not request.title.strip() or not request.status.strip() or not idempotency_key:
            return ProviderResult.invalid("title, status, and idempotency_key are required")
        if error := validate_task_status(request.status):
            return ProviderResult.invalid(error)
        if error := validate_task_attributes(request.attributes):
            return ProviderResult.invalid(error)
        argv = ["bd", "create", request.title]
        if request.description:
            argv.extend(["--description", request.description])
        argv.extend(["--status", request.status])
        for attribute in sorted(SUPPORTED_TASK_ATTRIBUTES):
            if attribute in request.attributes:
                argv.extend([f"--{attribute}", str(request.attributes[attribute])])
        argv.append("--json")
        invoked = self._invoke(argv)
        if invoked.value is None:
            return invoked
        normalized = self._task(invoked.value)
        return self._remember("create_task", idempotency_key, request, normalized)

    def read_task(self, task_id: str) -> ProviderResult[TaskRecord]:
        if guarded := self._guard():
            return guarded
        if not task_id.strip():
            return ProviderResult.invalid("task_id is required")
        invoked = self._invoke(["bd", "show", task_id, "--json"])
        return invoked if invoked.value is None else self._task(invoked.value)

    def update_task(self, task_id: str, changes: Mapping[str, Any], *, idempotency_key: str) -> ProviderResult[TaskRecord]:
        if guarded := self._guard():
            return guarded
        if replay := self._replay("update_task", idempotency_key, (task_id, changes)):
            return replay
        if not task_id.strip() or not changes or not idempotency_key:
            return ProviderResult.invalid("task_id, changes, and idempotency_key are required")
        normalized_changes, error = normalize_task_changes(changes)
        if error:
            return ProviderResult.invalid(error)
        argv = ["bd", "update", task_id]
        for field, value in normalized_changes.items():
            argv.extend([f"--{field}", str(value)])
        argv.append("--json")
        invoked = self._invoke(argv)
        if invoked.value is None:
            return invoked
        normalized = self._task(invoked.value)
        return self._remember("update_task", idempotency_key, (task_id, changes), normalized)
