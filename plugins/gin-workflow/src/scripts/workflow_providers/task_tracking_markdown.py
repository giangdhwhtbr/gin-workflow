"""Task tracking over the Markdown store (`workflow_core.task_markdown`), for repositories without Beads."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from workflow_core.ext import task_markdown

from .contracts import (
    ProviderBase,
    ProviderResult,
    TaskClosureRequest,
    TaskCreateRequest,
    TaskDependencyRecord,
    TaskPreflight,
    TaskReadiness,
    TaskRecord,
    TaskSyncRequest,
    TaskSyncResult,
    normalize_task_changes,
    validate_task_attributes,
    validate_task_status,
)
from .task_tracking import BeadsTaskTrackingProvider, _closure_note


class MarkdownTaskTrackingProvider(ProviderBase):
    provider_name = "markdown"
    provider_type = "task_tracking"
    capabilities = frozenset(
        {"task.create", "task.read", "task.update", "task.close", "task.dependency", "task.readiness",
         "task.preflight"}
    )

    def __init__(self, repository_root: Path) -> None:
        super().__init__()
        self.repository_root = Path(repository_root).resolve()

    def _run(self, *argv: str) -> ProviderResult[Any]:
        value = task_markdown.query(self.repository_root, argv)
        return ProviderResult.invalid(f"markdown task {argv[0]} failed") if value is None else ProviderResult.success(value)

    def _record(self, *argv: str) -> ProviderResult[TaskRecord]:
        ran = self._run(*argv)
        return ran if ran.value is None else BeadsTaskTrackingProvider._task(ran.value)

    def create_task(self, request: TaskCreateRequest, *, idempotency_key: str) -> ProviderResult[TaskRecord]:
        if not request.title.strip() or not idempotency_key:
            return ProviderResult.invalid("title and idempotency_key are required")
        if error := validate_task_status(request.status) or validate_task_attributes(request.attributes):
            return ProviderResult.invalid(error)
        if replay := self._replay("create_task", idempotency_key, request):
            return replay
        # `--flag=value` keeps a value that starts with "-" from being parsed as an option.
        argv = ["create", f"--title={request.title}", f"--status={request.status}",
                f"--description={request.description}"]
        if request.notes:
            argv.append("--notes=" + "\n".join(request.notes))
        if request.acceptance_criteria:
            argv.append("--acceptance=" + "\n".join(request.acceptance_criteria))
        argv += [f"--{key}={value}" for key, value in sorted(request.attributes.items())]
        return self._remember("create_task", idempotency_key, request, self._record(*argv))

    def read_task(self, task_id: str) -> ProviderResult[TaskRecord]:
        return self._record("show", task_id) if task_id.strip() else ProviderResult.invalid("task_id is required")

    def update_task(
        self, task_id: str, changes: Mapping[str, Any], *, idempotency_key: str
    ) -> ProviderResult[TaskRecord]:
        if not task_id.strip() or not changes or not idempotency_key:
            return ProviderResult.invalid("task_id, changes, and idempotency_key are required")
        normalized, error = normalize_task_changes(changes)
        if error:
            return ProviderResult.invalid(error)
        if replay := self._replay("update_task", idempotency_key, (task_id, changes)):
            return replay
        argv = ["update", task_id]
        for key, value in normalized.items():
            flag = "acceptance" if key == "acceptance_criteria" else key
            argv.append(f"--{flag}=" + ("\n".join(value) if isinstance(value, tuple) else str(value)))
        return self._remember("update_task", idempotency_key, (task_id, changes), self._record(*argv))

    def close_task(self, request: TaskClosureRequest, *, idempotency_key: str) -> ProviderResult[TaskRecord]:
        if not request.task_id.strip() or not request.closure_reason.strip() or not request.acceptance_evidence \
                or not idempotency_key:
            return ProviderResult.invalid(
                "task_id, closure_reason, acceptance_evidence, and idempotency_key are required"
            )
        if replay := self._replay("close_task", idempotency_key, request):
            return replay
        current = self.read_task(request.task_id)
        if current.value is None:
            return current
        matches = (current.value.acceptance_evidence, current.value.closure_reason) == (
            request.acceptance_evidence, request.closure_reason)
        if current.value.status == "closed":
            if matches:
                return ProviderResult.success(current.value, idempotent=True)
            return ProviderResult.invalid("closed task provenance does not match closure request")
        if not matches:
            noted = self._run("update", request.task_id, f"--append-notes={_closure_note(request)}")
            if noted.value is None:
                return noted
        closed = self._run("close", request.task_id, f"--reason={request.closure_reason}")
        if closed.value is None:
            return closed
        return self._remember("close_task", idempotency_key, request, self.read_task(request.task_id))

    def add_dependency(
        self, dependency: TaskDependencyRecord, *, idempotency_key: str
    ) -> ProviderResult[TaskDependencyRecord]:
        if not idempotency_key or dependency.dependency_type != "blocks":
            return ProviderResult.invalid("valid blocking dependency and idempotency_key are required")
        if replay := self._replay("add_dependency", idempotency_key, dependency):
            return replay
        added = self._run("dep", "add", dependency.task_id, dependency.depends_on_task_id)
        result = added if added.value is None else ProviderResult.success(dependency)
        return self._remember("add_dependency", idempotency_key, dependency, result)

    def readiness(self, task_id: str) -> ProviderResult[TaskReadiness]:
        shown = self.read_task(task_id)
        if shown.value is None:
            return shown
        blocked = self._run("blocked")
        if blocked.value is None:
            return blocked
        blockers = next((tuple(row["blocked_by"]) for row in blocked.value if row["id"] == task_id), ())
        return ProviderResult.success(TaskReadiness(task_id, shown.value.status == "open" and not blockers, blockers))

    def preflight(self) -> ProviderResult[TaskPreflight]:
        return ProviderResult.success(TaskPreflight("markdown", "1", self.capabilities, True))

    def sync(self, request: TaskSyncRequest, *, idempotency_key: str, **_: Any) -> ProviderResult[TaskSyncResult]:
        return ProviderResult.unavailable("markdown task tracking has no sync; task files are local to this checkout")
