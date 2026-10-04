"""`gin-qa e2e`: init, plan, pin, and check."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "plugins/gin-qa/src/scripts"))

from qa_fixtures import AUTH_SPEC, case, cases_file, gin_workflow_bin, make_repo, qa, write  # noqa: E402
from gin_qa.cases import hash8 as case_hash8, parse_file  # noqa: E402

def spec_text(tc_id: str, pinned: str) -> str:
    return (f"// TC: {tc_id}@{pinned}\nimport {{ test, expect }} from '../evidence';\n\n"
            f"test('{tc_id}', async ({{ page, ev }}) => {{\n"
            "  await ev.step('1. Open /login', async () => { await page.goto('/login'); });\n});\n")


class E2eCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.bin = gin_workflow_bin(self.base)
        self.root = make_repo(self.base / "repo")
        write(self.root, "docs/specs/auth/spec.md", AUTH_SPEC)
        manual = case("TC-AUTH-002", "REQ: REQ-AUTH-002@00000000").replace("Type: e2e", "Type: manual")
        self.cases = write(self.root, "qa/cases/auth.md",
                           cases_file("auth", case("TC-AUTH-001", "REQ: REQ-AUTH-001@00000000"), manual))

    def tearDown(self):
        self.tmp.cleanup()

    def e2e(self, *args: str, path: str = "/usr/bin:/bin"):
        return qa(self.root, self.bin, *args, group="e2e", path=path)

    def run_json(self, *args: str) -> dict:
        result = self.e2e(*args, "--format", "json")
        self.assertIn(result.returncode, (0, 1), result.stderr)
        return json.loads(result.stdout)

    def tc_hash(self, tc_id: str = "TC-AUTH-001") -> str:
        found, _ = parse_file(self.cases, "qa/cases/auth.md")
        return next(case_hash8(item) for item in found if item.id == tc_id)

    def write_spec(self, tc_id: str = "TC-AUTH-001", pinned: str | None = None, cap: str = "auth") -> Path:
        return write(self.root, f"qa/e2e/{cap}/{tc_id.lower()}.spec.ts",
                     spec_text(tc_id, pinned or self.tc_hash(tc_id)))


class TestInitPlanPin(E2eCase):
    def test_init_copies_the_fixture_once_and_ignores_evidence(self):
        result = self.e2e("init")
        self.assertEqual(0, result.returncode, result.stderr)
        fixture = self.root / "qa/e2e/evidence.ts"
        self.assertIn("result.json", fixture.read_text())
        self.assertIn("npm install -D @playwright/test", result.stdout)
        fixture.write_text("// edited by QA\n")
        write(self.root, "node_modules/@playwright/test/package.json", "{}")
        self.assertEqual((0, "already initialized\n"), (self.e2e("init").returncode, self.e2e("init").stdout))
        self.assertEqual("// edited by QA\n", fixture.read_text())
        self.assertEqual(1, (self.root / ".gitignore").read_text().splitlines().count("/qa/evidence/"))

    def test_plan_lists_missing_stale_and_orphan_e2e_cases_only(self):
        self.assertEqual(["TC-AUTH-001"], [row["tc"] for row in self.run_json("plan")["missing"]])
        self.write_spec(pinned="00000000")
        self.write_spec("TC-AUTH-002")
        payload = self.run_json("plan", "auth")
        self.assertEqual(([], ["TC-AUTH-001"], ["qa/e2e/auth/tc-auth-002.spec.ts"]),
                         (payload["missing"], [row["tc"] for row in payload["stale"]],
                          [row["spec"] for row in payload["orphan"]]))
        self.assertEqual(("qa/e2e", self.tc_hash(), "00000000", ["Open /login", 'Click "Sign in"']),
                         (payload["e2e"], payload["stale"][0]["hash8"], payload["stale"][0]["pinned"],
                          payload["stale"][0]["case"]["steps"]))
        self.assertEqual({"missing": [], "stale": [], "orphan": []},
                         {key: self.run_json("plan", "billing")[key] for key in ("missing", "stale", "orphan")})

    def test_pin_rewrites_or_inserts_only_the_header(self):
        spec = self.write_spec(pinned="00000000")
        body = spec.read_text().split("\n", 1)[1]
        self.assertEqual(0, self.e2e("pin", "TC-AUTH-001").returncode)
        self.assertEqual(f"// TC: TC-AUTH-001@{self.tc_hash()}\n{body}", spec.read_text())
        spec.write_text(body)
        self.assertEqual(0, self.e2e("pin", "TC-AUTH-001").returncode)
        self.assertEqual(f"// TC: TC-AUTH-001@{self.tc_hash()}\n{body}", spec.read_text())
        result = self.e2e("pin", "TC-AUTH-002", "TC-AUTH-009")
        self.assertEqual(1, result.returncode)
        self.assertEqual("TC-AUTH-002: no such e2e test case\nTC-AUTH-009: no such e2e test case\n", result.stdout)
        spec.unlink()
        self.assertEqual("TC-AUTH-001: no spec at qa/e2e/auth/tc-auth-001.spec.ts\n",
                         self.e2e("pin", "TC-AUTH-001").stdout)


class TestCheckSpecs(E2eCase):
    def test_clean_and_unaffected_by_requirement_pins(self):
        self.write_spec()
        self.assertEqual((0, "ok\n"), (self.e2e("check").returncode, self.e2e("check").stdout))
        self.cases.write_text(self.cases.read_text().replace("REQ-AUTH-001@00000000", "REQ-AUTH-001@12345678"))
        self.assertEqual(0, self.e2e("check").returncode)
        self.cases.write_text(self.cases.read_text().replace("Click \"Sign in\"", "Press Enter", 1))
        self.assertEqual(1, self.e2e("check").returncode)

    def test_every_finding(self):
        self.write_spec(pinned="00000000")
        write(self.root, "qa/e2e/auth/tc-auth-002.spec.ts", spec_text("TC-AUTH-002", "00000000"))
        write(self.root, "qa/e2e/auth/notes.spec.ts", "import { test } from '../evidence';\n")
        write(self.root, "qa/e2e/billing/tc-auth-001.spec.ts", spec_text("TC-AUTH-001", self.tc_hash()))
        now = self.tc_hash()
        self.assertEqual([
            "qa/e2e/auth/notes.spec.ts:1: needs a first line '// TC: <TC-ID>@<hash8>'; write it with "
            "`gin-qa e2e pin <TC-ID>`",
            "qa/e2e/billing/tc-auth-001.spec.ts:1: TC-AUTH-001 belongs in qa/e2e/auth/tc-auth-001.spec.ts",
            f"qa/e2e/auth/tc-auth-001.spec.ts:1: TC-AUTH-001 changed (pinned 00000000, now {now}); update the "
            "spec, then `gin-qa e2e pin TC-AUTH-001`",
            "qa/e2e/auth/tc-auth-002.spec.ts:1: TC-AUTH-002 is not an e2e test case any more",
        ], self.run_json("check")["findings"])
        for path in self.root.glob("qa/e2e/*/*.spec.ts"):
            path.unlink()
        self.assertEqual(["qa/cases/auth.md:3: TC-AUTH-001 has no e2e spec (qa/e2e/auth/tc-auth-001.spec.ts)"],
                         self.run_json("check")["findings"])


if __name__ == "__main__":
    unittest.main()
