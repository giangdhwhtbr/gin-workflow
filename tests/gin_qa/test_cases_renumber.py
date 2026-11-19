"""`gin-qa cases renumber`: close the gaps of a capability and rewrite every reference gin-qa owns."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "plugins/gin-qa/src/scripts"))

from qa_fixtures import (AUTH_SPEC, case_file, commit_all, gin_workflow_bin, hash8 as req_hash8,  # noqa: E402
                         make_repo, write, write_activity)
from qa_fixtures import qa as qa_subprocess, qa_in_process as qa  # noqa: E402
from gin_qa.cases import hash8 as case_hash8, parse_case_file  # noqa: E402

RUN = "qa/evidence/2026-11-04T08-00-00"
GUIDELINES = ("## Automated types\n\n### api\n- Tests: `backend/tests/**/test_*.py`\n"
              "- Run: `fake {files} --junitxml={junit}`\n")
CASES = (("001", "e2e", "One"), ("002", "api", "Two"), ("005", "e2e", "Five"), ("009", "api", "Nine"))


class RenumberCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.bin = gin_workflow_bin(self.base)
        self.root = make_repo(self.base / "repo")
        write(self.root, "docs/specs/auth/spec.md", AUTH_SPEC)
        write_activity(self.root)
        write(self.root, "qa/guidelines.md", GUIDELINES)
        for number, kind, title in CASES:
            self.add_case(number, kind, title)
        for number in ("001", "005"):
            tc_id = f"TC-AUTH-{number}"
            write(self.root, f"qa/e2e/auth/{tc_id.lower()}.spec.ts",
                  f"// TC: {tc_id}@{self.tc_hash(tc_id)}\ntest('{tc_id}: x', async () => {{}});\n")
        write(self.root, "backend/tests/test_auth.py", "".join(
            f"# TC: TC-AUTH-{n}@{self.tc_hash(f'TC-AUTH-{n}')}\ndef test_tc_auth_{n}_x():\n    pass\n\n"
            for n in ("002", "009")))
        write(self.root, f"{RUN}/run.json", json.dumps({"started": "2026-11-04T08:00:00+00:00",
                                                        "specs": ["qa/e2e/auth/tc-auth-005.spec.ts"],
                                                        "playwright_exit": 1}))
        write(self.root, f"{RUN}/tc-auth-005/01.png", "png-bytes")
        write(self.root, f"{RUN}/tc-auth-005/result.json", json.dumps({
            "tc": "TC-AUTH-005", "tc_hash8": self.tc_hash("TC-AUTH-005"), "project": None, "status": "failed",
            "error": None, "started": "2026-11-04T08:00:01Z", "finished": "2026-11-04T08:00:09Z",
            "steps": [{"n": 1, "title": "1. Open /login", "status": "failed", "screenshot": "01.png",
                       "snapshot": None, "url": "http://127.0.0.1/login", "error": "timeout"}]}))
        self.assertEqual(0, qa(self.root, self.bin, "result", "TC-AUTH-005", "failed", "--run", RUN).returncode)
        commit_all(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def add_case(self, number: str, kind: str, title: str) -> Path:
        req = "REQ-AUTH-002" if title == "Two" else "REQ-AUTH-001"  # every REQ covered, so `cases check` is ok
        return write(self.root, f"qa/cases/auth/TC-AUTH-{number}-{title.lower()}.{kind}.md",
                     case_file(f"TC-AUTH-{number}", f"REQ: {req}@{req_hash8(self.root, self.bin, req)}",
                               title=title))

    def tc_hash(self, tc_id: str) -> str:
        path = next((self.root / "qa/cases/auth").glob(f"{tc_id}-*.md"))
        return case_hash8(parse_case_file(path, path.relative_to(self.root).as_posix())[0][0])

    def tree(self) -> dict[str, bytes]:
        return {path.relative_to(self.root).as_posix(): path.read_bytes()
                for path in sorted(self.root.rglob("*")) if path.is_file() and ".git" not in path.parts}

    def renumber(self, *args: str):
        return qa(self.root, self.bin, "renumber", "auth", *args)


class TestRenumber(RenumberCase):
    def test_dry_run_prints_the_mapping_and_writes_nothing(self):
        before = self.tree()
        result = self.renumber("--dry-run", "--format", "json")
        self.assertEqual(0, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual({"TC-AUTH-005": "TC-AUTH-003", "TC-AUTH-009": "TC-AUTH-004"}, payload["mapping"])
        self.assertTrue(payload["dry_run"])
        self.assertEqual(before, self.tree())

    def test_rewrites_cases_specs_markers_and_evidence(self):
        result = qa_subprocess(self.root, self.bin, "renumber", "auth")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("TC-AUTH-005 -> TC-AUTH-003\nTC-AUTH-009 -> TC-AUTH-004\n", result.stdout)
        self.assertTrue(result.stdout.endswith(
            "not rewritten: bug bead titles, gin-qa tests run folders, exported reports\n"))
        self.assertEqual(["TC-AUTH-001-one.e2e.md", "TC-AUTH-002-two.api.md", "TC-AUTH-003-five.e2e.md",
                          "TC-AUTH-004-nine.api.md"],
                         sorted(path.name for path in (self.root / "qa/cases/auth").glob("*.md")))
        self.assertTrue((self.root / "qa/cases/auth/TC-AUTH-003-five.e2e.md").read_text()
                        .startswith("# TC-AUTH-003: Five\n"))
        spec = (self.root / "qa/e2e/auth/tc-auth-003.spec.ts").read_text()
        self.assertTrue(spec.startswith(f"// TC: TC-AUTH-003@{self.tc_hash('TC-AUTH-003')}\n"))
        self.assertIn("test('TC-AUTH-003: x'", spec)
        self.assertFalse((self.root / "qa/e2e/auth/tc-auth-005.spec.ts").exists())
        test = (self.root / "backend/tests/test_auth.py").read_text()
        self.assertIn("# TC: TC-AUTH-004@", test)
        self.assertIn("def test_tc_auth_004_x():", test)
        self.assertNotIn("009", test)
        self.assertEqual("TC-AUTH-003",
                         json.loads((self.root / RUN / "tc-auth-003/result.json").read_text())["tc"])
        self.assertEqual(["qa/e2e/auth/tc-auth-003.spec.ts"],
                         json.loads((self.root / RUN / "run.json").read_text())["specs"])
        for group in ("cases", "e2e", "tests"):
            found = qa(self.root, self.bin, "check", group=group)
            self.assertEqual((0, "ok\n"), (found.returncode, found.stdout), f"{group}: {found.stderr}")
        export = json.loads(qa(self.root, self.bin, "export", "--run", RUN, "--format", "json",
                               group="e2e").stdout)
        row = next(row for row in export["cases"] if row["id"] == "TC-AUTH-003")
        self.assertEqual(1, len(row["results"]))

    def test_chained_numbers_move_in_one_pass(self):
        (self.root / "qa/cases/auth/TC-AUTH-001-one.e2e.md").unlink()
        (self.root / "qa/e2e/auth/tc-auth-001.spec.ts").unlink()
        two, five = self.tc_hash("TC-AUTH-002"), self.tc_hash("TC-AUTH-005")
        write(self.root, "qa/e2e/auth/tc-auth-002.spec.ts", f"// TC: TC-AUTH-002@{two}\n")  # 002 -> 001 while 005 -> 002
        commit_all(self.root)
        self.assertEqual(0, self.renumber().returncode)
        self.assertEqual(["TC-AUTH-001-two.api.md", "TC-AUTH-002-five.e2e.md", "TC-AUTH-003-nine.api.md"],
                         sorted(path.name for path in (self.root / "qa/cases/auth").glob("*.md")))
        self.assertEqual(f"// TC: TC-AUTH-001@{two}\n", (self.root / "qa/e2e/auth/tc-auth-001.spec.ts").read_text())
        self.assertTrue((self.root / "qa/e2e/auth/tc-auth-002.spec.ts").read_text()
                        .startswith(f"// TC: TC-AUTH-002@{five}\n"))
        test = (self.root / "backend/tests/test_auth.py").read_text()
        self.assertIn("def test_tc_auth_001_x():", test)
        self.assertIn("def test_tc_auth_003_x():", test)

    def test_contiguous_numbers_print_nothing_to_renumber(self):
        self.renumber()
        commit_all(self.root)
        before = self.tree()
        result = self.renumber()
        self.assertEqual((0, "nothing to renumber\n"), (result.returncode, result.stdout))
        self.assertEqual(before, self.tree())

    def test_refusals_write_nothing(self):
        cases = {
            "flat": (lambda: write(self.root, "qa/cases/auth.md", "# Test cases: auth\n"),
                     "qa/cases/auth.md: a flat cases file; run `gin-qa cases split auth` first"),
            "duplicate": (lambda: self.add_case("005", "manual", "Again"), "duplicate TC-AUTH-005"),
            "orphan spec": (lambda: write(self.root, "qa/e2e/auth/tc-auth-007.spec.ts",
                                          "// TC: TC-AUTH-007@00000000\n"),
                            "qa/e2e/auth/tc-auth-007.spec.ts: orphan e2e spec"),
            "orphan marker": (lambda: write(self.root, "backend/tests/test_more.py",
                                            "# TC: TC-AUTH-007@00000000\n"),
                              "backend/tests/test_more.py:1: orphan marker TC-AUTH-007"),
            "uncommitted": (lambda: (self.root / "backend/tests/test_auth.py").open("a").write("# note\n"),
                            "backend/tests/test_auth.py: not committed"),
            "target": (lambda: write(self.root, f"{RUN}/tc-auth-003/result.json", "{}"),
                       f"{RUN}/tc-auth-003: already exists"),
        }
        for name, (make, message) in cases.items():
            with self.subTest(name):
                make()
                if name != "uncommitted":
                    commit_all(self.root)
                before = self.tree()
                result = self.renumber()
                self.assertEqual(1, result.returncode, result.stderr)
                self.assertIn(message, result.stdout)
                self.assertEqual(before, self.tree())
                subprocess.run(["git", "reset", "-q", "--hard", "HEAD~1" if name != "uncommitted" else "HEAD"],
                               cwd=self.root, check=True)
                subprocess.run(["git", "clean", "-qfdx", "--", "qa/evidence/"], cwd=self.root, check=True)


if __name__ == "__main__":
    unittest.main()
