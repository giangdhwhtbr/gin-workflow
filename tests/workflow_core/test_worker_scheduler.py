from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
import os
import sys
import tempfile
import threading
import time
import unittest


SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core.events import WorkflowEventStore  # noqa: E402
from workflow_core.identity import AcceptanceIdentity, RepositorySnapshot  # noqa: E402
from workflow_core.manifests import ContextRequest, create_context_manifest  # noqa: E402
from workflow_core.worker_scheduler import (  # noqa: E402
    WorkerScheduler,
    select_execution_strategy,
)
from workflow_providers.fakes import FakeTaskTrackingProvider, FakeWorkspaceProvider  # noqa: E402
from workflow_providers.claude_worker import ClaudeWorkerAdapter  # noqa: E402
from workflow_providers.native_cli import NativeCliRunner  # noqa: E402
from workflow_providers.contracts import TaskCreateRequest  # noqa: E402
from workflow_providers.sequential_worker import SequentialWorkerAdapter  # noqa: E402
from workflow_providers.worker_dispatch import (  # noqa: E402
    REQUIRED_RESULT_FIELDS,
    WorkerDispatcher,
    WorkerReceipt,
    WorkerRequest,
    WorkerState,
    cancelled_worker_result,
    worker_id_for,
)


def worker_request(index, *, acceptance_identity=None):
    task_id = f"task-{index}"
    return WorkerRequest(
        objective=f"Implement {task_id}",
        constraints=(f"scope-{index}",),
        generated_manifest=create_context_manifest("execute", ContextRequest()),
        isolation_policy={
            "mode": "isolated",
            "workspace_id": f"ws-{task_id}",
            "branch": f"worker/{task_id}",
        },
        expected_output=REQUIRED_RESULT_FIELDS,
        task_id=task_id,
        workflow_id="wf-1",
        retry_identity=f"wf-1:{task_id}",
        provider_role="backend",
        reasoning="medium",
        acceptance_identity=acceptance_identity,
    )


def request_identity(task_id="task-1", attempt_id="attempt-1"):
    return AcceptanceIdentity(
        "wf-1",
        attempt_id,
        task_id,
        (
            RepositorySnapshot(
                "primary",
                "scope-1",
                "tree-1",
                "checkpoint-1",
                f"refs/gin/review/{task_id}",
            ),
        ),
    )


def completed(payload):
    return {
        "status": "completed",
        "task_id": payload["task_id"],
        "summary": "done",
        "changed_files": [],
        "commits": [],
        "tests": [],
        "evidence": [],
        "blockers": [],
    }


