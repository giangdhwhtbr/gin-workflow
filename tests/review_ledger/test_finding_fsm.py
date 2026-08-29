import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../plugins/gin-workflow/src/scripts')))

from review_ledger.finding_fsm import validate_finding_transition, InvalidTransitionError, TERMINAL_STATUSES

class TestFindingFSM(unittest.TestCase):
    def test_valid_transitions(self):
        # worker fixes open finding
        validate_finding_transition("open", "fixed-awaiting-verification", "CRITICAL", "worker", 0)
        # reviewer verifies fixed finding
        validate_finding_transition("fixed-awaiting-verification", "verified", "CRITICAL", "reviewer", 0)
        # human waives decision required finding
        validate_finding_transition("human-decision-required", "human-waived", "CRITICAL", "human", 0)

    def test_invalid_transition_paths(self):
        # Open cannot go directly to verified
        with self.assertRaises(InvalidTransitionError):
            validate_finding_transition("open", "verified", "CRITICAL", "reviewer", 0)

    def test_actor_restrictions(self):
        # worker cannot verify a fix
        with self.assertRaises(InvalidTransitionError):
            validate_finding_transition("fixed-awaiting-verification", "verified", "CRITICAL", "worker", 0)
        # reviewer cannot waive a finding
        with self.assertRaises(InvalidTransitionError):
            validate_finding_transition("human-decision-required", "human-waived", "CRITICAL", "reviewer", 0)

    def test_critical_deferral_restriction(self):
        # Critical cannot be deferred
        with self.assertRaises(InvalidTransitionError):
            validate_finding_transition("open", "deferral-proposed", "CRITICAL", "worker", 0)

    def test_important_deferral_restriction(self):
        # Important cannot be deferred directly (needs human intervention)
        with self.assertRaises(InvalidTransitionError):
            validate_finding_transition("deferral-proposed", "deferred-verified", "IMPORTANT", "reviewer", 0)
            
        # Should allow transitioning Important to human-decision-required
        validate_finding_transition("deferral-proposed", "human-decision-required", "IMPORTANT", "reviewer", 0)

    def test_minor_deferral_shortcut(self):
        # Minor can be deferred directly
        validate_finding_transition("deferral-proposed", "deferred-verified", "MINOR", "reviewer", 0)

    def test_clarification_limit(self):
        # Disputed -> clarification-requested is allowed once
        validate_finding_transition("disputed", "clarification-requested", "CRITICAL", "reviewer", 0)
        
        # Second time is forbidden
        with self.assertRaises(InvalidTransitionError):
            validate_finding_transition("disputed", "clarification-requested", "CRITICAL", "reviewer", 1)

    def test_terminal_statuses(self):
        self.assertIn("verified", TERMINAL_STATUSES)
        self.assertIn("withdrawn", TERMINAL_STATUSES)
        self.assertIn("accepted-as-is", TERMINAL_STATUSES)
        self.assertIn("deferred-verified", TERMINAL_STATUSES)
        self.assertIn("human-waived", TERMINAL_STATUSES)

    def test_human_can_waive_an_open_finding_directly(self):
        """human-waived used to be reachable only from human-decision-required,
        so a human who had already decided had to stage a dispute first."""
        validate_finding_transition("open", "human-waived", "IMPORTANT", "human", 0)
        # Still a human-only decision.
        with self.assertRaises(InvalidTransitionError):
            validate_finding_transition("open", "human-waived", "IMPORTANT", "reviewer", 0)

    def test_waiving_an_open_finding_is_not_a_deferral_backdoor(self):
        """A waiver is a recorded human decision, not a deferral, so it stays
        available for CRITICAL findings while deferral remains forbidden."""
        validate_finding_transition("open", "human-waived", "CRITICAL", "human", 0)
        with self.assertRaises(InvalidTransitionError):
            validate_finding_transition("open", "deferral-proposed", "CRITICAL", "human", 0)

    def test_clarification_cap_is_a_parameter_with_the_previous_default(self):
        # Default is unchanged: one clarification.
        with self.assertRaises(InvalidTransitionError):
            validate_finding_transition("disputed", "clarification-requested", "CRITICAL", "reviewer", 1)
        # A caller that allows more rounds may raise the cap.
        validate_finding_transition(
            "disputed", "clarification-requested", "CRITICAL", "reviewer", 1,
            max_clarifications=2,
        )
        with self.assertRaises(InvalidTransitionError):
            validate_finding_transition(
                "disputed", "clarification-requested", "CRITICAL", "reviewer", 2,
                max_clarifications=2,
            )

if __name__ == "__main__":

    unittest.main()
