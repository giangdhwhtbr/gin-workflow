from pathlib import Path
import sys
import tempfile
import threading
import unittest


SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core.assignments import RouteCandidate  # noqa: E402
from workflow_core.events import WorkflowEventStore  # noqa: E402
from workflow_core.manifests import ContextRequest, create_context_manifest  # noqa: E402
from workflow_providers.circuit_breaker import CircuitBreakerStore, CircuitState, FailureKind  # noqa: E402
from workflow_providers.native_cli import NativeCliError  # noqa: E402
from workflow_providers.routed_worker import RoutedWorkerDispatcher  # noqa: E402
from workflow_providers.sequential_worker import SequentialWorkerAdapter  # noqa: E402
from workflow_providers.worker_dispatch import REQUIRED_RESULT_FIELDS, WorkerRequest, WorkerState  # noqa: E402


def request(task_id="task-1"):
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


if __name__ == "__main__":
    unittest.main()
