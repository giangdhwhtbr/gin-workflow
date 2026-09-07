"""Capability-driven Beads task tracking adapter."""

from __future__ import annotations

from pathlib import Path
import json
import re
import shutil
import subprocess
from typing import Any, Callable, Mapping, Sequence

from workflow_core.approvals import ApprovalAction
from workflow_core.router import authorize_protected_action

from .contracts import (
    ProviderBase,
    ProviderResult,
    SUPPORTED_TASK_ATTRIBUTES,
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
_LONG_OPTION = re.compile(r"(?<![A-Za-z0-9_-])--[a-z0-9][a-z0-9-]*")
_SYNC_FLAGS = {"flush": "--flush-only", "pull": "--import-only", "merge": "--merge"}
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


def _strict_strings(value: object) -> tuple[str, ...] | None:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        return None
    result = []
    for item in value:
        candidate = (
            item.get("id") or item.get("task_id")
            if isinstance(item, Mapping)
            else item
        )
        if not isinstance(candidate, str) or not candidate.strip():
            return None
        result.append(candidate)
    return tuple(result)


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


class BeadsTaskTrackingProvider(ProviderBase):
    provider_name = "beads"
    provider_type = "task_tracking"
    capabilities = frozenset(
        {
            "task.create", "task.read", "task.update", "task.close",
            "task.dependency", "task.readiness", "task.preflight", "task.sync",
        }
    )

    def __init__(
        self,
        repository_root: Path,
        *,
        runner: Runner | None = None,
        executable: str = "bd",
    ) -> None:
        if Path(executable).name not in {"bd", "br"}:
            raise ValueError("task executable must be bd or br")
        available = runner is not None or shutil.which(executable) is not None
        super().__init__(
            available=available,
            health_detail=f"{executable} executable was not found" if not available else "",
        )
        self.repository_root = Path(repository_root).resolve()
        self.executable = executable
        self.family = Path(executable).name
        self._runner = runner or _default_runner
        self._preflight_cache: ProviderResult[TaskPreflight] | None = None
        self._help_options: dict[tuple[str, ...], frozenset[str]] = {}
        self._observed_drift = ""
        self._backend_identity = ""

    def _raw(self, argv: Sequence[str]) -> subprocess.CompletedProcess[str] | ProviderResult[Any]:
        try:
            return self._runner(argv, self.repository_root)
        except (OSError, subprocess.SubprocessError) as error:
            return ProviderResult.unavailable(f"{self.family} unavailable: {error}")

    def _invoke_json(self, argv: Sequence[str]) -> ProviderResult[Any]:
        completed = self._raw(argv)
        if isinstance(completed, ProviderResult):
            return completed
        if completed.returncode:
            detail = completed.stderr.strip() or completed.stdout.strip() or "unknown task CLI error"
            return ProviderResult.unavailable(f"{self.family} unavailable: {detail}")
        try:
            return ProviderResult.success(json.loads(completed.stdout))
        except json.JSONDecodeError as error:
            return ProviderResult.unavailable(f"{self.family} returned invalid JSON: {error}")

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

    def _discover(self, *, force: bool) -> ProviderResult[TaskPreflight]:
        if not force and self._preflight_cache is not None:
            return self._preflight_cache
        if guarded := self._guard():
            return guarded
        version_call = self._raw((self.executable, "--version"))
        root_help = self._raw((self.executable, "--help"))
        if isinstance(version_call, ProviderResult) or isinstance(root_help, ProviderResult):
            result = ProviderResult.unavailable(f"{self.family} discovery failed")
            self._preflight_cache = result
            return result
        if version_call.returncode or root_help.returncode:
            detail = (
                version_call.stderr.strip()
                or root_help.stderr.strip()
                or f"{self.family} version/help probe failed"
            )
            result = ProviderResult.unavailable(detail)
            self._preflight_cache = result
            return result
        command_paths = [("create",), ("update",), ("close",), ("dep", "add"), ("ready",)]
        if self.family == "br":
            command_paths.append(("sync",))
        options: dict[tuple[str, ...], frozenset[str]] = {}
        for command_path in command_paths:
            completed = self._raw((self.executable, *command_path, "--help"))
            if isinstance(completed, ProviderResult) or completed.returncode:
                result = ProviderResult.unavailable(
                    f"{self.family} capability probe failed: {' '.join(command_path)}"
                )
                self._preflight_cache = result
                return result
            options[command_path] = frozenset(_LONG_OPTION.findall(completed.stdout))
        self._help_options = options
        capabilities = {"task.read", "task.preflight"}
        create = options[("create",)]
        update = options[("update",)]
        close = options[("close",)]
        dependency = options[("dep", "add")]
        ready = options[("ready",)]
        if "--json" in create:
            capabilities.add("task.create")
        if "--status" in create:
            capabilities.add("task.create.status")
        if "--notes" in create:
            capabilities.add("task.create.notes")
        if {"--acceptance", "--acceptance-criteria"} & create:
            capabilities.add("task.create.acceptance")
        for field_name in ("description", "priority", "assignee"):
            if f"--{field_name}" in create:
                capabilities.add(f"task.create.{field_name}")
        if {"--status", "--json"}.issubset(update):
            capabilities.add("task.update")
        if "--notes" in update:
            capabilities.add("task.update.notes")
        if "--append-notes" in update:
            capabilities.add("task.update.append_notes")
        if {"--acceptance", "--acceptance-criteria"} & update:
            capabilities.add("task.update.acceptance")
        for field_name in ("title", "description", "status", "priority", "assignee"):
            if f"--{field_name}" in update:
                capabilities.add(f"task.update.{field_name}")
        if {"--reason", "--json"}.issubset(close):
            capabilities.add("task.close")
        if {"--type", "--json"}.issubset(dependency):
            capabilities.add("task.dependency")
        if "--json" in ready:
            capabilities.add("task.readiness")
        if self.family == "br":
            sync = options[("sync",)]
            for mode, flag in _SYNC_FLAGS.items():
                if flag in sync and "--json" in sync:
                    capabilities.add(f"task.sync.{mode}")
        status_argv = (
            (self.executable, "context", "--json")
            if self.family == "bd"
            else (self.executable, "sync", "--status", "--json")
        )
        status = self._invoke_json(status_argv)
        if status.value is None or not isinstance(status.value, Mapping):
            result = ProviderResult.success(
                TaskPreflight(
                    self.family,
                    version_call.stdout.strip(),
                    frozenset(capabilities),
                    False,
                    status.message or "task backend status unavailable",
                )
            )
            self._preflight_cache = result
            return result
        backend_value = status.value.get("backend")
        if not isinstance(backend_value, str) or not backend_value.strip():
            if self.family == "br" and "workspace_health" in status.value:
                backend_value = "sqlite-jsonl"
            else:
                result = ProviderResult.success(
                    TaskPreflight(
                        self.family,
                        version_call.stdout.strip(),
                        frozenset(capabilities),
                        False,
                        "task backend status is missing backend identity",
                    )
                )
                self._preflight_cache = result
                return result
        backend = backend_value.strip()
        if self.family == "bd":
            identity_fields = ("database", "project_id", "repo_root")
            if any(
                not isinstance(status.value.get(field_name), str)
                or not status.value[field_name].strip()
                for field_name in identity_fields
            ):
                result = ProviderResult.success(
                    TaskPreflight(
                        backend,
                        version_call.stdout.strip(),
                        frozenset(capabilities),
                        False,
                        "bd context is missing database, project_id, or repo_root identity",
                    )
                )
                self._preflight_cache = result
                return result
            healthy_value = True
            reported_drift = ""
            reconciled = False
            backend_identity = "\0".join(
                (backend, *(str(status.value[field_name]) for field_name in identity_fields))
            )
        else:
            ws_health = status.value.get("workspace_health")
            healthy_value = status.value.get("healthy")
            reported_drift = status.value.get("drift")
            reconciled_value = status.value.get("reconciled")
            if isinstance(ws_health, Mapping):
                if healthy_value is None:
                    healthy_value = ws_health.get("healthy")
                if reported_drift is None:
                    reported_drift = ws_health.get("drift")
                if reconciled_value is None:
                    reconciled_value = ws_health.get("reconciled")
            elif isinstance(ws_health, str):
                if healthy_value is None:
                    healthy_value = ws_health.lower() in ("healthy", "ok", "clean")
                if reported_drift is None:
                    reported_drift = "" if healthy_value else ws_health
                if reconciled_value is None:
                    reconciled_value = False

            if healthy_value is None and "workspace_health" in status.value:
                healthy_value = True
            if reported_drift is None and "workspace_health" in status.value:
                reported_drift = ""
            if reconciled_value is None and "workspace_health" in status.value:
                reconciled_value = False

            if (
                type(healthy_value) is not bool
                or not isinstance(reported_drift, str)
                or type(reconciled_value) is not bool
            ):
                result = ProviderResult.success(
                    TaskPreflight(
                        backend,
                        version_call.stdout.strip(),
                        frozenset(capabilities),
                        False,
                        "br status requires boolean healthy/reconciled and string drift",
                    )
                )
                self._preflight_cache = result
                return result
            reconciled = reconciled_value
            backend_identity = backend
        if reconciled:
            self._observed_drift = ""
        if (
            self._backend_identity
            and backend_identity != self._backend_identity
            and not reconciled
        ):
            self._observed_drift = (
                "backend identity changed without reconciliation"
            )
        elif not self._backend_identity or reconciled:
            self._backend_identity = backend_identity
        drift = str(
            reported_drift
            or self._observed_drift
        )
        healthy = healthy_value is True and not drift
        result = ProviderResult.success(
            TaskPreflight(
                backend,
                version_call.stdout.strip(),
                frozenset(capabilities),
                healthy,
                drift,
            )
        )
        self._preflight_cache = result
        return result

    def preflight(self) -> ProviderResult[TaskPreflight]:
        return self._discover(force=False)

    def _require(self, required: set[str]) -> ProviderResult[TaskPreflight]:
        checked = self._discover(force=True)
        if checked.value is None:
            return checked
        if not checked.value.healthy:
            return ProviderResult.unavailable(
                f"task backend drift: {checked.value.drift or 'unhealthy'}"
            )
        missing = sorted(required - checked.value.capabilities)
        if missing:
            return ProviderResult.unavailable(
                f"task capabilities unavailable: {', '.join(missing)}"
            )
        return checked

    def _acceptance_flag(self, command: tuple[str, ...]) -> str:
        options = self._help_options.get(command, frozenset())
        return "--acceptance" if "--acceptance" in options else "--acceptance-criteria"

    def create_task(
        self, request: TaskCreateRequest, *, idempotency_key: str
    ) -> ProviderResult[TaskRecord]:
        if guarded := self._guard():
            return guarded
        if not request.title.strip() or not request.status.strip() or not idempotency_key:
            return ProviderResult.invalid("title, status, and idempotency_key are required")
        if error := validate_task_status(request.status):
            return ProviderResult.invalid(error)
        if error := validate_task_attributes(request.attributes):
            return ProviderResult.invalid(error)
        required = {"task.create"}
        if request.description:
            required.add("task.create.description")
        if request.status != "open":
            required.add("task.create.status")
        if request.notes:
            required.add("task.create.notes")
        if request.acceptance_criteria:
            required.add("task.create.acceptance")
        for attribute in request.attributes:
            required.add(f"task.create.{attribute}")
        checked = self._require(required)
        if checked.value is None:
            return checked
        if replay := self._replay("create_task", idempotency_key, request):
            return replay
        argv = [self.executable, "create", request.title]
        if request.description:
            argv.extend(["--description", request.description])
        if "task.create.status" in checked.value.capabilities:
            argv.extend(["--status", request.status])
        if request.notes:
            argv.extend(["--notes", "\n".join(request.notes)])
        if request.acceptance_criteria:
            argv.extend(
                [self._acceptance_flag(("create",)), "\n".join(request.acceptance_criteria)]
            )
        for attribute in sorted(SUPPORTED_TASK_ATTRIBUTES):
            if attribute in request.attributes:
                argv.extend([f"--{attribute}", str(request.attributes[attribute])])
        argv.append("--json")
        invoked = self._invoke_json(argv)
        if invoked.value is None:
            return invoked
        normalized = self._task(invoked.value)
        return self._remember("create_task", idempotency_key, request, normalized)

    def read_task(self, task_id: str) -> ProviderResult[TaskRecord]:
        if guarded := self._guard():
            return guarded
        if not task_id.strip():
            return ProviderResult.invalid("task_id is required")
        checked = self._require({"task.read"})
        if checked.value is None:
            return checked
        invoked = self._invoke_json((self.executable, "show", task_id, "--json"))
        return invoked if invoked.value is None else self._task(invoked.value)

    def update_task(
        self, task_id: str, changes: Mapping[str, Any], *, idempotency_key: str
    ) -> ProviderResult[TaskRecord]:
        if guarded := self._guard():
            return guarded
        if not task_id.strip() or not changes or not idempotency_key:
            return ProviderResult.invalid("task_id, changes, and idempotency_key are required")
        normalized_changes, error = normalize_task_changes(changes)
        if error:
            return ProviderResult.invalid(error)
        required = {"task.update"}
        if "notes" in normalized_changes:
            required.add("task.update.notes")
        if "acceptance_criteria" in normalized_changes:
            required.add("task.update.acceptance")
        for field_name in normalized_changes:
            if field_name not in {"notes", "acceptance_criteria"}:
                required.add(f"task.update.{field_name}")
        checked = self._require(required)
        if checked.value is None:
            return checked
        if replay := self._replay("update_task", idempotency_key, (task_id, changes)):
            return replay
        argv = [self.executable, "update", task_id]
        for field, value in normalized_changes.items():
            if field == "notes":
                argv.extend(["--notes", "\n".join(value)])
            elif field == "acceptance_criteria":
                argv.extend([self._acceptance_flag(("update",)), "\n".join(value)])
            else:
                argv.extend([f"--{field}", str(value)])
        argv.append("--json")
        invoked = self._invoke_json(argv)
        if invoked.value is None:
            return invoked
        normalized = self._task(invoked.value)
        return self._remember("update_task", idempotency_key, (task_id, changes), normalized)

    def close_task(
        self, request: TaskClosureRequest, *, idempotency_key: str
    ) -> ProviderResult[TaskRecord]:
        if guarded := self._guard():
            return guarded
        if (
            not request.task_id.strip()
            or not request.closure_reason.strip()
            or not request.acceptance_evidence
            or not idempotency_key
        ):
            return ProviderResult.invalid(
                "task_id, closure_reason, acceptance_evidence, and idempotency_key are required"
            )
        checked = self._require({"task.update.notes", "task.close"})
        if checked.value is None:
            return checked
        if replay := self._replay("close_task", idempotency_key, request):
            return replay
        loaded = self._invoke_json(
            (self.executable, "show", request.task_id, "--json")
        )
        if loaded.value is None:
            return loaded
        current_result = self._task(loaded.value)
        if current_result.value is None:
            return current_result
        current = current_result.value
        provenance_matches = (
            current.acceptance_evidence == request.acceptance_evidence
            and current.closure_reason == request.closure_reason
        )
        if current.status == "closed":
            if provenance_matches:
                return ProviderResult.success(current, idempotent=True)
            return ProviderResult.invalid("closed task provenance does not match closure request")
        note_flag = (
            "--append-notes"
            if "task.update.append_notes" in checked.value.capabilities
            else "--notes"
        )
        marker_note = _closure_note(request)
        if not provenance_matches:
            note_value = (
                marker_note
                if note_flag == "--append-notes"
                else "\n".join((*current.notes, marker_note))
            )
            persisted = self._invoke_json(
                (self.executable, "update", request.task_id, note_flag, note_value, "--json")
            )
            if persisted.value is None:
                return persisted
        rechecked = self._require({"task.close"})
        if rechecked.value is None:
            return rechecked
        closed = self._invoke_json(
            (
                self.executable, "close", request.task_id,
                "--reason", request.closure_reason, "--json",
            )
        )
        if closed.value is None:
            return closed
        normalized = self._task(closed.value)
        if normalized.value is not None:
            final_notes = current.notes if provenance_matches else (*current.notes, marker_note)
            normalized = ProviderResult.success(
                TaskRecord(
                    **{
                        **normalized.value.__dict__,
                        "acceptance_evidence": request.acceptance_evidence,
                        "closure_reason": request.closure_reason,
                        "notes": final_notes,
                    }
                )
            )
        return self._remember("close_task", idempotency_key, request, normalized)

    def add_dependency(
        self, dependency: TaskDependencyRecord, *, idempotency_key: str
    ) -> ProviderResult[TaskDependencyRecord]:
        if guarded := self._guard():
            return guarded
        if (
            not dependency.task_id.strip()
            or not dependency.depends_on_task_id.strip()
            or dependency.task_id == dependency.depends_on_task_id
            or dependency.dependency_type != "blocks"
            or not idempotency_key
        ):
            return ProviderResult.invalid("valid blocking dependency and idempotency_key are required")
        checked = self._require({"task.dependency"})
        if checked.value is None:
            return checked
        if replay := self._replay("add_dependency", idempotency_key, dependency):
            return replay
        invoked = self._invoke_json(
            (
                self.executable, "dep", "add", dependency.task_id,
                dependency.depends_on_task_id, "--type",
                dependency.dependency_type, "--json",
            )
        )
        if invoked.value is None:
            return invoked
        return self._remember(
            "add_dependency", idempotency_key, dependency, ProviderResult.success(dependency)
        )

    def readiness(self, task_id: str) -> ProviderResult[TaskReadiness]:
        if guarded := self._guard():
            return guarded
        if not task_id.strip():
            return ProviderResult.invalid("task_id is required")
        checked = self._require({"task.readiness"})
        if checked.value is None:
            return checked
        invoked = self._invoke_json((self.executable, "ready", "--json"))
        if invoked.value is None:
            return invoked
        if isinstance(invoked.value, Mapping):
            ready_value = invoked.value.get("ready")
            response_task_id = invoked.value.get("task_id") or invoked.value.get("id")
            blockers = _strict_strings(invoked.value.get("blockers"))
            if (
                type(ready_value) is not bool
                or blockers is None
                or not isinstance(response_task_id, str)
                or not response_task_id.strip()
                or response_task_id != task_id
            ):
                return ProviderResult.unavailable(
                    "task readiness response is malformed or mismatched"
                )
            ready = ready_value
        elif isinstance(invoked.value, list):
            if any(
                not isinstance(item, Mapping)
                or not isinstance(item.get("id") or item.get("task_id"), str)
                for item in invoked.value
            ):
                return ProviderResult.unavailable("task readiness response is malformed")
            ready_ids = {
                str(item.get("id") or item.get("task_id"))
                for item in invoked.value
                if isinstance(item, Mapping)
            }
            ready = task_id in ready_ids
            blockers = ()
        else:
            return ProviderResult.unavailable("task readiness response is invalid")
        return ProviderResult.success(TaskReadiness(task_id, ready, blockers))

    def sync(
        self,
        request: TaskSyncRequest,
        *,
        idempotency_key: str,
        approval_request=None,
        approval_decision=None,
        audit_event_store=None,
    ) -> ProviderResult[TaskSyncResult]:
        if guarded := self._guard():
            return guarded
        if request.mode not in _SYNC_FLAGS or not idempotency_key:
            return ProviderResult.invalid("supported sync mode and idempotency_key are required")
        command = (self.executable, "sync", _SYNC_FLAGS[request.mode], "--json")
        checked = self._discover(force=True)
        if checked.value is None:
            return checked
        capability = f"task.sync.{request.mode}"
        if capability not in checked.value.capabilities:
            return ProviderResult.unavailable(f"task capabilities unavailable: {capability}")
        preview = TaskSyncResult(
            checked.value.backend, request.mode, request.dry_run, command
        )
        if request.dry_run:
            if replay := self._replay("sync", idempotency_key, request):
                return replay
            return self._remember(
                "sync", idempotency_key, request, ProviderResult.success(preview)
            )
        if not checked.value.healthy:
            return ProviderResult.unavailable(
                f"task backend drift: {checked.value.drift or 'unhealthy'}"
            )
        approval_details = getattr(approval_request, "details", None)
        if (
            not isinstance(approval_details, Mapping)
            or approval_details.get("mode") != request.mode
            or approval_details.get("backend") != checked.value.backend
        ):
            return ProviderResult.invalid(
                "data_move approval must match sync mode and backend"
            )
        try:
            authorize_protected_action(
                ApprovalAction.DATA_MOVE,
                request.workflow_id,
                approval_request,
                approval_decision,
                audit_event_store,
            )
        except (PermissionError, TypeError, ValueError) as error:
            return ProviderResult.invalid(str(error))
        if replay := self._replay("sync", idempotency_key, request):
            return replay
        invoked = self._invoke_json(command)
        if invoked.value is None:
            self._observed_drift = invoked.message or "task sync failed"
            self._preflight_cache = None
            return invoked
        affected = (
            _strings(invoked.value.get("affected"))
            if isinstance(invoked.value, Mapping)
            else ()
        )
        result = TaskSyncResult(
            checked.value.backend, request.mode, False, command, affected
        )
        return self._remember("sync", idempotency_key, request, ProviderResult.success(result))
