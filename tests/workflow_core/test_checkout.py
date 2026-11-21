"""worktrees() lists the git worktrees inside a repository with their branch."""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"))

from team_fixtures import git  # noqa: E402
from workflow_core.checkout import worktrees  # noqa: E402


class WorktreeListTests(unittest.TestCase):
    def test_excludes_worktrees_outside_the_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            git(root, "init", "-q", "-b", "main")
            git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "x")
            git(root, "worktree", "add", "-q", "-b", "feat/ep1", str(root / ".planning/worktrees/ep1"))
            git(root, "worktree", "add", "-q", "-b", "other", str(Path(tmp) / "elsewhere"))
            found = worktrees(root)
            self.assertEqual([(t.path.name, t.branch) for t in found], [("ep1", "feat/ep1")])

    def test_lists_every_worktree_inside_the_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            git(root, "init", "-q", "-b", "main")
            git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "x")
            git(root, "worktree", "add", "-q", "-b", "wt-x", str(root / ".claude/worktrees/x"))
            self.assertEqual([(t.path.name, t.branch) for t in worktrees(root)], [("x", "wt-x")])

    def test_not_a_git_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(worktrees(Path(tmp)), [])


if __name__ == "__main__":
    unittest.main()
