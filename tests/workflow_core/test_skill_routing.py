"""Tests for routing instructions across workflow skills and agents."""

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "plugins/gin-workflow/src"


class SkillRoutingTests(unittest.TestCase):
    def test_execute_skill_delegates_via_routes_dispatch(self):
        text = (SRC / "skills/execute/SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn("three or fewer", text)
        self.assertNotIn("Execute directly", text)
        self.assertIn("routes dispatch", text)
        self.assertIn("gin-workflow:developer", text)
        self.assertIn("needs_clarification", text)
        self.assertIn("--escalate", text)
        self.assertIn("routes dispatch --workflow-id <w> --task-id <id> --escalate", text)
        self.assertIn('notify --event needs_input "', text)

    def test_review_skill_uses_model_and_effort(self):
        text = (SRC / "skills/review/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("--model", text)
        self.assertIn("gin-workflow:code-reviewer", text)
        self.assertNotIn("--tier", text)

    def test_plan_skill_and_schema_use_catalog_routes(self):
        for path in (SRC / "skills/plan/SKILL.md", SRC / "skills/plan/plan-schema.md"):
            text = path.read_text(encoding="utf-8")
            with self.subTest(file=path.name):
                self.assertIn("Model:", text)
                self.assertIn("Effort:", text)
                self.assertIn("Why:", text)
                self.assertNotIn("Reasoning", text)
                self.assertNotIn("Model Guidance", text)
                self.assertNotIn("high_reasoning", text)
                self.assertNotIn("standard_impl", text)
                self.assertNotIn("cheap_simple", text)

    def test_orchestrate_skill_tracks_file_format(self):
        text = (SRC / "skills/orchestrate/SKILL.md").read_text(encoding="utf-8")
        self.assertIn('"model", "effort"', text)
        self.assertNotIn('"reasoning"', text)
        self.assertNotIn("model names never enter", text)

    def test_discuss_and_plan_delegate_exploration_to_researcher(self):
        for path in (SRC / "skills/discuss/SKILL.md", SRC / "skills/plan/SKILL.md"):
            text = path.read_text(encoding="utf-8")
            with self.subTest(file=path.name):
                self.assertIn("gin-workflow:agent-researcher", text)

    def test_review_response_skill_routes_to_same_route(self):
        text = (SRC / "skills/gin-review-response/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("same route", text)
        self.assertNotIn("same-reasoning", text)

    def test_developer_agent_reports_normalized_status(self):
        text = (SRC / "agents/developer.md").read_text(encoding="utf-8")
        self.assertNotIn("routes dispatch", text)
        self.assertIn("section 2 (Implement)", text)
        for status in ("done", "needs_clarification", "failed", "blocked"):
            with self.subTest(status=status):
                self.assertIn(status, text)

    def test_execute_references_use_dispatch_and_normalized_statuses(self):
        ref_dir = SRC / "skills/execute/references"
        contract = (ref_dir / "result-contract.md").read_text(encoding="utf-8")
        dispatch = (ROOT / "plugins/gin-orchestrator/src/scripts/gin_orchestrator/worker_dispatch.py").read_text(encoding="utf-8")
        self.assertIn("status must be completed, failed, or cancelled", dispatch)
        self.assertIn("`status`: `completed`, `failed`, or `cancelled`", contract)
        policy = (ref_dir / "delegation-policy.md").read_text(encoding="utf-8")
        for status in ("done", "needs_clarification", "failed", "blocked"):
            with self.subTest(status=status):
                self.assertIn(status, policy)
        self.assertIn("never lowered", policy)
        self.assertIn("one isolated worktree per worker", policy)

        for path in (ref_dir / "worker-lifecycle.md", ref_dir / "delegation-policy.md"):
            text = path.read_text(encoding="utf-8")
            with self.subTest(file=path.name):
                self.assertIn("routes dispatch", text)
