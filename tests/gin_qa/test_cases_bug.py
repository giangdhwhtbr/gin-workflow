"""`gin-qa cases bug`: the epic of a manual case, the bug bead filed through `gin-workflow task`, and the result."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from qa_fixtures import (ADDED_BLOCK, AUTH_SPEC, LAUNCHER, case_file, delta, hash8, make_change,  # noqa: E402
                         make_repo, python_stub, qa, write)

# `specs` runs this checkout's gin-workflow. Any other call is logged to calls.jsonl with its stdin and answered
# from answers.json, keyed by its first three words, then its first two. No answer: bd's unknown-id failure.
STUB = r'''#!@PYTHON@
import json, pathlib, subprocess, sys
here = pathlib.Path(__file__).resolve().parent
args = sys.argv[1:]
if args[:1] == ["specs"]:
    sys.exit(subprocess.run([sys.executable, @LAUNCHER@, *args]).returncode)
with open(here / "calls.jsonl", "a", encoding="utf-8") as log:
    log.write(json.dumps({"argv": args, "cwd": str(pathlib.Path.cwd()), "stdin": sys.stdin.read()}) + "\n")
answers = json.loads((here / "answers.json").read_text(encoding="utf-8"))
answer = answers.get(" ".join(args[:3]), answers.get(" ".join(args[:2])))
if answer is None:
    sys.stderr.write("Error fetching: no issue found\n")
    sys.exit(1)
if "write" in answer:
    pathlib.Path(answer["write"][0]).write_text(answer["write"][1], encoding="utf-8")
sys.stderr.write(answer.get("stderr", ""))
sys.stdout.write(answer.get("stdout", ""))
sys.exit(answer.get("code", 0))
'''

SPEC = ".planning/specs/2026-01-01-login-design.md"
FILE = "qa/cases/auth/TC-AUTH-001-sign-in.manual.md"
CASE = f"""# TC-AUTH-001: Sign in

- **Source:** {SPEC}#US-1
- **Priority:** low

**Preconditions:**
- a user exists

**Test data:**
- user: alice

**Steps:**
1. Open /login
2. Click "Sign in"

