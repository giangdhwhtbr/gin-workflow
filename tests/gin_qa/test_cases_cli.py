"""`gin-qa cases`: plan, next-id, pin, check, and export over an SDD repository."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "plugins/gin-qa/src/scripts"))

from qa_fixtures import (ADDED_BLOCK, AUTH_SPEC, case, case_file, cases_file, commit_all, delta, failing_stub, gin_workflow_bin,  # noqa: E402
                         hash8, make_change, make_repo, qa, write, write_activity)
from gin_qa.cases import as_dict, hash8 as case_hash8, parse_case_file, parse_file  # noqa: E402


def parse_file_text(block: str):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "auth.md"
        path.write_text(cases_file("auth", block), encoding="utf-8")
        found, errors = parse_file(path, "qa/cases/auth.md")
    assert errors == [], errors
    return found[0]


class QaCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.bin = gin_workflow_bin(self.base)
        self.root = make_repo(self.base / "repo")
        write(self.root, "docs/specs/auth/spec.md", AUTH_SPEC)
        write_activity(self.root)

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


    def test_pin_keeps_the_bold_form(self):
        path = write(self.root, "qa/cases/auth/TC-AUTH-001.e2e.md",
                     case_file("TC-AUTH-001", "REQ: REQ-AUTH-001@00000000, REQ-AUTH-002@00000000"))
        self.assertEqual(0, qa(self.root, self.bin, "pin", "TC-AUTH-001").returncode)
        first = path.read_text().splitlines()[2]
        self.assertEqual(f"- **REQ:** REQ-AUTH-001@{hash8(self.root, self.bin, 'REQ-AUTH-001')}, "
                         f"REQ-AUTH-002@{hash8(self.root, self.bin, 'REQ-AUTH-002')}", first)

    def test_pin_keeps_crlf_line_endings(self):
        path = write(self.root, "qa/cases/auth/TC-AUTH-001.e2e.md",
                     case_file("TC-AUTH-001", "REQ: REQ-AUTH-001@00000000"))
        path.write_bytes(path.read_text().replace("\n", "\r\n").encode())
        self.assertEqual(0, qa(self.root, self.bin, "pin", "TC-AUTH-001").returncode)
        data = path.read_bytes()
        self.assertNotIn(b"\n", data.replace(b"\r\n", b""))
        self.assertIn(f"REQ-AUTH-001@{hash8(self.root, self.bin, 'REQ-AUTH-001')}\r\n".encode(), data)


class TestChanges(QaCase):
    def test_case_for_unarchived_change_is_valid_before_and_after_archive(self):
        make_change(self.root)
        self.assertEqual(["REQ-AUTH-003"], [row["req"] for row in self.run_json("plan", "--change", "ep-1")["missing"]])
        self.write_cases(case("TC-AUTH-001", self.ref("REQ-AUTH-001")), case("TC-AUTH-002", self.ref("REQ-AUTH-002")),
                         case("TC-AUTH-003", self.ref("REQ-AUTH-003")))
        self.assertEqual([], self.findings())
        commit_all(self.root)
        result = subprocess.run([shutil.which("gin", path=str(self.bin)), "specs", "archive", "--change", "ep-1",
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
        self.assertEqual(["docs/changes/ep-2-other/02-spec-delta.md:5: REQ-AUTH-003 is changed by both ep-1-lockout "
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
            "qa/cases/auth.md:26: TC-AUTH-003: sections must appear once, in the order Preconditions, Test data, Steps, Expected",
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

    def test_test_globs_matching_one_case_file_is_a_finding(self):
        config = self.root / ".agent-workflow/config.yaml"
        config.write_text(config.read_text().replace("  layout: sdd\n", "  layout: sdd\n  test_globs:\n"
                                                      "    - qa/cases/auth.md\n"))
        self.write_cases(case("TC-AUTH-001", self.ref("REQ-AUTH-001", "REQ-AUTH-002")))
        self.assertEqual(["qa/cases/auth.md: matches artifacts.test_globs pattern 'qa/cases/auth.md'; test cases "
                          "would count as executed tests in specs trace"], self.findings())


class TestIdsAndExport(QaCase):
    def test_next_id_never_reuses_a_number(self):
        first = qa(self.root, self.bin, "next-id", "auth")
        self.assertEqual("TC-AUTH-001\n", first.stdout, first.stderr)
        self.write_cases(case("TC-AUTH-001", self.ref("REQ-AUTH-001")), case("TC-AUTH-002", self.ref("REQ-AUTH-002")))
        self.assertEqual("TC-AUTH-003\n", qa(self.root, self.bin, "next-id", "auth").stdout)
        commit_all(self.root)
        self.write_cases(case("TC-AUTH-001", self.ref("REQ-AUTH-001", "REQ-AUTH-002")))
        self.assertEqual("TC-AUTH-003\n", qa(self.root, self.bin, "next-id", "auth").stdout)
        self.assertEqual("TC-USER-AUTH-001\n", qa(self.root, self.bin, "next-id", "user-auth").stdout)

    def test_export_keeps_free_fields(self):
        self.write_cases(case("TC-AUTH-001", self.ref("REQ-AUTH-001"), title="Login", extra="Owner: qa-team\n"))
        rows = self.run_json("export")["cases"]
        self.assertRegex(rows[0].pop("hash8"), "^[0-9a-f]{8}$")
        self.assertEqual([{
            "id": "TC-AUTH-001", "title": "Login", "capability": "auth", "file": "qa/cases/auth.md", "line": 3,
            "reqs": [{"id": "REQ-AUTH-001", "hash8": hash8(self.root, self.bin, "REQ-AUTH-001")}], "source": "",
            "type": "e2e", "priority": "high", "fields": {"Owner": "qa-team"},
            "preconditions": ["a user exists"], "steps": ["Open /login", 'Click "Sign in"'],
            "expected": ["The dashboard is shown"], "result": "not run", "run": "", "bug": "", "test_data": []}], rows)


class TestCaseFiles(QaCase):
    def put(self, name: str, body: str) -> Path:
        return write(self.root, f"qa/cases/{name}", body)

    def test_per_case_files_load_with_type_from_the_name(self):
        self.put("auth/TC-AUTH-001-sign-in.e2e.md", case_file("TC-AUTH-001", self.ref("REQ-AUTH-001"), title="Login"))
        self.put("auth/TC-AUTH-002-2024-tax.manual.md", case_file("TC-AUTH-002", self.ref("REQ-AUTH-002"), bold=False))
        self.assertEqual([], self.findings())
        rows = {row["id"]: row for row in self.run_json("export")["cases"]}
        self.assertEqual(("e2e", "qa/cases/auth/TC-AUTH-001-sign-in.e2e.md", 1, "Login"),
                         (rows["TC-AUTH-001"]["type"], rows["TC-AUTH-001"]["file"], rows["TC-AUTH-001"]["line"],
                          rows["TC-AUTH-001"]["title"]))
        self.assertEqual("manual", rows["TC-AUTH-002"]["type"])
        self.assertEqual(("not run", "", "", []), tuple(rows["TC-AUTH-001"][key]
                                                         for key in ("result", "run", "bug", "test_data")))

    def test_each_per_case_finding(self):
        good = self.ref("REQ-AUTH-001", "REQ-AUTH-002")
        self.put("auth/TC-AUTH-001.e2e.md", case_file("TC-AUTH-001", good))
        self.put("auth/sign-in.e2e.md", case_file("TC-AUTH-002", good))
        self.put("auth/TC-AUTH-003-Bad.e2e.md", case_file("TC-AUTH-003", good))
        self.put("auth/TC-AUTH-004.e2e.md", case_file("TC-AUTH-005", good))
        self.put("auth/TC-BILL-001.e2e.md", case_file("TC-BILL-001", good))
        self.put("auth/TC-AUTH-006.e2e.md", case_file("TC-AUTH-006", good) + "\n" + case_file("TC-AUTH-007", good))
        self.put("auth/TC-AUTH-008.e2e.md", case_file("TC-AUTH-008", good).replace("- **Priority:** high",
                                                                                  "- **Type:** e2e"))
        self.put("auth/TC-AUTH-009.e2e.md", case_file("TC-AUTH-009", good, extra="Result: done\n"))
        self.put("auth/TC-AUTH-010.e2e.md", case_file("TC-AUTH-010", good, extra="Bug: gw-1\n"))
        self.put("auth/TC-AUTH-011.e2e.md", case_file("TC-AUTH-011", good).replace("# TC-AUTH-011", "### TC-AUTH-011"))
        self.write_cases(case("TC-AUTH-012", good))
        self.maxDiff = None
        self.assertEqual([
            "qa/cases/auth/TC-AUTH-003-Bad.e2e.md: case file name is not '<TC-ID>[-<slug>].<type>.md'",
            "qa/cases/auth/TC-AUTH-004.e2e.md:1: TC-AUTH-005: file name says TC-AUTH-004",
            "qa/cases/auth/TC-AUTH-006.e2e.md: holds 2 headings; a case file holds one '# TC-<CAP>-<NNN>: <title>'",
            "qa/cases/auth/TC-AUTH-008.e2e.md:4: TC-AUTH-008: Type comes from the file name; remove the Type: line",
            "qa/cases/auth/TC-AUTH-009.e2e.md:5: TC-AUTH-009: Result is one of passed, failed, blocked, not run; "
            "got 'done'",
            "qa/cases/auth/TC-AUTH-010.e2e.md:5: TC-AUTH-010: Bug: needs a Result: line",
            "qa/cases/auth/TC-AUTH-011.e2e.md:1: heading is not a test case '# TC-<CAP>-<NNN>: <title>': "
            "'### TC-AUTH-011: Case'",
            "qa/cases/auth/TC-BILL-001.e2e.md:1: TC-BILL-001 belongs in qa/cases/bill/, not auth/",
            "qa/cases/auth/sign-in.e2e.md: case file name is not '<TC-ID>[-<slug>].<type>.md'",
            "qa/cases/auth.md: capability also has folder qa/cases/auth/; run gin-qa cases split auth",
        ], self.findings())

    def test_next_id_counts_file_names_and_their_history(self):
        self.put("auth/TC-AUTH-004-2024-old.e2e.md", case_file("TC-AUTH-004", self.ref("REQ-AUTH-001")))
        self.assertEqual("TC-AUTH-005\n", qa(self.root, self.bin, "next-id", "auth").stdout)
        commit_all(self.root)
        (self.root / "qa/cases/auth/TC-AUTH-004-2024-old.e2e.md").unlink()
        self.assertEqual("TC-AUTH-005\n", qa(self.root, self.bin, "next-id", "auth").stdout)
        self.assertEqual("TC-USER-AUTH-001\n", qa(self.root, self.bin, "next-id", "user-auth").stdout)

    def test_test_globs_probe_covers_case_files(self):
        config = self.root / ".agent-workflow/config.yaml"
        config.write_text(config.read_text().replace("  layout: sdd\n", "  layout: sdd\n  test_globs:\n"
                                                      "    - qa/cases/*/*.e2e.md\n"))
        self.put("auth/TC-AUTH-001.e2e.md", case_file("TC-AUTH-001", self.ref("REQ-AUTH-001", "REQ-AUTH-002")))
        self.assertEqual(["qa/cases/auth/TC-AUTH-001.e2e.md: matches artifacts.test_globs pattern "
                          "'qa/cases/*/*.e2e.md'; test cases would count as executed tests in specs trace"],
                         self.findings())


class TestResult(QaCase):
    def setUp(self):
        super().setUp()
        self.path = write(self.root, "qa/cases/auth/TC-AUTH-001.e2e.md",
                          case_file("TC-AUTH-001", self.ref("REQ-AUTH-001", "REQ-AUTH-002")))

    def result(self, *args: str):
        return qa(self.root, self.bin, "result", "TC-AUTH-001", *args)

    def test_add_replace_and_remove_lines_in_the_case_form(self):
        self.assertEqual(0, self.result("failed", "--run", "qa/evidence/r1", "--bug", "gw-7").returncode)
        text = self.path.read_text()
        self.assertIn("- **Priority:** high\n- **Result:** failed\n- **Run:** qa/evidence/r1\n- **Bug:** gw-7\n\n"
                      "**Preconditions:**", text)
        out = qa(self.root, self.bin, "result", "TC-AUTH-001", "passed", "--format", "json")
        self.assertEqual({"tc": "TC-AUTH-001", "result": "passed", "run": "", "bug": "gw-7",
                          "file": "qa/cases/auth/TC-AUTH-001.e2e.md"}, json.loads(out.stdout))
        self.assertIn("- **Priority:** high\n- **Result:** passed\n- **Bug:** gw-7\n\n", self.path.read_text())
        self.assertEqual(0, self.result("not run", "--bug", "none").returncode)
        self.assertIn("- **Priority:** high\n- **Result:** not run\n\n", self.path.read_text())
        self.assertEqual([], self.findings())

    def test_plain_flat_case_gets_plain_lines(self):
        self.path.unlink()
        self.path.parent.rmdir()
        flat = self.write_cases(case("TC-AUTH-001", self.ref("REQ-AUTH-001", "REQ-AUTH-002")))
        self.assertEqual(0, self.result("blocked", "--run", "manual 2026-11-04").returncode)
        self.assertIn("Priority: high\nResult: blocked\nRun: manual 2026-11-04\n", flat.read_text())

    def test_bad_input_exits_2_and_writes_nothing(self):
        before = self.path.read_text()
        for args, message in ((("done",), "status is one of passed, failed, blocked, not run"),
                              (("passed", "--run", "a\nb"), "values are one non-empty line"),
                              (("passed", "--run", "a\u2028b"), "values are one non-empty line"),
                              (("passed", "--bug", "gw\x7f"), "values are one non-empty line"),
                              (("passed", "--bug", ""), "values are one non-empty line")):
            with self.subTest(args=args):
                result = self.result(*args)
                self.assertEqual(2, result.returncode)
                self.assertIn(message, result.stderr)
        unknown = qa(self.root, self.bin, "result", "TC-AUTH-404", "passed")
        self.assertEqual((2, True), (unknown.returncode, "TC-AUTH-404: no such test case" in unknown.stderr))
        self.path.write_text(before.replace("1. Open /login", "- Open /login"))
        broken = self.path.read_text()
        self.assertEqual(2, self.result("passed").returncode)
        self.assertEqual(broken, self.path.read_text())

    def test_odd_line_breaks_keep_writes_on_their_lines(self):
        self.path.write_text(self.path.read_text().replace("\n\n- **REQ", "\n\x0c\n- **REQ", 1))
        for status in ("failed", "passed"):
            self.assertEqual(0, self.result(status, "--run", "r").returncode)
        self.assertIn("- **Priority:** high\n- **Result:** passed\n- **Run:** r\n\n", self.path.read_text())
        self.assertEqual([], self.findings())

    def test_a_duplicate_id_exits_2_and_writes_nothing(self):
        flat = self.write_cases(case("TC-AUTH-001", self.ref("REQ-AUTH-001", "REQ-AUTH-002")))
        before = (flat.read_text(), self.path.read_text())
        result = self.result("passed")
        self.assertEqual((2, True), (result.returncode, "duplicate TC-AUTH-001" in result.stderr))
        self.assertEqual(before, (flat.read_text(), self.path.read_text()))


class TestSplit(QaCase):
    def flat(self, *blocks: str) -> Path:
        return self.write_cases(*blocks)

    def test_split_writes_one_file_per_case_with_the_same_hash(self):
        good = self.ref("REQ-AUTH-001", "REQ-AUTH-002")
        manual = case("TC-AUTH-002", good, title="Reset: the password!").replace("Type: e2e", "Type: manual")
        path = self.flat(case("TC-AUTH-001", good, title="Sign in"), manual)
        before = {row["id"]: row["hash8"] for row in self.run_json("export")["cases"]}
        result = qa(self.root, self.bin, "split", "auth")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertFalse(path.exists())
        self.assertEqual(["TC-AUTH-001-sign-in.e2e.md", "TC-AUTH-002-reset-the-password.manual.md"],
                         sorted(item.name for item in (self.root / "qa/cases/auth").iterdir()))
        text = (self.root / "qa/cases/auth/TC-AUTH-001-sign-in.e2e.md").read_text()
        self.assertTrue(text.startswith("# TC-AUTH-001: Sign in\n"))
        self.assertNotIn("Type:", text)
        self.assertEqual([], self.findings())
        after = {row["id"]: (row["hash8"], row["type"]) for row in self.run_json("export")["cases"]}
        self.assertEqual({key: (value, kind) for (key, value), kind in zip(before.items(), ("e2e", "manual"))}, after)
        self.assertIn("TC-AUTH-003", qa(self.root, self.bin, "next-id", "auth").stdout)

    def test_refusals_write_nothing(self):
        good = self.ref("REQ-AUTH-001", "REQ-AUTH-002")
        cases = (
            (case("TC-AUTH-001", good).replace("Type: e2e\n", ""), "TC-AUTH-001: needs a Type: matching"),
            (case("TC-AUTH-001", good).replace("Type: e2e", "Type: Web UI"), "TC-AUTH-001: needs a Type: matching"),
            ("Intro prose.\n\n" + case("TC-AUTH-001", good), "holds text outside its title and case blocks"),
            (case("TC-AUTH-001", good) + "\n## Notes\n- later\n", "holds text outside its title and case blocks"),
            ("", "holds no test cases"),
        )
        for block, message in cases:
            with self.subTest(message=message):
                path = self.flat(block)
                before = path.read_text()
                result = qa(self.root, self.bin, "split", "auth")
                self.assertEqual(1, result.returncode)
                self.assertIn(message, result.stdout)
                self.assertEqual(before, path.read_text())
                self.assertFalse((self.root / "qa/cases/auth").exists())
        path = self.flat(case("TC-AUTH-001", good))
        write(self.root, "qa/cases/auth/TC-AUTH-001-case.e2e.md", "x\n")
        result = qa(self.root, self.bin, "split", "auth")
        self.assertEqual(1, result.returncode)
        self.assertIn("qa/cases/auth/TC-AUTH-001-case.e2e.md: already exists", result.stdout)
        self.assertTrue(path.exists())
        self.assertEqual(2, qa(self.root, self.bin, "split", "billing").returncode)
        write(self.root, "notes.md", "# Notes\n")
        self.assertEqual(2, qa(self.root, self.bin, "split", "../../notes").returncode)
        self.assertTrue((self.root / "notes.md").exists())


class TestReadableFormat(unittest.TestCase):
    def parse(self, body: str, name: str = "TC-AUTH-001.e2e.md"):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "auth" / name
            path.parent.mkdir()
            path.write_text(body, encoding="utf-8")
            found, errors = parse_case_file(path, f"qa/cases/auth/{name}")
        self.assertEqual([], errors)
        return found[0]

    def errors(self, body: str) -> list[str]:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "TC-AUTH-001.e2e.md"
            path.write_text(body, encoding="utf-8")
            return parse_case_file(path, "TC-AUTH-001.e2e.md")[1]

    def test_text_before_the_heading_and_unbalanced_bold_are_findings(self):
        body = case_file("TC-AUTH-001", "REQ: REQ-AUTH-001@00000000")
        self.assertEqual(["TC-AUTH-001.e2e.md:1: text before the case heading"], self.errors("Type: manual\n" + body))
        self.assertEqual(["TC-AUTH-001.e2e.md:4: TC-AUTH-001: expected 'Key: value' before Preconditions/Steps"],
                         self.errors(body.replace("- **Priority:** high", "Priority:** high")))
        for label in ("**Steps:", "Steps:**"):
            self.assertIn("TC-AUTH-001.e2e.md:1: TC-AUTH-001: needs at least one Steps item",
                          self.errors(body.replace("**Steps:**", label)))

    def test_bold_and_plain_forms_parse_alike_and_hash_alike(self):
        bold = self.parse(case_file("TC-AUTH-001", "REQ: REQ-AUTH-001@00000000", extra="Owner: qa\n"))
        plain = self.parse(case_file("TC-AUTH-001", "REQ: REQ-AUTH-001@00000000", extra="Owner: qa\n", bold=False))
        flat = parse_file_text(case("TC-AUTH-001", "REQ: REQ-AUTH-001@00000000", extra="Owner: qa\n"))
        self.assertEqual(({"Owner": "qa"}, [("REQ-AUTH-001", "00000000")]), (
            {k: v for k, v in bold.fields.items() if k == "Owner"}, bold.reqs))
        self.assertEqual(case_hash8(bold), case_hash8(plain))
        self.assertEqual(case_hash8(flat), case_hash8(bold))

    def test_test_data_is_parsed_exported_and_hashed_only_when_present(self):
        body = case_file("TC-AUTH-001", "REQ: REQ-AUTH-001@00000000")
        without = self.parse(body)
        with_data = self.parse(body.replace("**Steps:**", "**Test data:**\n- Email: alice@example.com\n\n**Steps:**"))
        self.assertEqual(["Email: alice@example.com"], with_data.test_data)
        self.assertNotEqual(case_hash8(without), case_hash8(with_data))
        self.assertEqual(case_hash8(without), case_hash8(self.parse(body.replace(
            "**Steps:**", "**Test data:**\n\n**Steps:**"))))

    def test_result_fields_change_neither_hash_nor_free_fields(self):
        body = case_file("TC-AUTH-001", "REQ: REQ-AUTH-001@00000000")
        recorded = self.parse(body.replace("- **Priority:** high", "- **Priority:** high\n- **Result:** failed\n"
                                                                   "- **Run:** qa/evidence/x\n- **Bug:** gw-9"))
        self.assertEqual(case_hash8(self.parse(body)), case_hash8(recorded))
        row = as_dict(recorded)
        self.assertEqual(({}, "failed", "qa/evidence/x", "gw-9"), (row["fields"], row["result"], row["run"], row["bug"]))


class TestCaseHash(unittest.TestCase):
    def hashes(self, *blocks: str) -> list[str]:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "auth.md"
            path.write_text(cases_file("auth", *blocks), encoding="utf-8")
            found, errors = parse_file(path, "qa/cases/auth.md")
        self.assertEqual([], errors)
        return [case_hash8(item) for item in found]

    def test_hash_ignores_pins_type_and_priority_but_not_content(self):
        base = case("TC-AUTH-001", "REQ: REQ-AUTH-001@00000000")
        repinned = base.replace("@00000000", "@11111111").replace("Type: e2e", "Type: manual")
        renamed = base.replace("Priority: high", "Priority: low")
        changed = base.replace("1. Open /login", "1. Open /signin")
        extra = case("TC-AUTH-001", "REQ: REQ-AUTH-001@00000000", extra="Owner: qa-team\n")
        first, *others = self.hashes(base, repinned, renamed, changed, extra)
        self.assertEqual([first, first, first], [first, *others[:2]])
        self.assertNotIn(first, others[2:])


TYPES_GUIDE = ("# Test case guidelines\n\n## Types\n\nThe types in use.\n\n- `e2e`: browser flows.\n"
               "- `manual`: walked by a tester.\n\n## Automated types\n\nNone yet.\n")
NOT_LISTED = "type '{}' is not listed under '## Types' in qa/guidelines.md"


class TestTypes(QaCase):
    def write_case(self, name: str, tc_id: str) -> None:
        write(self.root, f"qa/cases/auth/{name}", case_file(tc_id, self.ref("REQ-AUTH-001")))

    def test_listed_type_passes_and_unlisted_type_is_a_finding(self):
        write(self.root, "qa/guidelines.md", TYPES_GUIDE)
        self.write_case("TC-AUTH-001-login.manual.md", "TC-AUTH-001")
        self.write_case("TC-AUTH-002-login.ap.md", "TC-AUTH-002")
        result = qa(self.root, self.bin, "check")
        self.assertEqual(1, result.returncode, result.stderr)
        findings = self.findings()
        self.assertIn("qa/cases/auth/TC-AUTH-002-login.ap.md:1: TC-AUTH-002: " + NOT_LISTED.format("ap"), findings)
        self.assertFalse([f for f in findings if "TC-AUTH-001" in f and "## Types" in f], findings)
        # the sdd rules still run next to the type rule
        self.assertTrue([f for f in findings if "REQ-AUTH-002 has no test case" in f], findings)

    def test_malformed_entry_and_empty_section_are_findings(self):
        write(self.root, "qa/guidelines.md", "# G\n\n## Types\n\n- e2e: no backticks\n- `manual`: ok\n")
        self.assertIn("qa/guidelines.md:5: '## Types' entry is not \"- `<type>`: <description>\"", self.findings())
        write(self.root, "qa/guidelines.md", "## Types\n\nProse only.\n\n## Other\n\n- `e2e`: outside the section\n")
        self.assertIn("qa/guidelines.md:1: '## Types' lists no types", self.findings())

    def test_crlf_guidelines_parse(self):
        write(self.root, "qa/guidelines.md", TYPES_GUIDE.replace("\n", "\r\n"))
        self.write_case("TC-AUTH-001-login.e2e.md", "TC-AUTH-001")
        self.assertFalse([f for f in self.findings() if "## Types" in f])

    def test_no_section_or_no_guidelines_skips_the_rule(self):
        self.write_case("TC-AUTH-001-login.ap.md", "TC-AUTH-001")
        self.assertFalse([f for f in self.findings() if "## Types" in f])
        write(self.root, "qa/guidelines.md", "# Test case guidelines\n\n- One user action per step.\n")
        self.assertFalse([f for f in self.findings() if "## Types" in f])

    def test_flat_case_without_type_is_not_checked(self):
        write(self.root, "qa/guidelines.md", TYPES_GUIDE)
        self.write_cases(case("TC-AUTH-001", self.ref("REQ-AUTH-001")).replace("Type: e2e\n", ""))
        self.assertFalse([f for f in self.findings() if "## Types" in f])


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
        self.assertIn("gin is not on PATH", result.stderr)
        old = gin_workflow_bin(self.base / "old", failing_stub("error: argument command: invalid choice: 'reqs'", 2))
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
