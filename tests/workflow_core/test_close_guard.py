import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core import close_guard  # noqa: E402
from workflow_core.events import WorkflowEventStore  # noqa: E402
from tests.workflow_core.test_tasks import ENV, gw  # noqa: E402


class CloseGuardTests(unittest.TestCase):
    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.root = Path(self._directory.name) / "repo"
        (self.root / ".claude").mkdir(parents=True)
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "init"], cwd=self.root, env=ENV, check=True)

    def init(self, ledger):
        done = gw(self.root, "setup", "init", "--harness", "claude", "--non-interactive", "--approve",
                  "--set", "providers.task_tracking=markdown",
                  "--set", f"project.review_ledger={'true' if ledger else 'false'}")
        self.assertEqual(0, done.returncode, done.stdout + done.stderr)
        for argv in (("--id", "ep-1", "--type", "epic", "Epic"), ("--id", "ep-1.1", "--parent", "ep-1", "Track"),
                     ("--id", "loose", "Loose")):
            created = gw(self.root, "task", "create", *argv, "--json")
            self.assertEqual(0, created.returncode, created.stderr)

    def status(self, bead):
        return json.loads(gw(self.root, "task", "show", bead, "--json").stdout)[0]["status"]

    def test_us7_unreviewed_track_is_refused(self):
        self.init(ledger=True)
        closed = gw(self.root, "task", "close", "ep-1.1", "--reason", "done")
        self.assertEqual(2, closed.returncode, closed.stderr)
        self.assertIn("ep-1.1: review ledger not approved (no review ledger)", closed.stderr)
        self.assertEqual("open", self.status("ep-1.1"))

    def test_us7_waiver_is_recorded_and_the_track_closes(self):
        self.init(ledger=True)
        closed = gw(self.root, "task", "close", "ep-1.1", "--waive-review", "spike, no code", "--actor", "u")
        self.assertEqual(0, closed.returncode, closed.stderr)
        self.assertEqual("closed", self.status("ep-1.1"))
        events = WorkflowEventStore(self.root / ".agent-workflow/runtime/events.jsonl").read_all()
        self.assertEqual([("ep-1.1", "ep-1", "spike, no code", "u")],
                         [(e.task_id, e.workflow_id, e.payload["reason"], e.actor)
                          for e in events if e.event_type == "review.waived"])

    def test_us7_waiver_needs_a_reason_and_an_actor(self):
        self.init(ledger=True)
        self.assertIn("--waive-review needs", close_guard.check(self.root, ["close", "ep-1.1", "--waive-review", " "])[1])

    def test_us7_every_id_is_checked_even_after_a_flag_value(self):
        self.init(ledger=True)
        error = close_guard.check(self.root, ["close", "loose", "--reason", "x", "ep-1.1"])[1]
        self.assertIn("ep-1.1: review ledger not approved", error)

    def test_us7_dash_value_is_not_an_error(self):
        self.init(ledger=True)
        argv = ["close", "loose", "--reason", "-done"]
        self.assertEqual((argv, None), close_guard.check(self.root, argv))

    def test_us7_flag_without_value_is_left_to_the_backend(self):
        self.init(ledger=True)
        argv = ["close", "loose", "--reason"]
        self.assertEqual((argv, None), close_guard.check(self.root, argv))

    def test_us7_abbreviated_flag_is_not_waive_review(self):
        self.init(ledger=True)
        error = close_guard.check(self.root, ["close", "ep-1.1", "--wa=x"])[1]
        self.assertIn("ep-1.1: review ledger not approved", error)

    def test_us7_waiver_forwards_the_rest_untouched(self):
        self.init(ledger=True)
        with mock.patch.object(close_guard, "_record_waiver") as record:
            result = close_guard.check(self.root, ["close", "ep-1.1", "--session", "S", "--waive-review=why",
                                                   "--actor", "u", "--reason", "-d"])
        self.assertEqual((["close", "ep-1.1", "--session", "S", "--reason", "-d"], None), result)
        record.assert_called_once_with(self.root, "ep-1.1", "ep-1", "why", "u")

    def test_us7_standalone_bead_closes_as_today(self):
        self.init(ledger=True)
        self.assertEqual((["close", "loose"], None), close_guard.check(self.root, ["close", "loose"]))

    def test_us7_ledger_off_closes_as_today(self):
        self.init(ledger=False)
        self.assertEqual((["close", "ep-1.1", "--reason", "done"], None),
                         close_guard.check(self.root, ["close", "ep-1.1", "--reason", "done"]))
        argv = ["close", "ep-1.1", "--session", "S", "--reason", "-done", "--actor=me"]
        self.assertEqual((argv, None), close_guard.check(self.root, argv))

    def test_us7_approved_ledger_closes(self):
        self.init(ledger=True)
        with mock.patch.object(close_guard, "_review_state", return_value=None):
            self.assertEqual((["close", "ep-1.1"], None), close_guard.check(self.root, ["close", "ep-1.1"]))
