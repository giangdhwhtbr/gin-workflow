"""gin-orchestrator was retired in gin 3.3.0: nothing shipped or documented names it."""

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
ROOTS = ("plugins", "scripts", ".claude-plugin", "docs", "README.md", "AGENTS.md", "mkdocs.yml")
# History and upgrade notes keep the name. install.sh and install.ps1 are not swept:
# they name the plugin to refuse and remove it, and the install smoke tests cover them.
ALLOWED = {"docs/changelog.md", "docs/guides/upgrading.md", "docs/guides/upgrading.vi.md"}
NAMES = ("gin-orchestrator", "gin_orchestrator")
SUFFIXES = {".md", ".py", ".json", ".yaml", ".yml", ".toml", ".sh", ".ps1", ".txt", ".html", ""}


def scanned():
    for name in ROOTS:
        root = ROOT / name
        for path in ([root] if root.is_file() else sorted(root.rglob("*"))):
            rel = path.relative_to(ROOT).as_posix()
            if (path.is_file() and path.suffix in SUFFIXES and rel not in ALLOWED
                    and not {"dist", "__pycache__", "fixtures"} & set(path.relative_to(ROOT).parts)):
                yield rel, path.read_text(encoding="utf-8", errors="replace")


class RetiredExtensionSweepTests(unittest.TestCase):
    def test_nothing_names_the_retired_extension(self):
        for rel, text in scanned():
            with self.subTest(file=rel):
                for number, line in enumerate(text.splitlines(), 1):
                    self.assertFalse(any(name in line for name in NAMES), f"{rel}:{number}: {line.strip()}")

    def test_the_extension_sources_are_gone(self):
        self.assertFalse((ROOT / "plugins/gin-orchestrator/src").exists())
        self.assertFalse((ROOT / "plugins/gin-orchestrator/plugin.meta.json").exists())
        self.assertFalse((ROOT / "tests/gin_orchestrator").exists())
