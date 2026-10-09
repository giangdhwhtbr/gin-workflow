from pathlib import Path
import sys
import unittest


SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core.assignments import RouteCandidate  # noqa: E402
from workflow_core.identity import AcceptanceIdentity, RepositorySnapshot  # noqa: E402
from workflow_core.manifests import ContextRequest, create_context_manifest  # noqa: E402
from workflow_core.review_coordinator import (  # noqa: E402
    ReviewContext,
    ReviewCoordinationError,
    ReviewCoordinator,
)
from workflow_providers.contracts import ReviewFinding, ReviewStatus  # noqa: E402
from workflow_providers.fakes import FakeReviewProvider  # noqa: E402
from workflow_providers.sequential_worker import SequentialWorkerAdapter  # noqa: E402
from workflow_providers.worker_dispatch import REQUIRED_RESULT_FIELDS, WorkerRequest  # noqa: E402


class ReviewCoordinatorTests(unittest.TestCase):
    def identity(self):
        return AcceptanceIdentity(
            "wf",
            "attempt-review-1",
            "api",
            (
                RepositorySnapshot(
                    "primary",
                    "scope-1",
                    "tree-1",
                    "checkpoint-1",
                    "refs/gin/review/api",
                ),
            ),
        )

    def test_review_skills_require_independence_affinity_and_terminal_gate(self):
        plugin = SCRIPTS.parent / "skills"
        review = (plugin / "review/SKILL.md").read_text(encoding="utf-8")
        receiving = (plugin / "gin-review-response/SKILL.md").read_text(encoding="utf-8")

        self.assertIn("must differ from the implementation provider", review)
        self.assertIn("maximum review cycles", review)
        self.assertIn("original provider/model route", review)
        self.assertIn("same-role, same-reasoning fallback", receiving)
        self.assertIn("must not close", receiving)

    def context(self):
        return ReviewContext(
            approved_scope=("src/api.py",),
            diff="diff --git a/src/api.py b/src/api.py",
            acceptance_criteria=("returns 200",),
            tests=({"command": "pytest", "outcome": "passed"},),
            evidence=({"kind": "test", "reference": "pytest"},),
        )

    def test_session_independence_accepts_same_provider_with_distinct_session(self):
        coordinator = ReviewCoordinator(FakeReviewProvider(), independence="session")
        cycle = coordinator.request_review(
            task_id="ui", cycle_number=1, provider_role="review", reasoning="high",
            implementation_route=("claude", "opus"),
            reviewer_candidates=(RouteCandidate("claude", "opus", False),),
            context=self.context(), implementation_session="impl-1", reviewer_session="rev-1")
        self.assertEqual(("claude", "rev-1"), (cycle.reviewer_provider, cycle.reviewer_session))

    def test_provider_independence_accepts_opencode_reviewer_only_for_another_implementer(self):
        coordinator = ReviewCoordinator(FakeReviewProvider(), independence="provider")
        kwargs = dict(
            task_id="ui", cycle_number=1, provider_role="review", reasoning="high",
            reviewer_candidates=(RouteCandidate("opencode", "provider_default", False),),
            context=self.context(),
        )
        cycle = coordinator.request_review(implementation_route=("claude", "opus"), **kwargs)
        self.assertEqual("opencode", cycle.reviewer_provider)
        with self.assertRaises(ReviewCoordinationError):
            coordinator.request_review(implementation_route=("opencode", "provider_default"), **kwargs)

    def test_session_independence_rejects_same_or_missing_session(self):
        coordinator = ReviewCoordinator(FakeReviewProvider(), independence="session")
        for reviewer_session in ("impl-1", ""):
            with self.subTest(reviewer_session=reviewer_session):
                with self.assertRaises(ReviewCoordinationError):
                    coordinator.request_review(
                        task_id="ui", cycle_number=1, provider_role="review", reasoning="high",
                        implementation_route=("claude", "opus"),
                        reviewer_candidates=(RouteCandidate("claude", "opus", False),),
                        context=self.context(), implementation_session="impl-1",
                        reviewer_session=reviewer_session)

    def test_unknown_independence_mode_is_rejected(self):
        with self.assertRaises(ValueError):
            ReviewCoordinator(FakeReviewProvider(), independence="team")

    def test_review_context_is_bounded_and_independent_provider_is_selected(self):
        coordinator = ReviewCoordinator(FakeReviewProvider(), require_independent=True)

        cycle = coordinator.request_review(
            task_id="api",
            cycle_number=1,
            provider_role="review",
            reasoning="high",
            implementation_route=("codex", "reasoning"),
            reviewer_candidates=(
                RouteCandidate("codex", "reasoning", False),
                RouteCandidate("claude", "opus", True),
            ),
            context=self.context(),
        )

        self.assertEqual(("claude", "opus"), cycle.reviewer_route)
        self.assertEqual(
            {"approved_scope", "diff", "acceptance_criteria", "tests", "evidence"},
            set(cycle.context.to_dict()),
        )
        self.assertNotIn("parent_context", repr(cycle.context.to_dict()))

    def test_independent_review_rejects_self_when_fallback_is_not_explicitly_allowed(self):
        coordinator = ReviewCoordinator(
            FakeReviewProvider(),
            require_independent=True,
            allow_self_review_fallback=False,
        )
        with self.assertRaisesRegex(ReviewCoordinationError, "independent reviewer"):
            coordinator.request_review(
                task_id="api",
                cycle_number=1,
                provider_role="review",
                reasoning="high",
                implementation_route=("codex", "reasoning"),
                reviewer_candidates=(RouteCandidate("codex", "reasoning", False),),
                context=self.context(),
            )

    def test_findings_return_to_original_route_then_same_tier_fallback(self):
        finding = ReviewFinding(
            "F-1", "IMPORTANT", "open", "src/api.py:12", "validate input", "unit test"
        )
        base = ReviewCoordinator(FakeReviewProvider())
        cycle = base.request_review(
            task_id="api",
            cycle_number=1,
            provider_role="backend",
            reasoning="high",
            implementation_route=("claude", "opus"),
            reviewer_candidates=(RouteCandidate("codex", "reasoning", False),),
            context=self.context(),
        )

        sticky = base.route_revision(
            cycle,
            (finding,),
            fallback_candidates=(RouteCandidate("codex", "reasoning", True),),
        )
        fallback = ReviewCoordinator(
            base.review_provider,
            route_available=lambda provider, model: provider != "claude",
        ).route_revision(
            cycle,
            (finding,),
            fallback_candidates=(RouteCandidate("codex", "reasoning", True),),
        )

        self.assertEqual(("claude", "opus"), (sticky.provider, sticky.model))
        self.assertEqual(("codex", "reasoning"), (fallback.provider, fallback.model))
        self.assertEqual(sticky.revision_identity, base.route_revision(cycle, (finding,)).revision_identity)

    def test_fourth_unresolved_cycle_requires_human_decision_and_blocks_closure(self):
        coordinator = ReviewCoordinator(FakeReviewProvider(), max_cycles=3)

        limited = coordinator.next_cycle("api", completed_cycles=3, unresolved=("F-1",))
        pending = coordinator.completion_decision(
            ReviewStatus("api", "review-approved", 1, ("F-1",)),
            acceptance_evidence_complete=True,
        )
        ready = coordinator.completion_decision(
            ReviewStatus("api", "review-approved", 1, ()),
            acceptance_evidence_complete=True,
        )

        self.assertEqual("human_decision_required", limited.status)
        self.assertEqual("review_pending", pending.status)
        self.assertEqual("ready_to_close", ready.status)

    def test_review_cycle_dispatches_bounded_worker_and_derives_structured_findings(self):
        captured = []
        adapter = SequentialWorkerAdapter(
            lambda payload: {
                "status": "completed",
                "task_id": payload["task_id"],
                "summary": "reviewed",
                "changed_files": [],
                "commits": [],
                "tests": [],
                "evidence": [{
                    "kind": "review_decision",
                    "decision": "changes_requested",
                }, {
                    "kind": "review_finding",
                    "finding_id": "F-9",
                    "severity": "IMPORTANT",
                    "status": "open",
                    "location": "src/api.py:12",
                    "expected_behavior": "validate input",
                    "evidence": "missing regression test",
                }],
                "blockers": [],
            }
        )

        class Dispatcher:
            def dispatch(self, request):
                captured.append(request)
                return adapter.dispatch(request)

            def collect_result(self, worker_id, timeout=None):
                return adapter.collect_result(worker_id, timeout)

        coordinator = ReviewCoordinator(
            FakeReviewProvider(), worker_dispatcher=Dispatcher()
        )
        cycle = coordinator.request_review(
            task_id="api",
            cycle_number=1,
            provider_role="review",
            reasoning="high",
            implementation_route=("claude", "opus"),
            reviewer_candidates=(RouteCandidate("codex", "reasoning", False),),
            context=self.context(),
        )
        template = WorkerRequest(
            "placeholder", (), create_context_manifest("review", ContextRequest()),
            {"mode": "isolated", "workspace_id": "ws-api", "branch": "task/api"},
            REQUIRED_RESULT_FIELDS, "api", "wf", "review-1", "review", "high",
        )

        execution = coordinator.dispatch_review(cycle, template)

        self.assertEqual("changes_requested", execution.status)
        self.assertEqual(("F-9",), tuple(item.finding_id for item in execution.findings))
        self.assertEqual(
            "changes-requested",
            coordinator.review_provider.status("api").value.state,
        )
        self.assertEqual(("codex", "reasoning"), captured[0].route_affinity)
        bounded = captured[0].generated_manifest.to_dict()["categories"]["required"]
        self.assertEqual(self.context().to_dict(), bounded[0]["review_context"])

    def test_review_dispatch_and_outcome_preserve_acceptance_identity_and_revision(self):
        captured_requests = []
        captured_outcomes = []
        identity = self.identity()

        class CapturingReviewProvider(FakeReviewProvider):
            def record_outcome(self, request, *, idempotency_key):
                captured_outcomes.append(request)
                return super().record_outcome(request, idempotency_key=idempotency_key)

        adapter = SequentialWorkerAdapter(
            lambda payload: {
                "schema_version": "2.3",
                "status": "completed",
                "task_id": payload["task_id"],
                "summary": "approved",
                "changed_files": [],
                "commits": [],
                "tests": [],
                "evidence": [{"kind": "review_decision", "decision": "approved"}],
                "blockers": [],
                "acceptance_identity": payload["acceptance_identity"],
            }
        )

        class Dispatcher:
            def dispatch(self, request):
                captured_requests.append(request)
                return adapter.dispatch(request)

            def collect_result(self, worker_id, timeout=None):
                return adapter.collect_result(worker_id, timeout)

        coordinator = ReviewCoordinator(
            CapturingReviewProvider(), worker_dispatcher=Dispatcher()
        )
        cycle = coordinator.request_review(
            task_id="api",
            cycle_number=1,
            provider_role="review",
            reasoning="high",
            implementation_route=("claude", "opus"),
            reviewer_candidates=(RouteCandidate("codex", "reasoning", False),),
            context=self.context(),
            acceptance_identity=identity,
            expected_ledger_revision=12,
        )
        template = WorkerRequest(
            "placeholder",
            (),
            create_context_manifest("review", ContextRequest()),
            {"mode": "isolated", "workspace_id": "ws-api", "branch": "task/api"},
            REQUIRED_RESULT_FIELDS,
            "api",
            "wf",
            "review-identity-1",
            "review",
            "high",
        )

        execution = coordinator.dispatch_review(cycle, template)

        self.assertEqual("approved", execution.status)
        self.assertEqual(identity, captured_requests[0].acceptance_identity)
        self.assertEqual(identity, captured_outcomes[0].acceptance_identity)
        self.assertEqual(12, captured_outcomes[0].expected_ledger_revision)

    def test_review_result_rejects_implicit_approval_edits_and_blockers(self):
        invalid_results = (
            {
                "status": "completed", "task_id": "api", "summary": "ambiguous",
                "changed_files": [], "commits": [], "tests": [], "evidence": [], "blockers": [],
            },
            {
                "status": "completed", "task_id": "api", "summary": "edited",
                "changed_files": ["src/api.py"], "commits": [], "tests": [],
                "evidence": [{"kind": "review_decision", "decision": "approved"}], "blockers": [],
            },
            {
                "status": "completed", "task_id": "api", "summary": "blocked",
                "changed_files": [], "commits": [], "tests": [],
                "evidence": [{"kind": "review_decision", "decision": "approved"}],
                "blockers": ["uncertain"],
            },
            {
                "status": "completed", "task_id": "api", "summary": "malformed",
                "changed_files": [], "commits": [], "tests": [],
                "evidence": [
                    {"kind": "review_decision", "decision": "changes_requested"},
                    {"kind": "review_finding", "finding_id": "F-bad", "status": "open"},
                ],
                "blockers": [],
            },
        )
        for index, raw in enumerate(invalid_results):
            with self.subTest(index=index):
                adapter = SequentialWorkerAdapter(lambda payload, raw=raw: raw)

                class Dispatcher:
                    def dispatch(self, request):
                        return adapter.dispatch(request)

                    def collect_result(self, worker_id, timeout=None):
                        return adapter.collect_result(worker_id, timeout)

                provider = FakeReviewProvider()
                coordinator = ReviewCoordinator(provider, worker_dispatcher=Dispatcher())
                cycle = coordinator.request_review(
                    task_id="api", cycle_number=1, provider_role="review", reasoning="high",
                    implementation_route=("claude", "opus"),
                    reviewer_candidates=(RouteCandidate("codex", "reasoning", False),),
                    context=self.context(),
                )
                template = WorkerRequest(
                    "placeholder", (), create_context_manifest("review", ContextRequest()),
                    {"mode": "isolated", "workspace_id": "ws-api", "branch": "task/api"},
                    REQUIRED_RESULT_FIELDS, "api", "wf", f"invalid-{index}", "review", "high",
                )

                with self.assertRaises(ReviewCoordinationError):
                    coordinator.dispatch_review(cycle, template)
                self.assertEqual("review-requested", provider.status("api").value.state)


if __name__ == "__main__":
    unittest.main()
