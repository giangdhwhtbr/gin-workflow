"""Every gin entry point resolves the workspace root from inside a child repository."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "plugins/gin-workflow/src/scripts/gin"
sys.path.insert(0, str(ROOT / "plugins/gin-workflow/src/scripts"))

from tests.workflow_core.team_fixtures import path_with  # noqa: E402
from tests.workflow_core.test_workspace import git, make_workspace  # noqa: E402


def run(cwd: Path, *args: str, env=None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(LAUNCHER), *args], cwd=cwd, text=True, capture_output=True,
                          env={**os.environ, **(env or {})}, check=False)


class ResolutionFromChildTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.base = Path(directory.name).resolve()
        self.root = make_workspace(self.base)
        self.child = self.root / "services/api"
        (self.root / ".agent-workflow/config.yaml").write_text(
            (self.root / ".agent-workflow/config.yaml").read_text() + "providers:\n  task_tracking: beads\n")
        self.assertEqual(0, run(self.root, "setup", "init", "--harness", "claude", "--approve",
                                "--format", "json").returncode)

    def state(self, cwd: Path) -> dict:
        done = run(cwd, "state", "--format", "json")
        self.assertIn(done.returncode, (0, 1), done.stderr)
        return json.loads(done.stdout)

    def test_state_is_the_same_from_parent_child_and_track_worktree(self):
        wt = self.root / ".planning/worktrees/t1"
        wt.parent.mkdir(parents=True)
        git(self.child, "worktree", "add", "-b", "feat/x-t1", str(wt), "main")
        parent, child, linked = self.state(self.root), self.state(self.child), self.state(wt)
        self.assertEqual(parent["gates"], child["gates"])
        self.assertEqual(parent["gates"], linked["gates"])
        self.assertEqual([None, "services/api", "services/api"],
                         [s["workspace"]["current_repo"] for s in (parent, child, linked)])
        self.assertEqual(str(self.root), child["workspace"]["root"])

    def test_explicit_repository_is_taken_as_given(self):
        done = run(self.base, "state", "--repository", str(self.child), "--format", "json")
        # a repository without .agent-workflow: today's exit 0, state computed there (not at the workspace root)
        self.assertEqual(0, done.returncode, done.stderr)
        self.assertTrue((self.child / ".agent-workflow/runtime").is_dir())

    def test_plain_repository_reports_null_workspace(self):
        plain = self.base / "plain"
        plain.mkdir()
        (plain / ".agent-workflow").mkdir()
        (plain / ".agent-workflow/config.yaml").write_text("schema_version: '2.9'\n")
        run(plain, "setup", "init", "--harness", "claude", "--approve", "--format", "json")
        self.assertIsNone(self.state(plain)["workspace"])

    def test_task_runs_bd_at_the_workspace_root(self):
        with tempfile.TemporaryDirectory() as bin_dir:
            script = Path(bin_dir) / "bd"
            script.write_text('#!/bin/sh\npwd > "$BD_CWD_FILE"\necho "[]"\n', encoding="utf-8")
            script.chmod(0o755)
            marker = Path(bin_dir) / "cwd.txt"
            done = run(self.child, "task", "list", "--json",
                       env={**path_with(Path(bin_dir)), "BD_CWD_FILE": str(marker)})
            self.assertEqual(0, done.returncode, done.stderr)
            self.assertEqual(str(self.root), marker.read_text().strip())


if __name__ == "__main__":
    unittest.main()
