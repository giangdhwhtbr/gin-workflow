"""Provider-neutral lifecycle contracts and normalized operation results."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass, replace
from datetime import datetime
from enum import Enum
import hashlib
import json
from pathlib import Path
import re
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
    allowed = {
        "title",
        "description",
        "status",
        "attributes",
        "notes",
        "acceptance_criteria",
    } | SUPPORTED_TASK_ATTRIBUTES
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
    for field_name in ("notes", "acceptance_criteria"):
        if field_name in normalized:
            value = normalized[field_name]
            if not isinstance(value, (list, tuple)) or any(
                not isinstance(item, str) or not item.strip() for item in value
            ):
                return None, f"{field_name} must be a collection of non-empty strings"
            normalized[field_name] = tuple(value)
    return normalized, None


def _task_strings(value: object, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ValueError(f"{field_name} must be a collection of non-empty strings")
    return tuple(value)


@dataclass(frozen=True)
class TaskCreateRequest:
    title: str
    description: str = ""
    status: str = "open"
    attributes: Mapping[str, Any] = field(default_factory=dict)
    notes: tuple[str, ...] = ()
    acceptance_criteria: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "notes", _task_strings(self.notes, "notes"))
        object.__setattr__(
            self,
            "acceptance_criteria",
            _task_strings(self.acceptance_criteria, "acceptance_criteria"),
        )


@dataclass(frozen=True)
class TaskRecord:
    task_id: str
    title: str
    description: str = ""
    status: str = "open"
    attributes: Mapping[str, Any] = field(default_factory=dict)
    notes: tuple[str, ...] = ()
    acceptance_criteria: tuple[str, ...] = ()
    acceptance_evidence: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    closure_reason: str = ""

    def __post_init__(self) -> None:
        for field_name in (
            "notes",
            "acceptance_criteria",
            "acceptance_evidence",
            "dependencies",
        ):
            object.__setattr__(self, field_name, _task_strings(getattr(self, field_name), field_name))


@dataclass(frozen=True)
class TaskClosureRequest:
    task_id: str
    closure_reason: str
    acceptance_evidence: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "acceptance_evidence",
            _task_strings(self.acceptance_evidence, "acceptance_evidence"),
        )


@dataclass(frozen=True)
class TaskDependencyRecord:
    task_id: str
    depends_on_task_id: str
    dependency_type: str = "blocks"


@dataclass(frozen=True)
class TaskReadiness:
    task_id: str
    ready: bool
    blockers: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "blockers", _task_strings(self.blockers, "blockers"))


@dataclass(frozen=True)
class TaskPreflight:
    backend: str
    version: str
    capabilities: frozenset[str]
    healthy: bool
    drift: str = ""


@dataclass(frozen=True)
class TaskSyncRequest:
    mode: str
    dry_run: bool = True
    workflow_id: str = ""


@dataclass(frozen=True)
class TaskSyncResult:
    backend: str
    mode: str
    dry_run: bool
    command: tuple[str, ...]
    affected: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "command", tuple(self.command))
        object.__setattr__(self, "affected", _task_strings(self.affected, "affected"))


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
class ReviewInitRequest:
    """Declare the reviewed source before a review can be requested.

    ``ReviewRequest`` carries only review identity, so it cannot describe which
    repository, ref, or scope is under review. Bootstrapping the ledger needs
    that declaration, which is why initialization is a distinct capability
    rather than an implicit side effect of ``request``.
    """

    task_id: str
    actor_id: str
    repository_id: str
    repository_path: str
    base_ref: str
    review_ref: str
    scope: Mapping[str, Any]
    role: str = "primary"
    actor_role: str = "worker"
    workflow_id: str = ""
    attempt_id: str = ""


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
    acceptance_identity: AcceptanceIdentity | None = None
    recorded_at: str = ""


@dataclass(frozen=True)
class EvidenceQuery:
    task_id: str | None = None
    category: EvidenceCategory | None = None
    acceptance_identity: AcceptanceIdentity | None = None


@dataclass(frozen=True)
class EvidenceCompleteness:
    task_id: str
    complete: bool
    missing_categories: tuple[str, ...]
    evidence: tuple[EvidenceRecord, ...]
    diagnostics: tuple[str, ...] = ()


@runtime_checkable
class EvidenceAuthority(Protocol):
    """Resolve canonical evidence from trusted worker, Git, review, and event stores."""

    def resolve(
        self,
        category: EvidenceCategory,
        reference: str,
    ) -> Mapping[str, Any] | None: ...


EVIDENCE_CATEGORY_ORDER = (
    EvidenceCategory.TESTS,
    EvidenceCategory.REPOSITORY,
    EvidenceCategory.REVIEWS,
)

_EVIDENCE_SCHEMA_VERSION = "2.3"
_PORTABLE_EVIDENCE_ID = re.compile(r"^[A-Za-z0-9._-]+$")
_TEST_PROVENANCE_FIELDS = frozenset(
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


def parse_timestamp(value: object) -> datetime:
    """Parse an ISO-8601 instant that carries an explicit UTC offset."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("timestamp must be a non-empty ISO-8601 string")
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = f"{text[:-1]}+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a UTC offset")
    return parsed


