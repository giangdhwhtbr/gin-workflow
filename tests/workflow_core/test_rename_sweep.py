"""No `gin-workflow` command or `gin-workflow:` namespace left after the rename (gin-workflow-rename-gin)."""

from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "plugins/gin-workflow/src/scripts"))

from workflow_core.cli import TOP_COMMANDS  # noqa: E402

ROOTS = ("plugins/gin-workflow/src", "plugins/gin-qa/src", "plugins/gin-orchestrator/src", "tests",
         "docs", "README.md", "AGENTS.md")
# Files that must keep an old name: migration of old installs and markers, and this test.
ALLOWED = {
    "plugins/gin-workflow/src/scripts/workflow_core/hooks.py",
    "plugins/gin-workflow/src/scripts/workflow_core/agents_block.py",
    "plugins/gin-workflow/src/scripts/workflow_core/team_init.py",
    "tests/workflow_core/test_hooks.py",
    "tests/workflow_core/test_agents_block.py",
    "tests/workflow_core/test_team_init.py",
    "tests/workflow_core/test_rename_sweep.py",
    "tests/install_smoke_test.sh",
    "tests/install_smoke_test.ps1",
    "docs/reference/troubleshooting.md",  # the 2.x upgrade note names the old command
}
COMMAND = re.compile(r"(?<![\w./-])gin-workflow (?:%s)\b|(?<![\w.-])gin-workflow:(?!start|end)"
                     % "|".join(map(re.escape, TOP_COMMANDS)))
OLD_SKILL = re.compile(r"(?<![\w.#@-])gin-(?:knowledge|sdd|team|worktrees|debugging|review-response|parallel-agents)(?![\w-])")
BARE_PROGRAM = re.compile(r"`gin-workflow`")
SUFFIXES = {".md", ".py", ".json", ".yaml", ".yml", ".toml", ".sh", ".ps1", ".txt", ".html", ""}


def scanned():
    for name in ROOTS:
        for path in ([ROOT / name] if (ROOT / name).is_file() else sorted((ROOT / name).rglob("*"))):
            rel = path.relative_to(ROOT).as_posix()
            if (path.is_file() and path.suffix in SUFFIXES and rel not in ALLOWED
                    and not {"dist", "__pycache__", "fixtures"} & set(path.parts)):
                yield rel, path.read_text(encoding="utf-8", errors="replace")


class RenameSweepTests(unittest.TestCase):
    def test_no_old_command_or_namespace(self):
        for rel, text in scanned():
            for number, line in enumerate(text.splitlines(), 1):
                with self.subTest(file=rel, line=number):
                    self.assertIsNone(COMMAND.search(line), line)

    def test_no_old_skill_name(self):
        for rel, text in scanned():
            for number, line in enumerate(text.splitlines(), 1):
                with self.subTest(file=rel, line=number):
                    self.assertIsNone(OLD_SKILL.search(line), line)

    def test_no_bare_program_name_in_code_span(self):
        for rel, text in scanned():
            for number, line in enumerate(text.splitlines(), 1):
                with self.subTest(file=rel, line=number):
                    self.assertIsNone(BARE_PROGRAM.search(line), line)
