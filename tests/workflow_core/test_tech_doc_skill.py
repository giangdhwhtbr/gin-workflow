"""Tests for tech-doc skill roles, routes, and execution rules."""

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
SKILL_PATH = ROOT / "plugins/gin-workflow/src/skills/tech-doc/SKILL.md"


class TechDocSkillTests(unittest.TestCase):
    def setUp(self):
        self.text = SKILL_PATH.read_text(encoding="utf-8")

    def test_declares_agent_roles(self):
        self.assertIn("gin-workflow:agent-researcher", self.text)
        self.assertIn("gin-workflow:docs-writer", self.text)

    def test_declares_runtime_notes_path(self):
        self.assertIn(".agent-workflow/runtime/tech-doc/", self.text)

    def test_declares_review_cycle_bound(self):
        self.assertIn("routing.review.max_cycles", self.text)

    def test_declares_uncertainty_section(self):
        self.assertIn("Inference And Uncertainty", self.text)

    def test_writer_routes_for_documents(self):
        # R11 table routes: weakest, middle, strongest
        self.assertRegex(self.text, r"(?i)weakest.*\bSTACK\b")
        self.assertRegex(self.text, r"(?i)middle.*\bAPI\b")
        self.assertRegex(self.text, r"(?i)strongest.*\bARCHITECTURE\b")
        self.assertRegex(self.text, r"(?i)strongest.*\bCONCERNS\b")

    def test_scout_and_reviewer_routes(self):
        self.assertRegex(self.text, r"(?i)Scout.*agent-researcher.*(weakest|middle).*low")
        self.assertRegex(self.text, r"(?i)Reviewer.*agent-researcher.*middle.*medium")

    def test_features_after_api(self):
        self.assertIn("`FEATURES.md` starts after `API.md`", self.text)

    def test_regrounding_uses_same_roles(self):
        regrounding_part = self.text.split("## Regrounding existing docs")[-1]
        self.assertIn("same roles", regrounding_part)
        self.assertIn("one writer per page", regrounding_part)

    def test_failed_writer_escalates_as_in_execute(self):
        self.assertIn("escalates as in execute", self.text)

    def test_no_concrete_model_names(self):
        for banned in ("sonnet", "opus", "haiku", "gpt-4", "gpt-5", "claude-3"):
            self.assertNotIn(banned, self.text.lower())