def evidence_acceptance_identity(evidence: EvidenceRecord) -> AcceptanceIdentity | None:
    """Return direct identity, or None for a queryable legacy record."""
    return evidence.acceptance_identity


def evidence_recorded_at(evidence: EvidenceRecord) -> datetime | None:
    return None if not evidence.recorded_at else parse_timestamp(evidence.recorded_at)


def _utc_timestamp(value: object, field_name: str) -> tuple[datetime | None, str | None]:
    try:
        parsed = parse_timestamp(value)
    except (TypeError, ValueError) as error:
        return None, f"invalid {field_name}: {error}"
    if parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
        return None, f"{field_name} must be UTC"
    return parsed, None


def _validate_test_evidence(evidence: EvidenceRecord) -> str | None:
    details = evidence.details
    required = {"schema_version", "worker_id", "worker_result_schema_version", "tests"}
    if set(details) != required:
        return "tests category provenance requires schema_version, worker_id, worker_result_schema_version, and tests"
    if details["schema_version"] != _EVIDENCE_SCHEMA_VERSION:
        return "tests category provenance schema_version must be 2.3"
    if details["worker_result_schema_version"] != _EVIDENCE_SCHEMA_VERSION:
        return "tests worker result schema_version must be 2.3"
    worker_id = details["worker_id"]
    if not isinstance(worker_id, str) or not _PORTABLE_EVIDENCE_ID.fullmatch(worker_id):
        return "tests worker_id must be a portable identifier"
    if evidence.reference != worker_id:
        return "tests evidence reference must match worker_id"
    tests = details["tests"]
    if not isinstance(tests, (list, tuple)) or not tests:
        return "tests category provenance requires at least one test result"
    assert evidence.acceptance_identity is not None
    repositories = {
        repository.repository_id: repository
        for repository in evidence.acceptance_identity.repositories
    }
    recorded_at = evidence_recorded_at(evidence)
    for test in tests:
        if not isinstance(test, Mapping) or set(test) != _TEST_PROVENANCE_FIELDS:
            return "tests category provenance contains malformed test fields"
        argv = test["argv"]
        if (
            not isinstance(argv, (list, tuple))
            or not argv
            or any(not isinstance(part, str) or not part for part in argv)
        ):
            return "test argv must be a non-empty list of strings"
        exit_code = test["exit_code"]
        if isinstance(exit_code, bool) or not isinstance(exit_code, int):
            return "test exit_code must be an integer"
        if exit_code != 0:
            return "successful tests evidence requires every test to exit successfully"
        started_at, error = _utc_timestamp(test["started_at"], "test started_at")
        if error:
            return error
        finished_at, error = _utc_timestamp(test["finished_at"], "test finished_at")
        if error:
            return error
        assert started_at is not None and finished_at is not None
        if finished_at < started_at:
            return "test finished_at precedes started_at"
        if recorded_at is not None and finished_at > recorded_at:
            return "test result finishes after evidence was recorded"
        workspace_id = test["workspace_id"]
        if not isinstance(workspace_id, str) or not _PORTABLE_EVIDENCE_ID.fullmatch(workspace_id):
            return "test workspace_id must be a portable identifier"
        if test["attempt_id"] != evidence.acceptance_identity.attempt_id:
            return "test attempt does not match evidence acceptance identity"
        repository = repositories.get(test["repository_id"])
        if repository is None:
            return "test repository does not match evidence acceptance identity"
        if test["source_tree_hash"] != repository.source_tree_hash:
            return "test source tree does not match evidence acceptance identity"
    return None


def _validate_repository_evidence(evidence: EvidenceRecord) -> str | None:
    details = evidence.details
    required = {"schema_version", "checkpoint_event_id", "repositories"}
    if set(details) != required:
        return "repository category provenance requires schema_version, checkpoint_event_id, and repositories"
    if details["schema_version"] != _EVIDENCE_SCHEMA_VERSION:
        return "repository category provenance schema_version must be 2.3"
    event_id = details["checkpoint_event_id"]
    if not isinstance(event_id, str) or not _PORTABLE_EVIDENCE_ID.fullmatch(event_id):
        return "repository checkpoint_event_id must be a portable identifier"
    if evidence.reference != event_id:
        return "repository evidence reference must match checkpoint_event_id"
    assert evidence.acceptance_identity is not None
    if details["repositories"] != evidence.acceptance_identity.to_dict()["repositories"]:
        return "repository checkpoint, ref, scope, or tree does not match acceptance identity"
    return None


