from pathlib import Path
from datetime import datetime, timedelta, timezone
import json
import multiprocessing
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core.identity import AcceptanceIdentity, RepositorySnapshot  # noqa: E402
from workflow_providers.contracts import (  # noqa: E402
    EvidenceCategory,
    EvidenceQuery,
    EvidenceRecord,
    OperationStatus,
)
from workflow_providers.evidence import FileEvidenceProvider  # noqa: E402
from workflow_providers.fakes import FakeEvidenceProvider  # noqa: E402


def acceptance_identity(
    *,
    attempt_id="attempt-1",
    scope_hash="scope-1",
    tree_hash="tree-1",
    checkpoint_sha="checkpoint-1",
):
    return AcceptanceIdentity(
        workflow_id="wf-1",
        attempt_id=attempt_id,
        task_id="task-1",
        repositories=(
            RepositorySnapshot(
                "primary",
                scope_hash,
                tree_hash,
                checkpoint_sha,
                "refs/gin/review/task-1",
            ),
        ),
    )


def current_record(evidence_id, category, outcome, recorded_at, *, identity=None):
    selected_identity = identity or acceptance_identity()
    if category is EvidenceCategory.TESTS:
        reference = "worker-1"
        details = {
            "schema_version": "2.3",
            "worker_id": reference,
            "worker_result_schema_version": "2.3",
            "tests": [
                {
                    "argv": ["python3", "-m", "unittest"],
                    "exit_code": 0,
                    "started_at": "2026-08-20T09:58:00Z",
                    "finished_at": "2026-08-20T09:59:00Z",
                    "workspace_id": "ws-task-1",
                    "repository_id": selected_identity.repositories[0].repository_id,
                    "attempt_id": selected_identity.attempt_id,
                    "source_tree_hash": selected_identity.repositories[0].source_tree_hash,
                }
            ],
        }
    elif category is EvidenceCategory.REPOSITORY:
        reference = "checkpoint-event-1"
        details = {
            "schema_version": "2.3",
            "checkpoint_event_id": reference,
            "repositories": selected_identity.to_dict()["repositories"],
        }
    else:
        reference = "review-event-1"
        verification = datetime.fromisoformat(recorded_at.replace("Z", "+00:00"))
        details = {
            "schema_version": "2.3",
            "review_event_id": reference,
            "ledger_revision": 7,
            "approval_recorded_at": (verification - timedelta(seconds=30)).astimezone(
                timezone.utc
            ).isoformat().replace("+00:00", "Z"),
            "verification_event_id": "verification-event-1",
            "verification_recorded_at": recorded_at,
        }
    return EvidenceRecord(
        evidence_id=evidence_id,
        task_id="task-1",
        category=category,
        outcome=outcome,
        reference=reference,
        details=details,
        acceptance_identity=selected_identity,
        recorded_at=recorded_at,
    )


def authority_payload(record):
    return {
        "task_id": record.task_id,
        "category": record.category.value,
        "outcome": record.outcome,
        "reference": record.reference,
        "details": dict(record.details),
        "acceptance_identity": record.acceptance_identity.to_dict(),
        "recorded_at": record.recorded_at,
    }


class StaticEvidenceAuthority:
    def __init__(self, records):
        self._records = {
            (record.category, record.reference): authority_payload(record)
            for record in records
        }

    def resolve(self, category, reference):
        return self._records.get((category, reference))



def _record_from_process(index_path, evidence_id, start, outcomes):
    start.wait()
    result = FileEvidenceProvider(Path(index_path)).record(
        EvidenceRecord(
            evidence_id=evidence_id,
            task_id="task-concurrent",
            category=EvidenceCategory.TESTS,
            outcome="passed",
            reference=evidence_id,
        ),
        idempotency_key=evidence_id,
    )
    outcomes.put(result.status.value)


