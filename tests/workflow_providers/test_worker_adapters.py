from pathlib import Path
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest


SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core.manifests import ContextRequest, create_context_manifest  # noqa: E402
from workflow_providers.antigravity_worker import AntigravityWorkerAdapter  # noqa: E402
from workflow_providers.claude_worker import ClaudeWorkerAdapter  # noqa: E402
from workflow_providers.codex_worker import CodexWorkerAdapter  # noqa: E402
from workflow_providers.native_cli import NativeCliOutput, NativeCliRunner  # noqa: E402
from workflow_providers.sequential_worker import SequentialWorkerAdapter  # noqa: E402
from workflow_providers.worker_dispatch import (  # noqa: E402
    REQUIRED_RESULT_FIELDS,
    WorkerRequest,
    WorkerState,
)


def request(*, task_id="task-1", workflow_id="wf-1", retry_identity="retry-1"):
    return WorkerRequest(
        objective="Implement task",
        constraints=("scope",),
        generated_manifest=create_context_manifest("execute", ContextRequest()),
        isolation_policy={"mode": "isolated", "workspace_id": "ws-task-1"},
        expected_output=REQUIRED_RESULT_FIELDS,
        task_id=task_id,
        workflow_id=workflow_id,
        retry_identity=retry_identity,
        provider_role="backend",
        reasoning="medium",
    )


def result():
    return {
        "status": "completed",
        "task_id": "task-1",
        "summary": "done",
        "changed_files": [],
        "commits": [],
        "tests": [],
        "evidence": [],
        "blockers": [],
    }


