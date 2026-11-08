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
from tests.workflow_core.test_workspace import git, init_repo, make_workspace  # noqa: E402


def run(cwd: Path, *args: str, env=None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(LAUNCHER), *args], cwd=cwd, text=True, capture_output=True,
                          env={**os.environ, **(env or {})}, check=False)


SPEC = "### US-1: a\n\nAcceptance criteria:\n- x\n"


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

    def state(self, cwd: Path, *args: str) -> dict:
        done = run(cwd, "state", "--format", "json", *args)
        self.assertIn(done.returncode, (0, 1), done.stderr)
        return json.loads(done.stdout)

    def test_state_is_the_same_from_parent_child_and_track_worktree(self):
        spec = self.root / ".planning/specs/2026-01-01-w-design.md"
        spec.parent.mkdir(parents=True)
        spec.write_text(SPEC, encoding="utf-8")
        recorded = run(self.root, "record", "requirement-confirmed", "--workflow-id", "w", "--actor", "t",
                       "--evidence", ".planning/specs/2026-01-01-w-design.md")
        self.assertEqual(0, recorded.returncode, recorded.stderr)
        wt = self.root / ".planning/worktrees/t1"
        wt.parent.mkdir(parents=True)
        git(self.child, "worktree", "add", "-b", "feat/x-t1", str(wt), "main")
        parent, child, linked = (self.state(cwd, "--workflow-id", "w") for cwd in (self.root, self.child, wt))
        self.assertTrue(parent["gates"]["requirement_confirmed"])
        for key in ("gates", "decision", "epic"):
            self.assertEqual(parent[key], child[key], key)
            self.assertEqual(parent[key], linked[key], key)
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

    def test_linked_worktree_of_the_parent_is_its_own_root(self):
        wt = self.base / "parent-wt"
        git(self.root, "worktree", "add", str(wt), "-b", "feat/x", "main")
        spec = ".planning/specs/2026-01-01-x-design.md"
        (wt / spec).parent.mkdir(parents=True)
        (wt / spec).write_text("### US-1: a\n\nno criteria\n", encoding="utf-8")
        refused = run(wt, "record", "requirement-confirmed", "--evidence", spec, "--actor", "t", "--workflow-id", "x")
        self.assertEqual(1, refused.returncode, refused.stderr)  # the spec was read from the worktree, not the parent
        self.assertIn("US-1 has no acceptance criteria", refused.stderr)
        (wt / spec).write_text(SPEC, encoding="utf-8")
        done = run(wt, "record", "requirement-confirmed", "--evidence", spec, "--actor", "t", "--workflow-id", "x")
        self.assertEqual(0, done.returncode, done.stderr)
        self.assertTrue(self.state(wt, "--workflow-id", "x")["gates"]["requirement_confirmed"])

    def test_notify_from_a_child_reads_the_parent_config(self):
        config = self.root / ".agent-workflow/config.yaml"
        config.write_text(config.read_text() + "notifications:\n  telegram: true\n")
        self.assertEqual(0, run(self.root, "setup", "refresh", "--format", "json").returncode)
        done = run(self.child, "notify", "--event", "needs_input", "x",
                   env={"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": ""})
        self.assertEqual(0, done.returncode, done.stderr)
        # the parent's telegram switch is on, so the missing credentials are reported (a child-only read stays silent)
        self.assertIn("telegram_credentials_missing", done.stderr)
        self.assertNotIn("setup is required", done.stderr)

    @unittest.skipIf(os.name == "nt", "runs a #! bd stub from PATH, which needs POSIX")
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


class ManifestErrorTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.base = Path(directory.name).resolve()

    def assert_reported(self, cwd: Path) -> None:
        state = run(cwd, "state", "--format", "json")
        self.assertEqual(2, state.returncode, state.stderr)
        self.assertEqual("error", json.loads(state.stdout)["status"])
        rules = run(cwd, "rules", "--files", "x")
        self.assertEqual(2, rules.returncode)
        self.assertNotIn("Traceback", rules.stderr)
        self.assertIn("error:", rules.stderr)

    def test_invalid_yaml_in_a_plain_repository(self):
        plain = init_repo(self.base / "plain")
        (plain / ".agent-workflow").mkdir()
        (plain / ".agent-workflow/config.yaml").write_text("schema_version: [unclosed\n", encoding="utf-8")
        self.assert_reported(plain)

    def test_bad_manifest_in_an_enclosing_parent(self):
        root = init_repo(self.base / "ws")
        (root / ".agent-workflow").mkdir()
        (root / ".agent-workflow/config.yaml").write_text("workspace:\n  repos: {}\n", encoding="utf-8")
        self.assert_reported(init_repo(root / "services/api"))


if __name__ == "__main__":
    unittest.main()
