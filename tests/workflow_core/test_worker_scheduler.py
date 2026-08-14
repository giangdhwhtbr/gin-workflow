from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest


SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core.events import WorkflowEventStore  # noqa: E402
from workflow_core.manifests import ContextRequest, create_context_manifest  # noqa: E402
from workflow_core.worker_scheduler import (  # noqa: E402
    WorkerScheduler,
    select_execution_strategy,
)
from workflow_providers.fakes import FakeTaskTrackingProvider, FakeWorkspaceProvider  # noqa: E402
from workflow_providers.contracts import TaskCreateRequest  # noqa: E402
from workflow_providers.sequential_worker import SequentialWorkerAdapter  # noqa: E402
from workflow_providers.worker_dispatch import (  # noqa: E402
    REQUIRED_RESULT_FIELDS,
    WorkerDispatcher,
    WorkerRequest,
    worker_id_for,
)


def worker_request(index):
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
