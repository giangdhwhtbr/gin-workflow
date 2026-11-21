"""AI usage tracking was retired in gin 3.4.0: no command, no modules, and dispatch ignores `usage.budget_usd`."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"))

from team_fixtures import fake_cli, path_with, write  # noqa: E402
from workflow_core import cli, routes  # noqa: E402
from workflow_core.setup_service import refresh  # noqa: E402

CONFIG = "schema_version: '2.8'\nproviders:\n  task_tracking: beads\nusage:\n  budget_usd: 1\n"
ROUTE = {"provider": "claude", "selection_mode": "explicit", "model": "sonnet", "effort": "medium"}
MANIFEST = json.dumps({"workflow_id": "ep1", "tracks": {"t1": {"resolved": ROUTE}}})


class UsageRetiredTests(unittest.TestCase):
    def test_gin_usage_is_an_unknown_command(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(2, cli.main(["usage", "collect", "--bead", "x"]))
        self.assertIn("usage: gin {", err.getvalue())
        self.assertNotIn("usage", cli.TOP_COMMANDS)

    def test_the_usage_modules_are_gone(self):
        for name in ("usage", "usage_cli", "usage_logs", "usage_attribution"):
            with self.subTest(module=name):
                self.assertIsNone(importlib.util.find_spec(f"workflow_core.{name}"))

    def test_dispatch_ignores_the_budget_and_never_calls_bd(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(os.path.realpath(tmp))
            root, bin_dir = base / "repo", base / "bin"
            write(root, ".agent-workflow/runtime/assignments/ep1.yaml", MANIFEST)
            with mock.patch.dict(os.environ, path_with(bin_dir)):
                write(root, ".agent-workflow/config.yaml", CONFIG)
                refresh(root)
                (root / ".agent-workflow/executables.local.yaml").unlink()
                fake_cli(bin_dir, "bd", [{"argv": ["show", "ep1"], "stdout": [
                    {"id": "ep1", "issue_type": "epic",
                     "metadata": {"ai_usage": json.dumps({"cost": 5, "unpriced": []})}}]}])
                out = io.StringIO()
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                    code = routes.main(["dispatch", "--workflow-id", "ep1", "--task-id", "t1",
                                        "--repository", str(root), "--json"])
            self.assertEqual((0, "sonnet"), (code, json.loads(out.getvalue())["model"]))
            self.assertFalse((bin_dir / "calls.log").exists())
