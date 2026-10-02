"""Independent review selection and bounded revision-cycle coordination."""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
from typing import Any, Callable, Mapping

from workflow_providers.contracts import (
    OperationStatus,
    ReviewFinding,
    ReviewOutcomeRequest,
    ReviewRequest,
    ReviewStatus,
)

from .assignments import RouteCandidate
from .identity import AcceptanceIdentity
from .manifests import ContextRequest, create_context_manifest
from .models import freeze, thaw
from workflow_providers.worker_dispatch import WorkerRequest, WorkerResult


class ReviewCoordinationError(ValueError):
    """Raised when approved review policy cannot select a safe route."""


@dataclass(frozen=True)
class ReviewContext:
    approved_scope: tuple[str, ...]
    diff: str
    acceptance_criteria: tuple[str, ...]
    tests: tuple[Mapping[str, Any], ...]
    evidence: tuple[Mapping[str, Any], ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "approved_scope", tuple(self.approved_scope))
        object.__setattr__(self, "acceptance_criteria", tuple(self.acceptance_criteria))
        object.__setattr__(self, "tests", tuple(freeze(item) for item in self.tests))
        object.__setattr__(self, "evidence", tuple(freeze(item) for item in self.evidence))

    def to_dict(self) -> dict[str, Any]:
        return {
            "approved_scope": list(self.approved_scope),
            "diff": self.diff,
            "acceptance_criteria": list(self.acceptance_criteria),
            "tests": thaw(self.tests),
            "evidence": thaw(self.evidence),
        }


@dataclass(frozen=True)
class ReviewCycle:
    task_id: str
    cycle_number: int
    provider_role: str
    reasoning: str
    implementation_provider: str
    implementation_model: str
    reviewer_provider: str
    reviewer_model: str
    context: ReviewContext
    lease_id: str = ""
    status: str = "review_requested"
    acceptance_identity: AcceptanceIdentity | None = None
    expected_ledger_revision: int | None = None
    implementation_session: str = ""
    reviewer_session: str = ""

    @property
    def reviewer_route(self) -> tuple[str, str]:
        return self.reviewer_provider, self.reviewer_model


@dataclass(frozen=True)
class RevisionRequest:
    task_id: str
    revision_identity: str
    findings: tuple[ReviewFinding, ...]
    provider_role: str
    reasoning: str
    preferred_route: tuple[str, str]
    provider: str
    model: str
    fallback_used: bool
    status: str = "revision_required"


@dataclass(frozen=True)
class ReviewDecision:
    task_id: str
    status: str
    cycle_number: int
    unresolved: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReviewExecution:
    cycle: ReviewCycle
    receipt: Any
    result: WorkerResult
    findings: tuple[ReviewFinding, ...]
    status: str


