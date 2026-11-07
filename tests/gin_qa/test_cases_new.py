"""`gin-qa cases new`: the file it writes, the SDD and legacy references, and every refusal."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from qa_fixtures import AUTH_SPEC, gin_workflow_bin, make_repo, qa, write  # noqa: E402

FILE = "qa/cases/auth/TC-AUTH-001-cancel-an-order.manual.md"


class NewCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.bin = gin_workflow_bin(self.base)
        self.root = make_repo(self.base / "repo")
        write(self.root, "docs/specs/auth/spec.md", AUTH_SPEC)

    def tearDown(self):
        self.tmp.cleanup()

    def new(self, *args: str, title: str = "Cancel an order"):
        return qa(self.root, self.bin, "new", "auth", "--type", "manual", "--title", title, *args)

    def nothing_written(self) -> None:
        self.assertEqual([], list((self.root / "qa/cases").glob("**/*.md")) if (self.root / "qa/cases").exists() else [])
        self.assertFalse((self.root / "qa/cases/auth").exists())

    def test_writes_a_named_pinned_file_with_the_next_id(self):
        result = self.new("--req", "REQ-AUTH-001", "--format", "json")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual({"tc": "TC-AUTH-001", "file": FILE}, json.loads(result.stdout))
        text = (self.root / FILE).read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# TC-AUTH-001: Cancel an order\n"))
        self.assertRegex(text, r"- \*\*REQ:\*\* REQ-AUTH-001@[0-9a-f]{8}\n- \*\*Priority:\*\* medium\n")
        for heading in ("Preconditions", "Test data", "Steps", "Expected"):
            self.assertIn(f"**{heading}:**\n", text)
        second = self.new("--req", "REQ-AUTH-001", title="Second")
        self.assertEqual("qa/cases/auth/TC-AUTH-002-second.manual.md", second.stdout.strip())

    def test_refusals_write_nothing(self):
        write(self.root, "qa/guidelines.md", "# Guidelines\n\n## Types\n\n- `manual`: by hand\n")
        for args in (("--req", "REQ-AUTH-999"), ("--source", "x.md"), ()):
            with self.subTest(args=args):
                self.assertEqual(2, self.new(*args).returncode)
                self.nothing_written()
        self.assertEqual(2, self.new("--req", "REQ-AUTH-001", title="").returncode)
        self.nothing_written()
        unlisted = qa(self.root, self.bin, "new", "auth", "--type", "e2e", "--title", "T", "--req", "REQ-AUTH-001")
        self.assertEqual(2, unlisted.returncode)
        self.assertIn("## Types", unlisted.stderr)
        self.nothing_written()

    def test_a_flat_cases_file_is_refused(self):
        write(self.root, "qa/cases/auth.md", "# Test cases: auth\n")
        result = self.new("--req", "REQ-AUTH-001")
        self.assertEqual(2, result.returncode)
        self.assertIn("gin-qa cases split auth", result.stderr)
        self.assertFalse((self.root / "qa/cases/auth").exists())

    def test_a_repeated_req_is_pinned_once(self):
        result = self.new("--req", "REQ-AUTH-001", "--req", "REQ-AUTH-001")
        self.assertEqual(0, result.returncode, result.stderr)
        text = (self.root / FILE).read_text(encoding="utf-8")
        self.assertEqual(1, text.count("REQ-AUTH-001@"))

    def test_the_legacy_layout_takes_a_source(self):
        root = make_repo(self.base / "legacy", layout="legacy")
        args = ("new", "auth", "--type", "manual", "--title", "T")
        self.assertEqual(2, qa(root, self.bin, *args, "--req", "REQ-AUTH-001").returncode)
        result = qa(root, self.bin, *args, "--source", ".planning/specs/a.md#US-1")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("- **Source:** .planning/specs/a.md#US-1\n", (root / result.stdout.strip()).read_text(encoding="utf-8"))
