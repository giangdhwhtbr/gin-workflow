from pathlib import Path
import sys
import threading
import unittest


SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core.manifests import ContextRequest, create_context_manifest  # noqa: E402
from workflow_providers.antigravity_worker import AntigravityWorkerAdapter  # noqa: E402
from workflow_providers.claude_worker import ClaudeWorkerAdapter  # noqa: E402
from workflow_providers.codex_worker import CodexWorkerAdapter  # noqa: E402
from workflow_providers.native_cli import NativeCliOutput  # noqa: E402
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
    def test_native_adapters_build_model_specific_invocations_and_normalize_output(self):
        class FakeRunner:
            def __init__(self):
                self.invocations = []

            def run(self, invocation):
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
                )
                receipt = adapter.dispatch(request())
                self.assertEqual("completed", adapter.collect_result(receipt.worker_id).status)
                argv = runner.invocations[0].argv
                self.assertEqual(model, argv[argv.index("--model") + 1])

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
