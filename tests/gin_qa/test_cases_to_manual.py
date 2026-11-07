"""`gin-qa cases to-manual`: the renamed case, the deleted spec, and every refusal."""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from qa_fixtures import AUTH_SPEC, case_file, cases_file, case, gin_workflow_bin, make_repo, qa, write  # noqa: E402

OLD = "qa/cases/auth/TC-AUTH-001-login.e2e.md"
NEW = "qa/cases/auth/TC-AUTH-001-login.manual.md"
SPEC = "qa/e2e/auth/tc-auth-001.spec.ts"
MOVED = re.compile(r"^- \*\*Moved from e2e:\*\* \d{4}-\d{2}-\d{2}: flaky on CI$", re.M)


class ToManualCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.bin = gin_workflow_bin(self.base)
        self.root = make_repo(self.base / "repo")
        write(self.root, "docs/specs/auth/spec.md", AUTH_SPEC)
        write(self.root, OLD, case_file("TC-AUTH-001", "REQ: REQ-AUTH-001@00000000", title="Login",
                                        extra="Result: failed\nRun: qa/evidence/x\nBug: gw-7"))
        write(self.root, SPEC, "// TC: TC-AUTH-001@00000000\n")
        self.assertEqual(0, self.cases("pin", "TC-AUTH-001").returncode)

    def tearDown(self):
        self.tmp.cleanup()

    def cases(self, *args: str):
        return qa(self.root, self.bin, *args)

    def move(self, *args: str):
        return self.cases("to-manual", "TC-AUTH-001", "--reason", "flaky on CI", *args)

    def assert_unchanged(self, result) -> None:
        self.assertEqual(2, result.returncode, result.stdout)
        self.assertTrue((self.root / OLD).is_file())
        self.assertFalse((self.root / NEW).exists())
        self.assertTrue((self.root / SPEC).is_file())


class TestToManual(ToManualCase):
    def test_renames_records_the_reason_resets_the_result_and_deletes_the_spec(self):
        result = self.move("--format", "json")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual({"tc": "TC-AUTH-001", "file": NEW, "spec": SPEC}, json.loads(result.stdout))
        text = (self.root / NEW).read_text(encoding="utf-8")
        self.assertRegex(text, MOVED)
        self.assertIn("- **Result:** not run\n", text)
        self.assertIn("- **Bug:** gw-7\n", text)
        self.assertNotIn("**Run:**", text)
        self.assertFalse((self.root / OLD).exists())
        self.assertFalse((self.root / SPEC).exists())

    def test_checks_are_clean_and_the_hash_is_kept(self):
        before = json.loads(self.cases("export", "--format", "json").stdout)["cases"][0]["hash8"]
        self.assertEqual(0, self.move().returncode)
        after = json.loads(self.cases("export", "--format", "json").stdout)["cases"][0]
        self.assertEqual((before, "manual"), (after["hash8"], after["type"]))
        self.assertRegex(after["moved_from_e2e"]["date"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertEqual("flaky on CI", after["moved_from_e2e"]["reason"])
        self.assertNotIn("TC-AUTH-001", self.cases("check").stdout)
        self.assertNotIn("TC-AUTH-001", qa(self.root, self.bin, "check", group="e2e").stdout)

    def test_a_missing_spec_is_not_an_error(self):
        (self.root / SPEC).unlink()
        result = self.move()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual([NEW, "no spec"], result.stdout.split("\n")[:2])

    def test_crlf_line_endings_are_kept(self):
        path = self.root / OLD
        path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
        self.assertEqual(0, self.move().returncode)
        self.assertIn(b"\r\n", (self.root / NEW).read_bytes())
        self.assertNotIn(b"\n", (self.root / NEW).read_bytes().replace(b"\r\n", b""))


class TestRefusals(ToManualCase):
    def test_bad_reasons(self):
        for reason in ("", "   ", "two\nlines"):
            with self.subTest(reason=reason):
                self.assert_unchanged(self.cases("to-manual", "TC-AUTH-001", "--reason", reason))

    def test_unknown_case(self):
        self.assertEqual(2, self.cases("to-manual", "TC-AUTH-099", "--reason", "x").returncode)

    def test_a_manual_case(self):
        write(self.root, "qa/cases/auth/TC-AUTH-002-pay.manual.md",
              case_file("TC-AUTH-002", "REQ: REQ-AUTH-002@00000000", title="Pay"))
        result = self.cases("to-manual", "TC-AUTH-002", "--reason", "x")
        self.assertEqual(2, result.returncode)
        self.assertIn("only an e2e case", result.stderr)

    def test_manual_not_listed_in_the_guidelines(self):
        write(self.root, "qa/guidelines.md", "# Guidelines\n\n## Types\n\n- `e2e`: browser\n")
        result = self.move()
        self.assert_unchanged(result)
        self.assertIn("manual", result.stderr)

    def test_a_flat_cases_file(self):
        (self.root / OLD).unlink()
        write(self.root, "qa/cases/auth.md", cases_file("auth", case("TC-AUTH-001", "REQ: REQ-AUTH-001@00000000")))
        result = self.move()
        self.assertEqual(2, result.returncode)
        self.assertIn("gin-qa cases split auth", result.stderr)

    def test_a_malformed_moved_line_is_a_check_finding(self):
        path = self.root / OLD
        path.write_text(path.read_text(encoding="utf-8").replace(
            "- **Priority:** high\n", "- **Priority:** high\n- **Moved from e2e:** yesterday\n"), encoding="utf-8")
        result = self.cases("check")
        self.assertEqual(1, result.returncode)
        self.assertIn("Moved from e2e", result.stdout)
