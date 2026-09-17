from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../plugins/gin-workflow/src/scripts")
    ),
)

from review_ledger.cleanup import cleanup_review_ledgers, is_bead_closed


class TestReviewLedgerCleanup(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.repo_root = Path(self.test_dir)
        # Initialize git repo in test_dir
        subprocess.run(["git", "init"], cwd=self.repo_root, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=self.repo_root,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=self.repo_root,
            check=True,
            capture_output=True,
        )
        # Create an initial commit
        (self.repo_root / "README.md").write_text("# Test Repo\n")
        subprocess.run(["git", "add", "."], cwd=self.repo_root, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial commit"],
            cwd=self.repo_root,
            check=True,
            capture_output=True,
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_scoped_review(self, bead_id: str, state: str = "review-approved") -> Path:
        review_dir = self.repo_root / ".planning" / "reviews" / bead_id
        review_dir.mkdir(parents=True, exist_ok=True)
        (review_dir / "review.json").write_text(json.dumps({
            "review_state": state,
            "repositories": [{"checkpoint_sha": "HEAD", "repository_path": "."}],
        }))
        (review_dir / "review.md").write_text("# Review\n")
        (review_dir / ".review.lock").write_bytes(b"")
        return review_dir

    def _create_legacy_review(self, bead_id: str, state: str = "review-approved") -> Path:
        legacy_dir = self.repo_root / ".planning" / bead_id
        legacy_dir.mkdir(parents=True, exist_ok=True)
        (legacy_dir / "review.json").write_text(json.dumps({
            "review_state": state,
            "repositories": [{"checkpoint_sha": "HEAD", "repository_path": "."}],
        }))
        (legacy_dir / "review.md").write_text("# Legacy Review\n")
        (legacy_dir / ".review.lock").write_bytes(b"")
        return legacy_dir

    @patch("review_ledger.cleanup._query_beads_status")
    def test_cleanup_specific_closed_bead(self, mock_beads):
        mock_beads.return_value = ("closed", "bead status is closed")
        review_dir = self._create_scoped_review("closed-bead-1")
        self.assertTrue(review_dir.exists())
        self.assertTrue((review_dir / ".review.lock").exists())

        result = cleanup_review_ledgers(self.repo_root, bead_id="closed-bead-1")

        self.assertFalse(review_dir.exists())
        self.assertEqual(len(result["cleaned"]), 1)
        self.assertEqual(result["cleaned"][0]["bead_id"], "closed-bead-1")
        self.assertEqual(len(result["skipped"]), 0)

    @patch("review_ledger.cleanup._query_beads_status")
    def test_cleanup_open_bead_skips_and_preserves_directory(self, mock_beads):
        mock_beads.return_value = ("in_progress", "bead status is in_progress")
        review_dir = self._create_scoped_review("open-bead-1")

        result = cleanup_review_ledgers(self.repo_root, bead_id="open-bead-1")

        self.assertTrue(review_dir.exists())
        self.assertEqual(len(result["cleaned"]), 0)
        self.assertEqual(len(result["skipped"]), 1)
        self.assertEqual(result["skipped"][0]["bead_id"], "open-bead-1")

    @patch("review_ledger.cleanup._query_beads_status")
    def test_cleanup_dry_run_does_not_delete(self, mock_beads):
        mock_beads.return_value = ("closed", "bead status is closed")
        review_dir = self._create_scoped_review("closed-bead-dry")

        result = cleanup_review_ledgers(self.repo_root, bead_id="closed-bead-dry", dry_run=True)

        self.assertTrue(review_dir.exists())
        self.assertEqual(len(result["cleaned"]), 1)
        self.assertEqual(result["cleaned"][0]["bead_id"], "closed-bead-dry")
        self.assertTrue(result["dry_run"])

    @patch("review_ledger.cleanup._query_beads_status")
    def test_cleanup_legacy_directory(self, mock_beads):
        mock_beads.return_value = ("closed", "bead status is closed")
        legacy_dir = self._create_legacy_review("legacy-bead-1")
        self.assertTrue(legacy_dir.exists())

        result = cleanup_review_ledgers(self.repo_root, bead_id="legacy-bead-1")

        self.assertFalse(legacy_dir.exists())
        self.assertEqual(len(result["cleaned"]), 1)
        self.assertEqual(result["cleaned"][0]["bead_id"], "legacy-bead-1")

    @patch("review_ledger.cleanup._query_beads_status")
    def test_cleanup_all_closed_cleans_both_scoped_and_legacy_and_skips_active(self, mock_beads):
        def fake_beads_status(bead_id, repo_root, **kwargs):
            if bead_id.startswith("closed"):
                return "closed", "bead status is closed"
            return "open", "bead status is open"

        mock_beads.side_effect = fake_beads_status

        closed_scoped = self._create_scoped_review("closed-bead-a")
        open_scoped = self._create_scoped_review("open-bead-b")
        closed_legacy = self._create_legacy_review("closed-bead-c")
        open_legacy = self._create_legacy_review("open-bead-d")

        # Canonical dirs that must never be touched
        canonical_plans = self.repo_root / ".planning" / "plans"
        canonical_plans.mkdir(parents=True, exist_ok=True)
        (canonical_plans / "plan.md").write_text("# Plan\n")

        canonical_specs = self.repo_root / ".planning" / "specs"
        canonical_specs.mkdir(parents=True, exist_ok=True)
        (canonical_specs / "spec.md").write_text("# Spec\n")

        result = cleanup_review_ledgers(self.repo_root, all_closed=True)

        self.assertFalse(closed_scoped.exists())
        self.assertFalse(closed_legacy.exists())
        self.assertTrue(open_scoped.exists())
        self.assertTrue(open_legacy.exists())
        self.assertTrue(canonical_plans.exists())
        self.assertTrue(canonical_specs.exists())

        cleaned_ids = {item["bead_id"] for item in result["cleaned"]}
        skipped_ids = {item["bead_id"] for item in result["skipped"]}

        self.assertEqual(cleaned_ids, {"closed-bead-a", "closed-bead-c"})
        self.assertEqual(skipped_ids, {"open-bead-b", "open-bead-d"})

    def test_merged_git_fallback_when_beads_not_found(self):
        # Create a commit that is merged into HEAD
        commit_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=self.repo_root, capture_output=True, text=True, check=True
        ).stdout.strip()

        review_dir = self.repo_root / ".planning" / "reviews" / "git-merged-bead"
        review_dir.mkdir(parents=True, exist_ok=True)
        (review_dir / "review.json").write_text(json.dumps({
            "review_state": "review-approved",
            "repositories": [{"checkpoint_sha": commit_sha, "repository_path": "."}],
        }))

        with patch("review_ledger.cleanup._query_beads_status", return_value=(None, "not found in beads")):
            is_closed, reason = is_bead_closed("git-merged-bead", self.repo_root, review_dir)
            self.assertTrue(is_closed)
            self.assertIn("merged", reason)

    def test_cli_cleanup_subcommand_success(self):
        script_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "../../plugins/gin-workflow/src/scripts/review-ledger.py")
        )
        commit_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=self.repo_root, capture_output=True, text=True, check=True
        ).stdout.strip()

        review_dir = self._create_scoped_review("cli-bead-1")
        # Update review.json to point to commit_sha
        (review_dir / "review.json").write_text(json.dumps({
            "review_state": "review-approved",
            "repositories": [{"checkpoint_sha": commit_sha, "repository_path": "."}],
        }))

        res = subprocess.run(
            [sys.executable, script_path, "cleanup", "--repository", str(self.repo_root), "--bead-id", "cli-bead-1"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, res.returncode, res.stderr)
        data = json.loads(res.stdout)
        self.assertEqual(len(data["cleaned"]), 1)
        self.assertEqual(data["cleaned"][0]["bead_id"], "cli-bead-1")
        self.assertFalse(review_dir.exists())

    def test_cli_cleanup_requires_bead_or_all_closed(self):
        script_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "../../plugins/gin-workflow/src/scripts/review-ledger.py")
        )
        res = subprocess.run(
            [sys.executable, script_path, "cleanup", "--repository", str(self.repo_root)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(2, res.returncode)
        self.assertIn("Either --bead-id or --all-closed must be specified", res.stderr)

    def test_cli_cleanup_rejects_mutually_exclusive_options(self):
        script_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "../../plugins/gin-workflow/src/scripts/review-ledger.py")
        )
        res = subprocess.run(
            [sys.executable, script_path, "cleanup", "--repository", str(self.repo_root), "--bead-id", "b1", "--all-closed"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(2, res.returncode)
        self.assertIn("mutually exclusive", res.stderr)

    def test_path_traversal_bead_id_raises_value_error(self):
        for bad_id in ("../src", "../../etc", "foo/bar", "foo\\bar", ".", ".."):
            with self.subTest(bad_id=bad_id):
                with self.assertRaises(ValueError):
                    cleanup_review_ledgers(self.repo_root, bead_id=bad_id)

    @patch("review_ledger.cleanup._query_beads_status")
    def test_protected_planning_dir_as_bead_id_is_skipped_and_preserved(self, mock_beads):
        mock_beads.return_value = ("closed", "bead status is closed")
        plans_dir = self.repo_root / ".planning" / "plans"
        plans_dir.mkdir(parents=True, exist_ok=True)
        (plans_dir / "my_plan.md").write_text("# Sensitive Plan\n")

        result = cleanup_review_ledgers(self.repo_root, bead_id="plans")

        self.assertTrue(plans_dir.exists())
        self.assertTrue((plans_dir / "my_plan.md").exists())
        self.assertEqual(len(result["cleaned"]), 0)
        self.assertEqual(len(result["skipped"]), 1)
        self.assertIn("protected directory", result["skipped"][0]["reason"])

    @patch("review_ledger.cleanup._query_beads_status")
    def test_directory_without_review_artifacts_is_not_cleaned(self, mock_beads):
        mock_beads.return_value = ("closed", "bead status is closed")
        custom_dir = self.repo_root / ".planning" / "custom-bead"
        custom_dir.mkdir(parents=True, exist_ok=True)
        (custom_dir / "notes.txt").write_text("not a review ledger")

        result = cleanup_review_ledgers(self.repo_root, bead_id="custom-bead")

        self.assertTrue(custom_dir.exists())
        self.assertEqual(len(result["cleaned"]), 0)
        self.assertEqual(len(result["skipped"]), 1)
        self.assertIn("No review directory found", result["skipped"][0]["reason"])

    def test_multi_repository_review_requires_all_repos_merged(self):
        commit_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=self.repo_root, capture_output=True, text=True, check=True
        ).stdout.strip()
        unmerged_sha = "0123456789abcdef0123456789abcdef01234567"

        review_dir = self.repo_root / ".planning" / "reviews" / "multi-repo-bead"
        review_dir.mkdir(parents=True, exist_ok=True)
        # One merged, one unmerged
        (review_dir / "review.json").write_text(json.dumps({
            "review_state": "review-approved",
            "repositories": [
                {"checkpoint_sha": commit_sha, "repository_path": "."},
                {"checkpoint_sha": unmerged_sha, "repository_path": "sub-repo"},
            ],
        }))

        with patch("review_ledger.cleanup._query_beads_status", return_value=(None, "not in beads")):
            is_closed, reason = is_bead_closed("multi-repo-bead", self.repo_root, review_dir)
            self.assertFalse(is_closed)
            self.assertIn("not closed in task tracking and not merged in git", reason)


if __name__ == "__main__":
    unittest.main()
