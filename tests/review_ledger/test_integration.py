import unittest
import sys
import os
import tempfile
import shutil
import subprocess
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../plugins/gin-workflow/src/scripts')))

from review_ledger.cli import mutate_ledger, load_ledger
from review_ledger.events import WorkflowIntegrityError
from review_ledger.git_adapter import create_source_checkpoint, push_review_ref
from review_ledger.projections import ReviewProjection

class TestIntegration(unittest.TestCase):
    def setUp(self):
        # Create temp dir for local repo
        self.test_dir = tempfile.mkdtemp()
        self.remote_dir = tempfile.mkdtemp()
        
        # Init remote bare repo
        subprocess.run(["git", "init", "--bare"], cwd=self.remote_dir, check=True)
        
        # Init local repo
        subprocess.run(["git", "init"], cwd=self.test_dir, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.test_dir, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.test_dir, check=True)
        subprocess.run(["git", "remote", "add", "origin", self.remote_dir], cwd=self.test_dir, check=True)

        # Write first file & commit
        os.makedirs(os.path.join(self.test_dir, "src"))
        self.src_file = os.path.join(self.test_dir, "src/main.py")
        with open(self.src_file, "w") as f:
            f.write("print('first pass')")
        subprocess.run(["git", "add", "src/main.py"], cwd=self.test_dir, check=True)
        subprocess.run(["git", "commit", "-m", "initial commit"], cwd=self.test_dir, check=True)
        subprocess.run(["git", "push", "origin", "master"], cwd=self.test_dir, check=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir)
        shutil.rmtree(self.remote_dir)

    def test_full_review_integration_flow(self):
        bead_id = "test-bead-999"
        
        # 1. Initialize Review Ledger
        init_payload = {
            "repositories": [{
                "repository_id": "primary",
                "role": "primary",
                "review_ref": f"bead/{bead_id}",
                "review_base_sha": "master",
                "reviewed_source_sha": "master"
            }],
            "source_scope": {
                "included_paths": ["src/"],
                "excluded_artifact_paths": []
            }
        }
        mutate_ledger(bead_id, "ledger-created", init_payload, "worker", "worker-1", base_dir=self.test_dir)
        
        # 2. Worker makes changes and creates checkpoint
        with open(self.src_file, "w") as f:
            f.write("print('second pass')")
            
        _, proj = load_ledger(bead_id, base_dir=self.test_dir)
        new_sha = create_source_checkpoint(self.test_dir, proj.source_scope, bead_id, "feat: update main")
        
        # Record checkpoint in ledger
        checkpoint_payload = {"repositories": proj.repositories}
        checkpoint_payload["repositories"][0]["reviewed_source_sha"] = new_sha
        mutate_ledger(bead_id, "source-checkpoint-created", checkpoint_payload, "worker", "worker-1", base_dir=self.test_dir)
        
        # Switch to implementation-complete
        mutate_ledger(bead_id, "implementation-complete", {}, "worker", "worker-1", base_dir=self.test_dir)
        mutate_ledger(bead_id, "review-requested", {}, "worker", "worker-1", base_dir=self.test_dir)
        
        # 3. Reviewer starts review
        mutate_ledger(bead_id, "review-started", {}, "reviewer", "reviewer-1", base_dir=self.test_dir)
        
        # 4. Reviewer adds a critical finding
        mutate_ledger(bead_id, "finding-created", {"finding_id": "F-001", "severity": "CRITICAL"}, "reviewer", "reviewer-1", base_dir=self.test_dir)
        # Reviewer requests changes
        mutate_ledger(bead_id, "changes-requested", {}, "reviewer", "reviewer-1", base_dir=self.test_dir)
        
        # 5. Worker fixes the finding
        mutate_ledger(bead_id, "implementation-in-progress", {}, "worker", "worker-1", base_dir=self.test_dir)
        with open(self.src_file, "w") as f:
            f.write("print('fixed pass')")
            
        # Checkpoint the fix
        fix_sha = create_source_checkpoint(self.test_dir, proj.source_scope, bead_id, "fix: resolve F-001")
        checkpoint_payload["repositories"][0]["reviewed_source_sha"] = fix_sha
        mutate_ledger(bead_id, "source-checkpoint-created", checkpoint_payload, "worker", "worker-1", base_dir=self.test_dir)
        
        # Mark finding fixed
        mutate_ledger(bead_id, "finding-fixed", {"finding_id": "F-001"}, "worker", "worker-1", base_dir=self.test_dir)
        
        # Complete implementation & Request re-review
        mutate_ledger(bead_id, "implementation-complete", {}, "worker", "worker-1", base_dir=self.test_dir)
        mutate_ledger(bead_id, "review-requested", {}, "worker", "worker-1", base_dir=self.test_dir)
        
        # 6. Reviewer verifies the fix and approves
        mutate_ledger(bead_id, "review-started", {}, "reviewer", "reviewer-1", base_dir=self.test_dir)
        mutate_ledger(bead_id, "finding-verified", {"finding_id": "F-001"}, "reviewer", "reviewer-1", base_dir=self.test_dir)
        
        # Approve review
        app_payload = {
            "approved_repositories": [{
                "repository_id": "primary",
                "review_base_sha": "master",
                "reviewed_source_sha": fix_sha,
                "reviewed_source_tree_hash": "treehash"
            }],
            "source_scope_hash": "scopehash",
            "terminal_findings": ["F-001"]
        }
        mutate_ledger(bead_id, "review-approved", app_payload, "reviewer", "reviewer-1", base_dir=self.test_dir)
        
        # Load and verify final status
        _, final_proj = load_ledger(bead_id, base_dir=self.test_dir)
        self.assertEqual(final_proj.review_state, "review-approved")
        self.assertEqual(final_proj.findings["F-001"].status, "verified")

if __name__ == "__main__":
    unittest.main()
