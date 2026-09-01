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

from datetime import datetime, timedelta, timezone

from review_ledger.cli import (
    build_resync_lease_operations,
    build_start_review_operations,
    initialize_ledger,
    load_ledger,
    mutate_ledger,
    resync_lease,
    start_review,
)
from review_ledger.lease import (
    LeaseError,
    format_utc_timestamp,
    validate_lease_for_write,
)
from review_ledger.projections import LeaseProjection, ReviewProjection


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


class TestForcedLeaseTakeover(unittest.TestCase):
    """A review lease held by an actor that never came back is a hard wall.

    start-review only ever broke an *expired* lease, so a stalled reviewer
    blocked every other reviewer until the TTL ran out. Taking the lease early
    is allowed, but only deliberately and only on the record.
    """

    def _projection_with_active_lease(self, actor_id, expires_at):
        projection = ReviewProjection()
        projection.review_state = "review-requested"
        projection.ledger_revision = 3
        projection.active_lease = LeaseProjection(
            "lease-held", "reviewer", actor_id, "2026-01-01T00:00:00Z", expires_at, 3
        )
        return projection

    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.future = format_utc_timestamp(self.now + timedelta(minutes=10))

    def test_active_lease_of_another_actor_still_blocks_without_the_flag(self):
        projection = self._projection_with_active_lease("reviewer-a", self.future)
        with self.assertRaises(LeaseError):
            build_start_review_operations(projection, "reviewer-b", now=self.now)

    def test_force_takeover_breaks_the_held_lease_before_acquiring(self):
        projection = self._projection_with_active_lease("reviewer-a", self.future)
        operations, lease_id = build_start_review_operations(
            projection,
            "reviewer-b",
            requested_lease_id="lease-new",
            now=self.now,
            force_takeover=True,
            takeover_reason="reviewer-a went offline mid-review",
        )
        self.assertEqual("lease-new", lease_id)
        self.assertEqual(
            ["lease-broken", "lease-acquired", "review-started"],
            [action for action, _payload, _role, _actor in operations],
        )
        broken_payload = operations[0][1]
        self.assertEqual("lease-held", broken_payload["lease_id"])
        self.assertEqual("takeover", broken_payload["reason"])
        self.assertEqual("reviewer-a went offline mid-review", broken_payload["detail"])
        self.assertEqual("lease-new", broken_payload["replaced_by"])

    def test_force_takeover_without_a_reason_is_refused(self):
        projection = self._projection_with_active_lease("reviewer-a", self.future)
        with self.assertRaises(ValueError):
            build_start_review_operations(
                projection, "reviewer-b", now=self.now, force_takeover=True
            )

    def test_force_takeover_of_ones_own_lease_still_renews_it(self):
        """Takeover is about other actors; the holder's own retry must not
        churn the lease id, which existing callers depend on."""
        projection = self._projection_with_active_lease("reviewer-a", self.future)
        operations, lease_id = build_start_review_operations(
            projection,
            "reviewer-a",
            now=self.now,
            force_takeover=True,
            takeover_reason="retry",
        )
        self.assertEqual("lease-held", lease_id)
        self.assertEqual(
            ["lease-renewed", "review-started"],
            [action for action, _payload, _role, _actor in operations],
        )


