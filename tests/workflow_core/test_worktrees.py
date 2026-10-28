import contextlib
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"))

from workflow_core import worktrees  # noqa: E402


def git(root, *argv):
    return subprocess.run(["git", *argv], cwd=root, capture_output=True, text=True, check=True).stdout.strip()


class WorktreeTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        git(self.root, "init", "-q")
        git(self.root, "config", "user.email", "t@example.com")
        git(self.root, "config", "user.name", "Test")
        (self.root / "file.txt").write_text("base", encoding="utf-8")
        git(self.root, "add", ".")
        git(self.root, "commit", "-q", "-m", "base")
        self.base = git(self.root, "rev-parse", "--abbrev-ref", "HEAD")
        self.worktrees = self.root / ".planning/worktrees"

    def test_create_from_current_branch_then_cleanup_twice(self):
        path = worktrees.create(self.root, "t1", "bead/t1")
        self.assertEqual(self.worktrees / "t1", path)
        self.assertEqual("bead/t1", git(path, "rev-parse", "--abbrev-ref", "HEAD"))
        self.assertEqual(git(self.root, "rev-parse", self.base), git(path, "rev-parse", "HEAD"))
        self.assertEqual(path, worktrees.cleanup(self.root, "t1"))
        self.assertFalse(path.exists())
        self.assertIsNone(worktrees.cleanup(self.root, "t1"))

    def test_create_from_explicit_base_ref(self):
        git(self.root, "branch", "other")
        path = worktrees.create(self.root, "t2", "bead/t2", "other")
        self.assertEqual(git(self.root, "rev-parse", "other"), git(path, "rev-parse", "HEAD"))

    def test_rejects_unsafe_ids_without_side_effects(self):
        for track_id in ("../x", "a/b", "", ".", "..", "x y"):
            with self.subTest(track_id=track_id), self.assertRaises(ValueError):
                worktrees.create(self.root, track_id, "bead/x")
        self.assertFalse(self.worktrees.exists())
        self.assertEqual("", git(self.root, "branch", "--list", "bead/x"))

    def test_rejects_existing_target_and_empty_branch(self):
        (self.worktrees / "t3").mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, "already exists"):
            worktrees.create(self.root, "t3", "bead/t3")
        with self.assertRaisesRegex(ValueError, "branch"):
            worktrees.create(self.root, "t4", " ")
        self.assertEqual("", git(self.root, "branch", "--list", "bead/t3"))

    def test_git_failure_is_a_runtime_error(self):
        with self.assertRaises(RuntimeError):
            worktrees.create(self.root, "t5", "bead/t5", "no-such-ref")

    def test_cli_create_cleanup_and_error(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.assertEqual(0, worktrees.main(["create", "--repository", str(self.root), "t6", "bead/t6"]))
            self.assertEqual(1, worktrees.main(["create", "--repository", str(self.root), "../x", "b"]))
            self.assertEqual(0, worktrees.main(["cleanup", "--repository", str(self.root), "t6"]))
            self.assertEqual(0, worktrees.main(["cleanup", "--repository", str(self.root), "t6"]))
        self.assertIn(str(self.worktrees / "t6"), out.getvalue())
        self.assertIn("error: invalid track-id '../x'", err.getvalue())


if __name__ == "__main__":
    unittest.main()
