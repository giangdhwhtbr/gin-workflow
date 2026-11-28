"""`gin prime`: the state card a Claude Code session sees at start, after /clear, on resume, and after compaction."""

from __future__ import annotations

import contextlib
from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
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
            shipped = prime.shipped_among(self.root, prime._events(self.root)[0], ["wf-a", "wf-b"], timeout=3)
        self.assertEqual({"wf-a"}, shipped)
        self.assertEqual([["list", "--status", "closed", "--limit", "0", "--id", "ep-a,ep-b"]], calls)

    def test_the_folder_check_before_the_round_has_the_short_timeout(self):
        self.bind("wf-folder", OTHER)
        self.add("orchestration.ready", "wf-folder", {"epic": "ep-f", "evidence": "plan.md"})
        timeouts = {}

        def answer(root, argv, timeout=30):
            timeouts.setdefault(argv[0], timeout)
            return [], None

        with mock.patch("workflow_core.tasks.query_result", side_effect=answer):
            out = self.prime("--hook", stdin=json.dumps({"session_id": SESSION}))[1]
        self.assertIn("Workflow: wf-folder", out)
        self.assertEqual(prime.CALL_TIMEOUT, timeouts["show"])

    def test_a_workflow_idle_for_more_than_14_days_is_not_listed(self):
        self.add("requirement.confirmed", "wf-stale", {"evidence": "spec.md"}, days_ago=30)
        out = self.prime("--hook", stdin="{}")[1]
        self.assertIn("Open workflows: none; start one with /gin:discuss", out)

    def test_bad_hook_input_is_ignored(self):
        self.assertEqual(0, self.prime("--hook", stdin="not json")[0])

    def test_an_invalid_session_id_in_the_hook_input_is_ignored(self):
        self.bind("wf-folder", OTHER)
        for bad in ("../x", "a" * 200):
            with self.subTest(session_id=bad[:10]):
                self.add("session.bound", "wf-bad", {"session_id": bad, "cwd": "/elsewhere"})
                out = self.prime("--hook", stdin=json.dumps({"session_id": bad}))[1]
                self.assertIn("workflow found by: last session in this folder", out)
                self.assertIn("Workflow: wf-folder", out)
                self.assertNotIn("wf-bad", out)

    def test_a_failed_folder_check_marks_the_other_workflows_unknown(self):
        self.bind("wf-folder", OTHER)
        self.add("orchestration.ready", "wf-2", {"epic": "ep-2", "evidence": "plan.md"})

        def answer(root, argv, timeout=30):
            return (None, "bd timed out after 4s") if argv == ["show", "ep-2"] else ([], None)

        with mock.patch("workflow_core.tasks.query_result", side_effect=answer):
            out = self.prime("--hook", stdin=json.dumps({"session_id": SESSION}))[1]
        self.assertIn("Workflow: wf-folder", out)
        self.assertIn("Other open workflows: unknown (bd timed out after 4s)", out)
        self.assertNotIn("wf-2", out)

    def test_a_failed_folder_check_marks_the_open_list_unknown(self):
        self.add("orchestration.ready", "wf-2", {"epic": "ep-2", "evidence": "plan.md"})
        with mock.patch("workflow_core.tasks.query_result", return_value=(None, "bd timed out after 4s")):
            out = self.prime("--hook", stdin=json.dumps({"session_id": SESSION}))[1]
        self.assertIn("no workflow is bound", out)
        self.assertIn("Open workflows: unknown (bd timed out after 4s)", out)
        self.assertNotIn("wf-2", out)


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

    def test_the_card_creates_no_runtime_directory(self):
        runtime = self.root / ".agent-workflow/runtime"
        shutil.rmtree(runtime)
        code, out, _ = self.prime("--workflow-id", "wf-x")
        self.assertEqual(0, code)
        self.assertIn("Gates: requirement_confirmed=unmet", out)
        self.assertFalse(runtime.exists())

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

    def test_beads_calls_in_the_round_wait_for_the_whole_round(self):
        # concurrent bd calls queue, so one call's timeout must cover the round
        self.add("orchestration.ready", "wf-1", {"epic": "ep-1", "evidence": "plan.md"})
        self.add("orchestration.ready", "wf-2", {"epic": "ep-2", "evidence": "plan.md"})
        timeouts = []

        def answer(root, argv, timeout=30):
            if argv[0] == "ready" or argv == ["show", "ep-2"]:
                timeouts.append((argv[0], timeout))
            return [], None

        with mock.patch("workflow_core.tasks.query_result", side_effect=answer):
            self.prime("--workflow-id", "wf-1")
        self.assertEqual([("ready", prime.ROUND_TIMEOUT), ("show", prime.ROUND_TIMEOUT)], sorted(timeouts))

    def test_a_failed_shipped_check_marks_the_other_workflows_unknown(self):
        self.add("orchestration.ready", "wf-1", {"epic": "ep-1", "evidence": "plan.md"})
        self.add("orchestration.ready", "wf-2", {"epic": "ep-2", "evidence": "plan.md"})
        self.add("requirement.confirmed", "wf-3", {"evidence": "spec.md"})

        def answer(root, argv, timeout=30):
            return (None, "bd exited 1") if argv == ["show", "ep-2"] else ([], None)

        with mock.patch("workflow_core.tasks.query_result", side_effect=answer):
            out = self.prime("--workflow-id", "wf-1")[1]
        self.assertIn("Other open workflows: unknown (bd exited 1)", out)
        self.assertNotIn("wf-2", out)
        self.assertNotIn("wf-3", out)
        self.assertIn("Workflow: wf-1 (epic ep-1", out)

    def test_a_spec_with_a_kind_line_makes_no_beads_call_for_the_kind(self):
        (self.root / "spec.md").write_text("# X\n\nKind: technical\n", encoding="utf-8")
        self.add("requirement.confirmed", "wf-1", {"evidence": "spec.md"})
        with mock.patch.object(prime.epic_kind, "lookup", side_effect=AssertionError("no Beads call")) as lookup:
            out = self.prime("--workflow-id", "wf-1")[1]
        lookup.assert_not_called()
        self.assertIn("Workflow: wf-1 (kind technical)", out)

    def test_a_kind_that_cannot_be_read_is_marked_unknown(self):
        cases = [({"return_value": ("capability", "bd exited 1")}, "kind unknown (bd exited 1)"),
                 ({"side_effect": prime.SourceError("bd timed out")}, "kind unknown (bd timed out)")]
        self.add("requirement.confirmed", "wf-1", {"evidence": "spec.md"})
        for behaviour, expected in cases:
            with self.subTest(expected=expected), mock.patch.object(prime.epic_kind, "lookup", **behaviour):
                out = self.prime("--workflow-id", "wf-1")[1]
            self.assertIn(f"Workflow: wf-1 ({expected})", out)

    def test_without_a_kind_line_the_kind_comes_from_beads(self):
        (self.root / "spec.md").write_text("# X\n", encoding="utf-8")
        self.add("requirement.confirmed", "wf-1", {"evidence": "spec.md"})
        with mock.patch.object(prime.epic_kind, "lookup", return_value=("parity", None)) as lookup:
            out = self.prime("--workflow-id", "wf-1")[1]
        lookup.assert_called_once_with(self.root, "wf-1", "spec.md")
        self.assertIn("Workflow: wf-1 (kind parity)", out)

    def test_a_failed_ready_call_marks_only_its_line(self):
        self.add("orchestration.ready", "wf-1", {"epic": "ep-1", "evidence": "plan.md"})
        with mock.patch("workflow_core.tasks.query_result", return_value=(None, "bd exited 1")):
            out = self.prime("--workflow-id", "wf-1")[1]
        self.assertIn("Ready tracks: unknown (bd exited 1)", out)
        self.assertIn("Workflow: wf-1 (epic ep-1", out)


