"""Tests for agent definitions and installer agent templating."""

from pathlib import Path
import os
import re
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "plugins/gin-workflow/src/scripts"))

CLAUDE_TO_ANTIGRAVITY = {
    "Read": "view_file",
    "Grep": "grep_search",
    "Glob": "list_dir",
    "WebSearch": "search_web",
    "Bash": "run_command",
    "Edit": "replace_file_content",
    "Write": "write_to_file",
}

def _tools(path: Path) -> list[str]:
    m = re.search(r"^tools:\s*(\[[^\]]+\])", path.read_text(encoding="utf-8"), re.MULTILINE)
    assert m, f"{path} missing tools declaration"
    return re.findall(r'"([^"]+)"', m.group(1))

def _sed_args(function: str) -> list[str]:
    body = re.search(function + r"\(\)\s*\{([\s\S]*?)\n\}", (ROOT / "install.sh").read_text(encoding="utf-8"))
    assert body, f"{function} not found in install.sh"
    args = []
    for flag in re.findall(r"-e\s+('[^']+'|\"[^\"]+\")", body.group(1)):
        args.extend(["-e", flag[1:-1]])
    return args


class AgentFilesTests(unittest.TestCase):
    def test_no_agent_has_model_in_frontmatter(self):
        agent_files = list(ROOT.glob("plugins/*/src/agents/*.md"))
        self.assertTrue(len(agent_files) > 0, "Expected at least one agent file")
        for agent_file in agent_files:
            text = agent_file.read_text(encoding="utf-8")
            m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
            self.assertIsNotNone(m, f"{agent_file} missing YAML frontmatter")
            frontmatter = m.group(1)
            for line in frontmatter.splitlines():
                self.assertFalse(
                    bool(re.match(r"^model:", line.strip())),
                    f"Found forbidden model line in {agent_file}: {line}",
                )

    def test_deleted_agents_do_not_exist(self):
        agents_dir = ROOT / "plugins/gin-workflow/src/agents"
        self.assertFalse(
            (agents_dir / "bead-worker.md").exists(),
            "bead-worker.md should not exist under plugins/gin-workflow/src/agents/",
        )
        self.assertFalse(
            (agents_dir / "solution-architect.md").exists(),
            "solution-architect.md should not exist under plugins/gin-workflow/src/agents/",
        )

    def test_source_agents_list_claude_code_tool_names(self):
        agents = sorted(ROOT.glob("plugins/*/src/agents/*.md"))
        self.assertTrue(agents)
        for path in agents:
            with self.subTest(agent=path.relative_to(ROOT).as_posix()):
                tools = _tools(path)
                self.assertTrue(tools)
                self.assertLessEqual(set(tools), set(CLAUDE_TO_ANTIGRAVITY))

    def test_agent_tools_declared(self):
        agents = ROOT / "plugins/gin-workflow/src/agents"
        self.assertLessEqual({"Edit", "Write"}, set(_tools(agents / "developer.md")))
        self.assertIn("Bash", _tools(agents / "agent-researcher.md"))
        self.assertLessEqual({"Bash", "Edit", "Write"}, set(_tools(agents / "docs-writer.md")))
        self.assertIn("Glob", _tools(agents / "code-reviewer.md"))

    @unittest.skipIf(os.name == "nt", "runs the install.sh expressions through sed, a POSIX tool")
    def test_antigravity_template_round_trips_every_source_agent(self):
        forward = _sed_args("template_agents_for_antigravity")
        self.assertEqual(len(CLAUDE_TO_ANTIGRAVITY), len(forward) // 2)
        inverse = []
        for claude, antigravity in CLAUDE_TO_ANTIGRAVITY.items():
            inverse.extend(["-e", f's/"{antigravity}"/"{claude}"/g'])
        for path in sorted(ROOT.glob("plugins/*/src/agents/*.md")):
            source = path.read_text(encoding="utf-8")
            with self.subTest(agent=path.relative_to(ROOT).as_posix()):
                converted = subprocess.run(["sed", *forward], input=source, text=True,
                                           capture_output=True, check=True).stdout
                for claude, antigravity in CLAUDE_TO_ANTIGRAVITY.items():
                    self.assertNotIn(f'"{claude}"', converted)
                self.assertIn('"run_command"', converted)
                back = subprocess.run(["sed", *inverse], input=converted, text=True,
                                      capture_output=True, check=True).stdout
                self.assertEqual(source, back)

    @unittest.skipIf(os.name == "nt", "runs the install.sh expressions through sed, a POSIX tool")
    def test_copilot_template_maps_claude_code_names(self):
        source = (ROOT / "plugins/gin-workflow/src/agents/developer.md").read_text(encoding="utf-8")
        converted = subprocess.run(["sed", *_sed_args("template_agents_for_copilot")], input=source, text=True,
                                   capture_output=True, check=True).stdout
        self.assertIn('tools: ["view", "grep", "glob", "bash", "edit"]', converted)


if __name__ == "__main__":
    unittest.main()
