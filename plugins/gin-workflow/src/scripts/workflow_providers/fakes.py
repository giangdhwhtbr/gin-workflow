"""Deterministic in-memory providers used by shared contract tests and harnesses."""

from __future__ import annotations

from dataclasses import replace
import hashlib
from pathlib import Path
from typing import Any, Iterable, Mapping

from .contracts import (
    EvidenceAuthority,
    EvidenceCompleteness,
    EvidenceQuery,
    EvidenceRecord,
    evaluate_evidence_completeness,
    validate_evidence_details,
    validate_authoritative_evidence,
    KnowledgeProposal,
    KnowledgeProposalRecord,
    KnowledgeRecord,
    NotificationReceipt,
    NotificationRequest,
    OperationStatus,
    ProviderBase,
    ProviderResult,
    ReviewInitRequest,
    ReviewRequest,
    ReviewOutcomeRequest,
    ReviewStatus,
    TaskClosureRequest,
    TaskCreateRequest,
    TaskDependencyRecord,
    TaskPreflight,
    TaskReadiness,
    TaskRecord,
    TaskSyncRequest,
    TaskSyncResult,
    normalize_task_changes,
    validate_task_attributes,
    validate_task_status,
    WorkspaceRecord,
    WorkspaceRequest,
)
from workflow_core.identity import AcceptanceIdentity
from workflow_core.approvals import ApprovalAction


def _proposal_record(proposal: KnowledgeProposal) -> KnowledgeProposalRecord:
    digest = hashlib.sha256(
        f"{proposal.title}\0{proposal.body}\0{proposal.proposed_by}\0{proposal.target}".encode()
    ).hexdigest()[:16]
    return KnowledgeProposalRecord(f"proposal-{digest}", proposal)


