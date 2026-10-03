"""`gin-qa cases`: plan, next-id, pin, check, and export over an SDD repository."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from qa_fixtures import (ADDED_BLOCK, AUTH_SPEC, case, cases_file, commit_all, delta, gin_workflow_bin,  # noqa: E402
                         hash8, make_change, make_repo, qa, write)


class QaCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.bin = gin_workflow_bin(self.base)
        self.root = make_repo(self.base / "repo")
        write(self.root, "docs/specs/auth/spec.md", AUTH_SPEC)

    def tearDown(self):
        self.tmp.cleanup()

    def ref(self, *reqs: str) -> str:
        return "REQ: " + ", ".join(f"{req}@{hash8(self.root, self.bin, req)}" for req in reqs)

    def write_cases(self, *blocks: str, cap: str = "auth") -> Path:
        return write(self.root, f"qa/cases/{cap}.md", cases_file(cap, *blocks))

    def run_json(self, *args: str) -> dict:
        result = qa(self.root, self.bin, *args, "--format", "json")
        self.assertIn(result.returncode, (0, 1), result.stderr)
        return json.loads(result.stdout)

    def findings(self) -> list[str]:
        return self.run_json("check")["findings"]


class TestPlanAndCheck(QaCase):
    def test_plan_lists_missing_with_scenarios_and_paths(self):
        payload = self.run_json("plan", "auth")
        self.assertEqual(("sdd", "qa/cases", "qa/guidelines.md"),
                         (payload["layout"], payload["cases"], payload["guidelines"]))
        self.assertEqual(["REQ-AUTH-001", "REQ-AUTH-002"], [row["req"] for row in payload["missing"]])
        first = payload["missing"][0]
        self.assertEqual(("docs/specs/auth/spec.md:9", "valid password", hash8(self.root, self.bin, "REQ-AUTH-001")),
                         (first["source"], first["scenarios"][0]["title"], first["hash8"]))
        self.assertEqual([], payload["stale"] + payload["obsolete"])
        self.assertEqual([], self.run_json("plan", "billing")["missing"])

    def test_covered_repository_checks_clean_with_free_fields(self):
        self.write_cases(case("TC-AUTH-001", self.ref("REQ-AUTH-001"), extra="Owner: qa-team\nBrowser: firefox\n"),
                         case("TC-AUTH-002", self.ref("REQ-AUTH-001", "REQ-AUTH-002")))
        result = qa(self.root, self.bin, "check")
        self.assertEqual((0, "ok\n"), (result.returncode, result.stdout), result.stderr)

    def test_uncovered_requirement_is_a_finding(self):
        self.write_cases(case("TC-AUTH-001", self.ref("REQ-AUTH-001")))
        self.assertEqual(["docs/specs/auth/spec.md:17: REQ-AUTH-002 has no test case"], self.findings())

    def test_edited_requirement_marks_exactly_its_cases_stale_until_pinned(self):
        self.write_cases(case("TC-AUTH-001", self.ref("REQ-AUTH-001")), case("TC-AUTH-002", self.ref("REQ-AUTH-002")))
        old = hash8(self.root, self.bin, "REQ-AUTH-002")
        write(self.root, "docs/specs/auth/spec.md", AUTH_SPEC.replace("reject a wrong", "reject any wrong"))
        new = hash8(self.root, self.bin, "REQ-AUTH-002")
        self.assertEqual([f"qa/cases/auth.md:18: TC-AUTH-002: REQ-AUTH-002 changed (pinned {old}, now {new}); "
                          "update the case, then `gin-qa cases pin TC-AUTH-002`"], self.findings())
        stale = self.run_json("plan", "auth")["stale"]
        self.assertEqual([("TC-AUTH-002", old, new, "docs/specs/auth/spec.md:17")],
                         [(row["tc"], row["pinned"], row["current"], row["source"]) for row in stale])
        before = (self.root / "qa/cases/auth.md").read_text()
        self.assertEqual(0, qa(self.root, self.bin, "pin", "TC-AUTH-002").returncode)
        after = (self.root / "qa/cases/auth.md").read_text()
        self.assertEqual(before.replace(f"REQ-AUTH-002@{old}", f"REQ-AUTH-002@{new}"), after)
        self.assertEqual([], self.findings())

    def test_pin_refuses_unknown_case_or_requirement_and_writes_nothing(self):
        self.write_cases(case("TC-AUTH-001", "REQ: REQ-AUTH-009@00000000"))
        before = (self.root / "qa/cases/auth.md").read_text()
        result = qa(self.root, self.bin, "pin", "TC-AUTH-001", "TC-AUTH-404")
        self.assertEqual(1, result.returncode)
        self.assertIn("TC-AUTH-001: REQ-AUTH-009 not found", result.stdout)
        self.assertIn("TC-AUTH-404: no such test case", result.stdout)
        self.assertEqual(before, (self.root / "qa/cases/auth.md").read_text())

    def test_unknown_requirement_is_obsolete(self):
        self.write_cases(case("TC-AUTH-001", self.ref("REQ-AUTH-001")), case("TC-AUTH-002", self.ref("REQ-AUTH-002")),
                         case("TC-AUTH-003", "REQ: REQ-AUTH-009@00000000"))
        self.assertEqual(["qa/cases/auth.md:33: TC-AUTH-003: REQ-AUTH-009 does not exist"], self.findings())
        obsolete = self.run_json("plan", "auth")["obsolete"]
        self.assertEqual([("TC-AUTH-003", "REQ-AUTH-009", "does not exist")],
                         [(row["tc"], row["req"], row["reason"]) for row in obsolete])


class TestChanges(QaCase):
    def test_case_for_unarchived_change_is_valid_before_and_after_archive(self):
        make_change(self.root)
        self.assertEqual(["REQ-AUTH-003"], [row["req"] for row in self.run_json("plan", "--change", "ep-1")["missing"]])
        self.write_cases(case("TC-AUTH-001", self.ref("REQ-AUTH-001")), case("TC-AUTH-002", self.ref("REQ-AUTH-002")),
                         case("TC-AUTH-003", self.ref("REQ-AUTH-003")))
        self.assertEqual([], self.findings())
        commit_all(self.root)
        result = subprocess.run([str(self.bin / "gin-workflow"), "specs", "archive", "--change", "ep-1",
                                 "--repository", str(self.root)], capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual([], self.findings())

    def test_change_scope_and_removed_requirement(self):
        removed = ("### REQ-AUTH-002: Reject wrong password\n<!-- base: " + "0" * 64 + " -->\nReason: merged\n")
        make_change(self.root, spec_delta=delta(added=ADDED_BLOCK, removed=removed))
        self.write_cases(case("TC-AUTH-001", self.ref("REQ-AUTH-001")), case("TC-AUTH-002", self.ref("REQ-AUTH-002")))
        work = self.run_json("plan", "--change", "ep-1")
        self.assertEqual(["REQ-AUTH-003"], [row["req"] for row in work["missing"]])
        self.assertEqual([("TC-AUTH-002", "removed by ep-1-lockout")],
                         [(row["tc"], row["reason"]) for row in work["obsolete"]])
        scoped = qa(self.root, self.bin, "check", "--change", "ep-1")
        self.assertEqual(1, scoped.returncode)
        self.assertIn("REQ-AUTH-003 has no test case", scoped.stdout)
        self.assertIn("TC-AUTH-002: REQ-AUTH-002 removed by ep-1-lockout", scoped.stdout)

    def test_two_open_changes_on_one_requirement_conflict(self):
        make_change(self.root)
        make_change(self.root, "ep-2-other", epic="ep-2", spec_delta=delta(added=ADDED_BLOCK))
        self.write_cases(case("TC-AUTH-001", self.ref("REQ-AUTH-001")), case("TC-AUTH-002", self.ref("REQ-AUTH-002")),
                         case("TC-AUTH-003", self.ref("REQ-AUTH-003")))
        self.assertEqual(["docs/changes/ep-2-other/spec-delta.md:5: REQ-AUTH-003 is changed by both ep-1-lockout "
                          "and ep-2-other"], self.findings())


class TestStructure(QaCase):
    def test_each_structure_finding_has_file_and_line(self):
        good = self.ref("REQ-AUTH-001", "REQ-AUTH-002")
        self.write_cases(
            "### TC-1: not an id\n",
            "### TC-AUTH-001: no steps\n" + good + "\n\nExpected:\n- ok\n",
            "### TC-AUTH-002: unnumbered\n" + good + "\n\nSteps:\n- open\n\nExpected:\n- ok\n",
            "### TC-AUTH-003: order\n" + good + "\n\nExpected:\n- ok\n\nSteps:\n1. open\n",
            "### TC-AUTH-004: no hash\nREQ: REQ-AUTH-001\n\nSteps:\n1. open\n\nExpected:\n- ok\n",
            "### TC-AUTH-005: no ref\nType: manual\n\nSteps:\n1. open\n\nExpected:\n- ok\n",
            "### TC-AUTH-006: twice\n" + good + "\n\nSteps:\n1. open\n\nExpected:\n- ok\n",
            "### TC-AUTH-006: again\n" + good + "\n\nSteps:\n1. open\n\nExpected:\n- ok\n",
            "### TC-BILL-001: wrong file\n" + good + "\n\nSteps:\n1. open\n\nExpected:\n- ok\n",
        )
        self.maxDiff = None
        self.assertEqual([
            "qa/cases/auth.md:3: heading is not a test case '### TC-<CAP>-<NNN>: <title>': '### TC-1: not an id'",
            "qa/cases/auth.md:5: TC-AUTH-001: needs at least one Steps item",
            "qa/cases/auth.md:15: TC-AUTH-002: steps must be numbered 1., 2., 3., ...",
            "qa/cases/auth.md:11: TC-AUTH-002: needs at least one Steps item",
            "qa/cases/auth.md:26: TC-AUTH-003: sections must appear once, in the order Preconditions, Steps, Expected",
            "qa/cases/auth.md:30: TC-AUTH-004: REQ entries are 'REQ-<CAP>-<NNN>@<hash8>' separated by ', ', "
            "got 'REQ-AUTH-001'",
            "qa/cases/auth.md:65: TC-BILL-001 belongs in qa/cases/bill.md, not auth.md",
            "qa/cases/auth.md:56: duplicate TC-AUTH-006 (first at qa/cases/auth.md:47)",
            "qa/cases/auth.md:38: TC-AUTH-005: needs a REQ: field",
        ], self.findings())

    def test_cases_path_inside_test_globs_is_a_finding(self):
        config = self.root / ".agent-workflow/config.yaml"
        config.write_text(config.read_text() + "qa:\n  cases: tests/cases\n")
        write(self.root, "tests/cases/auth.md", cases_file("auth", case("TC-AUTH-001", self.ref("REQ-AUTH-001", "REQ-AUTH-002"))))
        self.assertEqual(["tests/cases: matches artifacts.test_globs pattern 'tests/**'; test cases would count as "
                          "executed tests in specs trace"], self.findings())


class TestIdsAndExport(QaCase):
    def test_next_id_never_reuses_a_number(self):
        self.assertEqual("TC-AUTH-001\n", qa(self.root, self.bin, "next-id", "auth").stdout)
        self.write_cases(case("TC-AUTH-001", self.ref("REQ-AUTH-001")), case("TC-AUTH-002", self.ref("REQ-AUTH-002")))
        self.assertEqual("TC-AUTH-003\n", qa(self.root, self.bin, "next-id", "auth").stdout)
        commit_all(self.root)
        self.write_cases(case("TC-AUTH-001", self.ref("REQ-AUTH-001", "REQ-AUTH-002")))
        self.assertEqual("TC-AUTH-003\n", qa(self.root, self.bin, "next-id", "auth").stdout)
        self.assertEqual("TC-USER-AUTH-001\n", qa(self.root, self.bin, "next-id", "user-auth").stdout)

    def test_export_keeps_free_fields(self):
        self.write_cases(case("TC-AUTH-001", self.ref("REQ-AUTH-001"), title="Login", extra="Owner: qa-team\n"))
        rows = self.run_json("export")["cases"]
        self.assertEqual([{
            "id": "TC-AUTH-001", "title": "Login", "capability": "auth", "file": "qa/cases/auth.md", "line": 3,
            "reqs": [{"id": "REQ-AUTH-001", "hash8": hash8(self.root, self.bin, "REQ-AUTH-001")}], "source": "",
            "type": "e2e", "priority": "high", "fields": {"Owner": "qa-team"},
            "preconditions": ["a user exists"], "steps": ["Open /login", 'Click "Sign in"'],
            "expected": ["The dashboard is shown"]}], rows)


class TestLegacyAndEnvironment(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_legacy_layout_needs_source_and_checks_structure_only(self):
        bin_dir = gin_workflow_bin(self.base)
        root = make_repo(self.base / "legacy", layout="legacy")
        write(root, "qa/cases/auth.md", cases_file("auth", case("TC-AUTH-001", "Source: .planning/specs/a.md#Login")))
        self.assertEqual(0, qa(root, bin_dir, "check").returncode)
        self.assertEqual([], json.loads(qa(root, bin_dir, "plan", "auth", "--format", "json").stdout)["missing"])
        write(root, "qa/cases/auth.md", cases_file("auth", case("TC-AUTH-001", "Type: manual")))
        result = qa(root, bin_dir, "check")
        self.assertEqual(1, result.returncode)
        self.assertIn("TC-AUTH-001: needs a Source: field", result.stdout)

    def test_missing_or_old_gin_workflow_and_missing_setup_exit_2(self):
        root = make_repo(self.base / "repo")
        result = qa(root, None, "check")
        self.assertEqual(2, result.returncode)
        self.assertIn("gin-workflow is not on PATH", result.stderr)
        old = gin_workflow_bin(self.base / "old", "#!/bin/sh\necho \"error: argument command: invalid choice: 'reqs'\" >&2\nexit 2\n")
        result = qa(root, old, "check")
        self.assertEqual(2, result.returncode)
        self.assertIn("no `specs reqs`; reinstall a newer gin-workflow", result.stderr)
        bare = self.base / "bare"
        bare.mkdir()
        result = qa(bare, gin_workflow_bin(self.base), "check")
        self.assertEqual(2, result.returncode)
        self.assertIn("run /setup once", result.stderr)


if __name__ == "__main__":
    unittest.main()