class RoundTests(unittest.TestCase):
    def test_the_round_runs_its_jobs_in_order_on_one_thread(self):
        seen = []

        def job(name):
            def run():
                seen.append(("start", name, threading.get_ident()))
                time.sleep(0.02)
                seen.append(("end", name, threading.get_ident()))
                return name
            return run

        got = prime.bounded({"state": job("state"), "ready": job("ready"), "shipped": job("shipped")}, 5)
        self.assertEqual({"state": ("state", None), "ready": ("ready", None), "shipped": ("shipped", None)}, got)
        self.assertEqual([("start", "state"), ("end", "state"), ("start", "ready"), ("end", "ready"),
                          ("start", "shipped"), ("end", "shipped")], [(step, name) for step, name, _ in seen])
        threads = {ident for _, _, ident in seen}
        self.assertEqual(1, len(threads))
        self.assertNotIn(threading.get_ident(), threads)

    def test_both_budgets_leave_room_for_start_up_under_the_hook_timeout(self):
        self.assertLessEqual(prime.CALL_TIMEOUT + prime.ROUND_TIMEOUT, 13)

    def test_a_side_job_gives_its_value_its_error_or_a_timeout(self):
        def fails():
            raise prime.SourceError("host exited 1")

        self.assertEqual((7, None), prime._Background(lambda: 7).result(1))
        self.assertEqual((None, "host exited 1"), prime._Background(fails).result(1))
        self.assertEqual((None, "timed out after 0.1s"), prime._Background(lambda: time.sleep(1)).result(0.1))

    def test_a_job_past_the_budget_times_out_and_earlier_ones_keep_their_results(self):
        def fails():
            raise prime.SourceError("bd exited 1")

        got = prime.bounded({"state": lambda: 1, "ready": fails, "shipped": lambda: time.sleep(1),
                             "kind": lambda: 4}, 0.2)
        self.assertEqual((1, None), got["state"])
        self.assertEqual((None, "bd exited 1"), got["ready"])
        self.assertEqual((None, "timed out after 0.2s"), got["shipped"])
        self.assertEqual((None, "timed out after 0.2s"), got["kind"])


