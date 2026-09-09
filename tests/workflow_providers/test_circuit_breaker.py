from pathlib import Path
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_providers.circuit_breaker import (  # noqa: E402
    CircuitBreakerStore,
    CircuitState,
    FailureKind,
)


class FakeClock:
    def __init__(self, value=1000.0):
        self.value = value

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


class CircuitBreakerTests(unittest.TestCase):
    def test_quota_failure_opens_only_selected_provider_model_and_persists(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "circuit-breakers.json"
            clock = FakeClock()
            store = CircuitBreakerStore(path, failure_threshold=1, cooldown_seconds=60, clock=clock)

            opened = store.record_failure(
                "claude",
                "opus",
                FailureKind.QUOTA,
                workflow_id="wf-1",
                task_id="api",
            )

            self.assertEqual(CircuitState.OPEN, store.state("claude", "opus").state)
            self.assertEqual(clock(), opened.transitioned_at)
            self.assertEqual("wf-1", opened.workflow_id)
            self.assertEqual("api", opened.task_id)
            self.assertEqual(CircuitState.CLOSED, store.state("claude", "sonnet").state)
            restored = CircuitBreakerStore(path, failure_threshold=1, cooldown_seconds=60, clock=clock)
            self.assertEqual(CircuitState.OPEN, restored.state("claude", "opus").state)

    def test_task_domain_failures_do_not_trip_breaker(self):
        with tempfile.TemporaryDirectory() as directory:
            store = CircuitBreakerStore(Path(directory) / "state.json", failure_threshold=1)
            for kind in (
                FailureKind.TASK,
                FailureKind.TEST,
                FailureKind.REVIEW,
                FailureKind.INVALID_RESULT,
            ):
                store.record_failure("claude", "opus", kind)

            self.assertEqual(CircuitState.CLOSED, store.state("claude", "opus").state)

    def test_cooldown_allows_one_half_open_probe_then_success_closes(self):
        with tempfile.TemporaryDirectory() as directory:
            clock = FakeClock()
            store = CircuitBreakerStore(
                Path(directory) / "state.json",
                failure_threshold=1,
                cooldown_seconds=30,
                half_open_max_probes=1,
                clock=clock,
            )
            store.record_failure("codex", "reasoning", FailureKind.TIMEOUT)
            self.assertFalse(store.acquire("codex", "reasoning").allowed)

            clock.advance(30)
            probe = store.acquire("codex", "reasoning")
            second = store.acquire("codex", "reasoning")

            self.assertTrue(probe.allowed)
            self.assertEqual(CircuitState.HALF_OPEN, probe.state)
            self.assertFalse(second.allowed)
            store.record_success("codex", "reasoning")
            self.assertEqual(CircuitState.CLOSED, store.state("codex", "reasoning").state)

    def test_corrupt_state_is_archived_and_unknown_circuits_fail_safe_open(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            path.write_text("{not-json", encoding="utf-8")
            clock = FakeClock()

            store = CircuitBreakerStore(path, cooldown_seconds=10, clock=clock)

            self.assertEqual(CircuitState.OPEN, store.state("agy", "flash").state)
            self.assertTrue(tuple(path.parent.glob("state.corrupt-*.json")))
            restored = CircuitBreakerStore(path, cooldown_seconds=10, clock=clock)
            self.assertEqual(CircuitState.OPEN, restored.state("claude", "opus").state)

    def test_circuit_breaker_isolates_failures_by_reasoning_effort(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            clock = FakeClock()
            store = CircuitBreakerStore(path, failure_threshold=1, cooldown_seconds=60, clock=clock)

            store.record_failure("codex", "gpt-6-astra", FailureKind.TIMEOUT, effort="high")

            self.assertEqual(CircuitState.OPEN, store.state("codex", "gpt-6-astra", effort="high").state)
            self.assertEqual(CircuitState.CLOSED, store.state("codex", "gpt-6-astra", effort="low").state)
            self.assertEqual(CircuitState.CLOSED, store.state("codex", "gpt-6-astra").state)

            restored = CircuitBreakerStore(path, failure_threshold=1, cooldown_seconds=60, clock=clock)
            self.assertEqual(CircuitState.OPEN, restored.state("codex", "gpt-6-astra", effort="high").state)
            self.assertEqual(CircuitState.CLOSED, restored.state("codex", "gpt-6-astra", effort="low").state)


if __name__ == "__main__":
    unittest.main()
