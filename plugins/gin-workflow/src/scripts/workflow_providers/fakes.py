"""Deterministic in-memory providers used by shared contract tests and harnesses."""

from __future__ import annotations

from dataclasses import replace
import hashlib
from pathlib import Path
from typing import Any, Iterable, Mapping

from .contracts import (
    EvidenceCategory,
    EvidenceCompleteness,
    EvidenceQuery,
    EvidenceRecord,
    evidence_outcome_succeeds,
    KnowledgeProposal,
    KnowledgeProposalRecord,
    KnowledgeRecord,
    NotificationReceipt,
    NotificationRequest,
    OperationStatus,
    ProviderBase,
    ProviderResult,
    ReviewRequest,
    ReviewStatus,
    TaskCreateRequest,
    TaskRecord,
    normalize_task_changes,
    validate_task_attributes,
    validate_task_status,
    WorkspaceRecord,
    WorkspaceRequest,
)


def _proposal_record(proposal: KnowledgeProposal) -> KnowledgeProposalRecord:
    digest = hashlib.sha256(
        f"{proposal.title}\0{proposal.body}\0{proposal.proposed_by}\0{proposal.target}".encode()
    ).hexdigest()[:16]
    return KnowledgeProposalRecord(f"proposal-{digest}", proposal)


class FakeTaskTrackingProvider(ProviderBase):
    provider_name = "fake"
    provider_type = "task_tracking"
    capabilities = frozenset({"task.create", "task.read", "task.update"})

    def __init__(self, *, available: bool = True) -> None:
        super().__init__(available=available)
        self.tasks: dict[str, TaskRecord] = {}

    def create_task(self, request: TaskCreateRequest, *, idempotency_key: str) -> ProviderResult[TaskRecord]:
        if guarded := self._guard():
            return guarded
        if replay := self._replay("create_task", idempotency_key, request):
            return replay
        if not request.title.strip() or not request.status.strip() or not idempotency_key:
            return ProviderResult.invalid("title, status, and idempotency_key are required")
        if error := validate_task_status(request.status):
            return ProviderResult.invalid(error)
        if error := validate_task_attributes(request.attributes):
            return ProviderResult.invalid(error)
        task_id = f"task-{len(self.tasks) + 1}"
        record = TaskRecord(task_id, request.title, request.description, request.status, request.attributes)
        self.tasks[task_id] = record
        return self._remember("create_task", idempotency_key, request, ProviderResult.success(record))

    def read_task(self, task_id: str) -> ProviderResult[TaskRecord]:
        if guarded := self._guard():
            return guarded
        if not task_id:
            return ProviderResult.invalid("task_id is required")
        record = self.tasks.get(task_id)
        return ProviderResult.success(record) if record else ProviderResult.invalid(f"unknown task: {task_id}")

    def update_task(self, task_id: str, changes: Mapping[str, Any], *, idempotency_key: str) -> ProviderResult[TaskRecord]:
        if guarded := self._guard():
            return guarded
        if replay := self._replay("update_task", idempotency_key, (task_id, changes)):
            return replay
        current = self.tasks.get(task_id)
        if current is None or not changes or not idempotency_key:
            return ProviderResult.invalid("known task_id, changes, and idempotency_key are required")
        normalized_changes, error = normalize_task_changes(changes)
        if error:
            return ProviderResult.invalid(error)
        attributes = dict(current.attributes)
        replacements = {}
        for field, value in normalized_changes.items():
            if field in {"priority", "assignee"}:
                attributes[field] = value
            else:
                replacements[field] = value
        updated = replace(current, attributes=attributes, **replacements)
        self.tasks[task_id] = updated
        return self._remember("update_task", idempotency_key, (task_id, changes), ProviderResult.success(updated))


class FakeKnowledgeProvider(ProviderBase):
    provider_name = "fake"
    provider_type = "knowledge"
    capabilities = frozenset({"knowledge.search", "knowledge.propose"})

    def __init__(self, entries: Iterable[Mapping[str, str] | KnowledgeRecord] = (), *, available: bool = True) -> None:
        super().__init__(available=available)
        self.entries = tuple(
            item if isinstance(item, KnowledgeRecord) else KnowledgeRecord(**item) for item in entries
        )
        self.proposals: list[KnowledgeProposalRecord] = []

    def search(self, query: str) -> ProviderResult[tuple[KnowledgeRecord, ...]]:
        if guarded := self._guard():
            return guarded
        if not query.strip():
            return ProviderResult.invalid("query is required")
        needle = query.casefold()
        found = tuple(item for item in self.entries if needle in f"{item.title}\n{item.body}".casefold())
        return ProviderResult.success(found)

    def propose(self, proposal: KnowledgeProposal, *, idempotency_key: str) -> ProviderResult[KnowledgeProposalRecord]:
        if guarded := self._guard():
            return guarded
        if replay := self._replay("propose", idempotency_key, proposal):
            return replay
        if not proposal.title.strip() or not proposal.body.strip() or not proposal.proposed_by.strip() or not idempotency_key:
            return ProviderResult.invalid("title, body, proposed_by, and idempotency_key are required")
        record = _proposal_record(proposal)
        self.proposals.append(record)
        return self._remember("propose", idempotency_key, proposal, ProviderResult.success(record))


