"""Every stage ends with one handoff line; setup offers the Claude Code compaction point."""

from __future__ import annotations

from pathlib import Path
import unittest

SRC = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src"


def read(relative: str) -> str:
    return (SRC / relative).read_text(encoding="utf-8")


class StageHandoffTests(unittest.TestCase):
    def test_the_contract_holds_the_handoff_rule(self):
        text = read("references/stage-contract.md")
        self.assertIn("## Handoff", text)
        self.assertIn("`Next: /clear, then <command>`", text)
        self.assertIn("`Next: /clear` if none", text)

    def test_orchestrate_and_ship_end_with_the_handoff_line(self):
        for skill in ("orchestrate", "ship"):
            with self.subTest(skill=skill):
                text = read(f"skills/{skill}/SKILL.md")
                self.assertIn("`Next: /clear, then /gin:execute <id-1> <id-2>`", text)
                self.assertNotIn("Next commands:", text)

    def test_orchestrate_keeps_the_goal_text(self):
        self.assertIn("`gin goal --workflow-id <workflow>`", read("skills/orchestrate/SKILL.md"))

    def test_setup_offers_the_compaction_point_only_when_unset(self):
        text = read("skills/setup/SKILL.md")
        self.assertIn("`autoCompactWindow`", text)
        self.assertIn("`200000`", text)
        self.assertIn("never change an existing value", text)
        self.assertIn("never write project settings", text)


if __name__ == "__main__":
    unittest.main()