def beads(**answers):
    """Patches for a Beads project whose bd answers each subcommand from `answers` (default: an empty list)."""
    def answer(root, argv, timeout=30):
        value = answers.get(argv[0], [])
        return (None, value[1]) if isinstance(value, tuple) else (value, None)

    return (mock.patch("workflow_core.tasks.backend", return_value="beads"),
            mock.patch("workflow_core.tasks.query_result", side_effect=answer))


class BeadsLinesTests(PrimeCase):
    def run_with(self, *argv, **answers):
        backend, query = beads(**answers)
        with backend, query:
            return self.prime(*argv)[1]

    def test_open_questions_without_a_newer_answer(self):
        comments = [
            {"text": "[gin question] t-1: which port?", "created_at": "2026-11-01T00:00:00Z"},
            {"text": "[gin answer] t-1: 8080", "created_at": "2026-11-02T00:00:00Z"},
            {"text": "[gin question] t-2: keep the old flag?", "created_at": "2026-11-03T00:00:00Z"},
            {"text": "[gin learn] something", "created_at": "2026-11-04T00:00:00Z"},
        ]
        self.assertEqual(["t-2: keep the old flag?"], prime.open_questions(comments))

    def test_a_workflow_id_that_is_no_bead_has_no_comments(self):
        with mock.patch("workflow_core.tasks.query_result", return_value=(None, "issue not found: wf-1")):
            self.assertEqual([], prime.epic_comments(self.root, "wf-1"))
        with mock.patch("workflow_core.tasks.query_result", return_value=(None, "bd not found")):
            with self.assertRaises(prime.SourceError):
                prime.epic_comments(self.root, "wf-1")

    def test_the_card_lists_bead_questions_and_open_design_questions(self):
        with mock.patch("workflow_core.lifecycle_cli._open_questions",
                        return_value=[(".planning/specs/x-design.md:40: TQ-1", "")]):
            out = self.run_with("--workflow-id", "wf-1",
                                comments=[{"text": "[gin question] t-2: keep it?", "created_at": "2026-11-03T00:00:00Z"}])
        self.assertIn("Open questions:\n  - .planning/specs/x-design.md:40: TQ-1\n  - t-2: keep it?", out)

    def test_memories_that_fit_are_all_shown_and_the_reference_ends_the_card(self):
        out = self.run_with("--workflow-id", "wf-1", memories={"a": "first", "b": "second\nline"})
        self.assertIn("Beads memories\n- a: first\n- b: second line\n", out)
        self.assertNotIn("more: bd memories", out)
        self.assertTrue(out.rstrip("\n").endswith(prime.REFERENCE))

    def test_memories_that_do_not_fit_end_with_more(self):
        many = {f"m{index:03d}": "x" * 100 for index in range(200)}
        out = self.run_with("--workflow-id", "wf-1", memories=many)
        self.assertLessEqual(len(out.rstrip("\n")), prime.CARD_CAP)
        self.assertRegex(out, r"\+\d+ more: bd memories\n")
        self.assertTrue(out.rstrip("\n").endswith(prime.REFERENCE))

    def test_failed_memories_mark_only_their_line(self):
        out = self.run_with("--workflow-id", "wf-1", memories=(None, "bd timed out after 4s"))
        self.assertIn("Beads memories: unknown (bd timed out after 4s)", out)
        self.assertIn("Workflow: wf-1", out)

    def test_a_slow_memories_job_leaves_the_earlier_lines_intact(self):
        def answer(root, argv, timeout=30):
            if argv[0] == "memories":
                time.sleep(1)
            return [], None

        with mock.patch.object(prime, "ROUND_TIMEOUT", 0.3), mock.patch("workflow_core.tasks.backend", return_value="beads"), \
                mock.patch("workflow_core.tasks.query_result", side_effect=answer):
            out = self.prime("--workflow-id", "wf-1")[1]
        self.assertIn("Beads memories: unknown (timed out after 0.3s)", out)
        self.assertIn("Stage:", out)
        self.assertIn("Next: /gin:discuss wf-1", out)
        self.assertTrue(out.rstrip("\n").endswith(prime.REFERENCE))

    def test_the_card_without_a_workflow_ends_with_the_memories(self):
        out = self.run_with("--hook", memories={"a": "first"})
        self.assertIn("no workflow is bound", out)
        self.assertIn("Beads memories\n- a: first\n", out)
        self.assertTrue(out.rstrip("\n").endswith(prime.REFERENCE))

    def test_memories_are_the_last_beads_call_of_the_round(self):
        self.add("orchestration.ready", "wf-1", {"epic": "ep-1", "evidence": "plan.md"})
        (self.root / ".agent-workflow/config.yaml").write_text(
            "schema_version: '2.3'\nproject:\n  review_ledger: true\n", encoding="utf-8")
        calls = []

        def answer(root, argv, timeout=30):
            calls.append(argv[0])
            return [], None

        with mock.patch("workflow_core.tasks.backend", return_value="beads"), \
                mock.patch("workflow_core.tasks.query_result", side_effect=answer):
            self.prime("--workflow-id", "wf-1")
        self.assertEqual(["comments", "list", "memories"], calls[-3:])

    def test_review_cycles_only_with_the_review_ledger(self):
        self.add("orchestration.ready", "wf-1", {"epic": "ep-1", "evidence": "plan.md"})
        with mock.patch.object(prime, "review_cycles", return_value=["t-1 1/2"]):
            self.assertNotIn("Review cycles:", self.run_with("--workflow-id", "wf-1"))
            (self.root / ".agent-workflow/config.yaml").write_text(
                "schema_version: '2.3'\nproject:\n  review_ledger: true\n", encoding="utf-8")
            self.assertIn("Review cycles: t-1 1/2", self.run_with("--workflow-id", "wf-1"))

    def test_a_markdown_project_has_no_memories_section(self):
        out = self.prime("--workflow-id", "wf-1")[1]
        self.assertNotIn("Beads memories", out)
        self.assertNotIn(prime.REFERENCE, out)


