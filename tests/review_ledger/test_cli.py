import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../plugins/gin-workflow/src/scripts")
    ),
)

from review_ledger.cli import initialize_ledger, load_ledger, mutate_ledger


class TestCLI(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_cli_ledger_lifecycle_keeps_legacy_repository_readable(self):
        bead_id = "bead-abc"
        payload = {
            "repositories": [
                {
                    "repository_id": "primary",
                    "role": "primary",
                    "review_ref": "ref",
                    "review_base_sha": "sha1",
                    "reviewed_source_sha": "sha2",
                }
            ]
        }
        mutate_ledger(bead_id, "ledger-created", payload, "worker", "w1", base_dir=self.test_dir)
        mutate_ledger(bead_id, "implementation-complete", {}, "worker", "w1", base_dir=self.test_dir)
        mutate_ledger(bead_id, "review-requested", {}, "worker", "w1", base_dir=self.test_dir)
        mutate_ledger(bead_id, "review-started", {}, "reviewer", "rev1", base_dir=self.test_dir)
        mutate_ledger(
            bead_id,
            "finding-created",
            {"finding_id": "F-001", "severity": "CRITICAL"},
            "reviewer",
            "rev1",
            base_dir=self.test_dir,
        )
        _log, projection = load_ledger(bead_id, base_dir=self.test_dir)
        self.assertEqual(projection.review_state, "review-in-progress")
        self.assertEqual(projection.repositories[0]["source_identity_status"], "missing")

    def test_init_command_accepts_repeatable_scope_arguments(self):
        subprocess.run(["git", "init"], cwd=self.test_dir, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.test_dir, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.test_dir, check=True)
        os.makedirs(os.path.join(self.test_dir, "src"))
        with open(os.path.join(self.test_dir, "src/base.py"), "w") as stream:
            stream.write("base")
        subprocess.run(["git", "add", "src/base.py"], cwd=self.test_dir, check=True)
        subprocess.run(["git", "commit", "-m", "base"], cwd=self.test_dir, capture_output=True, check=True)
        script = (
            Path(__file__).resolve().parents[2]
            / "plugins/gin-workflow/src/scripts/review-ledger.py"
        )
        process = subprocess.run(
            [
                sys.executable,
                str(script),
                "init",
                "--bead-id",
                "bead-command",
                "--repo-id",
                "primary",
                "--repo-path",
                ".",
                "--review-ref",
                "refs/gin/review/bead-command",
                "--include",
                "src/",
                "--exclude",
                "dist/",
                "--generated",
                "src/generated/",
                "--actor-id",
                "worker-1",
            ],
            cwd=self.test_dir,
            capture_output=True,
            text=True,
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        _log, projection = load_ledger("bead-command", base_dir=self.test_dir)
        self.assertEqual(projection.source_scope["included_paths"], ["src"])
        self.assertEqual(projection.repositories[0]["source_identity_status"], "complete")

    def test_initialize_computes_scope_and_tree_identity_without_mutating_checkout(self):
        subprocess.run(["git", "init"], cwd=self.test_dir, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.test_dir, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.test_dir, check=True)
        os.makedirs(os.path.join(self.test_dir, "src"))
        with open(os.path.join(self.test_dir, "src/base.py"), "w") as stream:
            stream.write("base")
        subprocess.run(["git", "add", "src/base.py"], cwd=self.test_dir, check=True)
        subprocess.run(["git", "commit", "-m", "base"], cwd=self.test_dir, capture_output=True, check=True)
        with open(os.path.join(self.test_dir, "src/new.py"), "w") as stream:
            stream.write("new")

        before_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=self.test_dir)
        before_status = subprocess.check_output(
            ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
            cwd=self.test_dir,
        )
        checkpoint = initialize_ledger(
            bead_id="bead-init",
            repository_id="primary",
            role="primary",
            repo_path=self.test_dir,
            review_ref="refs/gin/review/bead-init",
            base_ref="HEAD",
            scope={
                "included_paths": ["src/"],
                "excluded_artifact_paths": ["dist/"],
                "allowed_generated_paths": ["src/generated/"],
            },
            actor_role="worker",
            actor_id="w1",
            base_dir=self.test_dir,
        )

        _log, projection = load_ledger("bead-init", base_dir=self.test_dir)
        repository = projection.repositories[0]
        self.assertEqual(repository["checkpoint_sha"], checkpoint.checkpoint_sha)
        self.assertEqual(repository["reviewed_source_sha"], checkpoint.checkpoint_sha)
        self.assertEqual(repository["checkpoint_ref"], "refs/gin/review/bead-init")
        self.assertEqual(repository["source_scope_hash"], checkpoint.source_scope_hash)
        self.assertEqual(repository["source_tree_hash"], checkpoint.source_tree_hash)
        self.assertEqual(repository["source_identity_status"], "complete")
        self.assertEqual(projection.source_scope["included_paths"], ["src"])
        self.assertEqual(before_head, subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=self.test_dir))
        after_status = subprocess.check_output(
            ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
            cwd=self.test_dir,
        )
        self.assertTrue(set(before_status.split(b"\0")).issubset(set(after_status.split(b"\0"))))
        self.assertIn(b".planning/", after_status)


if __name__ == "__main__":
    unittest.main()
