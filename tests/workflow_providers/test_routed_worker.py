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
from workflow_providers.circuit_breaker import CircuitBreakerStore, CircuitState, FailureKind  # noqa: E402
from workflow_providers.native_cli import NativeCliError  # noqa: E402
from workflow_providers.routed_worker import RoutedWorkerDispatcher  # noqa: E402
from workflow_providers.sequential_worker import SequentialWorkerAdapter  # noqa: E402
from workflow_providers.worker_dispatch import REQUIRED_RESULT_FIELDS, WorkerRequest, WorkerState  # noqa: E402


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


class RoutedWorkerTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
