"""Tests for the write-doc skill: templates, checks, and trigger description."""

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
SKILL_PATH = ROOT / "plugins/gin-workflow/src/skills/write-doc/SKILL.md"


class WriteDocSkillTests(unittest.TestCase):
    def setUp(self):
        self.text = SKILL_PATH.read_text(encoding="utf-8")

    def test_names_templates_rules_and_check(self):
        for needle in ("`readme.md`", "`runbook.md`", "`adr.md`", "`changelog.md`",
                       "gin-workflow specs template", "gin-workflow rules --files",
                       "references/docs-style.md", "gin-workflow docs check", "artifacts.adr"):
            with self.subTest(needle=needle):
                self.assertIn(needle, self.text)

    def test_updates_in_place(self):
        self.assertIn("leave every other line unchanged", self.text)

    def test_stays_outside_the_lifecycle(self):
        self.assertIn("never records a gate", self.text)

    def test_description_within_budget(self):
        description = re.search(r"^description: (.+)$", self.text, re.M).group(1)
        self.assertLessEqual(len(description), 350)


if __name__ == "__main__":
    unittest.main()
