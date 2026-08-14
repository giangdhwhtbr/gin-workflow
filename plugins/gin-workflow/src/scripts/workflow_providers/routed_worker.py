"""Capacity-aware routing across provider/model worker candidates."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
import threading
from typing import Any

from workflow_core.assignments import RouteCandidate
from workflow_core.events import WorkflowEvent, WorkflowEventStore

from .circuit_breaker import CircuitBreakerStore, FailureKind
from .worker_dispatch import (
    TERMINAL_WORKER_STATES,
    WorkerReceipt,
    WorkerRequest,
    WorkerResult,
    WorkerState,
    failed_worker_result,
    worker_id_for,
    worker_request_identity,
)


@dataclass(frozen=True)
class RoutedWorkerReceipt:
    worker_id: str
    state: WorkerState
    task_id: str
    provider_name: str
    model_alias: str
    fallback_used: bool


@dataclass
class _RouteRecord:
    request: WorkerRequest
    receipt: RoutedWorkerReceipt
    candidate: RouteCandidate | None = None
    adapter: Any = None
    capacity: threading.BoundedSemaphore | None = None
    result: WorkerResult | None = None
    released: bool = False
    finish_lock: threading.Lock = field(default_factory=threading.Lock)


class RoutedWorkerDispatcher:
    """Resolve current route health/capacity before delegating native lifecycle."""

    def __init__(
        self,
        resolver: Callable[[WorkerRequest], tuple[RouteCandidate, ...]],
        adapter_factory: Callable[[RouteCandidate, WorkerRequest], Any],
        breakers: CircuitBreakerStore,
        event_store: WorkflowEventStore,
        *,
        concurrency: Mapping[str, int],
        max_wait_seconds: float,
        health: Mapping[str, Callable[[RouteCandidate], Any]] | None = None,
    ) -> None:
        if max_wait_seconds < 0:
            raise ValueError("max_wait_seconds cannot be negative")
        if not concurrency or any(int(limit) < 1 for limit in concurrency.values()):
            raise ValueError("provider concurrency limits must be positive")
        self.resolver = resolver
        self.adapter_factory = adapter_factory
        self.breakers = breakers
        self.event_store = event_store
        self.max_wait_seconds = float(max_wait_seconds)
        self.health = dict(health or {})
        self._capacity = {
            str(provider): threading.BoundedSemaphore(int(limit))
            for provider, limit in concurrency.items()
        }
        self._records: dict[str, _RouteRecord] = {}
        self._identities: dict[tuple[str, str, str], str] = {}
        self._lock = threading.RLock()

    @staticmethod
    def _context_available(request: WorkerRequest) -> bool:
        return all(
            not (isinstance(item, Mapping) and item.get("available") is False)
            for item in request.generated_manifest.categories["required"]
        )

    def _emit(
        self,
        request: WorkerRequest,
        name: str,
        *,
        candidate: RouteCandidate | None = None,
        worker_id: str = "",
        reason: str = "",
    ) -> None:
        payload: dict[str, Any] = {"retry_identity": request.retry_identity}
        route_key = "none"
        if candidate is not None:
            payload.update(
                {
                    "provider": candidate.provider,
                    "model": candidate.model,
                    "fallback_used": candidate.fallback,
                }
            )
            route_key = f"{candidate.provider}:{candidate.model}"
        if worker_id:
            payload["worker_id"] = worker_id
        if reason:
            payload["reason"] = reason
        self.event_store.append(
            WorkflowEvent.create(
                event_type=f"worker.{name}",
                workflow_id=request.workflow_id,
                task_id=request.task_id,
                payload=payload,
                idempotency_key=(
                    f"{request.workflow_id}:{request.task_id}:{request.retry_identity}:"
                    f"route:{name}:{route_key}"
                ),
            )
        )

    def _blocked(self, request: WorkerRequest, blocker: str) -> RoutedWorkerReceipt:
        worker_id = worker_id_for("routed", request)
        receipt = RoutedWorkerReceipt(
            worker_id, WorkerState.FAILED, request.task_id, "", "", False
        )
        self._records[worker_id] = _RouteRecord(
            request, receipt, result=failed_worker_result(request, blocker)
        )
        self._identities[worker_request_identity(request)] = worker_id
        self._emit(request, "failed", worker_id=worker_id, reason=blocker)
        return receipt

    def dispatch(self, request: WorkerRequest) -> RoutedWorkerReceipt:
        identity = worker_request_identity(request)
        with self._lock:
            previous = self._identities.get(identity)
            if previous is not None:
                return self._records[previous].receipt
            self._emit(request, "requested")
            if not self._context_available(request):
                return self._blocked(request, "context_unavailable")

            for candidate in self.resolver(request):
                health_check = self.health.get(candidate.provider)
                if health_check is not None:
                    health = health_check(candidate)
                    available = bool(getattr(health, "available", health))
                    if not available:
                        self.breakers.record_failure(
                            candidate.provider,
                            candidate.model,
                            FailureKind.SERVICE,
                            workflow_id=request.workflow_id,
                            task_id=request.task_id,
                        )
                        self._emit(request, "unavailable", candidate=candidate, reason="unhealthy")
                        continue
                preflight = self.breakers.can_attempt(candidate.provider, candidate.model)
                if not preflight.allowed:
                    self._emit(
                        request,
                        "unavailable",
                        candidate=candidate,
                        reason=f"circuit_{preflight.state.value}",
                    )
                    continue
                capacity = self._capacity.get(candidate.provider)
                if capacity is None:
                    self._emit(
                        request, "unavailable", candidate=candidate, reason="capacity_unconfigured"
                    )
                    continue
                if not capacity.acquire(timeout=self.max_wait_seconds):
                    self._emit(
                        request, "unavailable", candidate=candidate, reason="capacity_timeout"
                    )
                    continue
                decision = self.breakers.acquire(candidate.provider, candidate.model)
                if not decision.allowed:
                    capacity.release()
                    self._emit(
                        request,
                        "unavailable",
                        candidate=candidate,
                        reason=f"circuit_{decision.state.value}",
                    )
                    continue
                try:
                    adapter = self.adapter_factory(candidate, request)
                    adapter_receipt: WorkerReceipt = adapter.prepare(request)
                except Exception:
                    capacity.release()
                    self.breakers.record_failure(
                        candidate.provider,
                        candidate.model,
                        FailureKind.SERVICE,
                        workflow_id=request.workflow_id,
                        task_id=request.task_id,
                    )
                    self._emit(
                        request, "unavailable", candidate=candidate, reason="adapter_unavailable"
                    )
                    continue
                if adapter_receipt.state is WorkerState.UNAVAILABLE:
                    capacity.release()
                    self.breakers.record_failure(
                        candidate.provider,
                        candidate.model,
                        FailureKind.SERVICE,
                        workflow_id=request.workflow_id,
                        task_id=request.task_id,
                    )
                    self._emit(
                        request, "unavailable", candidate=candidate, reason="adapter_unavailable"
                    )
                    continue

                receipt = RoutedWorkerReceipt(
                    adapter_receipt.worker_id,
                    adapter_receipt.state,
                    request.task_id,
                    candidate.provider,
                    candidate.model,
                    candidate.fallback,
                )
                record = _RouteRecord(request, receipt, candidate, adapter, capacity)
                self._records[receipt.worker_id] = record
                self._identities[identity] = receipt.worker_id
                self._emit(
                    request,
                    "assigned",
                    candidate=candidate,
                    worker_id=receipt.worker_id,
                    reason="fallback_selected" if candidate.fallback else "preferred_selected",
                )

                def on_started(started: WorkerReceipt) -> None:
                    record.receipt = RoutedWorkerReceipt(
                        started.worker_id,
                        started.state,
                        started.task_id,
                        candidate.provider,
                        candidate.model,
                        candidate.fallback,
                    )
                    self._emit(request, "started", candidate=candidate, worker_id=started.worker_id)

                if adapter.start(receipt.worker_id, on_started=on_started):
                    self._emit(request, "context_loaded", candidate=candidate, worker_id=receipt.worker_id)
                    self._emit(request, "progress_updated", candidate=candidate, worker_id=receipt.worker_id)
                    threading.Thread(
                        target=self.collect_result,
                        args=(receipt.worker_id,),
                        name=f"route-monitor:{receipt.worker_id}",
                        daemon=True,
                    ).start()
                return record.receipt
            return self._blocked(request, "worker_routes_unavailable")

    def _release(self, record: _RouteRecord) -> None:
        if not record.released and record.capacity is not None:
            record.capacity.release()
            record.released = True

    def collect_result(self, worker_id: str, timeout: float | None = None) -> WorkerResult:
        record = self._records[worker_id]
        with record.finish_lock:
            if record.result is not None:
                return record.result
            result = record.adapter.collect_result(worker_id, timeout=timeout)
            candidate = record.candidate
            assert candidate is not None
            provider_failure = next(
                (
                    blocker.split(":", 1)[1]
                    for blocker in result.blockers
                    if blocker.startswith("provider_failure:")
                ),
                None,
            )
            if provider_failure is not None:
                self.breakers.record_failure(
                    candidate.provider,
                    candidate.model,
                    FailureKind(provider_failure),
                    workflow_id=record.request.workflow_id,
                    task_id=record.request.task_id,
                )
            elif "invalid_result_contract" in result.blockers:
                pass
            else:
                self.breakers.record_success(
                    candidate.provider,
                    candidate.model,
                    workflow_id=record.request.workflow_id,
                    task_id=record.request.task_id,
                )
            state = {
                "completed": WorkerState.COMPLETED,
                "failed": WorkerState.FAILED,
                "cancelled": WorkerState.CANCELLED,
            }[result.status]
            record.receipt = RoutedWorkerReceipt(
                worker_id,
                state,
                record.request.task_id,
                candidate.provider,
                candidate.model,
                candidate.fallback,
            )
            record.result = result
            self._release(record)
            self._emit(
                record.request,
                result.status,
                candidate=candidate,
                worker_id=worker_id,
            )
            return result

    def status(self, worker_id: str) -> RoutedWorkerReceipt:
        record = self._records[worker_id]
        if record.adapter is not None and record.result is None:
            receipt = record.adapter.status(worker_id)
            candidate = record.candidate
            assert candidate is not None
            record.receipt = RoutedWorkerReceipt(
                worker_id,
                receipt.state,
                receipt.task_id,
                candidate.provider,
                candidate.model,
                candidate.fallback,
            )
        return record.receipt

    def cancel(self, worker_id: str) -> bool:
        record = self._records[worker_id]
        if record.adapter is None:
            return False
        cancelled = bool(record.adapter.cancel(worker_id))
        if cancelled:
            self.collect_result(worker_id)
        return cancelled
