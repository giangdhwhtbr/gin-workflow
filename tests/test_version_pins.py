"""The launcher versions pinned in the installers, the CLIs, and the smoke tests agree."""

from __future__ import annotations

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


def _pin(path: str, pattern: str) -> str:
    match = re.search(pattern, (ROOT / path).read_text(encoding="utf-8"), re.MULTILINE)
    assert match, f"{path}: no match for {pattern!r}"
    return match.group(1)


class VersionPinTests(unittest.TestCase):
    def test_gin_launcher_version_matches_the_cli(self):
        cli = _pin("plugins/gin-workflow/src/scripts/workflow_core/cli.py", r'^CLI_VERSION = "([^"]+)"')
        self.assertEqual(cli, _pin("install.sh", r'^LAUNCHER_VERSION="([^"]+)"'))
        self.assertEqual(cli, _pin("install.ps1", r"^\$LauncherVersion = '([^']+)'"))

    def test_gin_qa_launcher_version_matches_the_cli_and_the_smoke_tests(self):
        cli = _pin("plugins/gin-qa/src/scripts/gin_qa/cli.py", r'^VERSION = "([^"]+)"')
        self.assertEqual(cli, _pin("install.sh", r'^QA_LAUNCHER_VERSION="([^"]+)"'))
        self.assertEqual(cli, _pin("install.ps1", r"^\$QaLauncherVersion = '([^']+)'"))
        self.assertEqual(cli, _pin("tests/install_smoke_test.sh", r'"gin-qa ([0-9.]+)"'))
        self.assertEqual(cli, _pin("tests/install_smoke_test.sh", r"gin-qa\) addon_version=([0-9.]+)"))
        self.assertEqual(cli, _pin("tests/install_smoke_test.ps1", r"Name = 'gin-qa'; Old = '[0-9.]+'; Current = '([0-9.]+)'"))


if __name__ == "__main__":
    unittest.main()
