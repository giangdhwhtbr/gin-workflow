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


class TestReopenFinding(unittest.TestCase):
    """A finding wrongly marked fixed must be recoverable.

    finding_fsm declares ("fixed-awaiting-verification", "open") legal for a
    reviewer, but before gin-workflow-tr7 no action could emit it, so such a
    finding was stuck non-terminal and blocked review-approved forever.
    """

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.bead_id = "bead-reopen"
        mutate_ledger(
            self.bead_id, "ledger-created", {"repositories": []},
            "worker", "w1", base_dir=self.test_dir,
        )
        mutate_ledger(self.bead_id, "implementation-complete", {}, "worker", "w1", base_dir=self.test_dir)
        mutate_ledger(self.bead_id, "review-requested", {}, "worker", "w1", base_dir=self.test_dir)
        mutate_ledger(self.bead_id, "review-started", {}, "reviewer", "rev1", base_dir=self.test_dir)
        mutate_ledger(
            self.bead_id, "finding-created",
            {"finding_id": "F-001", "severity": "IMPORTANT"},
            "reviewer", "rev1", base_dir=self.test_dir,
        )
        mutate_ledger(
            self.bead_id, "finding-fixed", {"finding_id": "F-001"},
            "worker", "w1", base_dir=self.test_dir,
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def _status(self):
        _, proj = load_ledger(self.bead_id, base_dir=self.test_dir)
        return proj.findings["F-001"].status

    def test_reviewer_can_reopen_a_wrongly_fixed_finding(self):
        self.assertEqual(self._status(), "fixed-awaiting-verification")

        mutate_ledger(
            self.bead_id, "finding-reopened",
            {"finding_id": "F-001", "reason": "fix is not in the tree"},
            "reviewer", "rev1", base_dir=self.test_dir,
        )

        self.assertEqual(self._status(), "open")

    def test_reopen_preserves_identity_rather_than_creating_a_new_finding(self):
        _, before = load_ledger(self.bead_id, base_dir=self.test_dir)
        severity = before.findings["F-001"].severity
        next_number = before.next_finding_number

        mutate_ledger(
            self.bead_id, "finding-reopened",
            {"finding_id": "F-001", "reason": "regressed"},
            "reviewer", "rev1", base_dir=self.test_dir,
        )

        _, after = load_ledger(self.bead_id, base_dir=self.test_dir)
        self.assertEqual(len(after.findings), 1)
        self.assertEqual(after.findings["F-001"].severity, severity)
        self.assertEqual(after.next_finding_number, next_number)

    def test_worker_cannot_reopen_its_own_finding(self):
        with self.assertRaises(Exception):
            mutate_ledger(
                self.bead_id, "finding-reopened",
                {"finding_id": "F-001", "reason": "self-serving"},
                "worker", "w1", base_dir=self.test_dir,
            )
        self.assertEqual(self._status(), "fixed-awaiting-verification")

    def test_reopen_is_fsm_validated_not_a_blind_status_write(self):
        """Registering the action in status_map is what subjects it to the FSM.

        Without that registration the mutation still lands - the projection
        handler runs regardless - but no transition is ever validated, so a
        finding could be dragged to open from any state by anyone. Reopening a
        finding that is already verified has no legal transition, so it must
        be refused.
        """
        mutate_ledger(
            self.bead_id, "finding-verified", {"finding_id": "F-001"},
            "reviewer", "rev1", base_dir=self.test_dir,
        )
        self.assertEqual(self._status(), "verified")

        with self.assertRaises(Exception):
            mutate_ledger(
                self.bead_id, "finding-reopened",
                {"finding_id": "F-001", "reason": "changed my mind"},
                "reviewer", "rev1", base_dir=self.test_dir,
            )
        self.assertEqual(self._status(), "verified")

    def test_reopening_an_unknown_finding_is_rejected(self):
        with self.assertRaises(Exception):
            mutate_ledger(
                self.bead_id, "finding-reopened",
                {"finding_id": "F-404", "reason": "typo"},
                "reviewer", "rev1", base_dir=self.test_dir,
            )

    def test_reopened_finding_can_be_fixed_and_verified_again(self):
        mutate_ledger(
            self.bead_id, "finding-reopened",
            {"finding_id": "F-001", "reason": "not in tree"},
            "reviewer", "rev1", base_dir=self.test_dir,
        )
        mutate_ledger(
            self.bead_id, "finding-fixed", {"finding_id": "F-001"},
            "worker", "w1", base_dir=self.test_dir,
        )
        mutate_ledger(
            self.bead_id, "finding-verified", {"finding_id": "F-001"},
            "reviewer", "rev1", base_dir=self.test_dir,
        )
        self.assertEqual(self._status(), "verified")


class TestChangeScope(unittest.TestCase):
    """Review scope must be amendable without destroying ledger history.

    review-scope-change-requested was already a valid schema event with
    projection support, but no CLI subcommand emitted it, so a finding whose
    remediation touched a file outside the initial scope could not be fixed
    inside the ledger at all.
    """

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.bead_id = "bead-scope"
        mutate_ledger(
            self.bead_id, "ledger-created",
            {
                "repositories": [],
                "source_scope": {
                    "included_paths": ["src"],
                    "excluded_artifact_paths": [],
                    "allowed_generated_paths": [],
                    "nested_repository_paths": [],
                },
            },
            "worker", "w1", base_dir=self.test_dir,
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_scope_change_replaces_included_paths(self):
        mutate_ledger(
            self.bead_id, "review-scope-change-requested",
            {
                "source_scope": {
                    "included_paths": [".env.example", "src"],
                    "excluded_artifact_paths": [],
                    "allowed_generated_paths": [],
                    "nested_repository_paths": [],
                },
                "reason": "finding remediation touches the env template",
            },
            "worker", "w1", base_dir=self.test_dir,
        )
        _, proj = load_ledger(self.bead_id, base_dir=self.test_dir)
        self.assertIn(".env.example", proj.source_scope["included_paths"])
        self.assertIn("src", proj.source_scope["included_paths"])

    def test_scope_change_invalidates_an_active_approval(self):
        mutate_ledger(self.bead_id, "implementation-complete", {}, "worker", "w1", base_dir=self.test_dir)
        mutate_ledger(self.bead_id, "review-requested", {}, "worker", "w1", base_dir=self.test_dir)
        mutate_ledger(self.bead_id, "review-started", {}, "reviewer", "rev1", base_dir=self.test_dir)
        mutate_ledger(
            self.bead_id, "review-approved",
            {
                "approved_repositories": [],
                "source_scope_hash": "scope-hash",
                "terminal_findings": [],
            },
            "reviewer", "rev1", base_dir=self.test_dir,
        )
        _, approved = load_ledger(self.bead_id, base_dir=self.test_dir)
        self.assertIsNotNone(approved.active_approval)

        mutate_ledger(
            self.bead_id, "review-scope-change-requested",
            {
                "source_scope": {
                    "included_paths": ["src", "docs"],
                    "excluded_artifact_paths": [],
                    "allowed_generated_paths": [],
                    "nested_repository_paths": [],
                },
                "reason": "widen",
            },
            "worker", "w1", base_dir=self.test_dir,
        )
        _, after = load_ledger(self.bead_id, base_dir=self.test_dir)
        self.assertIsNone(
            after.active_approval,
            "widening scope must invalidate approval: the added paths were never reviewed",
        )


class TestBeadStateActionResolution(unittest.TestCase):
    """A requested target state must resolve to an action the projection applies.

    Regression cover for gin-workflow-b8i: `transition-requested` passed the
    target STATE name straight through as the event ACTION. Five states happen
    to share a name with their action and worked by coincidence; the rest fell
    out of the mutation path's state_map, skipping bead-FSM validation and
    leaving review_state unchanged while the command printed success.
    """

    def test_every_reachable_state_resolves_to_an_action(self):
        from review_ledger.cli import BEAD_ACTION_STATES, resolve_bead_state_action

        for state in set(BEAD_ACTION_STATES.values()):
            action = resolve_bead_state_action(state)
            self.assertIn(action, BEAD_ACTION_STATES, state)
            self.assertEqual(
                state, BEAD_ACTION_STATES[action],
                f"{state} resolved to {action}, which yields "
                f"{BEAD_ACTION_STATES[action]}",
            )

    def test_post_approval_states_resolve_to_their_real_actions(self):
        from review_ledger.cli import resolve_bead_state_action

        self.assertEqual(
            "verification-started", resolve_bead_state_action("verification-in-progress")
        )
        self.assertEqual(
            "verification-passed", resolve_bead_state_action("ready-to-ship")
        )
        self.assertEqual(
            "shipping-completed", resolve_bead_state_action("closed")
        )

    def test_unreachable_state_is_rejected_rather_than_silently_ignored(self):
        from review_ledger.cli import resolve_bead_state_action

        with self.assertRaises(ValueError) as ctx:
            resolve_bead_state_action("not-a-state")
        self.assertIn("not-a-state", str(ctx.exception))
        # The diagnostic must tell the operator what IS reachable.
        self.assertIn("ready-to-ship", str(ctx.exception))


class TestTransitionRequestedAppliesState(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.script = str(
            Path(__file__).resolve().parents[2]
            / "plugins/gin-workflow/src/scripts/review-ledger.py"
        )
        subprocess.run(["git", "init", "-q", "."], cwd=self.test_dir, check=True)
        Path(self.test_dir, "f.txt").write_text("x\n")
        subprocess.run(["git", "add", "f.txt"], cwd=self.test_dir, check=True)
        subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@t",
             "commit", "-qm", "base"],
            cwd=self.test_dir, check=True,
        )
        subprocess.run(
            ["git", "update-ref", "refs/gin/review/bead-t", "HEAD"],
            cwd=self.test_dir, check=True,
        )
        self.run_cli(
            "init", "--bead-id", "bead-t", "--repo-id", "r", "--repo-path", ".",
            "--include", "f.txt", "--review-ref", "refs/gin/review/bead-t",
            "--base-sha", "HEAD", "--actor-id", "worker-1",
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, self.script, *args],
            cwd=self.test_dir, capture_output=True, text=True,
        )

    def state(self):
        result = self.run_cli("status", "--bead-id", "bead-t")
        for line in result.stdout.splitlines():
            if line.startswith("State:"):
                return line.split(":", 1)[1].strip()
        raise AssertionError(f"no state in: {result.stdout} {result.stderr}")

    def advance_to_review_approved(self):
        self.run_cli("transition-requested", "--bead-id", "bead-t",
                     "--to", "review-requested", "--actor-role", "worker",
                     "--actor-id", "worker-1")
        out = self.run_cli("start-review", "--bead-id", "bead-t",
                           "--actor-id", "rev-1")
        lease = out.stdout.strip().split()[-1].rstrip(".")
        self.run_cli("approve", "--bead-id", "bead-t", "--actor-role", "reviewer",
                     "--actor-id", "rev-1", "--lease-id", lease)
        return lease

    def test_transition_to_ready_to_ship_actually_changes_the_state(self):
        lease = self.advance_to_review_approved()
        self.assertEqual("review-approved", self.state())

        first = self.run_cli("transition-requested", "--bead-id", "bead-t",
                             "--to", "verification-in-progress",
                             "--actor-role", "verifier", "--actor-id", "ver-1",
                             "--lease-id", lease)
        self.assertEqual(0, first.returncode, first.stderr)
        self.assertEqual("verification-in-progress", self.state())

        second = self.run_cli("transition-requested", "--bead-id", "bead-t",
                              "--to", "ready-to-ship",
                              "--actor-role", "verifier", "--actor-id", "ver-1",
                              "--lease-id", lease)
        self.assertEqual(0, second.returncode, second.stderr)
        self.assertEqual("ready-to-ship", self.state())

    def test_state_survives_a_from_scratch_log_replay(self):
        lease = self.advance_to_review_approved()
        self.run_cli("transition-requested", "--bead-id", "bead-t",
                     "--to", "verification-in-progress", "--actor-role", "verifier",
                     "--actor-id", "ver-1", "--lease-id", lease)
        self.run_cli("transition-requested", "--bead-id", "bead-t",
                     "--to", "ready-to-ship", "--actor-role", "verifier",
                     "--actor-id", "ver-1", "--lease-id", lease)

        _, proj = load_ledger("bead-t", base_dir=self.test_dir)
        self.assertEqual("ready-to-ship", proj.review_state)

    def test_unappliable_transition_exits_non_zero_without_printing_success(self):
        lease = self.advance_to_review_approved()
        before = self.state()

        result = self.run_cli("transition-requested", "--bead-id", "bead-t",
                              "--to", "not-a-state", "--actor-role", "verifier",
                              "--actor-id", "ver-1", "--lease-id", lease)

        self.assertNotEqual(0, result.returncode)
        self.assertNotIn("Transitioned", result.stdout)
        self.assertEqual(before, self.state())

    def test_transition_forbidden_by_the_bead_fsm_is_still_refused(self):
        lease = self.advance_to_review_approved()

        result = self.run_cli("transition-requested", "--bead-id", "bead-t",
                              "--to", "closed", "--actor-role", "verifier",
                              "--actor-id", "ver-1", "--lease-id", lease)

        self.assertNotEqual(0, result.returncode)
        self.assertEqual("review-approved", self.state())