class WorkerAdapterTests(unittest.TestCase):
    def test_antigravity_provider_default_omits_explicit_model_argument(self):
        class FakeRunner:
            def __init__(self):
                self.invocations = []

            def run(self, invocation, *, cancel_event=None):
                self.invocations.append(invocation)
                return NativeCliOutput((result(),))

        runner = FakeRunner()
        adapter = AntigravityWorkerAdapter(
            native_runner=runner,
            executable="agy",
            model="provider_default",
            workspace=Path.cwd(),
        )

        receipt = adapter.dispatch(request())

        self.assertEqual("completed", adapter.collect_result(receipt.worker_id).status)
        self.assertEqual(
            ("agy", "--add-dir", str(Path.cwd().resolve()), "--sandbox", "--output-format", "json", "--print-timeout", "900s", "--print"),
            runner.invocations[0].argv[:9],
        )

    def test_native_adapters_build_model_specific_invocations_and_normalize_output(self):
        class FakeRunner:
            def __init__(self):
                self.invocations = []

            def run(self, invocation, *, cancel_event=None):
                self.invocations.append(invocation)
                return NativeCliOutput((result(),))

        for adapter_type, executable, model in (
            (ClaudeWorkerAdapter, "claude", "sonnet"),
            (CodexWorkerAdapter, "codex", "coding"),
            (AntigravityWorkerAdapter, "agy", "flash"),
        ):
            runner = FakeRunner()
            with self.subTest(adapter=adapter_type.__name__):
                adapter = adapter_type(
                    native_runner=runner,
                    executable=executable,
                    model=model,
                    workspace=Path.cwd(),
                    timeout_seconds=17,
                )
                receipt = adapter.dispatch(request())
                self.assertEqual("completed", adapter.collect_result(receipt.worker_id).status)
                argv = runner.invocations[0].argv
                self.assertEqual(model, argv[argv.index("--model") + 1])
                if adapter_type == AntigravityWorkerAdapter:
                    self.assertEqual(argv.index("--model") + 2, argv.index("--print"))
                    self.assertIn("--output-format", argv)
                    self.assertEqual("json", argv[argv.index("--output-format") + 1])
                self.assertEqual(17, runner.invocations[0].timeout_seconds)

    def test_codex_adapter_passes_reasoning_effort_configuration(self):
        class FakeRunner:
            def __init__(self):
                self.invocations = []

            def run(self, invocation, *, cancel_event=None):
                self.invocations.append(invocation)
                return NativeCliOutput((result(),))

        runner = FakeRunner()
        adapter = CodexWorkerAdapter(
            native_runner=runner,
            executable="codex",
            model="gpt-6-astra",
            workspace=Path.cwd(),
            effort="high",
        )
        receipt = adapter.dispatch(request())
        self.assertEqual("completed", adapter.collect_result(receipt.worker_id).status)
        argv = runner.invocations[0].argv
        self.assertIn("-c", argv)
        self.assertEqual("model_reasoning_effort=high", argv[argv.index("-c") + 1])
        self.assertEqual("-", argv[-1])
        self.assertLess(argv.index("-c"), argv.index("-"))


    def test_started_native_worker_can_be_cancelled_and_process_is_terminated(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executable = root / "sleeping-claude"
            executable.write_text(
                "#!/usr/bin/env python3\n"
                "import json, os, subprocess, sys, time\n"
                "open('native.pid', 'w').write(str(os.getpid()))\n"
                "child = subprocess.Popen([sys.executable, '-c', "
                "'import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(5)'], "
                "stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
                "open('child.pid', 'w').write(str(child.pid))\n"
                "time.sleep(5)\n"
                "print(json.dumps({'status':'completed','task_id':'task-1','summary':'late',"
                "'changed_files':[],'commits':[],'tests':[],'evidence':[],'blockers':[]}))\n",
                encoding="utf-8",
            )
            executable.chmod(0o755)
            adapter = ClaudeWorkerAdapter(
                native_runner=NativeCliRunner(),
                executable=str(executable),
                model="sonnet",
                workspace=root,
                timeout_seconds=10,
            )

            receipt = adapter.dispatch(request())
            deadline = time.monotonic() + 5
            while not (root / "native.pid").exists() and time.monotonic() < deadline:
                time.sleep(0.01)

            self.assertTrue(adapter.cancel(receipt.worker_id))
            cancelled = adapter.collect_result(receipt.worker_id, timeout=15)
            self.assertEqual("cancelled", cancelled.status)
            self.assertEqual(("provider_failure:cancelled",), cancelled.blockers)
            pid = int((root / "native.pid").read_text(encoding="utf-8"))
            child_pid = int((root / "child.pid").read_text(encoding="utf-8"))
            with self.assertRaises(ProcessLookupError):
                os.kill(pid, 0)
            child_stat = Path(f"/proc/{child_pid}/stat")
            def process_state():
                try:
                    return child_stat.read_text(encoding="utf-8").split()[2]
                except FileNotFoundError:
                    return None

            deadline = time.monotonic() + 1
            while child_stat.exists() and time.monotonic() < deadline:
                if process_state() in (None, "Z"):
                    break
                time.sleep(0.01)
            self.assertIn(process_state(), (None, "Z"))

    def test_native_worker_failure_preserves_classified_kind_and_diagnostic_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executable = root / "rejecting-codex"
            executable.write_text(
                "#!/usr/bin/env python3\n"
                "import sys\n"
                "sys.stdin.read()\n"
                "sys.stderr.write(\"The 'reasoning' model is not supported when using "
                "Codex with a ChatGPT account.\")\n"
                "sys.exit(1)\n",
                encoding="utf-8",
            )
            executable.chmod(0o755)
            adapter = CodexWorkerAdapter(
                native_runner=NativeCliRunner(),
                executable=str(executable),
                model="reasoning",
                workspace=root,
                timeout_seconds=5,
            )
            receipt = adapter.dispatch(request())
            outcome = adapter.collect_result(receipt.worker_id)
            self.assertEqual("failed", outcome.status)
            self.assertEqual(("provider_failure:invalid_model",), outcome.blockers)
            self.assertIn("not supported", outcome.summary)

    def test_native_worker_timeout_reports_real_changed_files_not_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            executable = root / "editing-claude"
            executable.write_text(
                "#!/usr/bin/env python3\n"
                "from pathlib import Path\n"
                "import time\n"
                "Path('report.md').write_text('work in progress')\n"
                "time.sleep(30)\n",
                encoding="utf-8",
            )
            executable.chmod(0o755)
            adapter = ClaudeWorkerAdapter(
                native_runner=NativeCliRunner(),
                executable=str(executable),
                model="sonnet",
                workspace=root,
                timeout_seconds=0.3,
            )
            receipt = adapter.dispatch(request())
            outcome = adapter.collect_result(receipt.worker_id, timeout=5)
            self.assertEqual("failed", outcome.status)
            self.assertIn("report.md", outcome.changed_files)

    def test_native_adapters_detect_missing_harness_support(self):
        for adapter_type in (
            ClaudeWorkerAdapter,
            CodexWorkerAdapter,
            AntigravityWorkerAdapter,
        ):
            with self.subTest(adapter=adapter_type.__name__):
                adapter = adapter_type()
                receipt = adapter.dispatch(request())
                self.assertEqual(WorkerState.UNAVAILABLE, receipt.state)
                self.assertEqual(WorkerState.UNAVAILABLE, adapter.status(receipt.worker_id).state)

    def test_native_adapters_normalize_without_provider_model_or_methodology_duplication(self):
        for adapter_type in (
            ClaudeWorkerAdapter,
            CodexWorkerAdapter,
            AntigravityWorkerAdapter,
        ):
            payloads = []

            def native_dispatch(payload):
                payloads.append(payload)
                return result()

            with self.subTest(adapter=adapter_type.__name__):
                adapter = adapter_type(native_dispatch=native_dispatch)
                receipt = adapter.dispatch(request())
                normalized = adapter.collect_result(receipt.worker_id)
                self.assertEqual("completed", normalized.status)
                self.assertEqual("subagent-driven-development", payloads[0]["delegate_to"])
                self.assertNotIn("provider_model", payloads[0])
                self.assertNotIn("tdd_steps", payloads[0])

    def test_sequential_adapter_implements_full_worker_lifecycle(self):
        adapter = SequentialWorkerAdapter(lambda payload: result())
        receipt = adapter.dispatch(request())

        self.assertEqual("completed", adapter.collect_result(receipt.worker_id).status)
        self.assertEqual(WorkerState.COMPLETED, adapter.status(receipt.worker_id).state)
        self.assertFalse(adapter.cancel(receipt.worker_id))

    def test_adapter_replays_same_retry_identity_without_running_twice(self):
        calls = []
        adapter = SequentialWorkerAdapter(lambda payload: calls.append(payload) or result())

        first = adapter.dispatch(request())
        repeated = adapter.dispatch(request())

        self.assertEqual(first.worker_id, repeated.worker_id)
        adapter.collect_result(first.worker_id)
        self.assertEqual(1, len(calls))

    def test_retry_identity_is_scoped_by_workflow_and_task(self):
        calls = []
        adapter = SequentialWorkerAdapter(
            lambda payload: calls.append(payload) or {**result(), "task_id": payload["task_id"]}
        )

        first = adapter.dispatch(request(retry_identity="shared"))
        second = adapter.dispatch(
            request(task_id="task-2", workflow_id="wf-2", retry_identity="shared")
        )

        self.assertNotEqual(first.worker_id, second.worker_id)
        self.assertEqual("task-1", adapter.collect_result(first.worker_id).task_id)
        self.assertEqual("task-2", adapter.collect_result(second.worker_id).task_id)
        self.assertEqual(2, len(calls))

    def test_in_flight_worker_is_observable_and_reports_non_cancellable(self):
        started = threading.Event()
        release = threading.Event()
        finished = threading.Event()

        def runner(payload):
            started.set()
            release.wait(timeout=2)
            finished.set()
            return result()

        adapter = SequentialWorkerAdapter(runner)
        receipt = adapter.dispatch(request())

        self.assertTrue(started.wait(timeout=1))
        self.assertEqual(WorkerState.STARTED, adapter.status(receipt.worker_id).state)
        self.assertFalse(adapter.cancel(receipt.worker_id))
        self.assertEqual(WorkerState.STARTED, adapter.status(receipt.worker_id).state)
        release.set()
        self.assertTrue(finished.wait(timeout=1))
        self.assertEqual("completed", adapter.collect_result(receipt.worker_id).status)
        self.assertEqual(WorkerState.COMPLETED, adapter.status(receipt.worker_id).state)


if __name__ == "__main__":
    unittest.main()
