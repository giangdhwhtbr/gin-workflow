import unittest
import sys
import os
import tempfile
import shutil

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../plugins/gin-workflow/src/scripts')))

from review_ledger.cli import mutate_ledger, load_ledger, get_ledger_paths
from review_ledger.events import WorkflowIntegrityError

class TestCLI(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_cli_ledger_lifecycle(self):
        bead_id = "bead-abc"
        
        # 1. Init ledger
        payload = {
            "repositories": [{
                "repository_id": "primary",
                "role": "primary",
                "review_ref": "ref",
                "review_base_sha": "sha1",
                "reviewed_source_sha": "sha2"
            }]
        }
        mutate_ledger(bead_id, "ledger-created", payload, "worker", "w1", base_dir=self.test_dir)
        
        # 2. Complete implementation and request review
        mutate_ledger(bead_id, "implementation-complete", {}, "worker", "w1", base_dir=self.test_dir)
        mutate_ledger(bead_id, "review-requested", {}, "worker", "w1", base_dir=self.test_dir)
        
        # 3. Start review
        mutate_ledger(bead_id, "review-started", {}, "reviewer", "rev1", base_dir=self.test_dir)
        
        # 3. Add finding
        payload_finding = {"finding_id": "F-001", "severity": "CRITICAL"}
        mutate_ledger(bead_id, "finding-created", payload_finding, "reviewer", "rev1", base_dir=self.test_dir)
        
        # Verify status
        log, proj = load_ledger(bead_id, base_dir=self.test_dir)
        self.assertEqual(proj.review_state, "review-in-progress")
        self.assertIn("F-001", proj.findings)
        self.assertEqual(proj.findings["F-001"].status, "open")
        
        # 4. Mark finding fixed
        mutate_ledger(bead_id, "finding-fixed", {"finding_id": "F-001"}, "worker", "w1", base_dir=self.test_dir)
        
        log, proj = load_ledger(bead_id, base_dir=self.test_dir)
        self.assertEqual(proj.findings["F-001"].status, "fixed-awaiting-verification")

if __name__ == "__main__":
    unittest.main()
