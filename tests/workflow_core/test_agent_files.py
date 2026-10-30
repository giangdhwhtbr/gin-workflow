"""Tests for agent definitions and installer agent templating."""

from pathlib import Path
import re
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "plugins/gin-workflow/src/scripts"))


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

    def test_agent_tools_declared(self):
        def get_tools(filename: str):
            path = ROOT / "plugins/gin-workflow/src/agents" / filename
            text = path.read_text(encoding="utf-8")
            m = re.search(r"^tools:\s*(\[[^\]]+\])", text, re.MULTILINE)
            self.assertIsNotNone(m, f"{filename} missing tools declaration")
            raw = m.group(1)
            return set(re.findall(r'"([^"]+)"', raw))

        dev_tools = get_tools("developer.md")
        self.assertIn("replace_file_content", dev_tools)
        self.assertIn("write_to_file", dev_tools)

        researcher_tools = get_tools("agent-researcher.md")
        self.assertIn("run_command", researcher_tools)

        docs_tools = get_tools("docs-writer.md")
        self.assertIn("run_command", docs_tools)
        self.assertIn("replace_file_content", docs_tools)
        self.assertIn("write_to_file", docs_tools)

        reviewer_tools = get_tools("code-reviewer.md")
        self.assertIn("list_dir", reviewer_tools)

    def test_claude_template_agents_maps_tools_for_developer(self):
        install_sh = (ROOT / "install.sh").read_text(encoding="utf-8")
        m = re.search(
            r"template_agents_for_claude\(\)\s*\{([\s\S]*?)\n\}",
            install_sh,
        )
        self.assertIsNotNone(m, "template_agents_for_claude not found in install.sh")
        body = m.group(1)

        sed_flags = re.findall(r"-e\s+('[^']+'|\"[^\"]+\")", body)
        self.assertTrue(len(sed_flags) > 0, "No sed -e expressions found in template_agents_for_claude")

        sed_args = []
        for flag in sed_flags:
            expr = flag[1:-1]
            sed_args.extend(["-e", expr])

        dev_file = ROOT / "plugins/gin-workflow/src/agents/developer.md"
        dev_content = dev_file.read_text(encoding="utf-8")

        result = subprocess.run(
            ["sed"] + sed_args,
            input=dev_content,
            text=True,
            capture_output=True,
            check=True,
        )
        templated = result.stdout

        self.assertIn('"Edit"', templated)
        self.assertIn('"Write"', templated)

        source_tools = [
            "view_file",
            "grep_search",
            "list_dir",
            "search_web",
            "run_command",
            "replace_file_content",
            "write_to_file",
        ]
        for src_tool in source_tools:
            self.assertNotIn(f'"{src_tool}"', templated)


if __name__ == "__main__":
    unittest.main()
