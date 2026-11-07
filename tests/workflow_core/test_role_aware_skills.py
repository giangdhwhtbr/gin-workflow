"""Skill text for role-aware discuss and plan (gin-workflow-746z)."""

from __future__ import annotations

from pathlib import Path
import unittest

SRC = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src"


def section(text: str, heading: str) -> str:
    start = text.index(heading)
    end = text.find("\n## ", start + len(heading))
    return text[start:] if end == -1 else text[start:end]


class TestRoleAwareSkills(unittest.TestCase):
    def test_team_discuss_limits_a_business_member_to_business_questions(self):
        text = section((SRC / "skills/team/SKILL.md").read_text(encoding="utf-8"), "## discuss")
        for needle in ("project.team.me.technical", "business questions", "- TQ-<n>: <question>",
                       "## Open Technical Questions"):
            self.assertIn(needle, text)

    def test_team_plan_puts_the_design_doc_in_the_plan_pull_request(self):
        text = section((SRC / "skills/team/SKILL.md").read_text(encoding="utf-8"), "## plan")
        self.assertIn("Decision:", text)

    def test_discuss_reads_the_team_skill_before_asking(self):
        text = (SRC / "skills/discuss/SKILL.md").read_text(encoding="utf-8")
        clarify = next(line for line in text.splitlines() if "**Clarify**" in line)
        self.assertIn("`team` skill", clarify)

    def test_plan_resolves_open_questions_first(self):
        text = (SRC / "skills/plan/SKILL.md").read_text(encoding="utf-8")
        step = next(line for line in section(text, "## Steps").splitlines() if line.startswith("1. "))
        for needle in ("## Open Technical Questions", "Decision:", "03-design.md", "record plan-approved"):
            self.assertIn(needle, step)


if __name__ == "__main__":
    unittest.main()
