"""`gin-workflow docs check`: mechanical rules for Markdown pages."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from specs_fixtures import LAUNCHER  # noqa: E402
from workflow_core import docs_check  # noqa: E402


def run_docs(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(LAUNCHER), "docs", "check", *args, "--repository", str(root)],
                          cwd=root, text=True, capture_output=True, check=False)


class TestPageFindings(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.page = self.root / "page.md"
        (self.root / "other.md").write_text("# Other\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def findings(self, text: str, required=()):
        return docs_check.page_findings(self.page, text, required)

    def test_each_rule_reports_its_line(self):
        text = ("# Title\nA — dash\n- **Label:** text\nDone ✅\n## 2. Step\n"
                "Fill {{name}} here\nStill TBD\nA TODO left\n[gone](missing.md)\n")
        self.assertEqual(
            [f"{self.page}:{n}: {rule}" for n, rule in
             ((2, "dash"), (3, "bold-label item"), (4, "emoji"), (5, "numbered heading"),
              (6, "placeholder"), (7, "placeholder"), (8, "placeholder"), (9, "dead link"))],
            self.findings(text))

    def test_code_is_not_checked(self):
        text = "# Title\n```\nA — dash {{x}} TODO [l](missing.md)\n```\nUse `{{name}}` and `TODO` and `[l](missing.md)`.\n"
        self.assertEqual([], self.findings(text))

    def test_live_external_and_anchor_links_pass(self):
        self.assertEqual([], self.findings("[a](other.md#top) [b](https://example.com/x.md) [c](#local)\n"))

    def test_words_containing_todo_pass(self):
        self.assertEqual([], self.findings("TODOS and MASTODON are words.\n"))

    def test_missing_section(self):
        required = ["## Steps", "## Rollback"]
        self.assertEqual([f"{self.page}: missing section: ## Rollback"], self.findings("## Steps\n", required))
        self.assertEqual([], self.findings("## Steps\n\n## Rollback\n", required))


class TestRequiredSections(unittest.TestCase):
    def test_placeholder_headings_are_not_required_and_overrides_apply(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            override = root / ".agent-workflow/templates/note.md"
            override.parent.mkdir(parents=True)
            override.write_text("# {{title}}\n\n## Context\n\n## [{{version}}]\n", encoding="utf-8")
            self.assertEqual(["## Context"], docs_check.required_sections(root, "note.md"))


class TestCli(unittest.TestCase):
    def test_exit_codes_and_formats_without_workflow_config(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "clean.md").write_text("# Clean\n\n## Context\n", encoding="utf-8")
            (root / "bad.md").write_text("# Bad — page\n", encoding="utf-8")
            clean = run_docs(root, "clean.md")
            self.assertEqual((0, "ok\n"), (clean.returncode, clean.stdout))
            bad = run_docs(root, "bad.md")
            self.assertEqual((1, "bad.md:1: dash\n"), (bad.returncode, bad.stdout))
            payload = json.loads(run_docs(root, "bad.md", "--format", "json").stdout)
            self.assertEqual({"status": "findings", "findings": ["bad.md:1: dash"]}, payload)
            self.assertEqual(2, run_docs(root, "absent.md").returncode)
            unknown = run_docs(root, "clean.md", "--template", "nope.md")
            self.assertEqual(2, unknown.returncode)
            self.assertIn("unknown template", unknown.stderr)
            self.assertFalse((root / ".agent-workflow").exists())


if __name__ == "__main__":
    unittest.main()
