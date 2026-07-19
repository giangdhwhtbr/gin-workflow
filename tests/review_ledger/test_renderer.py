import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../plugins/gin-workflow/src/scripts')))

from review_ledger.projections import ReviewProjection
from review_ledger.events import EventLog, LedgerEvent
from review_ledger.renderer import render_review_markdown

class TestRenderer(unittest.TestCase):
    def test_rendering_output(self):
        proj = ReviewProjection()
        proj.review_state = "review-in-progress"
        proj.repositories = [{"repository_id": "primary", "role": "primary", "review_ref": "ref", "review_base_sha": "sha1", "reviewed_source_sha": "sha2"}]
        
        log = EventLog()
        e1 = LedgerEvent("EV-1", "ledger-created", "2026-07-18T17:30:00Z", {"role": "worker", "actor_id": "w1"}, {}, None)
        log.append(e1)
        
        # Re-derive projection
        proj = ReviewProjection.replay(log.events)
        
        md = render_review_markdown(proj, log)
        
        self.assertIn("# Code Review Ledger", md)
        self.assertIn("**Bead Status:** `implementation-in-progress`", md)
        self.assertIn("## Event Chronology", md)
        self.assertIn("EV-1", md)

if __name__ == "__main__":
    unittest.main()
