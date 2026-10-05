"""Capacity-aware routing across provider/model worker candidates."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
import threading
import time
from typing import Any

from workflow_core.assignments import RouteCandidate
from workflow_core.events import WorkflowEvent, WorkflowEventStore

from .circuit_breaker import CircuitBreakerStore, FailureKind
from .worker_dispatch import (
    DEFAULT_CANCELLATION_TIMEOUT_SECONDS,
    TERMINAL_WORKER_STATES,
    WorkerReceipt,
    WorkerRequest,
    WorkerResult,
    WorkerState,
    cancelled_worker_result,
    collect_adapter_result,
    failed_worker_result,
    request_adapter_cancellation,
    worker_acceptance_key,
    worker_id_for,
    worker_request_identity,
)


class WorkspaceUnavailableError(RuntimeError):
    """The request's workspace cannot host a worker; not a provider failure."""


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
    explicit_model_selection: bool | None = None
    result: WorkerResult | None = None
    released: bool = False
    finish_lock: threading.Condition = field(default_factory=threading.Condition)
    cancel_in_progress: bool = False
    cancellation_decided: bool = False
    cancellation_accepted: bool = False
    cancellation_error: BaseException | None = None
    cancellation_abandoned: bool = False
    forced_result: WorkerResult | None = None


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
        self._pending: dict[tuple[str, str, str], threading.Event] = {}
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
        explicit_model_selection: bool | None = None,
    ) -> None:
        acceptance_key = worker_acceptance_key(request)
        payload: dict[str, Any] = {
            "retry_identity": request.retry_identity,
            "acceptance_identity_key": acceptance_key,
            "requested_tier": request.reasoning,
        }
        route_key = "none"
        if candidate is not None:
            payload.update(
                {
                    "provider": candidate.provider,
                    "selection_mode": candidate.selection_mode,
                    "fallback_used": candidate.fallback,
                }
            )
            if candidate.selection_mode == "explicit":
                payload["model"] = candidate.model
            if candidate.effort is not None:
                payload["effort"] = candidate.effort
            route_key = f"{candidate.provider}:{candidate.selection_mode}:{candidate.model}:{candidate.effort or 'none'}"
        if explicit_model_selection is not None:
            payload["explicit_model_selection"] = explicit_model_selection
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
                    f"{acceptance_key}:"
                    f"route:{name}:{route_key}"
                ),
            )
        )

    def _emit_worker_result(
        self,
        record: "_RouteRecord",
        result: WorkerResult,
    ) -> None:
        assert result.acceptance_identity is not None
        assert record.request.acceptance_identity is not None
        result_payload = {
            "worker_id": record.receipt.worker_id,
            "status": result.status,
            "schema_version": result.schema_version,
            "request_acceptance_identity": record.request.acceptance_identity.to_dict(),
            "result_acceptance_identity": result.acceptance_identity.to_dict(),
            "request_workspace_id": str(
                record.request.isolation_policy.get("workspace_id", "")
            ),
            "tests": [
                test.to_dict() for test in result.tests if test.auditable
            ],
        }
        if record.candidate is not None and record.candidate.effort is not None:
            result_payload["effort"] = record.candidate.effort
        self.event_store.append(
            WorkflowEvent.create(
                event_type="worker.result",
                workflow_id=record.request.workflow_id,
                task_id=record.request.task_id,
                payload=result_payload,
                idempotency_key=(
                    f"{record.request.workflow_id}:{record.request.task_id}:"
                    f"worker.result:{record.receipt.worker_id}"
                ),
            )
        )

    def _blocked(self, request: WorkerRequest, blocker: str) -> RoutedWorkerReceipt:
        worker_id = worker_id_for("routed", request)
        receipt = RoutedWorkerReceipt(
            worker_id, WorkerState.FAILED, request.task_id, "", "", False
        )
        with self._lock:
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
                record = self._records[previous]
                if record.request != request:
                    raise ValueError("worker replay request mismatch")
                return record.receipt
            pending = self._pending.get(identity)
            owner = pending is None
            if owner:
                pending = threading.Event()
                self._pending[identity] = pending
        assert pending is not None
        if not owner:
            pending.wait()
            with self._lock:
                record = self._records[self._identities[identity]]
                if record.request != request:
                    raise ValueError("worker replay request mismatch")
                return record.receipt
        try:
            return self._dispatch_new(request, identity)
        finally:
            with self._lock:
                self._pending.pop(identity, None)
                pending.set()

    def _dispatch_new(
        self,
        request: WorkerRequest,
        identity: tuple[str, str, str],
    ) -> RoutedWorkerReceipt:
        self._emit(request, "requested")
        if not self._context_available(request):
            return self._blocked(request, "context_unavailable")

        routes = tuple(self.resolver(request))
        if request.route_affinity is not None:
            affinity = request.route_affinity
            selected = next(
                (
                    candidate
                    for candidate in routes
                    if (candidate.provider, candidate.model) == affinity
                    or (candidate.provider, candidate.model, candidate.effort or "") == affinity
                ),
                None,
            )
            if selected is None:
                return self._blocked(request, "route_affinity_invalid")
            routes = (selected,) + tuple(candidate for candidate in routes if candidate != selected)
        deadline = time.monotonic() + self.max_wait_seconds

        for candidate in routes:
                explicit_model_selection: bool | None = None
                health_check = self.health.get(candidate.provider)
                if health_check is not None:
                    health = health_check(candidate)
                    available = bool(getattr(health, "available", health))
                    if not available:
                        self.breakers.record_failure(
                            candidate.provider,
                            candidate.model,
                            FailureKind.SERVICE,
                            effort=candidate.effort,
                            workflow_id=request.workflow_id,
                            task_id=request.task_id,
                        )
                        self._emit(request, "unavailable", candidate=candidate, reason="unhealthy")
                        continue
                    explicit_model_selection = getattr(
                        health, "explicit_model_selection", None
                    )
                if (
                    candidate.provider == "antigravity"
                    and candidate.selection_mode == "explicit"
                    and explicit_model_selection is not True
                ):
                    reason = (
                        "explicit_model_selection_unsupported"
                        if explicit_model_selection is False
                        else "explicit_model_selection_unverified"
                    )
                    self._emit(
                        request,
                        "unavailable",
                        candidate=candidate,
                        reason=reason,
                        explicit_model_selection=explicit_model_selection,
                    )
                    continue
                preflight = self.breakers.can_attempt(
                    candidate.provider, candidate.model, effort=candidate.effort
                )
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
                remaining = max(0.0, deadline - time.monotonic())
                if not capacity.acquire(timeout=remaining):
                    self._emit(
                        request, "unavailable", candidate=candidate, reason="capacity_timeout"
                    )
                    continue
                decision = self.breakers.acquire(
                    candidate.provider, candidate.model, effort=candidate.effort
                )
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
                except WorkspaceUnavailableError:
                    capacity.release()
                    self.breakers.release_probe(
                        candidate.provider, candidate.model, effort=candidate.effort
                    )
                    self._emit(
                        request, "unavailable", candidate=candidate, reason="workspace_unavailable"
                    )
                    continue
                except Exception:
                    capacity.release()
                    self.breakers.record_failure(
                        candidate.provider,
                        candidate.model,
                        FailureKind.SERVICE,
                        effort=candidate.effort,
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
                        effort=candidate.effort,
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
                record = _RouteRecord(
                    request,
                    receipt,
                    candidate,
                    adapter,
                    capacity,
                    explicit_model_selection,
                )
                with self._lock:
                    self._records[receipt.worker_id] = record
                    self._identities[identity] = receipt.worker_id
                def on_started(started: WorkerReceipt) -> None:
                    record.receipt = RoutedWorkerReceipt(
                        started.worker_id,
                        started.state,
                        started.task_id,
                        candidate.provider,
                        candidate.model,
                        candidate.fallback,
                    )
                try:
                    started = adapter.start(receipt.worker_id, on_started=on_started)
                except Exception:
                    started = False
                if not started:
                    try:
                        adapter.cancel(receipt.worker_id)
                    except Exception:
                        pass
                    self._release(record)
                    self.breakers.release_probe(
                        candidate.provider, candidate.model, effort=candidate.effort
                    )
                    with self._lock:
                        self._records.pop(receipt.worker_id, None)
                        self._identities.pop(identity, None)
                    self._emit(
                        request,
                        "unavailable",
                        candidate=candidate,
                        reason="adapter_start_failed",
                    )
                    continue
                self._emit(
                    request,
                    "assigned",
                    candidate=candidate,
                    worker_id=receipt.worker_id,
                    reason="fallback_selected" if candidate.fallback else "preferred_selected",
                    explicit_model_selection=explicit_model_selection,
                )
                self._emit(
                    request,
                    "started",
                    candidate=candidate,
                    worker_id=receipt.worker_id,
                    explicit_model_selection=explicit_model_selection,
                )
                if started:
                    self._emit(
                        request,
                        "context_loaded",
                        candidate=candidate,
                        worker_id=receipt.worker_id,
                        explicit_model_selection=explicit_model_selection,
                    )
                    self._emit(
                        request,
                        "progress_updated",
                        candidate=candidate,
                        worker_id=receipt.worker_id,
                        explicit_model_selection=explicit_model_selection,
                    )
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

    def _commit_result(self, record: _RouteRecord, result: WorkerResult) -> WorkerResult:
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
                failure_kind = FailureKind(provider_failure)
                if failure_kind is FailureKind.CANCELLED:
                    self.breakers.release_probe(
                        candidate.provider, candidate.model, effort=candidate.effort
                    )
                else:
                    self.breakers.record_failure(
                        candidate.provider,
                        candidate.model,
                        failure_kind,
                        effort=candidate.effort,
                        workflow_id=record.request.workflow_id,
                        task_id=record.request.task_id,
                    )
            elif "invalid_result_contract" in result.blockers or result.status == "cancelled":
                self.breakers.release_probe(
                    candidate.provider, candidate.model, effort=candidate.effort
                )
            else:
                self.breakers.record_success(
                    candidate.provider,
                    candidate.model,
                    effort=candidate.effort,
                    workflow_id=record.request.workflow_id,
                    task_id=record.request.task_id,
                )
            state = {
                "completed": WorkerState.COMPLETED,
                "failed": WorkerState.FAILED,
                "cancelled": WorkerState.CANCELLED,
            }[result.status]
            record.receipt = RoutedWorkerReceipt(
                record.receipt.worker_id,
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
                worker_id=record.receipt.worker_id,
                explicit_model_selection=record.explicit_model_selection,
            )
            if (
                result.status == "completed"
                and result.schema_version == "2.3"
                and result.acceptance_identity is not None
                and record.request.acceptance_identity is not None
            ):
                self._emit_worker_result(record, result)
            return result

    def collect_result(self, worker_id: str, timeout: float | None = None) -> WorkerResult:
        record = self._records[worker_id]
        with record.finish_lock:
            if record.result is not None:
                return record.result
        result = collect_adapter_result(record.adapter, worker_id, timeout)
        return self._commit_result(record, result)

    def status(self, worker_id: str) -> RoutedWorkerReceipt:
        record = self._records[worker_id]
        if record.adapter is not None and record.result is None:
            receipt = record.adapter.status(worker_id)
            candidate = record.candidate
            assert candidate is not None
            with record.finish_lock:
                if record.result is not None or record.receipt.state in TERMINAL_WORKER_STATES:
                    return record.receipt
                record.receipt = RoutedWorkerReceipt(
                    worker_id,
                    receipt.state,
                    receipt.task_id,
                    candidate.provider,
                    candidate.model,
                    candidate.fallback,
                )
        return record.receipt

    def cancel(
        self,
        worker_id: str,
        timeout: float | None = DEFAULT_CANCELLATION_TIMEOUT_SECONDS,
    ) -> bool:
        if timeout is not None and timeout < 0:
            raise ValueError("cancellation timeout cannot be negative")
        record = self._records[worker_id]
        if record.adapter is None:
            return False
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
            self.collect_result(worker_id, timeout=remaining)
        except TimeoutError:
            self._commit_result(record, cancelled_worker_result(record.request))
        return True
