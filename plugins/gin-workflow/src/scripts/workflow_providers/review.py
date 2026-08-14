"""Provider-neutral facade over the existing append-only review ledger."""

from __future__ import annotations

from pathlib import Path
import tempfile

from .contracts import (
    ProviderBase,
    ProviderResult,
    ReviewFinding,
    ReviewOutcomeRequest,
    ReviewRequest,
    ReviewStatus,
)
from workflow_core.atomic import atomic_write_many


class ReviewLedgerProvider(ProviderBase):
    provider_name = "review-ledger"
    provider_type = "review"
    capabilities = frozenset({"review.request", "review.outcome", "review.status"})

    def __init__(self, repository_root: Path) -> None:
        super().__init__()
        self.repository_root = Path(repository_root).resolve()

    def _load(self, task_id: str):
        from review_ledger.cli import load_ledger

        return load_ledger(task_id, str(self.repository_root))[1]

    def _mutate_batch(self, task_id: str, operations, *, lease_id: str):
        from review_ledger.cli import get_ledger_paths, mutate_ledger

        real_json, real_markdown = (
            Path(path) for path in get_ledger_paths(task_id, str(self.repository_root))
        )
        with tempfile.TemporaryDirectory() as directory:
            temporary_root = Path(directory)
            temp_json, temp_markdown = (
                Path(path) for path in get_ledger_paths(task_id, str(temporary_root))
            )
            temp_json.parent.mkdir(parents=True, exist_ok=True)
            temp_json.write_bytes(real_json.read_bytes())
            if real_markdown.is_file():
                temp_markdown.write_bytes(real_markdown.read_bytes())
            projection = None
            for index, (action, payload, actor_role, actor_id) in enumerate(operations):
                _, projection = mutate_ledger(
                    task_id,
                    action,
                    payload,
                    actor_role,
                    actor_id,
                    base_dir=str(temporary_root),
                    lease_id=lease_id or None,
                    bypass_lease=index > 0,
                )
            assert projection is not None
            if lease_id and projection.active_lease is not None:
                _, projection = mutate_ledger(
                    task_id,
                    "lease-renewed",
                    {"expires_at": projection.active_lease.expires_at},
                    "reviewer",
                    projection.active_lease.actor_id,
                    base_dir=str(temporary_root),
                    lease_id=lease_id,
                    bypass_lease=True,
                )
            atomic_write_many(
                {
                    real_json: temp_json.read_bytes(),
                    real_markdown: temp_markdown.read_bytes(),
                }
            )
            return projection

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
            operations = []
            if current.value.state == "implementation-in-progress":
                operations.append(
                    ("implementation-complete", {}, "worker", request.actor_id)
                )
            operations.append(
                ("review-requested", {"to": "review-requested"}, "worker", request.actor_id)
            )
            projection = self._mutate_batch(
                request.task_id, operations, lease_id=request.lease_id
            )
            normalized = self._normalize(request.task_id, projection)
        except FileNotFoundError as error:
            return ProviderResult.unavailable(str(error))
        except Exception as error:  # existing ledger boundary
            return ProviderResult.invalid(f"review request rejected: {error}")
        return self._remember("request", idempotency_key, request, ProviderResult.success(normalized))

    def record_outcome(
        self, request: ReviewOutcomeRequest, *, idempotency_key: str
    ) -> ProviderResult[ReviewStatus]:
        if guarded := self._guard():
            return guarded
        if replay := self._replay("record_outcome", idempotency_key, request):
            return replay
        if (
            request.decision not in {"approved", "changes_requested"}
            or not request.task_id
            or not request.actor_id
            or not idempotency_key
        ):
            return ProviderResult.invalid("valid review outcome fields are required")
        try:
            current = self.status(request.task_id)
            if current.value is None:
                return current
            wanted_state = (
                "review-approved" if request.decision == "approved" else "changes-requested"
            )
            if current.value.state == wanted_state:
                return ProviderResult.success(current.value, idempotent=True)
            operations = [("review-started", {}, "reviewer", request.actor_id)]
            existing = {finding.finding_id: finding for finding in current.value.findings}
            for finding in request.findings:
                if finding.finding_id in existing and finding.status == "verified":
                    operations.append(
                        (
                            "finding-verified",
                            {"finding_id": finding.finding_id},
                            "reviewer",
                            request.actor_id,
                        )
                    )
                elif finding.finding_id not in existing:
                    operations.append(("finding-created", {
                        "finding_id": finding.finding_id,
                        "severity": finding.severity,
                        "location": finding.location,
                        "expected_behavior": finding.expected_behavior,
                        "evidence": finding.evidence,
                    }, "reviewer", request.actor_id))
            action = (
                "review-approved"
                if request.decision == "approved"
                else "changes-requested"
            )
            decision_payload = {}
            if action == "review-approved":
                decision_payload = {
                    "approved_repositories": self._load(request.task_id).repositories,
                    "source_scope_hash": "",
                    "terminal_findings": [
                        finding.finding_id for finding in request.findings
                    ],
                }
            operations.append((action, decision_payload, "reviewer", request.actor_id))
            projection = self._mutate_batch(
                request.task_id, operations, lease_id=request.lease_id
            )
            normalized = self._normalize(request.task_id, projection)
        except FileNotFoundError as error:
            return ProviderResult.unavailable(str(error))
        except Exception as error:
            return ProviderResult.invalid(f"review outcome rejected: {error}")
        return self._remember(
            "record_outcome", idempotency_key, request, ProviderResult.success(normalized)
        )

    def begin_revision(
        self, task_id: str, *, actor_id: str, lease_id: str, idempotency_key: str
    ) -> ProviderResult[ReviewStatus]:
        if replay := self._replay(
            "begin_revision", idempotency_key, (task_id, actor_id, lease_id)
        ):
            return replay
        current = self.status(task_id)
        if current.value is None:
            return current
        if current.value.state == "implementation-in-progress":
            return ProviderResult.success(current.value, idempotent=True)
        try:
            projection = self._mutate_batch(
                task_id,
                [("implementation-in-progress", {}, "worker", actor_id)],
                lease_id=lease_id,
            )
            normalized = self._normalize(task_id, projection)
        except Exception as error:
            return ProviderResult.invalid(f"revision transition rejected: {error}")
        return self._remember(
            "begin_revision",
            idempotency_key,
            (task_id, actor_id, lease_id),
            ProviderResult.success(normalized),
        )

    def complete_revision(
        self, task_id: str, finding_ids: tuple[str, ...], *,
        actor_id: str, lease_id: str, idempotency_key: str
    ) -> ProviderResult[ReviewStatus]:
        fingerprint = (task_id, tuple(finding_ids), actor_id, lease_id)
        if replay := self._replay("complete_revision", idempotency_key, fingerprint):
            return replay
        operations = [
            ("finding-fixed", {"finding_id": finding_id}, "worker", actor_id)
            for finding_id in finding_ids
        ]
        operations.extend(
            [
                ("implementation-complete", {}, "worker", actor_id),
                ("review-requested", {}, "worker", actor_id),
            ]
        )
        try:
            projection = self._mutate_batch(task_id, operations, lease_id=lease_id)
            normalized = self._normalize(task_id, projection)
        except Exception as error:
            return ProviderResult.invalid(f"revision completion rejected: {error}")
        return self._remember(
            "complete_revision", idempotency_key, fingerprint,
            ProviderResult.success(normalized),
        )

    def complete_revision(
        self, task_id: str, finding_ids: tuple[str, ...], *,
        actor_id: str, lease_id: str, idempotency_key: str
    ) -> ProviderResult[ReviewStatus]:
        fingerprint = (task_id, tuple(finding_ids), actor_id, lease_id)
        if replay := self._replay("complete_revision", idempotency_key, fingerprint):
            return replay
        operations = [
            ("finding-fixed", {"finding_id": finding_id}, "worker", actor_id)
            for finding_id in finding_ids
        ]
        operations.extend(
            [
                ("implementation-complete", {}, "worker", actor_id),
                ("review-requested", {}, "worker", actor_id),
            ]
        )
        try:
            projection = self._mutate_batch(task_id, operations, lease_id=lease_id)
            normalized = self._normalize(task_id, projection)
        except Exception as error:
            return ProviderResult.invalid(f"revision completion rejected: {error}")
        return self._remember(
            "complete_revision", idempotency_key, fingerprint,
            ProviderResult.success(normalized),
        )
