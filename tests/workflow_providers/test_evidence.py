from pathlib import Path
import json
import multiprocessing
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_providers.contracts import (  # noqa: E402
    EvidenceCategory,
    EvidenceQuery,
    EvidenceRecord,
    OperationStatus,
)
from workflow_providers.evidence import FileEvidenceProvider  # noqa: E402
from workflow_providers.fakes import FakeEvidenceProvider  # noqa: E402



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

    def test_completeness_requires_passing_tests_review_and_repository_evidence(self):
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
            self.assertTrue(complete.value.complete)
            self.assertEqual((), complete.value.missing_categories)

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
        self.assertEqual(("tests",), completeness.value.missing_categories)

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
