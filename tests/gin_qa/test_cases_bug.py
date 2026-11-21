"""`gin-qa cases bug`: the epic of a case of any type, the bug bead filed through `gin task`, and the result."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from qa_fixtures import (ADDED_BLOCK, AUTH_SPEC, LAUNCHER, case_file, delta, hash8, make_change,  # noqa: E402
                         commit_all, make_repo, make_workspace_qa, python_stub, qa, write)

# `specs` runs this checkout's gin. Any other call is logged to calls.jsonl with its stdin and answered
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
        python_stub(self.bin, "gin",
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
        self.assertEqual({"tc": "TC-AUTH-001", "bug": "gw-bug1", "epic": "gw-epic", "created": True,
                          "appended": False, "file": FILE, "attachments": [], "warnings": []}, json.loads(result.stdout))
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
        self.assertRegex(text, r"- \*\*Checked:\*\* [0-9a-f]{8}\n")
        self.assertTrue(all(Path(call["cwd"]).resolve() == self.root.resolve() for call in self.calls()))

    def test_an_e2e_case_files_a_bug_and_records_it(self):
        path = write(self.root, "qa/cases/auth/TC-AUTH-002-sign-in.e2e.md", CASE.replace("TC-AUTH-001", "TC-AUTH-002"))
        self.answer({"task show gw-epic": shown("gw-epic", "open"), "task create": CREATED})
        result = self.bug("TC-AUTH-002", "--actual", "Redirect loop", "--run", "e2e 2026-11-12")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue(path.is_file())
        self.assert_filed_and_recorded(path)

    def test_an_api_case_files_a_bug_and_records_it(self):
        path = write(self.root, "qa/cases/auth/TC-AUTH-003-sign-in.api.md", CASE.replace("TC-AUTH-001", "TC-AUTH-003"))
        self.answer({"task show gw-epic": shown("gw-epic", "open"), "task create": CREATED})
        result = self.bug("TC-AUTH-003", "--actual", "401 on valid login", "--run", "api 2026-11-12")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assert_filed_and_recorded(path)

    def assert_filed_and_recorded(self, path: Path) -> None:
        [call] = self.creates()
        self.assertEqual(["task", "create", "-t", "bug"], call["argv"][:4])
        self.assertEqual("discovered-from:gw-epic", self.option(call["argv"], "--deps"))
        text = path.read_text(encoding="utf-8")
        for line in ("- **Result:** failed\n", "- **Bug:** gw-bug1\n"):
            self.assertIn(line, text)
        self.assertRegex(text, r"- \*\*Checked:\*\* [0-9a-f]{8}\n")
        self.assertRegex(text, r"- \*\*Run:\*\* (e2e|api) 2026-11-12\n")

    def test_a_re_run_of_an_e2e_case_appends_to_its_open_bug(self):
        path = write(self.root, "qa/cases/auth/TC-AUTH-002-sign-in.e2e.md",
                     CASE.replace("TC-AUTH-001", "TC-AUTH-002").replace(
                         "- **Priority:** low\n", "- **Priority:** low\n- **Result:** failed\n- **Bug:** gw-7\n"))
        self.answer({"task show gw-7": shown("gw-7", "open"), "task update gw-7": {}})
        result = self.bug("TC-AUTH-002", "--actual", "Still looping", "--format", "json")
        self.assertEqual(0, result.returncode, result.stderr)
        row = json.loads(result.stdout)
        self.assertEqual((False, True, "gw-7"), (row["created"], row["appended"], row["bug"]))
        self.assertEqual([], self.creates())
        self.assertIn("- **Bug:** gw-7\n", path.read_text(encoding="utf-8"))

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
        self.answer({"task show gw-7": shown("gw-7", "in_progress"), "task update gw-7": {}})
        result = self.bug("TC-AUTH-001", "--actual", "Still broken", "--format", "json")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual({"tc": "TC-AUTH-001", "bug": "gw-7", "epic": None, "created": False, "appended": True,
                          "file": FILE, "attachments": [], "warnings": []},
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

    def kept_bug(self) -> None:
        write(self.root, FILE, CASE.replace("- **Priority:** low\n",
                                            "- **Priority:** low\n- **Result:** blocked\n- **Bug:** gw-7\n"))

    def test_a_re_run_appends_one_line_to_the_notes_of_the_open_bug(self):
        self.kept_bug()
        self.answer({"task show gw-7": shown("gw-7", "open"), "task update gw-7": {}})
        result = self.bug("TC-AUTH-001", "--actual", 'Shows "500" again', "--evidence", "a.png", "--evidence", "b.png",
                          "--run", "manual 2026-11-07")
        self.assertEqual(0, result.returncode, result.stderr)
        [update] = [call for call in self.calls() if call["argv"][:2] == ["task", "update"]]
        note = self.option(update["argv"], "--append-notes")
        self.assertRegex(note, r"^Re-run \d{4}-\d{2}-\d{2}; Run: manual 2026-11-07; "
                               r"Actual: Shows '500' again; Evidence: a\.png, b\.png$")
        self.assertIn("- **Result:** failed\n", self.path.read_text(encoding="utf-8"))

    def test_a_failed_notes_update_exits_2_and_leaves_the_case(self):
        self.kept_bug()
        before = self.path.read_text(encoding="utf-8")
        self.answer({"task show gw-7": shown("gw-7", "open"),
                     "task update gw-7": {"stderr": "database locked\n", "code": 1}})
        result = self.bug("TC-AUTH-001", "--actual", "Still broken")
        self.assertEqual(2, result.returncode)
        self.assertIn("database locked", result.stderr)
        self.assertEqual(before, self.path.read_text(encoding="utf-8"))


class TestAttachments(BugCase):
    SHA = "a" * 64
    RUN = "qa/evidence/2026-11-04T08-00-00"

    def setUp(self):
        super().setUp()
        self.root = make_repo(self.base / "repo", layout="legacy")
        write(self.root, SPEC, "# Login\n\nEpic: gw-epic\nStatus: confirmed\n")
        self.path = write(self.root, FILE, CASE)
        write(self.root, "shot.png", "png-bytes")
        write(self.root, f"{self.RUN}/run.json", json.dumps({"specs": ["qa/e2e/auth/tc-auth-001.spec.ts"]}))
        write(self.root, f"{self.RUN}/tc-auth-001/02.png", "png-bytes")
        write(self.root, f"{self.RUN}/tc-auth-001/result.json", json.dumps({
            "tc": "TC-AUTH-001", "status": "failed", "steps": [
                {"n": 1, "title": "1. Open /login", "status": "passed", "screenshot": "01.png"},
                {"n": 2, "title": "2. Click Sign in", "status": "failed", "screenshot": "02.png"},
                {"n": 3, "title": "3. Escape", "status": "failed", "screenshot": "../../../../shot.png"}]}))

    def attached(self, sha: str | None = None) -> dict:
        entry = {"sha256": sha or self.SHA, "path": "aa/x", "name": "x"}
        return {"stdout": json.dumps({"bead": "gw-bug1", "entries": [entry], "refused": [], "warning": None})}

    def of(self, *head: str) -> list[dict]:
        return [call for call in self.calls() if call["argv"][:len(head)] == list(head)]

    def test_a_failed_step_screenshot_is_attached_and_the_description_rewritten(self):
        self.answer({"task show gw-epic": shown("gw-epic", "open"), "task create": CREATED,
                     "attach add": self.attached(), "task update": {}})
        result = self.bug("TC-AUTH-001", "--actual", "Error page", "--run", self.RUN, "--format", "json")
        self.assertEqual(0, result.returncode, result.stderr)
        row = json.loads(result.stdout)
        self.assertEqual(([self.SHA], []), (row["attachments"], row["warnings"]))
        [add] = self.of("attach", "add")  # step 3 points outside its folder; step 1 has no file
        self.assertEqual("gw-bug1", add["argv"][2])
        self.assertEqual(f"{self.RUN}/tc-auth-001/02.png", str(Path(add["argv"][3]).relative_to(self.root.resolve())))
        self.assertEqual("TC-AUTH-001", self.option(add["argv"], "--case"))
        self.assertEqual("2", self.option(add["argv"], "--step"))
        self.assertEqual("json", self.option(add["argv"], "--format"))
        self.assertEqual("TC-AUTH-001 step 2: 2. Click Sign in", self.option(add["argv"], "--caption"))
        [update] = self.of("task", "update")
        self.assertEqual(["task", "update", "gw-bug1", "--body-file", "-"], update["argv"])
        self.assertIn(f"- ![TC-AUTH-001 step 2: 2. Click Sign in](attachment:{self.SHA})\n"
                      f"  local: {self.RUN}/tc-auth-001/02.png", update["stdin"])
        [create] = self.creates()
        self.assertIn(f"- {self.RUN}/tc-auth-001/02.png", create["stdin"])
        self.assertNotIn("attachment:", create["stdin"])
        order = [call["argv"][:2] for call in self.calls() if call["argv"][:2] in (
            ["task", "create"], ["attach", "add"], ["task", "update"])]
        self.assertEqual([["task", "create"], ["attach", "add"], ["task", "update"]], order)

    def test_an_evidence_image_is_attached_and_other_evidence_stays_plain(self):
        self.answer({"task show gw-epic": shown("gw-epic", "open"), "task create": CREATED,
                     "attach add": self.attached(), "task update": {}})
        result = self.bug("TC-AUTH-001", "--actual", "Error", "--evidence", "shot.png", "--evidence", "see log")
        self.assertEqual(0, result.returncode, result.stderr)
        [add] = self.of("attach", "add")
        self.assertNotIn("--step", add["argv"])
        [update] = self.of("task", "update")
        self.assertIn(f"- ![TC-AUTH-001: shot.png](attachment:{self.SHA})\n  local: shot.png\n- see log",
                      update["stdin"])

    def test_the_open_bug_gets_the_attachment_before_the_note(self):
        write(self.root, FILE, CASE.replace("- **Priority:** low\n",
                                            "- **Priority:** low\n- **Result:** failed\n- **Bug:** gw-7\n"))
        self.answer({"task show gw-7": shown("gw-7", "open"), "attach add": self.attached(), "task update": {}})
        result = self.bug("TC-AUTH-001", "--actual", "Still", "--evidence", "shot.png", "--evidence", "see log")
        self.assertEqual(0, result.returncode, result.stderr)
        order = [call["argv"][:2] for call in self.calls() if call["argv"][0] in ("attach", "task")
                 and call["argv"][1] in ("add", "update")]
        self.assertEqual([["attach", "add"], ["task", "update"]], order)
        self.assertEqual("gw-7", self.of("attach", "add")[0]["argv"][2])
        note = self.option(self.of("task", "update")[0]["argv"], "--append-notes")
        self.assertRegex(note, rf"Evidence: shot\.png, see log, attachment:{self.SHA}$")

    def test_a_failing_attach_only_warns(self):
        self.answer({"task show gw-epic": shown("gw-epic", "open"), "task create": CREATED,
                     "attach add": {"stderr": "error: store unreachable\n", "code": 2}})
        result = self.bug("TC-AUTH-001", "--actual", "Error", "--run", self.RUN, "--format", "json")
        self.assertEqual(0, result.returncode, result.stderr)
        row = json.loads(result.stdout)
        self.assertEqual([], row["attachments"])
        self.assertEqual(1, len(row["warnings"]))
        self.assertIn("store unreachable", row["warnings"][0])
        self.assertIn("warning: ", result.stderr)
        self.assertIn("store unreachable", result.stderr)
        self.assertEqual([], self.of("task", "update"))
        self.assertIn("- **Bug:** gw-bug1\n", self.path.read_text(encoding="utf-8"))

    def test_a_refused_file_a_bad_answer_and_a_failed_rewrite_only_warn(self):
        refused = {"stdout": json.dumps({"bead": "gw-bug1", "entries": [],
                                         "refused": [{"name": "shot.png", "reason": "not an image"}]}), "code": 1}
        self.answer({"task show gw-epic": shown("gw-epic", "open"), "task create": CREATED, "attach add": refused})
        result = self.bug("TC-AUTH-001", "--actual", "Error", "--evidence", "shot.png", "--format", "json")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("not an image", json.loads(result.stdout)["warnings"][0])
        self.answer({"task show gw-epic": shown("gw-epic", "open"), "task create": CREATED,
                     "attach add": {"stdout": "not json"}})
        result = self.bug("TC-AUTH-001", "--actual", "Error", "--evidence", "shot.png", "--format", "json")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(1, len(json.loads(result.stdout)["warnings"]))
        self.answer({"task show gw-epic": shown("gw-epic", "open"), "task create": CREATED,
                     "attach add": self.attached(), "task update": {"stderr": "locked\n", "code": 1}})
        result = self.bug("TC-AUTH-001", "--actual", "Error", "--evidence", "shot.png", "--format", "json")
        self.assertEqual(0, result.returncode, result.stderr)
        row = json.loads(result.stdout)
        self.assertEqual(([self.SHA], 1), (row["attachments"], len(row["warnings"])))
        self.assertIn("locked", row["warnings"][0])

    def test_a_corrupt_result_json_warns_and_the_bug_is_still_filed(self):
        (self.root / self.RUN / "tc-auth-001/result.json").write_bytes(b"\xff\xfe\x00{")
        self.answer({"task show gw-epic": shown("gw-epic", "open"), "task create": CREATED})
        result = self.bug("TC-AUTH-001", "--actual", "Error", "--run", self.RUN, "--format", "json")
        self.assertEqual(0, result.returncode, result.stderr)
        warnings = json.loads(result.stdout)["warnings"]
        self.assertEqual(1, len(warnings))
        self.assertIn(self.RUN, warnings[0])
        self.assertIn("warning: ", result.stderr)
        self.assertEqual(1, len(self.creates()))

    def test_only_image_files_inside_the_repository_are_attached(self):
        outside = self.base / "outside.png"
        outside.write_bytes(b"png")
        (self.root / "link.png").symlink_to(outside)
        (self.root / "text.png.txt").write_text("x", encoding="utf-8")
        self.answer({"task show gw-epic": shown("gw-epic", "open"), "task create": CREATED})
        values = [str(outside), "../outside.png", "link.png", "text.png.txt"]
        result = self.bug("TC-AUTH-001", "--actual", "Error", *(a for v in values for a in ("--evidence", v)))
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual([], self.of("attach"))
        [create] = self.creates()
        for value in values:
            self.assertIn(f"- {value}\n" if value != values[-1] else f"- {value}", create["stdin"])

    def test_a_qa_repository_apart_from_the_project_resolves_paths_from_its_own_root(self):
        parent, child = make_workspace_qa(self.base / "ws")
        write(parent, "docs/specs/auth/spec.md", AUTH_SPEC)
        write(child, "cases/auth/TC-AUTH-001-sign-in.manual.md", case_file("TC-AUTH-001", "REQ: REQ-AUTH-001@00000000"))
        run = "evidence/2026-11-04T08-00-00"
        write(child, f"{run}/run.json", json.dumps({"specs": ["e2e/auth/tc-auth-001.spec.ts"]}))
        write(child, f"{run}/tc-auth-001/02.png", "png-bytes")
        write(child, f"{run}/tc-auth-001/result.json", json.dumps({
            "tc": "TC-AUTH-001", "status": "failed", "steps": [
                {"n": 2, "title": "2. Click", "status": "failed", "screenshot": "02.png"}]}))
        write(child, "shot.png", "png-bytes")
        commit_all(child, "case")
        self.answer({"task show gw-epic": shown("gw-epic", "open"), "task create": CREATED,
                     "attach add": self.attached(), "task update": {}})
        result = qa(None, self.bin, "bug", "TC-AUTH-001", "--actual", "Error", "--run", run, "--evidence", "shot.png",
                    "--discovered-from", "gw-epic", "--format", "json", cwd=child)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual([self.SHA, self.SHA], json.loads(result.stdout)["attachments"])
        files = [Path(call["argv"][3]).relative_to(child.resolve()).as_posix() for call in self.of("attach", "add")]
        self.assertEqual(["shot.png", f"{run}/tc-auth-001/02.png"], files)
        [update] = self.of("task", "update")
        self.assertIn(f"  local: {run}/tc-auth-001/02.png", update["stdin"])
        self.assertIn("  local: shot.png", update["stdin"])

    def test_no_image_means_no_attach_and_no_rewrite(self):
        self.answer({"task show gw-epic": shown("gw-epic", "open"), "task create": CREATED})
        result = self.bug("TC-AUTH-001", "--actual", "Error", "--evidence", "see log", "--evidence", "notes.txt")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual([], self.of("attach"))
        self.assertEqual([], self.of("task", "update"))


class TestSdd(BugCase):
    def setUp(self):
        super().setUp()
        self.root = make_repo(self.base / "repo")
        write(self.root, "docs/specs/auth/spec.md", AUTH_SPEC)
        make_change(self.root, spec_delta=delta(added=ADDED_BLOCK))

    def ref(self, *reqs: str) -> str:
        return "REQ: " + ", ".join(f"{req}@{hash8(self.root, self.bin, req)}" for req in reqs)

    def test_one_epic_files_without_a_choice(self):
        write(self.root, "qa/cases/auth/TC-AUTH-001.manual.md",
              case_file("TC-AUTH-001", self.ref("REQ-AUTH-001", "REQ-AUTH-003")))
        self.answer({"task show ep-1": shown("ep-1", "in_progress"), "task create": CREATED})
        result = self.bug("TC-AUTH-001", "--actual", "Locked out after 3 tries", "--format", "json")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("ep-1", json.loads(result.stdout)["epic"])
        [call] = self.creates()
        self.assertEqual("discovered-from:ep-1", self.option(call["argv"], "--deps"))
        self.assertEqual("1", self.option(call["argv"], "-p"))

    def test_several_epics_exit_2_until_one_is_chosen(self):
        make_change(self.root, "ep-2-other", epic="ep-2",
                    spec_delta=delta(added=ADDED_BLOCK.replace("REQ-AUTH-003", "REQ-AUTH-004")))
        path = write(self.root, "qa/cases/auth/TC-AUTH-001.manual.md",
                     case_file("TC-AUTH-001", self.ref("REQ-AUTH-003", "REQ-AUTH-004")))
        before = path.read_text(encoding="utf-8")
        result = self.bug("TC-AUTH-001", "--actual", "Error")
        self.assertEqual(2, result.returncode)
        self.assertIn("several epics for TC-AUTH-001: ep-1, ep-2", result.stderr)
        self.assertEqual([], self.creates())
        self.assertEqual(before, path.read_text(encoding="utf-8"))
        self.answer({"task show ep-2": shown("ep-2", "open"), "task create": CREATED})
        result = self.bug("TC-AUTH-001", "--actual", "Error", "--discovered-from", "ep-2")
        self.assertEqual(0, result.returncode, result.stderr)
        [call] = self.creates()
        self.assertEqual("discovered-from:ep-2", self.option(call["argv"], "--deps"))

    def test_living_reqs_only_have_no_epic(self):
        write(self.root, "qa/cases/auth/TC-AUTH-001.manual.md", case_file("TC-AUTH-001", self.ref("REQ-AUTH-001")))
        result = self.bug("TC-AUTH-001", "--actual", "Error")
        self.assertEqual(2, result.returncode)
        self.assertIn("no epic for TC-AUTH-001", result.stderr)


if __name__ == "__main__":
    unittest.main()
