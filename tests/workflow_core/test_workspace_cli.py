"""gin workspace clone/status, setup --workspace and the doctor findings."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"))

from tests.workflow_core.test_workspace import git, init_repo  # noqa: E402
from tests.workflow_core.test_workspace_cli_resolution import run  # noqa: E402

REPOS = (("services/api", "shape: backend\n      verify: {checks: {test: \"true\"}}"),
         ("apps/web", "shape: frontend"),
         ("legacy/portal", "frozen: true"),
         (".beads", "shape: beads"))


class WorkspaceCliTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.base = Path(directory.name).resolve()
        entries = []
        for path, extra in REPOS:
            bare = self.base / "remotes" / path
            bare.mkdir(parents=True)
            git(bare, "init", "-q", "--bare", "-b", "main")
            scratch = init_repo(self.base / "scratch" / path)
            git(scratch, "push", "-q", str(bare), "main")
            entries.append(f"    - path: {path}\n      url: file://{bare}\n      default_branch: main\n"
                           f"      {extra}\n")
        self.root = init_repo(self.base / "ws")
        (self.root / ".agent-workflow").mkdir()
        (self.root / ".agent-workflow/config.yaml").write_text(
            "schema_version: '2.9'\nharness: claude\nworkspace:\n  repos:\n" + "".join(entries), encoding="utf-8")

    def test_clone_all_then_status(self):
        done = run(self.root, "workspace", "clone", "--all", "--json")
        self.assertEqual(0, done.returncode, done.stderr)
        cloned = {item["path"]: item for item in json.loads(done.stdout)["repos"]}
        self.assertEqual({"services/api", "apps/web", "legacy/portal", ".beads"}, set(cloned))
        self.assertTrue(all(item["status"] == "cloned" for item in cloned.values()))
        self.assertEqual("true", git(self.root / "legacy/portal", "rev-parse", "--is-shallow-repository"))
        ignore = (self.root / ".gitignore").read_text()
        for path in cloned:
            self.assertIn(f"\n/{path}\n", ignore)
        again = json.loads(run(self.root, "workspace", "clone", "--all", "--json").stdout)
        self.assertTrue(all(item["status"] == "present" for item in again["repos"]))
        status = json.loads(run(self.root / "services/api", "workspace", "status", "--json").stdout)
        api = next(item for item in status["repos"] if item["path"] == "services/api")
        self.assertEqual({"path": "services/api", "present": True, "branch": "main", "dirty": False,
                          "frozen": False}, api)
        text = run(self.root, "workspace", "status").stdout
        self.assertIn("legacy/portal  present  main  clean  frozen", text)

    def test_clone_one_and_outside_workspace(self):
        done = run(self.root, "workspace", "clone", "services/api")
        self.assertEqual(0, done.returncode, done.stderr)
        self.assertTrue((self.root / "services/api/.git").exists())
        self.assertFalse((self.root / "apps/web").exists())
        plain = self.base / "plain"
        plain.mkdir()
        done = run(plain, "workspace", "status")
        self.assertEqual(1, done.returncode)
        self.assertIn(f"not in a workspace: {plain}", done.stderr)
        done = run(self.root, "workspace", "clone", "nope")
        self.assertEqual(1, done.returncode)
        self.assertIn("not in workspace.repos: nope", done.stderr)

    def test_setup_workspace_flag_and_doctor(self):
        preset = json.loads(run(self.root, "setup", "preset", "--project-stage", "brownfield", "--project-shape",
                                "backend", "--rigor", "standard", "--task-tracking", "markdown", "--workspace",
                                "--format", "json").stdout)
        self.assertIn("workspace.repos=[]", preset["assignments"])
        run(self.root, "workspace", "clone", "services/api")
        run(self.root, "setup", "init", "--harness", "claude", "--approve", "--format", "json")
        doctor = json.loads(run(self.root, "setup", "doctor", "--format", "json").stdout)
        self.assertEqual("healthy", doctor["status"])
        self.assertIn("workspace: clone apps/web: gin workspace clone apps/web", doctor["actions"])
        self.assertIn("workspace: apps/web has no verify.checks", doctor["actions"])
        self.assertFalse(doctor["checks_details"]["workspace"]["repos"]["apps/web"]["present"])


if __name__ == "__main__":
    unittest.main()
