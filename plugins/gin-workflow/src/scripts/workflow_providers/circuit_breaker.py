"""Persistent provider/model circuit breakers for native worker routing."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import json
import os
from pathlib import Path
import threading
import time
from typing import Callable

from workflow_core.atomic import atomic_write_text


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half-open"


class FailureKind(str, Enum):
    QUOTA = "quota"
    RATE_LIMIT = "rate_limit"
    AUTH = "auth"
    SERVICE = "service"
    TIMEOUT = "timeout"
    CRASH = "crash"
    TASK = "task"
    TEST = "test"
    REVIEW = "review"
    INVALID_RESULT = "invalid_result"
    CANCELLED = "cancelled"


COUNTED_FAILURES = frozenset(
    {
        FailureKind.QUOTA,
        FailureKind.RATE_LIMIT,
        FailureKind.AUTH,
        FailureKind.SERVICE,
        FailureKind.TIMEOUT,
        FailureKind.CRASH,
    }
)


@dataclass(frozen=True)
class CircuitRecord:
    state: CircuitState = CircuitState.CLOSED
    failures: int = 0
    opened_at: float | None = None
    probes: int = 0
    reason: str | None = None
    transitioned_at: float | None = None
    workflow_id: str | None = None
    task_id: str | None = None


@dataclass(frozen=True)
class CircuitDecision:
    allowed: bool
    state: CircuitState
    reason: str


class CircuitBreakerStore:
    def __init__(
        self,
        path: Path,
        *,
        failure_threshold: int = 1,
        cooldown_seconds: float = 900,
        half_open_max_probes: int = 1,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if failure_threshold < 1 or cooldown_seconds < 0 or half_open_max_probes < 1:
            raise ValueError("invalid circuit breaker policy")
        self.path = Path(path)
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = float(cooldown_seconds)
        self.half_open_max_probes = half_open_max_probes
        self._clock = clock
        self._lock = threading.RLock()
        self._records: dict[tuple[str, str], CircuitRecord] = {}
        self._corrupt_recovery = False
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if raw.get("version") != 1 or not isinstance(raw.get("circuits"), list):
                raise ValueError("unsupported circuit state")
            self._corrupt_recovery = bool(raw.get("corrupt_recovery", False))
            for item in raw["circuits"]:
                key = (str(item["provider"]), str(item["model"]))
                self._records[key] = CircuitRecord(
                    state=CircuitState(item["state"]),
                    failures=int(item.get("failures", 0)),
                    opened_at=item.get("opened_at"),
                    probes=int(item.get("probes", 0)),
                    reason=item.get("reason"),
                    transitioned_at=item.get("transitioned_at"),
                    workflow_id=item.get("workflow_id"),
                    task_id=item.get("task_id"),
                )
        except (OSError, UnicodeDecodeError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            timestamp = int(self._clock() * 1000)
            archive = self.path.with_name(f"{self.path.stem}.corrupt-{timestamp}.json")
            os.replace(self.path, archive)
            self._records.clear()
            self._corrupt_recovery = True

    def _save(self) -> None:
        circuits = []
        for (provider, model), record in sorted(self._records.items()):
            circuits.append(
                {
                    "provider": provider,
                    "model": model,
                    "state": record.state.value,
                    "failures": record.failures,
                    "opened_at": record.opened_at,
                    "probes": record.probes,
                    "reason": record.reason,
                    "transitioned_at": record.transitioned_at,
                    "workflow_id": record.workflow_id,
                    "task_id": record.task_id,
                    "cooldown_seconds": self.cooldown_seconds,
                }
            )
        atomic_write_text(
            self.path,
            json.dumps(
                {
                    "version": 1,
                    "corrupt_recovery": self._corrupt_recovery,
                    "circuits": circuits,
                },
                sort_keys=True,
            )
            + "\n",
        )

    def _record(self, provider: str, model: str) -> CircuitRecord:
        key = (provider, model)
        record = self._records.get(key)
        if record is None:
            if self._corrupt_recovery:
                record = CircuitRecord(
                    state=CircuitState.OPEN,
                    failures=self.failure_threshold,
                    opened_at=self._clock(),
                    reason="corrupt_state_recovery",
                    transitioned_at=self._clock(),
                )
                self._records[key] = record
                self._save()
            else:
                record = CircuitRecord()
        return record

    def state(self, provider: str, model: str) -> CircuitRecord:
        with self._lock:
            return self._record(provider, model)

    def can_attempt(self, provider: str, model: str) -> CircuitDecision:
        """Preview availability without claiming a half-open probe."""
        with self._lock:
            record = self._record(provider, model)
            if record.state is CircuitState.CLOSED:
                return CircuitDecision(True, record.state, "closed")
            if record.state is CircuitState.HALF_OPEN:
                allowed = record.probes < self.half_open_max_probes
                return CircuitDecision(
                    allowed,
                    record.state,
                    "half_open_ready" if allowed else "half_open_probe_limit",
                )
            opened_at = self._clock() if record.opened_at is None else record.opened_at
            if self._clock() - float(opened_at) >= self.cooldown_seconds:
                return CircuitDecision(True, CircuitState.HALF_OPEN, "cooldown_elapsed")
            return CircuitDecision(False, CircuitState.OPEN, record.reason or "cooldown")

    def acquire(self, provider: str, model: str) -> CircuitDecision:
        with self._lock:
            key = (provider, model)
            record = self._record(provider, model)
            if record.state is CircuitState.CLOSED:
                return CircuitDecision(True, record.state, "closed")
            if record.state is CircuitState.OPEN:
                opened_at = self._clock() if record.opened_at is None else record.opened_at
                elapsed = self._clock() - float(opened_at)
                if elapsed < self.cooldown_seconds:
                    return CircuitDecision(False, record.state, record.reason or "cooldown")
                record = replace(
                    record,
                    state=CircuitState.HALF_OPEN,
                    probes=0,
                    transitioned_at=self._clock(),
                )
            if record.probes >= self.half_open_max_probes:
                self._records[key] = record
                self._save()
                return CircuitDecision(False, CircuitState.HALF_OPEN, "half_open_probe_limit")
            record = replace(record, probes=record.probes + 1)
            self._records[key] = record
            self._save()
            return CircuitDecision(True, CircuitState.HALF_OPEN, "half_open_probe")

    def record_failure(
        self,
        provider: str,
        model: str,
        kind: FailureKind,
        *,
        workflow_id: str | None = None,
        task_id: str | None = None,
    ) -> CircuitRecord:
        with self._lock:
            record = self._record(provider, model)
            if kind not in COUNTED_FAILURES:
                return record
            failures = record.failures + 1
            state = record.state
            opened_at = record.opened_at
            if state is CircuitState.HALF_OPEN or failures >= self.failure_threshold:
                state = CircuitState.OPEN
                opened_at = self._clock()
            updated = CircuitRecord(
                state=state,
                failures=failures,
                opened_at=opened_at,
                probes=0,
                reason=kind.value,
                transitioned_at=self._clock(),
                workflow_id=workflow_id,
                task_id=task_id,
            )
            self._records[(provider, model)] = updated
            self._save()
            return updated

    def record_success(
        self,
        provider: str,
        model: str,
        *,
        workflow_id: str | None = None,
        task_id: str | None = None,
    ) -> CircuitRecord:
        with self._lock:
            updated = CircuitRecord(
                reason="success",
                transitioned_at=self._clock(),
                workflow_id=workflow_id,
                task_id=task_id,
            )
            self._records[(provider, model)] = updated
            self._save()
            return updated
