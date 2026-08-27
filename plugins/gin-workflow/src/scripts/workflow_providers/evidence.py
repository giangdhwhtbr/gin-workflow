"""Filesystem evidence index adapter."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import contextmanager
from dataclasses import asdict
import json
import fcntl
import os
from pathlib import Path
import threading
import tempfile
from typing import Any

from .contracts import (
    EvidenceCategory,
    EvidenceAuthority,
    EvidenceCompleteness,
    EvidenceQuery,
    EvidenceRecord,
    evaluate_evidence_completeness,
    OperationStatus,
    ProviderBase,
    ProviderResult,
    validate_evidence_details,
    validate_authoritative_evidence,
)
from workflow_core.events import WorkflowEvent, WorkflowEventStore
from workflow_core.models import thaw
from workflow_core.identity import AcceptanceIdentity


EvidenceSourceResolver = Callable[[str], Mapping[str, Any] | None]


class CompositeEvidenceAuthority:
    """Derive evidence from independent worker, Git, review, and verification stores."""

    def __init__(
        self,
        *,
        worker_resolver: EvidenceSourceResolver,
        checkpoint_resolver: EvidenceSourceResolver,
        review_resolver: EvidenceSourceResolver,
        verification_resolver: EvidenceSourceResolver,
    ) -> None:
        if not all(
            callable(resolver)
            for resolver in (
                worker_resolver,
                checkpoint_resolver,
                review_resolver,
                verification_resolver,
            )
        ):
            raise TypeError("composite evidence authority requires four callable resolvers")
        self.worker_resolver = worker_resolver
        self.checkpoint_resolver = checkpoint_resolver
        self.review_resolver = review_resolver
        self.verification_resolver = verification_resolver

    @staticmethod
    def _required(source: Mapping[str, Any], fields: set[str], label: str) -> None:
        missing = sorted(fields.difference(source))
        if missing:
            raise ValueError(f"{label} source is missing: {', '.join(missing)}")

    @staticmethod
    def _identity(source: Mapping[str, Any], label: str) -> AcceptanceIdentity:
        try:
            return AcceptanceIdentity.from_mapping(source["acceptance_identity"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"{label} source has invalid acceptance identity") from error

    @staticmethod
    def _payload(
        *,
        task_id: object,
        category: EvidenceCategory,
        outcome: str,
        reference: str,
        details: Mapping[str, Any],
        identity: AcceptanceIdentity,
        recorded_at: object,
    ) -> dict[str, Any]:
        return {
            "task_id": str(task_id),
            "category": category.value,
            "outcome": outcome,
            "reference": reference,
            "details": dict(details),
            "acceptance_identity": identity.to_dict(),
            "recorded_at": str(recorded_at),
        }

    def _worker(self, reference: str) -> Mapping[str, Any] | None:
        source = self.worker_resolver(reference)
        if source is None:
            return None
        self._required(
            source,
            {
                "task_id",
                "worker_id",
                "status",
                "schema_version",
                "request_acceptance_identity",
                "result_acceptance_identity",
                "request_workspace_id",
                "tests",
                "recorded_at",
            },
            "worker",
        )
        if source["status"] != "completed" or source["schema_version"] != "2.3":
            raise ValueError("worker source is not a completed schema-2.3 result")
        if source["worker_id"] != reference:
            raise ValueError("worker source receipt does not match reference")
        tests = source["tests"]
        if not isinstance(tests, (list, tuple)):
            raise ValueError("worker source tests must be a list")
        workspace_id = source["request_workspace_id"]
        if any(
            not isinstance(test, Mapping) or test.get("workspace_id") != workspace_id
            for test in tests
        ):
            raise ValueError("worker tests do not match the authoritative request workspace")
        try:
            request_identity = AcceptanceIdentity.from_mapping(
                source["request_acceptance_identity"]
            )
            result_identity = AcceptanceIdentity.from_mapping(
                source["result_acceptance_identity"]
            )
            request_identity.require_exact_match(result_identity)
        except (TypeError, ValueError) as error:
            raise ValueError("worker request and result identities do not match") from error
        return self._payload(
            task_id=source["task_id"],
            category=EvidenceCategory.TESTS,
            outcome="passed",
            reference=reference,
            details={
                "schema_version": "2.3",
                "worker_id": reference,
                "worker_result_schema_version": "2.3",
                "tests": [dict(test) for test in tests],
            },
            identity=request_identity,
            recorded_at=source["recorded_at"],
        )

    def _checkpoint(self, reference: str) -> Mapping[str, Any] | None:
        source = self.checkpoint_resolver(reference)
        if source is None:
            return None
        self._required(
            source,
            {
                "task_id",
                "checkpoint_event_id",
                "acceptance_identity",
                "repositories",
                "recorded_at",
            },
            "checkpoint",
        )
        if source["checkpoint_event_id"] != reference:
            raise ValueError("checkpoint source event does not match reference")
        identity = self._identity(source, "checkpoint")
        if source["repositories"] != identity.to_dict()["repositories"]:
            raise ValueError("checkpoint source does not match resolved Git repository state")
        return self._payload(
            task_id=source["task_id"],
            category=EvidenceCategory.REPOSITORY,
            outcome="recorded",
            reference=reference,
            details={
                "schema_version": "2.3",
                "checkpoint_event_id": reference,
                "repositories": identity.to_dict()["repositories"],
            },
            identity=identity,
            recorded_at=source["recorded_at"],
        )

    def _review(self, reference: str) -> Mapping[str, Any] | None:
        review = self.review_resolver(reference)
        if review is None:
            return None
        self._required(
            review,
            {
                "task_id",
                "review_event_id",
                "ledger_revision",
                "acceptance_identity",
                "status",
                "terminal",
                "recorded_at",
                "verification_event_id",
            },
            "review",
        )
        if (
            review["review_event_id"] != reference
            or review["status"] != "approved"
            or review["terminal"] is not True
        ):
            raise ValueError("review source is not the referenced terminal approval")
        verification_reference = str(review["verification_event_id"])
        verification = self.verification_resolver(verification_reference)
        if verification is None:
            return None
        self._required(
            verification,
            {
                "task_id",
                "verification_event_id",
                "review_event_id",
                "acceptance_identity",
                "status",
                "recorded_at",
            },
            "verification",
        )
        review_identity = self._identity(review, "review")
        verification_identity = self._identity(verification, "verification")
        review_identity.require_exact_match(verification_identity)
        if (
            verification["verification_event_id"] != verification_reference
            or verification["review_event_id"] != reference
            or verification["task_id"] != review["task_id"]
            or verification["status"] != "passed"
        ):
            raise ValueError("verification source does not verify the terminal review")
        return self._payload(
            task_id=review["task_id"],
            category=EvidenceCategory.REVIEWS,
            outcome="approved",
            reference=reference,
            details={
                "schema_version": "2.3",
                "review_event_id": reference,
                "ledger_revision": review["ledger_revision"],
                "approval_recorded_at": review["recorded_at"],
                "verification_event_id": verification_reference,
                "verification_recorded_at": verification["recorded_at"],
            },
            identity=review_identity,
            recorded_at=verification["recorded_at"],
        )

    def resolve(
        self,
        category: EvidenceCategory,
        reference: str,
    ) -> Mapping[str, Any] | None:
        if category is EvidenceCategory.TESTS:
            return self._worker(reference)
        if category is EvidenceCategory.REPOSITORY:
            return self._checkpoint(reference)
        if category is EvidenceCategory.REVIEWS:
            return self._review(reference)
        return None


def record_verification(
    event_store: WorkflowEventStore,
    *,
    workflow_id: str,
    task_id: str,
    verification_event_id: str,
    review_event_id: str,
    acceptance_identity: AcceptanceIdentity,
    status: str,
) -> bool:
    """Durably append a verification outcome for later CompositeEvidenceAuthority resolution."""
    for field_name, value in (
        ("workflow_id", workflow_id),
        ("task_id", task_id),
        ("verification_event_id", verification_event_id),
        ("review_event_id", review_event_id),
        ("status", status),
    ):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} is required")
    if not isinstance(acceptance_identity, AcceptanceIdentity):
        raise TypeError("acceptance_identity must be an AcceptanceIdentity")
    event = WorkflowEvent.create(
        event_type="verification.recorded",
        workflow_id=workflow_id,
        task_id=task_id,
        payload={
            "verification_event_id": verification_event_id,
            "review_event_id": review_event_id,
            "acceptance_identity": acceptance_identity.to_dict(),
            "status": status,
        },
        idempotency_key=f"{workflow_id}:{task_id}:verification.recorded:{verification_event_id}",
    )
    return event_store.append(event)


def find_verification(
    event_store: WorkflowEventStore,
    verification_event_id: str,
) -> Mapping[str, Any] | None:
    """Resolve a previously recorded verification event by its verification_event_id."""
    if not isinstance(verification_event_id, str) or not verification_event_id.strip():
        raise ValueError("verification_event_id is required")
    for event in event_store.read_all():
        if (
            event.event_type == "verification.recorded"
            and event.payload.get("verification_event_id") == verification_event_id
        ):
            return {
                "task_id": event.task_id,
                "verification_event_id": event.payload["verification_event_id"],
                "review_event_id": event.payload["review_event_id"],
                "acceptance_identity": thaw(event.payload["acceptance_identity"]),
                "status": event.payload["status"],
                "recorded_at": event.timestamp,
            }
    return None


class FileEvidenceProvider(ProviderBase):
    provider_name = "filesystem"
    provider_type = "evidence"
    capabilities = frozenset({"evidence.record", "evidence.query", "evidence.completeness"})

    def __init__(
        self,
        index_path: Path,
        *,
        authority: EvidenceAuthority | None = None,
    ) -> None:
        super().__init__()
        candidate = Path(index_path)
        self.index_path = candidate if candidate.suffix else candidate / "index.json"
        self.authority = authority
        self._lock = threading.RLock()

    @contextmanager
    def _file_lock(self, *, exclusive: bool):
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self.index_path.with_name(f".{self.index_path.name}.lock")
        with lock_path.open("a+b") as handle:
            operation = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
            fcntl.flock(handle.fileno(), operation)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def _load(self) -> list[EvidenceRecord]:
        if not self.index_path.exists():
            return []
        data = json.loads(self.index_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("records"), list):
            raise ValueError("evidence index must contain a records list")
        records: list[EvidenceRecord] = []
        for raw in data["records"]:
            if not isinstance(raw, dict):
                raise ValueError("evidence records must be objects")
            record = EvidenceRecord(
                    evidence_id=str(raw["evidence_id"]),
                    task_id=str(raw["task_id"]),
                    category=EvidenceCategory(str(raw["category"])),
                    outcome=str(raw["outcome"]),
                    reference=str(raw["reference"]),
                    details=raw.get("details", {}),
                    acceptance_identity=(
                        None
                        if raw.get("acceptance_identity") is None
                        else AcceptanceIdentity.from_mapping(raw["acceptance_identity"])
                    ),
                    recorded_at=str(raw.get("recorded_at", "")),
                )
            if error := validate_evidence_details(record):
                raise ValueError(f"persisted evidence is invalid: {error}")
            if error := validate_authoritative_evidence(record, self.authority):
                raise ValueError(f"persisted evidence is not authoritative: {error}")
            records.append(record)
        return records

    def _write(self, records: list[EvidenceRecord]) -> None:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        serialized = []
        for record in records:
            raw = {**asdict(record), "category": record.category.value}
            if record.acceptance_identity is None:
                raw.pop("acceptance_identity", None)
                raw.pop("recorded_at", None)
            serialized.append(raw)
        payload = {
            "schema_version": (
                "2.3"
                if any(record.acceptance_identity is not None for record in records)
                else "1.0"
            ),
            "records": serialized,
        }
        descriptor, temporary_name = tempfile.mkstemp(
            dir=self.index_path.parent,
            prefix=f".{self.index_path.name}.",
            suffix=".tmp",
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.index_path)
        finally:
            if temporary.exists():
                temporary.unlink()

    def _validate(self, evidence: EvidenceRecord, idempotency_key: str) -> str | None:
        if not evidence.evidence_id.strip():
            return "evidence_id is required"
        if not evidence.task_id.strip():
            return "task_id is required"
        if not evidence.outcome.strip() or not evidence.reference.strip():
            return "outcome and reference are required"
        if not idempotency_key:
            return "idempotency_key is required"
        if error := validate_evidence_details(evidence):
            return error
        return validate_authoritative_evidence(evidence, self.authority)

    def record(self, evidence: EvidenceRecord, *, idempotency_key: str) -> ProviderResult[EvidenceRecord]:
        if guarded := self._guard():
            return guarded
        if error := self._validate(evidence, idempotency_key):
            return ProviderResult.invalid(error)
        if replay := self._replay("record", idempotency_key, evidence):
            with self._lock, self._file_lock(exclusive=False):
                try:
                    records = self._load()
                except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
                    return ProviderResult.unavailable(f"evidence index unavailable: {error}")
            existing = next(
                (item for item in records if item.evidence_id == evidence.evidence_id),
                None,
            )
            if existing != evidence:
                return ProviderResult.invalid(
                    "idempotent evidence replay does not match the persisted record"
                )
            return replay
        with self._lock, self._file_lock(exclusive=True):
            try:
                records = self._load()
                existing = next((item for item in records if item.evidence_id == evidence.evidence_id), None)
                if existing is not None:
                    if existing == evidence:
                        return self._remember(
                            "record", idempotency_key, evidence,
                            ProviderResult.success(existing, idempotent=True),
                        )
                    return ProviderResult.invalid(
                        f"evidence_id already exists with different content: {evidence.evidence_id}"
                    )
                records.append(evidence)
                self._write(records)
            except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
                return ProviderResult.unavailable(f"evidence index unavailable: {error}")
        return self._remember("record", idempotency_key, evidence, ProviderResult.success(evidence))

    def query(self, query: EvidenceQuery) -> ProviderResult[tuple[EvidenceRecord, ...]]:
        if guarded := self._guard():
            return guarded
        with self._lock, self._file_lock(exclusive=False):
            try:
                records = self._load()
            except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
                return ProviderResult.unavailable(f"evidence index unavailable: {error}")
        found = tuple(
            item
            for item in records
            if (query.task_id is None or item.task_id == query.task_id)
            and (query.category is None or item.category is query.category)
            and (
                query.acceptance_identity is None
                or item.acceptance_identity == query.acceptance_identity
            )
        )
        return ProviderResult.success(found)

    def completeness(
        self,
        task_id: str,
        acceptance_identity: AcceptanceIdentity | None = None,
    ) -> ProviderResult[EvidenceCompleteness]:
        if not task_id.strip():
            return ProviderResult.invalid("task_id is required")
        queried = self.query(EvidenceQuery(task_id=task_id))
        if queried.status is not OperationStatus.SUCCESS:
            return ProviderResult(queried.status, message=queried.message)
        return ProviderResult.success(
            evaluate_evidence_completeness(
                task_id,
                queried.value or (),
                acceptance_identity=acceptance_identity,
                authority=self.authority,
            )
        )