def _validate_review_evidence(evidence: EvidenceRecord) -> str | None:
    details = evidence.details
    required = {
        "schema_version",
        "review_event_id",
        "ledger_revision",
        "approval_recorded_at",
        "verification_event_id",
        "verification_recorded_at",
    }
    if set(details) != required:
        return "reviews category provenance requires terminal approval and verification events"
    if details["schema_version"] != _EVIDENCE_SCHEMA_VERSION:
        return "reviews category provenance schema_version must be 2.3"
    review_event_id = details["review_event_id"]
    verification_event_id = details["verification_event_id"]
    if (
        not isinstance(review_event_id, str)
        or not _PORTABLE_EVIDENCE_ID.fullmatch(review_event_id)
        or not isinstance(verification_event_id, str)
        or not _PORTABLE_EVIDENCE_ID.fullmatch(verification_event_id)
        or review_event_id == verification_event_id
    ):
        return "review and verification event ids must be distinct portable identifiers"
    if evidence.reference != review_event_id:
        return "reviews evidence reference must match terminal review_event_id"
    revision = details["ledger_revision"]
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        return "reviews ledger_revision must be a positive integer"
    approval_at, error = _utc_timestamp(details["approval_recorded_at"], "approval_recorded_at")
    if error:
        return error
    verification_at, error = _utc_timestamp(
        details["verification_recorded_at"], "verification_recorded_at"
    )
    if error:
        return error
    assert approval_at is not None and verification_at is not None
    if verification_at <= approval_at:
        return "verification must occur after terminal approval"
    recorded_at = evidence_recorded_at(evidence)
    if recorded_at is not None and verification_at != recorded_at:
        return "reviews evidence recorded_at must identify the verification event"
    return None


def _validate_category_provenance(evidence: EvidenceRecord) -> str | None:
    validators = {
        EvidenceCategory.TESTS: _validate_test_evidence,
        EvidenceCategory.REPOSITORY: _validate_repository_evidence,
        EvidenceCategory.REVIEWS: _validate_review_evidence,
    }
    return validators[evidence.category](evidence)


def evidence_authority_payload(evidence: EvidenceRecord) -> dict[str, Any]:
    """Canonical payload an authority must derive independently of the evidence index."""
    return {
        "task_id": evidence.task_id,
        "category": evidence.category.value,
        "outcome": evidence.outcome,
        "reference": evidence.reference,
        "details": dict(evidence.details),
        "acceptance_identity": (
            None
            if evidence.acceptance_identity is None
            else evidence.acceptance_identity.to_dict()
        ),
        "recorded_at": evidence.recorded_at,
    }


def validate_authoritative_evidence(
    evidence: EvidenceRecord,
    authority: EvidenceAuthority | None,
) -> str | None:
    """Require successful identity-bound evidence to match a trusted source snapshot."""
    if (
        evidence.acceptance_identity is None
        or not evidence_outcome_succeeds(evidence.category, evidence.outcome)
    ):
        return None
    if authority is None or not isinstance(authority, EvidenceAuthority):
        return "authoritative evidence resolver is required"
    try:
        resolved = authority.resolve(evidence.category, evidence.reference)
    except Exception as error:
        return f"authoritative evidence resolution failed: {error}"
    if resolved is None:
        return "evidence reference is not resolvable by the authoritative source"
    if not isinstance(resolved, Mapping):
        return "authoritative evidence resolver returned an invalid snapshot"
    if dict(resolved) != evidence_authority_payload(evidence):
        return "evidence does not match authoritative worker, repository, review, or verification provenance"
    return None


def validate_evidence_details(evidence: EvidenceRecord) -> str | None:
    """Reject malformed provenance while leaving legacy details readable."""
    if not isinstance(evidence.details, Mapping):
        return "evidence details must be a mapping"
    if evidence.acceptance_identity is not None and not isinstance(
        evidence.acceptance_identity, AcceptanceIdentity
    ):
        return "evidence acceptance_identity must be an AcceptanceIdentity"
    if evidence.acceptance_identity is None:
        if evidence.recorded_at:
            return "legacy evidence cannot declare recorded_at without acceptance_identity"
        return None
    if evidence.acceptance_identity.task_id != evidence.task_id:
        return "evidence acceptance identity task does not match record"
    if not evidence.recorded_at:
        return "identity-bound evidence requires recorded_at"
    try:
        recorded_at = evidence_recorded_at(evidence)
    except (TypeError, ValueError) as error:
        return f"invalid evidence provenance: {error}"
    if recorded_at is None or recorded_at.utcoffset() is None:
        return "identity-bound evidence requires a UTC recorded_at"
    if recorded_at.utcoffset().total_seconds() != 0:
        return "identity-bound evidence recorded_at must be UTC"
    if evidence_outcome_succeeds(evidence.category, evidence.outcome):
        return _validate_category_provenance(evidence)
    return None