class FakeTaskTrackingProvider(ProviderBase):
    provider_name = "fake"
    provider_type = "task_tracking"
    capabilities = frozenset(
        {
            "task.create",
            "task.read",
            "task.update",
            "task.close",
            "task.dependency",
            "task.readiness",
            "task.preflight",
            "task.sync",
        }
    )

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
        record = TaskRecord(
            task_id,
            request.title,
            request.description,
            request.status,
            request.attributes,
            request.notes,
            request.acceptance_criteria,
        )
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

    def close_task(
        self, request: TaskClosureRequest, *, idempotency_key: str
    ) -> ProviderResult[TaskRecord]:
        if guarded := self._guard():
            return guarded
        if replay := self._replay("close_task", idempotency_key, request):
            return replay
        current = self.tasks.get(request.task_id)
        if current is None or not request.closure_reason.strip() or not request.acceptance_evidence:
            return ProviderResult.invalid(
                "known task_id, closure_reason, acceptance_evidence, and idempotency_key are required"
            )
        if not idempotency_key:
            return ProviderResult.invalid("idempotency_key is required")
        updated = replace(
            current,
            status="closed",
            closure_reason=request.closure_reason,
            acceptance_evidence=request.acceptance_evidence,
        )
        self.tasks[request.task_id] = updated
        return self._remember(
            "close_task", idempotency_key, request, ProviderResult.success(updated)
        )

    def add_dependency(
        self, dependency: TaskDependencyRecord, *, idempotency_key: str
    ) -> ProviderResult[TaskDependencyRecord]:
        if guarded := self._guard():
            return guarded
        if replay := self._replay("add_dependency", idempotency_key, dependency):
            return replay
        task = self.tasks.get(dependency.task_id)
        if (
            task is None
            or dependency.depends_on_task_id not in self.tasks
            or dependency.task_id == dependency.depends_on_task_id
            or dependency.dependency_type != "blocks"
            or not idempotency_key
        ):
            return ProviderResult.invalid("valid blocking dependency and idempotency_key are required")
        dependencies = tuple(sorted(set(task.dependencies) | {dependency.depends_on_task_id}))
        self.tasks[dependency.task_id] = replace(task, dependencies=dependencies)
        return self._remember(
            "add_dependency", idempotency_key, dependency, ProviderResult.success(dependency)
        )

    def readiness(self, task_id: str) -> ProviderResult[TaskReadiness]:
        if guarded := self._guard():
            return guarded
        task = self.tasks.get(task_id)
        if task is None:
            return ProviderResult.invalid(f"unknown task: {task_id}")
        blockers = tuple(
            dependency
            for dependency in task.dependencies
            if self.tasks[dependency].status != "closed"
        )
        return ProviderResult.success(TaskReadiness(task_id, not blockers, blockers))

    def preflight(self) -> ProviderResult[TaskPreflight]:
        if guarded := self._guard():
            return guarded
        return ProviderResult.success(
            TaskPreflight("fake", "fake-1", self.capabilities, True)
        )

    def sync(
        self,
        request: TaskSyncRequest,
        *,
        idempotency_key: str,
        approval_request=None,
        approval_decision=None,
        audit_event_store=None,
    ) -> ProviderResult[TaskSyncResult]:
        if guarded := self._guard():
            return guarded
        if replay := self._replay("sync", idempotency_key, request):
            return replay
        if request.mode not in {"flush", "pull", "merge"} or not idempotency_key:
            return ProviderResult.invalid("supported sync mode and idempotency_key are required")
        result = TaskSyncResult("fake", request.mode, request.dry_run, ("fake", "sync", request.mode))
        if request.dry_run:
            return self._remember("sync", idempotency_key, request, ProviderResult.success(result))
        approval_details = getattr(approval_request, "details", None)
        if (
            not isinstance(approval_details, Mapping)
            or approval_details.get("mode") != request.mode
            or approval_details.get("backend") != "fake"
        ):
            return ProviderResult.invalid(
                "data_move approval must match sync mode and backend"
            )
        try:
            from workflow_core.router import authorize_protected_action

            authorize_protected_action(
                ApprovalAction.DATA_MOVE,
                request.workflow_id,
                approval_request,
                approval_decision,
                audit_event_store,
            )
        except (PermissionError, TypeError, ValueError) as error:
            return ProviderResult.invalid(str(error))
        return self._remember("sync", idempotency_key, request, ProviderResult.success(result))


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
    capabilities = frozenset({
        "review.initialize", "review.request", "review.outcome", "review.status",
    })

    def __init__(self, *, available: bool = True) -> None:
        super().__init__(available=available)
        self.reviews: dict[str, ReviewStatus] = {}

    def initialize(
        self, request: ReviewInitRequest, *, idempotency_key: str
    ) -> ProviderResult[ReviewStatus]:
        if guarded := self._guard():
            return guarded
        if replay := self._replay("initialize", idempotency_key, request):
            return replay
        if not request.task_id or not request.actor_id or not idempotency_key:
            return ProviderResult.invalid("task_id, actor_id, and idempotency_key are required")
        existing = self.reviews.get(request.task_id)
        if existing is not None:
            return self._remember(
                "initialize", idempotency_key, request,
                ProviderResult.success(existing, idempotent=True),
            )
        status = ReviewStatus(request.task_id, "implementation-in-progress")
        self.reviews[request.task_id] = status
        return self._remember(
            "initialize", idempotency_key, request, ProviderResult.success(status)
        )

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

    def begin_revision(
        self, task_id: str, *, actor_id: str, lease_id: str, idempotency_key: str
    ) -> ProviderResult[ReviewStatus]:
        current = self.reviews.get(task_id)
        if current is None or not actor_id or not idempotency_key:
            return ProviderResult.invalid("known review and revision identity are required")
        status = ReviewStatus(
            task_id, "implementation-in-progress", current.total_findings,
            current.unresolved_findings, current.findings,
        )
        self.reviews[task_id] = status
        return ProviderResult.success(status)

    def complete_revision(
        self, task_id: str, finding_ids: tuple[str, ...], *,
        actor_id: str, lease_id: str, idempotency_key: str
    ) -> ProviderResult[ReviewStatus]:
        current = self.reviews.get(task_id)
        if current is None or not actor_id or not idempotency_key:
            return ProviderResult.invalid("known review and revision identity are required")
        selected = set(finding_ids)
        findings = tuple(
            replace(finding, status="fixed-awaiting-verification")
            if finding.finding_id in selected else finding
            for finding in current.findings
        )
        status = ReviewStatus(
            task_id, "review-requested", len(findings),
            tuple(f.finding_id for f in findings if f.status != "verified"), findings,
        )
        self.reviews[task_id] = status
        return ProviderResult.success(status)

    def status(self, task_id: str) -> ProviderResult[ReviewStatus]:
        if guarded := self._guard():
            return guarded
        status = self.reviews.get(task_id)
        return ProviderResult.success(status) if status else ProviderResult.invalid(f"unknown review: {task_id}")

    def record_outcome(
        self, request: ReviewOutcomeRequest, *, idempotency_key: str
    ) -> ProviderResult[ReviewStatus]:
        if guarded := self._guard():
            return guarded
        if replay := self._replay("record_outcome", idempotency_key, request):
            return replay
        if (
            request.task_id not in self.reviews
            or request.decision not in {"approved", "changes_requested"}
            or not request.actor_id
            or not idempotency_key
        ):
            return ProviderResult.invalid("valid review outcome fields are required")
        unresolved = tuple(
            finding.finding_id
            for finding in request.findings
            if finding.status not in {"verified", "withdrawn", "accepted-as-is", "deferred-verified", "human-waived"}
        )
        state = "review-approved" if request.decision == "approved" else "changes-requested"
        status = ReviewStatus(
            request.task_id, state, len(request.findings), unresolved, request.findings
        )
        self.reviews[request.task_id] = status
        return self._remember(
            "record_outcome", idempotency_key, request, ProviderResult.success(status)
        )


