"""Provider-neutral facade over the existing append-only review ledger."""

from __future__ import annotations

from pathlib import Path
import subprocess

from .contracts import (
    ProviderBase,
    ProviderResult,
    ReviewFinding,
    ReviewInitRequest,
    ReviewOutcomeRequest,
    ReviewRequest,
    ReviewStatus,
    ReviewLease,
)
from workflow_core.identity import AcceptanceIdentity, RepositorySnapshot


class ReviewLedgerProvider(ProviderBase):
    provider_name = "review-ledger"
    provider_type = "review"
    capabilities = frozenset({
        "review.initialize", "review.request", "review.outcome", "review.status",
    })

    def __init__(self, repository_root: Path) -> None:
        super().__init__()
        self.repository_root = Path(repository_root).resolve()

    def _load(self, task_id: str):
        from review_ledger.cli import load_ledger

        return load_ledger(task_id, str(self.repository_root))[1]

    def _mutate_batch(self, task_id: str, operations, *, lease_id: str):
        from review_ledger.cli import mutate_ledger_batch

        return mutate_ledger_batch(
            task_id,
            operations,
            base_dir=str(self.repository_root),
            lease_id=lease_id or None,
        )[1]

    def _acceptance_identity(
        self,
        task_id: str,
        projection,
        expected: AcceptanceIdentity,
    ) -> tuple[AcceptanceIdentity, list[dict]]:
        from review_ledger.source_identity import (
            compute_source_scope_hash,
            compute_tree_hash_for_commit,
        )

        scope_hash = compute_source_scope_hash(projection.source_scope)
        snapshots = []
        approved_repositories = []
        for repository in projection.repositories:
            required = (
                "repository_id", "repository_path", "checkpoint_ref",
                "checkpoint_sha", "source_scope_hash", "source_tree_hash",
            )
            if repository.get("source_identity_status") != "complete" or any(
                not str(repository.get(field, "")).strip() for field in required
            ):
                raise ValueError("legacy or incomplete source identity cannot be approved")
            repository_path = (
                self.repository_root / repository["repository_path"]
            ).resolve()
            try:
                repository_path.relative_to(self.repository_root)
            except ValueError as error:
                raise ValueError("repository path escapes provider root") from error
            resolved = subprocess.run(
                ["git", "rev-parse", "--verify", f"{repository['checkpoint_ref']}^{{commit}}"],
                cwd=repository_path,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            if resolved != repository["checkpoint_sha"]:
                raise ValueError("checkpoint ref no longer matches checkpoint SHA")
            recomputed_tree = compute_tree_hash_for_commit(
                repository["repository_id"],
                str(repository_path),
                projection.source_scope,
                resolved,
            )
            if repository["source_scope_hash"] != scope_hash:
                raise ValueError("stored source scope hash does not match current scope")
            if repository["source_tree_hash"] != recomputed_tree:
                raise ValueError("stored source tree hash does not match checkpoint object")
            snapshot = RepositorySnapshot(
                repository_id=repository["repository_id"],
                source_scope_hash=scope_hash,
                source_tree_hash=recomputed_tree,
                checkpoint_sha=resolved,
                checkpoint_ref=repository["checkpoint_ref"],
            )
            snapshots.append(snapshot)
            approved = dict(repository)
            approved.update({
                "source_scope_hash": scope_hash,
                "source_tree_hash": recomputed_tree,
                "reviewed_source_tree_hash": recomputed_tree,
                "checkpoint_sha": resolved,
                "reviewed_source_sha": resolved,
            })
            approved_repositories.append(approved)
        actual = AcceptanceIdentity(
            expected.workflow_id,
            expected.attempt_id,
            task_id,
            tuple(snapshots),
        )
        expected.require_exact_match(actual)
        return actual, approved_repositories

    def _validate_approved_retry(self, request, projection) -> None:
        approval = projection.active_approval
        expected = request.acceptance_identity
        if approval is None or expected is None or request.expected_ledger_revision is None:
            raise ValueError("approved retry requires complete persisted acceptance identity")
        if (
            approval.workflow_id != expected.workflow_id
            or approval.attempt_id != expected.attempt_id
            or approval.task_id != expected.task_id
            or approval.reviewer_id != request.actor_id
            or approval.expected_ledger_revision != request.expected_ledger_revision
            or not approval.review_event_id
            or approval.review_event_id != projection.review_event_id
        ):
            raise ValueError("approved retry does not match persisted approval provenance")
        snapshots = []
        for repository in approval.approved_repositories:
            snapshots.append(RepositorySnapshot(
                repository["repository_id"],
                repository["source_scope_hash"],
                repository["source_tree_hash"],
                repository["checkpoint_sha"],
                repository["checkpoint_ref"],
            ))
        persisted = AcceptanceIdentity(
            approval.workflow_id,
            approval.attempt_id,
            approval.task_id,
            tuple(snapshots),
        )
        expected.require_exact_match(persisted)
        from review_ledger.bead_fsm import TERMINAL_FINDING_STATUSES

        current_terminal = sorted(
            finding_id
            for finding_id, finding in projection.findings.items()
            if finding.status in TERMINAL_FINDING_STATUSES
        )
        if current_terminal != sorted(approval.terminal_findings):
            raise ValueError("persisted terminal findings do not match current ledger")
        for supplied in request.findings:
            current = projection.findings.get(supplied.finding_id)
            if current is None or current.status != supplied.status:
                raise ValueError("supplied retry finding does not match current ledger")
        self._acceptance_identity(request.task_id, projection, expected)

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
        lease = None
        if projection.active_lease is not None:
            lease = ReviewLease(
                projection.active_lease.lease_id,
                projection.active_lease.actor_id,
                projection.active_lease.expires_at,
                projection.active_lease.current_ledger_revision,
            )
        return ReviewStatus(
            task_id,
            projection.review_state,
            len(projection.findings),
            unresolved,
            findings,
            lease,
            projection.ledger_revision,
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

    def initialize(
        self, request: ReviewInitRequest, *, idempotency_key: str
    ) -> ProviderResult[ReviewStatus]:
        if guarded := self._guard():
            return guarded
        if replay := self._replay("initialize", idempotency_key, request):
            return replay
        required = (
            request.task_id, request.actor_id, request.repository_id,
            request.repository_path, request.base_ref, request.review_ref,
            request.role, request.actor_role,
        )
        if not all(str(field).strip() for field in required) or not idempotency_key:
            return ProviderResult.invalid(
                "task_id, actor_id, repository identity, refs, roles, and "
                "idempotency_key are required"
            )
        if not request.scope:
            return ProviderResult.invalid("a non-empty source scope is required")

        existing = self.status(request.task_id)
        if existing.value is not None:
            return self._remember(
                "initialize", idempotency_key, request,
                ProviderResult.success(existing.value, idempotent=True),
            )

        repository_path = (self.repository_root / request.repository_path).resolve()
        try:
            repository_path.relative_to(self.repository_root)
        except ValueError:
            return ProviderResult.invalid("repository path escapes provider root")
        if not repository_path.is_dir():
            return ProviderResult.invalid("repository path does not exist")

        try:
            from review_ledger.cli import initialize_ledger

            initialize_ledger(
                bead_id=request.task_id,
                repository_id=request.repository_id,
                role=request.role,
                repo_path=str(repository_path),
                review_ref=request.review_ref,
                base_ref=request.base_ref,
                scope=dict(request.scope),
                actor_role=request.actor_role,
                actor_id=request.actor_id,
                base_dir=str(self.repository_root),
            )
            normalized = self._normalize(request.task_id, self._load(request.task_id))
        except Exception as error:  # existing ledger boundary
            return ProviderResult.invalid(f"review initialization rejected: {error}")
        return self._remember(
            "initialize", idempotency_key, request, ProviderResult.success(normalized)
        )

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
                if request.decision == "approved":
                    self._validate_approved_retry(
                        request, self._load(request.task_id)
                    )
                return ProviderResult.success(current.value, idempotent=True)
            if request.decision == "approved" and (
                request.acceptance_identity is None
                or request.expected_ledger_revision is None
            ):
                return ProviderResult.invalid(
                    "approval requires acceptance_identity and expected_ledger_revision"
                )

            from review_ledger.cli import (
                build_start_review_operations,
                mutate_ledger_transaction,
            )

            def build(projection):
                if request.expected_ledger_revision is not None and (
                    request.expected_ledger_revision != projection.ledger_revision
                ):
                    raise ValueError(
                        "expected ledger revision does not match current ledger"
                    )
                operations, effective_lease_id = build_start_review_operations(
                    projection,
                    request.actor_id,
                    requested_lease_id=request.lease_id or None,
                )
                review_event_id = projection.review_event_id
                review_start_revision = projection.review_event_revision
                for index, operation in enumerate(operations, start=1):
                    if operation[0] == "review-started":
                        review_start_revision = projection.ledger_revision + index
                        review_event_id = f"EV-{review_start_revision:06d}"
                        break
                if not review_event_id or review_start_revision is None:
                    raise ValueError("review outcome has no auditable review-started event")
                existing = projection.findings
                for finding in request.findings:
                    if finding.finding_id in existing and finding.status == "verified":
                        operations.append((
                            "finding-verified",
                            {"finding_id": finding.finding_id},
                            "reviewer",
                            request.actor_id,
                        ))
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
                    identity, repositories = self._acceptance_identity(
                        request.task_id,
                        projection,
                        request.acceptance_identity,
                    )
                    decision_payload = {
                        "approved_repositories": repositories,
                        "source_scope_hash": repositories[0]["source_scope_hash"],
                        "terminal_findings": sorted({
                            finding_id
                            for finding_id, finding in projection.findings.items()
                            if finding.status in {
                                "verified", "withdrawn", "accepted-as-is",
                                "deferred-verified", "human-waived",
                            }
                        } | {
                            finding.finding_id
                            for finding in request.findings
                            if finding.status in {
                                "verified", "withdrawn", "accepted-as-is",
                                "deferred-verified", "human-waived",
                            }
                        }),
                        "workflow_id": identity.workflow_id,
                        "attempt_id": identity.attempt_id,
                        "task_id": identity.task_id,
                        "reviewer_id": request.actor_id,
                        "expected_ledger_revision": request.expected_ledger_revision,
                        "review_event_id": review_event_id,
                        "review_start_revision": review_start_revision,
                    }
                operations.append((
                    action, decision_payload, "reviewer", request.actor_id
                ))
                return operations, effective_lease_id

            _, projection = mutate_ledger_transaction(
                request.task_id,
                build,
                base_dir=str(self.repository_root),
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
            from datetime import datetime, timezone

            from review_ledger.cli import (
                build_start_review_operations,
                mutate_ledger_transaction,
            )
            from review_ledger.lease import is_lease_active

            def build(projection):
                operations = []
                effective_lease_id = lease_id or None
                if projection.active_lease is not None and not is_lease_active(
                    projection.active_lease, datetime.now(timezone.utc)
                ):
                    operations, effective_lease_id = build_start_review_operations(
                        projection,
                        actor_id,
                        requested_lease_id=lease_id or None,
                        actor_role="worker",
                    )
                operations.append(
                    ("implementation-in-progress", {}, "worker", actor_id)
                )
                return operations, effective_lease_id

            _, projection = mutate_ledger_transaction(
                task_id,
                build,
                base_dir=str(self.repository_root),
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
