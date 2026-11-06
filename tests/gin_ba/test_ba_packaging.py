"""Packaging rules of the gin-ba add-on: manifests, skill budgets and links, no code, and a core that never names it."""

import json
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
BA = ROOT / "plugins/gin-ba"
CORE = ROOT / "plugins/gin-workflow/src"
sys.path.insert(0, str(CORE / "scripts"))

from workflow_core.budget import description_chars  # noqa: E402


class BaPackagingTests(unittest.TestCase):
    def test_manifests_agree(self):
        meta = json.loads((BA / "plugin.meta.json").read_text(encoding="utf-8"))
        claude = json.loads((BA / "src/.claude-plugin/plugin.json").read_text(encoding="utf-8"))
        codex = json.loads((BA / "src/.codex-plugin/plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(("gin-ba", "0.1.0"), (meta["name"], meta["version"]))
        for key in ("name", "version", "description", "author", "repository"):
            with self.subTest(key=key):
                self.assertEqual(meta[key], claude[key])
                self.assertEqual(meta[key], codex[key])
        self.assertEqual("./skills/", codex["skills"])
        self.assertNotIn("hooks", codex)
        marketplace = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
        names = [p["name"] for p in marketplace["plugins"]]
        self.assertEqual(names.index("gin-qa") + 1, names.index("gin-ba"))
        entry = marketplace["plugins"][names.index("gin-ba")]
        self.assertEqual("plugins/gin-ba/src", entry["source"]["path"])

    def test_skill_budget_and_links(self):
        expected = {
            "mockup": ["references/mockup-html.md", "references/mockup-html.md"],
            "capture": ["references/legacy-description.md"],
        }
        self.assertEqual(sorted(expected), sorted(p.name for p in (BA / "src/skills").iterdir()))
        self.assertLessEqual(description_chars(BA / "src"), 1_000)
        for skill, links in expected.items():
            path = BA / "src/skills" / skill / "SKILL.md"
            text = path.read_text(encoding="utf-8")
            with self.subTest(skill=skill):
                self.assertLessEqual(len(text), 6_000)
                self.assertIn(f"name: {skill}\n", text)
                found = re.findall(r"\]\(([^)]+)\)", text)
                self.assertEqual(links, found)
                for link in found:
                    self.assertTrue((path.parent / link).is_file(), link)

    def test_skills_hold_the_spec_rules(self):
        mockup = (BA / "src/skills/mockup/SKILL.md").read_text(encoding="utf-8")
        capture = (BA / "src/skills/capture/SKILL.md").read_text(encoding="utf-8")
        for text in (mockup, capture):
            for needle in ("project.layout: sdd", "gin specs template iteration.md", "Confirmed: <YYYY-MM-DD>",
                           "frozen", "Confirmed: <today>", "[a-z][a-z0-9-]*", "Do not commit"):
                with self.subTest(needle=needle):
                    self.assertIn(needle, text)
        for needle in ("mockup/index.html", '<section id="<screen-id>">', "`frontend-design`", "no network request",
                       "empty, error, and loading", "`new`", "`change`"):
            with self.subTest(needle=needle):
                self.assertIn(needle, mockup)
        for needle in ("legacy/", "Kind: legacy", "`Field | Type | Required | Rule`", "## As-is behaviour",
                       "## Rules", "## Open questions", "none (as-is)", "never copy from outside the repository"):
            with self.subTest(needle=needle):
                self.assertIn(needle, capture)

    def test_no_code_or_agents(self):
        self.assertFalse((BA / "src/scripts").exists())
        self.assertFalse((BA / "src/agents").exists())

    def test_core_never_refers_to_gin_ba(self):
        hits = [p.relative_to(ROOT).as_posix() for p in CORE.rglob("*")
                if p.is_file() and p.suffix in {".md", ".py", ".yaml", ".json"}
                and "gin-ba" in p.read_text(encoding="utf-8")]
        self.assertEqual([], hits)


if __name__ == "__main__":
    unittest.main()
