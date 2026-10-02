import re
from typing import Dict, Any, List, Optional
from review_ledger.schema import EventActions
from review_ledger.events import LedgerEvent, WorkflowIntegrityError

SOURCE_IDENTITY_FIELDS = (
    "repository_path",
    "checkpoint_ref",
    "checkpoint_sha",
    "source_scope_hash",
    "source_tree_hash",
)


def normalize_repository(repository: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(repository)
    if "checkpoint_ref" not in normalized and normalized.get("review_ref"):
        normalized["checkpoint_ref"] = normalized["review_ref"]
    if "checkpoint_sha" not in normalized and normalized.get("reviewed_source_sha"):
        normalized["checkpoint_sha"] = normalized["reviewed_source_sha"]
    complete = all(normalized.get(field) for field in SOURCE_IDENTITY_FIELDS)
    normalized["source_identity_status"] = "complete" if complete else "missing"
    return normalized


class FindingProjection:
    def __init__(self, finding_id: str, severity: str, status: str = "open", location: str = "", expected_behavior: str = "", evidence: str = ""):
        self.finding_id: str = finding_id
        self.severity: str = severity
        self.status: str = status
        self.clarification_count: int = 0
        self.deferral_reason: Optional[str] = None
        self.follow_up_bead_id: Optional[str] = None
        self.follow_up_bead_title: Optional[str] = None
        self.decision: Optional[str] = None
        self.waived_reason: Optional[str] = None
        self.location: str = location
        self.expected_behavior: str = expected_behavior
        self.evidence: str = evidence

    def to_dict(self) -> Dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "severity": self.severity,
            "status": self.status,
            "clarification_count": self.clarification_count,
            "deferral_reason": self.deferral_reason,
            "follow_up_bead_id": self.follow_up_bead_id,
            "follow_up_bead_title": self.follow_up_bead_title,
            "decision": self.decision,
            "waived_reason": self.waived_reason,
            "location": self.location,
            "expected_behavior": self.expected_behavior,
            "evidence": self.evidence
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "FindingProjection":
        f = cls(
            d["finding_id"],
            d["severity"],
            d["status"],
            d.get("location", ""),
            d.get("expected_behavior", ""),
            d.get("evidence", ""),
        )
        f.clarification_count = d.get("clarification_count", 0)
        f.deferral_reason = d.get("deferral_reason")
        f.follow_up_bead_id = d.get("follow_up_bead_id")
        f.follow_up_bead_title = d.get("follow_up_bead_title")
        f.decision = d.get("decision")
        f.waived_reason = d.get("waived_reason")
        return f

class LeaseProjection:
    def __init__(self, lease_id: str, actor_role: str, actor_id: str, acquired_at: str, expires_at: str, current_ledger_revision: int):
        self.lease_id: str = lease_id
        self.actor_role: str = actor_role
        self.actor_id: str = actor_id
        self.acquired_at: str = acquired_at
        self.expires_at: str = expires_at
        self.current_ledger_revision: int = current_ledger_revision

    def to_dict(self) -> Dict[str, Any]:
        return {
            "lease_id": self.lease_id,
            "actor_role": self.actor_role,
            "actor_id": self.actor_id,
            "acquired_at": self.acquired_at,
            "expires_at": self.expires_at,
            "current_ledger_revision": self.current_ledger_revision
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "LeaseProjection":
        return cls(
            d["lease_id"],
            d["actor_role"],
            d["actor_id"],
            d["acquired_at"],
            d["expires_at"],
            d["current_ledger_revision"]
        )

class ApprovalProjection:
    def __init__(
        self,
        approved_repositories: List[Dict[str, Any]],
        source_scope_hash: str,
        terminal_findings: List[str],
        event_id: str,
        workflow_id: str = "",
        attempt_id: str = "",
        task_id: str = "",
        reviewer_id: str = "",
        review_event_id: str = "",
        expected_ledger_revision: Optional[int] = None,
        review_start_revision: Optional[int] = None,
    ):
        self.approved_repositories = approved_repositories
        self.source_scope_hash = source_scope_hash
        self.terminal_findings = terminal_findings
        self.event_id = event_id
        self.workflow_id = workflow_id
        self.attempt_id = attempt_id
        self.task_id = task_id
        self.reviewer_id = reviewer_id
        self.review_event_id = review_event_id
        self.expected_ledger_revision = expected_ledger_revision
        self.review_start_revision = review_start_revision

    def to_dict(self) -> Dict[str, Any]:
        return {
            "approved_repositories": self.approved_repositories,
            "source_scope_hash": self.source_scope_hash,
            "terminal_findings": self.terminal_findings,
            "event_id": self.event_id,
            "workflow_id": self.workflow_id,
            "attempt_id": self.attempt_id,
            "task_id": self.task_id,
            "reviewer_id": self.reviewer_id,
            "review_event_id": self.review_event_id,
            "expected_ledger_revision": self.expected_ledger_revision,
            "review_start_revision": self.review_start_revision,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ApprovalProjection":
        return cls(
            d["approved_repositories"],
            d["source_scope_hash"],
            d["terminal_findings"],
            d["event_id"],
            d.get("workflow_id", ""),
            d.get("attempt_id", ""),
            d.get("task_id", ""),
            d.get("reviewer_id", ""),
            d.get("review_event_id", ""),
            d.get("expected_ledger_revision"),
            d.get("review_start_revision"),
        )

def _reviewed_tree_hashes(repositories: List[Dict[str, Any]]) -> Dict[str, str]:
    return {
        str(item.get("repository_id", "primary")): str(
            item.get("reviewed_source_tree_hash") or item.get("source_tree_hash") or ""
        )
        for item in repositories
    }


def approval_tree_mismatch(approval: Optional["ApprovalProjection"], repositories: List[Dict[str, Any]]) -> str:
    """Describe how the approved trees differ from the current checkpoint; empty when they match."""
    if approval is None:
        return ""
    approved = _reviewed_tree_hashes(list(approval.approved_repositories))
    current = _reviewed_tree_hashes(list(repositories))
    if approved == current:
        return ""
    return f"binds source trees {approved} but the current checkpoint is {current}"


class ReviewProjection:
    def __init__(self):
        self.review_state: str = "implementation-in-progress"
        self.findings: Dict[str, FindingProjection] = {}
        self.active_lease: Optional[LeaseProjection] = None
        self.active_approval: Optional[ApprovalProjection] = None
        self.repositories: List[Dict[str, Any]] = []
        self.source_scope: Dict[str, Any] = {}
        self.ledger_revision: int = 0
        self.next_finding_number: int = 1
        self.review_event_id: str = ""
        self.review_event_revision: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "review_state": self.review_state,
            "findings": {fid: f.to_dict() for fid, f in self.findings.items()},
            "active_lease": self.active_lease.to_dict() if self.active_lease else None,
            "active_approval": self.active_approval.to_dict() if self.active_approval else None,
            "repositories": self.repositories,
            "source_scope": self.source_scope,
            "ledger_revision": self.ledger_revision,
            "next_finding_number": self.next_finding_number,
            "review_event_id": self.review_event_id,
            "review_event_revision": self.review_event_revision,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ReviewProjection":
        p = cls()
        p.review_state = d.get("review_state", "implementation-in-progress")
        p.findings = {fid: FindingProjection.from_dict(f) for fid, f in d.get("findings", {}).items()}
        
        lease_d = d.get("active_lease")
        p.active_lease = LeaseProjection.from_dict(lease_d) if lease_d else None
        
        approval_d = d.get("active_approval")
        p.active_approval = ApprovalProjection.from_dict(approval_d) if approval_d else None
        
        p.repositories = d.get("repositories", [])
        p.source_scope = d.get("source_scope", {})
        p.ledger_revision = d.get("ledger_revision", 0)
        p.next_finding_number = d.get("next_finding_number", 1)
        p.review_event_id = d.get("review_event_id", "")
        p.review_event_revision = d.get("review_event_revision")
        return p

    def apply_event(self, event: LedgerEvent):
        """Updates the projection by applying a single event."""
        self.ledger_revision += 1
        
        action = event.action
        payload = event.payload

        if action == EventActions.LEDGER_CREATED:
            self.review_state = payload.get("review_state", "implementation-in-progress")
            self.repositories = [normalize_repository(item) for item in payload.get("repositories", [])]
            self.source_scope = payload.get("source_scope", {})

        elif action == EventActions.REVIEW_SCOPE_ESTABLISHED:
            self.source_scope = payload.get("source_scope", {})

        elif action == EventActions.REVIEW_SCOPE_CHANGE_REQUESTED:
            self.source_scope = payload.get("source_scope", {})
            self.active_approval = None # Scope change invalidates approval
            if self.review_state in ("review-approved", "verification-in-progress", "ready-to-ship"):
                self.review_state = "review-requested"


        elif action == EventActions.LEASE_ACQUIRED:
            self.active_lease = LeaseProjection(
                lease_id=payload["lease_id"],
                actor_role=payload["actor_role"],
                actor_id=payload["actor_id"],
                acquired_at=payload["acquired_at"],
                expires_at=payload["expires_at"],
                current_ledger_revision=self.ledger_revision
            )

        elif action == EventActions.LEASE_RENEWED:
            if self.active_lease:
                self.active_lease.expires_at = payload["expires_at"]
                self.active_lease.current_ledger_revision = self.ledger_revision

        elif action in (EventActions.LEASE_RELEASED, EventActions.LEASE_BROKEN):
            self.active_lease = None

        elif action == EventActions.SOURCE_CHECKPOINT_CREATED:
            # Checkpoint payload has repositories
            if "repositories" in payload:
                self.repositories = [normalize_repository(item) for item in payload["repositories"]]
            # A checkpoint of a tree nobody approved invalidates the approval, like a scope change.
            if approval_tree_mismatch(self.active_approval, self.repositories):
                self.active_approval = None
                if self.review_state in ("review-approved", "verification-in-progress", "ready-to-ship"):
                    self.review_state = "review-requested"


        elif action == "implementation-complete":
            self.review_state = "implementation-complete"

        elif action == "review-requested":
            self.review_state = "review-requested"

        elif action == "changes-requested":
            self.review_state = "changes-requested"

        elif action == "implementation-in-progress":
            self.review_state = "implementation-in-progress"
            self.active_approval = None

        elif action == EventActions.REVIEW_STARTED:
            self.review_state = "review-in-progress"
            self.review_event_id = event.event_id
            self.review_event_revision = self.ledger_revision

        elif action == EventActions.FINDING_CREATED:
            fid = payload["finding_id"]
            if fid in self.findings:
                raise WorkflowIntegrityError(f"Duplicate finding ID: {fid}")
            self.findings[fid] = FindingProjection(
                finding_id=fid,
                severity=payload["severity"],
                status="open",
                location=payload.get("location", ""),
                expected_behavior=payload.get("expected_behavior", ""),
                evidence=payload.get("evidence", ""),
            )
            # Derive next finding number from highest parsed finding ID seen
            match = re.search(r'(\d+)$', fid)
            if match:
                num = int(match.group(1))
                if num >= self.next_finding_number:
                    self.next_finding_number = num + 1

        elif action == EventActions.FINDING_REOPENED:
            # A reviewer rejecting a claimed fix. Only the status moves: the
            # finding keeps its id, severity and evidence, so the ledger shows
            # one finding that went open -> fixed -> open, not a new finding
            # that happens to describe the same defect.
            fid = payload["finding_id"]
            if fid not in self.findings:
                raise WorkflowIntegrityError(f"Unknown finding ID: {fid}")
            self.findings[fid].status = "open"

        elif action == EventActions.FINDING_FIXED:
            fid = payload["finding_id"]
            if fid in self.findings:
                self.findings[fid].status = "fixed-awaiting-verification"

        elif action == EventActions.FINDING_DISPUTED:
            fid = payload["finding_id"]
            if fid in self.findings:
                self.findings[fid].status = "disputed"

        elif action == EventActions.CLARIFICATION_REQUESTED:
            fid = payload["finding_id"]
            if fid in self.findings:
                self.findings[fid].status = "clarification-requested"

        elif action == EventActions.CLARIFICATION_PROVIDED:
            fid = payload["finding_id"]
            if fid in self.findings:
                self.findings[fid].status = "clarification-provided"
                self.findings[fid].clarification_count += 1

        elif action == EventActions.DEFERRAL_PROPOSED:
            fid = payload["finding_id"]
            if fid in self.findings:
                self.findings[fid].status = "deferral-proposed"
                self.findings[fid].deferral_reason = payload.get("reason")
                self.findings[fid].follow_up_bead_id = payload.get("follow_up_bead_id")
                self.findings[fid].follow_up_bead_title = payload.get("follow_up_bead_title")

        elif action == EventActions.DEFERRAL_APPROVED:
            fid = payload["finding_id"]
            if fid in self.findings:
                self.findings[fid].status = "deferred-verified"

        elif action == EventActions.FINDING_VERIFIED:
            fid = payload["finding_id"]
            if fid in self.findings:
                self.findings[fid].status = "verified"

        elif action == EventActions.FINDING_WITHDRAWN:
            fid = payload["finding_id"]
            if fid in self.findings:
                self.findings[fid].status = "withdrawn"

        elif action == EventActions.FINDING_ACCEPTED_AS_IS:
            fid = payload["finding_id"]
            if fid in self.findings:
                self.findings[fid].status = "accepted-as-is"

        elif action == EventActions.HUMAN_DECISION_REQUIRED:
            fid = payload["finding_id"]
            if fid in self.findings:
                self.findings[fid].status = "human-decision-required"

        elif action == EventActions.HUMAN_DECISION_RECORDED:
            fid = payload["finding_id"]
            if fid in self.findings:
                self.findings[fid].status = "human-decision-recorded"
                self.findings[fid].decision = payload.get("decision")

        elif action == EventActions.FINDING_WAIVED:
            fid = payload["finding_id"]
            if fid in self.findings:
                self.findings[fid].status = "human-waived"
                self.findings[fid].waived_reason = payload.get("reason")

        elif action == EventActions.REVIEW_APPROVED:
            self.review_state = "review-approved"
            self.active_approval = ApprovalProjection(
                approved_repositories=payload["approved_repositories"],
                source_scope_hash=payload["source_scope_hash"],
                terminal_findings=payload["terminal_findings"],
                event_id=event.event_id,
                workflow_id=payload.get("workflow_id", ""),
                attempt_id=payload.get("attempt_id", ""),
                task_id=payload.get("task_id", ""),
                reviewer_id=payload.get("reviewer_id", ""),
                review_event_id=payload.get("review_event_id", ""),
                expected_ledger_revision=payload.get("expected_ledger_revision"),
                review_start_revision=payload.get("review_start_revision"),
            )

        elif action == EventActions.REVIEW_APPROVAL_INVALIDATED:
            self.review_state = "implementation-in-progress"
            self.active_approval = None

        elif action == EventActions.VERIFICATION_STARTED:
            self.review_state = "verification-in-progress"

        elif action == EventActions.VERIFICATION_PASSED:
            self.review_state = "ready-to-ship"

        elif action == EventActions.VERIFICATION_FAILED:
            # Spec says verification failed returns to implementation-in-progress (invalidating active approval)
            self.review_state = "implementation-in-progress"
            self.active_approval = None

        elif action == EventActions.TRANSITION_COMPLETED:
            self.review_state = payload["to"]

        elif action == EventActions.SHIPPING_STARTED:
            self.review_state = "ready-to-ship" # Or intermediate if defined

        elif action == EventActions.SHIPPING_FAILED:
            self.review_state = "shipping-failed"

        elif action == EventActions.SHIPPING_COMPLETED:
            self.review_state = "closed"

        elif action == EventActions.RECOVERY_PERFORMED:
            if "review_state" in payload:
                self.review_state = payload["review_state"]

        if self.active_lease is not None:
            self.active_lease.current_ledger_revision = self.ledger_revision

    @classmethod
    def replay(cls, events: List[LedgerEvent]) -> "ReviewProjection":
        p = cls()
        for e in events:
            p.apply_event(e)
        return p
