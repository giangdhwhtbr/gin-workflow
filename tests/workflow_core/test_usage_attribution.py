"""Usage attribution: each record goes to one (owner, stage) by worktree, review interval, or the next gate event."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from team_fixtures import git  # noqa: E402
from workflow_core.events import WorkflowEvent  # noqa: E402
from workflow_core.usage_attribution import (  # noqa: E402
    UNATTRIBUTED, BeadSpan, Gate, Worktree, attribute, gates_from_events, review_intervals, worktrees,
)
from workflow_core.usage_logs import UsageRecord  # noqa: E402

REPO = Path("/r/repo")
TREE = Worktree(REPO / ".planning/worktrees/ep1", "feat/ep1")
DAY = datetime(2026, 10, 4, tzinfo=timezone.utc)


def at(hour: float) -> datetime:
    return DAY + timedelta(hours=hour)


def rec(hour: float, cwd: Path = REPO, branch: str = "master") -> UsageRecord:
    return UsageRecord(at(hour), "claude_code", "m", "s", str(cwd), branch, 1, 1, 0, 0)


def event(event_type: str, workflow: str, hour: float, payload: dict | None = None) -> WorkflowEvent:
    return WorkflowEvent.create(event_type=event_type, workflow_id=workflow, payload=payload or {},
                                timestamp=at(hour).isoformat().replace("+00:00", "Z"))


def owners(groups) -> dict:
    return {key: len(value) for key, value in groups.items()}


class GateTests(unittest.TestCase):
    def test_gate_events_and_epics(self):
        approved = {"action": "plan_approved", "decision": {"status": "approved"}}
        gates, epic_of = gates_from_events([
            event("requirement.confirmed", "wf", 1),
            event("approval.recorded", "wf", 2, approved),
            event("approval.recorded", "wf", 2.5, {"action": "other", "decision": {"status": "approved"}}),
            event("orchestration.ready", "wf", 3, {"epic": "ep1"}),
            event("worker.completed", "wf", 3.5),
            event("gate.waived", "wf", 3.6),
            event("review.approved", "wf", 3.7),
            event("quick.completed", "q1", 3.8),
            event("verification.passed", "wf", 4),
            event("delivery.shipped", "wf", 5),
        ])
        self.assertEqual([(g.stage, g.workflow_id) for g in gates],
                         [("discuss", "wf"), ("plan", "wf"), ("orchestrate", "wf"), ("quick", "q1"),
                          ("verify", "wf"), ("ship", "wf")])
        self.assertEqual(epic_of, {"wf": "ep1"})


class ReviewIntervalTests(unittest.TestCase):
    def test_intervals_from_ledger_events(self):
        def entry(action, hour):
            return {"action": action, "timestamp": at(hour).isoformat().replace("+00:00", "Z")}
        ledger = {"events": [entry("ledger-created", 1), entry("review-requested", 2), entry("review-started", 2.1),
                             entry("changes-requested", 3), entry("review-requested", 4),
                             entry("review-approved", 5), entry("review-requested", 6)]}
        now = at(7)
        self.assertEqual(review_intervals(ledger, now=now), ((at(2), at(3)), (at(4), at(5)), (at(6), now)))
        self.assertEqual(review_intervals({}, now=now), ())


class AttributeTests(unittest.TestCase):
    def setUp(self):
        self.spans = {
            "ep1": BeadSpan("ep1", None, None, None),
            "ep1.1": BeadSpan("ep1.1", "ep1", at(9), at(10), review=((at(9.5), at(9.75)),)),
            "ep1.2": BeadSpan("ep1.2", "ep1", at(10.5), at(11)),
        }
        self.gates = [Gate(at(1), "wf", "discuss"), Gate(at(2), "wf", "plan"), Gate(at(3), "wf", "orchestrate"),
                      Gate(at(12), "wf", "verify")]
        self.epic_of = {"wf": "ep1"}

    def run_one(self, record, **kwargs):
        options = dict(repo=REPO, spans=self.spans, trees=[TREE], gates=self.gates, epic_of=self.epic_of, now=at(20))
        options.update(kwargs)
        return owners(attribute([record], **options))

    def test_worktree_record_goes_to_the_track_in_its_span(self):
        self.assertEqual(self.run_one(rec(9.25, TREE.path / "src")), {("ep1.1", "execute"): 1})
        self.assertEqual(self.run_one(rec(9.6, TREE.path)), {("ep1.1", "review"): 1})
        self.assertEqual(self.run_one(rec(10.75, TREE.path)), {("ep1.2", "execute"): 1})

    def test_worktree_record_outside_any_track_goes_to_the_worktree_owner(self):
        self.assertEqual(self.run_one(rec(10.25, TREE.path)), {("ep1", "execute"): 1})

    def test_overlapping_tracks_go_to_the_worktree_owner(self):
        self.spans["ep1.2"] = BeadSpan("ep1.2", "ep1", at(9.5), None)
        self.assertEqual(self.run_one(rec(9.8, TREE.path)), {("ep1", "execute"): 1})

    def test_open_track_holds_records_until_now(self):
        self.spans["ep1.2"] = BeadSpan("ep1.2", "ep1", at(10.5), None)
        self.assertEqual(self.run_one(rec(15, TREE.path)), {("ep1.2", "execute"): 1})

    def test_branch_match_counts_as_the_worktree(self):
        self.assertEqual(self.run_one(rec(9.25, REPO, "feat/ep1")), {("ep1.1", "execute"): 1})

    def test_root_records_go_to_the_next_gate(self):
        self.assertEqual(self.run_one(rec(0.5)), {("ep1", "discuss"): 1})
        self.assertEqual(self.run_one(rec(1.5)), {("ep1", "plan"): 1})
        self.assertEqual(self.run_one(rec(11)), {("ep1", "verify"): 1})

    def test_workflow_without_an_epic_owns_its_records(self):
        self.assertEqual(self.run_one(rec(0.5), epic_of={}), {("wf", "discuss"): 1})

    def test_after_the_last_gate_ship_while_collecting_a_verified_epic(self):
        self.assertEqual(self.run_one(rec(13), collecting="ep1"), {("ep1", "ship"): 1})
        self.assertEqual(self.run_one(rec(13)), {(UNATTRIBUTED, ""): 1})
        self.assertEqual(self.run_one(rec(13), collecting="other"), {(UNATTRIBUTED, ""): 1})

    def test_not_verified_epic_does_not_take_ship(self):
        self.gates = self.gates[:3]
        self.assertEqual(self.run_one(rec(5), collecting="ep1"), {(UNATTRIBUTED, ""): 1})


class WorktreeListTests(unittest.TestCase):
    def test_lists_only_planning_worktrees(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            git(root, "init", "-q", "-b", "main")
            git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "x")
            git(root, "worktree", "add", "-q", "-b", "feat/ep1", str(root / ".planning/worktrees/ep1"))
            git(root, "worktree", "add", "-q", "-b", "other", str(Path(tmp) / "elsewhere"))
            found = worktrees(root)
            self.assertEqual([(t.path.name, t.branch) for t in found], [("ep1", "feat/ep1")])

    def test_not_a_git_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(worktrees(Path(tmp)), [])


if __name__ == "__main__":
    unittest.main()