def _identity_key(identity: AcceptanceIdentity | None) -> str:
    if identity is None:
        return ""
    return json.dumps(identity.to_dict(), sort_keys=True, separators=(",", ":"))


def _ordered(evidence: list[EvidenceRecord], *, require_timestamps: bool) -> bool:
    stamps: dict[EvidenceCategory, list[datetime]] = {}
    for record in evidence:
        recorded_at = evidence_recorded_at(record)
        if recorded_at is None:
            if require_timestamps:
                return False
            continue
        stamps.setdefault(record.category, []).append(recorded_at)
    latest: datetime | None = None
    for category in EVIDENCE_CATEGORY_ORDER:
        current = stamps.get(category)
        if not current:
            continue
        if latest is not None and min(current) < latest:
            return False
        latest = max(current)
    return True


def evaluate_evidence_completeness(
    task_id: str,
    evidence: tuple[EvidenceRecord, ...],
    *,
    acceptance_identity: AcceptanceIdentity | None = None,
    authority: EvidenceAuthority | None = None,
) -> EvidenceCompleteness:
    """Complete only for the explicitly selected, successful, ordered identity set."""
    all_categories = tuple(category.value for category in EVIDENCE_CATEGORY_ORDER)
    if acceptance_identity is None:
        return EvidenceCompleteness(
            task_id,
            False,
            all_categories,
            (),
            ("acceptance identity is required; legacy evidence is insufficient",),
        )
    if acceptance_identity.task_id != task_id:
        return EvidenceCompleteness(
            task_id,
            False,
            all_categories,
            (),
            ("acceptance identity task does not match completeness task",),
        )

    selected: list[EvidenceRecord] = []
    mismatched_success = False
    authority_failures: list[str] = []
    for record in evidence:
        if not evidence_outcome_succeeds(record.category, record.outcome):
            continue
        identity = evidence_acceptance_identity(record)
        if identity is None:
            continue
        try:
            acceptance_identity.require_exact_match(identity)
        except (TypeError, ValueError):
            mismatched_success = True
            continue
        if error := validate_evidence_details(record):
            authority_failures.append(error)
            continue
        if error := validate_authoritative_evidence(record, authority):
            authority_failures.append(error)
            continue
        selected.append(record)

    present = {record.category.value for record in selected}
    missing = tuple(category for category in all_categories if category not in present)
    diagnostics: list[str] = []
    if mismatched_success:
        diagnostics.append("successful evidence exists for another acceptance identity")
    diagnostics.extend(authority_failures)
    if missing:
        return EvidenceCompleteness(
            task_id, False, missing, tuple(selected), tuple(diagnostics)
        )
    if not _ordered(selected, require_timestamps=True):
        diagnostics.append("evidence timestamps are out of order")
        return EvidenceCompleteness(
            task_id, False, (), tuple(selected), tuple(diagnostics)
        )
    repository_times = [
        evidence_recorded_at(record)
        for record in selected
        if record.category is EvidenceCategory.REPOSITORY
    ]
    approval_times = [
        parse_timestamp(record.details["approval_recorded_at"])
        for record in selected
        if record.category is EvidenceCategory.REVIEWS
    ]
    if repository_times and approval_times and min(approval_times) < max(repository_times):
        diagnostics.append("terminal approval predates repository checkpoint evidence")
        return EvidenceCompleteness(
            task_id, False, (), tuple(selected), tuple(diagnostics)
        )
    return EvidenceCompleteness(task_id, True, (), tuple(selected), tuple(diagnostics))


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
    def close_task(self, request: TaskClosureRequest, *, idempotency_key: str) -> ProviderResult[TaskRecord]: ...
    def add_dependency(self, dependency: TaskDependencyRecord, *, idempotency_key: str) -> ProviderResult[TaskDependencyRecord]: ...
    def readiness(self, task_id: str) -> ProviderResult[TaskReadiness]: ...
    def preflight(self) -> ProviderResult[TaskPreflight]: ...
    def sync(self, request: TaskSyncRequest, *, idempotency_key: str, **approval: Any) -> ProviderResult[TaskSyncResult]: ...


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

    def initialize(
        self, request: ReviewInitRequest, *, idempotency_key: str
    ) -> ProviderResult[ReviewStatus]: ...
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
    def completeness(
        self,
        task_id: str,
        acceptance_identity: AcceptanceIdentity | None = None,
    ) -> ProviderResult[EvidenceCompleteness]: ...


@runtime_checkable
class NotificationProvider(Protocol):
    metadata: ProviderMetadata

    def notify(self, request: NotificationRequest, *, idempotency_key: str) -> ProviderResult[NotificationReceipt]: ...
