"""Optional AcceptanceIdentity threading through checkpoint/approve ledger paths."""

import json
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

from review_ledger.cli import (
    build_acceptance_identity_payload,
    get_checkpoint_identity_record,
    get_review_identity_record,
    load_ledger,
    mutate_ledger,
    save_ledger,
)
from review_ledger.events import EventLog, LedgerEvent
from review_ledger.projections import ReviewProjection
from workflow_core.identity import AcceptanceIdentity
from workflow_providers.evidence import CompositeEvidenceAuthority


SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "plugins/gin-workflow/src/scripts/review-ledger.py"
)


def complete_repository(repository_id="primary", suffix="a"):
    return {
        "repository_id": repository_id,
        "role": "primary",
        "repository_path": ".",
        "review_ref": f"refs/gin/review/{repository_id}",
        "checkpoint_ref": f"refs/gin/review/{repository_id}",
        "review_base_sha": "0" * 40,
        "reviewed_source_sha": f"sha-{suffix}",
        "checkpoint_sha": f"sha-{suffix}",
        "source_scope_hash": f"scope-{suffix}",
        "source_tree_hash": f"tree-{suffix}",
        "reviewed_source_tree_hash": f"tree-{suffix}",
        "source_identity_status": "complete",
    }


class AcceptanceIdentityPayloadTests(unittest.TestCase):
    def test_absent_identity_produces_no_payload_fields(self):
        self.assertEqual(
            {},
            build_acceptance_identity_payload(
                task_id="bead-1",
                workflow_id=None,
                attempt_id=None,
                repositories=[complete_repository()],
            ),
        )
        self.assertEqual(
            {},
            build_acceptance_identity_payload(
                task_id="bead-1",
                workflow_id="  ",
                attempt_id="",
                repositories=[],
            ),
        )

    def test_half_an_identity_is_rejected(self):
        with self.assertRaises(ValueError):
            build_acceptance_identity_payload(
                task_id="bead-1",
                workflow_id="wf-1",
                attempt_id=None,
                repositories=[complete_repository()],
            )
        with self.assertRaises(ValueError):
            build_acceptance_identity_payload(
                task_id="bead-1",
                workflow_id=None,
                attempt_id="at-1",
                repositories=[complete_repository()],
            )

    def test_incomplete_source_identity_is_rejected_before_append(self):
        legacy = {"repository_id": "primary", "review_ref": "ref"}
        with self.assertRaises(ValueError):
            build_acceptance_identity_payload(
                task_id="bead-1",
                workflow_id="wf-1",
                attempt_id="at-1",
                repositories=[legacy],
            )

    def test_supplied_identity_returns_flat_payload_fields(self):
        self.assertEqual(
            {"workflow_id": "wf-1", "attempt_id": "at-1", "task_id": "bead-1"},
            build_acceptance_identity_payload(
                task_id="bead-1",
                workflow_id="wf-1",
                attempt_id="at-1",
                repositories=[complete_repository()],
            ),
        )


