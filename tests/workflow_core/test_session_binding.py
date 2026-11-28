"""`session.bound`: gin records once which Claude Code session worked on which workflow."""

from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core import session_binding  # noqa: E402
from workflow_core.events import WorkflowEvent, WorkflowEventStore  # noqa: E402
from workflow_core.lifecycle_cli import main as lifecycle_main  # noqa: E402

SESSION = "0a1b2c3d-1111-2222-3333-444455556666"


def session(value=SESSION):
    """The environment of a command run by a Claude Code session; None removes the variable."""
    env = {key: item for key, item in os.environ.items() if key != session_binding.SESSION_VARIABLE}
    if value is not None:
        env[session_binding.SESSION_VARIABLE] = value
    return mock.patch.dict(os.environ, env, clear=True)


class SessionBindingTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        (self.root / ".agent-workflow").mkdir()
        (self.root / ".agent-workflow/config.yaml").write_text("schema_version: '2.3'\n", encoding="utf-8")
        self.log = self.root / ".agent-workflow/runtime/events.jsonl"

    def bindings(self):
        events = WorkflowEventStore(self.log).read_all() if self.log.is_file() else []
        return [(event.workflow_id, event.payload["session_id"]) for event in events
                if event.event_type == "session.bound"]

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = lifecycle_main([argv[0], "--repository", str(self.root), *argv[1:]])
        return code, out.getvalue(), err.getvalue()

    def state(self, *argv):
        code, out, err = self.run_cli("state", "--format", "json", *argv)
        return code, json.loads(out), err

    def test_state_binds_the_session_once_and_lists_it(self):
        with session():
            code, payload, _ = self.state("--workflow-id", "wf-1")
            again = self.state("--workflow-id", "wf-1")[1]
        self.assertEqual(0, code)
        self.assertEqual([("wf-1", SESSION)], self.bindings())
        self.assertEqual([SESSION], [row["session_id"] for row in payload["sessions"]])
        self.assertTrue(payload["sessions"][0]["bound_at"])
        self.assertEqual(payload["sessions"], again["sessions"])

    def test_another_session_or_workflow_adds_a_binding(self):
        with session():
            self.state("--workflow-id", "wf-1")
            self.state("--workflow-id", "wf-2")
        with session("second-session"):
            payload = self.state("--workflow-id", "wf-1")[1]
        self.assertEqual([("wf-1", SESSION), ("wf-2", SESSION), ("wf-1", "second-session")], self.bindings())
        self.assertEqual([SESSION, "second-session"], [row["session_id"] for row in payload["sessions"]])

    def test_nothing_is_bound_without_a_usable_session_or_an_explicit_workflow(self):
        named = ("--workflow-id", "wf-1")
        for value, argv in ((None, named), ("", named), ("bad id; rm", named), ("x" * 129, named),
                            (SESSION, ()), (SESSION, ("--workflow-id", "default-workflow"))):
            with self.subTest(value=value, argv=argv), session(value):
                payload = self.state(*argv)[1]
                self.assertEqual([], self.bindings())
                self.assertEqual([], payload["sessions"])

    def test_record_and_unblock_bind_the_session(self):
        with session():
            self.assertEqual(0, self.run_cli("record", "requirement-confirmed", "--workflow-id", "wf-r",
                                             "--evidence", ".planning/specs/x.md", "--actor", "user")[0])
            self.assertEqual(0, self.run_cli("unblock", "--workflow-id", "wf-u", "--gate",
                                             "requirement_confirmed", "--reason", "hotfix", "--actor", "user")[0])
            self.assertEqual(0, self.run_cli("unblock", "--workflow-id", "wf-b", "--clear-blocker",
                                             "--reason", "done", "--actor", "user")[0])
        self.assertEqual([("wf-r", SESSION), ("wf-u", SESSION), ("wf-b", SESSION)], self.bindings())

    def test_a_failed_write_warns_and_leaves_state_unchanged(self):
        with session(None):
            expected = self.state("--workflow-id", "wf-1")[:2]
        with session(), mock.patch.object(WorkflowEventStore, "append", side_effect=OSError("read-only")):
            code, payload, err = self.state("--workflow-id", "wf-1")
        self.assertEqual(expected, (code, payload))
        self.assertIn("gin: session not bound: read-only", err)
        self.assertEqual([], self.bindings())

    def test_an_unreadable_log_is_not_written_to(self):
        self.log.parent.mkdir(parents=True)
        self.log.write_text("not json\n", encoding="utf-8")
        with session():
            payload = self.state("--workflow-id", "wf-1")[1]
        self.assertEqual("not json\n", self.log.read_text(encoding="utf-8"))
        self.assertEqual([], payload["sessions"])

    def test_gates_are_the_same_with_a_binding_in_the_log(self):
        with session(None):
            before = self.state("--workflow-id", "wf-1")[1]["gates"]
        with session():
            after = self.state("--workflow-id", "wf-1")[1]["gates"]
        self.assertEqual([("wf-1", SESSION)], self.bindings())
        self.assertEqual(before, after)


    def test_binding_records_the_folder_it_ran_in(self):
        with session():
            self.state("--workflow-id", "wf-1")
        bound = [event for event in WorkflowEventStore(self.log).read_all() if event.event_type == "session.bound"]
        self.assertEqual(str(self.root.resolve()), bound[0].payload["cwd"])

    @unittest.skipUnless(shutil.which("git"), "needs git")
    def test_the_folder_is_the_git_top_level(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        inner = self.root / "a/b"
        inner.mkdir(parents=True)
        self.assertEqual(str(self.root.resolve()), session_binding.folder_key(inner))

    def test_a_session_bound_before_the_cwd_key_is_listed_once(self):
        old = WorkflowEvent.create(event_type="session.bound", workflow_id="wf-1",
                                   payload={"session_id": SESSION}, idempotency_key=f"session:{SESSION}")
        self.log.parent.mkdir(parents=True, exist_ok=True)
        WorkflowEventStore(self.log).append(old)
        with session():
            _, payload, _ = self.state("--workflow-id", "wf-1")
        self.assertEqual([("wf-1", SESSION), ("wf-1", SESSION)], self.bindings())
        self.assertEqual([{"session_id": SESSION, "bound_at": old.timestamp}], payload["sessions"])

if __name__ == "__main__":
    unittest.main()
