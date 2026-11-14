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

    def test_clone_installs_verify_hooks(self):
        # R2, US-2: clone installs pre-commit and pre-push when entry has verify.checks
        done = run(self.root, "workspace", "clone", "services/api", "--json")
        self.assertEqual(0, done.returncode, done.stderr)
        data = json.loads(done.stdout)
        row = data["repos"][0]
        self.assertEqual("services/api", row["path"])
        self.assertEqual("cloned", row["status"])
        self.assertEqual({"pre-commit": "installed", "pre-push": "installed"}, row.get("hooks"))
        self.assertTrue((self.root / "services/api/.git/hooks/pre-commit").exists())

    def test_clone_without_checks_installs_no_verify_hooks(self):
        # R2, US-2: clone without checks gives no pre-commit key
        done = run(self.root, "workspace", "clone", "apps/web", "--json")
        self.assertEqual(0, done.returncode, done.stderr)
        data = json.loads(done.stdout)
        row = data["repos"][0]
        self.assertEqual("apps/web", row["path"])
        self.assertEqual("cloned", row["status"])
        self.assertNotIn("pre-commit", row.get("hooks", {}))

    def test_clone_frozen_and_beads_and_present_have_no_hooks_key(self):
        # R2, US-2: frozen, beads and present clones have no hooks key
        done = run(self.root, "workspace", "clone", "--all", "--json")
        self.assertEqual(0, done.returncode, done.stderr)
        cloned = {item["path"]: item for item in json.loads(done.stdout)["repos"]}
        self.assertNotIn("hooks", cloned["legacy/portal"])
        self.assertNotIn("hooks", cloned[".beads"])
        again = json.loads(run(self.root, "workspace", "clone", "--all", "--json").stdout)
        for item in again["repos"]:
            self.assertEqual("present", item["status"])
            self.assertNotIn("hooks", item)

    def test_clone_team_commit_msg_hook(self):
        # R2, US-2: in team mode, child with .githooks/commit-msg gets commit-msg installed
        from tests.workflow_core.team_fixtures import TEAM
        config_path = self.root / ".agent-workflow/config.yaml"
        config_path.write_text(config_path.read_text(encoding="utf-8") + "\n" + TEAM.format(host="github"), encoding="utf-8")
        scratch = self.base / "scratch/services/api"
        githooks = scratch / ".githooks"
        githooks.mkdir(parents=True, exist_ok=True)
        (githooks / "commit-msg").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        git(scratch, "add", ".githooks/commit-msg")
        git(scratch, "commit", "-q", "-m", "add commit-msg hook")
        git(scratch, "push", "-q", str(self.base / "remotes/services/api"), "main")
        done = run(self.root, "workspace", "clone", "services/api", "--json")
        self.assertEqual(0, done.returncode, done.stderr)
        data = json.loads(done.stdout)
        row = data["repos"][0]
        self.assertEqual("installed", row.get("hooks", {}).get("commit-msg"))

    def test_clone_occupied_hook_reports_status_and_chain_line(self):
        # R2, US-2: occupied hook reports occupied, prints chain line to stderr, exits 0
        template = self.base / "git-template"
        hooks_dir = template / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)
        (hooks_dir / "pre-commit").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        done = run(self.root, "workspace", "clone", "services/api", "--json", env={"GIT_TEMPLATE_DIR": str(template)})
        self.assertEqual(0, done.returncode)
        row = json.loads(done.stdout)["repos"][0]
        self.assertEqual("occupied", row.get("hooks", {}).get("pre-commit"))
        self.assertIn('add `exec gin hooks run pre-commit "$@"` to ', done.stderr)
        self.assertIn("to chain it", done.stderr)

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
        (self.root / "services/api/.git/hooks/pre-commit").unlink()
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

    def test_add_duplicate_refused(self):
        before = (self.root / ".agent-workflow/config.yaml").read_bytes()
        done = run(self.root, "workspace", "add", "services/api", "--url", "file:///x", "--shape", "backend")
        self.assertEqual(1, done.returncode)
        self.assertIn("duplicate path", done.stderr)
        self.assertEqual(before, (self.root / ".agent-workflow/config.yaml").read_bytes())


class WorkspaceAddTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.base = Path(directory.name).resolve()
        self.root = init_repo(self.base / "ws")
        (self.root / ".agent-workflow").mkdir()
        (self.root / ".agent-workflow/config.yaml").write_text(
            "schema_version: '2.9'\nharness: claude\nworkspace:\n  repos: []\n", encoding="utf-8"
        )

    def test_add_success_and_status(self):
        done = run(self.root, "workspace", "add", "services/order-api", "--url", "file:///x",
                   "--shape", "backend", "--check", "test=true")
        self.assertEqual(0, done.returncode, done.stderr)
        self.assertIn("added services/order-api; next: gin workspace clone services/order-api", done.stdout)
        status = json.loads(run(self.root, "workspace", "status", "--json").stdout)
        entry = next((item for item in status["repos"] if item["path"] == "services/order-api"), None)
        self.assertIsNotNone(entry)
        self.assertFalse(entry["present"])
        from workflow_core import workspace as ws
        yaml = ws.require_yaml()
        config = yaml.safe_load((self.root / ".agent-workflow/config.yaml").read_text(encoding="utf-8"))
        saved = next(item for item in config["workspace"]["repos"] if item["path"] == "services/order-api")
        self.assertEqual({"checks": {"test": "true"}}, saved.get("verify"))

    def test_add_frozen_without_shape_accepted(self):
        done = run(self.root, "workspace", "add", "legacy/portal", "--url", "file:///x", "--frozen")
        self.assertEqual(0, done.returncode, done.stderr)
        from workflow_core import workspace as ws
        yaml = ws.require_yaml()
        config = yaml.safe_load((self.root / ".agent-workflow/config.yaml").read_text(encoding="utf-8"))
        saved = next(item for item in config["workspace"]["repos"] if item["path"] == "legacy/portal")
        self.assertTrue(saved.get("frozen"))
        self.assertNotIn("shape", saved)

    def test_add_invalid_shape_refused(self):
        before = (self.root / ".agent-workflow/config.yaml").read_bytes()
        done = run(self.root, "workspace", "add", "services/order-api", "--url", "file:///x", "--shape", "web")
        self.assertEqual(1, done.returncode)
        self.assertEqual(before, (self.root / ".agent-workflow/config.yaml").read_bytes())

    def test_add_invalid_check_refused(self):
        before = (self.root / ".agent-workflow/config.yaml").read_bytes()
        done = run(self.root, "workspace", "add", "services/order-api", "--url", "file:///x",
                   "--shape", "backend", "--check", "test")
        self.assertEqual(1, done.returncode)
        self.assertIn("--check must be NAME=COMMAND", done.stderr)
        self.assertEqual(before, (self.root / ".agent-workflow/config.yaml").read_bytes())

    def test_add_outside_workspace_parent_refused(self):
        no_ws = init_repo(self.base / "no_ws")
        (no_ws / ".agent-workflow").mkdir()
        (no_ws / ".agent-workflow/config.yaml").write_text(
            "schema_version: '2.9'\nharness: claude\n", encoding="utf-8"
        )
        before = (no_ws / ".agent-workflow/config.yaml").read_bytes()
        done = run(no_ws, "workspace", "add", "services/order-api", "--url", "file:///x", "--shape", "backend")
        self.assertEqual(1, done.returncode)
        self.assertIn("run /gin:setup and answer workspace", done.stderr)
        self.assertEqual(before, (no_ws / ".agent-workflow/config.yaml").read_bytes())

    def test_add_check_with_embedded_equals(self):
        done = run(self.root, "workspace", "add", "services/order-api", "--url", "file:///x",
                   "--shape", "backend", "--check", "test=FOO=1 make t")
        self.assertEqual(0, done.returncode, done.stderr)
        from workflow_core import workspace as ws
        yaml = ws.require_yaml()
        config = yaml.safe_load((self.root / ".agent-workflow/config.yaml").read_text(encoding="utf-8"))
        saved = next(item for item in config["workspace"]["repos"] if item["path"] == "services/order-api")
        self.assertEqual({"checks": {"test": "FOO=1 make t"}}, saved.get("verify"))

    def test_add_config_validation_error_reports_clean_error(self):
        config_path = self.root / ".agent-workflow/config.yaml"
        config_path.write_text(
            "schema_version: '2.9'\nharness: claude\nworkspace:\n  repos:\n"
            "    - path: services/api\n      url: file:///x\n      shape: backend\n      extra_key: 1\n",
            encoding="utf-8",
        )
        before = config_path.read_bytes()
        done = run(self.root, "workspace", "add", "apps/new", "--url", "file:///x", "--shape", "backend")
        self.assertEqual(1, done.returncode)
        self.assertTrue(done.stderr.startswith("error:"), f"stderr does not start with error: {done.stderr}")
        self.assertNotIn("Traceback", done.stderr)
        self.assertEqual(before, config_path.read_bytes())

    def test_add_preserves_existing_frozen_and_verify_checks(self):
        config_path = self.root / ".agent-workflow/config.yaml"
        config_path.write_text(
            "schema_version: '2.9'\nharness: claude\nworkspace:\n  repos:\n"
            "    - path: legacy/portal\n      url: file:///legacy\n      frozen: true\n"
            "    - path: services/api\n      url: file:///api\n      shape: backend\n"
            "      verify:\n        checks:\n          test: 'true'\n",
            encoding="utf-8",
        )
        done = run(self.root, "workspace", "add", "apps/web", "--url", "file:///web", "--shape", "frontend")
        self.assertEqual(0, done.returncode, done.stderr)
        from workflow_core import workspace as ws
        yaml = ws.require_yaml()
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        saved = {repo["path"]: repo for repo in config["workspace"]["repos"]}
        self.assertEqual(True, saved["legacy/portal"].get("frozen"))
        self.assertEqual({"checks": {"test": "true"}}, saved["services/api"].get("verify"))

    def test_add_help_describes_flags(self):
        done = run(self.root, "workspace", "add", "--help")
        self.assertEqual(0, done.returncode, done.stderr)
        self.assertIn("--url", done.stdout)
        self.assertIn("--shape", done.stdout)
        self.assertIn("--frozen", done.stdout)
        self.assertIn("--default-branch", done.stdout)
        self.assertIn("--check", done.stdout)


if __name__ == "__main__":
    unittest.main()