class ReviewCoordinator:
    def __init__(
        self,
        review_provider: Any,
        *,
        require_independent: bool = True,
        allow_self_review_fallback: bool = False,
        max_cycles: int = 2,
        route_available: Callable[[str, str], bool] | None = None,
        worker_dispatcher: Any | None = None,
        independence: str = "provider",
    ) -> None:
        if max_cycles < 1:
            raise ValueError("max_cycles must be positive")
        if independence not in ("provider", "session"):
            raise ValueError("independence must be provider or session")
        self.independence = independence
        self.review_provider = review_provider
        self.require_independent = require_independent
        self.allow_self_review_fallback = allow_self_review_fallback
        self.max_cycles = max_cycles
        self.route_available = route_available or (lambda _provider, _model: True)
        self.worker_dispatcher = worker_dispatcher

    def request_review(
        self,
        *,
        task_id: str,
        cycle_number: int,
        provider_role: str,
        reasoning: str,
        implementation_route: tuple[str, str],
        reviewer_candidates: tuple[RouteCandidate, ...],
        context: ReviewContext,
        lease_id: str = "",
        acceptance_identity: AcceptanceIdentity | None = None,
        expected_ledger_revision: int | None = None,
        implementation_session: str = "",
        reviewer_session: str = "",
    ) -> ReviewCycle:
        if cycle_number < 1 or cycle_number > self.max_cycles:
            raise ReviewCoordinationError("review cycle exceeds configured maximum")

        def independent(candidate: RouteCandidate) -> bool:
            if not self.require_independent:
                return True
            if self.independence == "session":
                return bool(reviewer_session) and reviewer_session != implementation_session
            return candidate.provider != implementation_route[0]

        selected = next((c for c in reviewer_candidates if independent(c)), None)
        if selected is None and self.allow_self_review_fallback:
            selected = next(iter(reviewer_candidates), None)
        if selected is None:
            unavailable = "session" if self.independence == "session" else "route"
            raise ReviewCoordinationError(f"independent reviewer {unavailable} is unavailable")
        idempotency_key = f"{task_id}:review:{cycle_number}:{selected.provider}:{selected.model}"
        if reviewer_session:
            idempotency_key += f":{reviewer_session}"
        requested = self.review_provider.request(
            ReviewRequest(task_id, f"reviewer:{selected.provider}", lease_id),
            idempotency_key=idempotency_key,
        )
        if requested.status is not OperationStatus.SUCCESS:
            raise ReviewCoordinationError(requested.message or "review request failed")
        return ReviewCycle(
            task_id,
            cycle_number,
            provider_role,
            reasoning,
            implementation_route[0],
            implementation_route[1],
            selected.provider,
            selected.model,
            context,
            lease_id,
            acceptance_identity=acceptance_identity,
            expected_ledger_revision=expected_ledger_revision,
            implementation_session=implementation_session,
            reviewer_session=reviewer_session,
        )

    def dispatch_review(
        self,
        cycle: ReviewCycle,
        request: WorkerRequest,
    ) -> ReviewExecution:
        if self.worker_dispatcher is None:
            raise ReviewCoordinationError("review worker dispatcher is unavailable")
        bounded_manifest = create_context_manifest(
            "review",
            ContextRequest(required=({"review_context": cycle.context.to_dict()},)),
        )
        try:
            bounded_request = replace(
                request,
                objective=f"Review approved implementation scope for {cycle.task_id}",
                generated_manifest=bounded_manifest,
                provider_role=cycle.provider_role,
                reasoning=cycle.reasoning,
                route_affinity=cycle.reviewer_route,
                acceptance_identity=cycle.acceptance_identity,
            )
        except (TypeError, ValueError) as error:
            raise ReviewCoordinationError(
                f"review acceptance identity is inconsistent: {error}"
            ) from error
        receipt = self.worker_dispatcher.dispatch(bounded_request)
        result = self.worker_dispatcher.collect_result(receipt.worker_id)
        if result.status != "completed":
            return ReviewExecution(cycle, receipt, result, (), "failed")
        if result.changed_files or result.commits:
            raise ReviewCoordinationError("review worker must not change files or create commits")
        if result.blockers:
            raise ReviewCoordinationError("completed review result must not contain blockers")
        decisions = tuple(
            str(item.get("decision", ""))
            for item in result.evidence
            if item.get("kind") == "review_decision"
        )
        if len(decisions) != 1 or decisions[0] not in {
            "approved",
            "changes_requested",
        }:
            raise ReviewCoordinationError("review result requires one explicit valid decision")
        findings = []
        for item in result.evidence:
            if item.get("kind") != "review_finding":
                continue
            try:
                findings.append(
                    ReviewFinding(
                        str(item["finding_id"]),
                        str(item["severity"]),
                        str(item["status"]),
                        str(item.get("location", "")),
                        str(item.get("expected_behavior", "")),
                        str(item.get("evidence", "")),
                    )
                )
            except KeyError as error:
                raise ReviewCoordinationError(
                    f"review finding is missing required field: {error.args[0]}"
                ) from error
        decision = decisions[0]
        terminal = {
            "verified", "withdrawn", "accepted-as-is", "deferred-verified", "human-waived"
        }
        if (
            decision == "approved"
            and any(finding.status not in terminal for finding in findings)
        ) or (decision == "changes_requested" and not findings):
            raise ReviewCoordinationError("review decision and findings are inconsistent")
        persisted = self.review_provider.record_outcome(
            ReviewOutcomeRequest(
                cycle.task_id,
                f"reviewer:{cycle.reviewer_provider}",
                decision,
                tuple(findings),
                cycle.lease_id,
                cycle.acceptance_identity,
                cycle.expected_ledger_revision,
            ),
            idempotency_key=(
                f"{cycle.task_id}:review:{cycle.cycle_number}:outcome:"
                f"{cycle.reviewer_provider}:{cycle.reviewer_model}"
            ),
        )
        if persisted.status is not OperationStatus.SUCCESS:
            raise ReviewCoordinationError(persisted.message or "review outcome persistence failed")
        return ReviewExecution(cycle, receipt, result, tuple(findings), decision)

    def route_revision(
        self,
        cycle: ReviewCycle,
        findings: tuple[ReviewFinding, ...],
        *,
        fallback_candidates: tuple[RouteCandidate, ...] = (),
    ) -> RevisionRequest:
        preferred = (cycle.implementation_provider, cycle.implementation_model)
        selected = preferred if self.route_available(*preferred) else None
        fallback_used = False
        if selected is None:
            candidate = next(
                (
                    route
                    for route in fallback_candidates
                    if (route.provider, route.model) != preferred
                    and self.route_available(route.provider, route.model)
                ),
                None,
            )
            if candidate is not None:
                selected = (candidate.provider, candidate.model)
                fallback_used = True
        finding_ids = ",".join(sorted(finding.finding_id for finding in findings))
        identity = hashlib.sha256(
            f"{cycle.task_id}\0{cycle.cycle_number}\0{finding_ids}".encode("utf-8")
        ).hexdigest()[:24]
        if selected is None:
            return RevisionRequest(
                cycle.task_id,
                f"revision-{identity}",
                tuple(findings),
                cycle.provider_role,
                cycle.reasoning,
                preferred,
                "",
                "",
                False,
                "human_decision_required",
            )
        transitioned = self.review_provider.begin_revision(
            cycle.task_id,
            actor_id="worker:revision",
            lease_id=cycle.lease_id,
            idempotency_key=f"{cycle.task_id}:{identity}:begin",
        )
        if transitioned.status is not OperationStatus.SUCCESS:
            raise ReviewCoordinationError(
                transitioned.message or "revision transition failed"
            )
        return RevisionRequest(
            cycle.task_id,
            f"revision-{identity}",
            tuple(findings),
            cycle.provider_role,
            cycle.reasoning,
            preferred,
            selected[0],
            selected[1],
            fallback_used,
        )

    def complete_revision(self, cycle: ReviewCycle, revision: RevisionRequest) -> ReviewStatus:
        completed = self.review_provider.complete_revision(
            cycle.task_id,
            tuple(finding.finding_id for finding in revision.findings),
            actor_id="worker:revision",
            lease_id=cycle.lease_id,
            idempotency_key=f"{cycle.task_id}:{revision.revision_identity}:complete",
        )
        if completed.status is not OperationStatus.SUCCESS or completed.value is None:
            raise ReviewCoordinationError(
                completed.message or "revision completion transition failed"
            )
        return completed.value

    def next_cycle(
        self,
        task_id: str,
        *,
        completed_cycles: int,
        unresolved: tuple[str, ...],
    ) -> ReviewDecision:
        unresolved = tuple(unresolved)
        if not unresolved:
            return ReviewDecision(task_id, "review_complete", completed_cycles, ())
        if completed_cycles >= self.max_cycles:
            return ReviewDecision(
                task_id, "human_decision_required", completed_cycles, unresolved
            )
        return ReviewDecision(task_id, "review_required", completed_cycles + 1, unresolved)

    @staticmethod
    def completion_decision(
        review: ReviewStatus,
        *,
        acceptance_evidence_complete: bool,
    ) -> ReviewDecision:
        ready = (
            review.state == "review-approved"
            and not review.unresolved_findings
            and acceptance_evidence_complete
        )
        return ReviewDecision(
            review.task_id,
            "ready_to_close" if ready else "review_pending",
            0,
            tuple(review.unresolved_findings),
        )
