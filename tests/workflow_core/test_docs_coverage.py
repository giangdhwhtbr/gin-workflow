"""Docs stay in step with the code: every skill and CLI subcommand is documented, links resolve, Mermaid blocks are typed."""

from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
SCRIPTS = ROOT / "plugins/gin-workflow/src/scripts"
LINK = re.compile(r"\]\(([^)\s]+)\)")
MERMAID = re.compile(r"```mermaid\n(\S+)")
BEADS_DEFAULT = re.compile(r"(?i)beads[^.\n]{0,40}\b(default|required)\b|\b(default|required)\b[^.\n]{0,40}beads")
TYPES = {"flowchart", "graph", "sequenceDiagram", "stateDiagram-v2", "stateDiagram", "classDiagram", "erDiagram"}
STYLE_RULES = (("dash", re.compile("[\u2013\u2014]")),
               ("bold-label item", re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\*\*")),
               ("emoji", re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\u2B50\u2B55\uFE0F]")),
               ("numbered heading", re.compile(r"^#{1,6}\s+\d")))
STYLE_EXEMPT = {"docs/presentations/brownfield-modernization-script.md"}  # headings map to slide numbers


def style_violations(text: str) -> list[str]:
    """Mechanical docs-pack rules outside fenced code blocks, as '<line>: <rule>'."""
    found, fenced = [], False
    for number, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if not fenced:
            found += [f"{number}: {name}" for name, pattern in STYLE_RULES if pattern.search(line)]
    return found


def pages() -> list[Path]:
    return [ROOT / "README.md", ROOT / "AGENTS.md", ROOT / "CLAUDE.md", *sorted(DOCS.rglob("*.md")),
            *sorted(ROOT.glob("plugins/*/src/README.md"))]


class DocsCoverageTests(unittest.TestCase):
    def test_every_skill_is_in_the_skills_reference(self):
        text = (DOCS / "reference/skills.md").read_text(encoding="utf-8")
        skills = sorted(p.name for p in ROOT.glob("plugins/*/src/skills/*") if p.is_dir())
        self.assertTrue(skills)
        self.assertEqual([s for s in skills if f"`{s}`" not in text], [])

    def test_every_cli_subcommand_has_a_heading(self):
        done = subprocess.run([sys.executable, "-m", "workflow_core.cli"], cwd=SCRIPTS,
                              capture_output=True, text=True)
        commands = re.search(r"\{([^}]+)\}", done.stderr).group(1).split(",")
        text = (DOCS / "reference/cli.md").read_text(encoding="utf-8")
        self.assertEqual([c for c in commands if f"## `gin-workflow {c}" not in text], [])

    def test_relative_links_resolve(self):
        dead = []
        for page in pages():
            for target in LINK.findall(page.read_text(encoding="utf-8")):
                path = target.split("#", 1)[0]
                if not path or re.match(r"[a-z]+:", path):
                    continue
                if not (page.parent / path).exists():
                    dead.append(f"{page.relative_to(ROOT)} -> {target}")
        self.assertEqual(dead, [])

    def test_every_docs_page_is_in_the_readme_map(self):
        readme = ROOT / "README.md"
        linked = {(ROOT / target.split("#", 1)[0]).resolve()
                  for target in LINK.findall(readme.read_text(encoding="utf-8"))}
        self.assertEqual([str(p.relative_to(ROOT)) for p in sorted(DOCS.rglob("*.md")) if p.resolve() not in linked], [])

    def test_mermaid_blocks_name_a_diagram_type(self):
        bad = [f"{p.relative_to(ROOT)}: {kind}" for p in pages()
               for kind in MERMAID.findall(p.read_text(encoding="utf-8")) if kind not in TYPES]
        self.assertEqual(bad, [])

    def test_no_doc_calls_beads_the_default(self):
        bad = [f"{p.relative_to(ROOT)}:{n}: {line.strip()}" for p in pages()
               for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
               if BEADS_DEFAULT.search(line) and "optional" not in line]
        self.assertEqual(bad, [])

    def test_no_doc_mentions_workflow_providers(self):
        bad = [str(p.relative_to(ROOT)) for p in pages() if "workflow_providers" in p.read_text(encoding="utf-8")]
        self.assertEqual(bad, [])

    def test_no_doc_mentions_telegram_sh(self):
        targets = sorted(set(pages()) | set(ROOT.glob("plugins/*/src/skills/**/*.md")) | set(ROOT.glob("plugins/*/src/agents/*.md")) | {ROOT / "install.sh", ROOT / "install.ps1"})
        bad = [f"{p.relative_to(ROOT)}:{n}: {line.strip()}" for p in targets if p.exists()
               for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
               if "telegram.sh" in line or "telegram-notify" in line]
        self.assertEqual(bad, [])

    def test_style_check_catches_each_rule(self):
        sample = ("# Title\n## 2. Step\n- **Label:** text\n1. **Bold** start\n"
                  "A \u2014 dash\nDone \u2705\n```\n## 3. In code\n```\n")
        self.assertEqual(["2: numbered heading", "3: bold-label item", "4: bold-label item", "5: dash", "6: emoji"],
                         style_violations(sample))

    def test_pages_follow_the_mechanical_style_rules(self):
        problems = [f"{page.relative_to(ROOT).as_posix()}:{found}"
                    for page in [ROOT / "README.md", *sorted(DOCS.rglob("*.md"))]
                    if page.relative_to(ROOT).as_posix() not in STYLE_EXEMPT
                    for found in style_violations(page.read_text(encoding="utf-8"))]
        self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main()
