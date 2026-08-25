"""Bounded parallel scheduling over provider-neutral worker dispatch."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
import inspect
import threading
from typing import Any, Iterable

from workflow_providers.contracts import OperationStatus, WorkspaceRequest
from workflow_providers.worker_dispatch import (
    WorkerRequest,
    WorkerResult,
    failed_worker_result,
)


@dataclass(frozen=True)
class WorkerStrategy:
    mode: str


@dataclass(frozen=True)
class ExecutionStrategy:
    mode: str
    workers: WorkerStrategy
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "workers": {"mode": self.workers.mode},
            "rationale": self.rationale,
        }


def select_execution_strategy(
    *,
    task_count: int,
    sequential: bool = False,
    parallelizable: bool = False,
    one_agent: bool = False,
    long_running: bool = False,
    specialized: bool = False,
    review: bool = False,
) -> ExecutionStrategy:
    """Select direct execution unless work meets an explicit worker condition."""
    if task_count < 0:
        raise ValueError("task_count cannot be negative")
    if sequential:
        return ExecutionStrategy("direct", WorkerStrategy("sequential"), "work is sequential")
    if one_agent:
        return ExecutionStrategy("direct", WorkerStrategy("sequential"), "one agent requested")
    if task_count <= 3:
        return ExecutionStrategy("direct", WorkerStrategy("sequential"), "three or fewer tasks")
    worker_reason = next(
        (
            reason
            for enabled, reason in (
                (parallelizable, "independent parallel tasks"),
                (long_running, "long-running work"),
                (specialized, "specialized worker required"),
                (review, "independent review required"),
            )
            if enabled
        ),
        None,
    )
    if worker_reason is None:
        return ExecutionStrategy("direct", WorkerStrategy("sequential"), "no worker condition met")
    return ExecutionStrategy("worker", WorkerStrategy("parallel"), worker_reason)


@dataclass(frozen=True)
class ScheduleOutcome:
    completed: tuple[WorkerResult, ...]
    failed: tuple[WorkerResult, ...]


class WorkerScheduler:
    """Claim, isolate, and run each task with bounded concurrency and retries."""

    def __init__(
        self,
        dispatcher: Any,
        *,
        task_tracking: Any,
        workspace: Any,
        max_parallel_workers: int,
        max_retries: int = 0,
        worker_timeout_seconds: float = 600.0,
    ) -> None:
        if max_parallel_workers < 1:
            raise ValueError("max_parallel_workers must be positive")
        if max_retries < 0:
            raise ValueError("max_retries cannot be negative")
        if worker_timeout_seconds <= 0:
            raise ValueError("worker_timeout_seconds must be positive")
        self.dispatcher = dispatcher
        self.task_tracking = task_tracking
        self.workspace = workspace
        self.max_parallel_workers = max_parallel_workers
        self.max_retries = max_retries
        self.worker_timeout_seconds = worker_timeout_seconds
        self._claimed_tasks: set[str] = set()
        self._claim_lock = threading.Lock()

    @staticmethod
    def _validate_requests(requests: tuple[WorkerRequest, ...]) -> None:
        task_ids = [request.task_id for request in requests]
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("one task per worker claim is required")
        workspace_ids: list[str] = []
        for request in requests:
            isolation = request.isolation_policy
            workspace_id = isolation.get("workspace_id")
            branch = isolation.get("branch")
            if isolation.get("mode") != "isolated" or not workspace_id or not branch:
                raise ValueError("workspace isolation requires mode, workspace_id, and branch")
            workspace_ids.append(str(workspace_id))
        if len(workspace_ids) != len(set(workspace_ids)):
            raise ValueError("each worker claim requires a distinct isolated workspace")

    def _claim(self, requests: tuple[WorkerRequest, ...]) -> None:
        with self._claim_lock:
            duplicates = sorted(
                request.task_id for request in requests if request.task_id in self._claimed_tasks
            )
            if duplicates:
                raise ValueError(f"task already claimed: {', '.join(duplicates)}")
            self._claimed_tasks.update(request.task_id for request in requests)

    def _prepare(self, request: WorkerRequest) -> None:
        isolation = request.isolation_policy
        workspace_request = WorkspaceRequest(
            workspace_id=str(isolation["workspace_id"]),
            branch=str(isolation["branch"]),
            base_ref=str(isolation.get("base_ref", "HEAD")),
        )
        created = self.workspace.create(
            workspace_request,
            idempotency_key=f"{request.retry_identity}:workspace:create",
        )
        if created.status is not OperationStatus.SUCCESS:
            raise RuntimeError(created.message or "workspace creation failed")
        isolated = self.workspace.isolate(workspace_request.workspace_id)
        if isolated.status is not OperationStatus.SUCCESS or not isolated.value.isolated:
            raise RuntimeError(isolated.message or "workspace isolation failed")
        assignee = f"worker:{request.workflow_id}:{request.task_id}"
        tracking_task_id = request.task_id
        records = getattr(self.task_tracking, "tasks", None)
        if isinstance(records, dict):
            matching = [
                task_id
                for task_id, record in records.items()
                if getattr(record, "title", None) == request.task_id
            ]
            if len(matching) == 1:
                tracking_task_id = matching[0]
        updated = self.task_tracking.update_task(
            tracking_task_id,
            {"status": "in_progress", "assignee": assignee},
            idempotency_key=f"{request.retry_identity}:task:claim",
        )
        if updated.status is not OperationStatus.SUCCESS:
            raise RuntimeError(updated.message or "task tracking claim failed")

    def _run(self, request: WorkerRequest) -> WorkerResult:
        try:
            self._prepare(request)
        except Exception as error:
            return failed_worker_result(request, "preparation_failed", str(error))
        result: WorkerResult | None = None
        for attempt in range(self.max_retries + 1):
            attempted_request = request if attempt == 0 else self._retry_request(
                request, attempt
            )
            result, retry_safe = self._attempt_with_deadline(attempted_request)
            if result.status == "completed":
                return result
            if not retry_safe:
                return result
        assert result is not None
        return result

    @staticmethod
    def _retry_request(request: WorkerRequest, attempt: int) -> WorkerRequest:
        identity = request.acceptance_identity
        if identity is not None:
            identity = replace(
                identity, attempt_id=f"{identity.attempt_id}:retry:{attempt}"
            )
        return replace(
            request,
            retry_identity=f"{request.retry_identity}:retry:{attempt}",
            acceptance_identity=identity,
        )

    def _attempt_with_deadline(
        self, request: WorkerRequest
    ) -> tuple[WorkerResult, bool]:
        done = threading.Event()
        receipt_ready = threading.Event()
        state_lock = threading.Lock()
        state: dict[str, Any] = {}

        def execute_attempt() -> None:
            try:
                receipt = self.dispatcher.dispatch(request)
                with state_lock:
                    state["receipt"] = receipt
                receipt_ready.set()
                result = self.dispatcher.collect_result(receipt.worker_id)
                retry_safe = True
            except Exception as error:
                result = failed_worker_result(request, "worker_exception", str(error))
                retry_safe = False
            with state_lock:
                state["result"] = result
                state["retry_safe"] = retry_safe
            done.set()
            receipt_ready.set()

        threading.Thread(
            target=execute_attempt,
            name=f"attempt:{request.workflow_id}:{request.task_id}",
            daemon=True,
        ).start()
        if done.wait(timeout=self.worker_timeout_seconds):
            with state_lock:
                return state["result"], state["retry_safe"]

        timeout_result = failed_worker_result(
            request,
            "timeout",
            f"worker attempt exceeded {self.worker_timeout_seconds} seconds",
        )
        with state_lock:
            if done.is_set():
                return state["result"], state["retry_safe"]
            receipt = state.get("receipt")
        if receipt is None:
            receipt_ready.wait(timeout=self.worker_timeout_seconds)
            with state_lock:
                if done.is_set():
                    return state["result"], state["retry_safe"]
                receipt = state.get("receipt")
            if receipt is None:
                return timeout_result, False

        try:
            cancel = self.dispatcher.cancel
            parameters = inspect.signature(cancel).parameters.values()
            supports_timeout = "timeout" in inspect.signature(cancel).parameters or any(
                parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in parameters
            )
            accepted = (
                cancel(receipt.worker_id, timeout=self.worker_timeout_seconds)
                if supports_timeout
                else cancel(receipt.worker_id)
            )
            if accepted:
                quiescent = done.wait(timeout=self.worker_timeout_seconds)
                return timeout_result, quiescent
        except Exception:
            return timeout_result, False

        try:
            status = self.dispatcher.status(receipt.worker_id)
            if status.state.value in {"completed", "failed", "cancelled", "unavailable"}:
                terminal = self.dispatcher.collect_result(receipt.worker_id, timeout=0)
                return terminal, True
        except Exception:
            pass
        return timeout_result, False

    def schedule(self, requests: Iterable[WorkerRequest]) -> ScheduleOutcome:
        selected = tuple(requests)
        if not selected:
            return ScheduleOutcome((), ())
        self._validate_requests(selected)
        self._claim(selected)
        with ThreadPoolExecutor(max_workers=self.max_parallel_workers) as executor:
            results = tuple(executor.map(self._run, selected))
        return ScheduleOutcome(
            tuple(result for result in results if result.status == "completed"),
            tuple(result for result in results if result.status != "completed"),
        )
