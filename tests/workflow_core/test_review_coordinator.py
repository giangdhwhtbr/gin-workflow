from pathlib import Path
import sys
import unittest


SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core.assignments import RouteCandidate  # noqa: E402
from workflow_core.review_coordinator import (  # noqa: E402
    ReviewContext,
    ReviewCoordinationError,
    ReviewCoordinator,
)
from workflow_providers.contracts import ReviewFinding, ReviewStatus  # noqa: E402
from workflow_providers.fakes import FakeReviewProvider  # noqa: E402


class ReviewCoordinatorTests(unittest.TestCase):
    def test_review_skills_require_independence_affinity_and_terminal_gate(self):
        plugin = SCRIPTS.parent / "skills"
        cross_agent = (plugin / "cross-agent-code-review/SKILL.md").read_text(encoding="utf-8")
        requesting = (plugin / "requesting-code-review/SKILL.md").read_text(encoding="utf-8")
        receiving = (plugin / "receiving-code-review/SKILL.md").read_text(encoding="utf-8")

        self.assertIn("must differ from the implementation provider", cross_agent)
        self.assertIn("maximum review cycles", cross_agent)
        self.assertIn("original provider/model route", requesting)
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
            FakeReviewProvider(),
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


if __name__ == "__main__":
    unittest.main()
