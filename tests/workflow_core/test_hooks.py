"""`gin-workflow hooks install|run`: shims, idempotence, first-failure stop, push filtering."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core import hooks, setup_service  # noqa: E402

CONFIG = """schema_version: "2.7"
project:
  rigor: {rigor}
verify:
  checks:
    lint: '{lint}'
    typecheck: ""
    test: '{test}'
    build: ""
    e2e: ""
"""
ZERO = "0" * 40


def git(root, *args):
    return subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=True).stdout.strip()


def make_repo(base, *, lint="true", test="true", rigor="standard", extra=""):
    root = Path(base)
    git(root, "init", "-q")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "t")
    (root / ".agent-workflow").mkdir()
    (root / ".agent-workflow/config.yaml").write_text(CONFIG.format(rigor=rigor, lint=lint, test=test) + extra)
    (root / "f.txt").write_text("x")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "init", "--no-verify")
    return root


def push_ref(root):
    return f"refs/heads/main {git(root, 'rev-parse', 'HEAD')} refs/heads/main {ZERO}"


class TestHooksInstall(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = make_repo(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_install_is_idempotent(self):
        first = hooks.install(self.root)
        self.assertEqual("installed", first["status"])
        self.assertEqual({"pre-commit": "installed", "pre-push": "installed"}, first["hooks"])
        hook = self.root / ".git/hooks/pre-push"
        self.assertEqual(0o755, hook.stat().st_mode & 0o777)
        self.assertIn("hooks run pre-push", hook.read_text())
        again = hooks.install(self.root)
        self.assertEqual({"pre-commit": "unchanged", "pre-push": "unchanged"}, again["hooks"])

    def test_foreign_hook_is_kept(self):
        foreign = self.root / ".git/hooks/pre-commit"
        foreign.write_text("#!/bin/sh\necho mine\n")
        result = hooks.install(self.root)
        self.assertEqual("occupied", result["status"])
        self.assertEqual("occupied", result["hooks"]["pre-commit"])
        self.assertEqual("installed", result["hooks"]["pre-push"])
        self.assertEqual("#!/bin/sh\necho mine\n", foreign.read_text())

    def test_missing_hooks_path_is_reported_not_created(self):
        git(self.root, "config", "core.hooksPath", str(self.root / "nope"))
        result = hooks.install(self.root)
        self.assertEqual("missing", result["status"])
        self.assertFalse((self.root / "nope").exists())

    def test_status(self):
        self.assertEqual({"pre-commit": "missing", "pre-push": "missing"}, hooks.status(self.root))
        hooks.install(self.root)
        self.assertEqual({"pre-commit": "ok", "pre-push": "ok"}, hooks.status(self.root))

    def test_doctor_reports_hooks_without_flipping_health(self):
        payload = setup_service.doctor(repository=self.root)
        self.assertEqual({"pre-commit": "missing", "pre-push": "missing"}, payload["checks_details"]["hooks"])
        self.assertTrue(any(action.startswith("hooks: pre-push is missing") for action in payload["actions"]))
        self.assertTrue(all(payload["checks"].get(name, True) for name in ("configuration",)))


class TestHooksRun(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def repo(self, name, **kwargs):
        path = self.base / name
        path.mkdir()
        return make_repo(path, **kwargs)

    def test_pre_commit_runs_only_lint_and_typecheck(self):
        self.assertNotEqual(0, hooks.run(self.repo("a", lint="false", test="false"), "pre-commit"))
        self.assertEqual(0, hooks.run(self.repo("b", lint="true", test="false"), "pre-commit"))

    def test_pre_push_runs_test_and_stops_at_first_failure(self):
        root = self.repo("a", test="echo ran >> ran.txt; false")
        self.assertNotEqual(0, hooks.run(root, "pre-push", [push_ref(root)]))
        self.assertEqual("ran\n", (root / "ran.txt").read_text())

    def test_pre_push_skips_tags_deletes_and_other_shas(self):
        root = self.repo("a", test="false")
        head = git(root, "rev-parse", "HEAD")
        for ref in (f"refs/tags/v1 {head} refs/tags/v1 {ZERO}",
                    f"(delete) {ZERO} refs/heads/x {head}",
                    f"refs/heads/other {'a' * 40} refs/heads/other {ZERO}"):
            self.assertEqual(0, hooks.run(root, "pre-push", [ref]), ref)

    def test_empty_verify_commands_exit_zero(self):
        root = self.repo("a", lint="", test="")
        self.assertEqual(0, hooks.run(root, "pre-commit"))
        self.assertEqual(0, hooks.run(root, "pre-push", [push_ref(root)]))

    def test_git_env_is_stripped(self):
        root = self.repo("a", lint='test -z "$GIT_INDEX_FILE"')
        os.environ["GIT_INDEX_FILE"] = "/nonexistent"
        try:
            self.assertEqual(0, hooks.run(root, "pre-commit"))
        finally:
            del os.environ["GIT_INDEX_FILE"]

    def test_package_checks_run_in_the_package_directory(self):
        extra = ("  packages:\n    - path: pkg\n      shape: library\n      verify:\n"
                 "        checks:\n          test: \"touch ../pkg-ran\"\n")
        root = self.repo("a", test="true", extra="")
        config = root / ".agent-workflow/config.yaml"
        config.write_text(config.read_text().replace("project:\n  rigor: standard\n",
                                                     "project:\n  rigor: standard\n" + extra))
        (root / "pkg").mkdir()
        self.assertEqual(0, hooks.run(root, "pre-push", [push_ref(root)]))
        self.assertTrue((root / "pkg-ran").exists())

    def test_real_git_commit_is_blocked_by_installed_hook(self):
        root = self.repo("a", lint="false")
        bin_dir = self.base / "bin"
        bin_dir.mkdir()
        wrapper = bin_dir / "gin-workflow"
        wrapper.write_text(f'#!/bin/sh\nexec python3 "{SCRIPTS / "gin-workflow"}" "$@"\n')
        wrapper.chmod(0o755)
        hooks.install(root)
        (root / "f.txt").write_text("y")
        git(root, "add", "-A")
        env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"}
        blocked = subprocess.run(["git", "commit", "-qm", "x"], cwd=root, env=env, capture_output=True, text=True)
        self.assertNotEqual(0, blocked.returncode)
        self.assertIn("lint failed", blocked.stderr)


if __name__ == "__main__":
    unittest.main()
