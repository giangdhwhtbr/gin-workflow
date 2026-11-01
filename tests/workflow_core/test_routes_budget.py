"""`routes dispatch` refuses a track once the epic's stored cost reaches 120% of `usage.budget_usd`."""

from __future__ import annotations

import contextlib
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
from workflow_core import routes, usage  # noqa: E402
from workflow_core.events import WorkflowEvent, WorkflowEventStore  # noqa: E402
from workflow_core.setup_service import refresh  # noqa: E402

CONFIG = "schema_version: '2.8'\nproviders:\n  task_tracking: beads\n"
ROUTE = {"provider": "claude", "selection_mode": "explicit", "model": "sonnet", "effort": "medium"}
MANIFEST = json.dumps({"workflow_id": "ep1", "tracks": {"t1": {"resolved": ROUTE}}})


class DispatchBudgetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(os.path.realpath(self.tmp.name))
        self.root = base / "repo"
        self.manifest = write(self.root, ".agent-workflow/runtime/assignments/ep1.yaml", MANIFEST)
        self.events = self.root / ".agent-workflow/runtime/events.jsonl"
        self.bin = base / "bin"
        patcher = mock.patch.dict(os.environ, path_with(self.bin))
        patcher.start()
        self.addCleanup(patcher.stop)

    def config(self, extra=""):
        write(self.root, ".agent-workflow/config.yaml", CONFIG + extra)
        refresh(self.root)  # `bd` is used only when the generated config names Beads

    def stored(self, ai_usage):
        fake_cli(self.bin, "bd", [{"argv": ["show", "ep1"], "stdout": [
            {"id": "ep1", "issue_type": "epic", "metadata": {"ai_usage": json.dumps(ai_usage)}}]}])

    def dispatch(self, workflow_id="ep1"):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = routes.main(["dispatch", "--workflow-id", workflow_id, "--task-id", "t1",
                                "--repository", str(self.root), "--json"])
        return code, json.loads(out.getvalue()), err.getvalue()

    def test_us1_over_budget_exits_3_and_changes_nothing(self):
        self.config("usage:\n  budget_usd: 10\n")
        self.stored({"cost": 12, "unpriced": []})
        code, payload, _ = self.dispatch()
        self.assertEqual(code, 3)
        self.assertEqual(payload, {"status": "over_budget", "epic": "ep1", "cost": 12, "budget_usd": 10.0})
        self.assertEqual(self.manifest.read_text(encoding="utf-8"), MANIFEST)
        self.assertFalse(self.events.exists())

    def test_us1_raising_the_budget_lets_dispatch_proceed(self):
        self.config("usage:\n  budget_usd: 20\n")
        self.stored({"cost": 12, "unpriced": []})
        code, payload, _ = self.dispatch()
        self.assertEqual((code, payload["model"]), (0, "sonnet"))

    def test_us1_no_budget_dispatches_without_reading_bd(self):
        self.config()
        code, _, _ = self.dispatch()
        self.assertEqual(code, 0)
        self.assertFalse((self.bin / "calls.log").exists())

    def test_us2_null_cost_or_unpriced_model_never_stops(self):
        self.config("usage:\n  budget_usd: 10\n")
        for stored in ({"cost": None, "unpriced": ["m9"]}, {"cost": 50, "unpriced": ["m9"]}, {}):
            self.stored(stored)
            self.assertEqual(self.dispatch()[0], 0, stored)

    def test_unreadable_bd_warns_and_dispatches(self):
        self.config("usage:\n  budget_usd: 10\n")
        with mock.patch.object(usage, "_bd", side_effect=usage.UsageError("bd is not installed")):
            code, _, err = self.dispatch()
        self.assertEqual(code, 0)
        self.assertIn("budget not checked: bd is not installed", err)

    def test_us1_workflow_id_maps_to_its_recorded_epic(self):
        self.config("usage:\n  budget_usd: 10\n")
        self.stored({"cost": 12, "unpriced": []})
        write(self.root, ".agent-workflow/runtime/assignments/wf.yaml", MANIFEST)
        WorkflowEventStore(self.events).append(
            WorkflowEvent.create(event_type="orchestration.ready", workflow_id="wf", payload={"epic": "ep1"}))
        code, payload, _ = self.dispatch("wf")
        self.assertEqual((code, payload["epic"]), (3, "ep1"))
