"""`gin goal`: a /goal over the epic tracks the agent can finish unattended."""

from __future__ import annotations

import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from workflow_core.cli import main as cli_main
from workflow_core.goal import goal_text


def track(bead, status="open", labels=(), blocked_by=()):
    return {"id": bead, "title": f"title {bead}", "status": status, "labels": list(labels),
            "dependencies": [{"depends_on_id": "epic", "type": "parent-child"}]
            + [{"depends_on_id": dep, "type": "blocks"} for dep in blocked_by]}


class TestGoalText(unittest.TestCase):
    def test_all_open_tracks_runnable(self):
        text = goal_text("epic", [track("e.1", "closed"), track("e.2"), track("e.3", blocked_by=["e.2"])], "wf-1", True)
        self.assertTrue(text.startswith("/goal "))
        self.assertIn("e.2, e.3", text)
        self.assertNotIn("e.1", text)
        self.assertNotIn("human", text)
        # The Stop-hook judge checks durable state shown by commands, never skill wording or turn counts.
        self.assertNotIn("turns", text)
        self.assertNotIn("/gin:execute", text)
        self.assertIn("closed in Beads (`gin task show`)", text)
        self.assertIn("`gin state --workflow-id wf-1 --format json`", text)
        self.assertIn("`implementation_complete`", text)
        self.assertIn("`python3 review-ledger.py status --bead-id <id>`", text)
        self.assertIn("`review-approved` or later", text)
        self.assertIn("`review_waivers`", text)

    def test_ledger_off_has_no_review_clause(self):
        text = goal_text("epic", [track("e.2")], "wf-1", False)
        self.assertIn("`implementation_complete` satisfied.", text)
        for word in ("review", "waivers"):
            self.assertNotIn(word, text)

    def test_human_gate_and_its_dependents_are_left_out(self):
        tracks = [track("e.1"), track("e.2", blocked_by=["e.1"]), track("e.3", labels=["human-gate"]),
                  track("e.4", blocked_by=["e.3"]), track("e.5", blocked_by=["e.4"])]
        text = goal_text("epic", tracks, "wf", True)
        self.assertIn("e.1, e.2 of epic epic", text)
        self.assertIn("Do not start e.3, e.4, e.5", text)
        self.assertNotIn("turns", text)

    def test_tracks_listed_in_dependency_order(self):
        text = goal_text("epic", [track("e.3", blocked_by=["e.2"]), track("e.2", blocked_by=["e.1"]), track("e.1")], "wf", True)
        self.assertIn("tracks e.1, e.2, e.3 of", text)

    def test_no_goal_when_only_human_work_is_left(self):
        text = goal_text("epic", [track("e.1", "closed"), track("e.2", labels=["human-gate"]),
                                  track("e.3", blocked_by=["e.2"])], "wf", True)
        self.assertFalse(text.startswith("/goal"))
        self.assertIn("e.2 (title e.2)", text)

    def test_no_goal_when_every_track_is_closed(self):
        self.assertFalse(goal_text("epic", [track("e.1", "closed")], "wf", True).startswith("/goal"))


class TestGoalCommand(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        (self.repo / ".agent-workflow").mkdir()
        (self.repo / ".agent-workflow/config.yaml").write_text("schema_version: '2.3'\n")

    def tearDown(self):
        self.tmp.cleanup()

    def run_goal(self, beads):
        with patch("workflow_core.goal.query", beads), patch("sys.stdout", new=io.StringIO()) as out:
            code = cli_main(["goal", "--workflow-id", "wf", "--repository", str(self.repo)])
        return code, out.getvalue()

    def record(self, epic):
        self.assertEqual(0, cli_main(["record", "orchestration-ready", "--workflow-id", "wf", "--epic", epic,
                                      "--evidence", "beads", "--actor", "user", "--repository", str(self.repo)]))

    def test_fails_without_recorded_epic(self):
        with patch("sys.stderr", new=io.StringIO()):
            code, _ = self.run_goal(lambda root, argv: [])
        self.assertEqual(1, code)

    def test_review_clause_follows_review_ledger_setting(self):
        self.record("epic")
        _, out = self.run_goal(lambda root, argv: [track("e.1")])
        self.assertNotIn("review", out)
        (self.repo / ".agent-workflow/config.yaml").write_text("schema_version: '2.3'\nproject:\n  review_ledger: true\n")
        _, out = self.run_goal(lambda root, argv: [track("e.1")])
        self.assertIn("review-ledger.py status", out)

    def test_epic_children_become_the_goal(self):
        self.record("epic")
        code, out = self.run_goal(lambda root, argv: [track("e.1"), track("e.2", labels=["human-gate"])])
        self.assertEqual(0, code)
        self.assertIn("/goal tracks e.1 of epic epic", out)

    def test_standalone_bead_is_its_own_track(self):
        self.record("bead")
        beads = lambda root, argv: [] if argv[0] == "list" else [{**track("bead"), "dependencies": []}]
        code, out = self.run_goal(beads)
        self.assertEqual(0, code)
        self.assertIn("/goal tracks bead of epic bead", out)
        self.assertNotIn("turns", out)

    def test_gin_goal_lists_no_prep_task(self):
        self.record("epic")
        prep_track = {**track("e.prep", labels=["prep", "prep:capture"])}
        regular_track = track("e.1")
        code, out = self.run_goal(lambda root, argv: [prep_track, regular_track])
        self.assertEqual(0, code)
        self.assertIn("/goal tracks e.1 of epic epic", out)
        self.assertNotIn("e.prep", out)

    def test_epic_with_only_prep_children_prints_line_for_epic_without_children(self):
        self.record("epic")
        prep_track = {**track("e.prep", labels=["prep", "prep:mockup"])}
        def beads(root, argv):
            if argv[0] == "list":
                return [prep_track]
            return [{**track("epic"), "dependencies": []}]
        code, out = self.run_goal(beads)
        self.assertEqual(0, code)
        self.assertIn("/goal tracks epic of epic epic", out)
        self.assertNotIn("e.prep", out)

    def test_goal_uses_tracks_of(self):
        from unittest.mock import patch
        from workflow_core import prep
        self.record("epic")
        with patch("workflow_core.goal.tracks_of", wraps=prep.tracks_of) as mock_tracks_of:
            code, out = self.run_goal(lambda root, argv: [track("e.1")])
            self.assertEqual(0, code)
            mock_tracks_of.assert_called()


if __name__ == "__main__":
    unittest.main()
