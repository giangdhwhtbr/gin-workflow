"""Provider-neutral worker requests, results, and lifecycle dispatch."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import inspect
import json
import re
import threading
import time
from typing import Any, Callable, Mapping

from workflow_core.events import WorkflowEvent, WorkflowEventStore
from workflow_core.identity import AcceptanceIdentity
from workflow_core.manifests import ContextManifest

from .contracts import parse_timestamp


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
DEFAULT_CANCELLATION_TIMEOUT_SECONDS = 30.0


def collect_adapter_result(
    adapter: Any,
    worker_id: str,
    timeout: float | None,
) -> Any:
    """Collect with a real deadline, including legacy adapters without timeout support."""
    collect = adapter.collect_result
    try:
        parameters = inspect.signature(collect).parameters
        supports_timeout = "timeout" in parameters or any(
            parameter.kind is inspect.Parameter.VAR_KEYWORD
            for parameter in parameters.values()
        )
    except (TypeError, ValueError):
        supports_timeout = False
    if supports_timeout:
        return collect(worker_id, timeout=timeout)
    if timeout is None:
        return collect(worker_id)

    completed = threading.Event()
    state: dict[str, Any] = {}

    def run() -> None:
        try:
            state["result"] = collect(worker_id)
        except BaseException as error:
            state["error"] = error
        finally:
            completed.set()

    threading.Thread(
        target=run,
        name=f"legacy-collect:{worker_id}",
        daemon=True,
    ).start()
    if not completed.wait(timeout=timeout):
        raise TimeoutError(f"worker result deadline exceeded: {worker_id}")
    if "error" in state:
        raise state["error"]
    return state["result"]


def request_adapter_cancellation(
    record: Any,
    worker_id: str,
    timeout: float | None,
    timeout_result: WorkerResult,
) -> bool:
    """Resolve one provider cancellation decision within a shared deadline."""
    deadline = None if timeout is None else time.monotonic() + timeout
    with record.finish_lock:
        if record.result is not None or record.receipt.state in TERMINAL_WORKER_STATES:
            return False
        if not record.cancellation_decided and not record.cancel_in_progress:
            record.cancel_in_progress = True
            owner = True
        else:
            owner = False

    if owner:
        def decide() -> None:
            accepted = False
            error: BaseException | None = None
            try:
                accepted = bool(record.adapter.cancel(worker_id))
            except BaseException as caught:
                error = caught
            with record.finish_lock:
                record.cancel_in_progress = False
                record.cancellation_decided = True
                record.cancellation_accepted = accepted
                record.cancellation_error = error
                record.finish_lock.notify_all()

        threading.Thread(
            target=decide,
            name=f"cancel-decision:{worker_id}",
            daemon=True,
        ).start()

    with record.finish_lock:
        while record.cancel_in_progress:
            remaining = None if deadline is None else deadline - time.monotonic()
            if remaining is not None and remaining <= 0:
                record.cancellation_abandoned = True
                record.forced_result = timeout_result
                record.finish_lock.notify_all()
                raise TimeoutError(f"worker cancellation deadline exceeded: {worker_id}")
            record.finish_lock.wait(timeout=remaining)
        if record.cancellation_error is not None:
            raise record.cancellation_error
        return record.cancellation_accepted


class WorkerResultContractError(ValueError):
    """Raised when a native worker returns an unsafe or incomplete result."""


def _invalid_result(message: str) -> WorkerResultContractError:
    return WorkerResultContractError(f"invalid_result_contract: {message}")


TEST_RESULT_FIELDS = frozenset(
    {
        "argv",
        "exit_code",
        "started_at",
        "finished_at",
        "workspace_id",
        "repository_id",
        "attempt_id",
        "source_tree_hash",
    }
)
_PORTABLE_ID = re.compile(r"^[A-Za-z0-9._-]+$")
_SECRET_FLAGS = frozenset(
    {
        "--api-key",
        "--credential",
        "--password",
        "--private-key",
        "--secret",
        "--token",
    }
)
_SECRET_VALUE = re.compile(
    r"(?:-----BEGIN [A-Z ]*PRIVATE KEY-----|\bsk-[A-Za-z0-9_-]{6,}|"
    r"\bgh[pousr]_[A-Za-z0-9]{6,}|\bxox[baprs]-)",
    re.IGNORECASE,
)


def _sanitize_argv(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or any(
        not isinstance(item, str) for item in value
    ):
        raise _invalid_result("test argv must be a list of strings")
    if not value:
        raise _invalid_result("test argv must not be empty")
    sanitized: list[str] = []
    redact_next = False
    for item in value:
        normalized = item.casefold().replace("_", "-")
        if redact_next or _SECRET_VALUE.search(item):
            sanitized.append("[REDACTED]")
            redact_next = False
            continue
        name, separator, _candidate = normalized.partition("=")
        if name in _SECRET_FLAGS:
            if separator:
                sanitized.append(f"{item.split('=', 1)[0]}=[REDACTED]")
            else:
                sanitized.append(item)
                redact_next = True
            continue
        sanitized.append(item)
    return tuple(sanitized)


def _require_portable_id(field_name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _invalid_result(f"test {field_name} is required")
    if field_name == "workspace_id" and not _PORTABLE_ID.fullmatch(value):
        raise _invalid_result("test workspace_id must be a portable identifier")
    return value


@dataclass(frozen=True)
class WorkerTestResult:
    """One auditable test run bound to a workspace, attempt, repository, and tree."""

    argv: tuple[str, ...]
    exit_code: int
    started_at: str
    finished_at: str
    workspace_id: str
    repository_id: str
    attempt_id: str
    source_tree_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "argv", _sanitize_argv(self.argv))
        if isinstance(self.exit_code, bool) or not isinstance(self.exit_code, int):
            raise _invalid_result("test exit_code must be an integer")
        if not 0 <= self.exit_code <= 255:
            raise _invalid_result("test exit_code must be between 0 and 255")
        try:
            started = parse_timestamp(self.started_at)
            finished = parse_timestamp(self.finished_at)
        except (TypeError, ValueError) as error:
            raise _invalid_result(f"invalid test timestamp: {error}") from error
        if (
            started.utcoffset() is None
            or finished.utcoffset() is None
            or started.utcoffset().total_seconds() != 0
            or finished.utcoffset().total_seconds() != 0
        ):
            raise _invalid_result("test timestamps must be UTC")
        if finished < started:
            raise _invalid_result("test finished_at precedes started_at")
        for field_name in (
            "workspace_id",
            "repository_id",
            "attempt_id",
            "source_tree_hash",
        ):
            _require_portable_id(field_name, getattr(self, field_name))

    @property
    def auditable(self) -> bool:
        return True

    @property
    def passed(self) -> bool:
        return self.exit_code == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "argv": list(self.argv),
            "exit_code": self.exit_code,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "workspace_id": self.workspace_id,
            "repository_id": self.repository_id,
            "attempt_id": self.attempt_id,
            "source_tree_hash": self.source_tree_hash,
        }

    @classmethod
    def from_mapping(cls, value: object) -> "WorkerTestResult":
        if isinstance(value, WorkerTestResult):
            return value
        if not isinstance(value, Mapping):
            raise _invalid_result("tests must be a list of objects")
        if unknown := set(value) - TEST_RESULT_FIELDS:
            raise _invalid_result(f"unsupported test fields: {', '.join(sorted(unknown))}")
        missing = TEST_RESULT_FIELDS.difference(value)
        if missing:
            raise _invalid_result(
                f"test records are missing fields: {', '.join(sorted(missing))}"
            )
        return cls(
            argv=value["argv"],
            exit_code=value["exit_code"],
            started_at=value["started_at"],
            finished_at=value["finished_at"],
            workspace_id=value["workspace_id"],
            repository_id=value["repository_id"],
            attempt_id=value["attempt_id"],
            source_tree_hash=value["source_tree_hash"],
        )


@dataclass(frozen=True)
class _LegacyWorkerTestResult:
    """Readable schema-1 record that can never satisfy current evidence gates."""

    command: str
    outcome: str

    def __post_init__(self) -> None:
        if not isinstance(self.command, str) or not self.command.strip():
            raise _invalid_result("legacy test command is required")
        if not isinstance(self.outcome, str) or not self.outcome.strip():
            raise _invalid_result("legacy test outcome is required")

    @property
    def auditable(self) -> bool:
        return False

    @property
    def passed(self) -> bool:
        return False

    def to_dict(self) -> dict[str, str]:
        return {"command": self.command, "outcome": self.outcome}


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
    route_affinity: tuple[str, str] | None = None
    acceptance_identity: AcceptanceIdentity | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "constraints", tuple(self.constraints))
        object.__setattr__(self, "expected_output", tuple(self.expected_output))
        if self.route_affinity is not None:
            if len(self.route_affinity) != 2 or not all(self.route_affinity):
                raise ValueError("route_affinity requires provider and model")
            object.__setattr__(self, "route_affinity", tuple(self.route_affinity))
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
        if self.acceptance_identity is not None:
            if not isinstance(self.acceptance_identity, AcceptanceIdentity):
                raise TypeError("acceptance_identity must be an AcceptanceIdentity")
            if (
                self.acceptance_identity.workflow_id != self.workflow_id
                or self.acceptance_identity.task_id != self.task_id
            ):
                raise ValueError("acceptance identity must match the request workflow and task")
            workspace_id = self.isolation_policy.get("workspace_id")
            if not isinstance(workspace_id, str) or not _PORTABLE_ID.fullmatch(workspace_id):
                raise ValueError(
                    "identity-bound worker request requires a portable workspace_id"
                )
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
        payload = {
            "schema_version": "2.3",
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
        if self.acceptance_identity is not None:
            payload["acceptance_identity"] = self.acceptance_identity.to_dict()
        return payload


@dataclass(frozen=True)
class WorkerResult:
    status: str
    task_id: str
    summary: str
    changed_files: tuple[str, ...]
    commits: tuple[str, ...]
    tests: tuple[WorkerTestResult | _LegacyWorkerTestResult, ...]
    evidence: tuple[Mapping[str, Any], ...]
    blockers: tuple[str, ...]
    knowledge_candidates: tuple[Mapping[str, Any], ...] = ()
    acceptance_identity: AcceptanceIdentity | None = None
    schema_version: str = "2.3"


@dataclass(frozen=True)
class WorkerReceipt:
    worker_id: str
    state: WorkerState
    task_id: str
    fallback_used: bool = False


def _string_tuple(value: object, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or any(not isinstance(item, str) for item in value):
        raise _invalid_result(f"{field_name} must be a list of strings")
    return tuple(value)


def _mapping_tuple(value: object, field_name: str) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, (list, tuple)) or any(not isinstance(item, Mapping) for item in value):
        raise _invalid_result(f"{field_name} must be a list of objects")
    return tuple(dict(item) for item in value)


def _test_results(
    value: object, request: WorkerRequest
) -> tuple[WorkerTestResult | _LegacyWorkerTestResult, ...]:
    """Validate reported runs against the request's workspace and attempt identity."""
    if not isinstance(value, (list, tuple)):
        raise _invalid_result("tests must be a list of objects")
    expected_workspace = str(request.isolation_policy.get("workspace_id") or "")
    results = []
    for item in value:
        if isinstance(item, (WorkerTestResult, _LegacyWorkerTestResult)):
            normalized = item
        elif (
            request.acceptance_identity is None
            and isinstance(item, Mapping)
            and set(item) == {"command", "outcome"}
        ):
            normalized = _LegacyWorkerTestResult(
                command=item["command"],
                outcome=item["outcome"],
            )
        else:
            normalized = WorkerTestResult.from_mapping(item)
        results.append(normalized)
    for item in results:
        if isinstance(item, _LegacyWorkerTestResult):
            continue
        if expected_workspace and item.workspace_id != expected_workspace:
            raise _invalid_result("test workspace does not match the isolated workspace")
        if request.acceptance_identity is None:
            continue
        if item.attempt_id != request.acceptance_identity.attempt_id:
            raise _invalid_result("test attempt does not match request")
        repository = next(
            (
                snapshot
                for snapshot in request.acceptance_identity.repositories
                if snapshot.repository_id == item.repository_id
            ),
            None,
        )
        if repository is None:
            raise _invalid_result("test repository does not match request")
        if item.source_tree_hash != repository.source_tree_hash:
            raise _invalid_result("test source tree does not match request")
    return tuple(results)


