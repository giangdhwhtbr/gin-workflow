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
        # overall health also depends on the host's executables (the harness CLI on PATH), so check the parts
        self.assertTrue(doctor["checks"]["configuration"])
        self.assertIn("workspace: clone apps/web: gin workspace clone apps/web", doctor["actions"])
        self.assertIn("workspace: apps/web has no verify.checks", doctor["actions"])
        self.assertFalse(doctor["checks_details"]["workspace"]["repos"]["apps/web"]["present"])

    def _doctor_actions(self):
        return json.loads(run(self.root, "setup", "doctor", "--format", "json").stdout)["actions"]

    def _init(self, *extra):
        return run(self.root, "setup", "init", "--harness", "claude", "--approve", "--format", "json", *extra)

    def test_doctor_submodule_matches_path_exactly(self):
        self._init()
        message = ("workspace: services/api is still a submodule in .gitmodules; remove it "
                   "(git submodule deinit -f services/api; git rm -f services/api)")
        modules = self.root / ".gitmodules"
        modules.write_text('[submodule "x"]\n\tpath = services/api-legacy\n', encoding="utf-8")
        self.assertNotIn(message, self._doctor_actions())
        modules.write_text('[submodule "x"]\n\tpath = services/api\n', encoding="utf-8")
        self.assertIn(message, self._doctor_actions())
        modules.write_text('[submodule "x"]\n\tpath=services/api  \n', encoding="utf-8")
        self.assertIn(message, self._doctor_actions())

    def test_doctor_gitignore_action_clears_after_clone(self):
        self._init()
        message = "workspace: apps/web is not in .gitignore; gin workspace clone adds it"
        self.assertIn(message, self._doctor_actions())
        run(self.root, "workspace", "clone", "apps/web")
        self.assertNotIn(message, self._doctor_actions())

    def test_doctor_reports_the_hooks_of_each_cloned_child(self):
        self._init()
        run(self.root, "workspace", "clone", "services/api")
        missing = "workspace: services/api: pre-commit is missing; run gin hooks install --all-repos"
        self.assertIn(missing, self._doctor_actions())
        hook = self.root / "services/api/.git/hooks/pre-commit"
        hook.write_text("#!/bin/sh\nnpx lint-staged\n", encoding="utf-8")
        run(self.root, "hooks", "install", "--all-repos")
        doctor = json.loads(run(self.root, "setup", "doctor", "--format", "json").stdout)
        self.assertNotIn(missing, doctor["actions"])
        self.assertIn("workspace: services/api: pre-commit is occupied; chain "
                      f'`exec gin hooks run pre-commit "$@"` into {hook}', doctor["actions"])
        self.assertEqual({"pre-commit": "occupied", "pre-push": "ok"},
                         doctor["checks_details"]["workspace"]["repos"]["services/api"]["hooks"])
        self.assertNotIn("hooks", doctor["checks_details"]["workspace"]["repos"]["apps/web"])

    def test_doctor_reports_a_broken_clone_instead_of_crashing(self):
        self._init()
        broken = self.root / "services/api"
        broken.mkdir(parents=True)
        (broken / ".git").write_text("gitdir: /nonexistent/api.git\n", encoding="utf-8")
        actions = self._doctor_actions()
        self.assertIn("workspace: services/api: is not a readable git repository", actions)

    def test_doctor_asks_for_checks_on_backend_frontend_and_qa_only(self):
        self._init()
        message = "workspace: apps/web has no verify.checks"
        self.assertIn(message, self._doctor_actions())
        config = self.root / ".agent-workflow/config.yaml"
        config.write_text(config.read_text(encoding="utf-8").replace("shape: frontend", "shape: library"),
                          encoding="utf-8")
        self.assertNotIn(message, self._doctor_actions())

    def test_help_describes_clone_and_status(self):
        top = run(self.root, "workspace", "--help")
        self.assertEqual(0, top.returncode, top.stderr)
        self.assertIn("clone the named entries, or every entry with --all", top.stdout)
        self.assertIn("one line per entry", top.stdout)
        clone = run(self.root, "workspace", "clone", "--help").stdout
        self.assertIn("every entry of workspace.repos", clone)
        self.assertIn("a directory inside the workspace", clone)
        self.assertIn("print JSON", clone)

    def test_init_workspace_gitignore_header_once_and_idempotent(self):
        header = "# workspace repos (gin workspace clone adds one line per repository)"
        fresh = init_repo(self.base / "fresh")
        for _ in range(2):
            done = run(fresh, "setup", "init", "--harness", "claude", "--approve", "--workspace", "--format", "json")
            self.assertEqual(0, done.returncode, done.stderr)
            lines = (fresh / ".gitignore").read_text().splitlines()
            self.assertEqual(1, lines.count(header))
            self.assertEqual(1, lines.count("/.beads"))
            self.assertEqual(1, lines.count(".planning/worktrees/"))

    def test_ensure_gitignore_without_trailing_newline(self):
        from workflow_core.workspace import GITIGNORE_HEADER, ensure_gitignore
        (self.root / ".gitignore").write_text("node_modules", encoding="utf-8")
        self.assertEqual(["/apps/web"], ensure_gitignore(self.root, ["/apps/web"]))
        self.assertEqual(["node_modules", "", GITIGNORE_HEADER, "/apps/web"],
                         (self.root / ".gitignore").read_text().splitlines())

    def test_partial_clone_failure_keeps_gitignore_in_step(self):
        config = self.root / ".agent-workflow/config.yaml"
        config.write_text(config.read_text().replace(f"file://{self.base / 'remotes/apps/web'}",
                                                     f"file://{self.base / 'remotes/missing'}"), encoding="utf-8")
        done = run(self.root, "workspace", "clone", "services/api", "apps/web")
        self.assertEqual(1, done.returncode)
        self.assertIn("apps/web:", done.stderr)
        self.assertIn("(cloned so far: services/api)", done.stderr)
        lines = (self.root / ".gitignore").read_text().splitlines()
        self.assertIn("/services/api", lines)
        self.assertNotIn("/apps/web", lines)


if __name__ == "__main__":
    unittest.main()
