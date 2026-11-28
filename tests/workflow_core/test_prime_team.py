"""`gin prime` in team mode: member, claimed lane, waiting pull requests, and the shared gates."""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest import mock

from workflow_core import lifecycle_cli, prime
from workflow_core.team import Member
from tests.workflow_core.team_fixtures import make_team_repo

MEMBER = Member("binh@corp.com", ("dev",), "binh", "")


class PrimeTeamTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = make_team_repo(Path(directory.name).resolve() / "app")
        for target, value in (("workflow_core.team.require_member", mock.DEFAULT),
                              ("workflow_core.team_beads.ready", mock.DEFAULT),
                              ("workflow_core.team_pending.pending", mock.DEFAULT)):
            patcher = mock.patch(target)
            setattr(self, target.rsplit(".", 1)[1], patcher.start())
            self.addCleanup(patcher.stop)
        self.require_member.return_value = MEMBER
        self.ready.return_value = [
            {"id": "t-1", "title": "API", "assignee": "binh@corp.com", "lane": "api", "branch": "feat/x-api"},
            {"id": "t-2", "title": "UI", "assignee": "", "lane": "ui", "branch": "feat/x-ui"},
        ]
        self.pending.return_value = [{"gate": "plan_approved", "url": "https://github.com/org/app/pull/7",
                                      "branch": "plan/x", "missing": ["1 approval"]}]

    def prime(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), mock.patch("sys.stdin", io.StringIO("{}")):
            code = prime.main(["--repository", str(self.root), *argv])
        return code, out.getvalue()

    def test_member_lane_and_pull_requests(self):
        code, out = self.prime("--workflow-id", "wf-1")
        self.assertEqual(0, code)
        self.assertIn("Member: binh (roles: dev)", out)
        self.assertIn("Claimed lane: api (feat/x-api)", out)
        self.assertNotIn("ui (feat/x-ui)", out)
        self.assertIn("Pull requests waiting:\n  - plan_approved https://github.com/org/app/pull/7 missing: 1 approval",
                      out)

    def test_a_slow_host_does_not_hold_the_card(self):
        def slow(*args, **kwargs):
            time.sleep(1)
            return []

        self.pending.side_effect = slow
        with mock.patch.object(prime, "TEAM_TIMEOUT", 0.1):
            code, out = self.prime("--workflow-id", "wf-1")
        self.assertEqual(0, code)
        self.assertIn("Pull requests waiting: not checked (timed out after 0.1s); run gin team pending", out)
        self.assertIn("Member: binh", out)

    def test_a_host_failure_names_its_cause(self):
        self.pending.side_effect = RuntimeError("gh: not logged in")
        self.assertIn("Pull requests waiting: not checked (gh: not logged in); run gin team pending",
                      self.prime("--workflow-id", "wf-1")[1])

    def test_the_card_gates_are_the_shared_gates_of_gin_state(self):
        shared = ("ep-1", {"requirement_confirmed": {"pr_url": "u", "actor": "a", "at": "t"},
                           "plan_approved": {"pr_url": "u", "actor": "a", "at": "t"}}, None)
        with mock.patch("workflow_core.team_beads.shared_gates", return_value=shared), \
                mock.patch("workflow_core.lifecycle_cli.tasks_backend", return_value="beads"), \
                mock.patch("workflow_core.lifecycle_cli._delivery_state",
                           return_value=({"implementation_complete": False, "shipped": False}, False, None)):
            card = self.prime("--workflow-id", "wf-1")[1]
            gates = lifecycle_cli.state_payload(self.root, "wf-1", bind=False)[0]["gates"]
        line = "Gates: " + ", ".join(f"{gate}={status}" for gate, status in gates.items())
        self.assertIn("requirement_confirmed=satisfied, plan_approved=satisfied", line)
        self.assertIn(line, card)


if __name__ == "__main__":
    unittest.main()
