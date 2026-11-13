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

from review_ledger.cli import load_ledger, mutate_ledger
from review_ledger.finding_fsm import InvalidTransitionError, validate_finding_transition
from review_ledger.projections import ReviewProjection
from review_ledger.renderer import render_review_markdown
from review_ledger.schema import EventActions

SCRIPT = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts/review-ledger.py"


class TestDeferralWithdrawnFSM(unittest.TestCase):
    def test_worker_can_take_back_a_proposed_deferral(self):
        for severity in ("IMPORTANT", "MINOR"):
            validate_finding_transition("deferral-proposed", "open", severity, "worker", 0)

    def test_reviewer_and_human_cannot_take_back_a_proposed_deferral(self):
        for role in ("reviewer", "human"):
            with self.assertRaises(InvalidTransitionError):
                validate_finding_transition("deferral-proposed", "open", "IMPORTANT", role, 0)

    def test_existing_deferral_transitions_are_unchanged(self):
        validate_finding_transition("deferral-proposed", "deferred-verified", "MINOR", "reviewer", 0)
        validate_finding_transition("deferral-proposed", "human-decision-required", "IMPORTANT", "reviewer", 0)
        with self.assertRaises(InvalidTransitionError):
            validate_finding_transition("deferral-proposed", "human-decision-required", "IMPORTANT", "worker", 0)
        with self.assertRaises(InvalidTransitionError):
            validate_finding_transition("deferral-proposed", "fixed-awaiting-verification", "IMPORTANT", "worker", 0)
        with self.assertRaises(InvalidTransitionError):
            validate_finding_transition("deferral-proposed", "deferred-verified", "IMPORTANT", "reviewer", 0)


class TestDeferralDecisionCommands(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.bead_id = "bead-defer"
        self._mutate("ledger-created", {"repositories": []}, "worker", "w1")
        self._mutate("implementation-complete", {}, "worker", "w1")
        self._mutate("review-requested", {}, "worker", "w1")
        self._mutate("review-started", {}, "reviewer", "rev1")
        self._mutate("finding-created", {"finding_id": "F-001", "severity": "IMPORTANT"}, "reviewer", "rev1")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _mutate(self, action, payload, role, actor):
        mutate_ledger(self.bead_id, action, payload, role, actor, base_dir=self.test_dir)

    def _run(self, command, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), command, "--bead-id", self.bead_id, "--finding-id", "F-001", *args],
            cwd=self.test_dir, capture_output=True, text=True,
        )

    def _finding(self):
        _, proj = load_ledger(self.bead_id, base_dir=self.test_dir)
        return proj.findings["F-001"]

    def _propose(self):
        done = self._run(
            "propose-deferral", "--reason", "later", "--follow-up-bead-id", "b-9",
            "--follow-up-bead-title", "Later", "--actor-id", "w1",
        )
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_withdraw_deferral_reopens_and_clears_deferral_fields(self):
        self._propose()
        self.assertEqual(self._finding().status, "deferral-proposed")

        done = self._run("withdraw-deferral", "--reason", "declined", "--actor-id", "w1")

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("Withdrew deferral for finding F-001", done.stdout)
        finding = self._finding()
        self.assertEqual(finding.status, "open")
        self.assertIsNone(finding.deferral_reason)
        self.assertIsNone(finding.follow_up_bead_id)
        self.assertIsNone(finding.follow_up_bead_title)

    def test_withdrawn_finding_can_be_fixed_verified_and_approved(self):
        self._propose()
        self._run("withdraw-deferral", "--reason", "declined", "--actor-id", "w1")
        for command, role, actor in (("fix-finding", "worker", "w1"), ("verify-finding", "reviewer", "rev1")):
            done = self._run(command, "--actor-role", role, "--actor-id", actor)
            self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self._finding().status, "verified")
        approved = subprocess.run(
            [sys.executable, str(SCRIPT), "approve", "--bead-id", self.bead_id, "--actor-id", "rev1"],
            cwd=self.test_dir, capture_output=True, text=True,
        )
        self.assertEqual(approved.returncode, 0, approved.stderr)
        self.assertIn("Review approved.", approved.stdout)

    def test_reviewer_cannot_withdraw_a_deferral(self):
        self._propose()
        done = self._run("withdraw-deferral", "--reason", "x", "--actor-role", "reviewer", "--actor-id", "rev1")
        self.assertNotEqual(done.returncode, 0)
        self.assertEqual(self._finding().status, "deferral-proposed")

    def test_withdraw_requires_a_proposed_deferral(self):
        done = self._run("withdraw-deferral", "--reason", "x", "--actor-id", "w1")
        self.assertNotEqual(done.returncode, 0)
        self.assertEqual(self._finding().status, "open")

    def test_important_deferral_goes_through_a_human_decision(self):
        self._propose()
        done = self._run("require-human-decision", "--reason", "needs a human", "--actor-id", "rev1")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("Required a human decision for finding F-001", done.stdout)
        self.assertEqual(self._finding().status, "human-decision-required")

        done = self._run(
            "record-human-decision", "--question", "defer?", "--decision", "no",
            "--reason", "fix it", "--actor-role", "human", "--actor-id", "boss",
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self._finding().status, "human-decision-recorded")

    def test_human_can_still_waive_from_human_decision_required(self):
        self._propose()
        self._run("require-human-decision", "--reason", "needs a human", "--actor-id", "rev1")
        done = self._run("waive-finding", "--reason", "accept", "--actor-role", "human", "--actor-id", "boss")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self._finding().status, "human-waived")

    def test_worker_cannot_require_a_human_decision(self):
        self._propose()
        done = self._run("require-human-decision", "--reason", "x", "--actor-role", "worker", "--actor-id", "w1")
        self.assertNotEqual(done.returncode, 0)
        self.assertEqual(self._finding().status, "deferral-proposed")

    def test_require_human_decision_works_from_disputed(self):
        self._mutate("finding-disputed", {"finding_id": "F-001", "reason": "wrong"}, "worker", "w1")
        done = self._run("require-human-decision", "--reason", "deadlock", "--actor-id", "rev1")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self._finding().status, "human-decision-required")

    def test_validate_and_render_accept_both_new_events(self):
        self._propose()
        self._run("withdraw-deferral", "--reason", "declined", "--actor-id", "w1")
        self._run("fix-finding", "--actor-role", "worker", "--actor-id", "w1")
        self._run("reopen-finding", "--reason", "no", "--actor-role", "reviewer", "--actor-id", "rev1")
        self._propose()
        self._run("require-human-decision", "--reason", "needs a human", "--actor-id", "rev1")

        validated = subprocess.run(
            [sys.executable, str(SCRIPT), "validate", "--bead-id", self.bead_id],
            cwd=self.test_dir, capture_output=True, text=True,
        )
        self.assertEqual(validated.returncode, 0, validated.stderr)
        log, proj = load_ledger(self.bead_id, base_dir=self.test_dir)
        self.assertEqual(proj.findings["F-001"].status, "human-decision-required")
        actions = [e.action for e in log.events]
        self.assertIn(EventActions.DEFERRAL_WITHDRAWN, actions)
        self.assertIn(EventActions.HUMAN_DECISION_REQUIRED, actions)
        self.assertIn("deferral-withdrawn", render_review_markdown(proj, log))
        rebuilt = ReviewProjection()
        for event in log.events:
            rebuilt.apply_event(event)
        self.assertEqual(rebuilt.findings["F-001"].status, "human-decision-required")


if __name__ == "__main__":
    unittest.main()
