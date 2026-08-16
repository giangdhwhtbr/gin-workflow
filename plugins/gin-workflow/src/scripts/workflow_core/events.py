"""Deterministic, idempotent, concurrency-safe workflow event persistence."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Iterator, Mapping

from .atomic import atomic_write_bytes
from .models import WorkflowCoreError, freeze, thaw
from .schemas import validate_workflow_event


class EventPersistenceError(WorkflowCoreError):
    """Raised when an existing event stream is invalid or cannot be persisted."""


def _canonical_json(value: object) -> str:
    return json.dumps(thaw(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


_TERMINAL_WORKER_EVENTS = {"worker.completed", "worker.failed", "worker.cancelled"}


def _deterministic_event_id(
    *,
    event_type: str,
    workflow_id: str,
    task_id: str | None,
    payload: Mapping[str, Any],
    idempotency_key: str | None,
) -> str:
    identity: dict[str, Any] = {
        "event_type": event_type,
        "workflow_id": workflow_id,
        "task_id": task_id,
        "idempotency_key": idempotency_key,
    }
    if event_type not in _TERMINAL_WORKER_EVENTS:
        identity["payload"] = payload
    digest = hashlib.sha256(_canonical_json(identity).encode("utf-8")).hexdigest()
    return f"evt-{digest}"


def _validate_event_mapping(value: Mapping[str, Any]) -> None:
    required = {"event_id", "event_type", "workflow_id", "timestamp", "task_id", "payload"}
    missing = sorted(required.difference(value))
    if missing:
        raise EventPersistenceError(
            f"workflow event is missing required fields: {', '.join(missing)}"
        )
    payload = value.get("payload")
    if not isinstance(payload, Mapping):
        raise EventPersistenceError("workflow event payload must be an object")
    try:
        validate_workflow_event(thaw(value))
    except ValueError as error:
        raise EventPersistenceError("workflow event failed schema validation") from error
    expected_id = _deterministic_event_id(
        event_type=value["event_type"],
        workflow_id=value["workflow_id"],
        task_id=value["task_id"],
        payload=payload,
        idempotency_key=value.get("idempotency_key"),
    )
    if value["event_id"] != expected_id:
        raise EventPersistenceError(
            "workflow event_id does not match deterministic event identity"
        )


@dataclass(frozen=True)
class WorkflowEvent:
    event_id: str
    event_type: str
    workflow_id: str
    timestamp: str
    task_id: str | None = None
    payload: Mapping[str, Any] | None = None
    actor: str | None = None
    idempotency_key: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "payload", freeze({} if self.payload is None else self.payload))

    @classmethod
    def create(
        cls,
        *,
        event_type: str,
        workflow_id: str,
        task_id: str | None = None,
        payload: Mapping[str, Any] | None = None,
        timestamp: str | None = None,
        actor: str | None = None,
        idempotency_key: str | None = None,
    ) -> "WorkflowEvent":
        if not event_type or not workflow_id:
            raise ValueError("event_type and workflow_id are required")
        if payload is not None and not isinstance(payload, Mapping):
            raise ValueError("workflow event payload must be an object")
        immutable_payload = freeze({} if payload is None else payload)
        event_id = _deterministic_event_id(
            event_type=event_type,
            workflow_id=workflow_id,
            task_id=task_id,
            payload=immutable_payload,
            idempotency_key=idempotency_key,
        )
        return cls(
            event_id=event_id,
            event_type=event_type,
            workflow_id=workflow_id,
            task_id=task_id,
            payload=immutable_payload,
            timestamp=timestamp or _now(),
            actor=actor,
            idempotency_key=idempotency_key,
        )

    def to_dict(self) -> dict[str, Any]:
        result = {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "workflow_id": self.workflow_id,
            "timestamp": self.timestamp,
            "task_id": self.task_id,
            "payload": thaw(self.payload),
        }
        if self.actor is not None:
            result["actor"] = self.actor
        if self.idempotency_key is not None:
            result["idempotency_key"] = self.idempotency_key
        return result

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "WorkflowEvent":
        if not isinstance(value, Mapping):
            raise EventPersistenceError("workflow event must be an object")
        _validate_event_mapping(value)
        return cls(
            event_id=value["event_id"],
            event_type=value["event_type"],
            workflow_id=value["workflow_id"],
            timestamp=value["timestamp"],
            task_id=value["task_id"],
            payload=value["payload"],
            actor=value.get("actor"),
            idempotency_key=value.get("idempotency_key"),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "WorkflowEvent":
        return cls.from_mapping(value)


@contextmanager
def _file_lock(path: Path, *, exclusive: bool) -> Iterator[None]:
    try:
        import fcntl
    except ImportError as error:  # pragma: no cover - current supported harnesses are POSIX
        raise EventPersistenceError("event persistence requires POSIX advisory file locking") from error
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _decode_events(content: bytes, path: Path) -> list[WorkflowEvent]:
    events: list[WorkflowEvent] = []
    seen: set[str] = set()
    for line_number, raw_line in enumerate(content.splitlines(), start=1):
        if not raw_line.strip():
            continue
        try:
            value = json.loads(raw_line)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise EventPersistenceError(
                f"invalid JSONL event at {path}:{line_number}: {error}"
            ) from error
        if not isinstance(value, Mapping):
            raise EventPersistenceError(f"event at {path}:{line_number} must be an object")
        event = WorkflowEvent.from_mapping(value)
        if event.event_id in seen:
            raise EventPersistenceError(
                f"duplicate event_id in existing stream at {path}:{line_number}: {event.event_id}"
            )
        seen.add(event.event_id)
        events.append(event)
    return events


class WorkflowEventStore:
    """JSONL store serialized through a stable sidecar advisory lock."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.lock_path = self.path.with_name(f"{self.path.name}.lock")

    def append(self, event: WorkflowEvent) -> bool:
        if not isinstance(event, WorkflowEvent):
            raise TypeError("event must be a WorkflowEvent")
        _validate_event_mapping(event.to_dict())
        with _file_lock(self.lock_path, exclusive=True):
            current = self.path.read_bytes() if self.path.exists() else b""
            existing = _decode_events(current, self.path)
            if any(item.event_id == event.event_id for item in existing):
                return False
            prefix = current
            if prefix and not prefix.endswith(b"\n"):
                prefix += b"\n"
            line = (_canonical_json(event.to_dict()) + "\n").encode("utf-8")
            atomic_write_bytes(self.path, prefix + line)
            return True

    def read_all(self) -> list[WorkflowEvent]:
        with _file_lock(self.lock_path, exclusive=False):
            if not self.path.exists():
                return []
            return _decode_events(self.path.read_bytes(), self.path)


EventStore = WorkflowEventStore


def append_workflow_event(path: Path, event: WorkflowEvent) -> bool:
    return WorkflowEventStore(path).append(event)
