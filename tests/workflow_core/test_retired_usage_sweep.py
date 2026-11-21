"""AI usage tracking was retired in gin 3.4.0: nothing shipped or documented describes it."""

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
ROOTS = ("plugins", "scripts", ".claude-plugin", "docs", "README.md", "AGENTS.md", "mkdocs.yml",
         "install.sh", "install.ps1")
# The changelog keeps the history; schemas.py keeps `usage: {budget_usd}` valid and ignored.
ALLOWED = {"docs/changelog.md", "plugins/gin-workflow/src/scripts/workflow_core/schemas.py"}
PATTERN = re.compile(r"(?<![\w-])gin usage|ai_usage|budget_usd|over_budget|usage-prices|usage_prices|usage-report"
                     r"|usage_cli|usage_logs|usage_attribution|/gin:report|@gin-report")
SUFFIXES = {".md", ".py", ".json", ".yaml", ".yml", ".toml", ".sh", ".ps1", ".txt", ".html", ""}


def scanned():
    for name in ROOTS:
        root = ROOT / name
        for path in ([root] if root.is_file() else sorted(root.rglob("*"))):
            rel = path.relative_to(ROOT).as_posix()
            if (path.is_file() and path.suffix in SUFFIXES and rel not in ALLOWED
                    and not {"dist", "__pycache__", "fixtures"} & set(path.parts)):
                yield rel, path.read_text(encoding="utf-8", errors="replace")


class RetiredUsageSweepTests(unittest.TestCase):
    def test_nothing_describes_ai_usage_tracking(self):
        for rel, text in scanned():
            with self.subTest(file=rel):
                for number, line in enumerate(text.splitlines(), 1):
                    self.assertIsNone(PATTERN.search(line), f"{rel}:{number}: {line.strip()}")
