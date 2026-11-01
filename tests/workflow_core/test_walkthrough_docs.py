"""The walkthrough cites only documented gin-workflow commands."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WALKTHROUGH = ROOT / "docs/starters/brownfield-walkthrough.md"


class TestWalkthroughCommands(unittest.TestCase):
    def test_every_cited_command_is_in_the_cli_reference(self):
        cli = (ROOT / "docs/reference/cli.md").read_text(encoding="utf-8")
        text = WALKTHROUGH.read_text(encoding="utf-8")
        cited = set(re.findall(r"gin-workflow ((?:[a-z]+(?: [a-z-]+)?))", text))
        missing = []
        for token in sorted(cited):
            command, _, sub = token.partition(" ")
            documented = (
                f"gin-workflow {token}" in cli
                # `team` subcommands are table rows; `task` passes its arguments to bd
                or (sub and re.search(rf"^\| `{re.escape(sub)}[` ]", cli, re.M)
                    and f"## `gin-workflow {command}`" in cli)
                or (command == "task" and "## `gin-workflow task`" in cli)
            )
            if not documented:
                missing.append(token)
        self.assertEqual([], missing)

    def test_walkthrough_has_the_milestone_stages(self):
        text = WALKTHROUGH.read_text(encoding="utf-8")
        for heading in ("## Repository and workspace setup", "## Roadmap overview", "## Milestone planning",
                        "## Milestone review and spill-over"):
            self.assertIn(heading, text)
        self.assertNotIn("sprint", text.lower())


if __name__ == "__main__":
    unittest.main()
