"""gin-qa run history: a record per result, the union merge, and `gin-qa runs export`."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from qa_fixtures import case_file, commit_all, gin_workflow_bin, make_repo, write  # noqa: E402
from qa_fixtures import qa as qa_subprocess, qa_in_process as qa  # noqa: E402
from gin_qa import runs  # noqa: E402

FILE = "qa/cases/auth/TC-AUTH-001.e2e.md"
SOURCE = "Source: docs/specs/login.md"


class RunsCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.bin = gin_workflow_bin(self.base)
        self.root = make_repo(self.base / "repo", layout="legacy")
        write(self.root, "docs/specs/login.md", "# Login\n")
        write(self.root, FILE, case_file("TC-AUTH-001", SOURCE))

    def tearDown(self):
        self.tmp.cleanup()

    def result(self, *args: str):
        return qa(self.root, self.bin, "result", "TC-AUTH-001", *args)

    def records(self, relative: str) -> list[dict]:
        text = (self.root / relative).read_text(encoding="utf-8")
        return [json.loads(line) for line in text.splitlines()]

    def exported_case(self) -> dict:
        return json.loads(qa(self.root, self.bin, "export", "--format", "json").stdout)["cases"][0]


class TestRecord(RunsCase):
    def test_each_result_appends_a_record_and_the_case_keeps_the_latest(self):
        with mock.patch.object(runs, "now", side_effect=["2026-11-22T10:15:03Z", "2026-11-22T11:00:00Z"]):
            first = self.result("failed", "--run", "manual 2026-11-22", "--bug", "gw-7", "--actor", "a@x.com",
                                "--evidence", "shots/1.png", "--evidence", "https://logs.example/42")
            second = self.result("passed", "--run", "manual 2026-11-22", "--actor", "a@x.com")
        self.assertEqual((0, 0), (first.returncode, second.returncode), first.stderr + second.stderr)
        exported = self.exported_case()
        common = {"actor": "a@x.com", "bug": "gw-7", "capability": "auth", "case": "TC-AUTH-001",
                  "hash8": exported["hash8"], "run": "manual 2026-11-22"}
        self.assertEqual([{**common, "at": "2026-11-22T10:15:03Z", "result": "failed",
                           "evidence": ["shots/1.png", "https://logs.example/42"]},
                          {**common, "at": "2026-11-22T11:00:00Z", "result": "passed", "evidence": []}],
                         self.records("qa/runs/2026-11/a-x.com.jsonl"))
        line = (self.root / "qa/runs/2026-11/a-x.com.jsonl").read_text(encoding="utf-8").splitlines()[0]
        self.assertTrue(line.startswith('{"actor":"a@x.com","at":"2026-11-22T10:15:03Z","bug":"gw-7",'), line)
        self.assertEqual(("passed", "manual 2026-11-22", "gw-7"),
                         (exported["result"], exported["run"], exported["bug"]))

    def test_the_actor_defaults_to_the_git_email_then_unknown(self):
        with mock.patch.object(runs, "now", return_value="2026-11-22T10:15:03Z"):
            self.assertEqual(0, self.result("passed").returncode)
            subprocess.run(["git", "config", "--unset", "user.email"], cwd=self.root, check=True)
            with mock.patch.dict(os.environ, {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}):
                self.assertEqual(0, self.result("passed").returncode)
        self.assertEqual(["t@example.com"], [row["actor"] for row in self.records("qa/runs/2026-11/t-example.com.jsonl")])
        self.assertEqual(["unknown"], [row["actor"] for row in self.records("qa/runs/2026-11/unknown.jsonl")])

    def test_a_bad_actor_or_evidence_exits_2_and_writes_nothing(self):
        before = (self.root / FILE).read_text(encoding="utf-8")
        for args in (("--actor", "a\nb"), ("--actor", ""), ("--evidence", "")):
            with self.subTest(args=args):
                result = self.result("passed", *args)
                self.assertEqual(2, result.returncode)
                self.assertIn("values are one non-empty line", result.stderr)
        self.assertEqual(before, (self.root / FILE).read_text(encoding="utf-8"))
        self.assertFalse((self.root / "qa/runs").exists())

    def test_a_failed_append_exits_2_and_leaves_the_case_file_unchanged(self):
        before = (self.root / FILE).read_text(encoding="utf-8")
        write(self.root, "qa/runs", "a file where the folder should be\n")
        result = self.result("passed", "--actor", "a@x.com")
        self.assertEqual(2, result.returncode)
        self.assertIn("qa/runs/", result.stderr)
        self.assertIn("run record not written", result.stderr)
        self.assertEqual(before, (self.root / FILE).read_text(encoding="utf-8"))

    def test_gitattributes_gets_the_union_entry_once(self):
        write(self.root, ".gitattributes", "* text=auto eol=lf\n")
        for _ in range(2):
            self.assertEqual(0, self.result("passed").returncode)
        self.assertEqual("* text=auto eol=lf\n/qa/runs/** merge=union\n",
                         (self.root / ".gitattributes").read_text(encoding="utf-8"))

    def test_to_manual_appends_no_record(self):
        with mock.patch.object(runs, "now", return_value="2026-11-22T10:15:03Z"):
            self.assertEqual(0, self.result("passed", "--actor", "a@x.com").returncode)
            moved = qa(self.root, self.bin, "to-manual", "TC-AUTH-001", "--reason", "flaky")
        self.assertEqual(0, moved.returncode, moved.stderr)
        self.assertEqual(["a-x.com.jsonl"], [path.name for path in (self.root / "qa/runs").rglob("*.jsonl")])
        self.assertEqual(1, len(self.records("qa/runs/2026-11/a-x.com.jsonl")))


class TestMerge(RunsCase):
    def setUp(self):
        super().setUp()
        commit_all(self.root, "base")

    def git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["git", *args], cwd=self.root, capture_output=True, text=True)

    def branch(self, name: str, actor: str) -> None:
        self.assertEqual(0, self.git("checkout", "-q", "-b", name, "main").returncode)
        self.assertEqual(0, self.result("passed", "--run", "manual 2026-11-22", "--actor", actor).returncode)
        # only what gin-qa wrote: a gin run may leave local runtime files that differ per branch
        self.assertEqual(0, self.git("add", "qa", ".gitattributes").returncode)
        self.assertEqual(0, self.git("commit", "-q", "-m", name).returncode)

    def merge(self) -> None:
        self.assertEqual(0, self.git("checkout", "-q", "a").returncode)
        done = self.git("merge", "--no-edit", "b")
        self.assertEqual(0, done.returncode, done.stdout + done.stderr)
        self.assertEqual("", self.git("status", "--porcelain", "--untracked-files=no").stdout)

    def test_two_testers_merge_without_conflicts(self):
        with mock.patch.object(runs, "now", side_effect=["2026-11-22T10:15:03Z", "2026-11-22T11:00:00Z"]):
            self.branch("a", "a@x.com")
            self.branch("b", "b@x.com")
        self.merge()
        self.assertEqual(["a@x.com"], [row["actor"] for row in self.records("qa/runs/2026-11/a-x.com.jsonl")])
        self.assertEqual(["b@x.com"], [row["actor"] for row in self.records("qa/runs/2026-11/b-x.com.jsonl")])

    def test_one_tester_on_two_branches_merges_by_union(self):
        with mock.patch.object(runs, "now", side_effect=["2026-11-22T10:15:03Z", "2026-11-22T11:00:00Z"]):
            self.branch("a", "a@x.com")
            self.branch("b", "a@x.com")
        self.merge()
        self.assertEqual(["2026-11-22T10:15:03Z", "2026-11-22T11:00:00Z"],
                         sorted(row["at"] for row in self.records("qa/runs/2026-11/a-x.com.jsonl")))


def record(case: str = "TC-AUTH-001", at: str = "2026-11-22T10:00:00Z", capability: str = "auth",
           result: str = "passed", actor: str = "a@x.com") -> dict:
    return {"actor": actor, "at": at, "bug": "", "capability": capability, "case": case, "evidence": [],
            "hash8": "1a2b3c4d", "result": result, "run": "manual"}


def jsonl(*rows) -> str:
    return "".join((row if isinstance(row, str) else json.dumps(row)) + "\n" for row in rows)


class TestExport(RunsCase):
    def export(self, *args: str):
        return qa(self.root, self.bin, "export", *args, "--format", "json", group="runs")

    def test_two_runs_of_one_case_give_two_records_by_time(self):
        with mock.patch.object(runs, "now", side_effect=["2026-11-22T11:00:00Z", "2026-11-22T10:00:00Z"]):
            self.assertEqual(0, self.result("passed", "--actor", "b@x.com").returncode)
            self.assertEqual(0, self.result("failed", "--actor", "a@x.com").returncode)
        result = qa_subprocess(self.root, self.bin, "export", "--format", "json", group="runs")
        self.assertEqual(0, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual([], payload["problems"])
        self.assertEqual([("2026-11-22T10:00:00Z", "failed"), ("2026-11-22T11:00:00Z", "passed")],
                         [(row["at"], row["result"]) for row in payload["runs"]])

    def test_filters_combine(self):
        write(self.root, "qa/runs/2026-11/a-x.com.jsonl", jsonl(
            record(), record(case="TC-AUTH-002", at="2026-11-23T09:00:00Z"),
            record(case="TC-PAY-001", capability="pay", at="2026-11-24T09:00:00Z")))
        write(self.root, "qa/runs/2026-10/a-x.com.jsonl", jsonl(record(at="2026-10-30T09:00:00Z")))
        for args, cases in ((("--capability", "auth"), ["TC-AUTH-001", "TC-AUTH-001", "TC-AUTH-002"]),
                            (("--case", "TC-AUTH-001"), ["TC-AUTH-001", "TC-AUTH-001"]),
                            (("--since", "2026-11-23"), ["TC-AUTH-002", "TC-PAY-001"]),
                            (("--capability", "auth", "--since", "2026-11-01"), ["TC-AUTH-001", "TC-AUTH-002"])):
            with self.subTest(args=args):
                result = self.export(*args)
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual(cases, [row["case"] for row in json.loads(result.stdout)["runs"]])

    def test_a_broken_line_is_a_problem_and_the_rest_is_returned(self):
        write(self.root, "qa/runs/2026-11/a-x.com.jsonl", jsonl(
            record(), "{not json", "[1]", {"case": "TC-AUTH-001"}, {**record(), "at": "yesterday"},
            record(at="2026-11-22T12:00:00Z")))
        result = self.export()
        self.assertEqual(0, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(["2026-11-22T10:00:00Z", "2026-11-22T12:00:00Z"], [row["at"] for row in payload["runs"]])
        self.assertEqual(["qa/runs/2026-11/a-x.com.jsonl:2: not JSON",
                          "qa/runs/2026-11/a-x.com.jsonl:3: not a JSON object",
                          "qa/runs/2026-11/a-x.com.jsonl:4: missing actor, at, bug, capability, evidence, hash8, "
                          "result, run",
                          "qa/runs/2026-11/a-x.com.jsonl:5: at is not YYYY-MM-DDTHH:MM:SSZ"], payload["problems"])

    def test_no_run_history_is_an_empty_export(self):
        result = self.export()
        self.assertEqual((0, {"problems": [], "runs": []}), (result.returncode, json.loads(result.stdout)))
        text = qa(self.root, self.bin, "export", group="runs")
        self.assertEqual((0, "no runs\n"), (text.returncode, text.stdout))

    def test_text_lists_records_then_problems(self):
        write(self.root, "qa/runs/2026-11/a-x.com.jsonl", jsonl(record(), "{"))
        text = qa(self.root, self.bin, "export", group="runs")
        self.assertEqual("2026-11-22T10:00:00Z TC-AUTH-001 passed a@x.com manual\n"
                         "qa/runs/2026-11/a-x.com.jsonl:2: not JSON\n", text.stdout)

    def test_a_bad_since_exits_2(self):
        for value in ("2026-13-01", "20261122", "yesterday"):
            with self.subTest(value=value):
                self.assertEqual(2, self.export("--since", value).returncode)


if __name__ == "__main__":
    unittest.main()