class LedgerIdentityRecordTests(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.bead_id = "bead-identity"

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def _mutate(self, action, payload, role="worker", actor="w1"):
        return mutate_ledger(
            self.bead_id, action, payload, role, actor, base_dir=self.test_dir
        )

    def _prepare(self, repositories):
        self._mutate("ledger-created", {"repositories": repositories})

    def _reach_review_in_progress(self):
        self._mutate("implementation-complete", {})
        self._mutate("review-requested", {})
        self._mutate("review-started", {}, role="reviewer", actor="rev1")

    def _checkpoint(self, repositories, identity=True):
        payload = {"repositories": repositories}
        if identity:
            payload.update(
                build_acceptance_identity_payload(
                    task_id=self.bead_id,
                    workflow_id="wf-1",
                    attempt_id="at-1",
                    repositories=repositories,
                )
            )
        log, _ = self._mutate("source-checkpoint-created", payload)
        return log.events[-1].event_id

    def _approve(self, repositories, identity=True):
        payload = {
            "approved_repositories": repositories,
            "source_scope_hash": repositories[0]["source_scope_hash"],
            "terminal_findings": [],
        }
        if identity:
            payload.update(
                build_acceptance_identity_payload(
                    task_id=self.bead_id,
                    workflow_id="wf-1",
                    attempt_id="at-1",
                    repositories=repositories,
                )
            )
        log, _ = self._mutate("review-approved", payload, role="reviewer", actor="rev1")
        return log.events[-1].event_id

    def test_checkpoint_identity_record_matches_evidence_source_shape(self):
        repositories = [complete_repository()]
        self._prepare(repositories)
        event_id = self._checkpoint(repositories)

        record = get_checkpoint_identity_record(
            self.bead_id, event_id, base_dir=self.test_dir
        )
        self.assertIsNotNone(record)
        self.assertEqual(
            {
                "task_id",
                "checkpoint_event_id",
                "acceptance_identity",
                "repositories",
                "recorded_at",
            },
            set(record),
        )
        self.assertEqual(self.bead_id, record["task_id"])
        self.assertEqual(event_id, record["checkpoint_event_id"])
        identity = AcceptanceIdentity.from_mapping(record["acceptance_identity"])
        self.assertEqual("wf-1", identity.workflow_id)
        self.assertEqual("at-1", identity.attempt_id)
        # The exact invariant CompositeEvidenceAuthority._checkpoint() enforces.
        self.assertEqual(record["repositories"], identity.to_dict()["repositories"])
        self.assertTrue(record["recorded_at"])

    def test_checkpoint_without_identity_is_unchanged_and_has_no_record(self):
        repositories = [complete_repository()]
        self._prepare(repositories)
        event_id = self._checkpoint(repositories, identity=False)

        log, _ = load_ledger(self.bead_id, base_dir=self.test_dir)
        payload = log.events[-1].payload
        self.assertEqual({"repositories"}, set(payload))
        self.assertIsNone(
            get_checkpoint_identity_record(
                self.bead_id, event_id, base_dir=self.test_dir
            )
        )

    def test_checkpoint_record_is_none_for_unknown_or_mistyped_event(self):
        repositories = [complete_repository()]
        self._prepare(repositories)
        self._checkpoint(repositories)
        self.assertIsNone(
            get_checkpoint_identity_record(
                self.bead_id, "EV-999999", base_dir=self.test_dir
            )
        )
        # EV-000001 is `ledger-created`, not a source checkpoint.
        self.assertIsNone(
            get_checkpoint_identity_record(
                self.bead_id, "EV-000001", base_dir=self.test_dir
            )
        )

    def test_approval_identity_record_is_terminal_until_invalidated(self):
        repositories = [complete_repository()]
        self._prepare(repositories)
        self._reach_review_in_progress()
        event_id = self._approve(repositories)

        record = get_review_identity_record(
            self.bead_id, event_id, base_dir=self.test_dir
        )
        self.assertIsNotNone(record)
        self.assertEqual(event_id, record["review_event_id"])
        self.assertEqual("approved", record["status"])
        self.assertIs(True, record["terminal"])
        self.assertEqual(self.bead_id, record["task_id"])
        _log, projection = load_ledger(self.bead_id, base_dir=self.test_dir)
        self.assertEqual(projection.ledger_revision, record["ledger_revision"])
        identity = AcceptanceIdentity.from_mapping(record["acceptance_identity"])
        self.assertEqual(record["repositories"], identity.to_dict()["repositories"])

        self._mutate(
            "review-approval-invalidated",
            {"reason": "scope drift"},
            role="reviewer",
            actor="rev1",
        )
        after = get_review_identity_record(
            self.bead_id, event_id, base_dir=self.test_dir
        )
        self.assertIs(False, after["terminal"])

    def test_approval_record_passes_through_review_started_back_reference(self):
        repositories = [complete_repository()]
        self._prepare(repositories)
        self._reach_review_in_progress()
        payload = {
            "approved_repositories": repositories,
            "source_scope_hash": repositories[0]["source_scope_hash"],
            "terminal_findings": [],
            "review_event_id": "EV-000004",
            "workflow_id": "wf-1",
            "attempt_id": "at-1",
            "task_id": self.bead_id,
        }
        log, _ = self._mutate(
            "review-approved", payload, role="reviewer", actor="rev1"
        )
        record = get_review_identity_record(
            self.bead_id, log.events[-1].event_id, base_dir=self.test_dir
        )
        self.assertEqual("EV-000004", record["review_started_event_id"])
        self.assertNotEqual(record["review_started_event_id"], record["review_event_id"])

    def test_approval_without_identity_is_unchanged_and_has_no_record(self):
        repositories = [complete_repository()]
        self._prepare(repositories)
        self._reach_review_in_progress()
        event_id = self._approve(repositories, identity=False)

        log, _ = load_ledger(self.bead_id, base_dir=self.test_dir)
        self.assertEqual(
            {"approved_repositories", "source_scope_hash", "terminal_findings"},
            set(log.events[-1].payload),
        )
        self.assertIsNone(
            get_review_identity_record(self.bead_id, event_id, base_dir=self.test_dir)
        )

    def test_records_feed_composite_evidence_authority_unchanged(self):
        repositories = [complete_repository()]
        self._prepare(repositories)
        checkpoint_event_id = self._checkpoint(repositories)
        self._reach_review_in_progress()
        review_event_id = self._approve(repositories)

        checkpoint_record = get_checkpoint_identity_record(
            self.bead_id, checkpoint_event_id, base_dir=self.test_dir
        )
        review_record = dict(
            get_review_identity_record(
                self.bead_id, review_event_id, base_dir=self.test_dir
            )
        )
        # verification_event_id is owned by the verification record store, not
        # the review ledger; the caller merges it in.
        review_record["verification_event_id"] = "VER-1"
        verification_record = {
            "task_id": review_record["task_id"],
            "verification_event_id": "VER-1",
            "review_event_id": review_event_id,
            "acceptance_identity": review_record["acceptance_identity"],
            "status": "passed",
            "recorded_at": "2026-08-27T00:00:00Z",
        }
        authority = CompositeEvidenceAuthority(
            worker_resolver=lambda reference: None,
            checkpoint_resolver=lambda reference: (
                checkpoint_record if reference == checkpoint_event_id else None
            ),
            review_resolver=lambda reference: (
                review_record if reference == review_event_id else None
            ),
            verification_resolver=lambda reference: (
                verification_record if reference == "VER-1" else None
            ),
        )
        checkpoint_evidence = authority._checkpoint(checkpoint_event_id)
        self.assertEqual("recorded", checkpoint_evidence["outcome"])
        self.assertEqual(
            checkpoint_record["acceptance_identity"],
            checkpoint_evidence["acceptance_identity"],
        )
        review_evidence = authority._review(review_event_id)
        self.assertEqual("approved", review_evidence["outcome"])
        self.assertEqual(
            review_record["ledger_revision"],
            review_evidence["details"]["ledger_revision"],
        )


class LegacyLedgerCompatibilityTests(unittest.TestCase):
    """A ledger written before identity threading must still load and validate."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.bead_id = "legacy-bead"

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def _write_legacy_ledger(self):
        legacy_repository = {
            "repository_id": "primary",
            "role": "primary",
            "review_ref": "bead/legacy",
            "review_base_sha": "master",
            "reviewed_source_sha": "abc123",
        }
        actor = {"role": "worker", "actor_id": "w1"}
        reviewer = {"role": "reviewer", "actor_id": "rev1"}
        raw_events = [
            ("EV-000001", "ledger-created", actor, {"repositories": [legacy_repository]}),
            ("EV-000002", "implementation-complete", actor, {}),
            ("EV-000003", "review-requested", actor, {}),
            ("EV-000004", "review-started", reviewer, {}),
            (
                "EV-000005",
                "source-checkpoint-created",
                actor,
                {"repositories": [legacy_repository]},
            ),
            (
                "EV-000006",
                "review-approved",
                reviewer,
                {
                    "approved_repositories": [legacy_repository],
                    "source_scope_hash": "scopehash",
                    "terminal_findings": [],
                },
            ),
        ]
        log = EventLog()
        projection = ReviewProjection()
        for event_id, action, event_actor, payload in raw_events:
            event = LedgerEvent(
                event_id=event_id,
                action=action,
                timestamp="2026-01-01T00:00:00Z",
                actor=event_actor,
                payload=payload,
                previous_event_hash=None,
            )
            log.append(event)
            projection.apply_event(event)
        save_ledger(self.bead_id, log, projection, self.test_dir)

    def test_legacy_ledger_loads_and_validates(self):
        self._write_legacy_ledger()
        before = Path(self.test_dir, ".planning", self.bead_id, "review.json").read_bytes()

        log, projection = load_ledger(self.bead_id, base_dir=self.test_dir)
        self.assertEqual("review-approved", projection.review_state)
        self.assertEqual(6, projection.ledger_revision)
        for event in log.events:
            self.assertNotIn("workflow_id", event.payload)
            self.assertNotIn("attempt_id", event.payload)
        self.assertEqual("", projection.active_approval.workflow_id)

        process = subprocess.run(
            [sys.executable, str(SCRIPT), "validate", "--bead-id", self.bead_id],
            cwd=self.test_dir,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, process.returncode, process.stderr)
        self.assertIn("validation passed", process.stdout)
        self.assertEqual(
            before,
            Path(self.test_dir, ".planning", self.bead_id, "review.json").read_bytes(),
        )

    def test_legacy_ledger_exposes_no_identity_records(self):
        self._write_legacy_ledger()
        self.assertIsNone(
            get_checkpoint_identity_record(
                self.bead_id, "EV-000005", base_dir=self.test_dir
            )
        )
        self.assertIsNone(
            get_review_identity_record(
                self.bead_id, "EV-000006", base_dir=self.test_dir
            )
        )


class ReviewLedgerCommandIdentityTests(unittest.TestCase):
    """End-to-end coverage of the new optional flags on the real CLI."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.bead_id = "cli-identity"
        run = lambda *args: subprocess.run(
            args, cwd=self.test_dir, capture_output=True, check=True
        )
        run("git", "init")
        run("git", "config", "user.name", "Test User")
        run("git", "config", "user.email", "test@example.com")
        os.makedirs(os.path.join(self.test_dir, "src"))
        Path(self.test_dir, "src/main.py").write_text("print('base')\n")
        run("git", "add", "src/main.py")
        run("git", "commit", "-m", "base")
        self._cli(
            "init",
            "--bead-id", self.bead_id,
            "--repo-id", "primary",
            "--repo-path", ".",
            "--review-ref", f"refs/gin/review/{self.bead_id}",
            "--include", "src/",
            "--actor-id", "worker-1",
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def _cli(self, *args, expect_success=True):
        process = subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=self.test_dir,
            capture_output=True,
            text=True,
        )
        if expect_success:
            self.assertEqual(0, process.returncode, process.stderr)
        return process

    def _last_event(self):
        log, _ = load_ledger(self.bead_id, base_dir=self.test_dir)
        return log.events[-1]

    def _checkpoint_args(self, *extra):
        Path(self.test_dir, "src/main.py").write_text(f"print('{len(extra)}-{os.urandom(4).hex()}')\n")
        return (
            "checkpoint",
            "--bead-id", self.bead_id,
            "--repo-id", "primary",
            "--commit-msg", "feat: change",
            "--actor-id", "worker-1",
            *extra,
        )

    def test_checkpoint_command_without_flags_is_unchanged(self):
        self._cli(*self._checkpoint_args())
        event = self._last_event()
        self.assertEqual("source-checkpoint-created", event.action)
        self.assertEqual({"repositories"}, set(event.payload))
        self.assertIsNone(
            get_checkpoint_identity_record(
                self.bead_id, event.event_id, base_dir=self.test_dir
            )
        )

    def test_checkpoint_command_with_flags_attaches_identity(self):
        self._cli(
            *self._checkpoint_args("--workflow-id", "wf-9", "--attempt-id", "at-9")
        )
        event = self._last_event()
        self.assertEqual("wf-9", event.payload["workflow_id"])
        self.assertEqual("at-9", event.payload["attempt_id"])
        self.assertEqual(self.bead_id, event.payload["task_id"])

        record = get_checkpoint_identity_record(
            self.bead_id, event.event_id, base_dir=self.test_dir
        )
        identity = AcceptanceIdentity.from_mapping(record["acceptance_identity"])
        self.assertEqual("wf-9", identity.workflow_id)
        self.assertEqual(
            event.payload["repositories"][0]["checkpoint_sha"],
            identity.repositories[0].checkpoint_sha,
        )
        self.assertEqual(record["repositories"], identity.to_dict()["repositories"])

    def test_checkpoint_command_rejects_half_an_identity(self):
        process = self._cli(
            *self._checkpoint_args("--workflow-id", "wf-9"), expect_success=False
        )
        self.assertEqual(1, process.returncode)
        self.assertIn("must be supplied together", process.stderr)
        self.assertEqual("ledger-created", self._last_event().action)

    def _reach_review_in_progress(self):
        for action, role, actor in (
            ("implementation-complete", "worker", "worker-1"),
            ("review-requested", "worker", "worker-1"),
            ("review-started", "reviewer", "reviewer-1"),
        ):
            mutate_ledger(
                self.bead_id, action, {}, role, actor, base_dir=self.test_dir
            )

    def test_approve_command_without_flags_is_unchanged(self):
        self._reach_review_in_progress()
        self._cli(
            "approve", "--bead-id", self.bead_id, "--actor-id", "reviewer-1"
        )
        event = self._last_event()
        self.assertEqual(
            {"approved_repositories", "source_scope_hash", "terminal_findings"},
            set(event.payload),
        )
        self.assertIsNone(
            get_review_identity_record(
                self.bead_id, event.event_id, base_dir=self.test_dir
            )
        )

    def test_approve_command_with_flags_attaches_identity(self):
        self._reach_review_in_progress()
        self._cli(
            "approve",
            "--bead-id", self.bead_id,
            "--actor-id", "reviewer-1",
            "--workflow-id", "wf-9",
            "--attempt-id", "at-9",
        )
        event = self._last_event()
        record = get_review_identity_record(
            self.bead_id, event.event_id, base_dir=self.test_dir
        )
        self.assertIs(True, record["terminal"])
        self.assertEqual("approved", record["status"])
        identity = AcceptanceIdentity.from_mapping(record["acceptance_identity"])
        self.assertEqual(("wf-9", "at-9", self.bead_id), (
            identity.workflow_id, identity.attempt_id, identity.task_id
        ))
        # The CLI approve path does not record a review-started back-reference;
        # only ReviewLedgerProvider.record_outcome() populates that payload field.
        self.assertEqual("", record["review_started_event_id"])

    def test_approve_command_still_renders_and_validates(self):
        self._reach_review_in_progress()
        self._cli(
            "approve",
            "--bead-id", self.bead_id,
            "--actor-id", "reviewer-1",
            "--workflow-id", "wf-9",
            "--attempt-id", "at-9",
        )
        self._cli("validate", "--bead-id", self.bead_id)
        self._cli("render", "--bead-id", self.bead_id, "--check")
        payload = json.loads(
            Path(self.test_dir, ".planning", self.bead_id, "review.json").read_text()
        )
        self.assertEqual("1.0", payload["schema_version"])


    def test_init_command_with_flags_attaches_identity(self):
        bead_id = "cli-init-identity"
        self._cli(
            "init",
            "--bead-id", bead_id,
            "--repo-id", "primary",
            "--repo-path", ".",
            "--review-ref", f"refs/gin/review/{bead_id}",
            "--include", "src/",
            "--actor-id", "worker-1",
            "--workflow-id", "wf-init",
            "--attempt-id", "at-init",
        )
        log, _ = load_ledger(bead_id, base_dir=self.test_dir)
        event = log.events[0]
        self.assertEqual("ledger-created", event.action)
        self.assertEqual("wf-init", event.payload["workflow_id"])
        self.assertEqual("at-init", event.payload["attempt_id"])
        self.assertEqual(bead_id, event.payload["task_id"])

        record = get_checkpoint_identity_record(
            bead_id, event.event_id, base_dir=self.test_dir
        )
        self.assertIsNotNone(record)
        identity = AcceptanceIdentity.from_mapping(record["acceptance_identity"])
        self.assertEqual("wf-init", identity.workflow_id)
        self.assertEqual("at-init", identity.attempt_id)
        self.assertEqual(bead_id, identity.task_id)

    def test_init_command_rejects_half_an_identity(self):
        bead_id = "cli-init-half-identity"
        process = self._cli(
            "init",
            "--bead-id", bead_id,
            "--repo-id", "primary",
            "--repo-path", ".",
            "--review-ref", f"refs/gin/review/{bead_id}",
            "--include", "src/",
            "--actor-id", "worker-1",
            "--workflow-id", "wf-init",
            expect_success=False,
        )
        self.assertEqual(1, process.returncode)
        self.assertIn("must be supplied together", process.stderr)


if __name__ == "__main__":
    unittest.main()