class FakeWorkspaceProvider(ProviderBase):
    provider_name = "fake"
    provider_type = "workspace"
    capabilities = frozenset({"workspace.create", "workspace.isolate", "workspace.cleanup"})

    def __init__(self, root: Path | None = None, *, available: bool = True) -> None:
        super().__init__(available=available)
        self.root = Path(root or ".planning/worktrees").resolve()
        self.workspaces: dict[str, WorkspaceRecord] = {}

    def create(self, request: WorkspaceRequest, *, idempotency_key: str) -> ProviderResult[WorkspaceRecord]:
        if guarded := self._guard():
            return guarded
        if replay := self._replay("create", idempotency_key, request):
            return replay
        if not request.workspace_id or not request.branch or not idempotency_key:
            return ProviderResult.invalid("workspace_id, branch, and idempotency_key are required")
        path = self.root / request.workspace_id
        path.mkdir(parents=True, exist_ok=True)
        record = WorkspaceRecord(request.workspace_id, request.branch, path)
        self.workspaces[request.workspace_id] = record
        return self._remember("create", idempotency_key, request, ProviderResult.success(record))

    def isolate(self, workspace_id: str) -> ProviderResult[WorkspaceRecord]:
        if guarded := self._guard():
            return guarded
        record = self.workspaces.get(workspace_id)
        return ProviderResult.success(record) if record and record.path.is_dir() else ProviderResult.invalid(f"unknown workspace: {workspace_id}")

    def cleanup(self, workspace_id: str, *, idempotency_key: str) -> ProviderResult[bool]:
        if guarded := self._guard():
            return guarded
        if replay := self._replay("cleanup", idempotency_key, workspace_id):
            return replay
        if not workspace_id or not idempotency_key:
            return ProviderResult.invalid("workspace_id and idempotency_key are required")
        record = self.workspaces.pop(workspace_id, None)
        if record and record.path.is_dir():
            record.path.rmdir()
        return self._remember("cleanup", idempotency_key, workspace_id, ProviderResult.success(True))


class FakeReviewProvider(ProviderBase):
    provider_name = "fake"
    provider_type = "review"
    capabilities = frozenset({"review.request", "review.status"})

    def __init__(self, *, available: bool = True) -> None:
        super().__init__(available=available)
        self.reviews: dict[str, ReviewStatus] = {}

    def request(self, request: ReviewRequest, *, idempotency_key: str) -> ProviderResult[ReviewStatus]:
        if guarded := self._guard():
            return guarded
        if replay := self._replay("request", idempotency_key, request):
            return replay
        if not request.task_id or not request.actor_id or not idempotency_key:
            return ProviderResult.invalid("task_id, actor_id, and idempotency_key are required")
        status = ReviewStatus(request.task_id, "review-requested")
        self.reviews[request.task_id] = status
        return self._remember("request", idempotency_key, request, ProviderResult.success(status))

    def status(self, task_id: str) -> ProviderResult[ReviewStatus]:
        if guarded := self._guard():
            return guarded
        status = self.reviews.get(task_id)
        return ProviderResult.success(status) if status else ProviderResult.invalid(f"unknown review: {task_id}")


class FakeEvidenceProvider(ProviderBase):
    provider_name = "fake"
    provider_type = "evidence"
    capabilities = frozenset({"evidence.record", "evidence.query", "evidence.completeness"})

    def __init__(self, *, available: bool = True) -> None:
        super().__init__(available=available)
        self.records: list[EvidenceRecord] = []

    def record(self, evidence: EvidenceRecord, *, idempotency_key: str) -> ProviderResult[EvidenceRecord]:
        if guarded := self._guard():
            return guarded
        if replay := self._replay("record", idempotency_key, evidence):
            return replay
        if not evidence.evidence_id or not evidence.task_id or not evidence.outcome or not evidence.reference or not idempotency_key:
            return ProviderResult.invalid("complete evidence and idempotency_key are required")
        self.records.append(evidence)
        return self._remember("record", idempotency_key, evidence, ProviderResult.success(evidence))

    def query(self, query: EvidenceQuery) -> ProviderResult[tuple[EvidenceRecord, ...]]:
        if guarded := self._guard():
            return guarded
        found = tuple(
            item for item in self.records
            if (query.task_id is None or item.task_id == query.task_id)
            and (query.category is None or item.category is query.category)
        )
        return ProviderResult.success(found)

    def completeness(self, task_id: str) -> ProviderResult[EvidenceCompleteness]:
        if not task_id:
            return ProviderResult.invalid("task_id is required")
        queried = self.query(EvidenceQuery(task_id=task_id))
        if queried.status is not OperationStatus.SUCCESS:
            return ProviderResult(queried.status, message=queried.message)
        present = {
            record.category.value
            for record in queried.value or ()
            if evidence_outcome_succeeds(record.category, record.outcome)
        }
        missing = tuple(category.value for category in EvidenceCategory if category.value not in present)
        return ProviderResult.success(EvidenceCompleteness(task_id, not missing, missing, queried.value or ()))


class FakeNotificationProvider(ProviderBase):
    provider_name = "fake"
    provider_type = "notifications"
    capabilities = frozenset({"notification.send", "notification.ask"})

    def __init__(self, *, available: bool = True) -> None:
        super().__init__(available=available)
        self.sent: list[NotificationRequest] = []

    def notify(self, request: NotificationRequest, *, idempotency_key: str) -> ProviderResult[NotificationReceipt]:
        if guarded := self._guard():
            return guarded
        if replay := self._replay("notify", idempotency_key, request):
            return replay
        if not request.event or not request.message or not idempotency_key or request.timeout_seconds < 1:
            return ProviderResult.invalid("event, message, positive timeout, and idempotency_key are required")
        self.sent.append(request)
        receipt = NotificationReceipt(request.event, True)
        return self._remember("notify", idempotency_key, request, ProviderResult.success(receipt))