class EvidenceProviderTests(unittest.TestCase):
    def test_idempotent_replay_revalidates_current_authority(self):
        record = current_record(
            "test-current",
            EvidenceCategory.TESTS,
            "passed",
            "2026-08-20T10:00:00Z",
        )
        for provider_kind in ("filesystem", "fake"):
            with self.subTest(provider=provider_kind), tempfile.TemporaryDirectory() as directory:
                authority = StaticEvidenceAuthority((record,))
                provider = (
                    FileEvidenceProvider(
                        Path(directory) / "evidence.json",
                        authority=authority,
                    )
                    if provider_kind == "filesystem"
                    else FakeEvidenceProvider(authority=authority)
                )
                first = provider.record(record, idempotency_key="same")
                authority._records.clear()

                replay = provider.record(record, idempotency_key="same")

                self.assertIs(OperationStatus.SUCCESS, first.status)
                self.assertIs(OperationStatus.INVALID, replay.status)
                self.assertIn("not resolvable", replay.message)

    def test_successful_identity_bound_evidence_requires_authoritative_resolution(self):
        record = current_record(
            "test-current",
            EvidenceCategory.TESTS,
            "passed",
            "2026-08-20T10:00:00Z",
        )
        with tempfile.TemporaryDirectory() as directory:
            provider = FileEvidenceProvider(Path(directory) / "evidence.json")

            result = provider.record(record, idempotency_key=record.evidence_id)

        self.assertIs(OperationStatus.INVALID, result.status)
        self.assertIn("authoritative evidence resolver", result.message)

    def test_authority_rejects_self_asserted_workspace_or_event_provenance(self):
        canonical = current_record(
            "test-current",
            EvidenceCategory.TESTS,
            "passed",
            "2026-08-20T10:00:00Z",
        )
        claimed = EvidenceRecord(
            **{
                **canonical.__dict__,
                "details": {
                    **canonical.details,
                    "tests": [
                        {
                            **canonical.details["tests"][0],
                            "workspace_id": "ws-another",
                        }
                    ],
                },
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            provider = FileEvidenceProvider(
                Path(directory) / "evidence.json",
                authority=StaticEvidenceAuthority((canonical,)),
            )

            result = provider.record(claimed, idempotency_key=claimed.evidence_id)

        self.assertIs(OperationStatus.INVALID, result.status)
        self.assertIn("does not match authoritative", result.message)

    def test_authority_rejects_unresolved_repository_checkpoint_event(self):
        canonical = current_record(
            "repo-current",
            EvidenceCategory.REPOSITORY,
            "recorded",
            "2026-08-20T10:01:00Z",
        )
        claimed = EvidenceRecord(
            **{
                **canonical.__dict__,
                "reference": "checkpoint-event-invented",
                "details": {
                    **canonical.details,
                    "checkpoint_event_id": "checkpoint-event-invented",
                },
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            result = FileEvidenceProvider(
                Path(directory) / "evidence.json",
                authority=StaticEvidenceAuthority((canonical,)),
            ).record(claimed, idempotency_key=claimed.evidence_id)

        self.assertIs(OperationStatus.INVALID, result.status)
        self.assertIn("not resolvable", result.message)

    def test_authority_rejects_review_revision_or_verification_event_drift(self):
        canonical = current_record(
            "review-current",
            EvidenceCategory.REVIEWS,
            "approved",
            "2026-08-20T10:02:00Z",
        )
        authority = StaticEvidenceAuthority((canonical,))
        for override in (
            {"ledger_revision": 8},
            {"verification_event_id": "verification-event-invented"},
        ):
            with self.subTest(override=override), tempfile.TemporaryDirectory() as directory:
                claimed = EvidenceRecord(
                    **{
                        **canonical.__dict__,
                        "details": {**canonical.details, **override},
                    }
                )
                result = FileEvidenceProvider(
                    Path(directory) / "evidence.json",
                    authority=authority,
                ).record(claimed, idempotency_key=claimed.evidence_id)

                self.assertIs(OperationStatus.INVALID, result.status)
                self.assertIn("does not match authoritative", result.message)

    def test_persisted_identity_bound_records_are_revalidated_against_authority(self):
        record = current_record(
            "test-current",
            EvidenceCategory.TESTS,
            "passed",
            "2026-08-20T10:00:00Z",
        )
        with tempfile.TemporaryDirectory() as directory:
            index = Path(directory) / "evidence.json"
            provider = FileEvidenceProvider(
                index,
                authority=StaticEvidenceAuthority((record,)),
            )
            self.assertIs(
                OperationStatus.SUCCESS,
                provider.record(record, idempotency_key=record.evidence_id).status,
            )
            persisted = json.loads(index.read_text(encoding="utf-8"))
            persisted["records"][0]["details"]["tests"][0]["workspace_id"] = "ws-corrupt"
            index.write_text(json.dumps(persisted), encoding="utf-8")

            replay = provider.record(record, idempotency_key=record.evidence_id)
            queried = provider.query(EvidenceQuery(task_id="task-1"))
            completeness = provider.completeness("task-1", acceptance_identity())

        self.assertIs(OperationStatus.UNAVAILABLE, replay.status)
        self.assertIs(OperationStatus.UNAVAILABLE, queried.status)
        self.assertIn("authoritative", queried.message)
        self.assertIs(OperationStatus.UNAVAILABLE, completeness.status)

    def test_identity_bound_evidence_rejects_missing_or_false_provenance(self):
        base = current_record(
            "test-current",
            EvidenceCategory.TESTS,
            "passed",
            "2026-08-20T10:00:00Z",
        )
        cases = (
            ("category provenance", EvidenceRecord(**{**base.__dict__, "details": {}})),
            (
                "exit successfully",
                EvidenceRecord(
                    **{
                        **base.__dict__,
                        "details": {
                            **base.details,
                            "tests": [{**base.details["tests"][0], "exit_code": 1}],
                        },
                    }
                ),
            ),
            (
                "reference",
                EvidenceRecord(**{**base.__dict__, "reference": "another-worker"}),
            ),
        )
        for message, record in cases:
            with self.subTest(message=message), tempfile.TemporaryDirectory() as directory:
                result = FileEvidenceProvider(Path(directory) / "evidence.json").record(
                    record,
                    idempotency_key=record.evidence_id,
                )

                self.assertIs(OperationStatus.INVALID, result.status)
                self.assertIn(message, result.message)

    def test_review_provenance_requires_verification_after_terminal_approval(self):
        review = current_record(
            "review-current",
            EvidenceCategory.REVIEWS,
            "approved",
            "2026-08-20T10:02:00Z",
        )
        invalid = EvidenceRecord(
            **{
                **review.__dict__,
                "details": {
                    **review.details,
                    "verification_recorded_at": review.details["approval_recorded_at"],
                },
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            result = FileEvidenceProvider(Path(directory) / "evidence.json").record(
                invalid,
                idempotency_key=invalid.evidence_id,
            )

        self.assertIs(OperationStatus.INVALID, result.status)
        self.assertIn("after terminal approval", result.message)

    def test_records_and_queries_the_configured_index(self):
        with tempfile.TemporaryDirectory() as directory:
            index = Path(directory) / "configured/evidence.json"
            provider = FileEvidenceProvider(index)
            record = EvidenceRecord(
                evidence_id="test-1",
                task_id="task-1",
                category=EvidenceCategory.TESTS,
                outcome="passed",
                reference="python -m unittest",
            )

            result = provider.record(record, idempotency_key="record-1")
            queried = provider.query(EvidenceQuery(task_id="task-1"))

            self.assertIs(OperationStatus.SUCCESS, result.status)
            self.assertEqual([record], list(queried.value))
            self.assertTrue(index.is_file())
            self.assertEqual("test-1", json.loads(index.read_text())["records"][0]["evidence_id"])

    def test_record_is_idempotent_and_does_not_duplicate_index_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            provider = FileEvidenceProvider(Path(directory) / "evidence.json")
            record = EvidenceRecord(
                evidence_id="review-1",
                task_id="task-1",
                category=EvidenceCategory.REVIEWS,
                outcome="approved",
                reference=".planning/task-1/review.json",
            )

            first = provider.record(record, idempotency_key="same")
            replay = provider.record(record, idempotency_key="same")
            queried = provider.query(EvidenceQuery(task_id="task-1"))

            self.assertFalse(first.idempotent)
            self.assertTrue(replay.idempotent)
            self.assertEqual(1, len(queried.value))

    def test_legacy_evidence_remains_queryable_but_cannot_satisfy_completeness(self):
        with tempfile.TemporaryDirectory() as directory:
            provider = FileEvidenceProvider(Path(directory) / "evidence.json")
            fixtures = (
                ("test", EvidenceCategory.TESTS, "passed"),
                ("review", EvidenceCategory.REVIEWS, "approved"),
                ("repo", EvidenceCategory.REPOSITORY, "recorded"),
            )

            initial = provider.completeness("task-1")
            for evidence_id, category, outcome in fixtures:
                provider.record(
                    EvidenceRecord(
                        evidence_id=evidence_id,
                        task_id="task-1",
                        category=category,
                        outcome=outcome,
                        reference=evidence_id,
                    ),
                    idempotency_key=evidence_id,
                )
            complete = provider.completeness("task-1")

            self.assertFalse(initial.value.complete)
            self.assertEqual(
                {"tests", "reviews", "repository"}, set(initial.value.missing_categories)
            )
            self.assertFalse(complete.value.complete)
            self.assertEqual(
                {"tests", "reviews", "repository"}, set(complete.value.missing_categories)
            )
            self.assertEqual(3, len(provider.query(EvidenceQuery(task_id="task-1")).value))

    def test_identity_bound_completeness_selects_one_ordered_coherent_set(self):
        with tempfile.TemporaryDirectory() as directory:
            index = Path(directory) / "evidence.json"
            records = (
                current_record(
                    "test-current",
                    EvidenceCategory.TESTS,
                    "passed",
                    "2026-08-20T10:00:00Z",
                ),
                current_record(
                    "repo-current",
                    EvidenceCategory.REPOSITORY,
                    "recorded",
                    "2026-08-20T10:01:00Z",
                ),
                current_record(
                    "review-current",
                    EvidenceCategory.REVIEWS,
                    "approved",
                    "2026-08-20T10:02:00Z",
                ),
            )
            provider = FileEvidenceProvider(
                index,
                authority=StaticEvidenceAuthority(records),
            )
            for record in records:
                provider.record(record, idempotency_key=record.evidence_id)

            complete = provider.completeness("task-1", acceptance_identity())
            queried = provider.query(
                EvidenceQuery(
                    task_id="task-1",
                    acceptance_identity=acceptance_identity(),
                )
            )

            self.assertTrue(complete.value.complete)
            self.assertEqual(records, complete.value.evidence)
            self.assertEqual(records, queried.value)
            persisted = json.loads(index.read_text(encoding="utf-8"))
            self.assertEqual("2.3", persisted["schema_version"])
            self.assertEqual(
                acceptance_identity().to_dict(),
                persisted["records"][0]["acceptance_identity"],
            )

    def test_successful_records_from_other_attempts_or_trees_never_combine(self):
        cases = (
            (
                "attempt",
                acceptance_identity(attempt_id="attempt-2"),
                acceptance_identity(),
            ),
            (
                "tree",
                acceptance_identity(tree_hash="tree-2"),
                acceptance_identity(),
            ),
            (
                "scope",
                acceptance_identity(scope_hash="scope-2"),
                acceptance_identity(),
            ),
        )
        for label, mismatched, selected in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                records = (
                    current_record(
                        "test-current",
                        EvidenceCategory.TESTS,
                        "passed",
                        "2026-08-20T10:00:00Z",
                        identity=selected,
                    ),
                    current_record(
                        "repo-mismatch",
                        EvidenceCategory.REPOSITORY,
                        "recorded",
                        "2026-08-20T10:01:00Z",
                        identity=mismatched,
                    ),
                    current_record(
                        "review-current",
                        EvidenceCategory.REVIEWS,
                        "approved",
                        "2026-08-20T10:02:00Z",
                        identity=selected,
                    ),
                )
                provider = FileEvidenceProvider(
                    Path(directory) / "evidence.json",
                    authority=StaticEvidenceAuthority(records),
                )
                for record in records:
                    provider.record(record, idempotency_key=record.evidence_id)

                incomplete = provider.completeness("task-1", selected)

                self.assertFalse(incomplete.value.complete)
                self.assertEqual(("repository",), incomplete.value.missing_categories)
                self.assertIn("identity", " ".join(incomplete.value.diagnostics))

    def test_identity_bound_completeness_rejects_invalid_event_order(self):
        with tempfile.TemporaryDirectory() as directory:
            records = (
                current_record(
                    "test-late",
                    EvidenceCategory.TESTS,
                    "passed",
                    "2026-08-20T10:02:00Z",
                ),
                current_record(
                    "repo-early",
                    EvidenceCategory.REPOSITORY,
                    "recorded",
                    "2026-08-20T10:01:00Z",
                ),
                current_record(
                    "review-last",
                    EvidenceCategory.REVIEWS,
                    "approved",
                    "2026-08-20T10:03:00Z",
                ),
            )
            provider = FileEvidenceProvider(
                Path(directory) / "evidence.json",
                authority=StaticEvidenceAuthority(records),
            )
            for record in records:
                provider.record(record, idempotency_key=record.evidence_id)

            incomplete = provider.completeness("task-1", acceptance_identity())

            self.assertFalse(incomplete.value.complete)
            self.assertIn("out of order", " ".join(incomplete.value.diagnostics))

    def test_completeness_fails_closed_for_non_success_and_cross_category_outcomes(self):
        rejected = (
            (EvidenceCategory.TESTS, "skipped"),
            (EvidenceCategory.TESTS, "not-run"),
            (EvidenceCategory.TESTS, "cancelled"),
            (EvidenceCategory.TESTS, "error"),
            (EvidenceCategory.TESTS, "arbitrary"),
            (EvidenceCategory.REVIEWS, "passed"),
            (EvidenceCategory.REPOSITORY, "approved"),
        )

        for category, outcome in rejected:
            with self.subTest(category=category.value, outcome=outcome):
                with tempfile.TemporaryDirectory() as directory:
                    provider = FileEvidenceProvider(Path(directory) / "evidence.json")
                    accepted = {
                        EvidenceCategory.TESTS: "passed",
                        EvidenceCategory.REVIEWS: "approved",
                        EvidenceCategory.REPOSITORY: "recorded",
                    }
                    accepted[category] = outcome
                    for current_category, current_outcome in accepted.items():
                        provider.record(
                            EvidenceRecord(
                                evidence_id=current_category.value,
                                task_id="task-1",
                                category=current_category,
                                outcome=current_outcome,
                                reference=current_category.value,
                            ),
                            idempotency_key=current_category.value,
                        )

                    completeness = provider.completeness("task-1")

                    self.assertFalse(completeness.value.complete)
                    self.assertIn(category.value, completeness.value.missing_categories)

    def test_concurrent_processes_record_without_lost_updates_or_temp_leaks(self):
        with tempfile.TemporaryDirectory() as directory:
            index = Path(directory) / "evidence.json"
            context = multiprocessing.get_context("fork")
            start = context.Event()
            outcomes = context.Queue()
            processes = [
                context.Process(
                    target=_record_from_process,
                    args=(str(index), f"evidence-{number}", start, outcomes),
                )
                for number in range(12)
            ]
            for process in processes:
                process.start()
            start.set()
            for process in processes:
                process.join(timeout=10)

            self.assertTrue(all(process.exitcode == 0 for process in processes))
            self.assertEqual(["success"] * 12, sorted(outcomes.get() for _ in processes))
            queried = FileEvidenceProvider(index).query(
                EvidenceQuery(task_id="task-concurrent")
            )
            self.assertEqual(12, len(queried.value))
            self.assertEqual([], list(index.parent.glob(f".{index.name}.*.tmp")))

    def test_fake_evidence_uses_the_same_fail_closed_completeness_contract(self):
        provider = FakeEvidenceProvider()
        fixtures = (
            ("test", EvidenceCategory.TESTS, "skipped"),
            ("review", EvidenceCategory.REVIEWS, "approved"),
            ("repo", EvidenceCategory.REPOSITORY, "recorded"),
        )
        for evidence_id, category, outcome in fixtures:
            provider.record(
                EvidenceRecord(
                    evidence_id=evidence_id,
                    task_id="task-1",
                    category=category,
                    outcome=outcome,
                    reference=evidence_id,
                ),
                idempotency_key=evidence_id,
            )

        completeness = provider.completeness("task-1")

        self.assertFalse(completeness.value.complete)
        self.assertEqual(
            {"tests", "reviews", "repository"}, set(completeness.value.missing_categories)
        )

    def test_invalid_record_and_corrupt_index_are_normalized(self):
        with tempfile.TemporaryDirectory() as directory:
            index = Path(directory) / "evidence.json"
            provider = FileEvidenceProvider(index)
            invalid = provider.record(
                EvidenceRecord(
                    evidence_id="",
                    task_id="task-1",
                    category=EvidenceCategory.TESTS,
                    outcome="passed",
                    reference="tests",
                ),
                idempotency_key="bad",
            )
            index.write_text("not json", encoding="utf-8")
            unavailable = provider.query(EvidenceQuery(task_id="task-1"))

            self.assertIs(OperationStatus.INVALID, invalid.status)
            self.assertIs(OperationStatus.UNAVAILABLE, unavailable.status)


if __name__ == "__main__":
    unittest.main()
