import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = str(Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts/review-ledger.py")
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"))

BEAD = "bead-t"


class TestReviewDecisionWithoutFinding(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        subprocess.run(["git", "init", "-q", "."], cwd=self.test_dir, check=True)
        Path(self.test_dir, "f.txt").write_text("x\n")
        subprocess.run(["git", "add", "f.txt"], cwd=self.test_dir, check=True)
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base"],
                       cwd=self.test_dir, check=True)
        subprocess.run(["git", "update-ref", f"refs/gin/review/{BEAD}", "HEAD"], cwd=self.test_dir, check=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def cli(self, *args):
        return subprocess.run([sys.executable, SCRIPT, *args], cwd=self.test_dir, capture_output=True, text=True)

    def ok(self, *args):
        done = self.cli(*args)
        self.assertEqual(0, done.returncode, done.stderr + done.stdout)
        return done

    def to_state(self, state, role, actor, lease=None):
        extra = ["--lease-id", lease] if lease else []
        self.ok("transition-requested", "--bead-id", BEAD, "--to", state, "--actor-role", role, "--actor-id", actor, *extra)

    def start(self):
        return self.cli("start-review", "--bead-id", BEAD, "--actor-id", "b@x")

    @staticmethod
    def lease_of(done):
        return done.stdout.strip().split()[-1].rstrip(".")

    def status(self):
        return json.loads(self.ok("status", "--bead-id", BEAD, "--format", "json").stdout)

    def decide(self, *extra):
        return self.cli("record-human-decision", "--bead-id", BEAD, "--question", "more?", "--decision", "one more",
                        "--reason", "scope", "--actor-id", "lead@x", *extra)

    def reach_max_cycles_with_fixed_finding(self):
        self.ok("init", "--bead-id", BEAD, "--repo-id", "r", "--repo-path", ".", "--include", "f.txt",
                "--review-ref", f"refs/gin/review/{BEAD}", "--base-sha", "HEAD", "--actor-id", "a@x",
                "--max-cycles", "1")
        self.to_state("review-requested", "worker", "a@x")
        lease = self.lease_of(self.start())
        self.ok("add-finding", "--bead-id", BEAD, "--finding-id", "F-1", "--severity", "IMPORTANT",
                "--actor-id", "b@x", "--lease-id", lease)
        self.to_state("changes-requested", "reviewer", "b@x", lease)
        self.ok("release-lease", "--bead-id", BEAD, "--actor-id", "b@x", "--lease-id", lease)
        self.to_state("implementation-in-progress", "worker", "a@x")
        self.ok("fix-finding", "--bead-id", BEAD, "--finding-id", "F-1", "--actor-id", "a@x")
        self.to_state("review-requested", "worker", "a@x")

    def test_decision_without_finding_allows_one_more_cycle_then_approval(self):
        self.reach_max_cycles_with_fixed_finding()
        refused = self.start()
        self.assertEqual(1, refused.returncode)
        self.assertIn("max review cycles (1) reached; record a human decision", refused.stderr + refused.stdout)

        decided = self.decide()
        self.assertEqual(0, decided.returncode, decided.stderr)
        self.assertIn("Recorded human decision for the review", decided.stdout)

        started = self.start()
        self.assertEqual(0, started.returncode, started.stderr + started.stdout)
        lease = self.lease_of(started)
        self.ok("verify-finding", "--bead-id", BEAD, "--finding-id", "F-1", "--actor-role", "reviewer",
                "--actor-id", "b@x", "--lease-id", lease)
        self.ok("approve", "--bead-id", BEAD, "--actor-id", "b@x", "--lease-id", lease)
        self.assertEqual("review-approved", self.status()["review_state"])
        self.ok("validate", "--bead-id", BEAD)
        self.ok("render", "--bead-id", BEAD)

    def test_finding_stays_fixed_awaiting_verification_after_decision(self):
        self.reach_max_cycles_with_fixed_finding()
        self.ok("record-human-decision", "--bead-id", BEAD, "--question", "q", "--decision", "d",
                "--reason", "r", "--actor-id", "lead@x")
        from review_ledger.cli import load_ledger
        _, proj = load_ledger(BEAD, base_dir=self.test_dir)
        self.assertEqual("fixed-awaiting-verification", proj.findings["F-1"].status)

    def test_a_later_cycle_is_refused_until_another_decision(self):
        self.reach_max_cycles_with_fixed_finding()
        self.ok("record-human-decision", "--bead-id", BEAD, "--question", "q", "--decision", "d",
                "--reason", "r", "--actor-id", "lead@x")
        lease = self.lease_of(self.start())
        self.to_state("changes-requested", "reviewer", "b@x", lease)
        self.ok("release-lease", "--bead-id", BEAD, "--actor-id", "b@x", "--lease-id", lease)
        self.to_state("implementation-in-progress", "worker", "a@x")
        self.to_state("review-requested", "worker", "a@x")
        self.assertEqual(1, self.start().returncode)
        self.ok("record-human-decision", "--bead-id", BEAD, "--question", "q", "--decision", "d2",
                "--reason", "r", "--actor-id", "lead@x")
        self.assertEqual(0, self.start().returncode)

    def test_only_a_human_records_a_decision_for_the_review(self):
        self.reach_max_cycles_with_fixed_finding()
        from review_ledger.cli import load_ledger
        log_before, _ = load_ledger(BEAD, base_dir=self.test_dir)
        for role in ("worker", "reviewer"):
            refused = self.decide("--actor-role", role)
            self.assertNotEqual(0, refused.returncode, role)
        log_after, proj = load_ledger(BEAD, base_dir=self.test_dir)
        self.assertEqual(len(log_before.events), len(log_after.events))
        self.assertFalse(proj.decided_since_cycle)
        self.assertEqual(1, self.start().returncode)

    def test_decision_with_finding_id_still_needs_human_decision_required(self):
        self.reach_max_cycles_with_fixed_finding()
        refused = self.decide("--finding-id", "F-1")
        self.assertNotEqual(0, refused.returncode)

    def test_decision_with_finding_id_works_from_human_decision_required(self):
        self.reach_max_cycles_with_fixed_finding()
        # Reopen path: reviewer escalates a fresh review's disputed finding is out of scope here, so use the FSM
        # directly through the library for the precondition.
        from review_ledger.cli import load_ledger, mutate_ledger
        mutate_ledger(BEAD, "finding-reopened", {"finding_id": "F-1"}, "reviewer", "b@x",
                      base_dir=self.test_dir, bypass_lease=True)
        mutate_ledger(BEAD, "finding-disputed", {"finding_id": "F-1", "reason": "no"}, "worker", "a@x",
                      base_dir=self.test_dir, bypass_lease=True)
        mutate_ledger(BEAD, "human-decision-required", {"finding_id": "F-1", "reason": "?"}, "reviewer", "b@x",
                      base_dir=self.test_dir, bypass_lease=True)
        done = self.decide("--finding-id", "F-1")
        self.assertEqual(0, done.returncode, done.stderr)
        self.assertIn("Recorded human decision for finding F-1", done.stdout)
        _, proj = load_ledger(BEAD, base_dir=self.test_dir)
        self.assertEqual("human-decision-recorded", proj.findings["F-1"].status)


if __name__ == "__main__":
    unittest.main()
