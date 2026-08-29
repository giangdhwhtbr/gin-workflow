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

from workflow_core.assignments import RouteCandidate  # noqa: E402
from workflow_core.events import WorkflowEventStore  # noqa: E402
from workflow_core.identity import AcceptanceIdentity, RepositorySnapshot  # noqa: E402
from workflow_core.manifests import ContextRequest, create_context_manifest  # noqa: E402
from workflow_core.models import thaw  # noqa: E402
from workflow_providers.circuit_breaker import CircuitBreakerStore, CircuitState, FailureKind  # noqa: E402
from workflow_providers.native_cli import NativeCliError, NativeHealth  # noqa: E402
from workflow_providers.routed_worker import RoutedWorkerDispatcher  # noqa: E402
from workflow_providers.sequential_worker import SequentialWorkerAdapter  # noqa: E402
from workflow_providers.worker_dispatch import (  # noqa: E402
    REQUIRED_RESULT_FIELDS,
    SynchronousWorkerAdapter,
    WorkerRequest,
    WorkerResult,
    WorkerState,
    WorkerTestResult,
    _LegacyWorkerTestResult,
)


class NoopEventStore:
    def append(self, _event):
        return True


def acceptance_identity(*, tree="tree-1"):
    return AcceptanceIdentity(
        workflow_id="wf-1",
        attempt_id="attempt-1",
        task_id="task-1",
        repositories=(
            RepositorySnapshot(
                "primary", "scope-1", tree, "checkpoint-1", "refs/gin/review/task-1"
            ),
        ),
    )


def request(task_id="task-1", *, route_affinity=None, acceptance_identity=None):
    return WorkerRequest(
        objective="Implement task",
        constraints=("bounded",),
        generated_manifest=create_context_manifest("execute", ContextRequest()),
        isolation_policy={"mode": "isolated", "workspace_id": f"ws-{task_id}", "branch": f"task/{task_id}"},
        expected_output=REQUIRED_RESULT_FIELDS,
        task_id=task_id,
        workflow_id="wf-1",
        retry_identity=f"retry-{task_id}",
        provider_role="backend",
        reasoning="high",
        route_affinity=route_affinity,
        acceptance_identity=acceptance_identity,
    )


def result(task_id):
    return {
        "status": "completed",
        "task_id": task_id,
        "summary": "done",
        "changed_files": [],
        "commits": [],
        "tests": [],
        "evidence": [],
        "blockers": [],
    }


def provenance_record(task_id="task-1", **overrides):
    record = {
        "argv": ["python3", "-m", "unittest"],
        "exit_code": 0,
        "started_at": "2026-08-20T10:00:00Z",
        "finished_at": "2026-08-20T10:01:00Z",
        "workspace_id": f"ws-{task_id}",
        "repository_id": "primary",
        "attempt_id": "attempt-1",
        "source_tree_hash": "tree-1",
    }
    record.update(overrides)
    return record


