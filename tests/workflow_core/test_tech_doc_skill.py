"""Tests for tech-doc skill roles, routes, and execution rules."""

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
SKILL_PATH = ROOT / "plugins/gin-workflow/src/skills/tech-doc/SKILL.md"
TEMPLATES = ROOT / "plugins/gin-workflow/src/templates/codebase"
READING_ORDER = ["OVERVIEW", "FEATURES", "ARCHITECTURE", "STRUCTURE", "API",
                 "INTEGRATIONS", "STACK", "CONVENTIONS", "TESTING", "CONCERNS"]


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
        row = next(line for line in self.text.splitlines() if line.startswith("| Writer |"))
        groups = dict(re.findall(r"(weakest|middle|strongest) model for ([^;|]+)", row))
        self.assertIn("`STACK`", groups["weakest"])
        self.assertIn("`API`", groups["middle"])
        self.assertIn("`ARCHITECTURE`", groups["strongest"])
        self.assertIn("`CONCERNS`", groups["strongest"])
        self.assertNotIn("`STACK`", groups["strongest"])

    def test_writers_cite_every_row(self):
        self.assertIn("Every `05-API.md` and `02-FEATURES.md` row cites `file:line`", self.text)

    def test_scout_and_reviewer_routes(self):
        self.assertRegex(self.text, r"(?i)Scout.*agent-researcher.*(weakest|middle).*low")
        self.assertRegex(self.text, r"(?i)Reviewer.*agent-researcher.*middle.*medium")

    def test_features_after_api(self):
        self.assertIn("`02-FEATURES.md` starts after `05-API.md`", self.text)

    def test_regrounding_uses_same_roles(self):
        regrounding_part = self.text.split("## Regrounding existing docs")[-1]
        self.assertIn("same roles", regrounding_part)
        self.assertIn("one writer per page", regrounding_part)

    def test_failed_writer_escalates_as_in_execute(self):
        self.assertIn("escalates as in execute", self.text)

    def test_no_concrete_model_names(self):
        for banned in ("sonnet", "opus", "haiku", "gpt-4", "gpt-5", "claude-3"):
            self.assertNotIn(banned, self.text.lower())

    def test_templates_list_in_reading_order(self):
        names = sorted(path.name for path in TEMPLATES.glob("*.md"))
        self.assertEqual([f"{n:02d}-{topic}.md" for n, topic in enumerate(READING_ORDER, start=1)], names)

    def test_split_set_table_lists_every_template_in_order(self):
        rows = re.findall(r"^\| `(\d\d-[A-Z]+\.md)` \|", self.text, re.MULTILINE)
        self.assertEqual(sorted(path.name for path in TEMPLATES.glob("*.md")), rows)

    def test_unnumbered_files_are_renamed_before_writing(self):
        self.assertIn("`OVERVIEW.md` … `CONCERNS.md`", self.text)
        self.assertIn("renamed to their numbered names with `git mv`", self.text)
        self.assertIn(".agent-workflow/templates/codebase/", self.text)
