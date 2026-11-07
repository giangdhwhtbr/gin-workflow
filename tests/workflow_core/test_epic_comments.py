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


class TestPlanReadsNewerComments(unittest.TestCase):
    def test_step_one_reads_comments_newer_than_the_spec(self):
        step = line_with(skill("plan"), "1. Require `requirement_confirmed`")
        for needle in (
            "`gin task comments <epic> --json`",
            "Comments considered:",
            "return to `/discuss <epic>`",
            "markdown",
        ):
            self.assertIn(needle, step)


class TestShipCommentsDependents(unittest.TestCase):
    def test_close_out_comments_open_dependent_epics(self):
        step = line_with(skill("ship"), "7. Close out:")
        for needle in (
            "`gin task show <epic> --json --include-dependents`",
            "`issue_type: epic`",
            "`open` or `in_progress`",
            "[gin ship]",
            "`requirement.confirmed`",
            "never blocks",
            "markdown",
        ):
            self.assertIn(needle, step)

    def test_handoff_lists_commented_epics(self):
        self.assertIn("[gin ship]", line_with(skill("ship"), "9. Handoff:"))


class TestRoadmapCommentsChangedEpics(unittest.TestCase):
    def test_unchanged_epic_gets_a_comment_once(self):
        bullet = line_with(skill("roadmap"), "warn and leave its title, description, and dependencies unchanged")
        for needle in (
            "[gin roadmap]",
            "`Depends on:`",
            "most recent `[gin roadmap]` comment",
            "closed epic gets no comment",
            "sync continues",
            "markdown",
        ):
            self.assertIn(needle, bullet)

    def test_report_lists_commented_epics(self):
        self.assertIn("[gin roadmap]", line_with(skill("roadmap"), "7. **Report**"))


if __name__ == "__main__":
    unittest.main()
