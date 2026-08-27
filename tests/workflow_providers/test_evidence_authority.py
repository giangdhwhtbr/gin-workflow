from pathlib import Path
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from review_ledger.cli import (  # noqa: E402
    build_acceptance_identity,
    build_acceptance_identity_payload,
    mutate_ledger,
)
from workflow_core.events import WorkflowEvent, WorkflowEventStore  # noqa: E402
from workflow_core.identity import AcceptanceIdentity, RepositorySnapshot  # noqa: E402
from workflow_providers.contracts import EvidenceCategory  # noqa: E402
from workflow_providers.evidence import CompositeEvidenceAuthority, record_verification  # noqa: E402
from workflow_providers.evidence_authority import build_composite_evidence_authority  # noqa: E402


def _repository(suffix="a"):
    return {
        "repository_id": "primary",
        "role": "primary",
        "repository_path": ".",
        "review_ref": f"refs/gin/review/{suffix}",
        "checkpoint_ref": f"refs/gin/review/{suffix}",
        "review_base_sha": "0" * 40,
        "reviewed_source_sha": f"sha-{suffix}",
        "checkpoint_sha": f"sha-{suffix}",
        "source_scope_hash": f"scope-{suffix}",
        "source_tree_hash": f"tree-{suffix}",
        "reviewed_source_tree_hash": f"tree-{suffix}",
        "source_identity_status": "complete",
    }


class BuildCompositeEvidenceAuthorityTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.bead_id = "bead-authority"
        self.event_store = WorkflowEventStore(
            self.root / ".agent-workflow/runtime/events.jsonl"
        )

    def _mutate(self, action, payload, role="worker", actor="w1"):
        return mutate_ledger(
            self.bead_id, action, payload, role, actor, base_dir=str(self.root)
        )

    def test_returns_a_real_composite_evidence_authority(self):
        authority = build_composite_evidence_authority(self.root, self.event_store)
        self.assertIsInstance(authority, CompositeEvidenceAuthority)

    def test_worker_resolver_resolves_a_real_persisted_worker_result_event(self):
        identity = AcceptanceIdentity(
            "wf-1",
            "attempt-1",
            "task-1",
            (RepositorySnapshot("primary", "scope-1", "tree-1", "checkpoint-1", "refs/gin/review/task-1"),),
        ).to_dict()
        self.event_store.append(
            WorkflowEvent.create(
                event_type="worker.result",
                workflow_id="wf-1",
                task_id="task-1",
                payload={
                    "worker_id": "worker-1",
                    "status": "completed",
                    "schema_version": "2.3",
                    "request_acceptance_identity": identity,
                    "result_acceptance_identity": identity,
                    "request_workspace_id": "ws-task-1",
                    "tests": [
                        {
                            "argv": ["python3", "-m", "unittest"],
                            "exit_code": 0,
                            "started_at": "2026-08-20T09:58:00Z",
                            "finished_at": "2026-08-20T09:59:00Z",
                            "workspace_id": "ws-task-1",
                            "repository_id": "primary",
                            "attempt_id": "attempt-1",
                            "source_tree_hash": "tree-1",
                        }
                    ],
                },
                idempotency_key="wf-1:task-1:worker.result:worker-1",
            )
        )

        authority = build_composite_evidence_authority(self.root, self.event_store)
        resolved = authority.resolve(EvidenceCategory.TESTS, "worker-1")

        self.assertIsNotNone(resolved)
        self.assertEqual("passed", resolved["outcome"])
        self.assertEqual("task-1", resolved["task_id"])

    def test_worker_resolver_returns_none_for_an_unknown_worker_id(self):
        authority = build_composite_evidence_authority(self.root, self.event_store)
        self.assertIsNone(authority.resolve(EvidenceCategory.TESTS, "no-such-worker"))

    def test_checkpoint_and_review_resolvers_read_a_real_ledger_end_to_end(self):
        repositories = [_repository()]
        self._mutate("ledger-created", {"repositories": repositories})
        checkpoint_payload = {"repositories": repositories}
        checkpoint_payload.update(
            build_acceptance_identity_payload(
                task_id=self.bead_id,
                workflow_id="wf-1",
                attempt_id="attempt-1",
                repositories=repositories,
            )
        )
        log, _ = self._mutate("source-checkpoint-created", checkpoint_payload)
        checkpoint_event_id = log.events[-1].event_id

        self._mutate("implementation-complete", {})
        self._mutate("review-requested", {})
        self._mutate("review-started", {}, role="reviewer", actor="rev1")
        approve_payload = {
            "approved_repositories": repositories,
            "source_scope_hash": repositories[0]["source_scope_hash"],
            "terminal_findings": [],
        }
        approve_payload.update(
            build_acceptance_identity_payload(
                task_id=self.bead_id,
                workflow_id="wf-1",
                attempt_id="attempt-1",
                repositories=repositories,
            )
        )
        log, _ = self._mutate(
            "review-approved", approve_payload, role="reviewer", actor="rev1"
        )
        review_event_id = log.events[-1].event_id

        authority = build_composite_evidence_authority(self.root, self.event_store)

        checkpoint_reference = f"{self.bead_id}:{checkpoint_event_id}"
        resolved_checkpoint = authority.resolve(
            EvidenceCategory.REPOSITORY, checkpoint_reference
        )
        self.assertIsNotNone(resolved_checkpoint)
        self.assertEqual("recorded", resolved_checkpoint["outcome"])
        self.assertEqual(self.bead_id, resolved_checkpoint["task_id"])

        # Not yet resolvable: no verification has been recorded against this
        # review yet, so the composite review category has no evidence.
        review_reference = f"{self.bead_id}:{review_event_id}"
        self.assertIsNone(authority.resolve(EvidenceCategory.REVIEWS, review_reference))

        identity = build_acceptance_identity(
            task_id=self.bead_id,
            workflow_id="wf-1",
            attempt_id="attempt-1",
            repositories=repositories,
        )
        record_verification(
            self.event_store,
            workflow_id="wf-1",
            task_id=self.bead_id,
            verification_event_id="VER-1",
            review_event_id=review_reference,
            acceptance_identity=identity,
            status="passed",
        )

        resolved_review = authority.resolve(EvidenceCategory.REVIEWS, review_reference)
        self.assertIsNotNone(resolved_review)
        self.assertEqual("approved", resolved_review["outcome"])
        self.assertEqual(self.bead_id, resolved_review["task_id"])
        self.assertEqual("VER-1", resolved_review["details"]["verification_event_id"])

    def test_checkpoint_and_review_resolvers_return_none_for_malformed_reference(self):
        authority = build_composite_evidence_authority(self.root, self.event_store)
        self.assertIsNone(authority.resolve(EvidenceCategory.REPOSITORY, "no-colon-here"))
        self.assertIsNone(authority.resolve(EvidenceCategory.REVIEWS, "no-colon-here"))

    def test_checkpoint_and_review_resolvers_return_none_for_unknown_bead(self):
        authority = build_composite_evidence_authority(self.root, self.event_store)
        self.assertIsNone(
            authority.resolve(EvidenceCategory.REPOSITORY, "no-such-bead:EV-000001")
        )
        self.assertIsNone(
            authority.resolve(EvidenceCategory.REVIEWS, "no-such-bead:EV-000001")
        )


if __name__ == "__main__":
    unittest.main()