class HookModeTests(PrimeCase):
    def test_a_terminal_is_not_read_in_hook_mode(self):
        class Terminal:
            def isatty(self):
                return True

            def read(self):
                raise AssertionError("a terminal must not be read")

        self.bind("wf-1", SESSION)
        out, err = io.StringIO(), io.StringIO()
        with mock.patch("sys.stdin", Terminal()), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = prime.main(["--repository", str(self.root), "--hook"])
        self.assertEqual((0, ""), (code, err.getvalue()))
        self.assertIn("gin state card", out.getvalue())

    def test_pre_compact_takes_the_session_from_the_hook_input(self):
        self.bind("wf-folder", OTHER)
        self.bind("wf-session", SESSION, cwd="/elsewhere")
        out = self.prime("--pre-compact", stdin=json.dumps({"session_id": SESSION}))[1]
        self.assertIn("wf-session", out)
        self.assertNotIn("wf-folder", out)

    def test_an_internal_error_is_silent_in_both_hook_modes(self):
        for mode in ("--hook", "--pre-compact"):
            with self.subTest(mode=mode), mock.patch.object(prime, "folder_key", side_effect=RuntimeError("boom")):
                code, out, err = self.prime(mode, stdin="{}")
            self.assertEqual((0, ""), (code, out))
            self.assertIn("gin prime: boom", err)

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
