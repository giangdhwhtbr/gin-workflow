"""gin-qa packaging: manifests, skill budget and links, and a core that never refers to gin-qa."""

from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
QA = ROOT / "plugins/gin-qa"
CORE = ROOT / "plugins/gin-workflow/src"
sys.path.insert(0, str(CORE / "scripts"))
sys.path.insert(0, str(QA / "src/scripts"))

from workflow_core.budget import description_chars  # noqa: E402


class TestPackaging(unittest.TestCase):
    def test_manifests_agree(self):
        meta = json.loads((QA / "plugin.meta.json").read_text())
        for relative in ("src/.claude-plugin/plugin.json", "src/.codex-plugin/plugin.json"):
            manifest = json.loads((QA / relative).read_text())
            with self.subTest(manifest=relative):
                for key in ("name", "version", "description", "author", "repository"):
                    self.assertEqual(meta[key], manifest[key])
        self.assertNotIn("hooks", json.loads((QA / "src/.codex-plugin/plugin.json").read_text()))
        marketplace = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
        self.assertEqual({"gin": "plugins/gin-workflow/src", "gin-qa": "plugins/gin-qa/src",
                          "gin-orchestrator": "plugins/gin-orchestrator/src"},
                         {p["name"]: p["source"]["path"] for p in marketplace["plugins"]})

    def test_skill_budget_and_links(self):
        expected = {"cases": ["../../templates/guidelines.md", "../../templates/qa-readme.md", "../../templates/cases.md"], "e2e": ["references/explore-case.md"] * 2, "report": [], "run": [], "setup": ["../../templates/guidelines.md", "../../templates/qa-readme.md", "../../templates/project-skill.md"], "tests": []}
        self.assertEqual(sorted(expected), sorted(p.name for p in (QA / "src/skills").iterdir()))
        self.assertLessEqual(description_chars(QA / "src"), 1_000)
        for name, want in expected.items():
            skill = QA / f"src/skills/{name}/SKILL.md"
            text = skill.read_text(encoding="utf-8")
            self.assertLessEqual(len(text), 6_000, name)
            links = re.findall(r"\]\(([^)]+)\)", text)
            self.assertEqual(want, links, name)
            for link in links:
                with self.subTest(link=link):
                    self.assertTrue((skill.parent / link).resolve().is_file())

    def test_guidelines_template_sets_no_language(self):
        text = (QA / "src/templates/guidelines.md").read_text(encoding="utf-8")
        self.assertRegex(text, r"- Language: not set yet")

    def test_guidelines_template_lists_e2e_and_manual(self):
        from gin_qa.cases import declared_types
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "qa").mkdir()
            shutil.copyfile(QA / "src/templates/guidelines.md", root / "qa/guidelines.md")
            self.assertEqual(({"e2e", "manual"}, []), declared_types(root, "qa/guidelines.md"))
            text = (root / "qa/guidelines.md").read_text(encoding="utf-8")
            for heading in ("## Manual runs\n", "## Bugs\n"):
                self.assertIn(heading, text)

    def test_project_skill_template_placeholders(self):
        text = (QA / "src/templates/project-skill.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\nname: {{name}}-qa\ndescription: "))
        self.assertEqual({"{{name}}", "{{guidelines}}", "{{readme}}"}, set(re.findall(r"\{\{[a-z]+\}\}", text)))
        self.assertIn("## Process", (QA / "src/templates/qa-readme.md").read_text(encoding="utf-8"))

    def test_guidelines_template_declares_no_automated_type(self):
        from gin_qa.reqs import Effective
        from gin_qa.tests import declared
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "qa").mkdir()
            shutil.copyfile(QA / "src/templates/guidelines.md", root / "qa/guidelines.md")
            text = (root / "qa/guidelines.md").read_text(encoding="utf-8")
            self.assertIn("## Automated types\n", text)
            self.assertEqual(({}, []), declared(root, Effective("legacy", "qa/cases", "qa/guidelines.md", [])))

    def test_core_never_refers_to_gin_qa(self):
        for path in sorted(p for p in CORE.rglob("*") if p.is_file() and p.suffix in (".md", ".py", ".yaml", ".json")):
            with self.subTest(path=str(path.relative_to(CORE))):
                self.assertNotIn("gin-qa", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
