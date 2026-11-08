"""`gin-qa report`: the report folder, its embedded data, copied screenshots, scope, and errors."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))

from qa_fixtures import AUTH_SPEC, ROOT, TOOLS_PATH, case_file, gin_workflow_bin, make_repo, qa, write  # noqa: E402
from gin_qa import report  # noqa: E402
from gin_qa.reqs import resolve, specs_reqs  # noqa: E402

TEMPLATE = ROOT / "plugins/gin-qa/src/templates/report.html"
SLOT = '<script type="application/json" id="gin-qa-data">/*GIN_QA_DATA*/</script>'
DATA = re.compile(r'<script type="application/json" id="gin-qa-data">(.*?)</script>', re.S)
RUN = "qa/evidence/2026-11-04T08-00-00"


class ReportCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.bin = gin_workflow_bin(self.base)
        self.root = make_repo(self.base / "repo")
        write(self.root, "docs/specs/auth/spec.md", AUTH_SPEC)
        write(self.root, "qa/cases/auth/TC-AUTH-001-login.e2e.md",
              case_file("TC-AUTH-001", "REQ: REQ-AUTH-001@00000000", title="Login"))
        write(self.root, "qa/cases/billing/TC-BILLING-001-pay.manual.md",
              case_file("TC-BILLING-001", "REQ: REQ-BILLING-001@00000000", title="Pay"))
        write(self.root, f"{RUN}/run.json", json.dumps({"started": "2026-11-04T08:00:00+00:00",
                                                        "specs": ["qa/e2e/auth/tc-auth-001.spec.ts"],
                                                        "playwright_exit": 1}))
        write(self.root, f"{RUN}/tc-auth-001/01.png", "png-bytes")
        write(self.root, f"{RUN}/tc-auth-001/result.json", json.dumps({
            "tc": "TC-AUTH-001", "tc_hash8": "00000000", "project": None, "status": "failed", "error": None,
            "started": "2026-11-04T08:00:01Z", "finished": "2026-11-04T08:00:09Z",
            "steps": [{"n": 1, "title": "1. Open /login", "status": "failed", "screenshot": "01.png",
                       "snapshot": None, "url": "http://127.0.0.1/login", "error": "timeout"}]}))
        self.record("TC-AUTH-001", "failed", RUN)

    def tearDown(self):
        self.tmp.cleanup()

    def record(self, tc_id: str, status: str, run: str) -> None:
        result = qa(self.root, self.bin, "result", tc_id, status, "--run", run)
        self.assertEqual(0, result.returncode, result.stderr)

    def report(self, *args: str):
        return qa(self.root, self.bin, *args, group="report")

    def report_json(self, *args: str) -> dict:
        result = self.report(*args, "--format", "json")
        self.assertEqual(0, result.returncode, result.stderr)
        return json.loads(result.stdout)

    def page(self, index: Path) -> dict:
        return json.loads(DATA.search(index.read_text(encoding="utf-8")).group(1))

    def reports(self) -> list[Path]:
        return sorted((self.root / "qa/evidence").glob("report-*"))


class TestReport(ReportCase):
    def test_writes_the_folder_and_prints_the_index_path(self):
        result = self.report()
        self.assertEqual(0, result.returncode, result.stderr)
        printed = result.stdout.strip()
        self.assertRegex(printed, r"^qa/evidence/report-\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}/index\.html$")
        index = self.root / printed
        data = self.page(index)
        self.assertEqual((None, ["TC-AUTH-001", "TC-BILLING-001"]),
                         (data["scope"], [row["id"] for row in data["cases"]]))
        auth, billing = data["cases"]
        self.assertEqual(("found", "failed", RUN, "Login"), (auth["evidence"], auth["result"], auth["run"], auth["title"]))
        [run_result] = auth["results"]
        self.assertEqual((None, "failed", "2026-11-04T08:00:01Z"),
                         (run_result["project"], run_result["status"], run_result["started"]))
        self.assertEqual([{"n": 1, "title": "1. Open /login", "status": "failed", "url": "http://127.0.0.1/login",
                           "error": "timeout", "screenshot": "2026-11-04T08-00-00/tc-auth-001/01.png"}],
                         run_result["steps"])
        self.assertEqual("png-bytes", (index.parent / run_result["steps"][0]["screenshot"]).read_text())
        self.assertEqual(("none", [], "not run"), (billing["evidence"], billing["results"], billing["result"]))

    def test_a_screenshot_linking_outside_the_run_folder_is_not_copied(self):
        outside = write(self.root, "secret.png", "secret")
        shot = self.root / RUN / "tc-auth-001/01.png"
        shot.unlink()
        try:
            shot.symlink_to(outside)
        except OSError:  # Windows without the symlink privilege
            self.skipTest("cannot create symlinks here")
        payload = self.report_json()
        [step] = self.page(self.root / payload["report"])["cases"][0]["results"][0]["steps"]
        self.assertEqual((None, 0), (step["screenshot"], payload["screenshots"]))
        self.assertEqual(["index.html"], [path.name for path in (self.root / payload["report"]).parent.iterdir()])

    def test_a_failed_copy_leaves_no_partial_report(self):
        empty = self.root / "empty"
        empty.mkdir()
        search = os.pathsep.join([str(self.bin), TOOLS_PATH])
        with mock.patch.dict(os.environ, {"PATH": search}), \
                mock.patch("gin_qa.report.shutil.copyfile", side_effect=OSError("disk full")):
            eff = resolve(specs_reqs(self.root))
            for out in (None, "empty", "fresh/out"):
                with self.subTest(out=out), self.assertRaises(OSError):
                    report.build(self.root, eff, None, out)
        self.assertEqual([], self.reports())
        self.assertEqual([], list(empty.iterdir()))
        self.assertFalse((self.root / "fresh/out").exists())

    def test_json_output(self):
        payload = self.report_json()
        self.assertEqual((2, 1, []), (payload["cases"], payload["screenshots"], payload["missing_evidence"]))
        self.assertTrue((self.root / payload["report"]).is_file())

    def test_the_folder_moved_elsewhere_still_holds_every_image(self):
        index = self.root / self.report_json()["report"]
        moved = Path(shutil.move(str(index.parent), str(self.base / "sent")))
        shots = [step["screenshot"] for row in self.page(moved / "index.html")["cases"]
                 for result in row["results"] for step in result["steps"]]
        self.assertEqual(["2026-11-04T08-00-00/tc-auth-001/01.png"], shots)
        for shot in shots:
            self.assertFalse(Path(shot).is_absolute() or ".." in Path(shot).parts, shot)
            self.assertTrue((moved / shot).is_file(), shot)

    def test_capability_scope(self):
        payload = self.report_json("billing")
        folder = (self.root / payload["report"]).parent
        data = self.page(folder / "index.html")
        self.assertEqual(("billing", ["TC-BILLING-001"], 0),
                         (data["scope"], [row["id"] for row in data["cases"]], payload["screenshots"]))
        self.assertEqual(["index.html"], [path.name for path in folder.iterdir()])

    def test_case_text_cannot_close_the_script_element(self):
        title = "Login </script><script>alert(1)</script>"
        write(self.root, "qa/cases/auth/TC-AUTH-001-login.e2e.md",
              case_file("TC-AUTH-001", "REQ: REQ-AUTH-001@00000000", title=title))
        index = self.root / self.report_json()["report"]
        text = index.read_text(encoding="utf-8")
        self.assertEqual(TEMPLATE.read_text(encoding="utf-8").count("</script>"), text.count("</script>"))
        self.assertEqual(title, self.page(index)["cases"][0]["title"])

    def test_a_missing_run_folder_is_reported_and_the_rest_is_written(self):
        self.record("TC-AUTH-001", "failed", "qa/evidence/gone")
        result = self.report("--format", "json")
        self.assertEqual(0, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(["qa/evidence/gone"], payload["missing_evidence"])
        self.assertIn("evidence not found: qa/evidence/gone", result.stderr)
        auth = self.page(self.root / payload["report"])["cases"][0]
        self.assertEqual(("missing", "failed", []), (auth["evidence"], auth["result"], auth["results"]))

    def test_a_run_outside_the_evidence_folder_is_plain_text(self):
        self.record("TC-BILLING-001", "passed", "sprint-12 sheet")
        payload = self.report_json()
        billing = self.page(self.root / payload["report"])["cases"][1]
        self.assertEqual(("none", "sprint-12 sheet", "passed", []),
                         (billing["evidence"], billing["run"], billing["result"], payload["missing_evidence"]))

    def test_a_tests_run_folder_is_a_plain_reference(self):
        run = "qa/evidence/2026-11-04T09-00-00-api"
        write(self.root, f"{run}/run.json", json.dumps({"type": "api", "started": "2026-11-04T09:00:00+00:00",
                                                        "command": ["pytest"], "cases": ["TC-BILLING-001"], "exit": 0}))
        self.record("TC-BILLING-001", "passed", run)
        result = self.report_json()
        payload = result
        billing = self.page(self.root / payload["report"])["cases"][1]
        self.assertEqual(("none", run, "passed", []),
                         (billing["evidence"], billing["run"], billing["result"], payload["missing_evidence"]))

    def test_out_folder(self):
        result = self.report("--out", "reports/today")
        self.assertEqual((0, "reports/today/index.html"), (result.returncode, result.stdout.strip()), result.stderr)
        self.assertTrue((self.root / "reports/today/2026-11-04T08-00-00/tc-auth-001/01.png").is_file())
        self.assertEqual([], self.reports())

    def test_two_reports_get_two_folders(self):
        first, second = self.report_json()["report"], self.report_json()["report"]
        self.assertNotEqual(first, second)
        self.assertEqual(2, len(self.reports()))

    def test_errors_exit_2_and_write_nothing(self):
        write(self.root, "out/kept.txt", "kept")
        for args, message in ((["nope"], "no test cases for capability nope"),
                              (["--out", "out"], "out: exists and is not an empty folder")):
            with self.subTest(args=args):
                result = self.report(*args)
                self.assertEqual(2, result.returncode)
                self.assertIn(message, result.stderr)
        shutil.rmtree(self.root / "qa/cases")
        result = self.report()
        self.assertEqual(2, result.returncode)
        self.assertIn("no test cases under qa/cases", result.stderr)
        self.assertEqual([], self.reports())
        self.assertEqual(["kept.txt"], [path.name for path in (self.root / "out").iterdir()])

    def test_moved_cases_are_counted_and_carry_date_and_reason(self):
        self.assertEqual(0, self.report_json()["moved"])
        result = qa(self.root, self.bin, "to-manual", "TC-AUTH-001", "--reason", "flaky on CI")
        self.assertEqual(0, result.returncode, result.stderr)
        self.record("TC-AUTH-001", "passed", "manual 2026-11-07")
        payload = self.report_json()
        self.assertEqual(1, payload["moved"])
        row = next(item for item in self.page(self.root / payload["report"])["cases"] if item["id"] == "TC-AUTH-001")
        self.assertEqual(("manual", "passed", "flaky on CI"),
                         (row["type"], row["result"], row["moved_from_e2e"]["reason"]))

    def test_the_template_holds_the_moved_section(self):
        text = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn('id="moved"', text)
        self.assertIn("Moved from e2e to manual", text)
        self.assertIn("moved_from_e2e", text)

    def test_zip_holds_the_folder_and_keeps_it(self):
        payload = self.report_json("--zip")
        folder = (self.root / payload["report"]).parent
        self.assertEqual(f"{folder.name}.zip", Path(payload["zip"]).name)
        with zipfile.ZipFile(self.root / payload["zip"]) as archive:
            names = archive.namelist()
        self.assertIn(f"{folder.name}/index.html", names)
        self.assertIn(f"{folder.name}/2026-11-04T08-00-00/tc-auth-001/01.png", names)
        self.assertTrue(folder.is_dir())
        self.assertIsNone(self.report_json()["zip"])

    def test_a_failed_zip_exits_2_and_leaves_no_archive(self):
        search = os.pathsep.join([str(self.bin), TOOLS_PATH])
        with mock.patch.dict(os.environ, {"PATH": search}), \
                mock.patch("gin_qa.report.shutil.make_archive", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                report.build(self.root, resolve(specs_reqs(self.root)), None, "out", archive=True)
        self.assertEqual([], list(self.root.glob("*.zip")) + list(self.root.glob(".*.zip")))

    def test_the_evidence_folder_is_ignored_once_and_out_elsewhere_is_not(self):
        self.assertEqual(0, self.report("--out", "elsewhere").returncode)
        self.assertFalse((self.root / ".gitignore").exists())
        self.report_json()
        self.report_json()
        self.assertEqual(1, (self.root / ".gitignore").read_text().split().count("/qa/evidence/"))


class TestTemplate(unittest.TestCase):
    def test_one_data_slot_and_no_unsafe_or_remote_code(self):
        text = TEMPLATE.read_text(encoding="utf-8")
        self.assertEqual(1, text.count(SLOT))
        self.assertEqual(1, text.count("/*GIN_QA_DATA*/"))
        for banned in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function",
                       "http://", "https://", "<link", "<script src", "@import"):
            with self.subTest(banned=banned):
                self.assertNotIn(banned, text)


if __name__ == "__main__":
    unittest.main()
