"""Provider-neutral lifecycle contracts and normalized operation results."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass, replace
from enum import Enum
import hashlib
import json
from pathlib import Path
from typing import Any, Generic, Mapping, Protocol, TypeVar, runtime_checkable

from workflow_core.identity import AcceptanceIdentity


T = TypeVar("T")


class OperationStatus(str, Enum):
    SUCCESS = "success"
    UNAVAILABLE = "unavailable"
    INVALID = "invalid"


class ProviderHealth(str, Enum):
    AVAILABLE = "available"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class ProviderResult(Generic[T]):
    status: OperationStatus
    value: T | None = None
    message: str = ""
    idempotent: bool = False

    @classmethod
    def success(cls, value: T, *, idempotent: bool = False) -> "ProviderResult[T]":
        return cls(OperationStatus.SUCCESS, value, idempotent=idempotent)

    @classmethod
    def unavailable(cls, message: str) -> "ProviderResult[T]":
        return cls(OperationStatus.UNAVAILABLE, message=message)

    @classmethod
    def invalid(cls, message: str) -> "ProviderResult[T]":
        return cls(OperationStatus.INVALID, message=message)


@dataclass(frozen=True)
class ProviderMetadata:
    name: str
    provider_type: str
    capabilities: frozenset[str]
    health: ProviderHealth
    detail: str = ""


SUPPORTED_TASK_STATUSES = frozenset({"open", "in_progress", "blocked", "deferred", "closed"})


def validate_task_status(status: object) -> str | None:
    candidate = str(status).strip()
    if candidate not in SUPPORTED_TASK_STATUSES:
        return f"unsupported task status: {candidate or '<empty>'}"
    return None


SUPPORTED_TASK_ATTRIBUTES = frozenset({"priority", "assignee"})


def validate_task_attributes(attributes: Mapping[str, Any]) -> str | None:
    if not isinstance(attributes, Mapping):
        return "task attributes must be a mapping"
    if unknown := set(attributes) - SUPPORTED_TASK_ATTRIBUTES:
        return f"unsupported task attributes: {', '.join(sorted(unknown))}"
    return None


def normalize_task_changes(changes: Mapping[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    allowed = {"title", "description", "status", "attributes"} | SUPPORTED_TASK_ATTRIBUTES
    if unknown := set(changes) - allowed:
        return None, f"unsupported task fields: {', '.join(sorted(unknown))}"
    normalized = {key: value for key, value in changes.items() if key != "attributes"}
    attributes = changes.get("attributes", {})
    if not isinstance(attributes, Mapping):
        return None, "task attributes must be a mapping"
    if error := validate_task_attributes(attributes):
        return None, error
    for key, value in attributes.items():
        if key in normalized and normalized[key] != value:
            return None, f"conflicting task attribute: {key}"
        normalized[key] = value
    if "title" in normalized and not str(normalized["title"]).strip():
        return None, "title cannot be empty"
    if "status" in normalized:
        if error := validate_task_status(normalized["status"]):
            return None, error
    return normalized, None


@dataclass(frozen=True)
class TaskCreateRequest:
    title: str
    description: str = ""
    status: str = "open"
    attributes: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TaskRecord:
    task_id: str
    title: str
    description: str = ""
    status: str = "open"
    attributes: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class KnowledgeRecord:
    knowledge_id: str
    title: str
    body: str
    source: str = ""


@dataclass(frozen=True)
class KnowledgeProposal:
    title: str
    body: str
    proposed_by: str
    target: str = ""


@dataclass(frozen=True)
class KnowledgeProposalRecord:
    proposal_id: str
    proposal: KnowledgeProposal
    status: str = "proposed"


@dataclass(frozen=True)
class WorkspaceRequest:
    workspace_id: str
    branch: str
    base_ref: str = "HEAD"


@dataclass(frozen=True)
class WorkspaceRecord:
    workspace_id: str
    branch: str
    path: Path
    isolated: bool = True


@dataclass(frozen=True)
class ReviewRequest:
    task_id: str
    actor_id: str
    lease_id: str = ""


@dataclass(frozen=True)
class ReviewFinding:
    finding_id: str
    severity: str
    status: str
    location: str = ""
    expected_behavior: str = ""
    evidence: str = ""


@dataclass(frozen=True)
class ReviewLease:
    lease_id: str
    actor_id: str
    expires_at: str
    ledger_revision: int


@dataclass(frozen=True)
class ReviewStatus:
    task_id: str
    state: str
    total_findings: int = 0
    unresolved_findings: tuple[str, ...] = ()
    findings: tuple[ReviewFinding, ...] = ()
    lease: ReviewLease | None = None
    ledger_revision: int = 0


@dataclass(frozen=True)
class ReviewOutcomeRequest:
    task_id: str
    actor_id: str
    decision: str
    findings: tuple[ReviewFinding, ...] = ()
    lease_id: str = ""
    acceptance_identity: AcceptanceIdentity | None = None
    expected_ledger_revision: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "findings", tuple(self.findings))


class EvidenceCategory(str, Enum):
    TESTS = "tests"
    REVIEWS = "reviews"
    REPOSITORY = "repository"


_EVIDENCE_SUCCESS_OUTCOMES = {
    EvidenceCategory.TESTS: frozenset({"passed"}),
    EvidenceCategory.REVIEWS: frozenset({"approved"}),
    EvidenceCategory.REPOSITORY: frozenset({"recorded"}),
}


def evidence_outcome_succeeds(category: EvidenceCategory, outcome: str) -> bool:
    """Return true only for an explicitly accepted outcome for this category."""
    return outcome.strip().casefold() in _EVIDENCE_SUCCESS_OUTCOMES.get(category, frozenset())


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str
    task_id: str
    category: EvidenceCategory
    outcome: str
    reference: str
    details: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EvidenceQuery:
    task_id: str | None = None
    category: EvidenceCategory | None = None


@dataclass(frozen=True)
class EvidenceCompleteness:
    task_id: str
    complete: bool
    missing_categories: tuple[str, ...]
    evidence: tuple[EvidenceRecord, ...]


@dataclass(frozen=True)
class NotificationRequest:
    event: str
    message: str
    wait_for_reply: bool = False
    timeout_seconds: int = 600
    session_id: str = ""


@dataclass(frozen=True)
class NotificationReceipt:
    event: str
    delivered: bool
    reply: str = ""


class ProviderBase:
    """Shared health and in-process replay handling; adapters own external calls."""

    provider_name = "provider"
    provider_type = "unknown"
    capabilities: frozenset[str] = frozenset()

    def __init__(self, *, available: bool = True, health_detail: str = "") -> None:
        self._available = available
        self._health_detail = health_detail
        self._idempotency: dict[tuple[str, str, str], ProviderResult[Any]] = {}

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name=self.provider_name,
            provider_type=self.provider_type,
            capabilities=self.capabilities,
            health=ProviderHealth.AVAILABLE if self._available else ProviderHealth.UNAVAILABLE,
            detail=self._health_detail,
        )

    def set_available(self, available: bool, detail: str = "") -> None:
        self._available = available
        self._health_detail = detail

    def _guard(self) -> ProviderResult[Any] | None:
        if self._available:
            return None
        return ProviderResult.unavailable(self._health_detail or f"{self.provider_name} is unavailable")

    @staticmethod
    def _fingerprint(request: object) -> str:
        def normalize(value: object) -> object:
            if is_dataclass(value) and not isinstance(value, type):
                return normalize(asdict(value))
            if isinstance(value, Enum):
                return value.value
            if isinstance(value, Mapping):
                return {
                    str(key): normalize(item)
                    for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
                }
            if isinstance(value, (list, tuple)):
                return [normalize(item) for item in value]
            if isinstance(value, (set, frozenset)):
                return sorted((normalize(item) for item in value), key=repr)
            if isinstance(value, Path):
                return str(value)
            if value is None or isinstance(value, (str, int, float, bool)):
                return value
            return repr(value)

        payload = json.dumps(normalize(request), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _cache_key(self, operation: str, key: str, request: object) -> tuple[str, str, str]:
        return operation, key, self._fingerprint(request)

    def _replay(
        self, operation: str, key: str, request: object
    ) -> ProviderResult[Any] | None:
        previous = self._idempotency.get(self._cache_key(operation, key, request))
        return replace(previous, idempotent=True) if previous is not None else None

    def _remember(
        self,
        operation: str,
        key: str,
        request: object,
        result: ProviderResult[T],
    ) -> ProviderResult[T]:
        if result.status is OperationStatus.SUCCESS:
            self._idempotency[self._cache_key(operation, key, request)] = result
        return result


@runtime_checkable
class TaskTrackingProvider(Protocol):
    metadata: ProviderMetadata

    def create_task(self, request: TaskCreateRequest, *, idempotency_key: str) -> ProviderResult[TaskRecord]: ...
    def read_task(self, task_id: str) -> ProviderResult[TaskRecord]: ...
    def update_task(self, task_id: str, changes: Mapping[str, Any], *, idempotency_key: str) -> ProviderResult[TaskRecord]: ...


@runtime_checkable
class KnowledgeProvider(Protocol):
    metadata: ProviderMetadata

    def search(self, query: str) -> ProviderResult[tuple[KnowledgeRecord, ...]]: ...
    def propose(self, proposal: KnowledgeProposal, *, idempotency_key: str) -> ProviderResult[KnowledgeProposalRecord]: ...


@runtime_checkable
class WorkspaceProvider(Protocol):
    metadata: ProviderMetadata

    def create(self, request: WorkspaceRequest, *, idempotency_key: str) -> ProviderResult[WorkspaceRecord]: ...
    def isolate(self, workspace_id: str) -> ProviderResult[WorkspaceRecord]: ...
    def cleanup(self, workspace_id: str, *, idempotency_key: str) -> ProviderResult[bool]: ...


@runtime_checkable
class ReviewProvider(Protocol):
    metadata: ProviderMetadata

    def request(self, request: ReviewRequest, *, idempotency_key: str) -> ProviderResult[ReviewStatus]: ...
    def record_outcome(
        self, request: ReviewOutcomeRequest, *, idempotency_key: str
    ) -> ProviderResult[ReviewStatus]: ...
    def begin_revision(
        self,
        task_id: str,
        *,
        actor_id: str,
        lease_id: str,
        idempotency_key: str,
    ) -> ProviderResult[ReviewStatus]: ...
    def complete_revision(
        self,
        task_id: str,
        finding_ids: tuple[str, ...],
        *,
        actor_id: str,
        lease_id: str,
        idempotency_key: str,
    ) -> ProviderResult[ReviewStatus]: ...
    def complete_revision(
        self,
        task_id: str,
        finding_ids: tuple[str, ...],
        *,
        actor_id: str,
        lease_id: str,
        idempotency_key: str,
    ) -> ProviderResult[ReviewStatus]: ...
    def status(self, task_id: str) -> ProviderResult[ReviewStatus]: ...


@runtime_checkable
class EvidenceProvider(Protocol):
    metadata: ProviderMetadata

    def record(self, evidence: EvidenceRecord, *, idempotency_key: str) -> ProviderResult[EvidenceRecord]: ...
    def query(self, query: EvidenceQuery) -> ProviderResult[tuple[EvidenceRecord, ...]]: ...
    def completeness(self, task_id: str) -> ProviderResult[EvidenceCompleteness]: ...


@runtime_checkable
class NotificationProvider(Protocol):
    metadata: ProviderMetadata

    def notify(self, request: NotificationRequest, *, idempotency_key: str) -> ProviderResult[NotificationReceipt]: ...
