"""`gin-qa tests`: automated types declared in the guidelines; plan, pin, check, and run (with a fake runner)."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import textwrap
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "plugins/gin-qa/src/scripts"))

from qa_fixtures import AUTH_SPEC, case_file, gin_workflow_bin, make_repo, python_stub, qa, write  # noqa: E402
from gin_qa.cases import hash8 as case_hash8, parse_case_file  # noqa: E402

GUIDELINES = textwrap.dedent("""\
    # Test case guidelines

    - Language: English.

    ## Automated types

    ### api
    - Tests: `backend/tests/**/test_*.py`
    - Run: `fake-runner {files} --junitxml={junit}`
    """)

FAKE_RUNNER = textwrap.dedent('''\
    #!{python}
    """Stands in for a test runner: records its arguments and copies .fake-junit to the --junitxml path."""
    import json, pathlib, sys
    root = pathlib.Path.cwd()
    (root / ".runner-args").write_text(json.dumps(sys.argv[1:]))
    target = next(arg.split("=", 1)[1] for arg in sys.argv[1:] if arg.startswith("--junitxml="))
    if (root / ".fake-junit").exists():
        pathlib.Path(target).write_text((root / ".fake-junit").read_text())
    exit_file = root / ".fake-exit"
    sys.exit(int(exit_file.read_text()) if exit_file.exists() else 0)
''').format(python=sys.executable)


def junit(*tests: tuple[str, str]) -> str:
    """A JUnit file with one testcase per (name, outcome); outcome is passed, failure, error, or skipped."""
    body = "".join(f'<testcase classname="tests.test_auth" name="{name}">'
                   + ("" if outcome == "passed" else f"<{outcome}/>") + "</testcase>" for name, outcome in tests)
    return f'<?xml version="1.0"?><testsuites><testsuite name="pytest">{body}</testsuite></testsuites>'


class TestsCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.bin = gin_workflow_bin(self.base)
        python_stub(self.bin, "fake-runner", FAKE_RUNNER)
        self.root = make_repo(self.base / "repo")
        write(self.root, "docs/specs/auth/spec.md", AUTH_SPEC)
        self.guidelines = write(self.root, "qa/guidelines.md", GUIDELINES)
        for tc_id, kind in (("TC-AUTH-001", "api"), ("TC-AUTH-002", "api"), ("TC-AUTH-003", "manual")):
            self.add_case(tc_id, kind)

    def tearDown(self):
        self.tmp.cleanup()

    def add_case(self, tc_id: str, kind: str) -> None:
        write(self.root, f"qa/cases/auth/{tc_id}-x.{kind}.md",
              case_file(tc_id, "REQ: REQ-AUTH-001@00000000", title=tc_id))

    def tests(self, *args: str):
        return qa(self.root, self.bin, *args, group="tests")

    def run_json(self, *args: str) -> dict:
        result = self.tests(*args, "--format", "json")
        self.assertIn(result.returncode, (0, 1), result.stderr)
        return json.loads(result.stdout)

    def tc_hash(self, tc_id: str) -> str:
        path = next((self.root / "qa/cases/auth").glob(f"{tc_id}-*.md"), None)
        if path is None:
            return "00000000"  # a marker for a case that does not exist
        found, _ = parse_case_file(path, path.relative_to(self.root).as_posix())
        return case_hash8(found[0])

    def write_test(self, *tc_ids: str, name: str = "test_auth.py", pinned: str | None = None) -> Path:
        lines: list[str] = []
        for tc_id in tc_ids:
            lines += [f"# TC: {tc_id}@{pinned or self.tc_hash(tc_id)}",
                      f"def test_{tc_id.lower().replace('-', '_')}():", "    pass", ""]
        return write(self.root, f"backend/tests/{name}", "\n".join(lines))

    def case_fields(self, tc_id: str) -> dict:
        payload = json.loads(qa(self.root, self.bin, "export", "--format", "json").stdout)
        return next(row for row in payload["cases"] if row["id"] == tc_id)


class TestDeclaration(TestsCase):
    def test_check_reports_each_declaration_error_and_other_commands_exit_2(self):
        self.guidelines.write_text(textwrap.dedent("""\
            ## Automated types

            ### api
            - Tests: `backend/tests/**/test_*.py`
            - Run: `pytest --junitxml=out.xml`

            ### e2e
            - Tests: `qa/e2e/**/*.spec.ts`
            - Run: `npx playwright test --reporter=junit {junit}`

            ### unit
            - Run: `pytest {files}x --junitxml={junit}`

            ### api
            - Tests: `a/*.py`
            - Run: `pytest --junitxml={junit}`
            """))
        result = self.tests("check")
        self.assertEqual(1, result.returncode, result.stderr)
        self.assertEqual([
            "qa/guidelines.md:3: api: Run needs {junit}",
            "qa/guidelines.md:7: e2e: cannot be declared here; e2e and manual have their own commands",
            "qa/guidelines.md:11: unit: needs a '- Tests:' line with one or more backticked globs",
            "qa/guidelines.md:11: unit: {files} must be a whole argument",
            "qa/guidelines.md:14: api: declared twice (first at line 3)",
        ], result.stdout.splitlines())
        for args in (("plan",), ("pin", "TC-AUTH-001"), ("run", "--type", "api")):
            with self.subTest(args=args):
                result = self.tests(*args)
                self.assertEqual(2, result.returncode, result.stdout)
                self.assertIn("gin-qa tests check", result.stderr)

    def test_no_declared_type_means_nothing_to_do(self):
        self.guidelines.write_text("# Test case guidelines\n\n## Automated types\n\nNone yet.\n")
        result = self.tests("check")
        self.assertEqual((0, "ok\n"), (result.returncode, result.stdout))
        payload = self.run_json("plan")
        self.assertEqual(({}, [], [], []), (payload["types"], payload["missing"], payload["stale"], payload["orphan"]))
        self.guidelines.unlink()
        self.assertEqual("ok\n", self.tests("check").stdout)
        for args in (("run", "--type", "api"), ("plan", "--type", "api")):
            with self.subTest(args=args):
                result = self.tests(*args)
                self.assertEqual(2, result.returncode)
                self.assertIn("--type api: not declared", result.stderr)


class TestPlanPinCheck(TestsCase):
    def test_plan_lists_missing_stale_and_orphan(self):
        payload = self.run_json("plan")
        self.assertEqual(["TC-AUTH-001", "TC-AUTH-002"], [row["tc"] for row in payload["missing"]])
        self.assertEqual({"api": {"tests": ["backend/tests/**/test_*.py"],
                                  "run": "fake-runner {files} --junitxml={junit}"}}, payload["types"])
        self.assertEqual(("qa/guidelines.md", "api", self.tc_hash("TC-AUTH-001")),
                         (payload["guidelines"], payload["missing"][0]["type"], payload["missing"][0]["hash8"]))
        self.write_test("TC-AUTH-001", pinned="00000000")
        self.write_test("TC-AUTH-002", "TC-AUTH-003", "TC-AUTH-009", name="sub/test_more.py")
        write(self.root, "backend/other/test_x.py", "# TC: TC-AUTH-009@00000000\n")
        payload = self.run_json("plan", "auth", "--type", "api")
        self.assertEqual([], payload["missing"])
        self.assertEqual([("TC-AUTH-001", "backend/tests/test_auth.py", 1, "00000000")],
                         [(row["tc"], row["file"], row["line"], row["pinned"]) for row in payload["stale"]])
        self.assertEqual([("TC-AUTH-003", "backend/tests/sub/test_more.py", 5),
                          ("TC-AUTH-009", "backend/tests/sub/test_more.py", 9)],
                         [(row["tc"], row["file"], row["line"]) for row in payload["orphan"]])
        self.assertEqual(([], [], []), tuple(self.run_json("plan", "billing")[key]
                                             for key in ("missing", "stale", "orphan")))

    def test_a_marker_of_another_declared_type_is_not_an_orphan(self):
        self.guidelines.write_text(GUIDELINES + "\n### unit\n- Tests: `backend/tests/unit/*.py`\n"
                                                "- Run: `fake-runner --junitxml={junit}`\n")
        self.add_case("TC-AUTH-004", "unit")
        self.write_test("TC-AUTH-004", name="unit/test_unit.py")
        payload = self.run_json("plan")
        self.assertEqual(([], ["TC-AUTH-001", "TC-AUTH-002"]),
                         (payload["orphan"], [row["tc"] for row in payload["missing"]]))
        self.assertEqual([], self.run_json("plan", "--type", "unit")["missing"])

    def test_pin_rewrites_every_marker_of_the_case(self):
        first = self.write_test("TC-AUTH-001", pinned="00000000")
        second = write(self.root, "backend/tests/test_other.py", "x = 1  -- TC: TC-AUTH-001@11111111\n")
        result = self.tests("pin", "TC-AUTH-001", "TC-AUTH-009")
        self.assertEqual((1, "TC-AUTH-009: not a test case of a declared automated type\n"),
                         (result.returncode, result.stdout))
        self.assertIn("TC-AUTH-001@00000000", first.read_text())
        self.assertEqual(0, self.tests("pin", "TC-AUTH-001").returncode)
        now = self.tc_hash("TC-AUTH-001")
        self.assertTrue(first.read_text().startswith(f"# TC: TC-AUTH-001@{now}\ndef test_tc_auth_001():"))
        self.assertEqual(f"x = 1  -- TC: TC-AUTH-001@{now}\n", second.read_text())
        self.assertEqual([], self.run_json("plan")["stale"])
        result = self.tests("pin", "TC-AUTH-002", "TC-AUTH-003")
        self.assertEqual([
            "TC-AUTH-002: no 'TC: TC-AUTH-002@<hash8>' marker in the api tests",
            "TC-AUTH-003: not a test case of a declared automated type",
        ], result.stdout.splitlines())

    def test_check_reports_missing_stale_and_orphan(self):
        self.write_test("TC-AUTH-001", pinned="00000000")
        gone = self.write_test("TC-AUTH-009", name="test_gone.py", pinned="00000000")
        result = self.tests("check")
        self.assertEqual(1, result.returncode, result.stderr)
        self.assertEqual([
            "qa/cases/auth/TC-AUTH-002-x.api.md:1: TC-AUTH-002 has no test of type api; "
            "write it with `/gin-qa:tests auth --type api`",
            f"backend/tests/test_auth.py:1: TC-AUTH-001 changed (pinned 00000000, now {self.tc_hash('TC-AUTH-001')}); "
            "update the test, then `gin-qa tests pin TC-AUTH-001`",
            "backend/tests/test_gone.py:1: TC-AUTH-009 is not a test case of type api",
        ], result.stdout.splitlines())
        self.write_test("TC-AUTH-001", "TC-AUTH-002")
        gone.unlink()
        result = self.tests("check", "--type", "api")
        self.assertEqual((0, "ok\n"), (result.returncode, result.stdout))


if __name__ == "__main__":
    unittest.main()
