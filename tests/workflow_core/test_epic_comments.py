"""Skill text for epic comments (workflow epic-comments)."""

from __future__ import annotations

from pathlib import Path
import unittest

SRC = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src"


def skill(name: str) -> str:
    return (SRC / f"skills/{name}/SKILL.md").read_text(encoding="utf-8")


def line_with(text: str, needle: str) -> str:
    return next(line for line in text.splitlines() if needle in line)


class TestDiscussReadsComments(unittest.TestCase):
    def test_roadmap_epic_reads_comments_in_time_order(self):
        line = line_with(skill("discuss"), "**Roadmap epic:**")
        for needle in (
            "`gin task comments <id> --json`",
            "`created_at` order",
            "confirm or correct",
            "`project.max_questions`",
            "which comments to keep",
            "markdown task backend",
        ):
            self.assertIn(needle, line)

    def test_spec_records_comments_considered(self):
        line = line_with(skill("discuss"), "**Write the spec**")
        self.assertIn("Comments considered: <count>, latest <created_at", line)


if __name__ == "__main__":
    unittest.main()
