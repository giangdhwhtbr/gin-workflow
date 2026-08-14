"""Provider-neutral facade over the existing append-only review ledger."""

from __future__ import annotations

from pathlib import Path

from .contracts import ProviderBase, ProviderResult, ReviewFinding, ReviewRequest, ReviewStatus


class ReviewLedgerProvider(ProviderBase):
    provider_name = "review-ledger"
    provider_type = "review"
    capabilities = frozenset({"review.request", "review.status"})

    def __init__(self, repository_root: Path) -> None:
        super().__init__()
        self.repository_root = Path(repository_root).resolve()

    def _load(self, task_id: str):
        from review_ledger.cli import load_ledger

        return load_ledger(task_id, str(self.repository_root))[1]

    @staticmethod
    def _normalize(task_id: str, projection) -> ReviewStatus:
        from review_ledger.bead_fsm import TERMINAL_FINDING_STATUSES

        unresolved = tuple(
            finding_id
            for finding_id, finding in projection.findings.items()
            if finding.status not in TERMINAL_FINDING_STATUSES
        )
        findings = tuple(
            ReviewFinding(
                finding_id,
                finding.severity,
                finding.status,
                getattr(finding, "location", ""),
                getattr(finding, "expected_behavior", ""),
                getattr(finding, "evidence", ""),
            )
            for finding_id, finding in sorted(projection.findings.items())
        )
        return ReviewStatus(
            task_id,
            projection.review_state,
            len(projection.findings),
            unresolved,
            findings,
        )

    def status(self, task_id: str) -> ProviderResult[ReviewStatus]:
        if guarded := self._guard():
            return guarded
        if not task_id.strip():
            return ProviderResult.invalid("task_id is required")
        try:
            return ProviderResult.success(self._normalize(task_id, self._load(task_id)))
        except FileNotFoundError as error:
            return ProviderResult.unavailable(str(error))
        except Exception as error:  # existing ledger boundary
            return ProviderResult.unavailable(f"review ledger unavailable: {error}")

    def request(self, request: ReviewRequest, *, idempotency_key: str) -> ProviderResult[ReviewStatus]:
        if guarded := self._guard():
            return guarded
        if replay := self._replay("request", idempotency_key, request):
            return replay
        if not request.task_id.strip() or not request.actor_id.strip() or not idempotency_key:
            return ProviderResult.invalid("task_id, actor_id, and idempotency_key are required")
        current = self.status(request.task_id)
        if current.value is None:
            return current
        if current.value.state in {"review-requested", "review-in-progress", "review-approved"}:
            return self._remember(
                "request", idempotency_key, request,
                ProviderResult.success(current.value, idempotent=True),
            )
        try:
            from review_ledger.cli import mutate_ledger

            _, projection = mutate_ledger(
                request.task_id,
                "review-requested",
                {"to": "review-requested"},
                "worker",
                request.actor_id,
                base_dir=str(self.repository_root),
            )
            normalized = self._normalize(request.task_id, projection)
        except FileNotFoundError as error:
            return ProviderResult.unavailable(str(error))
        except Exception as error:  # existing ledger boundary
            return ProviderResult.invalid(f"review request rejected: {error}")
        return self._remember("request", idempotency_key, request, ProviderResult.success(normalized))