class WorkerSchedulerTests(unittest.TestCase):
    def test_strategy_is_direct_for_small_or_sequential_work(self):
        self.assertEqual(
            "direct", select_execution_strategy(task_count=3, parallelizable=True).mode
        )
        self.assertEqual(
            "direct",
            select_execution_strategy(task_count=8, sequential=True, parallelizable=True).mode,
        )
        self.assertEqual(
            "worker",
            select_execution_strategy(task_count=4, parallelizable=True).mode,
        )
        self.assertEqual(
            "direct", select_execution_strategy(task_count=8, parallelizable=False).mode
        )

    def test_parallel_schedule_enforces_limit_isolation_and_one_claim_per_task(self):
        active = 0
        maximum = 0
        lock = threading.Lock()

        def runner(payload):
            nonlocal active, maximum
            with lock:
                active += 1
                maximum = max(maximum, active)
            time.sleep(0.02)
            with lock:
                active -= 1
            return completed(payload)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tasks = FakeTaskTrackingProvider()
            workspaces = FakeWorkspaceProvider(root / "worktrees")
            requests = tuple(worker_request(index) for index in range(5))
            for item in requests:
                tasks.create_task(
                    TaskCreateRequest(item.task_id), idempotency_key=f"create:{item.task_id}"
                )
            dispatcher = WorkerDispatcher(
                SequentialWorkerAdapter(runner), WorkflowEventStore(root / "events.jsonl")
            )
            scheduler = WorkerScheduler(
                dispatcher,
                task_tracking=tasks,
                workspace=workspaces,
                max_parallel_workers=2,
            )

            outcome = scheduler.schedule(requests)

            self.assertEqual(2, maximum)
            self.assertEqual(5, len(outcome.completed))
            self.assertEqual((), outcome.failed)
            self.assertEqual(5, len(workspaces.workspaces))
            self.assertEqual(5, len({record.attributes["assignee"] for record in tasks.tasks.values()}))

    def test_duplicate_task_request_is_rejected_before_dispatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dispatcher = WorkerDispatcher(
                SequentialWorkerAdapter(completed), WorkflowEventStore(root / "events.jsonl")
            )
            scheduler = WorkerScheduler(
                dispatcher,
                task_tracking=FakeTaskTrackingProvider(),
                workspace=FakeWorkspaceProvider(root / "worktrees"),
                max_parallel_workers=2,
            )

            with self.assertRaisesRegex(ValueError, "one task per worker claim"):
                scheduler.schedule((worker_request(1), worker_request(1)))

    def test_retry_preserves_completed_results_and_does_not_rerun_them(self):
        attempts = {}

        def flaky(payload):
            task_id = payload["task_id"]
            attempts[task_id] = attempts.get(task_id, 0) + 1
            if task_id == "task-2" and attempts[task_id] == 1:
                failed = completed(payload)
                failed.update(status="failed", summary="temporary", blockers=["timeout"])
                return failed
            return completed(payload)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tasks = FakeTaskTrackingProvider()
            requests = (worker_request(1), worker_request(2))
            for item in requests:
                tasks.create_task(
                    TaskCreateRequest(item.task_id), idempotency_key=f"create:{item.task_id}"
                )
            scheduler = WorkerScheduler(
                WorkerDispatcher(
                    SequentialWorkerAdapter(flaky), WorkflowEventStore(root / "events.jsonl")
                ),
                task_tracking=tasks,
                workspace=FakeWorkspaceProvider(root / "worktrees"),
                max_parallel_workers=2,
                max_retries=1,
            )

            outcome = scheduler.schedule(requests)

            self.assertEqual({"task-1": 1, "task-2": 2}, attempts)
            self.assertEqual(2, len(outcome.completed))
            self.assertEqual((), outcome.failed)

    def test_retry_uses_a_new_acceptance_attempt_identity(self):
        observed_attempts = []

        def retry_once(payload):
            observed_attempts.append(payload["acceptance_identity"]["attempt_id"])
            result = completed(payload)
            result.update(
                schema_version="2.3",
                acceptance_identity=payload["acceptance_identity"],
            )
            if len(observed_attempts) == 1:
                result.update(status="failed", summary="retry", blockers=["temporary"])
            return result

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tasks = FakeTaskTrackingProvider()
            item = worker_request(
                1,
                acceptance_identity=request_identity(),
            )
            tasks.create_task(TaskCreateRequest(item.task_id), idempotency_key="create")
            scheduler = WorkerScheduler(
                WorkerDispatcher(
                    SequentialWorkerAdapter(retry_once),
                    WorkflowEventStore(root / "events.jsonl"),
                ),
                task_tracking=tasks,
                workspace=FakeWorkspaceProvider(root / "worktrees"),
                max_parallel_workers=1,
                max_retries=1,
            )

            outcome = scheduler.schedule((item,))

            self.assertEqual(["attempt-1", "attempt-1:retry:1"], observed_attempts)
            self.assertEqual(
                "attempt-1:retry:1",
                outcome.completed[0].acceptance_identity.attempt_id,
            )

    def test_partial_preparation_failure_preserves_completed_results(self):
        class PartiallyFailingWorkspace(FakeWorkspaceProvider):
            def create(self, workspace_request, *, idempotency_key):
                if workspace_request.workspace_id == "ws-task-2":
                    raise RuntimeError("workspace backend failed")
                return super().create(workspace_request, idempotency_key=idempotency_key)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tasks = FakeTaskTrackingProvider()
            requests = (worker_request(1), worker_request(2))
            for item in requests:
                tasks.create_task(
                    TaskCreateRequest(item.task_id), idempotency_key=f"create:{item.task_id}"
                )
            scheduler = WorkerScheduler(
                WorkerDispatcher(
                    SequentialWorkerAdapter(completed), WorkflowEventStore(root / "events.jsonl")
                ),
                task_tracking=tasks,
                workspace=PartiallyFailingWorkspace(root / "worktrees"),
                max_parallel_workers=2,
            )

            outcome = scheduler.schedule(requests)

            self.assertEqual(("task-1",), tuple(item.task_id for item in outcome.completed))
            self.assertEqual(("task-2",), tuple(item.task_id for item in outcome.failed))
            self.assertEqual(("preparation_failed",), outcome.failed[0].blockers)

    def test_timeout_cancels_attempt_and_retries_with_a_deadline(self):
        termination_requested = threading.Event()
        first_finished = threading.Event()
        attempts = 0
        active = 0
        maximum = 0
        lock = threading.Lock()

        class TerminationAwareAdapter(SequentialWorkerAdapter):
            def _run(self, worker_id):
                super()._run(worker_id)
                first_finished.set()

            def cancel(self, worker_id):
                termination_requested.set()
                first_finished.wait(timeout=1)
                return False

        def slow_once(payload):
            nonlocal active, attempts, maximum
            with lock:
                attempts += 1
                attempt = attempts
                active += 1
                maximum = max(maximum, active)
            if attempt == 1:
                termination_requested.wait(timeout=2)
                outcome = completed(payload)
                outcome.update(status="failed", summary="stopped", blockers=["timeout"])
            else:
                outcome = completed(payload)
            with lock:
                active -= 1
            return outcome

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tasks = FakeTaskTrackingProvider()
            item = worker_request(1)
            tasks.create_task(TaskCreateRequest(item.task_id), idempotency_key="create")
            scheduler = WorkerScheduler(
                WorkerDispatcher(
                    TerminationAwareAdapter(slow_once), WorkflowEventStore(root / "events.jsonl")
                ),
                task_tracking=tasks,
                workspace=FakeWorkspaceProvider(root / "worktrees"),
                max_parallel_workers=1,
                max_retries=1,
                worker_timeout_seconds=0.2,
            )

            started_at = time.monotonic()
            outcome = scheduler.schedule((item,))
            elapsed = time.monotonic() - started_at

            self.assertLess(elapsed, 0.5)
            self.assertEqual(2, attempts)
            self.assertEqual(1, maximum)
            self.assertEqual(("task-1",), tuple(result.task_id for result in outcome.completed))
            self.assertEqual((), outcome.failed)

    def test_failed_timeout_cancellation_does_not_start_duplicate_attempt(self):
        release = threading.Event()
        attempts = 0
        lock = threading.Lock()

        def blocked(payload):
            nonlocal attempts
            with lock:
                attempts += 1
            release.wait(timeout=2)
            return completed(payload)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tasks = FakeTaskTrackingProvider()
            item = worker_request(1)
            tasks.create_task(TaskCreateRequest(item.task_id), idempotency_key="create")
            dispatcher = WorkerDispatcher(
                SequentialWorkerAdapter(blocked), WorkflowEventStore(root / "events.jsonl")
            )
            scheduler = WorkerScheduler(
                dispatcher,
                task_tracking=tasks,
                workspace=FakeWorkspaceProvider(root / "worktrees"),
                max_parallel_workers=1,
                max_retries=1,
                worker_timeout_seconds=0.2,
            )

            outcome = scheduler.schedule((item,))
            release.set()
            dispatcher.collect_result(worker_id_for("sequential", item))
            if attempts > 1:
                retried = replace(item, retry_identity=f"{item.retry_identity}:retry:1")
                dispatcher.collect_result(worker_id_for("sequential", retried))

            self.assertEqual(1, attempts)
            self.assertEqual((), outcome.completed)
            self.assertEqual(("timeout",), outcome.failed[0].blockers)

    def test_blocking_dispatch_is_bounded_by_complete_attempt_timeout(self):
        release_dispatch = threading.Event()
        dispatch_finished = threading.Event()
        attempt_finished = threading.Event()
        calls = []

        class BlockingDispatcher(WorkerDispatcher):
            def dispatch(self, worker_request):
                release_dispatch.wait(timeout=0.2)
                try:
                    return super().dispatch(worker_request)
                finally:
                    dispatch_finished.set()

            def collect_result(self, worker_id, timeout=None):
                try:
                    return super().collect_result(worker_id, timeout=timeout)
                finally:
                    attempt_finished.set()

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tasks = FakeTaskTrackingProvider()
            item = worker_request(1)
            tasks.create_task(TaskCreateRequest(item.task_id), idempotency_key="create")
            scheduler = WorkerScheduler(
                BlockingDispatcher(
                    SequentialWorkerAdapter(
                        lambda payload: calls.append(payload) or completed(payload)
                    ),
                    WorkflowEventStore(root / "events.jsonl"),
                ),
                task_tracking=tasks,
                workspace=FakeWorkspaceProvider(root / "worktrees"),
                max_parallel_workers=1,
                max_retries=1,
                worker_timeout_seconds=0.03,
            )

            started_at = time.monotonic()
            outcome = scheduler.schedule((item,))
            elapsed = time.monotonic() - started_at
            release_dispatch.set()
            self.assertTrue(dispatch_finished.wait(timeout=1))
            self.assertTrue(attempt_finished.wait(timeout=1))

            self.assertLess(elapsed, 0.15)
            self.assertEqual(1, len(calls))
            self.assertEqual((), outcome.completed)
            self.assertEqual(("timeout",), outcome.failed[0].blockers)

    def test_timeout_cancels_worker_when_dispatch_returns_receipt_during_cleanup(self):
        dispatch_entered = threading.Event()
        release_receipt = threading.Event()
        terminal = threading.Event()
        cancel_calls = []
        item = worker_request(1)

        class LateReceiptDispatcher:
            def dispatch(self, request):
                dispatch_entered.set()
                release_receipt.wait(timeout=1)
                return WorkerReceipt("late-worker", WorkerState.STARTED, request.task_id)

            def collect_result(self, worker_id, timeout=None):
                terminal.wait(timeout=1)
                return cancelled_worker_result(item)

            def cancel(self, worker_id):
                cancel_calls.append(worker_id)
                terminal.set()
                return True

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tasks = FakeTaskTrackingProvider()
            tasks.create_task(TaskCreateRequest(item.task_id), idempotency_key="create")
            scheduler = WorkerScheduler(
                LateReceiptDispatcher(),
                task_tracking=tasks,
                workspace=FakeWorkspaceProvider(root / "worktrees"),
                max_parallel_workers=1,
                worker_timeout_seconds=0.05,
            )

            timer = threading.Timer(0.075, release_receipt.set)
            timer.start()
            try:
                outcome = scheduler.schedule((item,))
            finally:
                release_receipt.set()
                terminal.set()
                timer.cancel()

            self.assertTrue(dispatch_entered.is_set())
            self.assertEqual(["late-worker"], cancel_calls)
            self.assertEqual(("timeout",), outcome.failed[0].blockers)

    def test_timeout_does_not_retry_until_accepted_cancellation_is_quiescent(self):
        terminal = threading.Event()
        dispatch_calls = []
        item = worker_request(1)

        class AcceptedButNonTerminalDispatcher:
            def dispatch(self, request):
                dispatch_calls.append(request.retry_identity)
                return WorkerReceipt(
                    f"worker-{len(dispatch_calls)}", WorkerState.STARTED, request.task_id
                )

            def collect_result(self, worker_id, timeout=None):
                terminal.wait(timeout=1)
                return cancelled_worker_result(item)

            def cancel(self, worker_id, timeout=None):
                return True

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tasks = FakeTaskTrackingProvider()
            tasks.create_task(TaskCreateRequest(item.task_id), idempotency_key="create")
            scheduler = WorkerScheduler(
                AcceptedButNonTerminalDispatcher(),
                task_tracking=tasks,
                workspace=FakeWorkspaceProvider(root / "worktrees"),
                max_parallel_workers=1,
                max_retries=1,
                worker_timeout_seconds=0.03,
            )

            try:
                outcome = scheduler.schedule((item,))
            finally:
                terminal.set()

            self.assertEqual([item.retry_identity], dispatch_calls)
            self.assertEqual(("timeout",), outcome.failed[0].blockers)

    def test_scheduler_timeout_cancels_started_native_process(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            worktrees = root / "worktrees"
            executable = root / "sleeping-claude"
            executable.write_text(
                "#!/usr/bin/env python3\n"
                "import os, time\n"
                "open('native.pid', 'w').write(str(os.getpid()))\n"
                "time.sleep(5)\n",
                encoding="utf-8",
            )
            executable.chmod(0o755)
            tasks = FakeTaskTrackingProvider()
            item = worker_request(1)
            tasks.create_task(TaskCreateRequest(item.task_id), idempotency_key="create")
            adapter = ClaudeWorkerAdapter(
                native_runner=NativeCliRunner(),
                executable=str(executable),
                model="sonnet",
                workspace=worktrees / "ws-task-1",
                timeout_seconds=10,
            )
            scheduler = WorkerScheduler(
                WorkerDispatcher(adapter, WorkflowEventStore(root / "events.jsonl")),
                task_tracking=tasks,
                workspace=FakeWorkspaceProvider(worktrees),
                max_parallel_workers=1,
                worker_timeout_seconds=0.2,
            )

            outcome = scheduler.schedule((item,))

            self.assertEqual(("timeout",), outcome.failed[0].blockers)
            pid = int((worktrees / "ws-task-1/native.pid").read_text(encoding="utf-8"))
            deadline = time.monotonic() + 1
            while time.monotonic() < deadline:
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    break
                time.sleep(0.01)
            with self.assertRaises(ProcessLookupError):
                os.kill(pid, 0)

    def test_concurrent_scheduler_calls_cannot_claim_same_task_twice(self):
        gate = threading.Barrier(2)

        def runner(payload):
            gate.wait(timeout=2)
            return completed(payload)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tasks = FakeTaskTrackingProvider()
            item = worker_request(1)
            tasks.create_task(TaskCreateRequest(item.task_id), idempotency_key="create")
            scheduler = WorkerScheduler(
                WorkerDispatcher(
                    SequentialWorkerAdapter(runner), WorkflowEventStore(root / "events.jsonl")
                ),
                task_tracking=tasks,
                workspace=FakeWorkspaceProvider(root / "worktrees"),
                max_parallel_workers=2,
            )

            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [executor.submit(scheduler.schedule, (item,)) for _ in range(2)]
                outcomes = []
                errors = []
                for future in futures:
                    try:
                        outcomes.append(future.result(timeout=3))
                    except Exception as error:
                        errors.append(error)

            self.assertEqual(1, len(outcomes))
            self.assertEqual(1, len(errors))
            self.assertIn("already claimed", str(errors[0]))


if __name__ == "__main__":
    unittest.main()
