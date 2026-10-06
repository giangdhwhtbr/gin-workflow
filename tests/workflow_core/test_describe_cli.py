"""`gin-workflow describe` command line interface tests."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from team_fixtures import fake_cli, git, path_with, run_cli  # noqa: E402


class DescribeCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "main")
        self.bin = Path(self.tmp.name) / "bin"
        self.env = path_with(self.bin)

        # fake bd for basic tree: t1 has child t1.1
        self.fake_rules = [
            {"argv": ["show", "t1", "--json", "--include-comments"], "stdout": [{"id": "t1", "title": "Task 1", "issue_type": "epic", "status": "open"}]},
            {"argv": ["show", "t1.1", "--json", "--include-comments"], "stdout": [{"id": "t1.1", "title": "Subtask 1.1", "issue_type": "task", "status": "open", "parent": "t1"}]},
            {"argv": ["dep", "list", "t1", "--direction=up", "--type", "parent-child", "--json"], "stdout": [{"id": "t1.1", "dependency_type": "parent-child"}]},
            {"argv": ["dep", "list", "t1.1", "--direction=up", "--type", "parent-child", "--json"], "stdout": []},
            {"argv": ["dep", "list", "t1", "t1.1", "--direction=up", "--type", "discovered-from", "--json"], "stdout": []},
        ]
        fake_cli(self.bin, "bd", self.fake_rules)

    def test_default_output_path_and_json_format(self):
        done = run_cli(self.repo, "describe", "t1", "--format", "json", env=self.env)
        self.assertEqual(done.returncode, 0, done.stderr)
        data = json.loads(done.stdout)
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["nodes"], 2)
        self.assertEqual(data["edges"], 1)

        expected_path = self.repo / ".agent-workflow/runtime/describe/t1.html"
        self.assertEqual(Path(data["path"]), expected_path)
        self.assertTrue(expected_path.is_file())
        content = expected_path.read_text(encoding="utf-8")
        self.assertIn("t1.1", content)
        self.assertIn("Subtask 1.1", content)

    def test_custom_out_flag(self):
        out_path = Path(self.tmp.name) / "custom" / "view.html"
        done = run_cli(self.repo, "describe", "t1", "--out", str(out_path), env=self.env)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn(str(out_path), done.stdout)
        self.assertTrue(out_path.is_file())

    def test_unknown_bead_exits_2(self):
        missing = [
            {"argv": ["show", "unknown", "--json", "--include-comments"], "exit": 1, "stderr": 'Error fetching unknown: no issue found matching "unknown"\n'}
        ]
        fake_cli(self.bin, "bd", missing)
        done = run_cli(self.repo, "describe", "unknown", env=self.env)
        self.assertEqual(done.returncode, 2)
        self.assertIn("error: bd show unknown: no such bead", done.stderr)

    def test_exceeding_max_nodes_exits_3(self):
        # Create fake bd rule returning 305 child nodes for t1
        kids = [f"t1.{i}" for i in range(1, 305)]
        overflow_rules = [
            {"argv": ["show", "t1", "--json", "--include-comments"], "stdout": [{"id": "t1", "title": "Task 1", "issue_type": "epic", "status": "open"}]},
            {"argv": ["dep", "list", "t1", "--direction=up", "--type", "parent-child", "--json"], "stdout": [{"id": k, "dependency_type": "parent-child"} for k in kids]},
        ]
        fake_cli(self.bin, "bd", overflow_rules)
        done = run_cli(self.repo, "describe", "t1", env=self.env)
        self.assertEqual(done.returncode, 3)
        self.assertIn("error: graph has more than 300 nodes", done.stderr)

    def test_cli_usage_mentions_describe(self):
        done = run_cli(self.repo)
        self.assertEqual(done.returncode, 2)
        self.assertIn("describe", done.stderr)


if __name__ == "__main__":
    unittest.main()
