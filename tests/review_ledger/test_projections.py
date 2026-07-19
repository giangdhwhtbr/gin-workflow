import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../plugins/gin-workflow/src/scripts')))

from review_ledger.events import LedgerEvent
from review_ledger.projections import ReviewProjection
from review_ledger.schema import EventActions

class TestProjections(unittest.TestCase):
    def setUp(self):
        self.actor = {"role": "reviewer", "actor_id": "rev-1"}

    def test_projection_replay(self):
        events = [
            LedgerEvent(
                event_id="EV-000001",
                action=EventActions.LEDGER_CREATED,
                timestamp="2026-07-18T17:30:00Z",
                actor=self.actor,
                payload={"repositories": [{"id": "repo1"}]},
                previous_event_hash=None
            ),
            LedgerEvent(
                event_id="EV-000002",
                action=EventActions.LEASE_ACQUIRED,
                timestamp="2026-07-18T17:31:00Z",
                actor=self.actor,
                payload={
                    "lease_id": "lease-abc",
                    "actor_role": "reviewer",
                    "actor_id": "rev-1",
                    "acquired_at": "2026-07-18T17:31:00Z",
                    "expires_at": "2026-07-18T17:41:00Z"
                },
                previous_event_hash="hash1"
            ),
            LedgerEvent(
                event_id="EV-000003",
                action=EventActions.FINDING_CREATED,
                timestamp="2026-07-18T17:32:00Z",
                actor=self.actor,
                payload={"finding_id": "F-001", "severity": "CRITICAL"},
                previous_event_hash="hash2"
            )
        ]
        
        proj = ReviewProjection.replay(events)
        self.assertEqual(proj.review_state, "implementation-in-progress")
        self.assertEqual(len(proj.repositories), 1)
        self.assertEqual(proj.repositories[0]["id"], "repo1")
        self.assertIsNotNone(proj.active_lease)
        self.assertEqual(proj.active_lease.lease_id, "lease-abc")
        self.assertIn("F-001", proj.findings)
        self.assertEqual(proj.findings["F-001"].severity, "CRITICAL")
        self.assertEqual(proj.findings["F-001"].status, "open")
        self.assertEqual(proj.next_finding_number, 2)

    def test_lease_release_and_approval(self):
        events = [
            LedgerEvent(
                event_id="EV-000001",
                action=EventActions.LEASE_ACQUIRED,
                timestamp="2026-07-18T17:31:00Z",
                actor=self.actor,
                payload={
                    "lease_id": "lease-abc",
                    "actor_role": "reviewer",
                    "actor_id": "rev-1",
                    "acquired_at": "2026-07-18T17:31:00Z",
                    "expires_at": "2026-07-18T17:41:00Z"
                },
                previous_event_hash=None
            ),
            LedgerEvent(
                event_id="EV-000002",
                action=EventActions.LEASE_RELEASED,
                timestamp="2026-07-18T17:32:00Z",
                actor=self.actor,
                payload={},
                previous_event_hash="hash1"
            ),
            LedgerEvent(
                event_id="EV-000003",
                action=EventActions.REVIEW_APPROVED,
                timestamp="2026-07-18T17:33:00Z",
                actor=self.actor,
                payload={
                    "approved_repositories": [],
                    "source_scope_hash": "scopehash",
                    "terminal_findings": []
                },
                previous_event_hash="hash2"
            )
        ]
        proj = ReviewProjection.replay(events)
        self.assertIsNone(proj.active_lease)
        self.assertEqual(proj.review_state, "review-approved")
        self.assertIsNotNone(proj.active_approval)
        self.assertEqual(proj.active_approval.source_scope_hash, "scopehash")

    def test_duplicate_finding_id_rejected(self):
        from review_ledger.events import WorkflowIntegrityError
        events = [
            LedgerEvent(
                event_id="EV-000001",
                action=EventActions.FINDING_CREATED,
                timestamp="2026-07-18T17:32:00Z",
                actor=self.actor,
                payload={"finding_id": "F-001", "severity": "CRITICAL"},
                previous_event_hash=None
            ),
            LedgerEvent(
                event_id="EV-000002",
                action=EventActions.FINDING_CREATED,
                timestamp="2026-07-18T17:33:00Z",
                actor=self.actor,
                payload={"finding_id": "F-001", "severity": "MINOR"},
                previous_event_hash="hash1"
            )
        ]
        with self.assertRaises(WorkflowIntegrityError):
            ReviewProjection.replay(events)

    def test_review_approval_invalidation_resets_state(self):
        events = [
            LedgerEvent(
                event_id="EV-000001",
                action=EventActions.REVIEW_APPROVED,
                timestamp="2026-07-18T17:33:00Z",
                actor=self.actor,
                payload={
                    "approved_repositories": [],
                    "source_scope_hash": "scopehash",
                    "terminal_findings": []
                },
                previous_event_hash=None
            ),
            LedgerEvent(
                event_id="EV-000002",
                action=EventActions.REVIEW_APPROVAL_INVALIDATED,
                timestamp="2026-07-18T17:34:00Z",
                actor=self.actor,
                payload={"reason": "incorrect changes"},
                previous_event_hash="hash2"
            )
        ]
        proj = ReviewProjection.replay(events)
        self.assertIsNone(proj.active_approval)
        self.assertEqual(proj.review_state, "implementation-in-progress")

if __name__ == "__main__":
    unittest.main()
