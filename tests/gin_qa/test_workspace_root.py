"""gin-qa in a workspace and with `qa.dir`: the files root, the QA home defaults, and the Playwright folder
(gin-workflow-qa-workspace R2-R6, US-1 to US-3)."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "plugins/gin-qa/src/scripts"))

from test_e2e_cli import FAKE_NPX, spec_text  # noqa: E402
from qa_fixtures import (AUTH_SPEC, TOOLS_PATH, case, case_file, cases_file, commit_all, gin_workflow_bin,  # noqa: E402
                         make_repo, make_workspace_qa, python_stub, qa, write)
from qa_fixtures import LAUNCHER as GIN_LAUNCHER  # noqa: E402
from gin_qa.cases import hash8, parse_file  # noqa: E402

# A `gin` from before `root` was reported: its `specs reqs` payload has no `root`.
OLD_GIN = '#!/bin/sh\necho \'{"layout": "sdd", "requirements": [], "qa": {}}\'\n'

# The real `gin` with `qa.dir` added to the `specs reqs` payload: the config schema does not know `qa.dir` yet, so
# these tests exercise gin-qa's reading of the payload, not the core's validation.
QA_DIR_GIN = '''#!{python}
import json, subprocess, sys
done = subprocess.run([sys.executable, {launcher!r}, *sys.argv[1:]], capture_output=True, text=True)
if sys.argv[1:3] == ["specs", "reqs"] and done.returncode == 0:
    payload = json.loads(done.stdout)
    payload["qa"] = {{**(payload.get("qa") or {{}}), "dir": {qa_dir!r}}}
    print(json.dumps(payload))
else:
    sys.stdout.write(done.stdout)
    sys.stderr.write(done.stderr)
sys.exit(done.returncode)
'''


class TestQaWorkspaceRoot(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name).resolve()
        self.bin = gin_workflow_bin(self.base)

    def tearDown(self):
        self.tmp.cleanup()

    def workspace(self) -> tuple[Path, Path]:
        parent, child = make_workspace_qa(self.base)
        write(parent, "docs/specs/auth/spec.md", AUTH_SPEC)
        write(child, "cases/auth/TC-AUTH-001-sign-in.md", case_file("TC-AUTH-001", "REQ: REQ-AUTH-001@00000000"))
        commit_all(child, "case")
        return parent, child

    def single(self) -> Path:
        root = make_repo(self.base / "repo")
        write(root, "docs/specs/auth/spec.md", AUTH_SPEC)
        return root

    def gin_with_qa_dir(self, qa_dir: str) -> Path:
        body = QA_DIR_GIN.format(python=sys.executable, launcher=str(GIN_LAUNCHER), qa_dir=qa_dir)
        return python_stub(self.base / "dirbin", "gin", body).parent

    def test_next_id_from_the_child_uses_child_history(self):
        parent, child = self.workspace()
        before = sorted(path.name for path in parent.iterdir())
        result = qa(None, self.bin, "next-id", "auth", cwd=child)
        self.assertEqual((0, "TC-AUTH-002\n"), (result.returncode, result.stdout), result.stderr)
        self.assertEqual(before, sorted(path.name for path in parent.iterdir()))

    def test_next_id_from_a_child_worktree(self):
        _, child = self.workspace()
        linked = self.base / "linked"
        subprocess.run(["git", "worktree", "add", "-q", "-b", "t", str(linked)], cwd=child, check=True)
        write(linked, "cases/auth/TC-AUTH-002-sign-out.md", case_file("TC-AUTH-002", "REQ: REQ-AUTH-001@00000000"))
        result = qa(None, self.bin, "next-id", "auth", cwd=linked)
        self.assertEqual((0, "TC-AUTH-003\n"), (result.returncode, result.stdout), result.stderr)

    def test_e2e_init_writes_into_the_child_e2e_folder(self):
        parent, child = self.workspace()
        names = ("playwright.config.ts", "package.json", ".gitignore")
        before = {name: (parent / name).exists() for name in names}
        result = qa(None, self.bin, "init", "--base-url", "http://localhost:3000", group="e2e", cwd=child)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("testDir: '.'", (child / "e2e/playwright.config.ts").read_text())
        self.assertTrue((child / "e2e/evidence.ts").is_file())
        self.assertIn("/evidence/", (child / ".gitignore").read_text().splitlines())
        self.assertEqual(before, {name: (parent / name).exists() for name in names})

    def test_single_repo_qa_dir(self):
        root, bin_dir = self.single(), self.gin_with_qa_dir("new-app/testing")
        written = qa(root, bin_dir, "new", "auth", "--type", "manual", "--title", "Sign in", "--req",
                     "REQ-AUTH-001", "--format", "json")
        self.assertEqual(0, written.returncode, written.stderr)
        self.assertTrue(json.loads(written.stdout)["file"].startswith("new-app/testing/cases/"))
        result = qa(root, bin_dir, "init", group="e2e")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("testDir: '.'", (root / "new-app/testing/e2e/playwright.config.ts").read_text())
        self.assertFalse((root / "playwright.config.ts").exists() or (root / "qa").exists())
        self.assertIn("/new-app/testing/evidence/", (root / ".gitignore").read_text().splitlines())

    def test_qa_dir_outside_is_refused(self):
        root = self.single()
        result = qa(root, self.gin_with_qa_dir("../x"), "next-id", "auth")
        self.assertEqual(2, result.returncode)
        self.assertIn("must be a path inside the repository", result.stderr)

    def test_root_playwright_kept(self):
        root = self.single()
        write(root, "playwright.config.ts", "export default {};\n")
        write(root, "node_modules/@playwright/test/package.json", "{}")
        cases = write(root, "qa/cases/auth.md", cases_file("auth", case("TC-AUTH-001", "REQ: REQ-AUTH-001@00000000")))
        self.assertEqual(0, qa(root, self.bin, "init", group="e2e").returncode)
        self.assertFalse((root / "qa/e2e/playwright.config.ts").exists())
        pinned = hash8(parse_file(cases, "qa/cases/auth.md")[0][0])
        write(root, "qa/e2e/auth/tc-auth-001.spec.ts", spec_text("TC-AUTH-001", pinned))
        npx = self.base / "npx-bin"
        python_stub(npx, "npx", FAKE_NPX)
        result = qa(root, self.bin, "run", "--format", "json", group="e2e",
                    path=os.pathsep.join([str(npx), TOOLS_PATH]))
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(["playwright", "test", "qa/e2e/auth/tc-auth-001.spec.ts", "--output",
                          f"{json.loads(result.stdout)['run']}/playwright"],
                         json.loads((root / ".npx-args").read_text()))

    def test_e2e_run_from_the_child_runs_playwright_in_its_e2e_folder(self):
        _, child = self.workspace()
        cases = write(child, "cases/auth.md", cases_file("auth", case("TC-AUTH-002", "REQ: REQ-AUTH-001@00000000")))
        self.assertEqual(0, qa(None, self.bin, "init", group="e2e", cwd=child).returncode)
        write(child, "e2e/node_modules/@playwright/test/package.json", "{}")
        pinned = hash8(parse_file(cases, "cases/auth.md")[0][0])
        write(child, "e2e/auth/tc-auth-002.spec.ts", spec_text("TC-AUTH-002", pinned))
        npx = self.base / "npx-bin"
        python_stub(npx, "npx", FAKE_NPX)
        result = qa(None, self.bin, "run", "--format", "json", group="e2e", cwd=child,
                    path=os.pathsep.join([str(npx), TOOLS_PATH]))
        self.assertEqual(0, result.returncode, result.stderr)
        run = json.loads(result.stdout)["run"]
        self.assertRegex(run, r"^evidence/\d{4}-")
        self.assertEqual(["playwright", "test", "auth/tc-auth-002.spec.ts", "--output",
                          str(child / run / "playwright")], json.loads((child / "e2e/.npx-args").read_text()))

    def test_old_gin_is_refused(self):
        root = self.single()
        result = qa(root, gin_workflow_bin(self.base / "old", OLD_GIN), "next-id", "auth")
        self.assertEqual(2, result.returncode)
        self.assertIn("this gin is too old for gin-qa", result.stderr)

    def test_a_qa_child_that_is_not_cloned_is_refused(self):
        parent, _ = make_workspace_qa(self.base / "missing", clone=False)
        result = qa(None, self.bin, "next-id", "auth", cwd=parent)
        self.assertEqual(2, result.returncode)
        self.assertIn("gin workspace clone qa", result.stderr)


if __name__ == "__main__":
    unittest.main()