**Expected:**
- The dashboard is shown
"""


def shown(bead: str, status: str) -> dict:
    return {"stdout": json.dumps([{"id": bead, "status": status}])}


CREATED = {"stdout": json.dumps({"id": "gw-bug1", "status": "open"})}


class BugCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.bin = self.base / "bin"
        python_stub(self.bin, "gin-workflow",
                    STUB.replace("@PYTHON@", sys.executable).replace("@LAUNCHER@", repr(str(LAUNCHER))))
        self.answer({})

    def tearDown(self):
        self.tmp.cleanup()

    def answer(self, answers: dict) -> None:
        (self.bin / "answers.json").write_text(json.dumps(answers), encoding="utf-8")

    def calls(self) -> list[dict]:
        log = self.bin / "calls.jsonl"
        return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()] if log.is_file() else []

    def creates(self) -> list[dict]:
        return [call for call in self.calls() if call["argv"][:2] == ["task", "create"]]

    @staticmethod
    def option(argv: list[str], name: str) -> str:
        return argv[argv.index(name) + 1]

    def bug(self, *args: str):
        return qa(self.root, self.bin, "bug", *args)


class TestLegacy(BugCase):
    def setUp(self):
        super().setUp()
        self.root = make_repo(self.base / "repo", layout="legacy")
        write(self.root, SPEC, "# Login\n\nEpic: gw-epic\nStatus: confirmed\n")
        self.path = write(self.root, FILE, CASE)

    def test_files_a_bug_linked_to_the_spec_epic_and_records_it(self):
        self.answer({"task show gw-epic": shown("gw-epic", "in_progress"), "task create": CREATED})
        result = self.bug("TC-AUTH-001", "--actual", "An error page is shown", "--evidence", "shots/1.png",
                          "--evidence", "https://logs.example/42", "--run", "manual 2026-11-04", "--format", "json")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual({"tc": "TC-AUTH-001", "bug": "gw-bug1", "epic": "gw-epic", "created": True, "file": FILE},
                         json.loads(result.stdout))
        [call] = self.creates()
        argv = call["argv"]
        self.assertEqual(["task", "create", "-t", "bug"], argv[:4])
        self.assertEqual("TC-AUTH-001: Sign in", self.option(argv, "--title"))
        self.assertEqual("-", self.option(argv, "--body-file"))
        self.assertEqual("discovered-from:gw-epic", self.option(argv, "--deps"))
        self.assertEqual("3", self.option(argv, "-p"))
        self.assertEqual("--json", argv[-1])
        self.assertNotIn("--external-ref", argv)
        self.assertFalse(any("\n" in arg for arg in argv))
        self.assertEqual(
            f"- Case: {FILE}:1\n- Run: manual 2026-11-04\n\n"
            "## Preconditions\n\n- a user exists\n\n## Test data\n\n- user: alice\n\n"
            "## Steps\n\n1. Open /login\n2. Click \"Sign in\"\n\n## Expected\n\n- The dashboard is shown\n\n"
            "## Actual\n\nAn error page is shown\n\n## Evidence\n\n- shots/1.png\n- https://logs.example/42",
            call["stdin"])
        text = self.path.read_text(encoding="utf-8")
        for line in ("- **Result:** failed\n", "- **Run:** manual 2026-11-04\n", "- **Bug:** gw-bug1\n"):
            self.assertIn(line, text)
        self.assertTrue(all(Path(call["cwd"]).resolve() == self.root.resolve() for call in self.calls()))

    def test_keeps_the_current_run_and_names_a_bug_value_that_is_not_a_bead(self):
        write(self.root, FILE, CASE.replace("- **Priority:** low\n",
                                            "- **Result:** failed\n- **Run:** manual 2026-01-01\n- **Bug:** JIRA-12\n"))
        self.answer({"task show gw-epic": shown("gw-epic", "open"), "task create": CREATED})
        result = self.bug("TC-AUTH-001", "--actual", "Nothing happens")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("TC-AUTH-001 failed gw-bug1", result.stdout.strip())
        [call] = self.creates()
        self.assertEqual("2", self.option(call["argv"], "-p"))
        self.assertIn("- Run: manual 2026-01-01\n- Previous bug: JIRA-12\n\n", call["stdin"])
        self.assertNotIn("## Evidence", call["stdin"])
        text = self.path.read_text(encoding="utf-8")
        self.assertIn("- **Run:** manual 2026-01-01\n", text)
        self.assertIn("- **Bug:** gw-bug1\n", text)

    def test_an_open_bug_is_kept_without_an_epic_and_a_closed_bug_is_replaced(self):
        write(self.root, SPEC, "# Login\n")
        write(self.root, FILE, CASE.replace("- **Priority:** low\n",
                                            "- **Priority:** low\n- **Result:** failed\n- **Bug:** gw-7\n"))
        self.answer({"task show gw-7": shown("gw-7", "in_progress")})
        result = self.bug("TC-AUTH-001", "--actual", "Still broken", "--format", "json")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual({"tc": "TC-AUTH-001", "bug": "gw-7", "epic": None, "created": False, "file": FILE},
                         json.loads(result.stdout))
        self.assertEqual([], self.creates())
        self.assertIn("- **Bug:** gw-7\n", self.path.read_text(encoding="utf-8"))
        write(self.root, SPEC, "# Login\n\nEpic: gw-epic\n")
        self.answer({"task show gw-epic": shown("gw-epic", "open"), "task show gw-7": shown("gw-7", "closed"),
                     "task create": CREATED})
        result = self.bug("TC-AUTH-001", "--actual", "Broken again", "--format", "json")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(("gw-bug1", True), (json.loads(result.stdout)["bug"], json.loads(result.stdout)["created"]))
        [call] = self.creates()
        self.assertIn("- Previous bug: gw-7\n", call["stdin"])

    def test_a_workflow_spec_uses_the_epic_recorded_for_its_workflow(self):
        write(self.root, SPEC, "# Login\n\nWorkflow: login\n")
        self.answer({"state --workflow-id login": {"stdout": json.dumps({"epic": "gw-login"}), "code": 1},
                     "task show gw-login": shown("gw-login", "closed"), "task create": CREATED})
        result = self.bug("TC-AUTH-001", "--actual", "Error", "--format", "json")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("gw-login", json.loads(result.stdout)["epic"])
        [call] = self.creates()
        self.assertEqual("discovered-from:gw-login", self.option(call["argv"], "--deps"))

    def test_no_epic_exits_2_until_a_bead_is_given(self):
        write(self.root, SPEC, "# Login\n\nWorkflow: login\n")
        before = self.path.read_text(encoding="utf-8")
        result = self.bug("TC-AUTH-001", "--actual", "Error")
        self.assertEqual(2, result.returncode)
        self.assertIn("no epic for TC-AUTH-001; pass --discovered-from <bead>", result.stderr)
        self.assertEqual([], [call for call in self.calls() if call["argv"][0] == "task"])
        self.assertEqual(before, self.path.read_text(encoding="utf-8"))
        self.answer({"task show gw-other": shown("gw-other", "open"), "task create": CREATED})
        result = self.bug("TC-AUTH-001", "--actual", "Error", "--discovered-from", "gw-other",
                          "--external-ref", "JIRA-9")
        self.assertEqual(0, result.returncode, result.stderr)
        [call] = self.creates()
        self.assertEqual("discovered-from:gw-other", self.option(call["argv"], "--deps"))
        self.assertEqual("JIRA-9", self.option(call["argv"], "--external-ref"))

    def test_an_unknown_epic_a_tracker_failure_or_a_failing_create_writes_nothing(self):
        before = self.path.read_text(encoding="utf-8")
        result = self.bug("TC-AUTH-001", "--actual", "Error")
        self.assertEqual(2, result.returncode)
        self.assertIn("gw-epic: no such bead", result.stderr)
        self.answer({"task show gw-epic": {"stderr": "Error: no beads database found\n", "code": 1}})
        result = self.bug("TC-AUTH-001", "--actual", "Error")
        self.assertEqual(2, result.returncode)
        self.assertIn("no beads database found", result.stderr)
        self.assertNotIn("no such bead", result.stderr)
        self.assertEqual([], self.creates())
        self.answer({"task show gw-epic": shown("gw-epic", "open"),
                     "task create": {"stderr": "bd: database is locked\n", "code": 1}})
        result = self.bug("TC-AUTH-001", "--actual", "Error")
        self.assertEqual(2, result.returncode)
        self.assertIn("bd: database is locked", result.stderr)
        self.assertEqual(before, self.path.read_text(encoding="utf-8"))

    def test_a_bead_created_but_not_recorded_is_named(self):
        broken = {**CREATED, "write": [str(self.path), "# not a test case\n"]}
        self.answer({"task show gw-epic": shown("gw-epic", "open"), "task create": broken})
        result = self.bug("TC-AUTH-001", "--actual", "Error")
        self.assertEqual(2, result.returncode)
        self.assertIn("filed gw-bug1 but could not record it", result.stderr)
        self.assertIn("gin-qa cases result TC-AUTH-001 failed --bug gw-bug1", result.stderr)

    def test_usage_errors_exit_2_and_call_nothing(self):
        write(self.root, "qa/cases/auth/TC-AUTH-002.e2e.md", case_file("TC-AUTH-002", f"Source: {SPEC}#US-1"))
        write(self.root, "qa/cases/auth/TC-AUTH-003.manual.md", case_file("TC-AUTH-003", "Source: missing.md#US-1"))
        write(self.root, "qa/cases/auth/TC-AUTH-004.manual.md", case_file("TC-AUTH-004", "Source: ../outside.md#US-1"))
        before = self.path.read_text(encoding="utf-8")
        for args, error in (
                (("TC-AUTH-002", "--actual", "x"), "TC-AUTH-002: is a e2e case; cases bug files bugs for manual"),
                (("TC-AUTH-003", "--actual", "x"), "TC-AUTH-003: cannot read missing.md"),
                (("TC-AUTH-004", "--actual", "x"), "TC-AUTH-004: ../outside.md is outside the repository"),
                (("TC-AUTH-099", "--actual", "x"), "TC-AUTH-099: no such test case"),
                (("TC-AUTH-001", "--actual", " "), "values are one non-empty line"),
                (("TC-AUTH-001", "--actual", "x", "--evidence", "a\nb"), "values are one non-empty line"),
                (("TC-AUTH-001", "--actual", "x", "--run", ""), "values are one non-empty line")):
            with self.subTest(args=args):
                result = self.bug(*args)
                self.assertEqual(2, result.returncode)
                self.assertIn(error, result.stderr)
        self.assertEqual([], self.calls())
        self.assertEqual(before, self.path.read_text(encoding="utf-8"))


class TestSdd(BugCase):
    def setUp(self):
        super().setUp()
        self.root = make_repo(self.base / "repo")
        write(self.root, "docs/specs/auth/spec.md", AUTH_SPEC)
        make_change(self.root, spec_delta=delta(added=ADDED_BLOCK))

    def ref(self, *reqs: str) -> str:
        return "REQ: " + ", ".join(f"{req}@{hash8(self.root, self.bin, req)}" for req in reqs)

    def test_the_epic_comes_from_the_first_req_in_a_change(self):
        write(self.root, "qa/cases/auth/TC-AUTH-001.manual.md",
              case_file("TC-AUTH-001", self.ref("REQ-AUTH-001", "REQ-AUTH-003")))
        self.answer({"task show ep-1": shown("ep-1", "in_progress"), "task create": CREATED})
        result = self.bug("TC-AUTH-001", "--actual", "Locked out after 3 tries", "--format", "json")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("ep-1", json.loads(result.stdout)["epic"])
        [call] = self.creates()
        self.assertEqual("discovered-from:ep-1", self.option(call["argv"], "--deps"))
        self.assertEqual("1", self.option(call["argv"], "-p"))

    def test_living_reqs_only_have_no_epic(self):
        write(self.root, "qa/cases/auth/TC-AUTH-001.manual.md", case_file("TC-AUTH-001", self.ref("REQ-AUTH-001")))
        result = self.bug("TC-AUTH-001", "--actual", "Error")
        self.assertEqual(2, result.returncode)
        self.assertIn("no epic for TC-AUTH-001", result.stderr)


if __name__ == "__main__":
    unittest.main()
