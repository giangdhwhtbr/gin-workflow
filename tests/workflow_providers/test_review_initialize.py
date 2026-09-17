"""Ledger bootstrap through the review capability.

Regression for a reported blocker: ``ReviewLedgerProvider.request()`` assumed
the ledger already existed, so a task whose review had never been initialized
could not enter review at all -- ``request`` returned ``unavailable`` with
"Ledger file not found" and there was no provider-level way to create it. The
``requesting-code-review`` skill directs initialization "through the review
capability", and repository policy forbids lifecycle skills from invoking
adapter scripts directly, so the bootstrap has to exist on the provider.
"""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../plugins/gin-workflow/src/scripts")
    ),
)

from workflow_providers.contracts import (  # noqa: E402
    OperationStatus,
    ReviewInitRequest,
    ReviewRequest,
)
from workflow_providers.fakes import FakeReviewProvider  # noqa: E402
from workflow_providers.review import ReviewLedgerProvider  # noqa: E402


def _git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _seed_repository(path: Path) -> None:
    """Build a real git repository so checkpoint/tree hashing is genuine."""
    path.mkdir(parents=True, exist_ok=True)
    _git("init", "-q", "-b", "main", cwd=path)
    _git("config", "user.email", "test@example.com", cwd=path)
    _git("config", "user.name", "Test", cwd=path)
    source = path / "src"
    source.mkdir()
    (source / "app.py").write_text("value = 1\n", encoding="utf-8")
    _git("add", "-A", cwd=path)
    _git("commit", "-q", "-m", "seed", cwd=path)


