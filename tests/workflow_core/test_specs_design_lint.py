"""US-5: legacy design spec lint."""

from __future__ import annotations

import contextlib
import io
from pathlib import Path
import tempfile
import unittest

from tests.workflow_core.specs_fixtures import make_repo, write
from workflow_core import specs, specs_cli

GOOD = "# T\n\n### US-1: a\n\n**Acceptance criteria:**\n  - x\n\n### US-2: b\n\nAcceptance criteria:\n- y\n"


class TestDesignSpecLint(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = make_repo(Path(self.tmp.name) / "r", layout="legacy")

    def lint(self, text: str) -> list[str]:
        return specs.lint_design_spec(write(self.root, "spec.md", text))

    def test_us5_clean_spec(self):
        self.assertEqual([], self.lint(GOOD))

    def test_us5_missing_criteria_names_story(self):
        errors = self.lint("### US-1: a\n\nAcceptance criteria:\n- x\n\n### US-2: b\n\ntext\n")
        self.assertEqual(1, len(errors))
        self.assertIn("US-2", errors[0])

    def test_us5_empty_bullet_is_an_error(self):
        errors = self.lint("### US-1: a\n\nAcceptance criteria:\n-\n")
        self.assertEqual(1, len(errors))

    def test_us5_no_stories(self):
        errors = self.lint("# T\n\ntext\n")
        self.assertEqual(1, len(errors))
        self.assertIn("no user stories", errors[0])

    def test_us5_placeholders_in_prose(self):
        errors = self.lint(GOOD + "\n{{title}}\nTBD\nTODO\n")
        self.assertEqual(3, len(errors))
        self.assertIn(":13:", errors[0])

    def test_us5_placeholders_in_code_are_ignored(self):
        self.assertEqual([], self.lint(GOOD + "\nuse `TBD` and `{{x}}`\n```\nTODO {{y}}\n```\n"))

    def test_us5_subheading_does_not_end_story(self):
        before = "### US-1: a\n\n#### Notes\n\nAcceptance criteria:\n- x\n"
        after = "### US-1: a\n\nAcceptance criteria:\n- x\n\n#### Notes\n\ntext\n"
        self.assertEqual([], self.lint(before))
        self.assertEqual([], self.lint(after))

    def test_us5_existing_specs_lint_clean_or_have_no_stories(self):
        for path in sorted((Path(__file__).resolve().parents[2] / ".planning/specs").glob("*.md")):
            errors = specs.lint_design_spec(path)
            self.assertTrue(errors == [] or (len(errors) == 1 and "no user stories" in errors[0]), (path, errors))

    def test_us5_cli_lint_spec(self):
        bad = write(self.root, "bad.md", "# T\n")
        good = write(self.root, "good.md", GOOD)
        for path, code in ((bad, 1), (good, 0)):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(code, specs_cli.main(["lint", "--spec", str(path), "--repository", str(self.root)]))


if __name__ == "__main__":
    unittest.main()
