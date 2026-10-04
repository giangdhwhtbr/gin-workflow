"""`gin-workflow usage` command line: collect (best effort) and report, exits 0 ok and 2 errors."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from team_fixtures import calls, fake_cli, git, path_with, run_cli, write  # noqa: E402

USAGE = {"version": 1, "cost": 2.5, "models": {"m1": {"input": 1, "output": 2, "cache_read": 0, "cache_write": 0,
                                                     "cost": 2.5}},
         "stages": {"execute": {"tokens": 3, "cost": 2.5}}, "unpriced": ["m9"],
         "quality": {"reopens": 1, "bugs": 0, "review_cycles": 2, "rejections": 1,
                     "findings": {"critical": 0, "important": 1, "minor": 0, "suggestion": 0}, "waivers": 0}}


class UsageCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "main")
        self.bin = Path(self.tmp.name) / "bin"
        self.home = Path(self.tmp.name) / "home"
        self.env = {**path_with(self.bin), "CLAUDE_CONFIG_DIR": str(self.home / "claude"),
                    "CODEX_HOME": str(self.home / "codex")}
        fake_cli(self.bin, "bd", [
            {"argv": ["show", "t1"], "stdout": [{"id": "t1", "issue_type": "task", "title": "T1",
                                                "started_at": "2026-10-04T09:00:00Z", "closed_at": None}]},
            {"argv": ["history", "t1"], "stdout": []},
            {"argv": ["dep", "list", "t1"], "stdout": []},
            {"argv": ["update"], "stdout": ""},
            {"argv": ["list", "--all"], "stdout": [
                {"id": "t1", "title": "T1", "issue_type": "task", "status": "closed",
                 "closed_at": "2026-10-04T10:00:00Z", "metadata": {"ai_usage": json.dumps(USAGE)}},
                {"id": "t2", "title": "T2", "issue_type": "task", "status": "closed",
                 "closed_at": "2026-10-04T10:00:00Z"}]},
        ])

    def test_collect_writes_metadata_and_prints_the_summary(self):
        done = run_cli(self.repo, "usage", "collect", "--bead", "t1", "--format", "json", env=self.env)
        self.assertEqual(done.returncode, 0, done.stderr)
        summary = json.loads(done.stdout)
        self.assertEqual(summary["sources"], {"claude_code": "not_found", "codex": "not_found"})
        self.assertIn("update", [argv[1] for argv in calls(self.bin)])

    def test_collect_errors_exit_2_unless_best_effort(self):
        env = {**self.env, "PATH": str(Path(self.tmp.name) / "nothing")}
        done = run_cli(self.repo, "usage", "collect", "--bead", "t1", env=env)
        self.assertEqual(done.returncode, 2)
        self.assertIn("bd is not installed", done.stderr)
        done = run_cli(self.repo, "usage", "collect", "--bead", "t1", "--best-effort", env=env)
        self.assertEqual(done.returncode, 0)
        self.assertIn("warning:", done.stderr)

    def test_bad_price_list_exits_2(self):
        write(self.repo, ".agent-workflow/usage-prices.yaml", "prices: [1, 2]\n")
        done = run_cli(self.repo, "usage", "collect", "--bead", "t1", env=self.env)
        self.assertEqual(done.returncode, 2)

    def test_report_json_and_text(self):
        done = run_cli(self.repo, "usage", "report", "--format", "json", env=self.env)
        self.assertEqual(done.returncode, 0, done.stderr)
        out = json.loads(done.stdout)
        self.assertEqual(set(out), {"beads", "totals", "unpriced", "unattributed", "not_collected"})
        self.assertEqual(out["not_collected"], ["t2"])
        text = run_cli(self.repo, "usage", "report", env=self.env).stdout
        self.assertIn("t1", text)
        self.assertIn("2.5", text)
        self.assertIn("m9", text)
        self.assertIn("not collected: t2", text)

    def test_report_scope_flags_are_exclusive_and_since_is_a_date(self):
        done = run_cli(self.repo, "usage", "report", "--bead", "t1", "--epic", "e1", env=self.env)
        self.assertEqual(done.returncode, 2)
        done = run_cli(self.repo, "usage", "report", "--since", "yesterday", env=self.env)
        self.assertEqual(done.returncode, 2)

    def test_top_level_usage_lists_usage(self):
        done = run_cli(self.repo, env=self.env)
        self.assertEqual(done.returncode, 2)
        self.assertIn("usage", done.stderr.split("{", 1)[1])


if __name__ == "__main__":
    unittest.main()
