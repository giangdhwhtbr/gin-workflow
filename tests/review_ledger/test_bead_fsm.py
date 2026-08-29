import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../plugins/gin-workflow/src/scripts')))

from review_ledger.bead_fsm import validate_bead_transition, InvalidTransitionError

class TestBeadFSM(unittest.TestCase):
    def test_valid_transitions(self):
        # worker completes implementation
        validate_bead_transition("implementation-in-progress", "implementation-complete", "worker")
        # reviewer starts review
        validate_bead_transition("review-requested", "review-in-progress", "reviewer")
        # verifier passes verification
        validate_bead_transition("review-approved", "verification-in-progress", "verifier")

    def test_invalid_transition_paths(self):
        # Direct implementation-in-progress to review-approved is invalid
        with self.assertRaises(InvalidTransitionError):
            validate_bead_transition("implementation-in-progress", "review-approved", "reviewer")

    def test_actor_restrictions(self):
        # reviewer cannot complete implementation
        with self.assertRaises(InvalidTransitionError):
            validate_bead_transition("implementation-in-progress", "implementation-complete", "reviewer")
        # worker cannot approve review
        with self.assertRaises(InvalidTransitionError):
            validate_bead_transition("review-in-progress", "review-approved", "worker")

    def test_review_approval_finding_checks(self):
        # Non-terminal finding blocks approval
        with self.assertRaises(InvalidTransitionError):
            validate_bead_transition(
                "review-in-progress",
                "review-approved",
                "reviewer",
                finding_statuses=["verified", "open"]
            )
            
        # All terminal findings allow approval
        validate_bead_transition(
            "review-in-progress",
            "review-approved",
            "reviewer",
            finding_statuses=["verified", "withdrawn", "accepted-as-is"]
        )

    def test_review_rejection_transition(self):
        # reviewer can reject/invalidate approval
        validate_bead_transition("review-approved", "implementation-in-progress", "reviewer")
        # worker cannot reject/invalidate approval
        with self.assertRaises(InvalidTransitionError):
            validate_bead_transition("review-approved", "implementation-in-progress", "worker")

    def test_worker_can_withdraw_work_already_submitted_for_review(self):
        """A worker who spots a defect after requesting review must be able to
        pull the work back instead of waiting for a reviewer to reject it."""
        validate_bead_transition("review-requested", "implementation-in-progress", "worker")
        # Only the worker owns the implementation, so nobody else may withdraw it.
        with self.assertRaises(InvalidTransitionError):
            validate_bead_transition("review-requested", "implementation-in-progress", "reviewer")

    def test_reviewer_can_hand_a_review_back_without_recording_a_finding(self):
        """Not every abandoned review has a finding to record; the reviewer must
        be able to return the bead to the queue."""
        validate_bead_transition("review-in-progress", "review-requested", "reviewer")
        with self.assertRaises(InvalidTransitionError):
            validate_bead_transition("review-in-progress", "review-requested", "worker")

if __name__ == "__main__":

    unittest.main()
