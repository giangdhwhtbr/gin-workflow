"""SDD archive (delta -> living spec), traceability, spec-review status, and an end-to-end cycle."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from specs_fixtures import (ADDED_BLOCK, AUTH_SPEC, LAUNCHER, commit_all, delta, git,  # noqa: E402
                            make_change, make_repo, write)
from workflow_core import specs, specs_trace  # noqa: E402
from workflow_core.specs_archive import ArchiveConflict, archive  # noqa: E402

TODAY = __import__("datetime").date(2026, 10, 3)
MODIFIED = """### REQ-AUTH-002: Reject wrong password
<!-- base: {base} -->
The system SHALL reject a wrong password and count the failure.

#### Scenario: wrong password
- GIVEN a registered user
- WHEN they submit a wrong password
- THEN they see "Invalid credentials" and the failure count grows
"""


class TestArchive(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = make_repo(Path(self.tmp.name) / "repo")
        write(self.root, "docs/specs/auth/spec.md", AUTH_SPEC)
        write(self.root, "docs/specs/README.md", "# Specs\n\n## Capabilities\n- [auth](auth/spec.md)\n")
        self.cfg = specs.sdd_config(specs.load_config(self.root))
        self.base2 = specs.requirement_hash(self.root, self.cfg, "REQ-AUTH-002")[1]
        self.base1 = specs.requirement_hash(self.root, self.cfg, "REQ-AUTH-001")[1]

    def tearDown(self):
        self.tmp.cleanup()

    def test_applies_added_modified_removed_and_new_capability(self):
        billing = ADDED_BLOCK.replace("REQ-AUTH-003", "REQ-BILLING-001")
        change = make_change(self.root, spec_delta=delta(
            added=ADDED_BLOCK + "\n" + billing, modified=MODIFIED.format(base=self.base2),
            removed=f"### REQ-AUTH-001: Sign in with password\n<!-- base: {self.base1} -->\nReason: replaced by SSO\n"))
        commit_all(self.root)
        result = archive(self.root, self.cfg, change, today=TODAY)
        auth = (self.root / "docs/specs/auth/spec.md").read_text(encoding="utf-8")
        self.assertNotIn("REQ-AUTH-001", auth)
        self.assertIn("and count the failure.", auth)
        self.assertNotIn("<!-- base:", auth)
        self.assertTrue(auth.rstrip().endswith("- THEN the account is locked"))
        self.assertEqual(["REQ-AUTH-002", "REQ-AUTH-003"], [b.id for b in specs.parse_blocks(auth)[0]])
        billing_spec = (self.root / "docs/specs/billing/spec.md").read_text(encoding="utf-8")
        self.assertTrue(billing_spec.startswith("# Billing\n"))
        self.assertIn("### REQ-BILLING-001", billing_spec)
        self.assertIn("- [billing](billing/spec.md)", (self.root / "docs/specs/README.md").read_text(encoding="utf-8"))
        self.assertEqual("docs/changes/archive/2026-10-03-ep-1-lockout", result["archived_to"])
        self.assertFalse(change.exists())
        self.assertTrue((self.root / result["archived_to"] / "spec-delta.md").is_file())
        self.assertTrue(any(line.startswith("R") for line in git(self.root, "status", "--porcelain").splitlines()))
        self.assertEqual([], specs.lint_living(self.root, self.cfg))

    def test_base_hash_conflict_writes_nothing(self):
        change = make_change(self.root, spec_delta=delta(modified=MODIFIED.format(base=self.base2)))
        write(self.root, "docs/specs/auth/spec.md", AUTH_SPEC.replace("reject a wrong password.", "reject it."))
        before = (self.root / "docs/specs/auth/spec.md").read_text(encoding="utf-8")
        with self.assertRaises(ArchiveConflict) as caught:
            archive(self.root, self.cfg, change, today=TODAY)
        self.assertIn("REQ-AUTH-002: living block changed since the delta was written", caught.exception.errors[0])
        self.assertEqual(before, (self.root / "docs/specs/auth/spec.md").read_text(encoding="utf-8"))
        self.assertTrue(change.is_dir())

    def test_lint_errors_block_archive(self):
        change = make_change(self.root, spec_delta=delta(added="### REQ-AUTH-003: X\nNo statement.\n"))
        with self.assertRaises(ArchiveConflict):
            archive(self.root, self.cfg, change, today=TODAY)
        self.assertTrue(change.is_dir())


class TestTraceAndStatus(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = make_repo(Path(self.tmp.name) / "repo")
        write(self.root, "docs/specs/auth/spec.md", AUTH_SPEC)
        self.cfg = specs.sdd_config(specs.load_config(self.root))
        base = specs.requirement_hash(self.root, self.cfg, "REQ-AUTH-002")[1]
        self.change = make_change(self.root, spec_delta=delta(added=ADDED_BLOCK, modified=MODIFIED.format(base=base)))

    def tearDown(self):
        self.tmp.cleanup()

    def test_trace_finds_code_tags_and_tests_md_rows(self):
        write(self.root, "tests/test_lockout.py", "def test_lock():  # REQ-AUTH-003\n    pass\n")
        write(self.root, "src/notes.py", "# REQ-AUTH-002 is not a test file\n")
        commit_all(self.root)
        result = specs_trace.trace(self.root, self.cfg, self.change)
        self.assertEqual(["REQ-AUTH-002"], result["missing"])
        self.assertEqual(["tests/test_lockout.py"], result["requirements"][0]["sources"])
        write(self.root, "docs/changes/ep-1-lockout/tests.md",
              "| TC | REQ | type | evidence |\n|---|---|---|---|\n| TC-1 | REQ-AUTH-002 | manual | screenshot.png |\n"
              "| TC-2 | REQ-AUTH-002 | manual | - |\n")
        result = specs_trace.trace(self.root, self.cfg, self.change)
        self.assertEqual([], result["missing"])
        self.assertEqual(["docs/changes/ep-1-lockout/tests.md#TC-1"], result["requirements"][1]["sources"])

    def _gh(self, stdout: str, returncode: int = 0):
        return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr="boom")

    def test_status_states(self):
        with mock.patch("workflow_core.specs_trace.shutil.which", return_value=None):
            self.assertEqual("gh_unavailable", specs_trace.status(self.root, self.change)["status"])
        cases = [("[]", {"status": "none"}),
                 ('[{"url": "u", "state": "OPEN", "mergeCommit": null}]', {"status": "open", "url": "u"}),
                 ('[{"url": "u", "state": "MERGED", "mergeCommit": {"oid": "abc"}}]',
                  {"status": "merged", "url": "u", "merge_commit": "abc"}),
                 ('[{"url": "u", "state": "CLOSED", "mergeCommit": null}]', {"status": "closed", "url": "u"})]
        for stdout, expected in cases:
            with self.subTest(stdout=stdout), \
                    mock.patch("workflow_core.specs_trace.shutil.which", return_value="/usr/bin/gh"), \
                    mock.patch("workflow_core.specs_trace.subprocess.run", return_value=self._gh(stdout)) as run:
                result = specs_trace.status(self.root, self.change)
                self.assertEqual({"change": "ep-1-lockout", "branch": "spec/ep-1-lockout", **expected}, result)
                self.assertIn("spec/ep-1-lockout", run.call_args.args[0])
        with mock.patch("workflow_core.specs_trace.shutil.which", return_value="/usr/bin/gh"), \
                mock.patch("workflow_core.specs_trace.subprocess.run", return_value=self._gh("", 1)):
            with self.assertRaises(specs.SpecsError):
                specs_trace.status(self.root, self.change)


class TestEndToEnd(unittest.TestCase):
    def run_specs(self, root: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(LAUNCHER), "specs", *args, "--repository", str(root)],
                              text=True, capture_output=True, check=False)

    def test_new_delta_lint_trace_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = make_repo(Path(directory) / "repo")
            write(root, "docs/specs/auth/spec.md", AUTH_SPEC)
            commit_all(root)
            self.assertEqual(0, self.run_specs(root, "new", "lockout", "--epic", "ep-1").returncode)
            req = self.run_specs(root, "next-id", "auth").stdout.strip()
            write(root, "docs/changes/ep-1-lockout/spec-delta.md", delta(added=ADDED_BLOCK.replace("REQ-AUTH-003", req)))
            self.assertEqual(0, self.run_specs(root, "lint", "--change", "ep-1", "--against", "main").returncode)
            self.assertEqual(1, self.run_specs(root, "trace", "--change", "ep-1").returncode)
            write(root, "tests/test_lockout.py", f"def test_lock():  # {req}\n    pass\n")
            commit_all(root)
            traced = json.loads(self.run_specs(root, "trace", "--change", "ep-1", "--format", "json").stdout)
            self.assertEqual([], traced["missing"])
            archived = self.run_specs(root, "archive", "--change", "ep-1", "--format", "json")
            self.assertEqual(0, archived.returncode, archived.stderr)
            self.assertIn(req, (root / "docs/specs/auth/spec.md").read_text(encoding="utf-8"))
            self.assertEqual(0, self.run_specs(root, "lint").returncode)


if __name__ == "__main__":
    unittest.main()
