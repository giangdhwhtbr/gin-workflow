"""Evidence-authority checks on the review ledger's identity records.

The two tests live here because `CompositeEvidenceAuthority` belongs to the worker library. They are the
verbatim methods of `tests/review_ledger/test_acceptance_identity.py`, run through subclasses of its classes.
"""

import importlib.util
import unittest

from tests.gin_orchestrator import paths
from gin_orchestrator.evidence import CompositeEvidenceAuthority

_SOURCE = paths.ROOT / "tests/review_ledger/test_acceptance_identity.py"
_spec = importlib.util.spec_from_file_location("gin_orchestrator_tests.ledger_acceptance_identity", _SOURCE)
if _spec is None or _spec.loader is None:
    raise ImportError(f"cannot load test module: {_SOURCE}")
_base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_base)

complete_repository = _base.complete_repository
get_checkpoint_identity_record = _base.get_checkpoint_identity_record
get_review_identity_record = _base.get_review_identity_record
mutate_ledger = _base.mutate_ledger


class LedgerIdentityRecordEvidenceTests(_base.LedgerIdentityRecordTests):
    def test_records_feed_composite_evidence_authority_unchanged(self):
        repositories = [complete_repository()]
        self._prepare(repositories)
        checkpoint_event_id = self._checkpoint(repositories)
        self._reach_review_in_progress()
        review_event_id = self._approve(repositories)

        checkpoint_record = get_checkpoint_identity_record(
            self.bead_id, checkpoint_event_id, base_dir=self.test_dir
        )
        review_record = dict(
            get_review_identity_record(
                self.bead_id, review_event_id, base_dir=self.test_dir
            )
        )
        # verification_event_id is owned by the verification record store, not
        # the review ledger; the caller merges it in.
        review_record["verification_event_id"] = "VER-1"
        verification_record = {
            "task_id": review_record["task_id"],
            "verification_event_id": "VER-1",
            "review_event_id": review_event_id,
            "acceptance_identity": review_record["acceptance_identity"],
            "status": "passed",
            "recorded_at": "2026-08-27T00:00:00Z",
        }
        authority = CompositeEvidenceAuthority(
            worker_resolver=lambda reference: None,
            checkpoint_resolver=lambda reference: (
                checkpoint_record if reference == checkpoint_event_id else None
            ),
            review_resolver=lambda reference: (
                review_record if reference == review_event_id else None
            ),
            verification_resolver=lambda reference: (
                verification_record if reference == "VER-1" else None
            ),
        )
        checkpoint_evidence = authority._checkpoint(checkpoint_event_id)
        self.assertEqual("recorded", checkpoint_evidence["outcome"])
        self.assertEqual(
            checkpoint_record["acceptance_identity"],
            checkpoint_evidence["acceptance_identity"],
        )
        review_evidence = authority._review(review_event_id)
        self.assertEqual("approved", review_evidence["outcome"])
        self.assertEqual(
            review_record["ledger_revision"],
            review_evidence["details"]["ledger_revision"],
        )


class ReviewLedgerCommandEvidenceTests(_base.ReviewLedgerCommandIdentityTests):
    def test_refresh_cycle_inherits_identity_and_feeds_evidence_authority(self):
        self._cli(
            *self._checkpoint_args("--workflow-id", "wf-9", "--attempt-id", "at-9")
        )
        initial_checkpoint_event = self._last_event()
        initial_checkpoint_record = get_checkpoint_identity_record(
            self.bead_id, initial_checkpoint_event.event_id, base_dir=self.test_dir
        )

        self._reach_review_in_progress()
        mutate_ledger(
            self.bead_id,
            "finding-created",
            {"finding_id": "F-001", "severity": "IMPORTANT"},
            "reviewer",
            "reviewer-1",
            base_dir=self.test_dir,
        )
        mutate_ledger(
            self.bead_id,
            "changes-requested",
            {},
            "reviewer",
            "reviewer-1",
            base_dir=self.test_dir,
        )
        mutate_ledger(
            self.bead_id,
            "implementation-in-progress",
            {},
            "worker",
            "worker-1",
            base_dir=self.test_dir,
        )

        self._cli(*self._checkpoint_args())
        checkpoint_event = self._last_event()
        checkpoint_record = get_checkpoint_identity_record(
            self.bead_id, checkpoint_event.event_id, base_dir=self.test_dir
        )
        self.assertIsNotNone(checkpoint_record)
        self.assertEqual("wf-9", checkpoint_event.payload["workflow_id"])
        self.assertEqual("at-9", checkpoint_event.payload["attempt_id"])
        initial_snapshot = initial_checkpoint_record["acceptance_identity"][
            "repositories"
        ][0]
        refreshed_snapshot = checkpoint_record["acceptance_identity"][
            "repositories"
        ][0]
        self.assertNotEqual(
            initial_snapshot["checkpoint_sha"], refreshed_snapshot["checkpoint_sha"]
        )
        self.assertNotEqual(
            initial_snapshot["source_tree_hash"], refreshed_snapshot["source_tree_hash"]
        )

        for action, role, actor in (
            ("finding-fixed", "worker", "worker-1"),
            ("implementation-complete", "worker", "worker-1"),
            ("review-requested", "worker", "worker-1"),
            ("review-started", "reviewer", "reviewer-1"),
            ("finding-verified", "reviewer", "reviewer-1"),
        ):
            payload = {"finding_id": "F-001"} if action.startswith("finding-") else {}
            mutate_ledger(
                self.bead_id,
                action,
                payload,
                role,
                actor,
                base_dir=self.test_dir,
            )
        self._cli(
            "approve", "--bead-id", self.bead_id, "--actor-id", "reviewer-1"
        )
        review_event = self._last_event()
        review_record = get_review_identity_record(
            self.bead_id, review_event.event_id, base_dir=self.test_dir
        )
        self.assertIsNotNone(review_record)
        review_record = dict(review_record)
        review_record["verification_event_id"] = "VER-refresh"
        verification_record = {
            "task_id": self.bead_id,
            "verification_event_id": "VER-refresh",
            "review_event_id": review_event.event_id,
            "acceptance_identity": review_record["acceptance_identity"],
            "status": "passed",
            "recorded_at": "2026-09-01T00:00:00Z",
        }
        authority = CompositeEvidenceAuthority(
            worker_resolver=lambda reference: None,
            checkpoint_resolver=lambda reference: (
                checkpoint_record
                if reference == checkpoint_event.event_id
                else None
            ),
            review_resolver=lambda reference: (
                review_record if reference == review_event.event_id else None
            ),
            verification_resolver=lambda reference: (
                verification_record if reference == "VER-refresh" else None
            ),
        )
        self.assertEqual(
            "recorded", authority._checkpoint(checkpoint_event.event_id)["outcome"]
        )
        self.assertEqual(
            "approved", authority._review(review_event.event_id)["outcome"]
        )


# The inherited tests already run in the base module; only the two above run here.
for _cls in (LedgerIdentityRecordEvidenceTests, ReviewLedgerCommandEvidenceTests):
    for _name in dir(_cls):
        if _name.startswith("test_") and _name not in vars(_cls):
            setattr(_cls, _name, None)
del _cls, _name  # a leaked class variable would be collected a second time


if __name__ == "__main__":
    unittest.main()
