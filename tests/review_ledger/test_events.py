import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../plugins/gin-workflow/src/scripts')))

from review_ledger.events import LedgerEvent, EventLog, WorkflowIntegrityError

class TestEvents(unittest.TestCase):
    def setUp(self):
        self.actor = {"role": "reviewer", "actor_id": "rev-1"}
        
    def test_event_hash_computation(self):
        event = LedgerEvent(
            event_id="EV-000001",
            action="ledger-created",
            timestamp="2026-07-18T17:30:00Z",
            actor=self.actor,
            payload={"version": "1.0"},
            previous_event_hash=None
        )
        # Compute and verify
        h1 = event.compute_hash()
        self.assertIsNotNone(h1)
        event.event_hash = h1
        self.assertTrue(event.verify_hash())
        
        # Tampering with payload should change computed hash
        event.payload["version"] = "2.0"
        self.assertFalse(event.verify_hash())

    def test_event_log_append_and_replay(self):
        log = EventLog()
        
        e1 = LedgerEvent(
            event_id="EV-000001",
            action="ledger-created",
            timestamp="2026-07-18T17:30:00Z",
            actor=self.actor,
            payload={"version": "1.0"},
            previous_event_hash=None
        )
        log.append(e1)
        
        e2 = LedgerEvent(
            event_id="EV-000002",
            action="review-started",
            timestamp="2026-07-18T17:31:00Z",
            actor=self.actor,
            payload={},
            previous_event_hash=None # will be set during append
        )
        log.append(e2)
        
        self.assertEqual(e2.previous_event_hash, e1.event_hash)
        
        # Replay should succeed
        log.replay_and_validate()
        
    def test_event_log_duplicate_id(self):
        log = EventLog()
        e1 = LedgerEvent(
            event_id="EV-000001",
            action="ledger-created",
            timestamp="2026-07-18T17:30:00Z",
            actor=self.actor,
            payload={},
            previous_event_hash=None
        )
        log.append(e1)
        
        e2 = LedgerEvent(
            event_id="EV-000001", # Duplicate
            action="review-started",
            timestamp="2026-07-18T17:31:00Z",
            actor=self.actor,
            payload={},
            previous_event_hash=None
        )
        # Force append duplicate directly (bypass append hash assignment for failure test)
        log.events.append(e2)
        e2.event_hash = e2.compute_hash()
        
        with self.assertRaises(WorkflowIntegrityError):
            log.replay_and_validate()

    def test_event_log_broken_chain(self):
        log = EventLog()
        e1 = LedgerEvent(
            event_id="EV-000001",
            action="ledger-created",
            timestamp="2026-07-18T17:30:00Z",
            actor=self.actor,
            payload={},
            previous_event_hash=None
        )
        log.append(e1)
        
        e2 = LedgerEvent(
            event_id="EV-000002",
            action="review-started",
            timestamp="2026-07-18T17:31:00Z",
            actor=self.actor,
            payload={},
            previous_event_hash="wrong_hash" # broken link
        )
        e2.event_hash = e2.compute_hash()
        log.events.append(e2)
        
        with self.assertRaises(WorkflowIntegrityError):
            log.replay_and_validate()

    def test_event_log_decreasing_sequence(self):
        log = EventLog()
        e1 = LedgerEvent(
            event_id="EV-000002", # High sequence
            action="ledger-created",
            timestamp="2026-07-18T17:30:00Z",
            actor=self.actor,
            payload={},
            previous_event_hash=None
        )
        log.append(e1)
        
        e2 = LedgerEvent(
            event_id="EV-000001", # Low sequence
            action="review-started",
            timestamp="2026-07-18T17:31:00Z",
            actor=self.actor,
            payload={},
            previous_event_hash=e1.event_hash
        )
        e2.event_hash = e2.compute_hash()
        log.events.append(e2)
        
        with self.assertRaises(WorkflowIntegrityError):
            log.replay_and_validate()

    def test_event_log_first_event_null_previous(self):
        log = EventLog()
        e1 = LedgerEvent(
            event_id="EV-000001",
            action="ledger-created",
            timestamp="2026-07-18T17:30:00Z",
            actor=self.actor,
            payload={},
            previous_event_hash="not_null" # invalid first event link
        )
        e1.event_hash = e1.compute_hash()
        log.events.append(e1)
        
        with self.assertRaises(WorkflowIntegrityError):
            log.replay_and_validate()

if __name__ == "__main__":
    unittest.main()
