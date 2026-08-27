import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../plugins/gin-workflow/src/scripts')))

from review_ledger.schema import EventActions

class TestSchema(unittest.TestCase):
    def test_schema_actions_defined(self):
        self.assertEqual(len(EventActions.ALL_ACTIONS), 34)
        self.assertIn("ledger-created", EventActions.ALL_ACTIONS)
        self.assertIn("review-approved", EventActions.ALL_ACTIONS)
        # An action is only reachable if it is registered here; finding-reopened
        # was the missing half of a transition finding_fsm already allowed.
        self.assertIn("finding-reopened", EventActions.ALL_ACTIONS)
        self.assertIn("review-scope-change-requested", EventActions.ALL_ACTIONS)

if __name__ == "__main__":
    unittest.main()
