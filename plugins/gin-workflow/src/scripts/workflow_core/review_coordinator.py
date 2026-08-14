"""Independent review selection and bounded revision-cycle coordination."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, Callable, Mapping

from workflow_providers.contracts import (
    OperationStatus,
    ReviewFinding,
    ReviewRequest,
    ReviewStatus,
)

from .assignments import RouteCandidate
from .models import freeze, thaw


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
    status: str = "review_requested"

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


class ReviewCoordinator:
    def __init__(
        self,
        review_provider: Any,
        *,
        require_independent: bool = True,
        allow_self_review_fallback: bool = False,
        max_cycles: int = 3,
        route_available: Callable[[str, str], bool] | None = None,
    ) -> None:
        if max_cycles < 1:
            raise ValueError("max_cycles must be positive")
        self.review_provider = review_provider
        self.require_independent = require_independent
        self.allow_self_review_fallback = allow_self_review_fallback
        self.max_cycles = max_cycles
        self.route_available = route_available or (lambda _provider, _model: True)

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
    ) -> ReviewCycle:
        if cycle_number < 1 or cycle_number > self.max_cycles:
            raise ReviewCoordinationError("review cycle exceeds configured maximum")
        selected = next(
            (
                candidate
                for candidate in reviewer_candidates
                if not self.require_independent
                or candidate.provider != implementation_route[0]
            ),
            None,
        )
        if selected is None and self.allow_self_review_fallback:
            selected = next(iter(reviewer_candidates), None)
        if selected is None:
            raise ReviewCoordinationError("independent reviewer route is unavailable")
        requested = self.review_provider.request(
            ReviewRequest(task_id, f"reviewer:{selected.provider}"),
            idempotency_key=f"{task_id}:review:{cycle_number}:{selected.provider}:{selected.model}",
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
        )

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
