"""Regressions for gin-workflow-atr: stale approvals, expired leases, and ledger files in the source hash."""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../plugins/gin-workflow/src/scripts"))
sys.path.insert(0, SCRIPTS)

from review_ledger.cli import load_ledger, mutate_ledger  # noqa: E402
from review_ledger.lease import LeaseError, format_utc_timestamp  # noqa: E402

LEDGER = os.path.join(SCRIPTS, "review-ledger.py")
BEAD = "bead-atr"
REVIEWER = "reviewer:other:model"


class LedgerRepo(unittest.TestCase):
    """A real git repository whose ledger stays untracked, as in a feature worktree."""

    def setUp(self):
        self.repo = tempfile.mkdtemp()
        for args in (["init", "-q"], ["config", "user.email", "t@example.com"], ["config", "user.name", "T"]):
            self.git(*args)
        self.write("src/app.py", "print('v1')\n")
        self.git("add", ".")
        self.git("commit", "-qm", "base")
        self.base = self.git("rev-parse", "HEAD").strip()
        self.cli("init", "--bead-id", BEAD, "--repo-id", "r", "--repo-path", ".",
                 "--review-ref", f"refs/gin/review/{BEAD}", "--base-sha", self.base, "--actor-id", "w1")

    def tearDown(self):
        shutil.rmtree(self.repo)

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.repo, check=True, capture_output=True, text=True).stdout

    def write(self, relative, text):
        path = os.path.join(self.repo, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as stream:
            stream.write(text)

    def cli(self, *args, check=True):
        result = subprocess.run([sys.executable, LEDGER, *args], cwd=self.repo, capture_output=True, text=True)
        if check and result.returncode != 0:
            self.fail(f"review-ledger {' '.join(args)} failed: {result.stdout}{result.stderr}")
        return result

    def checkpoint(self):
        self.cli("checkpoint", "--bead-id", BEAD, "--repo-id", "r", "--commit-msg", "cp", "--actor-id", "w1",
                 *self.lease_args())

    def lease_args(self):
        _, projection = load_ledger(BEAD, base_dir=self.repo)
        return ["--lease-id", projection.active_lease.lease_id] if projection.active_lease else []

    def start_review(self):
        output = self.cli("start-review", "--bead-id", BEAD, "--actor-role", "reviewer", "--actor-id", REVIEWER).stdout
        return output.strip().split()[-1].rstrip(".")

    def approve(self, lease, check=True):
        return self.cli("approve", "--bead-id", BEAD, "--actor-role", "reviewer", "--actor-id", REVIEWER,
                        "--lease-id", lease, check=check)

    def state(self):
        return load_ledger(BEAD, base_dir=self.repo)[1]

    def request_and_approve(self):
        self.checkpoint()
        self.cli("transition-requested", "--bead-id", BEAD, "--to", "review-requested", "--actor-id", "w1",
                 *self.lease_args())
        lease = self.start_review()
        self.approve(lease)
        return lease


class TestUntrackedLedgerDoesNotBreakApproval(LedgerRepo):
    def test_approve_and_validate_pass_with_an_untracked_ledger_and_unchanged_source(self):
        self.request_and_approve()
        self.assertEqual("review-approved", self.state().review_state)
        self.cli("validate", "--bead-id", BEAD)

    def test_untracked_in_scope_source_change_after_checkpoint_refuses_approval(self):
        self.write("src/new.py", "x = 1\n")
        self.checkpoint()
        self.cli("transition-requested", "--bead-id", BEAD, "--to", "review-requested", "--actor-id", "w1")
        lease = self.start_review()
        self.write("src/new.py", "x = 2\n")
        refused = self.approve(lease, check=False)
        self.assertNotEqual(0, refused.returncode)
        self.assertIn("differs from checkpoint", refused.stderr + refused.stdout)


class TestCheckpointInvalidatesStaleApproval(LedgerRepo):
    def test_checkpoint_of_a_changed_tree_invalidates_the_approval(self):
        self.request_and_approve()
        self.write("src/app.py", "print('v2')\n")
        self.git("commit", "-qam", "change after approval")
        self.checkpoint()

        projection = self.state()
        self.assertIsNone(projection.active_approval)
        self.assertEqual("review-requested", projection.review_state)

        lease = self.start_review()
        self.approve(lease)
        self.assertEqual("review-approved", self.state().review_state)

    def test_checkpoint_of_the_same_tree_keeps_the_approval(self):
        self.request_and_approve()
        self.checkpoint()
        projection = self.state()
        self.assertIsNotNone(projection.active_approval)
        self.assertEqual("review-approved", projection.review_state)

    def test_validate_fails_when_the_active_approval_binds_another_tree(self):
        self.checkpoint()
        self.cli("transition-requested", "--bead-id", BEAD, "--to", "review-requested", "--actor-id", "w1")
        lease = self.start_review()
        repositories = [dict(item, reviewed_source_tree_hash="0" * 64) for item in self.state().repositories]
        mutate_ledger(BEAD, "review-approved", {
            "approved_repositories": repositories, "source_scope_hash": "s", "terminal_findings": [],
        }, "reviewer", REVIEWER, base_dir=self.repo, lease_id=lease)
        result = self.cli("validate", "--bead-id", BEAD, check=False)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("active approval", result.stderr + result.stdout)


class TestExpiredLeaseDoesNotBlockWriters(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp()
        mutate_ledger(BEAD, "ledger-created", {"repositories": []}, "worker", "w1", base_dir=self.base)
        mutate_ledger(BEAD, "implementation-complete", {}, "worker", "w1", base_dir=self.base)
        mutate_ledger(BEAD, "review-requested", {}, "worker", "w1", base_dir=self.base)
        past = datetime.now(timezone.utc) - timedelta(minutes=30)
        mutate_ledger(BEAD, "lease-acquired", {
            "lease_id": "old", "actor_role": "reviewer", "actor_id": "rev",
            "acquired_at": format_utc_timestamp(past - timedelta(minutes=10)),
            "expires_at": format_utc_timestamp(past),
        }, "reviewer", "rev", base_dir=self.base)

    def tearDown(self):
        shutil.rmtree(self.base)

    def test_write_without_lease_succeeds_once_the_lease_expired(self):
        mutate_ledger(BEAD, "source-checkpoint-created", {"repositories": []}, "worker", "w1", base_dir=self.base)

    def test_the_expired_lease_id_itself_is_still_refused(self):
        with self.assertRaises(LeaseError):
            mutate_ledger(BEAD, "source-checkpoint-created", {"repositories": []}, "worker", "w1",
                          base_dir=self.base, lease_id="old")


if __name__ == "__main__":
    unittest.main()
