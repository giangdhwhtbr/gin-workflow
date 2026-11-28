"""`gin prime`: the state card a Claude Code session sees at start, after /clear, on resume, and after compaction."""

from __future__ import annotations

import contextlib
from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest import mock

from workflow_core import prime
from workflow_core.events import WorkflowEvent, WorkflowEventStore
from workflow_core.session_binding import SESSION_VARIABLE

SESSION = "0a1b2c3d-1111-2222-3333-444455556666"
OTHER = "0a1b2c3d-1111-2222-3333-777788889999"
THIRD = "0a1b2c3d-1111-2222-3333-aaaabbbbcccc"


class PrimeCase(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        (self.root / ".agent-workflow/runtime").mkdir(parents=True)
        (self.root / ".agent-workflow/config.yaml").write_text("schema_version: '2.3'\n", encoding="utf-8")
        self.log = self.root / ".agent-workflow/runtime/events.jsonl"
        env = {key: value for key, value in os.environ.items() if key != SESSION_VARIABLE}
        patcher = mock.patch.dict(os.environ, env, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def add(self, event_type, workflow_id, payload=None, days_ago=0):
        stamp = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat().replace("+00:00", "Z")
        WorkflowEventStore(self.log).append(WorkflowEvent.create(
            event_type=event_type, workflow_id=workflow_id, payload=payload or {}, timestamp=stamp,
            idempotency_key=f"{event_type}:{workflow_id}:{stamp}"))

    def bind(self, workflow_id, session_id, cwd=None):
        self.add("session.bound", workflow_id, {"session_id": session_id, "cwd": cwd or str(self.root)})

    def prime(self, *argv, stdin=""):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch("sys.stdin", io.StringIO(stdin)), contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(err):
            code = prime.main(["--repository", str(self.root), *argv])
        return code, out.getvalue(), err.getvalue()


class ResolveTests(PrimeCase):
    def test_prints_nothing_outside_a_gin_project(self):
        (self.root / ".agent-workflow/config.yaml").unlink()
        self.assertEqual((0, ""), self.prime("--hook", stdin="{}")[:2])

    def test_the_flag_comes_first(self):
        self.bind("wf-session", SESSION)
        code, out, _ = self.prime("--workflow-id", "wf-flag")
        self.assertEqual(0, code)
        self.assertIn("gin state card (workflow found by: flag)", out)
        self.assertIn("Workflow: wf-flag", out)
        self.assertIn("Next: /gin:discuss wf-flag", out)

    def test_the_hook_input_session_comes_next(self):
        self.bind("wf-folder", OTHER)
        self.bind("wf-session", SESSION, cwd="/elsewhere")
        out = self.prime("--hook", stdin=json.dumps({"session_id": SESSION, "source": "compact"}))[1]
        self.assertIn("workflow found by: this session", out)
        self.assertIn("Workflow: wf-session", out)

    def test_without_hook_the_session_comes_from_the_environment(self):
        self.bind("wf-session", SESSION, cwd="/elsewhere")
        with mock.patch.dict(os.environ, {SESSION_VARIABLE: SESSION}):
            out = self.prime()[1]
        self.assertIn("Workflow: wf-session", out)

    def test_a_cleared_session_gets_the_last_workflow_of_its_folder(self):
        self.bind("wf-old", OTHER)
        self.bind("wf-new", THIRD)
        out = self.prime("--hook", stdin=json.dumps({"session_id": SESSION, "source": "clear"}))[1]
        self.assertIn("workflow found by: last session in this folder", out)
        self.assertIn("Workflow: wf-new", out)

    def test_a_shipped_workflow_is_skipped_and_the_open_ones_are_listed(self):
        self.bind("wf-done", OTHER)
        self.add("delivery.shipped", "wf-done", {"evidence": "abc123"})
        self.add("requirement.confirmed", "wf-open", {"evidence": "spec.md"})
        out = self.prime("--hook", stdin=json.dumps({"session_id": SESSION}))[1]
        self.assertIn("no workflow is bound to this session or this folder", out)
        self.assertIn("  - wf-open: plan, next: /gin:plan wf-open", out)
        self.assertNotIn("wf-done", out)

    def test_a_workflow_whose_epic_is_closed_is_shipped(self):
        self.bind("wf-epic", OTHER)
        self.add("orchestration.ready", "wf-epic", {"epic": "ep-1", "evidence": "plan.md"})

        def answer(root, argv, timeout=30):
            return ([{"id": "ep-1", "status": "closed"}], None) if argv[0] == "show" else ([], None)

        with mock.patch("workflow_core.tasks.query_result", side_effect=answer):
            out = self.prime("--hook", stdin=json.dumps({"session_id": SESSION}))[1]
        self.assertIn("no workflow is bound", out)
        self.assertNotIn("wf-epic", out)

    def test_with_beads_one_list_call_finds_the_closed_epics(self):
        # bd show takes about a second per id; bd list --id answers for all of them at once
        self.add("orchestration.ready", "wf-a", {"epic": "ep-a", "evidence": "plan.md"})
        self.add("orchestration.ready", "wf-b", {"epic": "ep-b", "evidence": "plan.md"})
        calls = []

        def answer(root, argv, timeout=30):
            calls.append(list(argv))
            return [{"id": "ep-a", "status": "closed"}], None

        with mock.patch.object(prime, "_uses_beads", return_value=True), \
                mock.patch("workflow_core.tasks.query_result", side_effect=answer):
            shipped = prime.shipped_among(self.root, prime._events(self.root)[0], ["wf-a", "wf-b"])
        self.assertEqual({"wf-a"}, shipped)
        self.assertEqual([["list", "--status", "closed", "--limit", "0", "--id", "ep-a,ep-b"]], calls)

    def test_a_workflow_idle_for_more_than_14_days_is_not_listed(self):
        self.add("requirement.confirmed", "wf-stale", {"evidence": "spec.md"}, days_ago=30)
        out = self.prime("--hook", stdin="{}")[1]
        self.assertIn("Open workflows: none; start one with /gin:discuss", out)

    def test_bad_hook_input_is_ignored(self):
        self.assertEqual(0, self.prime("--hook", stdin="not json")[0])


class CardTests(PrimeCase):
    def test_spec_and_plan_come_from_the_gate_events(self):
        self.add("requirement.confirmed", "wf-1", {"evidence": ".planning/specs/x-design.md"})
        self.add("approval.recorded", "wf-1", {"action": "plan_approved", "decision": {"status": "approved"},
                                               "evidence": ".planning/plans/x.md"})
        out = self.prime("--workflow-id", "wf-1")[1]
        self.assertIn("Spec: .planning/specs/x-design.md", out)
        self.assertIn("Plan: .planning/plans/x.md", out)
        self.assertIn("Gates: requirement_confirmed=satisfied, plan_approved=satisfied, orchestration_ready=unmet", out)
        self.assertIn("Next: /gin:orchestrate wf-1", out)

    def test_next_command(self):
        cases = [
            ({"decision": "route", "stage": "plan"}, [], "/gin:plan wf"),
            ({"decision": "route", "stage": "execute"}, ["t-1", "t-2"], "/gin:execute t-1 t-2"),
            ({"decision": "route", "stage": "execute"}, [], "/gin:workflow wf"),
            ({"decision": "hold", "stage": "progress"}, [], "/gin:workflow wf"),
            ({"decision": "complete", "stage": "progress"}, [], None),
        ]
        for state, ready, expected in cases:
            with self.subTest(state=state, ready=ready):
                self.assertEqual(expected, prime.next_command("wf", state, ready))

    def test_the_card_writes_nothing(self):
        self.bind("wf-1", OTHER)
        before = self.log.read_bytes()
        with mock.patch.dict(os.environ, {SESSION_VARIABLE: SESSION}):
            self.prime("--workflow-id", "wf-2")
        self.assertEqual(before, self.log.read_bytes())

    def test_a_timed_out_state_marks_only_its_lines(self):
        def slow(*args, **kwargs):
            time.sleep(1)
            return {}, 0

        with mock.patch.object(prime, "ROUND_TIMEOUT", 0.1), \
                mock.patch("workflow_core.lifecycle_cli.state_payload", side_effect=slow):
            code, out, _ = self.prime("--workflow-id", "wf-1")
        self.assertEqual(0, code)
        self.assertIn("Stage: unknown (timed out after 0.1s)", out)
        self.assertIn("Workflow: wf-1", out)
        self.assertNotIn("Next:", out)

    def test_a_failed_ready_call_marks_only_its_line(self):
        self.add("orchestration.ready", "wf-1", {"epic": "ep-1", "evidence": "plan.md"})
        with mock.patch("workflow_core.tasks.query_result", return_value=(None, "bd exited 1")):
            out = self.prime("--workflow-id", "wf-1")[1]
        self.assertIn("Ready tracks: unknown (bd exited 1)", out)
        self.assertIn("Workflow: wf-1 (epic ep-1", out)


class HookModeTests(PrimeCase):
    def test_pre_compact_makes_no_beads_call_and_fits(self):
        self.bind("wf-1", SESSION)
        with mock.patch("workflow_core.tasks.query_result", side_effect=AssertionError("no Beads call")), \
                mock.patch.dict(os.environ, {SESSION_VARIABLE: SESSION}):
            code, out, err = self.prime("--pre-compact")
        self.assertEqual((0, ""), (code, err))
        self.assertLessEqual(len(out.rstrip("\n")), prime.PRE_COMPACT_CAP)
        self.assertIn("wf-1", out)
        self.assertIn("word for word", out)

    def test_a_refusing_version_pin_is_silent_in_the_hook_and_an_error_otherwise(self):
        (self.root / ".ginrc").write_text("99.0.0\n", encoding="utf-8")
        self.assertEqual((0, "", ""), self.prime("--hook", stdin="{}"))
        code, out, err = self.prime()
        self.assertEqual((2, ""), (code, out))
        self.assertIn("error:", err)


if __name__ == "__main__":
    unittest.main()