class ReviewInitializeTests(unittest.TestCase):
    def _request(self, repository_path: str, **overrides) -> ReviewInitRequest:
        fields = {
            "task_id": "task-init",
            "actor_id": "worker-1",
            "repository_id": "Backend",
            "repository_path": repository_path,
            "base_ref": "main",
            "review_ref": "refs/gin/review/task-init",
            "scope": {"include": ["src/**"]},
        }
        fields.update(overrides)
        return ReviewInitRequest(**fields)

    def test_initializes_a_real_ledger_for_a_nested_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            nested = root / ".planning/worktrees/attempt-1/backend"
            _seed_repository(nested)
            provider = ReviewLedgerProvider(root)

            result = provider.initialize(
                self._request(".planning/worktrees/attempt-1/backend"),
                idempotency_key="init-1",
            )

            self.assertIs(OperationStatus.SUCCESS, result.status)
            self.assertEqual("implementation-in-progress", result.value.state)
            self.assertTrue((root / ".planning/reviews/task-init/review.json").is_file())
            self.assertTrue((root / ".planning/reviews/task-init/review.md").is_file())

    def test_initialized_ledger_lets_request_proceed_instead_of_reporting_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            _seed_repository(root / "backend")
            provider = ReviewLedgerProvider(root)

            before = provider.request(
                ReviewRequest("task-init", "worker-1"), idempotency_key="req-0"
            )
            provider.initialize(self._request("backend"), idempotency_key="init-1")
            after = provider.request(
                ReviewRequest("task-init", "worker-1"), idempotency_key="req-1"
            )

            self.assertIs(OperationStatus.UNAVAILABLE, before.status)
            self.assertIn("Ledger file not found", before.message)
            self.assertIs(OperationStatus.SUCCESS, after.status)
            self.assertEqual("review-requested", after.value.state)

    def test_records_genuine_checkpoint_and_source_tree_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            nested = root / "backend"
            _seed_repository(nested)
            provider = ReviewLedgerProvider(root)

            provider.initialize(self._request("backend"), idempotency_key="init-1")

            from review_ledger.cli import load_ledger

            projection = load_ledger("task-init", str(root))[1]
            recorded = projection.repositories[0]
            head = subprocess.run(
                ["git", "rev-parse", "--verify", "HEAD"],
                cwd=nested, capture_output=True, text=True, check=True,
            ).stdout.strip()

            self.assertEqual("complete", recorded["source_identity_status"])
            self.assertEqual("Backend", recorded["repository_id"])
            self.assertEqual("backend", recorded["repository_path"])
            self.assertEqual(head, recorded["review_base_sha"])
            for field in ("checkpoint_sha", "source_scope_hash", "source_tree_hash"):
                self.assertTrue(str(recorded[field]).strip())

    def test_initializes_ledger_with_acceptance_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            nested = root / "backend"
            _seed_repository(nested)
            provider = ReviewLedgerProvider(root)

            request = self._request(
                "backend", workflow_id="wf-prov-init", attempt_id="at-prov-init"
            )
            result = provider.initialize(request, idempotency_key="init-identity-1")

            self.assertIs(OperationStatus.SUCCESS, result.status)

            from review_ledger.cli import get_checkpoint_identity_record, load_ledger

            log, _ = load_ledger("task-init", str(root))
            event = log.events[0]
            self.assertEqual("wf-prov-init", event.payload["workflow_id"])
            self.assertEqual("at-prov-init", event.payload["attempt_id"])

            record = get_checkpoint_identity_record("task-init", "EV-000001", base_dir=str(root))
            self.assertIsNotNone(record)
            self.assertEqual("wf-prov-init", record["acceptance_identity"]["workflow_id"])
            self.assertEqual("at-prov-init", record["acceptance_identity"]["attempt_id"])

    def test_initialize_is_idempotent_and_never_reinitializes_an_existing_ledger(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            _seed_repository(root / "backend")
            provider = ReviewLedgerProvider(root)
            request = self._request("backend")

            first = provider.initialize(request, idempotency_key="init-1")
            ledger = (root / ".planning/reviews/task-init/review.json").read_bytes()
            replay = provider.initialize(request, idempotency_key="init-1")
            fresh_key = provider.initialize(request, idempotency_key="init-2")

            self.assertIs(OperationStatus.SUCCESS, first.status)
            self.assertFalse(first.idempotent)
            self.assertTrue(replay.idempotent)
            self.assertTrue(fresh_key.idempotent)
            self.assertEqual(
                ledger, (root / ".planning/reviews/task-init/review.json").read_bytes()
            )

    def test_rejects_a_repository_path_escaping_the_provider_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            outside = root.parent / f"{root.name}-outside"
            _seed_repository(outside)
            try:
                result = ReviewLedgerProvider(root).initialize(
                    self._request("../" + outside.name), idempotency_key="init-1"
                )
            finally:
                subprocess.run(["rm", "-rf", str(outside)], check=False)

            self.assertIs(OperationStatus.INVALID, result.status)
            self.assertIn("escapes provider root", result.message)
            self.assertFalse((root / ".planning/reviews/task-init/review.json").exists())

    def test_rejects_incomplete_identity_and_empty_scope_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            _seed_repository(root / "backend")
            provider = ReviewLedgerProvider(root)

            cases = {
                "actor": self._request("backend", actor_id="  "),
                "repository_id": self._request("backend", repository_id=""),
                "base_ref": self._request("backend", base_ref=""),
                "review_ref": self._request("backend", review_ref=""),
                "scope": self._request("backend", scope={}),
                "missing_path": self._request("does-not-exist"),
            }
            for name, request in cases.items():
                with self.subTest(case=name):
                    result = provider.initialize(request, idempotency_key=f"k-{name}")
                    self.assertIs(OperationStatus.INVALID, result.status)
            self.assertFalse((root / ".planning/reviews/task-init/review.json").exists())

    def test_fake_review_provider_satisfies_the_same_initialize_contract(self):
        provider = FakeReviewProvider()
        request = ReviewInitRequest(
            task_id="task-init",
            actor_id="worker-1",
            repository_id="Backend",
            repository_path="backend",
            base_ref="main",
            review_ref="refs/gin/review/task-init",
            scope={"include": ["src/**"]},
        )

        first = provider.initialize(request, idempotency_key="init-1")
        again = provider.initialize(request, idempotency_key="init-2")
        invalid = provider.initialize(
            ReviewInitRequest(
                task_id="",
                actor_id="worker-1",
                repository_id="Backend",
                repository_path="backend",
                base_ref="main",
                review_ref="refs/gin/review/task-init",
                scope={"include": ["src/**"]},
            ),
            idempotency_key="init-3",
        )

        self.assertIs(OperationStatus.SUCCESS, first.status)
        self.assertTrue(again.idempotent)
        self.assertIs(OperationStatus.INVALID, invalid.status)


if __name__ == "__main__":
    unittest.main()