class FakeEvidenceProvider(ProviderBase):
    provider_name = "fake"
    provider_type = "evidence"
    capabilities = frozenset({"evidence.record", "evidence.query", "evidence.completeness"})

    def __init__(
        self,
        *,
        available: bool = True,
        authority: EvidenceAuthority | None = None,
    ) -> None:
        super().__init__(available=available)
        self.records: list[EvidenceRecord] = []
        self.authority = authority

    def record(self, evidence: EvidenceRecord, *, idempotency_key: str) -> ProviderResult[EvidenceRecord]:
        if guarded := self._guard():
            return guarded
        if not evidence.evidence_id or not evidence.task_id or not evidence.outcome or not evidence.reference or not idempotency_key:
            return ProviderResult.invalid("complete evidence and idempotency_key are required")
        if error := validate_evidence_details(evidence):
            return ProviderResult.invalid(error)
        if error := validate_authoritative_evidence(evidence, self.authority):
            return ProviderResult.invalid(error)
        if replay := self._replay("record", idempotency_key, evidence):
            existing = next(
                (item for item in self.records if item.evidence_id == evidence.evidence_id),
                None,
            )
            if existing != evidence:
                return ProviderResult.invalid(
                    "idempotent evidence replay does not match the stored record"
                )
            if error := validate_evidence_details(existing):
                return ProviderResult.unavailable(f"stored evidence is invalid: {error}")
            if error := validate_authoritative_evidence(existing, self.authority):
                return ProviderResult.unavailable(
                    f"stored evidence is not authoritative: {error}"
                )
            return replay
        self.records.append(evidence)
        return self._remember("record", idempotency_key, evidence, ProviderResult.success(evidence))

    def query(self, query: EvidenceQuery) -> ProviderResult[tuple[EvidenceRecord, ...]]:
        if guarded := self._guard():
            return guarded
        for record in self.records:
            if error := validate_evidence_details(record):
                return ProviderResult.unavailable(f"stored evidence is invalid: {error}")
            if error := validate_authoritative_evidence(record, self.authority):
                return ProviderResult.unavailable(
                    f"stored evidence is not authoritative: {error}"
                )
        found = tuple(
            item for item in self.records
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
        if not task_id:
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
