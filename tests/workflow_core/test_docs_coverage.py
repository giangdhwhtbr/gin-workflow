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


if __name__ == "__main__":
    unittest.main()
