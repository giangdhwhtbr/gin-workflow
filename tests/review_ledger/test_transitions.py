import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../plugins/gin-workflow/src/scripts')))

from review_ledger.transitions import generate_transition_id, reconcile_transition_states
from review_ledger.events import WorkflowIntegrityError

class TestTransitions(unittest.TestCase):
    def test_transition_id_generation(self):
        tid = generate_transition_id()
        self.assertTrue(tid.startswith("CRT-"))
        self.assertEqual(len(tid), 12)

    def test_reconcile_aligned_states(self):
        # implementation-in-progress maps to in_progress
        self.assertEqual(reconcile_transition_states("in_progress", "implementation-in-progress", None), "ok")
        # closed maps to closed
        self.assertEqual(reconcile_transition_states("closed", "closed", None), "ok")

    def test_reconcile_ledger_ahead_beads_behind(self):
        pending = {"transition_id": "CRT-123456", "from": "review-in-progress", "to": "changes-requested"}
        # review-in-progress maps to in_progress, changes-requested also maps to in_progress.
        # Let's test a case where the mapping transitions:
        # e.g., implementation-in-progress -> implementation-complete.
        # implementation-in-progress is in_progress. implementation-complete can be open.
        pending_complete = {"transition_id": "CRT-ABCDEF", "from": "ready-to-ship", "to": "closed"}
        # Beads is open, ledger is closed
        res = reconcile_transition_states("open", "closed", pending_complete)
        self.assertEqual(res, "replay_bead")

    def test_reconcile_beads_ahead_ledger_missing(self):
        # Beads closed, but ledger in implementation-in-progress with no pending transition
        with self.assertRaises(WorkflowIntegrityError):
            reconcile_transition_states("closed", "implementation-in-progress", None)

    def test_reconcile_unrecognized_mismatch(self):
        # Beads is in_progress, ledger is closed, no pending transition
        with self.assertRaises(WorkflowIntegrityError):
            reconcile_transition_states("in_progress", "closed", None)

    def test_reconcile_beads_ahead_replays_onto_the_ledger(self):
        """Beads recorded the shipping close but the ledger never saw the
        completion event. The pending transition matches in reverse, so the
        ledger is the lagging side and can be replayed forward."""
        pending = {"transition_id": "CRT-BEEF01", "from": "ready-to-ship", "to": "closed"}
        res = reconcile_transition_states("closed", "ready-to-ship", pending)
        self.assertEqual(res, "replay_ledger")

    def test_reconcile_prefers_replay_bead_when_both_directions_match(self):
        """Existing callers must keep seeing replay_bead for the ledger-ahead
        case, so the new outcome may never take precedence over it."""
        pending = {"transition_id": "CRT-BEEF02", "from": "ready-to-ship", "to": "closed"}
        self.assertEqual(
            reconcile_transition_states("open", "closed", pending), "replay_bead"
        )

    def test_reconcile_beads_ahead_without_a_pending_transition_still_raises(self):
        pending = {"transition_id": "CRT-BEEF03", "from": "review-requested", "to": "review-in-progress"}
        with self.assertRaises(WorkflowIntegrityError):
            reconcile_transition_states("closed", "ready-to-ship", pending)

    def test_integrity_error_names_a_concrete_remedy(self):
        with self.assertRaises(WorkflowIntegrityError) as caught:
            reconcile_transition_states("closed", "implementation-in-progress", None)
        message = str(caught.exception)
        self.assertIn("replay", message)
        self.assertIn("resync-lease", message)

if __name__ == "__main__":

    unittest.main()
