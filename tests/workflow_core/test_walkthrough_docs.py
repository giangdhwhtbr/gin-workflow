"""The walkthrough cites only documented gin-workflow commands."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WALKTHROUGH = ROOT / "docs/starters/brownfield.md"
AI_STRATEGY = ROOT / "docs/guides/ai-strategy.md"


# `task` runs bd unchanged; cli.md lists only some of its subcommands, so name the others the walkthrough uses.
BD_PASSTHROUGH = {"graph", "dep"}


def undocumented(cli, text):
    """Cited `gin-workflow <command> <sub>` tokens that cli.md does not document."""
    missing = []
    for token in sorted(set(re.findall(r"gin-workflow ((?:[a-z]+(?: [a-z-]+)?))", text))):
        command, _, sub = token.partition(" ")
        match = re.search(rf"^## `gin-workflow {command}`.*?(?=^## |\Z)", cli, re.M | re.S)
        section = match.group(0) if match else ""
        documented = f"gin-workflow {token}" in cli or (
            bool(sub) and re.search(rf"^\| `{re.escape(sub)}[` ]", section, re.M) is not None
        ) or (command == "task" and (f"`{sub}`" in section or sub in BD_PASSTHROUGH))
        if not documented:
            missing.append(token)
    return missing


class TestWalkthroughCommands(unittest.TestCase):
    def test_every_cited_command_is_in_the_cli_reference(self):
        cli = (ROOT / "docs/reference/cli.md").read_text(encoding="utf-8")
        text = WALKTHROUGH.read_text(encoding="utf-8")
        self.assertEqual([], undocumented(cli, text))

    def test_ai_strategy_cites_only_documented_commands(self):
        cli = (ROOT / "docs/reference/cli.md").read_text(encoding="utf-8")
        text = AI_STRATEGY.read_text(encoding="utf-8")
        self.assertEqual([], undocumented(cli, text))

    def test_unknown_subcommand_is_reported(self):
        cli = (ROOT / "docs/reference/cli.md").read_text(encoding="utf-8")
        self.assertEqual(["team nonsense"], undocumented(cli, "gin team nonsense"))
        self.assertEqual(["task nonsense"], undocumented(cli, "gin task nonsense"))

    def test_walkthrough_has_the_milestone_stages(self):
        text = WALKTHROUGH.read_text(encoding="utf-8")
        for heading in ("## Repository and workspace setup", "## Roadmap overview", "## Milestone planning",
                        "## Milestone review and spill-over"):
            self.assertIn(heading, text)
        self.assertNotIn("sprint", text.lower())


if __name__ == "__main__":
    unittest.main()
