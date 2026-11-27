"""`gin goal`: a /goal over the epic tracks the agent can finish unattended."""

from __future__ import annotations

import io
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from team_fixtures import git, make_team_repo  # noqa: E402
from workflow_core.cli import main as cli_main  # noqa: E402
from workflow_core.goal import goal_text  # noqa: E402


def track(bead, status="open", labels=(), blocked_by=(), assignee="", description="", title=None):
    return {"id": bead, "title": title or f"title {bead}", "status": status, "labels": list(labels),
            "assignee": assignee, "description": description,
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
        # implementation_complete needs every track closed, so it cannot hold while a held track stays open.
        self.assertNotIn("implementation_complete", text)
        self.assertIn("`python3 review-ledger.py status --bead-id <id>`", text)
        self.assertIn("are closed in Beads (`gin task show`). Do not start",
                      goal_text("epic", tracks, "wf", False))

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


def lane_desc(lane, number=1):
    return f"Plan: p.md, Track {number}\nLane: {lane}"


class TestGoalTeam(unittest.TestCase):
    ME = "a@corp.com"

    def lane_bead(self, bead: str, name: str, assignee: str = "a@corp.com"):
        return track(bead, assignee=assignee, title=f"Lane {name}: scope",
                     description=f"Plan: p.md, Lane {name}\nLane: {name}")

    def test_only_lane_beads_left_say_to_plan_each_lane(self):
        text = goal_text("epic", [self.lane_bead("e.1", "be"), self.lane_bead("e.2", "fe"), track("e.3", "closed")],
                         "wf", False, member=self.ME)
        self.assertEqual("No goal: lane be has no tracks yet; run /plan for it.\n"
                         "No goal: lane fe has no tracks yet; run /plan for it.", text)
        self.assertEqual("No goal: lane fe has no tracks yet; run /plan for it.",
                         goal_text("epic", [self.lane_bead("e.1", "be"), self.lane_bead("e.2", "fe")], "wf", False,
                                   member=self.ME, lane="fe"))

    def test_a_lane_bead_is_never_a_track_of_the_goal(self):
        tracks = [self.lane_bead("e.1", "be"), track("e.2", assignee=self.ME, description=lane_desc("fe", 2))]
        text = goal_text("epic", tracks, "wf", False, member=self.ME)
        self.assertTrue(text.startswith("/goal tracks e.2 of epic epic"), text)
        self.assertNotIn("e.1", text)

    def test_another_members_lane_bead_gives_the_usual_line(self):
        self.assertEqual("No goal: a@corp.com has no open track in epic epic.",
                         goal_text("epic", [self.lane_bead("e.1", "be", "b@corp.com")], "wf", False, member=self.ME))

    def test_member_goal_covers_only_their_tracks(self):
        tracks = [track("e.1", assignee=self.ME), track("e.2", assignee=self.ME), track("e.3", assignee="b@corp.com")]
        text = goal_text("epic", tracks, "wf", False, member=self.ME)
        self.assertIn("tracks e.1, e.2 of epic epic", text)
        self.assertNotIn("e.3", text)
        self.assertIn("`git status -sb`", text)
        self.assertIn("not ahead of `origin", text)
        self.assertNotIn("implementation_complete", text)

    def test_lane_covers_own_and_unassigned_tracks_of_that_lane(self):
        tracks = [track("e.1", assignee=self.ME, description=lane_desc("be")),
                  track("e.2", description=lane_desc("be", 2)),
                  track("e.3", assignee=self.ME, description=lane_desc("fe", 3)),
                  track("e.4", description=lane_desc("be", 4), assignee="b@corp.com")]
        text = goal_text("epic", tracks, "wf", False, member=self.ME, lane="be")
        self.assertIn("tracks e.1, e.2 of epic epic", text)
        self.assertNotIn("e.3", text)
        self.assertNotIn("e.4", text)

    def test_tracks_behind_a_waiting_lane_are_not_started(self):
        tracks = [track("e.1", assignee=self.ME), track("e.2", assignee=self.ME, blocked_by=["x.1"]),
                  track("e.3", assignee=self.ME, blocked_by=["e.2"])]
        text = goal_text("epic", tracks, "wf", False, member=self.ME, waiting=frozenset({"x.1"}))
        self.assertIn("tracks e.1 of epic epic", text)
        self.assertTrue(text.endswith(" Do not start e.2, e.3: they wait for another lane to merge."))

    def test_human_and_waiting_sentences_come_in_that_order(self):
        tracks = [track("e.1", assignee=self.ME), track("e.2", assignee=self.ME, labels=["human-gate"]),
                  track("e.3", assignee=self.ME, blocked_by=["x.1"])]
        text = goal_text("epic", tracks, "wf", False, member=self.ME, waiting=frozenset({"x.1"}))
        self.assertLess(text.index("e.2: they need a human"), text.index("e.3: they wait for another lane"))

    def test_nothing_assigned(self):
        self.assertEqual("No goal: a@corp.com has no open track in epic epic.",
                         goal_text("epic", [track("e.1", assignee="b@corp.com")], "wf", False, member=self.ME))
        self.assertEqual("No goal: a@corp.com has no open track in lane be of epic epic.",
                         goal_text("epic", [track("e.1", assignee=self.ME)], "wf", False, member=self.ME, lane="be"))

    def test_everything_waits(self):
        text = goal_text("epic", [track("e.1", assignee=self.ME, blocked_by=["x.1"])], "wf", False,
                         member=self.ME, waiting=frozenset({"x.1"}))
        self.assertEqual("No goal: every open track of epic epic assigned to a@corp.com waits on a human "
                         "or on another lane to merge: e.1.", text)

    def test_external_bead_is_never_named(self):
        tracks = [track("e.1", assignee=self.ME), track("x.1", assignee=self.ME, title="external: p.md#2")]
        self.assertNotIn("x.1", goal_text("epic", tracks, "wf", False, member=self.ME))


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

    def run_team_goal(self, email, *extra):
        self.record("epic")
        team = make_team_repo(Path(self.tmp.name) / "team", email=email)
        shutil.copy(team / ".agent-workflow/config.yaml", self.repo / ".agent-workflow/config.yaml")
        git(self.repo, "init", "-q", "-b", "main")
        git(self.repo, "config", "user.email", email)
        beads = lambda root, argv: [track("e.1", assignee="binh@corp.com", description=lane_desc("be")),
                                    track("e.2", assignee="chi@corp.com", description=lane_desc("fe", 2))]
        with patch("workflow_core.goal.query", beads), patch("sys.stdout", new=io.StringIO()) as out, \
                patch("sys.stderr", new=io.StringIO()) as err:
            code = cli_main(["goal", "--workflow-id", "wf", "--repository", str(self.repo), *extra])
        return code, out.getvalue(), err.getvalue()

    def test_team_mode_passes_the_member(self):
        code, out, _ = self.run_team_goal("binh@corp.com")
        self.assertEqual(0, code)
        self.assertIn("tracks e.1 of epic epic", out)
        self.assertNotIn("e.2", out)

    def test_team_mode_lane_option(self):
        code, out, _ = self.run_team_goal("binh@corp.com", "--lane", "fe")
        self.assertEqual(0, code)
        self.assertIn("has no open track in lane fe of epic epic", out)

    def test_team_mode_rejects_a_stranger(self):
        code, out, err = self.run_team_goal("who@else.com")
        self.assertEqual(1, code)
        self.assertIn("error: git user.email is not in team.members", err)

    def test_lane_needs_team_mode(self):
        self.record("epic")
        with patch("sys.stderr", new=io.StringIO()) as err:
            with patch("workflow_core.goal.query", lambda root, argv: [track("e.1")]):
                code = cli_main(["goal", "--workflow-id", "wf", "--repository", str(self.repo), "--lane", "be"])
        self.assertEqual(1, code)
        self.assertIn("error: --lane needs team mode", err.getvalue())

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
