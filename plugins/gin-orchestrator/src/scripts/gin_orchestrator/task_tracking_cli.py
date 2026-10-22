"""Task tracking through the `gin-workflow task` CLI, so the orchestrator never touches a task backend directly."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
from typing import Any, Callable, Mapping, Sequence

from .contracts import (
    OperationStatus,
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


Runner = Callable[[Sequence[str], Path], subprocess.CompletedProcess[str]]
_EVIDENCE_PREFIX = "gin:acceptance-evidence="
_CLOSURE_PREFIX = "gin:closure-reason="


def _default_runner(argv: Sequence[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=cwd, text=True, capture_output=True, check=False)


def _strings(value: object) -> tuple[str, ...]:
    if value is None or value == "":
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (list, tuple)):
        result = []
        for item in value:
            candidate = (
                item.get("id") or item.get("task_id") or item.get("depends_on_id")
                if isinstance(item, Mapping)
                else item
            )
            if candidate is not None and str(candidate).strip():
                result.append(str(candidate))
        return tuple(result)
    return (str(value),)


def _closure_note(request: TaskClosureRequest) -> str:
    return "\n".join(
        (
            _EVIDENCE_PREFIX + json.dumps(list(request.acceptance_evidence), separators=(",", ":")),
            _CLOSURE_PREFIX + json.dumps(request.closure_reason, separators=(",", ":")),
        )
    )


def _closure_provenance(notes: tuple[str, ...]) -> tuple[tuple[str, ...], str]:
    evidence: tuple[str, ...] = ()
    reason = ""
    for note in notes:
        for line in note.splitlines():
            try:
                if line.startswith(_EVIDENCE_PREFIX):
                    value = json.loads(line.removeprefix(_EVIDENCE_PREFIX))
                    evidence = _strings(value)
                elif line.startswith(_CLOSURE_PREFIX):
                    value = json.loads(line.removeprefix(_CLOSURE_PREFIX))
                    reason = value if isinstance(value, str) else ""
            except json.JSONDecodeError:
                continue
    return evidence, reason


def _task_record(raw: Any) -> ProviderResult[TaskRecord]:
    if isinstance(raw, list) and len(raw) == 1:
        raw = raw[0]
    if isinstance(raw, dict) and isinstance(raw.get("issue"), dict):
        raw = raw["issue"]
    if not isinstance(raw, dict):
        return ProviderResult.unavailable("gin-workflow task response did not contain a task object")
    task_id = raw.get("id") or raw.get("task_id")
    title = raw.get("title") or raw.get("name")
    if not task_id or not title:
        return ProviderResult.unavailable("gin-workflow task response is missing id or title")
    known = {
        "id", "task_id", "title", "name", "description", "status", "notes",
        "acceptance", "acceptance_criteria", "acceptance_evidence",
        "dependencies", "closure_reason",
    }
    notes = _strings(raw.get("notes"))
    marker_evidence, marker_reason = _closure_provenance(notes)
    return ProviderResult.success(
        TaskRecord(
            str(task_id),
            str(title),
            str(raw.get("description", "")),
            str(raw.get("status", "open")),
            {key: value for key, value in raw.items() if key not in known},
            notes,
            _strings(raw.get("acceptance_criteria") or raw.get("acceptance")),
            _strings(raw.get("acceptance_evidence")) or marker_evidence,
            _strings(raw.get("dependencies")),
            str(raw.get("closure_reason") or marker_reason),
        )
    )


class CliTaskTrackingProvider(ProviderBase):
    provider_name = "gin-workflow"
    provider_type = "task_tracking"
    capabilities = frozenset(
        {"task.create", "task.read", "task.update", "task.close", "task.dependency", "task.readiness",
         "task.preflight"}
    )

    def __init__(self, repository_root: Path, *, executable: str = "gin-workflow",
                 runner: Runner | None = None) -> None:
        super().__init__()
        self.repository_root = Path(repository_root).resolve()
        self.executable = executable
        self._runner = runner or _default_runner

    def _run(self, *argv: str) -> ProviderResult[Any]:
        try:
            completed = self._runner([self.executable, "task", *argv, "--json"], self.repository_root)
        except (OSError, subprocess.SubprocessError) as error:
            return ProviderResult.unavailable(f"{self.executable} unavailable: {error}")
        if completed.returncode:
            return ProviderResult.invalid(f"gin-workflow task {argv[0]} failed: {completed.stderr.strip()}")
        try:
            return ProviderResult.success(json.loads(completed.stdout))
        except json.JSONDecodeError as error:
            return ProviderResult.unavailable(f"gin-workflow task {argv[0]} returned invalid JSON: {error}")

    def _record(self, *argv: str) -> ProviderResult[TaskRecord]:
        ran = self._run(*argv)
        return ran if ran.value is None else _task_record(ran.value)

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
        ran = self._run("ready")
        if ran.status is OperationStatus.UNAVAILABLE:
            return ran
        return ProviderResult.success(
            TaskPreflight("gin-workflow", "1", self.capabilities, ran.value is not None, ran.message))

    def sync(self, request: TaskSyncRequest, *, idempotency_key: str, **_: Any) -> ProviderResult[TaskSyncResult]:
        return ProviderResult.invalid("sync is owned by the gin-workflow task backend")
