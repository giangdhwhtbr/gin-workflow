"""Tests for `gin commit`: scoped commit for BA and tester output."""

from __future__ import annotations

from datetime import date
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core import scoped_commit  # noqa: E402
from workflow_core.scoped_commit import ScopedCommitError, commit, main  # noqa: E402


def git(root: Path, *args: str) -> str:
    res = subprocess.run(["git", *args], cwd=root, text=True, capture_output=True)
    if res.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed in {root}: {res.stderr}")
    return res.stdout.strip()


def init_repo(root: Path, branch: str = "master") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    git(root, "init", "-q", "-b", branch)
    git(root, "config", "user.email", "tester@example.com")
    git(root, "config", "user.name", "Tester")
    git(root, "config", "commit.gpgsign", "false")
    (root / "initial.txt").write_text("initial content", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "initial commit", "--no-verify")
    return root


class TestScopedCommit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name).resolve()
        self.repo = init_repo(self.base / "repo", branch="master")

    def tearDown(self):
        self.tmp.cleanup()

    def test_feature_branch_commits_only_named_paths_with_other_staged(self):
        # Checkout a feature branch
        git(self.repo, "checkout", "-b", "feat/my-feature")
        # Stage an unrelated file
        (self.repo / "unrelated.txt").write_text("unrelated change", encoding="utf-8")
        git(self.repo, "add", "unrelated.txt")

        # Create changes under qa/cases/catalog
        target_dir = self.repo / "qa/cases/catalog"
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "case1.md").write_text("case 1 content", encoding="utf-8")

        # Run commit
        buf_out = io.StringIO()
        with mock.patch("sys.stdout", buf_out), mock.patch("os.getcwd", return_value=str(self.repo)):
            rc = main(["qa/cases/catalog", "-m", "add catalog cases"])
        self.assertEqual(rc, 0)

        # Check branch is still feat/my-feature
        self.assertEqual(git(self.repo, "branch", "--show-current"), "feat/my-feature")

        # Check git log -1 --name-only lists only qa/cases/catalog/case1.md
        log_files = git(self.repo, "log", "-1", "--name-only", "--format=").splitlines()
        self.assertEqual(log_files, ["qa/cases/catalog/case1.md"])

        # Check unrelated.txt is still staged in the index
        status = git(self.repo, "status", "--porcelain")
        self.assertIn("A  unrelated.txt", status)

    def test_new_modified_deleted_committed_and_gitignore_ignored(self):
        git(self.repo, "checkout", "-b", "feat/files-test")
        target_dir = self.repo / "qa/cases/catalog"
        target_dir.mkdir(parents=True, exist_ok=True)

        # Existing tracked file to modify and delete
        (target_dir / "mod.txt").write_text("before mod", encoding="utf-8")
        (target_dir / "del.txt").write_text("to delete", encoding="utf-8")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "prepare files", "--no-verify")

        # Set up gitignore
        (self.repo / ".gitignore").write_text("*.ignored\n", encoding="utf-8")
        git(self.repo, "add", ".gitignore")
        git(self.repo, "commit", "-qm", "add gitignore", "--no-verify")

        # Make changes: new, mod, del, ignored
        (target_dir / "new.txt").write_text("new content", encoding="utf-8")
        (target_dir / "mod.txt").write_text("after mod", encoding="utf-8")
        (target_dir / "del.txt").unlink()
        (target_dir / "file.ignored").write_text("ignored content", encoding="utf-8")

        buf_out = io.StringIO()
        with mock.patch("sys.stdout", buf_out), mock.patch("os.getcwd", return_value=str(self.repo)):
            rc = main(["qa/cases/catalog", "-m", "update catalog"])
        self.assertEqual(rc, 0)

        log_files = set(git(self.repo, "log", "-1", "--name-only", "--format=").splitlines())
        self.assertEqual(log_files, {"qa/cases/catalog/new.txt", "qa/cases/catalog/mod.txt", "qa/cases/catalog/del.txt"})
        self.assertNotIn("qa/cases/catalog/file.ignored", log_files)

    def test_on_master_creates_branch_and_second_run_appends_suffix(self):
        target_dir = self.repo / "qa/cases/catalog"
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "case1.md").write_text("case 1", encoding="utf-8")

        test_today = date(2026, 11, 14)
        buf_out = io.StringIO()
        with mock.patch("sys.stdout", buf_out), mock.patch("os.getcwd", return_value=str(self.repo)):
            with mock.patch("workflow_core.scoped_commit.date") as mock_date:
                mock_date.today.return_value = test_today
                rc = main(["qa/cases/catalog", "-m", "first run on master"])
        self.assertEqual(rc, 0)
        output = buf_out.getvalue()
        self.assertIn("Created branch gin/qa-cases-catalog-2026-11-14", output)
        self.assertIn("Not pushed.", output)
        self.assertEqual(git(self.repo, "branch", "--show-current"), "gin/qa-cases-catalog-2026-11-14")

        # Switch back to master
        git(self.repo, "checkout", "master")
        # Ensure master commit is untouched
        self.assertEqual(git(self.repo, "log", "-1", "--format=%s"), "initial commit")

        # Second run on master on the same day creates ...-2
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "case2.md").write_text("case 2", encoding="utf-8")
        buf_out2 = io.StringIO()
        with mock.patch("sys.stdout", buf_out2), mock.patch("os.getcwd", return_value=str(self.repo)):
            with mock.patch("workflow_core.scoped_commit.date") as mock_date:
                mock_date.today.return_value = test_today
                rc = main(["qa/cases/catalog", "-m", "second run on master"])
        self.assertEqual(rc, 0)
        output2 = buf_out2.getvalue()
        self.assertIn("Created branch gin/qa-cases-catalog-2026-11-14-2", output2)
        self.assertEqual(git(self.repo, "branch", "--show-current"), "gin/qa-cases-catalog-2026-11-14-2")

    def test_on_master_with_explicit_branch(self):
        target_dir = self.repo / "qa/cases"
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "cases.md").write_text("cases", encoding="utf-8")

        buf_out = io.StringIO()
        with mock.patch("sys.stdout", buf_out), mock.patch("os.getcwd", return_value=str(self.repo)):
            rc = main(["qa/cases", "-m", "custom branch", "--branch", "qa/my-cases"])
        self.assertEqual(rc, 0)
        self.assertEqual(git(self.repo, "branch", "--show-current"), "qa/my-cases")

    def test_workspace_child_default_branch(self):
        # Create a workspace parent and a child
        ws_root = self.base / "workspace"
        init_repo(ws_root, branch="main")
        (ws_root / ".agent-workflow").mkdir(parents=True, exist_ok=True)
        (ws_root / ".agent-workflow/config.yaml").write_text(
            "schema_version: '2.9'\n"
            "workspace:\n"
            "  repos:\n"
            "    - path: child\n"
            "      url: git@example.com:acme/child.git\n"
            "      shape: backend\n"
            "      default_branch: develop\n",
            encoding="utf-8",
        )
        child_repo = init_repo(ws_root / "child", branch="develop")
        (child_repo / "foo.txt").write_text("child change", encoding="utf-8")

        test_today = date(2026, 11, 14)
        buf_out = io.StringIO()
        with mock.patch("sys.stdout", buf_out), mock.patch("os.getcwd", return_value=str(child_repo)):
            with mock.patch("workflow_core.scoped_commit.date") as mock_date:
                mock_date.today.return_value = test_today
                rc = main(["foo.txt", "-m", "develop branch commit"])
        self.assertEqual(rc, 0)
        self.assertEqual(git(child_repo, "branch", "--show-current"), "gin/foo-txt-2026-11-14")

    def test_refusals_exit_2_and_leave_state_unchanged(self):
        # Record baseline state
        initial_commit = git(self.repo, "rev-parse", "HEAD")
        initial_branch = git(self.repo, "branch", "--show-current")

        # 1. Missing path
        buf_err = io.StringIO()
        with mock.patch("sys.stderr", buf_err), mock.patch("os.getcwd", return_value=str(self.repo)):
            rc = main(["non_existent.txt", "-m", "commit"])
        self.assertEqual(rc, 2)
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), initial_commit)
        self.assertEqual(git(self.repo, "branch", "--show-current"), initial_branch)

        # 2. Path outside the repository
        outside_file = self.base / "outside.txt"
        outside_file.write_text("outside", encoding="utf-8")
        buf_err = io.StringIO()
        with mock.patch("sys.stderr", buf_err), mock.patch("os.getcwd", return_value=str(self.repo)):
            rc = main([str(outside_file), "-m", "commit"])
        self.assertEqual(rc, 2)
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), initial_commit)

        # 3. Two repositories
        second_repo = init_repo(self.base / "repo2")
        (self.repo / "f1.txt").write_text("f1", encoding="utf-8")
        (second_repo / "f2.txt").write_text("f2", encoding="utf-8")
        buf_err = io.StringIO()
        with mock.patch("sys.stderr", buf_err), mock.patch("os.getcwd", return_value=str(self.repo)):
            rc = main(["f1.txt", str(second_repo / "f2.txt"), "-m", "commit"])
        self.assertEqual(rc, 2)
        err = buf_err.getvalue()
        self.assertIn(str(self.repo), err)
        self.assertIn(str(second_repo), err)
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), initial_commit)

        # 4. Detached HEAD
        git(self.repo, "checkout", "--detach", "HEAD")
        (self.repo / "detached.txt").write_text("detached change", encoding="utf-8")
        buf_err = io.StringIO()
        with mock.patch("sys.stderr", buf_err), mock.patch("os.getcwd", return_value=str(self.repo)):
            rc = main(["detached.txt", "-m", "detached commit"])
        self.assertEqual(rc, 2)
        self.assertIn("detached", buf_err.getvalue().lower())
        # Restore attached HEAD
        git(self.repo, "checkout", initial_branch)

        # 5. Empty message
        (self.repo / "empty_msg.txt").write_text("empty msg", encoding="utf-8")
        buf_err = io.StringIO()
        with mock.patch("sys.stderr", buf_err), mock.patch("os.getcwd", return_value=str(self.repo)):
            rc = main(["empty_msg.txt", "-m", "   "])
        self.assertEqual(rc, 2)
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), initial_commit)

        # 6. Invalid --branch
        (self.repo / "bad_branch.txt").write_text("bad branch", encoding="utf-8")
        buf_err = io.StringIO()
        with mock.patch("sys.stderr", buf_err), mock.patch("os.getcwd", return_value=str(self.repo)):
            rc = main(["bad_branch.txt", "-m", "bad branch test", "--branch", "-invalid-branch"])
        self.assertEqual(rc, 2)
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), initial_commit)

    def test_nothing_to_commit(self):
        buf_out = io.StringIO()
        with mock.patch("sys.stdout", buf_out), mock.patch("os.getcwd", return_value=str(self.repo)):
            rc = main(["initial.txt", "-m", "no change"])
        self.assertEqual(rc, 0)
        output = buf_out.getvalue()
        self.assertIn("Nothing to commit", output)
        self.assertEqual(git(self.repo, "branch", "--show-current"), "master")

    def test_pre_commit_hook_failure(self):
        hook = self.repo / ".git/hooks/pre-commit"
        hook.write_text("#!/bin/sh\necho 'hook rejection error' >&2\nexit 1\n", encoding="utf-8")
        hook.chmod(0o755)

        (self.repo / "hook_test.txt").write_text("hook test", encoding="utf-8")
        buf_err = io.StringIO()
        with mock.patch("sys.stderr", buf_err), mock.patch("os.getcwd", return_value=str(self.repo)):
            rc = main(["hook_test.txt", "-m", "should fail in hook"])
        self.assertEqual(rc, 1)
        self.assertIn("hook rejection error", buf_err.getvalue())
        # Branch created stays, but nothing committed
        self.assertIn("gin/hook-test-txt-", git(self.repo, "branch", "--show-current"))
        self.assertEqual(git(self.repo, "log", "-1", "--format=%s"), "initial commit")

    def test_no_push_and_json_output(self):
        # Set up a bare origin
        origin = self.base / "origin.git"
        subprocess.run(["git", "init", "--bare", str(origin)], check=True, capture_output=True)
        git(self.repo, "remote", "add", "origin", str(origin))
        git(self.repo, "push", "-u", "origin", "master")

        # Now checkout feature branch
        git(self.repo, "checkout", "-b", "feat/json-test")
        (self.repo / "json_file.txt").write_text("json test", encoding="utf-8")

        buf_out = io.StringIO()
        with mock.patch("sys.stdout", buf_out), mock.patch("os.getcwd", return_value=str(self.repo)):
            rc = main(["json_file.txt", "-m", "test json format", "--format", "json"])
        self.assertEqual(rc, 0)
        data = json.loads(buf_out.getvalue())
        self.assertFalse(data["pushed"])
        self.assertFalse(data["created_branch"])
        self.assertEqual(data["branch"], "feat/json-test")
        self.assertEqual(data["files"], ["json_file.txt"])
        self.assertTrue(data["commit"])

        # Verify origin has not received feat/json-test
        origin_refs = subprocess.run(["git", "branch", "-a"], cwd=origin, text=True, capture_output=True).stdout
        self.assertNotIn("feat/json-test", origin_refs)


if __name__ == "__main__":
    unittest.main()
