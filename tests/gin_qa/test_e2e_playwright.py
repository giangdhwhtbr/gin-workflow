"""`gin-qa e2e run` with real Playwright and the evidence fixture against a static page.

Runs only when GIN_QA_PLAYWRIGHT_NODE_MODULES names a node_modules folder holding @playwright/test with its
browsers installed (`npm install @playwright/test && npx playwright install chromium`); skipped otherwise.
"""

from __future__ import annotations

import functools
import http.server
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from qa_fixtures import AUTH_SPEC, case, cases_file, gin_workflow_bin, make_repo, qa, write  # noqa: E402

NODE_MODULES = os.environ.get("GIN_QA_PLAYWRIGHT_NODE_MODULES", "")

PAGE = """<!doctype html><title>Login</title>
<label>Email <input name="email"></label>
<button onclick="document.querySelector('h1').hidden = false">Sign in</button>
<h1 hidden>Dashboard</h1>
"""

SPEC = """// TC: TC-AUTH-001@{pinned}
import {{ test, expect }} from '../evidence';

test('TC-AUTH-001: Sign in', async ({{ page, ev }}) => {{
  await ev.step('1. Open /login', async () => {{
    await page.goto('/login.html');
  }});
  await ev.step('2. Click "Sign in"', async () => {{
    await page.getByRole('button', {{ name: 'Sign in' }}).click();
    await expect(page.getByRole('heading', {{ name: '{heading}' }})).toBeVisible({{ timeout: 2000 }});
  }});
}});
"""


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args) -> None:
        pass


@unittest.skipUnless(NODE_MODULES and Path(NODE_MODULES, "@playwright/test").is_dir() and shutil.which("npx"),
                     "set GIN_QA_PLAYWRIGHT_NODE_MODULES to a node_modules with @playwright/test")
class TestPlaywrightRun(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.bin = gin_workflow_bin(base)
        self.root = make_repo(base / "repo")
        write(self.root, "docs/specs/auth/spec.md", AUTH_SPEC)
        write(self.root, "site/login.html", PAGE)
        write(self.root, "qa/cases/auth.md", cases_file("auth", case("TC-AUTH-001", "REQ: REQ-AUTH-001@00000000")))
        (self.root / "node_modules").symlink_to(Path(NODE_MODULES).resolve())
        handler = functools.partial(QuietHandler, directory=str(self.root / "site"))
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        write(self.root, "playwright.config.ts",
              "import { defineConfig } from '@playwright/test';\n"
              f"export default defineConfig({{ reporter: 'line', use: {{ baseURL: "
              f"'http://127.0.0.1:{self.server.server_address[1]}' }} }});\n")
        self.assertEqual(0, self.e2e("init").returncode)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def e2e(self, *args: str):
        return qa(self.root, self.bin, *args, group="e2e", path=os.environ.get("PATH", "/usr/bin:/bin"))

    def url(self, page: str) -> str:
        return f"http://127.0.0.1:{self.server.server_address[1]}{page}"

    def write_spec(self, heading: str) -> None:
        write(self.root, "qa/e2e/auth/tc-auth-001.spec.ts", SPEC.format(pinned="00000000", heading=heading))
        self.assertEqual(0, self.e2e("pin", "TC-AUTH-001").returncode)

    def run_once(self) -> tuple[int, dict]:
        result = self.e2e("run", "--format", "json")
        return result.returncode, json.loads(result.stdout)

    def test_passing_run_leaves_checked_evidence(self):
        self.write_spec("Dashboard")
        code, payload = self.run_once()
        self.assertEqual((0, 0, []), (code, payload["playwright_exit"], payload["findings"]))
        evidence = self.root / payload["run"] / "tc-auth-001"
        result = json.loads((evidence / "result.json").read_text())
        self.assertEqual(("passed", None, ["passed", "passed"], ["01.png", "02.png"]),
                         (result["status"], result["error"], [s["status"] for s in result["steps"]],
                          [s["screenshot"] for s in result["steps"]]))
        self.assertTrue(all((evidence / name).stat().st_size > 1000 for name in ("01.png", "02.png")))
        self.assertEqual((["01.aria.yml", "02.aria.yml"], [self.url("/login.html")] * 2),
                         ([s["snapshot"] for s in result["steps"]], [s["url"] for s in result["steps"]]))
        self.assertIn('button "Sign in"', (evidence / "01.aria.yml").read_text())
        self.assertIn('heading "Dashboard"', (evidence / "02.aria.yml").read_text())
        self.assertEqual(0, self.e2e("check", "--run", payload["run"]).returncode)

    def test_failing_step_is_recorded_with_its_screenshot(self):
        self.write_spec("Settings")
        code, payload = self.run_once()
        self.assertEqual((1, 1, []), (code, payload["playwright_exit"], payload["findings"]))
        result = json.loads((self.root / payload["run"] / "tc-auth-001/result.json").read_text())
        self.assertEqual(("failed", ["passed", "failed"], "02.png"),
                         (result["status"], [s["status"] for s in result["steps"]], result["steps"][1]["screenshot"]))
        self.assertIn("expect(locator).toBeVisible()", result["steps"][1]["error"])
        self.assertEqual("02.aria.yml", result["steps"][1]["snapshot"])
        self.assertIn('button "Sign in"', (self.root / payload["run"] / "tc-auth-001/02.aria.yml").read_text())
        self.assertNotIn("\x1b", result["steps"][1]["error"])


if __name__ == "__main__":
    unittest.main()
