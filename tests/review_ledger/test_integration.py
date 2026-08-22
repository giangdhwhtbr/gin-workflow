import unittest
import sys
import os
import tempfile
import shutil
import subprocess
import json
from pathlib import Path
import multiprocessing

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../plugins/gin-workflow/src/scripts')))

from review_ledger.cli import mutate_ledger, load_ledger, start_review
from review_ledger.events import WorkflowIntegrityError
from review_ledger.git_adapter import create_source_checkpoint, push_review_ref
from review_ledger.projections import ReviewProjection

def _start_review_process(base_dir, queue, actor_id):
    try:
        _, projection = start_review(
            "concurrent-review", actor_id, base_dir=base_dir, ttl_seconds=600
        )
        queue.put(("ok", projection.active_lease.actor_id))
    except Exception as error:
        queue.put(("error", type(error).__name__))

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
        new_checkpoint = create_source_checkpoint(self.test_dir, proj.source_scope, bead_id, commit_msg="feat: update main")
        new_sha = new_checkpoint.checkpoint_sha
        
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
        fix_checkpoint = create_source_checkpoint(self.test_dir, proj.source_scope, bead_id, commit_msg="fix: resolve F-001")
        fix_sha = fix_checkpoint.checkpoint_sha
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


    def test_start_review_atomically_acquires_one_cross_process_owner(self):
        bead_id = "concurrent-review"
        mutate_ledger(bead_id, "ledger-created", {"repositories": []}, "worker", "worker-1", base_dir=self.test_dir)
        mutate_ledger(bead_id, "implementation-complete", {}, "worker", "worker-1", base_dir=self.test_dir)
        mutate_ledger(bead_id, "review-requested", {}, "worker", "worker-1", base_dir=self.test_dir)
        context = multiprocessing.get_context("spawn")
        queue = context.Queue()
        processes = [
            context.Process(target=_start_review_process, args=(self.test_dir, queue, actor_id))
            for actor_id in ("reviewer-a", "reviewer-b")
        ]
        for process in processes:
            process.start()
        for process in processes:
            process.join(10)
            self.assertEqual(0, process.exitcode)

        results = [queue.get(timeout=2) for _ in processes]
        self.assertEqual(1, sum(result[0] == "ok" for result in results))
        log, projection = load_ledger(bead_id, base_dir=self.test_dir)
        self.assertEqual("review-in-progress", projection.review_state)
        self.assertEqual(
            ["lease-acquired", "review-started"],
            [event.action for event in log.events[-2:]],
        )
        self.assertIn(projection.active_lease.actor_id, {"reviewer-a", "reviewer-b"})

    def test_start_review_same_actor_retry_renews_without_changing_lease_id(self):
        bead_id = "retry-review"
        mutate_ledger(bead_id, "ledger-created", {"repositories": []}, "worker", "w", base_dir=self.test_dir)
        mutate_ledger(bead_id, "implementation-complete", {}, "worker", "w", base_dir=self.test_dir)
        mutate_ledger(bead_id, "review-requested", {}, "worker", "w", base_dir=self.test_dir)
        _, first = start_review(bead_id, "reviewer-a", base_dir=self.test_dir, requested_lease_id="stable")
        _, second = start_review(bead_id, "reviewer-a", base_dir=self.test_dir, requested_lease_id="stable")

        self.assertEqual(first.active_lease.lease_id, second.active_lease.lease_id)
        log, _ = load_ledger(bead_id, base_dir=self.test_dir)
        self.assertEqual("lease-renewed", log.events[-1].action)


    def _prepare_requested_review(self, bead_id):
        mutate_ledger(bead_id, "ledger-created", {"repositories": []}, "worker", "w", base_dir=self.test_dir)
        mutate_ledger(bead_id, "implementation-complete", {}, "worker", "w", base_dir=self.test_dir)
        mutate_ledger(bead_id, "review-requested", {}, "worker", "w", base_dir=self.test_dir)

    def test_start_review_conflict_does_not_mutate_ledger_files(self):
        bead_id = "conflict-review"
        self._prepare_requested_review(bead_id)
        start_review(bead_id, "reviewer-a", base_dir=self.test_dir, requested_lease_id="lease-a")
        json_path = Path(self.test_dir, ".planning", bead_id, "review.json")
        md_path = Path(self.test_dir, ".planning", bead_id, "review.md")
        before = (json_path.read_bytes(), md_path.read_bytes())

        with self.assertRaises(Exception):
            start_review(bead_id, "reviewer-b", base_dir=self.test_dir)

        self.assertEqual(before, (json_path.read_bytes(), md_path.read_bytes()))

    def test_expired_lease_takeover_is_auditable(self):
        bead_id = "expired-review"
        self._prepare_requested_review(bead_id)
        mutate_ledger(
            bead_id,
            "lease-acquired",
            {
                "lease_id": "old",
                "actor_role": "reviewer",
                "actor_id": "reviewer-a",
                "acquired_at": "2000-01-01T00:00:00Z",
                "expires_at": "2999-01-01T00:01:00Z",
            },
            "reviewer",
            "reviewer-a",
            base_dir=self.test_dir,
        )
        mutate_ledger(
            bead_id, "review-started", {}, "reviewer", "reviewer-a",
            base_dir=self.test_dir, lease_id="old",
        )
        mutate_ledger(
            bead_id,
            "lease-renewed",
            {"expires_at": "2000-01-01T00:01:00Z"},
            "reviewer",
            "reviewer-a",
            base_dir=self.test_dir,
            lease_id="old",
        )
        log, projection = start_review(
            bead_id,
            "reviewer-b",
            base_dir=self.test_dir,
            requested_lease_id="new",
        )

        self.assertEqual("reviewer-b", projection.active_lease.actor_id)
        self.assertEqual(
            ["lease-broken", "lease-acquired"],
            [event.action for event in log.events[-2:]],
        )
        self.assertEqual("old", log.events[-2].payload["lease_id"])
        self.assertEqual("new", log.events[-2].payload["replaced_by"])

if __name__ == "__main__":
    unittest.main()