class TestForcedTakeoverEndToEnd(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.bead_id = "bead-takeover"
        mutate_ledger(
            self.bead_id, "ledger-created", {"repositories": []},
            "worker", "w1", base_dir=self.test_dir,
        )
        mutate_ledger(self.bead_id, "implementation-complete", {}, "worker", "w1", base_dir=self.test_dir)
        mutate_ledger(self.bead_id, "review-requested", {}, "worker", "w1", base_dir=self.test_dir)
        start_review(self.bead_id, "reviewer-a", base_dir=self.test_dir, requested_lease_id="lease-a")

    def tearDown(self):
        shutil.rmtree(self.test_dir)
    def test_takeover_transfers_ownership_and_leaves_an_audit_trail(self):
        with self.assertRaises(LeaseError):
            start_review(self.bead_id, "reviewer-b", base_dir=self.test_dir)

        log, projection = start_review(
            self.bead_id,
            "reviewer-b",
            base_dir=self.test_dir,
            requested_lease_id="lease-b",
            force_takeover=True,
            takeover_reason="reviewer-a is unreachable",
        )
        self.assertEqual("reviewer-b", projection.active_lease.actor_id)
        self.assertEqual("lease-b", projection.active_lease.lease_id)
        self.assertEqual(
            ["lease-broken", "lease-acquired"],
            [event.action for event in log.events[-2:]],
        )
        broken = log.events[-2]
        self.assertEqual("takeover", broken.payload["reason"])
        self.assertEqual("reviewer-a is unreachable", broken.payload["detail"])
        self.assertEqual("lease-a", broken.payload["lease_id"])

    def test_the_displaced_reviewer_can_no_longer_write(self):
        start_review(
            self.bead_id, "reviewer-b", base_dir=self.test_dir,
            requested_lease_id="lease-b", force_takeover=True,
            takeover_reason="stalled",
        )
        with self.assertRaises(LeaseError):
            mutate_ledger(
                self.bead_id, "finding-created",
                {"finding_id": "F-001", "severity": "MINOR"},
                "reviewer", "reviewer-a", base_dir=self.test_dir, lease_id="lease-a",
            )


class TestResyncLease(unittest.TestCase):
    """Ledger-revision drift used to be a one-way door.

    validate_lease_for_write demands projection.ledger_revision ==
    lease.current_ledger_revision. Commit a25e94c taught start-review to break
    and reacquire an *expired* lease, but a lease whose recorded revision fell
    behind had no recovery at all: every write raised LeaseError forever.
    resync-lease re-points the lease at the ledger, for its own holder only.
    """

    def _drifted(self):
        projection = ReviewProjection()
        projection.review_state = "review-in-progress"
        projection.ledger_revision = 9
        projection.active_lease = LeaseProjection(
            "lease-held",
            "reviewer",
            "reviewer-a",
            "2026-01-01T00:00:00Z",
            format_utc_timestamp(datetime.now(timezone.utc) + timedelta(minutes=10)),
            4,
        )
        return projection

    def test_resync_repoints_the_lease_at_the_current_ledger_revision(self):
        projection = self._drifted()
        operations, lease_id = build_resync_lease_operations(
            projection, "reviewer-a", "lease-held"
        )
        self.assertEqual("lease-held", lease_id)
        self.assertEqual(
            ["lease-resynced"],
            [action for action, _payload, _role, _actor in operations],
        )
        payload = operations[0][1]
        self.assertEqual("lease-held", payload["lease_id"])
        self.assertEqual(9, payload["ledger_revision"])

    def test_resync_by_a_different_actor_is_refused(self):
        projection = self._drifted()
        with self.assertRaises(LeaseError):
            build_resync_lease_operations(projection, "reviewer-b", "lease-held")

    def test_resync_of_a_lease_that_is_not_the_active_one_is_refused(self):
        projection = self._drifted()
        with self.assertRaises(LeaseError):
            build_resync_lease_operations(projection, "reviewer-a", "lease-stale")

    def test_resync_without_an_active_lease_is_refused(self):
        projection = ReviewProjection()
        projection.ledger_revision = 3
        with self.assertRaises(LeaseError):
            build_resync_lease_operations(projection, "reviewer-a", "lease-held")


class TestResyncLeaseEndToEnd(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.bead_id = "bead-resync"
        mutate_ledger(
            self.bead_id, "ledger-created", {"repositories": []},
            "worker", "w1", base_dir=self.test_dir,
        )
        mutate_ledger(self.bead_id, "implementation-complete", {}, "worker", "w1", base_dir=self.test_dir)
        mutate_ledger(self.bead_id, "review-requested", {}, "worker", "w1", base_dir=self.test_dir)
        start_review(self.bead_id, "reviewer-a", base_dir=self.test_dir, requested_lease_id="lease-a")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_holder_can_resync_and_keep_writing(self):
        _log, projection = resync_lease(
            self.bead_id, "reviewer-a", "lease-a", base_dir=self.test_dir
        )
        self.assertEqual("lease-resynced", _log.events[-1].action)
        self.assertEqual(
            projection.ledger_revision, projection.active_lease.current_ledger_revision
        )
        mutate_ledger(
            self.bead_id, "finding-created",
            {"finding_id": "F-001", "severity": "MINOR"},
            "reviewer", "reviewer-a", base_dir=self.test_dir, lease_id="lease-a",
        )
        _, after = load_ledger(self.bead_id, base_dir=self.test_dir)
        self.assertIn("F-001", after.findings)

    def test_resync_is_exempt_from_the_lease_check_it_repairs(self):
        """Registering the action as lease-exempt is what makes recovery possible.

        Without that registration the resync write is itself gated on the lease
        being in sync, so the one event that clears revision drift could never
        be appended while the drift lasted. Exemption is observable here as the
        write succeeding with no lease id supplied at all.
        """
        log, _ = mutate_ledger(
            self.bead_id, "lease-resynced",
            {"lease_id": "lease-a", "ledger_revision": 4},
            "reviewer", "reviewer-a", base_dir=self.test_dir,
        )
        self.assertEqual("lease-resynced", log.events[-1].action)

    def test_non_holder_resync_leaves_the_ledger_untouched(self):
        json_path = Path(self.test_dir, ".planning", self.bead_id, "review.json")
        before = json_path.read_bytes()
        with self.assertRaises(LeaseError):
            resync_lease(self.bead_id, "reviewer-b", "lease-a", base_dir=self.test_dir)
        self.assertEqual(before, json_path.read_bytes())


class TestRecoverySubcommands(unittest.TestCase):
    """The recovery paths must be reachable from the CLI, not only the library."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.bead_id = "bead-subcommand"
        self.script = (
            Path(__file__).resolve().parents[2]
            / "plugins/gin-workflow/src/scripts/review-ledger.py"
        )
        mutate_ledger(
            self.bead_id, "ledger-created", {"repositories": []},
            "worker", "w1", base_dir=self.test_dir,
        )
        mutate_ledger(self.bead_id, "implementation-complete", {}, "worker", "w1", base_dir=self.test_dir)
        mutate_ledger(self.bead_id, "review-requested", {}, "worker", "w1", base_dir=self.test_dir)
        start_review(self.bead_id, "reviewer-a", base_dir=self.test_dir, requested_lease_id="lease-a")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def _run(self, *argv):
        return subprocess.run(
            [sys.executable, str(self.script), *argv],
            cwd=self.test_dir,
            capture_output=True,
            text=True,
        )

    def test_resync_lease_subcommand_appends_the_event(self):
        process = self._run(
            "resync-lease", "--bead-id", self.bead_id,
            "--actor-id", "reviewer-a", "--lease-id", "lease-a",
        )
        self.assertEqual(0, process.returncode, process.stderr)
        log, _ = load_ledger(self.bead_id, base_dir=self.test_dir)
        self.assertEqual("lease-resynced", log.events[-1].action)

    def test_resync_lease_subcommand_refuses_a_non_holder(self):
        process = self._run(
            "resync-lease", "--bead-id", self.bead_id,
            "--actor-id", "reviewer-b", "--lease-id", "lease-a",
        )
        self.assertEqual(1, process.returncode)
        log, _ = load_ledger(self.bead_id, base_dir=self.test_dir)
        self.assertNotEqual("lease-resynced", log.events[-1].action)

    def test_force_takeover_subcommand_requires_a_reason(self):
        process = self._run(
            "start-review", "--bead-id", self.bead_id,
            "--actor-id", "reviewer-b", "--force-takeover",
        )
        self.assertEqual(1, process.returncode, process.stdout)
        self.assertIn("reason", process.stderr.lower())
        _, projection = load_ledger(self.bead_id, base_dir=self.test_dir)
        self.assertEqual("reviewer-a", projection.active_lease.actor_id)

    def test_force_takeover_subcommand_transfers_the_lease(self):
        process = self._run(
            "start-review", "--bead-id", self.bead_id,
            "--actor-id", "reviewer-b", "--lease-id", "lease-b",
            "--force-takeover", "--reason", "reviewer-a is unreachable",
        )
        self.assertEqual(0, process.returncode, process.stderr)
        log, projection = load_ledger(self.bead_id, base_dir=self.test_dir)
        self.assertEqual("reviewer-b", projection.active_lease.actor_id)
        self.assertEqual("takeover", log.events[-2].payload["reason"])
        self.assertEqual("reviewer-a is unreachable", log.events[-2].payload["detail"])

    def test_approve_refuses_stale_checkpoint_hash_and_succeeds_after_refresh(self):
        bead_id = "bead-drift"
        repo_dir = os.path.join(self.test_dir, "repo")
        os.makedirs(repo_dir, exist_ok=True)
        subprocess.check_call(["git", "init", "-q", "."], cwd=repo_dir)
        test_file = os.path.join(repo_dir, "code.py")
        with open(test_file, "w") as f:
            f.write("print(1)\n")
        subprocess.check_call(["git", "add", "code.py"], cwd=repo_dir)
        subprocess.check_call(["git", "commit", "-m", "initial", "-q"], cwd=repo_dir)

        # Initialize ledger
        mutate_ledger(
            bead_id,
            "ledger-created",
            {
                "review_state": "review-in-progress",
                "repositories": [
                    {
                        "repository_id": "primary",
                        "role": "primary",
                        "repository_path": repo_dir,
                        "review_ref": "refs/gin/review/test",
                        "review_base_sha": "sha1",
                        "reviewed_source_sha": "sha1",
                        "source_tree_hash": "stale_hash",
                        "reviewed_source_tree_hash": "stale_hash",
                    }
                ],
                "source_scope": {"included_paths": ["code.py"]},
            },
            "worker",
            "w1",
            base_dir=self.test_dir,
        )

        # 1. approve should fail due to tree hash mismatch
        process_app = self._run("approve", "--bead-id", bead_id, "--actor-id", "reviewer-1")
        self.assertEqual(1, process_app.returncode)
        self.assertIn("Refusing approval", process_app.stderr)
        self.assertIn("checkpoint", process_app.stderr)

        # 2. validate should fail due to tree hash mismatch
        process_val = self._run("validate", "--bead-id", bead_id)
        self.assertEqual(1, process_val.returncode)
        self.assertIn("Ledger validation failed", process_val.stderr)

        # 3. Create fresh checkpoint
        from review_ledger.source_identity import compute_source_tree_hash
        fresh_hash = compute_source_tree_hash("primary", repo_dir, {"included_paths": ["code.py"]})
        mutate_ledger(
            bead_id,
            "source-checkpoint-created",
            {
                "review_state": "review-in-progress",
                "repositories": [
                    {
                        "repository_id": "primary",
                        "role": "primary",
                        "repository_path": repo_dir,
                        "review_ref": "refs/gin/review/test",
                        "review_base_sha": "sha1",
                        "reviewed_source_sha": "sha1",
                        "source_tree_hash": fresh_hash,
                        "reviewed_source_tree_hash": fresh_hash,
                    }
                ]
            },
            "worker",
            "w1",
            base_dir=self.test_dir,
        )

        # 4. Now approve and validate succeed
        process_app_ok = self._run("approve", "--bead-id", bead_id, "--actor-id", "reviewer-1")
        self.assertEqual(0, process_app_ok.returncode, process_app_ok.stderr)

        process_val_ok = self._run("validate", "--bead-id", bead_id)
        self.assertEqual(0, process_val_ok.returncode, process_val_ok.stderr)

    def test_change_scope_invalidates_approval_state(self):
        bead_id = "bead-scope"
        mutate_ledger(
            bead_id,
            "ledger-created",
            {
                "review_state": "review-approved",
                "source_scope": {"included_paths": ["src/a.py"]},
            },
            "worker",
            "w1",
            base_dir=self.test_dir,
        )
        process = self._run(
            "change-scope",
            "--bead-id",
            bead_id,
            "--actor-id",
            "reviewer-1",
            "--add-include",
            "src/b.py",
            "--reason",
            "expanding scope",
        )
        self.assertEqual(0, process.returncode, process.stderr)
        self.assertIn("invalidated", process.stdout.lower())

        _, proj = load_ledger(bead_id, base_dir=self.test_dir)
        self.assertIsNone(proj.active_approval)
        self.assertEqual("review-requested", proj.review_state)