def normalize_worker_result(
    value: Mapping[str, Any] | WorkerResult, request: WorkerRequest
) -> WorkerResult:
    """Validate and freeze a provider result at the workflow boundary."""
    if isinstance(value, WorkerResult):
        value = {
            "schema_version": value.schema_version,
            "status": value.status,
            "task_id": value.task_id,
            "summary": value.summary,
            "changed_files": value.changed_files,
            "commits": value.commits,
            "tests": value.tests,
            "evidence": value.evidence,
            "blockers": value.blockers,
            "knowledge_candidates": value.knowledge_candidates,
            "acceptance_identity": (
                None
                if value.acceptance_identity is None
                else value.acceptance_identity.to_dict()
            ),
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
    raw_identity = value.get("acceptance_identity")
    result_identity = None
    if raw_identity is not None:
        if isinstance(raw_identity, AcceptanceIdentity):
            result_identity = raw_identity
        else:
            try:
                result_identity = AcceptanceIdentity.from_mapping(raw_identity)
            except (TypeError, ValueError) as error:
                raise _invalid_result(f"invalid result acceptance_identity: {error}") from error
    if request.acceptance_identity is not None:
        if value.get("schema_version") != "2.3":
            raise _invalid_result("identity-bound result schema_version must be 2.3")
        if result_identity is None:
            raise _invalid_result("result acceptance_identity is required")
        try:
            request.acceptance_identity.require_exact_match(result_identity)
        except (TypeError, ValueError) as error:
            raise _invalid_result(str(error)) from error
    knowledge = value.get("knowledge_candidates", ())
    return WorkerResult(
        status=value["status"],
        task_id=value["task_id"],
        summary=value["summary"],
        changed_files=_string_tuple(value["changed_files"], "changed_files"),
        commits=_string_tuple(value["commits"], "commits"),
        tests=_test_results(value["tests"], request),
        evidence=_mapping_tuple(value["evidence"], "evidence"),
        blockers=_string_tuple(value["blockers"], "blockers"),
        knowledge_candidates=_mapping_tuple(knowledge, "knowledge_candidates"),
        acceptance_identity=result_identity,
        schema_version=str(value.get("schema_version", "1.0")),
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
        acceptance_identity=request.acceptance_identity,
    )


def cancelled_worker_result(
    request: WorkerRequest,
    blocker: str = "cancelled",
    summary: str = "cancelled",
) -> WorkerResult:
    """Create cancellation through the same identity-bound result contract."""
    return normalize_worker_result(
        WorkerResult(
            status="cancelled",
            task_id=request.task_id,
            summary=summary,
            changed_files=(),
            commits=(),
            tests=(),
            evidence=(),
            blockers=(blocker,),
            acceptance_identity=request.acceptance_identity,
            schema_version="2.3" if request.acceptance_identity is not None else "1.0",
        ),
        request,
    )


def worker_acceptance_key(request: WorkerRequest) -> str:
    """Return a deterministic replay key with an explicit legacy marker."""
    if request.acceptance_identity is None:
        return "legacy"
    serialized = json.dumps(
        request.acceptance_identity.to_dict(),
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"identity-{hashlib.sha256(serialized.encode('utf-8')).hexdigest()}"


def worker_id_for(provider_name: str, request: WorkerRequest) -> str:
    replay_identity = worker_request_identity(request)[2]
    digest = hashlib.sha256(
        (
            f"{provider_name}\0{request.workflow_id}\0{request.task_id}"
            f"\0{replay_identity}"
        ).encode("utf-8")
    ).hexdigest()[:24]
    return f"worker-{digest}"


def worker_request_identity(request: WorkerRequest) -> tuple[str, str, str]:
    return (
        request.workflow_id,
        request.task_id,
        f"{request.retry_identity}\0{worker_acceptance_key(request)}",
    )


@dataclass
class _AdapterRecord:
    request: WorkerRequest
    receipt: WorkerReceipt
    result: WorkerResult | None = None
    completed: threading.Event = field(default_factory=threading.Event)
    cancel_requested: threading.Event = field(default_factory=threading.Event)


class SynchronousWorkerAdapter:
    """Thread-backed lifecycle for native bridges and sequential fallback."""

    provider_name = "worker"

    def __init__(
        self,
        runner: Callable[[Mapping[str, Any]], Mapping[str, Any] | WorkerResult] | None,
        *,
        available: bool = True,
        payload_factory: Callable[[WorkerRequest], Mapping[str, Any]] | None = None,
        cancellable_runner: Callable[
            [Mapping[str, Any], threading.Event], Mapping[str, Any] | WorkerResult
        ] | None = None,
    ) -> None:
        self._runner = runner
        self._cancellable_runner = cancellable_runner
        self._available = bool(available and (runner is not None or cancellable_runner is not None))
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
                previous = self._records[previous_id]
                if previous.request != request:
                    raise ValueError("worker replay request mismatch")
                return previous.receipt
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
            payload = dict(self._payload_factory(request))
            if self._cancellable_runner is not None:
                raw_result = self._cancellable_runner(payload, record.cancel_requested)
            else:
                raw_result = self._runner(payload)
            result = normalize_worker_result(raw_result, request)
        except WorkerResultContractError as error:
            result = failed_worker_result(request, "invalid_result_contract", str(error))
        except Exception as error:  # Native boundaries return normalized failures.
            kind = getattr(error, "kind", None)
            kind_value = getattr(kind, "value", None)
            blocker = f"provider_failure:{kind_value}" if kind_value else "worker_exception"
            if kind_value == "cancelled":
                result = cancelled_worker_result(request, blocker, str(error))
            else:
                result = failed_worker_result(request, blocker, str(error))
        state = {
            "completed": WorkerState.COMPLETED,
            "failed": WorkerState.FAILED,
            "cancelled": WorkerState.CANCELLED,
        }[result.status]
        completed_receipt = WorkerReceipt(worker_id, state, request.task_id)
        with self._lock:
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
                if self._cancellable_runner is None:
                    return False
                record.cancel_requested.set()
                return True
            record.result = cancelled_worker_result(record.request)
            record.receipt = WorkerReceipt(worker_id, WorkerState.CANCELLED, record.request.task_id)
            record.completed.set()
            return True


@dataclass
class _DispatchRecord:
    request: WorkerRequest
    adapter: Any
    receipt: WorkerReceipt
    result: WorkerResult | None = None
    finish_lock: threading.Condition = field(default_factory=threading.Condition)
    lifecycle_ready: threading.Event = field(default_factory=threading.Event)
    dispatch_ready: threading.Event = field(default_factory=threading.Event)
    cancel_in_progress: bool = False
    cancellation_decided: bool = False
    cancellation_accepted: bool = False
    cancellation_error: BaseException | None = None
    cancellation_abandoned: bool = False
    forced_result: WorkerResult | None = None


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
        acceptance_key = worker_acceptance_key(request)
        body = {
            "retry_identity": request.retry_identity,
            "acceptance_identity_key": acceptance_key,
        }
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
                    f"{request.retry_identity}:{acceptance_key}:{event_name}"
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
                if existing_record.request != request:
                    raise ValueError("worker replay request mismatch")
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

    def _commit_result(self, record: _DispatchRecord, result: WorkerResult) -> WorkerResult:
        with record.finish_lock:
            while (
                record.cancel_in_progress
                and not record.cancellation_abandoned
                and record.result is None
            ):
                record.finish_lock.wait()
            if record.result is not None:
                return record.result
            if record.forced_result is not None:
                result = record.forced_result
            elif record.cancellation_accepted:
                result = cancelled_worker_result(record.request)
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

    def _finish(self, record: _DispatchRecord, timeout: float | None = None) -> WorkerResult:
        if record.result is not None:
            return record.result
        try:
            result = collect_adapter_result(
                record.adapter, record.receipt.worker_id, timeout
            )
            result = normalize_worker_result(result, record.request)
        except TimeoutError:
            raise
        except WorkerResultContractError as error:
            result = failed_worker_result(record.request, "invalid_result_contract", str(error))
        except Exception as error:
            result = failed_worker_result(record.request, "worker_exception", str(error))
        return self._commit_result(record, result)

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
        with record.finish_lock:
            if record.result is not None or record.receipt.state in TERMINAL_WORKER_STATES:
                return record.receipt
            if adapter_receipt.state not in TERMINAL_WORKER_STATES:
                record.receipt = WorkerReceipt(
                    worker_id,
                    adapter_receipt.state,
                    record.receipt.task_id,
                    record.receipt.fallback_used,
                )
            else:
                return record.receipt
        return record.receipt

    def cancel(
        self,
        worker_id: str,
        timeout: float | None = DEFAULT_CANCELLATION_TIMEOUT_SECONDS,
    ) -> bool:
        if timeout is not None and timeout < 0:
            raise ValueError("cancellation timeout cannot be negative")
        with self._lock:
            try:
                record = self._records[worker_id]
            except KeyError as error:
                raise KeyError(f"unknown worker: {worker_id}") from error
        record.lifecycle_ready.wait()
        started_at = time.monotonic()
        decision_timeout_result = cancelled_worker_result(
            record.request,
            "cancellation_decision_timeout",
            "provider cancellation decision exceeded its deadline",
        )
        try:
            accepted = request_adapter_cancellation(
                record, worker_id, timeout, decision_timeout_result
            )
        except TimeoutError:
            self._commit_result(record, decision_timeout_result)
            raise
        if not accepted:
            return False
        remaining = (
            None
            if timeout is None
            else max(0.0, timeout - (time.monotonic() - started_at))
        )
        try:
            self._finish(record, timeout=remaining)
        except TimeoutError:
            self._commit_result(record, cancelled_worker_result(record.request))
        return True
