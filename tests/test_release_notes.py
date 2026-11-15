"""scripts/release_notes.py prints one changelog section for the GitHub release (R13)."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("release_notes", ROOT / "scripts/release_notes.py")
release_notes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release_notes)

TWO = "# Changelog\n\nintro\n\n## [2.0.0] - 2026-02-01\n\nNew.\n\n### Added\n\n- one\n\n## [1.0.0] - 2026-01-01\n\nOld.\n"


def run_main(args: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = release_notes.main(args)
    return code, out.getvalue(), err.getvalue()


class SectionTests(unittest.TestCase):
    def test_returns_the_first_section_without_the_second(self):
        text = release_notes.section(TWO, "2.0.0")
        self.assertEqual("New.\n\n### Added\n\n- one", text)

    def test_returns_the_last_section_to_the_end(self):
        self.assertEqual("Old.", release_notes.section(TWO, "1.0.0"))

    def test_missing_version_raises(self):
        with self.assertRaisesRegex(ValueError, "docs/changelog.md has no section for 3.0.0"):
            release_notes.section(TWO, "3.0.0")

    def test_empty_section_raises(self):
        with self.assertRaises(ValueError):
            release_notes.section("## [2.0.0] - x\n\n## [1.0.0] - y\n\nOld.\n", "2.0.0")

    def test_heading_matches_exactly(self):
        text = "## [3.1.01] - x\n\nwrong\n\n## [13.1.0] - x\n\nwrong\n"
        with self.assertRaises(ValueError):
            release_notes.section(text, "3.1.0")

    def test_heading_in_a_code_fence_is_not_a_section(self):
        text = "## [2.0.0] - x\n\nBody.\n\n```\n## [1.0.0] - y\n```\n\nMore.\n"
        self.assertEqual("Body.\n\n```\n## [1.0.0] - y\n```\n\nMore.", release_notes.section(text, "2.0.0"))
        with self.assertRaises(ValueError):
            release_notes.section("```\n## [1.0.0] - y\n\nx\n```\n", "1.0.0")

    def test_bad_version_raises(self):
        for bad in ("3.1", "3.1.x", "v3.1.0", "3.1.0\n", "٣.1.0", ""):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                release_notes.section(TWO, bad)


class MainTests(unittest.TestCase):
    def write(self, text: str) -> str:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "changelog.md"
        path.write_text(text, encoding="utf-8")
        return str(path)

    def test_prints_the_section_and_exits_0(self):
        code, out, err = run_main(["2.0.0", "--file", self.write(TWO)])
        self.assertEqual((0, ""), (code, err))
        self.assertEqual("New.\n\n### Added\n\n- one\n", out)

    def test_reads_utf8(self):
        code, out, _ = run_main(["1.0.0", "--file", self.write("## [1.0.0] - x\n\nTiếng Việt\n")])
        self.assertEqual((0, "Tiếng Việt\n"), (code, out))

    def test_missing_version_exits_1_with_an_error(self):
        code, out, err = run_main(["9.9.9", "--file", self.write(TWO)])
        self.assertEqual((1, ""), (code, out))
        self.assertEqual("error: docs/changelog.md has no section for 9.9.9\n", err)

    def test_missing_file_exits_1(self):
        code, _, err = run_main(["1.0.0", "--file", "/nonexistent/changelog.md"])
        self.assertEqual(1, code)
        self.assertTrue(err.startswith("error: "))

    def test_bad_arguments_exit_1(self):
        for args in ([], ["1.0.0", "--file"], ["1.0.0", "extra"], ["bad"]):
            with self.subTest(args=args):
                code, _, err = run_main(args)
                self.assertEqual(1, code)
                self.assertTrue(err.startswith("error: "))


class RealChangelogTests(unittest.TestCase):
    def test_changelog_has_a_section_for_the_current_version(self):
        meta = json.loads((ROOT / "plugins/gin-workflow/plugin.meta.json").read_text(encoding="utf-8"))
        text = (ROOT / "docs/changelog.md").read_text(encoding="utf-8")
        self.assertTrue(release_notes.section(text, meta["version"]))


if __name__ == "__main__":
    unittest.main()
