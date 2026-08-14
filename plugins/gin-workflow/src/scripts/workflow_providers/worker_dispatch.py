"""Provider-neutral worker requests, results, and lifecycle dispatch."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import threading
from typing import Any, Callable, Mapping

from workflow_core.events import WorkflowEvent, WorkflowEventStore
from workflow_core.manifests import ContextManifest


MAX_MANIFEST_BYTES = 65_536
REQUIRED_RESULT_FIELDS = (
    "status",
    "task_id",
    "summary",
    "changed_files",
    "commits",
    "tests",
    "evidence",
    "blockers",
)


class WorkerState(str, Enum):
    REQUESTED = "requested"
    ASSIGNED = "assigned"
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNAVAILABLE = "unavailable"


TERMINAL_WORKER_STATES = frozenset(
    {
        WorkerState.COMPLETED,
        WorkerState.FAILED,
        WorkerState.CANCELLED,
        WorkerState.UNAVAILABLE,
    }
)


class WorkerResultContractError(ValueError):
    """Raised when a native worker returns an unsafe or incomplete result."""


@dataclass(frozen=True)
class WorkerRequest:
    objective: str
    constraints: tuple[str, ...]
    generated_manifest: ContextManifest
    isolation_policy: Mapping[str, Any]
    expected_output: tuple[str, ...]
    task_id: str
    workflow_id: str
    retry_identity: str
    provider_role: str
    reasoning: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "constraints", tuple(self.constraints))
        object.__setattr__(self, "expected_output", tuple(self.expected_output))
        if not all(
            (
                self.objective,
                self.task_id,
                self.workflow_id,
                self.retry_identity,
                self.provider_role,
                self.reasoning,
            )
        ):
            raise ValueError("worker request identity and objective fields are required")
        if self.reasoning not in {"low", "medium", "high"}:
            raise ValueError("worker request reasoning must be low, medium, or high")
        if not isinstance(self.generated_manifest, ContextManifest):
            raise TypeError("generated_manifest must be a ContextManifest")
        if len(self.manifest_json().encode("utf-8")) > MAX_MANIFEST_BYTES:
            raise ValueError("generated manifest exceeds 65536 bytes")

    def manifest_json(self) -> str:
        return self.generated_manifest.to_json()

    @property
    def model_tier(self) -> str:
        return {
            "low": "cheap_simple",
            "medium": "standard_impl",
            "high": "high_reasoning",
        }[self.reasoning]

    def to_payload(self) -> dict[str, Any]:
        return {
            "objective": self.objective,
            "constraints": list(self.constraints),
            "generated_manifest": self.generated_manifest.to_dict(),
            "isolation_policy": dict(self.isolation_policy),
            "expected_output": list(self.expected_output),
            "task_id": self.task_id,
            "workflow_id": self.workflow_id,
            "retry_identity": self.retry_identity,
            "provider_role": self.provider_role,
            "reasoning": self.reasoning,
        }


@dataclass(frozen=True)
class WorkerResult:
    status: str
    task_id: str
    summary: str
    changed_files: tuple[str, ...]
    commits: tuple[str, ...]
    tests: tuple[Mapping[str, Any], ...]
    evidence: tuple[Mapping[str, Any], ...]
    blockers: tuple[str, ...]
    knowledge_candidates: tuple[Mapping[str, Any], ...] = ()


@dataclass(frozen=True)
class WorkerReceipt:
    worker_id: str
    state: WorkerState
    task_id: str
    fallback_used: bool = False


def _invalid_result(message: str) -> WorkerResultContractError:
    return WorkerResultContractError(f"invalid_result_contract: {message}")


def _string_tuple(value: object, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or any(not isinstance(item, str) for item in value):
        raise _invalid_result(f"{field_name} must be a list of strings")
    return tuple(value)


def _mapping_tuple(value: object, field_name: str) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, (list, tuple)) or any(not isinstance(item, Mapping) for item in value):
        raise _invalid_result(f"{field_name} must be a list of objects")
    return tuple(dict(item) for item in value)


def normalize_worker_result(
    value: Mapping[str, Any] | WorkerResult, request: WorkerRequest
) -> WorkerResult:
    """Validate and freeze a provider result at the workflow boundary."""
    if isinstance(value, WorkerResult):
        value = {
            "status": value.status,
            "task_id": value.task_id,
            "summary": value.summary,
            "changed_files": value.changed_files,
            "commits": value.commits,
            "tests": value.tests,
            "evidence": value.evidence,
            "blockers": value.blockers,
            "knowledge_candidates": value.knowledge_candidates,
        }
    if not isinstance(value, Mapping):
        raise _invalid_result("result must be an object")
    missing = [field_name for field_name in REQUIRED_RESULT_FIELDS if field_name not in value]
    if missing:
        raise _invalid_result(f"missing fields: {', '.join(missing)}")
    if not isinstance(value["status"], str) or value["status"] not in {
        "completed",
        "failed",
        "cancelled",
    }:
        raise _invalid_result("status must be completed, failed, or cancelled")
    if value["task_id"] != request.task_id:
        raise _invalid_result("task_id does not match request")
    if not isinstance(value["summary"], str):
        raise _invalid_result("summary must be a string")
    knowledge = value.get("knowledge_candidates", ())
    return WorkerResult(
        status=value["status"],
        task_id=value["task_id"],
        summary=value["summary"],
        changed_files=_string_tuple(value["changed_files"], "changed_files"),
        commits=_string_tuple(value["commits"], "commits"),
        tests=_mapping_tuple(value["tests"], "tests"),
        evidence=_mapping_tuple(value["evidence"], "evidence"),
        blockers=_string_tuple(value["blockers"], "blockers"),
        knowledge_candidates=_mapping_tuple(knowledge, "knowledge_candidates"),
    )


def failed_worker_result(request: WorkerRequest, blocker: str, summary: str = "") -> WorkerResult:
    return WorkerResult(
        status="failed",
        task_id=request.task_id,
        summary=summary or blocker,
        changed_files=(),
        commits=(),
        tests=(),
        evidence=(),
        blockers=(blocker,),
    )


def worker_id_for(provider_name: str, request: WorkerRequest) -> str:
    digest = hashlib.sha256(
        (
            f"{provider_name}\0{request.workflow_id}\0{request.task_id}"
            f"\0{request.retry_identity}"
        ).encode("utf-8")
    ).hexdigest()[:24]
    return f"worker-{digest}"


def worker_request_identity(request: WorkerRequest) -> tuple[str, str, str]:
    return request.workflow_id, request.task_id, request.retry_identity


@dataclass
class _AdapterRecord:
    request: WorkerRequest
    receipt: WorkerReceipt
    result: WorkerResult | None = None
    completed: threading.Event = field(default_factory=threading.Event)


class SynchronousWorkerAdapter:
    """Thread-backed lifecycle for native bridges and sequential fallback."""

    provider_name = "worker"

    def __init__(
        self,
        runner: Callable[[Mapping[str, Any]], Mapping[str, Any] | WorkerResult] | None,
        *,
        available: bool = True,
        payload_factory: Callable[[WorkerRequest], Mapping[str, Any]] | None = None,
    ) -> None:
        self._runner = runner
        self._available = bool(available and runner is not None)
        self._payload_factory = payload_factory or (lambda request: request.to_payload())
        self._records: dict[str, _AdapterRecord] = {}
        self._retries: dict[tuple[str, str, str], str] = {}
        self._lock = threading.RLock()

    def prepare(self, request: WorkerRequest) -> WorkerReceipt:
        """Register an attempt without starting native work."""
        identity = worker_request_identity(request)
        with self._lock:
            previous_id = self._retries.get(identity)
            if previous_id is not None:
                return self._records[previous_id].receipt
            worker_id = worker_id_for(self.provider_name, request)
            state = WorkerState.ASSIGNED if self._available else WorkerState.UNAVAILABLE
            receipt = WorkerReceipt(worker_id, state, request.task_id)
            record = _AdapterRecord(request, receipt)
            self._records[worker_id] = record
            self._retries[identity] = worker_id
            if state is WorkerState.UNAVAILABLE:
                record.result = failed_worker_result(request, "worker_unavailable")
                record.completed.set()
            return receipt

    def start(
        self,
        worker_id: str,
        *,
        on_started: Callable[[WorkerReceipt], None] | None = None,
    ) -> bool:
        """Start a prepared attempt once and expose its running state immediately."""
        with self._lock:
            try:
                record = self._records[worker_id]
            except KeyError as error:
                raise KeyError(f"unknown worker: {worker_id}") from error
            if record.receipt.state is not WorkerState.ASSIGNED:
                return False
            assigned_receipt = record.receipt
            started_receipt = WorkerReceipt(worker_id, WorkerState.STARTED, record.request.task_id)
            record.receipt = started_receipt
            try:
                if on_started is not None:
                    on_started(started_receipt)
            except Exception:
                record.receipt = assigned_receipt
                raise
            thread = threading.Thread(
                target=self._run,
                args=(worker_id,),
                name=worker_id,
                daemon=True,
            )
            thread.start()
            return True

    def _run(self, worker_id: str) -> None:
        with self._lock:
            record = self._records[worker_id]
            request = record.request
        try:
            raw_result = self._runner(dict(self._payload_factory(request)))
            result = normalize_worker_result(raw_result, request)
        except WorkerResultContractError as error:
            result = failed_worker_result(request, "invalid_result_contract", str(error))
        except Exception as error:  # Native boundaries return normalized failures.
            result = failed_worker_result(request, "worker_exception", str(error))
        state = {
            "completed": WorkerState.COMPLETED,
            "failed": WorkerState.FAILED,
            "cancelled": WorkerState.CANCELLED,
        }[result.status]
        completed_receipt = WorkerReceipt(worker_id, state, request.task_id)
        with self._lock:
            if record.receipt.state is WorkerState.CANCELLED:
                return
            record.result = result
            record.receipt = completed_receipt
            record.completed.set()

    def dispatch(self, request: WorkerRequest) -> WorkerReceipt:
        receipt = self.prepare(request)
        self.start(receipt.worker_id)
        return self.status(receipt.worker_id)

    def status(self, worker_id: str) -> WorkerReceipt:
        with self._lock:
            try:
                return self._records[worker_id].receipt
            except KeyError as error:
                raise KeyError(f"unknown worker: {worker_id}") from error

    def collect_result(self, worker_id: str, timeout: float | None = None) -> WorkerResult:
        with self._lock:
            try:
                record = self._records[worker_id]
            except KeyError as error:
                raise KeyError(f"unknown worker: {worker_id}") from error
        if not record.completed.wait(timeout=timeout):
            raise TimeoutError(f"worker result deadline exceeded: {worker_id}")
        with self._lock:
            if record.result is None:
                raise RuntimeError(f"worker completed without a result: {worker_id}")
            return record.result

    def cancel(self, worker_id: str) -> bool:
        with self._lock:
            try:
                record = self._records[worker_id]
            except KeyError as error:
                raise KeyError(f"unknown worker: {worker_id}") from error
            if record.receipt.state in TERMINAL_WORKER_STATES:
                return False
            if record.receipt.state is WorkerState.STARTED:
                return False
            record.result = WorkerResult(
                "cancelled", record.request.task_id, "cancelled", (), (), (), (), ("cancelled",)
            )
            record.receipt = WorkerReceipt(worker_id, WorkerState.CANCELLED, record.request.task_id)
            record.completed.set()
            return True


@dataclass
class _DispatchRecord:
    request: WorkerRequest
    adapter: Any
    receipt: WorkerReceipt
    result: WorkerResult | None = None
    finish_lock: threading.Lock = field(default_factory=threading.Lock)
    lifecycle_ready: threading.Event = field(default_factory=threading.Event)
    dispatch_ready: threading.Event = field(default_factory=threading.Event)


class WorkerDispatcher:
    """Normalize provider lifecycles into idempotent workflow events."""

    def __init__(self, adapter: Any, event_store: WorkflowEventStore, *, fallback: Any = None):
        self.adapter = adapter
        self.fallback = fallback
        self.event_store = event_store
        self._records: dict[str, _DispatchRecord] = {}
        self._identities: dict[tuple[str, str, str], str] = {}
        self._lock = threading.RLock()

    def _emit(
        self,
        request: WorkerRequest,
        event_name: str,
        *,
        worker_id: str = "",
        payload: Mapping[str, Any] | None = None,
    ) -> None:
        body = {"retry_identity": request.retry_identity}
        if worker_id:
            body["worker_id"] = worker_id
        body.update(payload or {})
        self.event_store.append(
            WorkflowEvent.create(
                event_type=f"worker.{event_name}",
                workflow_id=request.workflow_id,
                task_id=request.task_id,
                payload=body,
                idempotency_key=(
                    f"{request.workflow_id}:{request.task_id}:"
                    f"{request.retry_identity}:{event_name}"
                ),
            )
        )

    @staticmethod
    def _context_available(request: WorkerRequest) -> bool:
        for item in request.generated_manifest.categories["required"]:
            if isinstance(item, Mapping) and item.get("available") is False:
                return False
        return True

    @staticmethod
    def _supports_preregistration(adapter: Any) -> bool:
        return all(
            callable(getattr(adapter, method_name, None))
            for method_name in ("prepare", "start", "status", "collect_result", "cancel")
        )

    def dispatch(self, request: WorkerRequest) -> WorkerReceipt:
        identity = worker_request_identity(request)
        unavailable_worker_ids: list[str] = []
        failure_blocker = ""
        with self._lock:
            existing_id = self._identities.get(identity)
            if existing_id is not None:
                existing_record = self._records[existing_id]
                existing_record.dispatch_ready.wait()
                return existing_record.receipt
            if not self._context_available(request):
                worker_id = worker_id_for("context", request)
                result = failed_worker_result(request, "context_unavailable")
                receipt = WorkerReceipt(worker_id, WorkerState.FAILED, request.task_id)
                record = _DispatchRecord(request, self.adapter, receipt, result)
                failure_blocker = "context_unavailable"
                deferred_start = False
                adapter_receipt = receipt
            else:
                selected = self.adapter
                fallback_used = False
                deferred_start = self._supports_preregistration(selected)
                if deferred_start:
                    adapter_receipt = selected.prepare(request)
                else:
                    adapter_receipt = WorkerReceipt(
                        worker_id_for("unsupported", request),
                        WorkerState.FAILED,
                        request.task_id,
                    )
                    failure_blocker = "worker_adapter_unsupported"
                if not failure_blocker and adapter_receipt.state is WorkerState.UNAVAILABLE:
                    unavailable_worker_ids.append(adapter_receipt.worker_id)
                    if self.fallback is None:
                        failure_blocker = "worker_unavailable"
                    else:
                        selected = self.fallback
                        fallback_used = True
                        deferred_start = self._supports_preregistration(selected)
                        if deferred_start:
                            adapter_receipt = selected.prepare(request)
                        else:
                            adapter_receipt = WorkerReceipt(
                                worker_id_for("unsupported-fallback", request),
                                WorkerState.FAILED,
                                request.task_id,
                            )
                            failure_blocker = "worker_adapter_unsupported"
                        if (
                            not failure_blocker
                            and adapter_receipt.state is WorkerState.UNAVAILABLE
                        ):
                            unavailable_worker_ids.append(adapter_receipt.worker_id)
                            failure_blocker = "worker_unavailable"
                if failure_blocker:
                    result = failed_worker_result(request, failure_blocker)
                    receipt = WorkerReceipt(
                        adapter_receipt.worker_id,
                        WorkerState.FAILED,
                        request.task_id,
                        fallback_used,
                    )
                    record = _DispatchRecord(request, selected, receipt, result)
                else:
                    receipt = WorkerReceipt(
                        adapter_receipt.worker_id,
                        adapter_receipt.state,
                        request.task_id,
                        fallback_used,
                    )
                    record = _DispatchRecord(request, selected, receipt)
            self._records[receipt.worker_id] = record
            self._identities[identity] = receipt.worker_id

        try:
            self._emit(request, "requested")
            for unavailable_worker_id in unavailable_worker_ids:
                self._emit(request, "unavailable", worker_id=unavailable_worker_id)
            if failure_blocker:
                self._emit(
                    request,
                    "failed",
                    worker_id=receipt.worker_id,
                    payload={"blocker": failure_blocker},
                )
                return receipt
            self._emit(request, "assigned", worker_id=receipt.worker_id)
        finally:
            record.lifecycle_ready.set()
            if failure_blocker:
                record.dispatch_ready.set()

        if deferred_start:
            def publish_started(started_receipt: WorkerReceipt) -> None:
                with record.finish_lock:
                    if record.result is not None:
                        return
                    record.receipt = WorkerReceipt(
                        receipt.worker_id,
                        started_receipt.state,
                        receipt.task_id,
                        receipt.fallback_used,
                    )
                    self._emit(request, "started", worker_id=receipt.worker_id)

            try:
                started = selected.start(receipt.worker_id, on_started=publish_started)
                with record.finish_lock:
                    if record.result is not None:
                        return record.receipt
                    if not started:
                        adapter_receipt = selected.status(receipt.worker_id)
                        record.receipt = WorkerReceipt(
                            receipt.worker_id,
                            adapter_receipt.state,
                            receipt.task_id,
                            receipt.fallback_used,
                        )
                    else:
                        self._emit(request, "context_loaded", worker_id=receipt.worker_id)
                        self._emit(request, "progress_updated", worker_id=receipt.worker_id)
                if not started and adapter_receipt.state in TERMINAL_WORKER_STATES:
                    self._finish(record)
            finally:
                record.dispatch_ready.set()
        return record.receipt

    def _finish(self, record: _DispatchRecord, timeout: float | None = None) -> WorkerResult:
        if record.result is not None:
            return record.result
        try:
            try:
                result = record.adapter.collect_result(record.receipt.worker_id, timeout=timeout)
            except TypeError:
                result = record.adapter.collect_result(record.receipt.worker_id)
            result = normalize_worker_result(result, record.request)
        except TimeoutError:
            raise
        except WorkerResultContractError as error:
            result = failed_worker_result(record.request, "invalid_result_contract", str(error))
        except Exception as error:
            result = failed_worker_result(record.request, "worker_exception", str(error))
        with record.finish_lock:
            if record.result is not None:
                return record.result
            state = {
                "completed": WorkerState.COMPLETED,
                "failed": WorkerState.FAILED,
                "cancelled": WorkerState.CANCELLED,
            }[result.status]
            record.result = result
            record.receipt = WorkerReceipt(
                record.receipt.worker_id,
                state,
                record.receipt.task_id,
                record.receipt.fallback_used,
            )
            event_name = "completed" if state is WorkerState.COMPLETED else (
                "cancelled" if state is WorkerState.CANCELLED else "failed"
            )
            self._emit(
                record.request,
                event_name,
                worker_id=record.receipt.worker_id,
                payload={"blockers": list(result.blockers)},
            )
            return result

    def collect_result(self, worker_id: str, timeout: float | None = None) -> WorkerResult:
        with self._lock:
            try:
                record = self._records[worker_id]
            except KeyError as error:
                raise KeyError(f"unknown worker: {worker_id}") from error
        return self._finish(record, timeout=timeout)

    def status(self, worker_id: str) -> WorkerReceipt:
        with self._lock:
            try:
                record = self._records[worker_id]
            except KeyError as error:
                raise KeyError(f"unknown worker: {worker_id}") from error
        if record.result is not None:
            return record.receipt
        adapter_receipt = record.adapter.status(worker_id)
        if adapter_receipt.state in TERMINAL_WORKER_STATES:
            self._finish(record, timeout=0)
        else:
            record.receipt = WorkerReceipt(
                worker_id,
                adapter_receipt.state,
                record.receipt.task_id,
                record.receipt.fallback_used,
            )
        return record.receipt

    def cancel(self, worker_id: str) -> bool:
        with self._lock:
            try:
                record = self._records[worker_id]
            except KeyError as error:
                raise KeyError(f"unknown worker: {worker_id}") from error
        record.lifecycle_ready.wait()
        with record.finish_lock:
            if record.result is not None or record.receipt.state in TERMINAL_WORKER_STATES:
                return False
        if not record.adapter.cancel(worker_id):
            return False
        with record.finish_lock:
            if record.result is not None:
                return record.receipt.state is WorkerState.CANCELLED
            adapter_receipt = record.adapter.status(worker_id)
            if adapter_receipt.state is not WorkerState.CANCELLED:
                return False
            record.result = WorkerResult(
                "cancelled", record.request.task_id, "cancelled", (), (), (), (), ("cancelled",)
            )
            record.receipt = WorkerReceipt(
                worker_id, WorkerState.CANCELLED, record.request.task_id, record.receipt.fallback_used
            )
            self._emit(record.request, "cancelled", worker_id=worker_id)
            return True
