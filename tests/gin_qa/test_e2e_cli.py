"""`gin-qa e2e`: init, plan, pin, check, run (with a fake npx), and export."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "plugins/gin-qa/src/scripts"))

from qa_fixtures import AUTH_SPEC, QA_LAUNCHER, TOOLS_PATH, case, cases_file, gin_workflow_bin, make_repo, python_stub, write  # noqa: E402
from qa_fixtures import qa as qa_subprocess, qa_in_process  # noqa: E402
from gin_qa.cases import hash8 as case_hash8, parse_file  # noqa: E402

FAKE_NPX = textwrap.dedent('''\
    #!{python}
    """Stands in for `npx playwright test <specs>`: writes the evidence a passing spec would leave."""
    import json, os, pathlib, re, sys
    root, run = pathlib.Path.cwd(), pathlib.Path(os.environ["GIN_QA_RUN_DIR"])
    (root / ".npx-args").write_text(json.dumps(sys.argv[1:]))
    skip = (root / ".fake-skip").read_text().split() if (root / ".fake-skip").exists() else []
    for spec in [arg for arg in sys.argv[3:] if arg.endswith(".spec.ts")]:
        tc, pinned = re.match(r"// TC: (\\S+)@(\\w+)", (root / spec).read_text()).groups()
        if tc in skip:
            continue
        folder = run / tc.lower()
        folder.mkdir(parents=True)
        (folder / "01.png").write_bytes(b"png")
        (folder / "01.aria.yml").write_text("- heading Login")
        (folder / "result.json").write_text(json.dumps({{"tc": tc, "tc_hash8": pinned, "status": "passed",
            "steps": [{{"n": 1, "title": "1. Open /login", "status": "passed", "screenshot": "01.png",
                        "snapshot": "01.aria.yml", "url": "http://127.0.0.1/login", "error": None}}]}}))
    exit_file = root / ".fake-exit"
    sys.exit(int(exit_file.read_text()) if exit_file.exists() else 0)
''').format(python=sys.executable)

FAKE_MANAGER = textwrap.dedent('''\
    #!{python}
    """Stands in for npm, npx, pnpm, and yarn: logs its call; .pm-exit holds its exit code."""
    import pathlib, sys
    root = pathlib.Path.cwd()
    with open(root / ".pm-calls", "a") as log:
        log.write(" ".join([pathlib.Path(sys.argv[0]).stem, *sys.argv[1:]]) + "\\n")
    sys.exit(int((root / ".pm-exit").read_text()) if (root / ".pm-exit").exists() else 0)
''')

OLD_FIXTURE = ("  screenshot: string | null;\n  error: string | null;\n"
               "          let screenshot: string | null = null;\n"
               "            } catch {\n              screenshot = null;\n            }\n"
               "            screenshot,\n            error: failure ? firstLine(failure) : null,\n")


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

    def e2e(self, *args: str, path: str = TOOLS_PATH):
        # One test per subcommand keeps the subprocess (`qa_subprocess`); the rest run gin-qa in this process.
        return qa_in_process(self.root, self.bin, *args, group="e2e", path=path, through_files=True)

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
        result = qa_subprocess(self.root, self.bin, "init", group="e2e")
        self.assertEqual(0, result.returncode, result.stderr)
        fixture = self.root / "qa/e2e/evidence.ts"
        self.assertIn("result.json", fixture.read_text())
        self.assertIn("npm install -D @playwright/test", result.stdout)
        fixture.write_text("// edited by QA\n")
        write(self.root, "node_modules/@playwright/test/package.json", "{}")
        write(self.root, "package.json", '{"scripts": {"e2e": "playwright test"}}')
        by_hand = ("qa/e2e/evidence.ts has no ariaSnapshot and differs from the template; merge it by hand "
                   "(references/explore-case.md of the e2e skill)\n")
        self.assertEqual((0, by_hand), (self.e2e("init").returncode, self.e2e("init").stdout))
        self.assertEqual("// edited by QA\n", fixture.read_text())
        self.assertEqual(1, (self.root / ".gitignore").read_text().splitlines().count("/qa/evidence/"))

    def test_plan_rejects_a_tc_id_as_the_capability(self):
        result = qa_subprocess(self.root, self.bin, "plan", "TC-AUTH-001", group="e2e")
        self.assertEqual((2, ""), (result.returncode, result.stdout))
        self.assertIn("TC-AUTH-001: a TC-ID, not a capability; pass its capability, for example `auth`",
                      result.stderr)

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
        self.assertEqual(0, qa_subprocess(self.root, self.bin, "pin", "TC-AUTH-001", group="e2e").returncode)
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


    def test_pin_keeps_crlf_line_endings(self):
        spec = self.write_spec(pinned="00000000")
        body = spec.read_text().split("\n", 1)[1].replace("\n", "\r\n")
        spec.write_bytes(f"// TC: TC-AUTH-001@00000000\r\n{body}".encode())
        self.assertEqual(0, self.e2e("pin", "TC-AUTH-001").returncode)
        self.assertEqual(f"// TC: TC-AUTH-001@{self.tc_hash()}\r\n{body}".encode(), spec.read_bytes())
        spec.write_bytes(body.encode())
        self.assertEqual(0, self.e2e("pin", "TC-AUTH-001").returncode)
        self.assertEqual(f"// TC: TC-AUTH-001@{self.tc_hash()}\r\n{body}".encode(), spec.read_bytes())

class TestInitConfig(E2eCase):
    HINT = 'add "e2e": "playwright test" to the package.json scripts'

    def test_writes_the_config_with_the_e2e_folder_and_base_url(self):
        config = self.root / ".agent-workflow/config.yaml"
        config.write_text(config.read_text() + "qa:\n  e2e: tests/e2e\n")
        write(self.root, "package.json", '{"scripts": {"e2e": "playwright test"}}')  # a root Playwright setup
        result = self.e2e("init", "--base-url", "http://127.0.0.1:8080")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("wrote playwright.config.ts (baseURL http://127.0.0.1:8080)", result.stdout)
        text = (self.root / "playwright.config.ts").read_text()
        self.assertIn("testDir: 'tests/e2e'", text)
        self.assertIn("baseURL: process.env.E2E_BASE_URL ?? 'http://127.0.0.1:8080'", text)
        self.assertIn("url: 'http://127.0.0.1:8080'", text)
        self.assertNotIn("__E2E_DIR__", text)
        self.assertNotIn("__BASE_URL__", text)
        self.assertTrue((self.root / "tests/e2e/evidence.ts").is_file())

    def test_default_url_and_the_config_is_never_overwritten(self):
        self.assertEqual(0, self.e2e("init").returncode)
        config = self.root / "qa/e2e/playwright.config.ts"
        self.assertIn("process.env.E2E_BASE_URL ?? 'http://localhost:3000'", config.read_text())
        before = config.read_bytes()
        result = self.e2e("init", "--base-url", "http://example.test")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("qa/e2e/playwright.config.ts exists; --base-url not applied", result.stdout)
        self.assertEqual(before, config.read_bytes())
        self.assertNotIn("not applied", self.e2e("init").stdout)

    def test_an_existing_js_config_is_kept(self):
        write(self.root, "playwright.config.js", "module.exports = {};\n")
        result = self.e2e("init", "--base-url", "http://example.test")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertFalse((self.root / "playwright.config.ts").exists())
        self.assertIn("playwright.config.js exists; --base-url not applied", result.stdout)
        self.assertEqual("module.exports = {};\n", (self.root / "playwright.config.js").read_text())

    def test_bad_base_urls_exit_2_and_write_nothing(self):
        ignore = self.root / ".gitignore"
        for value in ("localhost:3000", "http://x/'", "ftp://x", "http://", "http://x/\\", "http://x/`",
                      "http://x/\n", "http://[::1"):
            with self.subTest(value=value):
                result = self.e2e("init", "--base-url", value)
                self.assertEqual(2, result.returncode)
                self.assertIn("--base-url: expected an http(s) URL, got", result.stderr)
                self.assertFalse((self.root / "playwright.config.ts").exists())
                self.assertFalse((self.root / "qa/e2e/evidence.ts").exists())
                self.assertNotIn("/qa/evidence/", ignore.read_text() if ignore.exists() else "")

    def test_npm_script_hint(self):
        package = self.root / "package.json"
        for body, shown in ((None, True), ('{"scripts": {"test": "x"}}', True), ("{not json", True),
                            ("[]", True), ('{"scripts": {"e2e": "playwright test"}}', False)):
            with self.subTest(body=body):
                if body is None:
                    package.unlink(missing_ok=True)
                else:
                    package.write_text(body)
                result = self.e2e("init")
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual(shown, self.HINT in result.stdout)


class TestE2eFolderConfig(E2eCase):
    def test_equivalent_spellings_of_the_e2e_folder(self):
        config = self.root / ".agent-workflow/config.yaml"
        base = config.read_text()
        self.write_spec()
        for value in ("./qa/e2e", "qa/e2e/", "qa//e2e"):
            with self.subTest(value=value):
                config.write_text(base + f"qa:\n  e2e: {value}\n")
                work = self.run_json("plan")
                self.assertEqual(("qa/e2e", [], []), (work["e2e"], work["missing"], work["stale"]))
                self.assertEqual(0, self.e2e("check").returncode)

    def test_folders_outside_the_repository_are_rejected(self):
        config = self.root / ".agent-workflow/config.yaml"
        base = config.read_text()
        for key, value in (("e2e", "../e2e"), ("cases", "/tmp/cases")):
            with self.subTest(key=key):
                config.write_text(base + f"qa:\n  {key}: {value}\n")
                result = self.e2e("plan")
                self.assertEqual(2, result.returncode)
                self.assertIn(f"qa.{key} must be a path inside the repository", result.stderr)


class TestCheckSpecs(E2eCase):
    def test_clean_and_unaffected_by_requirement_pins(self):
        self.write_spec()
        self.assertEqual((0, "ok\n"), (qa_subprocess(self.root, self.bin, "check", group="e2e").returncode,
                                       self.e2e("check").stdout))
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


class TestRunAndEvidence(E2eCase):
    def setUp(self):
        super().setUp()
        self.npx = self.base / "npx-bin"
        python_stub(self.npx, "npx", FAKE_NPX)
        self.assertEqual(0, self.e2e("init").returncode)
        write(self.root, "node_modules/@playwright/test/package.json", "{}")
        self.write_spec()
        self.pkg = self.root / "qa/e2e"  # a new setup: Playwright runs in the e2e folder

    def run_e2e(self, *args: str):
        return self.e2e("run", *args, "--format", "json", path=os.pathsep.join([str(self.npx), TOOLS_PATH]))

    def test_run_records_the_selection_and_checks_the_evidence(self):
        result = self.run_e2e("TC-AUTH-001")
        self.assertEqual(0, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual((0, []), (payload["playwright_exit"], payload["findings"]))
        self.assertRegex(payload["run"], r"^qa/evidence/\d{4}-\d\d-\d\dT\d\d-\d\d-\d\d$")
        self.assertEqual(["playwright", "test", "auth/tc-auth-001.spec.ts",
                          "--output", str(self.root / payload["run"] / "playwright")],
                         json.loads((self.pkg / ".npx-args").read_text()))
        record = json.loads((self.root / payload["run"] / "run.json").read_text())
        self.assertEqual((["qa/e2e/auth/tc-auth-001.spec.ts"], 0), (record["specs"], record["playwright_exit"]))
        self.assertNotEqual(payload["run"], json.loads(self.run_e2e("auth").stdout)["run"])
        self.assertEqual(0, self.e2e("check", "--run", payload["run"]).returncode)

    def case_lines(self) -> str:
        return self.cases.read_text().split("### TC-AUTH-002")[0]

    def test_run_records_the_result_and_run_folder(self):
        payload = json.loads(self.run_e2e().stdout)
        self.assertEqual([{"tc": "TC-AUTH-001", "result": "passed"}], payload["recorded"])
        self.assertIn(f"Priority: high\nResult: passed\nRun: {payload['run']}\n", self.case_lines())
        self.assertEqual(0, self.e2e("check", "--run", payload["run"]).returncode)

    def test_worst_result_over_projects_and_missing_results(self):
        (self.pkg / ".fake-skip").write_text("TC-AUTH-001")
        payload = json.loads(self.run_e2e().stdout)
        self.assertEqual([{"tc": "TC-AUTH-001", "result": "blocked"}], payload["recorded"])
        (self.pkg / ".fake-skip").unlink()
        folder = json.loads(self.run_e2e().stdout)["run"]
        case_dir = self.root / folder / "tc-auth-001"
        data = json.loads((case_dir / "result.json").read_text())
        for project, status in (("chromium", "passed"), ("mobile", "failed")):
            (case_dir / project).mkdir()
            (case_dir / project / "result.json").write_text(json.dumps({**data, "status": status}))
        for name in ("result.json", "01.png", "01.aria.yml"):
            (case_dir / name).unlink()
        from gin_qa import e2e as e2e_module
        self.assertEqual("failed", e2e_module._outcome(self.root / folder, "TC-AUTH-001"))

    def test_a_taken_folder_moves_to_the_next_suffix(self):
        now = datetime.now(timezone.utc)
        for moment in (now, now + timedelta(seconds=1)):
            (self.root / "qa/evidence" / moment.strftime("%Y-%m-%dT%H-%M-%S")).mkdir(parents=True)
        self.assertRegex(json.loads(self.run_e2e().stdout)["run"], r"^qa/evidence/[0-9T-]+-2$")

    def test_concurrent_runs_keep_separate_complete_evidence(self):
        env = {**os.environ, "PATH": os.pathsep.join([str(self.bin), str(self.npx), TOOLS_PATH])}
        command = [sys.executable, str(QA_LAUNCHER), "e2e", "run", "--format", "json", "--repository", str(self.root)]
        procs = [subprocess.Popen(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
                 for _ in range(3)]
        outputs = [proc.communicate() for proc in procs]
        self.assertEqual([0, 0, 0], [proc.returncode for proc in procs], outputs)
        runs = [json.loads(out)["run"] for out, _ in outputs]
        self.assertEqual(3, len(set(runs)))
        for folder in runs:
            self.assertEqual(0, self.e2e("check", "--run", folder).returncode)

    def test_run_exit_codes(self):
        (self.pkg / ".fake-exit").write_text("1")
        self.assertEqual(1, self.run_e2e().returncode)
        (self.pkg / ".fake-exit").write_text("0")
        (self.pkg / ".fake-skip").write_text("TC-AUTH-001")
        result = self.run_e2e()
        self.assertEqual(1, result.returncode)
        self.assertIn("no result.json", json.loads(result.stdout)["findings"][0])

    def test_run_environment_errors(self):
        cases = [
            ((), "/nonexistent", "npx is not on PATH"),
            (("TC-AUTH-009",), None, "TC-AUTH-009: no e2e spec"),
            (("billing",), None, "billing: no e2e specs under qa/e2e/billing"),
        ]
        for targets, path, message in cases:
            with self.subTest(message=message):
                result = self.e2e("run", *targets, path=path or os.pathsep.join([str(self.npx), TOOLS_PATH]))
                self.assertEqual(2, result.returncode)
                self.assertIn(message, result.stderr)
        (self.root / "node_modules/@playwright/test/package.json").unlink()
        self.assertIn("@playwright/test is not installed", self.run_e2e().stderr)
        (self.root / "qa/e2e/evidence.ts").unlink()
        self.assertIn("run `gin-qa e2e init`", self.run_e2e().stderr)

    def test_check_run_findings(self):
        folder = json.loads(self.run_e2e().stdout)["run"]
        result_file = self.root / folder / "tc-auth-001/result.json"
        data = json.loads(result_file.read_text())
        where = f"{folder}/tc-auth-001/result.json"
        variants = [
            ({**data, "steps": []}, f"{where}: passed without any ev.step; nothing was checked"),
            ({**data, "tc_hash8": "00000000"},
             f"{where}: ran TC-AUTH-001@00000000, but the case is now @{self.tc_hash()}"),
            ({**data, "status": "skipped"}, f"{where}: result.json needs a status of passed or failed and a steps list"),
            ({**data, "tc": "TC-AUTH-003"}, f"{where}: tc is 'TC-AUTH-003', expected TC-AUTH-001"),
        ]
        for content, finding in variants:
            with self.subTest(finding=finding):
                result_file.write_text(json.dumps(content))
                self.assertEqual([finding], self.run_json("check", "--run", folder)["findings"])
        result_file.write_text(json.dumps(data))
        (self.root / folder / "tc-auth-001/01.png").write_bytes(b"")
        (self.root / folder / "tc-auth-001/01.aria.yml").unlink()
        self.assertEqual([f"{where}: step 1 has no screenshot on disk", f"{where}: step 1 has no snapshot on disk"],
                         self.run_json("check", "--run", folder)["findings"])
        (self.root / folder / "tc-auth-001/01.png").write_bytes(b"png")
        for step in ({"snapshot": None, "url": None}, {}):
            with self.subTest(step=step):
                g2_step = {key: value for key, value in data["steps"][0].items() if key not in ("snapshot", "url")}
                result_file.write_text(json.dumps({**data, "steps": [{**g2_step, **step}]}))
                self.assertEqual([], self.run_json("check", "--run", folder)["findings"])
        outside = self.root / "README.md"
        outside.write_text("not evidence")
        for name in (str(outside), "../../../README.md"):
            with self.subTest(screenshot=name):
                step = {**data["steps"][0], "screenshot": name, "snapshot": name}
                result_file.write_text(json.dumps({**data, "steps": [step]}))
                self.assertEqual([f"{where}: step 1 has no screenshot on disk", f"{where}: step 1 has no snapshot on disk"],
                                 self.run_json("check", "--run", folder)["findings"])
                exported = self.run_json("export", "--run", folder)["cases"][0]["results"][0]["steps"][0]
                self.assertEqual((None, None), (exported["screenshot"], exported["snapshot"]))
        result_file.write_text("{")
        self.assertIn("result.json is not valid JSON", self.run_json("check", "--run", folder)["findings"][0])
        for bad in ("qa/cases", "qa/evidence/none"):
            with self.subTest(folder=bad):
                self.assertEqual(2, self.e2e("check", "--run", bad).returncode)
        for record in ("{}", "[]", '{"specs": []}', '{"specs": [1]}'):
            with self.subTest(record=record):
                (self.root / folder / "run.json").write_text(record)
                result = self.e2e("check", "--run", folder)
                self.assertEqual(2, result.returncode)
                self.assertIn("run.json is not a gin-qa run record", result.stderr)

    def test_export_joins_results_with_repository_paths(self):
        folder = json.loads(self.run_e2e().stdout)["run"]
        payload = json.loads(qa_subprocess(self.root, self.bin, "export", "--run", folder, "--format", "json",
                                           group="e2e").stdout)
        self.assertEqual((folder, 0), (payload["run"], payload["playwright_exit"]))
        [row] = payload["cases"]
        self.assertEqual(("TC-AUTH-001", self.tc_hash(), "qa/e2e/auth/tc-auth-001.spec.ts", "passed",
                          f"{folder}/tc-auth-001/01.png", f"{folder}/tc-auth-001/01.aria.yml"),
                         (row["id"], row["hash8"], row["spec"], row["results"][0]["status"],
                          row["results"][0]["steps"][0]["screenshot"], row["results"][0]["steps"][0]["snapshot"]))
        (self.root / folder / "tc-auth-001/result.json").unlink()
        self.assertEqual([], self.run_json("export", "--run", folder)["cases"][0]["results"])

    def test_one_result_per_playwright_project(self):
        folder = json.loads(self.run_e2e().stdout)["run"]
        case_dir = self.root / folder / "tc-auth-001"
        data = json.loads((case_dir / "result.json").read_text())
        for project in ("desktop", "mobile"):
            (case_dir / project).mkdir()
            for name in ("01.png", "01.aria.yml"):
                (case_dir / project / name).write_bytes((case_dir / name).read_bytes())
            (case_dir / project / "result.json").write_text(json.dumps({**data, "project": project}))
        for name in ("result.json", "01.png", "01.aria.yml"):
            (case_dir / name).unlink()
        self.assertEqual([], self.run_json("check", "--run", folder)["findings"])
        results = self.run_json("export", "--run", folder)["cases"][0]["results"]
        self.assertEqual([("desktop", f"{folder}/tc-auth-001/desktop/01.png"),
                          ("mobile", f"{folder}/tc-auth-001/mobile/01.png")],
                         [(r["project"], r["steps"][0]["screenshot"]) for r in results])
        (case_dir / "mobile/01.png").write_bytes(b"")
        self.assertEqual([f"{folder}/tc-auth-001/mobile/result.json: step 1 has no screenshot on disk"],
                         self.run_json("check", "--run", folder)["findings"])
        (case_dir / "01.png").write_bytes(b"png")
        self.assertEqual([f"{folder}/tc-auth-001/result.json: no result.json (the spec did not run, or it does not use "
                          "the evidence fixture)", f"{folder}/tc-auth-001/mobile/result.json: step 1 has no screenshot "
                          "on disk"], self.run_json("check", "--run", folder)["findings"])
        (case_dir / "01.png").unlink()
        (case_dir / "tablet").symlink_to(self.base / "gone", target_is_directory=True)
        self.assertEqual([f"{folder}/tc-auth-001/mobile/result.json: step 1 has no screenshot on disk",
                          f"{folder}/tc-auth-001/tablet: not a folder inside the run"],
                         self.run_json("check", "--run", folder)["findings"])
        self.assertEqual(["desktop", "mobile"], [r["project"] for r in
                                                 self.run_json("export", "--run", folder)["cases"][0]["results"]])
        (case_dir / "tablet").unlink()
        (case_dir / "mobile/01.png").write_bytes(b"png")
        (case_dir / "mobile/result.json").unlink()
        self.assertEqual([f"{folder}/tc-auth-001/mobile/result.json: no result.json (the spec did not run, or it does "
                          "not use the evidence fixture)"], self.run_json("check", "--run", folder)["findings"])
        outside = self.base / "elsewhere"
        (case_dir / "mobile").rename(outside)
        (outside / "result.json").write_text(json.dumps({**data, "project": "mobile"}))
        (case_dir / "mobile").symlink_to(outside, target_is_directory=True)
        self.assertEqual([f"{folder}/tc-auth-001/mobile: not a folder inside the run"],
                         self.run_json("check", "--run", folder)["findings"])
        self.assertEqual(["desktop"], [r["project"] for r in
                                       self.run_json("export", "--run", folder)["cases"][0]["results"]])
        (case_dir / "mobile").unlink()
        case_dir.rename(self.base / "case-elsewhere")
        case_dir.symlink_to(self.base / "case-elsewhere", target_is_directory=True)
        self.assertEqual([f"{folder}/tc-auth-001: not a folder inside the run"],
                         self.run_json("check", "--run", folder)["findings"])



class TestInitInstall(E2eCase):
    def setUp(self):
        super().setUp()
        for name in ("npm", "npx", "pnpm", "yarn"):
            python_stub(self.bin, name, FAKE_MANAGER.format(python=sys.executable))
        write(self.root, "package.json", '{"name": "app"}\n')

    def root_setup(self) -> None:
        """A project with Playwright at the root, which `init --install` keeps using."""
        write(self.root, "playwright.config.js", "module.exports = {};\n")

    def calls(self) -> list[str]:
        log = self.root / ".pm-calls"
        return log.read_text().splitlines() if log.exists() else []

    def test_without_the_flag_nothing_is_installed(self):
        self.assertEqual(0, self.e2e("init").returncode)
        self.assertEqual([], self.calls())

    def test_the_manager_follows_the_lockfile(self):
        self.root_setup()
        for lockfile, expected in (
                (None, ["npm install -D @playwright/test", "npx playwright install chromium"]),
                ("pnpm-lock.yaml", ["pnpm add -D @playwright/test", "pnpm exec playwright install chromium"]),
                ("yarn.lock", ["yarn add -D @playwright/test", "yarn playwright install chromium"])):
            with self.subTest(lockfile=lockfile):
                (self.root / ".pm-calls").unlink(missing_ok=True)
                if lockfile:
                    write(self.root, lockfile, "")
                result = self.e2e("init", "--install")
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual(expected, self.calls())
                (self.root / (lockfile or "none")).unlink(missing_ok=True)

    def test_adds_the_script_and_keeps_the_rest_of_package_json(self):
        self.root_setup()
        self.assertEqual(0, self.e2e("init", "--install").returncode)
        data = json.loads((self.root / "package.json").read_text())
        self.assertEqual({"name": "app", "scripts": {"e2e": "playwright test"}}, data)

    def test_an_installed_package_is_not_installed_again(self):
        self.root_setup()
        write(self.root, "node_modules/@playwright/test/package.json", "{}")
        self.assertEqual(0, self.e2e("init", "--install").returncode)
        self.assertEqual(["npx playwright install chromium"], self.calls())

    def test_a_failed_install_exits_2_and_names_the_commands(self):
        self.root_setup()
        write(self.root, ".pm-exit", "3")
        result = self.e2e("init", "--install")
        self.assertEqual(2, result.returncode)
        self.assertIn("npm install -D @playwright/test", result.stderr)
        self.assertIn("npx playwright install chromium", result.stderr)

    def test_no_package_json_exits_2_and_writes_nothing(self):
        self.root_setup()
        (self.root / "package.json").unlink()
        result = self.e2e("init", "--install")
        self.assertEqual(2, result.returncode)
        self.assertIn("package.json", result.stderr)
        self.assertFalse((self.root / "qa/e2e/evidence.ts").exists())

    def test_a_bad_package_json_exits_2_before_anything_is_installed_or_written(self):
        self.root_setup()
        for text in ("{not json", "[]", '{"scripts": []}'):
            with self.subTest(text=text):
                write(self.root, "package.json", text)
                result = self.e2e("init", "--install")
                self.assertEqual(2, result.returncode)
                self.assertIn("package.json", result.stderr)
                self.assertEqual([], self.calls())
                self.assertEqual(text, (self.root / "package.json").read_text())
                for name in ("qa/e2e/evidence.ts", "playwright.config.ts", ".gitignore"):
                    self.assertFalse((self.root / name).exists(), name)


class TestSnapshotMerge(E2eCase):
    def test_an_older_fixture_matching_the_anchors_is_merged(self):
        path = write(self.root, "qa/e2e/evidence.ts", OLD_FIXTURE)
        result = self.e2e("init")
        self.assertEqual(0, result.returncode, result.stderr)
        text = path.read_text()
        for needle in ("  snapshot: string | null;\n  url: string;\n", "let snapshot: string | null = null;",
                       "ariaSnapshot({ timeout: 5000 })", "snapshot,\n            url: page.url(),"):
            self.assertIn(needle, text)
        self.assertIn("merged", result.stdout)

    def test_an_edited_fixture_stays_unchanged_and_names_the_manual_steps(self):
        path = write(self.root, "qa/e2e/evidence.ts", "// my own fixture\n")
        result = self.e2e("init")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("// my own fixture\n", path.read_text())
        self.assertIn("explore-case.md", result.stdout)

    def test_a_current_fixture_is_left_alone(self):
        self.assertEqual(0, self.e2e("init").returncode)
        path = self.root / "qa/e2e/evidence.ts"
        before = path.read_text()
        self.assertNotIn("merged", self.e2e("init").stdout)
        self.assertEqual(before, path.read_text())


if __name__ == "__main__":
    unittest.main()