class RoutedWorkerTests(unittest.TestCase):
    def test_cancel_deadline_seals_non_cooperative_route_as_cancelled(self):
        runner_started = threading.Event()
        cancellation_seen = threading.Event()
        release_terminal = threading.Event()

        def non_cooperative_runner(payload, cancel_event):
            runner_started.set()
            self.assertTrue(cancel_event.wait(timeout=1))
            cancellation_seen.set()
            release_terminal.wait(timeout=1)
            return result(payload["task_id"])

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            routes = (RouteCandidate("claude", "opus", False),)
            adapter = SynchronousWorkerAdapter(
                None, cancellable_runner=non_cooperative_runner
            )
            events = WorkflowEventStore(root / "events.jsonl")
            router = RoutedWorkerDispatcher(
                lambda item: routes,
                lambda candidate, item: adapter,
                CircuitBreakerStore(root / "breakers.json", failure_threshold=1),
                events,
                concurrency={"claude": 1},
                max_wait_seconds=0.01,
            )
            receipt = router.dispatch(request())
            self.assertTrue(runner_started.wait(timeout=1))

            started_at = time.monotonic()
            try:
                accepted = router.cancel(receipt.worker_id, timeout=0.05)
                elapsed = time.monotonic() - started_at
                self.assertTrue(cancellation_seen.is_set())
                self.assertTrue(accepted)
                self.assertLess(elapsed, 0.15)
                self.assertEqual("cancelled", router.collect_result(receipt.worker_id).status)
            finally:
                release_terminal.set()

            deadline = time.monotonic() + 1
            while adapter.status(receipt.worker_id).state is WorkerState.STARTED:
                self.assertLess(time.monotonic(), deadline)
                time.sleep(0.01)
            self.assertEqual("cancelled", router.collect_result(receipt.worker_id).status)
            self.assertEqual(
                ["worker.cancelled"],
                [
                    event.event_type
                    for event in events.read_all()
                    if event.event_type in {"worker.completed", "worker.cancelled"}
                ],
            )

    def test_status_cannot_overwrite_routed_canonical_cancelled_receipt(self):
        status_captured = threading.Event()
        release_status = threading.Event()
        release_terminal = threading.Event()

        class PausingStatusAdapter(SynchronousWorkerAdapter):
            def status(self, worker_id):
                snapshot = super().status(worker_id)
                status_captured.set()
                release_status.wait(timeout=1)
                return snapshot

        def non_cooperative_runner(payload, cancel_event):
            self.assertTrue(cancel_event.wait(timeout=1))
            release_terminal.wait(timeout=1)
            return result(payload["task_id"])

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            routes = (RouteCandidate("claude", "opus", False),)
            adapter = PausingStatusAdapter(
                None, cancellable_runner=non_cooperative_runner
            )
            router = RoutedWorkerDispatcher(
                lambda item: routes,
                lambda candidate, item: adapter,
                CircuitBreakerStore(root / "breakers.json", failure_threshold=1),
                WorkflowEventStore(root / "events.jsonl"),
                concurrency={"claude": 1},
                max_wait_seconds=0.01,
            )
            receipt = router.dispatch(request())
            with ThreadPoolExecutor(max_workers=1) as executor:
                pending_status = executor.submit(router.status, receipt.worker_id)
                self.assertTrue(status_captured.wait(timeout=1))
                self.assertTrue(router.cancel(receipt.worker_id, timeout=0.02))
                release_status.set()
                observed = pending_status.result(timeout=1)
            release_terminal.set()

            self.assertEqual(WorkerState.CANCELLED, observed.state)
            self.assertEqual(WorkerState.CANCELLED, router.status(receipt.worker_id).state)
            self.assertEqual("cancelled", router.collect_result(receipt.worker_id).status)

    def test_routed_provider_cancel_call_is_bounded_by_deadline(self):
        cancel_entered = threading.Event()
        release_cancel = threading.Event()

        class BlockingCancelAdapter(SynchronousWorkerAdapter):
            def cancel(self, worker_id):
                cancel_entered.set()
                release_cancel.wait(timeout=1)
                return super().cancel(worker_id)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            routes = (RouteCandidate("claude", "opus", False),)
            adapter = BlockingCancelAdapter(
                None,
                cancellable_runner=lambda payload, cancel_event: (
                    cancel_event.wait(timeout=1) and result(payload["task_id"])
                ),
            )
            router = RoutedWorkerDispatcher(
                lambda item: routes,
                lambda candidate, item: adapter,
                CircuitBreakerStore(root / "breakers.json", failure_threshold=1),
                WorkflowEventStore(root / "events.jsonl"),
                concurrency={"claude": 1},
                max_wait_seconds=0.01,
            )
            receipt = router.dispatch(request())

            def invoke_cancel():
                try:
                    router.cancel(receipt.worker_id, timeout=0.02)
                except TimeoutError:
                    return "timeout"
                return "returned"

            with ThreadPoolExecutor(max_workers=1) as executor:
                pending = executor.submit(invoke_cancel)
                self.assertTrue(cancel_entered.wait(timeout=1))
                completed_within_deadline = False
                try:
                    outcome = pending.result(timeout=0.15)
                    completed_within_deadline = True
                finally:
                    release_cancel.set()
                pending.result(timeout=1)

            self.assertTrue(completed_within_deadline)
            self.assertEqual("timeout", outcome)

    def test_concurrent_routed_cancel_calls_provider_once(self):
        cancel_entered = threading.Event()
        release_cancel = threading.Event()
        release_terminal = threading.Event()
        cancel_calls = 0
        cancel_lock = threading.Lock()

        class CountingCancelAdapter(SynchronousWorkerAdapter):
            def cancel(self, worker_id):
                nonlocal cancel_calls
                with cancel_lock:
                    cancel_calls += 1
                cancel_entered.set()
                release_cancel.wait(timeout=1)
                return super().cancel(worker_id)

        def non_cooperative_runner(payload, cancel_event):
            self.assertTrue(cancel_event.wait(timeout=1))
            release_terminal.wait(timeout=1)
            return result(payload["task_id"])

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            routes = (RouteCandidate("claude", "opus", False),)
            adapter = CountingCancelAdapter(
                None, cancellable_runner=non_cooperative_runner
            )
            router = RoutedWorkerDispatcher(
                lambda item: routes,
                lambda candidate, item: adapter,
                CircuitBreakerStore(root / "breakers.json", failure_threshold=1),
                WorkflowEventStore(root / "events.jsonl"),
                concurrency={"claude": 1},
                max_wait_seconds=0.01,
            )
            receipt = router.dispatch(request())
            with ThreadPoolExecutor(max_workers=2) as executor:
                first = executor.submit(router.cancel, receipt.worker_id, 0.05)
                self.assertTrue(cancel_entered.wait(timeout=1))
                second = executor.submit(router.cancel, receipt.worker_id, 0.05)
                release_cancel.set()
                self.assertTrue(first.result(timeout=1))
                self.assertTrue(second.result(timeout=1))
            release_terminal.set()

            self.assertEqual(1, cancel_calls)
            self.assertEqual("cancelled", router.collect_result(receipt.worker_id).status)

    def test_routed_abandonment_forces_cancelled_before_collector_commits(self):
        cancel_entered = threading.Event()
        release_cancel = threading.Event()
        release_result = threading.Event()
        seal_started = threading.Event()
        collector_committed = threading.Event()

        class BlockingCancelAdapter(SynchronousWorkerAdapter):
            def cancel(self, worker_id):
                cancel_entered.set()
                release_cancel.wait(timeout=1)
                return super().cancel(worker_id)

        class PausingSealRouter(RoutedWorkerDispatcher):
            def _commit_result(self, record, worker_result):
                if worker_result.status == "cancelled" and record.cancellation_abandoned:
                    seal_started.set()
                    collector_committed.wait(timeout=1)
                committed = super()._commit_result(record, worker_result)
                if worker_result.status == "completed":
                    collector_committed.set()
                return committed

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            routes = (RouteCandidate("claude", "opus", False),)
            adapter = BlockingCancelAdapter(
                lambda payload: (
                    release_result.wait(timeout=1) and result(payload["task_id"])
                )
            )
            events = WorkflowEventStore(root / "events.jsonl")
            router = PausingSealRouter(
                lambda item: routes,
                lambda candidate, item: adapter,
                CircuitBreakerStore(root / "breakers.json", failure_threshold=1),
                events,
                concurrency={"claude": 1},
                max_wait_seconds=0.01,
            )
            receipt = router.dispatch(request())

            def invoke_cancel():
                try:
                    router.cancel(receipt.worker_id, timeout=0.02)
                except TimeoutError:
                    return "timeout"
                return "returned"

            with ThreadPoolExecutor(max_workers=1) as executor:
                pending_cancel = executor.submit(invoke_cancel)
                self.assertTrue(cancel_entered.wait(timeout=1))
                self.assertTrue(seal_started.wait(timeout=1))
                release_result.set()
                self.assertEqual("timeout", pending_cancel.result(timeout=1))
            release_cancel.set()

            deadline = time.monotonic() + 1
            while not collector_committed.is_set():
                self.assertLess(time.monotonic(), deadline)
                time.sleep(0.01)
            self.assertEqual("cancelled", router.collect_result(receipt.worker_id).status)
            self.assertEqual(
                ["worker.cancelled"],
                [
                    event.event_type
                    for event in events.read_all()
                    if event.event_type in {"worker.completed", "worker.cancelled"}
                ],
            )

    def test_routed_replay_rejects_changed_request(self):
        with tempfile.TemporaryDirectory() as directory:
            routes = (RouteCandidate("claude", "opus", False),)
            router, _, _ = self.build(
                directory,
                routes=routes,
                runners={"claude": lambda payload: result(payload["task_id"])},
            )
            original = request()
            receipt = router.dispatch(original)

            with self.assertRaisesRegex(ValueError, "replay request mismatch"):
                router.dispatch(replace(original, objective="Different objective"))
            router.collect_result(receipt.worker_id)

    def test_routed_events_are_partitioned_by_acceptance_identity(self):
        def bound_result(payload):
            normalized = result(payload["task_id"])
            normalized["schema_version"] = "2.3"
            normalized["acceptance_identity"] = payload["acceptance_identity"]
            return normalized

        with tempfile.TemporaryDirectory() as directory:
            routes = (RouteCandidate("claude", "opus", False),)
            router, _, events = self.build(
                directory,
                routes=routes,
                runners={"claude": bound_result},
            )
            tree_1 = request(acceptance_identity=acceptance_identity(tree="tree-1"))
            tree_2 = replace(
                tree_1,
                acceptance_identity=acceptance_identity(tree="tree-2"),
            )

            first = router.dispatch(tree_1)
            router.collect_result(first.worker_id)
            second = router.dispatch(tree_2)
            router.collect_result(second.worker_id)

            self.assertNotEqual(first.worker_id, second.worker_id)
            event_types = [event.event_type for event in events.read_all()]
            self.assertEqual(2, event_types.count("worker.requested"))
            self.assertEqual(2, event_types.count("worker.completed"))
    def test_provider_default_route_records_degraded_capability_without_claiming_model(self):
        with tempfile.TemporaryDirectory() as directory:
            routes = (RouteCandidate("antigravity", "provider_default", False),)
            router, _, events = self.build(
                directory,
                routes=routes,
                runners={"antigravity": lambda payload: result(payload["task_id"])},
                health={
                    "antigravity": lambda candidate: NativeHealth(
                        True, "explicit_model_selection_unverified", False
                    )
                },
            )

            receipt = router.dispatch(request())
            normalized = router.collect_result(receipt.worker_id)

            self.assertEqual("completed", normalized.status)
            self.assertEqual("provider_default", receipt.model_alias)
            assigned = next(
                event for event in events.read_all() if event.event_type == "worker.assigned"
            )
            self.assertEqual("provider_default", assigned.payload["selection_mode"])
            self.assertFalse(assigned.payload["explicit_model_selection"])
            self.assertNotIn("model", assigned.payload)
            completed = next(
                event for event in events.read_all() if event.event_type == "worker.completed"
            )
            self.assertFalse(completed.payload["explicit_model_selection"])
            self.assertNotIn("model", completed.payload)
            for event in events.read_all():
                self.assertEqual("high", event.payload["requested_tier"])

    def test_explicit_antigravity_route_without_capability_uses_same_tier_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            routes = (
                RouteCandidate("antigravity", "gemini-pro", False),
                RouteCandidate("codex", "reasoning", True),
            )
            router, breaker, events = self.build(
                directory,
                routes=routes,
                runners={
                    "antigravity": lambda payload: result(payload["task_id"]),
                    "codex": lambda payload: result(payload["task_id"]),
                },
                health={
                    "antigravity": lambda candidate: NativeHealth(
                        True, "explicit_model_selection_unverified", False
                    ),
                    "codex": lambda candidate: True,
                },
            )

            receipt = router.dispatch(request())
            normalized = router.collect_result(receipt.worker_id)

            self.assertEqual("completed", normalized.status)
            self.assertEqual(("codex", "reasoning", True), (
                receipt.provider_name, receipt.model_alias, receipt.fallback_used
            ))
            unavailable = next(
                event for event in events.read_all()
                if event.event_type == "worker.unavailable"
            )
            self.assertEqual(
                "explicit_model_selection_unsupported", unavailable.payload["reason"]
            )
            self.assertEqual(
                CircuitState.CLOSED,
                breaker.state("antigravity", "gemini-pro").state,
            )

    def test_explicit_antigravity_route_requires_positive_capability_evidence(self):
        for health in (None, {"antigravity": lambda candidate: True}):
            with self.subTest(health=health), tempfile.TemporaryDirectory() as directory:
                routes = (
                    RouteCandidate("antigravity", "gemini-pro", False),
                    RouteCandidate("codex", "reasoning", True),
                )
                router, _, events = self.build(
                    directory,
                    routes=routes,
                    runners={
                        "antigravity": lambda payload: result(payload["task_id"]),
                        "codex": lambda payload: result(payload["task_id"]),
                    },
                    health=health,
                )

                receipt = router.dispatch(request())
                normalized = router.collect_result(receipt.worker_id)

                self.assertEqual("completed", normalized.status)
                self.assertEqual("codex", receipt.provider_name)
                unavailable = next(
                    event for event in events.read_all()
                    if event.event_type == "worker.unavailable"
                )
                self.assertEqual(
                    "explicit_model_selection_unverified",
                    unavailable.payload["reason"],
                )

    def test_worker_dispatch_skill_requires_route_revalidation_and_same_tier_fallback(self):
        skill = (
            SCRIPTS.parent / "skills/worker-dispatch/SKILL.md"
        ).read_text(encoding="utf-8")
        lifecycle = (
            SCRIPTS.parent / "skills/worker-dispatch/references/worker-lifecycle.md"
        ).read_text(encoding="utf-8")

        self.assertIn("provider role and reasoning", skill)
        self.assertIn("never downgrade the requested reasoning", skill)
        self.assertIn("circuit", lifecycle)
        self.assertIn("capacity", lifecycle)

    def build(self, root, *, routes, runners, health=None, concurrency=None, wait=0.01):
        breaker = CircuitBreakerStore(Path(root) / "breakers.json", failure_threshold=1)
        events = WorkflowEventStore(Path(root) / "events.jsonl")

        def factory(candidate, item):
            return SequentialWorkerAdapter(runners[candidate.provider])

        router = RoutedWorkerDispatcher(
            lambda item: tuple(routes),
            factory,
            breaker,
            events,
            concurrency=concurrency or {candidate.provider: 1 for candidate in routes},
            max_wait_seconds=wait,
            health=health or {},
        )
        return router, breaker, events

    def _join_route_monitor(self, worker_id, *, timeout=2.0):
        """Wait for the background route-monitor thread so tempdir teardown is safe."""
        deadline = time.monotonic() + timeout
        for thread in list(threading.enumerate()):
            if thread.name == f"route-monitor:{worker_id}":
                thread.join(timeout=max(0.0, deadline - time.monotonic()))

    def test_open_primary_emits_unavailable_then_routes_to_same_tier_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            routes = (
                RouteCandidate("claude", "opus", False),
                RouteCandidate("codex", "reasoning", True),
            )
            router, breaker, events = self.build(
                directory,
                routes=routes,
                runners={"claude": lambda payload: result(payload["task_id"]), "codex": lambda payload: result(payload["task_id"])},
            )
            breaker.record_failure("claude", "opus", FailureKind.QUOTA)

            receipt = router.dispatch(request())
            normalized = router.collect_result(receipt.worker_id)

            self.assertEqual(("codex", "reasoning", True), (receipt.provider_name, receipt.model_alias, receipt.fallback_used))
            self.assertEqual("completed", normalized.status)
            event_types = [event.event_type for event in events.read_all()]
            self.assertLess(event_types.index("worker.unavailable"), event_types.index("worker.assigned"))

    def test_unhealthy_primary_is_skipped_and_all_unavailable_returns_blocked_result(self):
        with tempfile.TemporaryDirectory() as directory:
            routes = (RouteCandidate("claude", "opus", False),)
            router, _, _ = self.build(
                directory,
                routes=routes,
                runners={"claude": lambda payload: result(payload["task_id"])},
                health={"claude": lambda candidate: False},
            )

            receipt = router.dispatch(request())
            blocked = router.collect_result(receipt.worker_id)

            self.assertEqual(WorkerState.FAILED, receipt.state)
            self.assertEqual(("worker_routes_unavailable",), blocked.blockers)

    def test_saturated_provider_waits_then_falls_back_without_opening_breaker(self):
        with tempfile.TemporaryDirectory() as directory:
            release = threading.Event()

            def slow(payload):
                release.wait(timeout=2)
                return result(payload["task_id"])

            routes = (
                RouteCandidate("claude", "opus", False),
                RouteCandidate("codex", "reasoning", True),
            )
            router, breaker, _ = self.build(
                directory,
                routes=routes,
                runners={"claude": slow, "codex": lambda payload: result(payload["task_id"])},
                concurrency={"claude": 1, "codex": 1},
                wait=0.02,
            )
            first = router.dispatch(request("one"))
            second = router.dispatch(request("two"))

            self.assertEqual("claude", first.provider_name)
            self.assertEqual("codex", second.provider_name)
            self.assertTrue(second.fallback_used)
            self.assertEqual(CircuitState.CLOSED, breaker.state("claude", "opus").state)
            release.set()
            router.collect_result(first.worker_id)
            router.collect_result(second.worker_id)

    def test_classified_provider_failure_opens_only_actual_route(self):
        with tempfile.TemporaryDirectory() as directory:
            def quota(_payload):
                raise NativeCliError(FailureKind.QUOTA, "classified quota")

            routes = (RouteCandidate("claude", "opus", False),)
            router, breaker, _ = self.build(
                directory,
                routes=routes,
                runners={"claude": quota},
            )
            receipt = router.dispatch(request())

            failed = router.collect_result(receipt.worker_id)

            self.assertEqual("failed", failed.status)
            self.assertEqual(CircuitState.OPEN, breaker.state("claude", "opus").state)
            self.assertEqual(CircuitState.CLOSED, breaker.state("claude", "sonnet").state)

    def test_invalid_half_open_result_releases_probe_without_counting_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            breaker = CircuitBreakerStore(
                root / "breakers.json",
                failure_threshold=1,
                cooldown_seconds=0,
                half_open_max_probes=1,
            )
            breaker.record_failure("claude", "opus", FailureKind.QUOTA)
            router = RoutedWorkerDispatcher(
                lambda _item: (RouteCandidate("claude", "opus", False),),
                lambda _candidate, _item: SequentialWorkerAdapter(lambda _payload: {}),
                breaker,
                WorkflowEventStore(root / "events.jsonl"),
                concurrency={"claude": 1},
                max_wait_seconds=0,
            )

            receipt = router.dispatch(request())
            failed = router.collect_result(receipt.worker_id)

            self.assertEqual(("invalid_result_contract",), failed.blockers)
            self.assertEqual(0, breaker.state("claude", "opus").probes)
            self.assertTrue(breaker.can_attempt("claude", "opus").allowed)

    def test_route_affinity_is_revalidated_and_selected_before_preferred_route(self):
        with tempfile.TemporaryDirectory() as directory:
            routes = (
                RouteCandidate("claude", "opus", False),
                RouteCandidate("codex", "reasoning", True),
            )
            router, _, _ = self.build(
                directory,
                routes=routes,
                runners={
                    "claude": lambda payload: result(payload["task_id"]),
                    "codex": lambda payload: result(payload["task_id"]),
                },
            )

            receipt = router.dispatch(
                request(route_affinity=("codex", "reasoning"))
            )

            self.assertEqual(("codex", "reasoning"), (receipt.provider_name, receipt.model_alias))
            router.collect_result(receipt.worker_id)

    def test_invalid_route_affinity_is_blocked_without_dispatch(self):
        with tempfile.TemporaryDirectory() as directory:
            called = []
            router, _, _ = self.build(
                directory,
                routes=(RouteCandidate("claude", "opus", False),),
                runners={"claude": lambda payload: called.append(payload) or result(payload["task_id"])},
            )

            receipt = router.dispatch(request(route_affinity=("codex", "reasoning")))

            self.assertEqual(("route_affinity_invalid",), router.collect_result(receipt.worker_id).blockers)
            self.assertEqual([], called)

    def test_capacity_wait_uses_one_deadline_across_all_candidates(self):
        with tempfile.TemporaryDirectory() as directory:
            routes = tuple(
                RouteCandidate(provider, "model", index > 0)
                for index, provider in enumerate(("claude", "codex", "antigravity"))
            )
            router, _, _ = self.build(
                directory,
                routes=routes,
                runners={provider: lambda payload: result(payload["task_id"]) for provider in ("claude", "codex", "antigravity")},
                wait=0.08,
            )
            router.event_store = NoopEventStore()
            for capacity in router._capacity.values():
                self.assertTrue(capacity.acquire(timeout=0))

            started = time.monotonic()
            receipt = router.dispatch(request())
            elapsed = time.monotonic() - started

            self.assertEqual(("worker_routes_unavailable",), router.collect_result(receipt.worker_id).blockers)
            self.assertLess(elapsed, 0.14)
            for capacity in router._capacity.values():
                capacity.release()

    def test_capacity_wait_does_not_block_unrelated_provider_dispatch(self):
        with tempfile.TemporaryDirectory() as directory:
            routes_by_task = {
                "waiting": (RouteCandidate("claude", "opus", False),),
                "fast": (RouteCandidate("codex", "reasoning", False),),
            }
            breaker = CircuitBreakerStore(Path(directory) / "breakers.json", failure_threshold=1)
            router = RoutedWorkerDispatcher(
                lambda item: routes_by_task[item.task_id],
                lambda candidate, item: SequentialWorkerAdapter(
                    lambda payload: result(payload["task_id"])
                ),
                breaker,
                WorkflowEventStore(Path(directory) / "events.jsonl"),
                concurrency={"claude": 1, "codex": 1},
                max_wait_seconds=0.2,
            )
            self.assertTrue(router._capacity["claude"].acquire(timeout=0))
            waiting_receipts = []
            waiting = threading.Thread(
                target=lambda: waiting_receipts.append(router.dispatch(request("waiting")))
            )
            waiting.start()
            time.sleep(0.02)

            started = time.monotonic()
            fast = router.dispatch(request("fast"))
            elapsed = time.monotonic() - started

            self.assertEqual("codex", fast.provider_name)
            self.assertLess(elapsed, 0.08)
            router.collect_result(fast.worker_id)
            router._capacity["claude"].release()
            waiting.join(timeout=1)
            self.assertFalse(waiting.is_alive())
            router.collect_result(waiting_receipts[0].worker_id)

    def test_adapter_start_failure_releases_route_and_uses_fallback(self):
        class CannotStart(SequentialWorkerAdapter):
            def __init__(self, behavior):
                super().__init__(lambda payload: result(payload["task_id"]))
                self.behavior = behavior

            def start(self, worker_id, *, on_started=None):
                if self.behavior == "raise":
                    raise RuntimeError("thread start failed")
                return False

        for behavior in ("false", "raise"):
            with self.subTest(behavior=behavior), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                breaker = CircuitBreakerStore(
                    root / "breakers.json",
                    failure_threshold=1,
                    cooldown_seconds=0,
                )
                breaker.record_failure("claude", "opus", FailureKind.QUOTA)
                router = RoutedWorkerDispatcher(
                    lambda item: (
                        RouteCandidate("claude", "opus", False),
                        RouteCandidate("codex", "reasoning", True),
                    ),
                    lambda candidate, item: (
                        CannotStart(behavior)
                        if candidate.provider == "claude"
                        else SequentialWorkerAdapter(
                            lambda payload: result(payload["task_id"])
                        )
                    ),
                    breaker,
                    WorkflowEventStore(root / "events.jsonl"),
                    concurrency={"claude": 1, "codex": 1},
                    max_wait_seconds=0,
                )

                receipt = router.dispatch(request())

                self.assertEqual("codex", receipt.provider_name)
                self.assertEqual("completed", router.collect_result(receipt.worker_id).status)
                self.assertEqual(0, breaker.state("claude", "opus").probes)


    def test_completed_schema_23_identity_bearing_result_emits_worker_result_event(self):
        def runner(payload):
            normalized = result(payload["task_id"])
            normalized["schema_version"] = "2.3"
            normalized["acceptance_identity"] = payload["acceptance_identity"]
            normalized["tests"] = [provenance_record(payload["task_id"])]
            return normalized

        with tempfile.TemporaryDirectory() as directory:
            routes = (RouteCandidate("claude", "opus", False),)
            router, _, events = self.build(
                directory, routes=routes, runners={"claude": runner}
            )
            identity = acceptance_identity()
            receipt = router.dispatch(request(acceptance_identity=identity))
            outcome = router.collect_result(receipt.worker_id)
            self._join_route_monitor(receipt.worker_id)

            self.assertEqual("completed", outcome.status)
            worker_result_events = [
                event for event in events.read_all() if event.event_type == "worker.result"
            ]
            self.assertEqual(1, len(worker_result_events))
            payload = thaw(worker_result_events[0].payload)
            self.assertEqual(
                {
                    "worker_id": receipt.worker_id,
                    "status": "completed",
                    "schema_version": "2.3",
                    "request_acceptance_identity": identity.to_dict(),
                    "result_acceptance_identity": identity.to_dict(),
                    "request_workspace_id": "ws-task-1",
                    "tests": [provenance_record("task-1")],
                },
                payload,
            )

    def test_failed_and_cancelled_results_do_not_emit_worker_result_event(self):
        for status in ("failed", "cancelled"):
            with self.subTest(status=status):

                def runner(payload, status=status):
                    normalized = result(payload["task_id"])
                    normalized["status"] = status
                    normalized["schema_version"] = "2.3"
                    normalized["acceptance_identity"] = payload["acceptance_identity"]
                    return normalized

                with tempfile.TemporaryDirectory() as directory:
                    routes = (RouteCandidate("claude", "opus", False),)
                    router, _, events = self.build(
                        directory, routes=routes, runners={"claude": runner}
                    )
                    receipt = router.dispatch(
                        request(acceptance_identity=acceptance_identity())
                    )
                    outcome = router.collect_result(receipt.worker_id)
                    self._join_route_monitor(receipt.worker_id)

                    self.assertEqual(status, outcome.status)
                    self.assertEqual(
                        [],
                        [
                            event
                            for event in events.read_all()
                            if event.event_type == "worker.result"
                        ],
                    )

    def test_completed_result_missing_request_side_identity_does_not_emit(self):
        def runner(payload):
            normalized = result(payload["task_id"])
            normalized["schema_version"] = "2.3"
            normalized["acceptance_identity"] = acceptance_identity().to_dict()
            return normalized

        with tempfile.TemporaryDirectory() as directory:
            routes = (RouteCandidate("claude", "opus", False),)
            router, _, events = self.build(
                directory, routes=routes, runners={"claude": runner}
            )
            receipt = router.dispatch(request())
            outcome = router.collect_result(receipt.worker_id)
            self._join_route_monitor(receipt.worker_id)

            self.assertEqual("completed", outcome.status)
            self.assertIsNotNone(outcome.acceptance_identity)
            self.assertEqual(
                [],
                [event for event in events.read_all() if event.event_type == "worker.result"],
            )

    def test_completed_result_missing_result_side_identity_does_not_emit(self):
        block = threading.Event()

        def runner(payload):
            block.wait(timeout=2)
            return result(payload["task_id"])

        with tempfile.TemporaryDirectory() as directory:
            routes = (RouteCandidate("claude", "opus", False),)
            router, _, events = self.build(
                directory, routes=routes, runners={"claude": runner}
            )
            bound_request = request(acceptance_identity=acceptance_identity())
            receipt = router.dispatch(bound_request)
            record = router._records[receipt.worker_id]
            try:
                forged = WorkerResult(
                    status="completed",
                    task_id=bound_request.task_id,
                    summary="done",
                    changed_files=(),
                    commits=(),
                    tests=(),
                    evidence=(),
                    blockers=(),
                    acceptance_identity=None,
                    schema_version="2.3",
                )
                committed = router._commit_result(record, forged)

                self.assertEqual("completed", committed.status)
                self.assertEqual(
                    [],
                    [
                        event
                        for event in events.read_all()
                        if event.event_type == "worker.result"
                    ],
                )
            finally:
                block.set()
                self._join_route_monitor(receipt.worker_id)

    def test_worker_result_event_is_idempotent_across_repeated_commits(self):
        def runner(payload):
            normalized = result(payload["task_id"])
            normalized["schema_version"] = "2.3"
            normalized["acceptance_identity"] = payload["acceptance_identity"]
            normalized["tests"] = [provenance_record(payload["task_id"])]
            return normalized

        with tempfile.TemporaryDirectory() as directory:
            routes = (RouteCandidate("claude", "opus", False),)
            router, _, events = self.build(
                directory, routes=routes, runners={"claude": runner}
            )
            receipt = router.dispatch(
                request(acceptance_identity=acceptance_identity())
            )

            router.collect_result(receipt.worker_id)
            router.collect_result(receipt.worker_id)
            self._join_route_monitor(receipt.worker_id)

            worker_result_events = [
                event for event in events.read_all() if event.event_type == "worker.result"
            ]
            self.assertEqual(1, len(worker_result_events))

    def test_non_auditable_legacy_tests_are_excluded_from_persisted_tests(self):
        def runner(payload):
            auditable = WorkerTestResult(**provenance_record(payload["task_id"]))
            legacy = _LegacyWorkerTestResult(command="echo hi", outcome="ok")
            return WorkerResult(
                status="completed",
                task_id=payload["task_id"],
                summary="done",
                changed_files=(),
                commits=(),
                tests=(auditable, legacy),
                evidence=(),
                blockers=(),
                acceptance_identity=acceptance_identity(),
                schema_version="2.3",
            )

        with tempfile.TemporaryDirectory() as directory:
            routes = (RouteCandidate("claude", "opus", False),)
            router, _, events = self.build(
                directory, routes=routes, runners={"claude": runner}
            )
            receipt = router.dispatch(
                request(acceptance_identity=acceptance_identity())
            )
            outcome = router.collect_result(receipt.worker_id)
            self._join_route_monitor(receipt.worker_id)

            self.assertEqual("completed", outcome.status)
            worker_result_events = [
                event for event in events.read_all() if event.event_type == "worker.result"
            ]
            self.assertEqual(1, len(worker_result_events))
            self.assertEqual(
                [provenance_record("task-1")],
                thaw(worker_result_events[0].payload["tests"]),
            )

    def test_collect_result_waits_for_commit_finish_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            routes = (RouteCandidate("claude", "opus", False),)
            router, _, events = self.build(
                directory, routes=routes, runners={"claude": lambda payload: result(payload["task_id"])}
            )
            receipt = router.dispatch(request())
            outcome = router.collect_result(receipt.worker_id)

            self.assertEqual("completed", outcome.status)
            event_types = [event.event_type for event in events.read_all()]
            self.assertIn("worker.completed", event_types)


if __name__ == "__main__":
    unittest.main()
