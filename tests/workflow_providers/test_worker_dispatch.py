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
from workflow_core.identity import AcceptanceIdentity, RepositorySnapshot  # noqa: E402
from workflow_core.manifests import ContextRequest, create_context_manifest  # noqa: E402
from workflow_providers.sequential_worker import SequentialWorkerAdapter  # noqa: E402
from workflow_providers.worker_dispatch import (  # noqa: E402
    REQUIRED_RESULT_FIELDS,
    WorkerDispatcher,
    WorkerRequest,
    WorkerResult,
    WorkerResultContractError,
    WorkerState,
    normalize_worker_result,
    worker_id_for,
)


def valid_result(task_id="task-1", *, summary="implemented"):
    return {
        "status": "completed",
        "task_id": task_id,
        "summary": summary,
        "changed_files": ["src/example.py"],
        "commits": [],
        "tests": [],
        "evidence": [{"kind": "test", "reference": "unit"}],
        "blockers": [],
    }


def acceptance_identity(task_id="task-1", *, attempt_id="attempt-1", tree="tree-1"):
    return AcceptanceIdentity(
        workflow_id="wf-1",
        attempt_id=attempt_id,
        task_id=task_id,
        repositories=(
            RepositorySnapshot(
                "primary", "scope-1", tree, "commit-1", "refs/gin/review/primary"
            ),
        ),
    )


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


def request(
    task_id="task-1",
    *,
    required=(),
    provider_role="backend",
    reasoning="high",
    acceptance_identity=None,
):
    manifest = create_context_manifest(
        "execute",
        ContextRequest(
            required=required,
            prohibited=(
                {"classification": "secret", "name": "TOKEN", "value": "sk-secret123"},
            ),
            parent_context={"conversation": "must not cross boundary"},
        ),
    )
    return WorkerRequest(
        objective="Implement the selected task",
        constraints=("Only edit the approved files",),
        generated_manifest=manifest,
        isolation_policy={"mode": "isolated", "workspace_id": f"ws-{task_id}"},
        expected_output=REQUIRED_RESULT_FIELDS,
        task_id=task_id,
        workflow_id="wf-1",
        retry_identity=f"wf-1:{task_id}",
        provider_role=provider_role,
        reasoning=reasoning,
        acceptance_identity=acceptance_identity,
    )


class WorkerTestProvenanceTests(unittest.TestCase):
    def test_schema_1_test_records_remain_readable_but_are_not_auditable(self):
        payload = valid_result()
        payload["tests"] = [
            {"command": "python3 -m unittest", "outcome": "passed"}
        ]

        result = normalize_worker_result(payload, request())

        self.assertEqual("1.0", result.schema_version)
        self.assertEqual(
            {"command": "python3 -m unittest", "outcome": "passed"},
            result.tests[0].to_dict(),
        )
        self.assertFalse(result.tests[0].auditable)

    def test_invalid_test_semantics_and_provenance_fail_normalization(self):
        cases = (
            ("argv must be a list of strings", {"argv": "python3 -m unittest"}),
            ("argv must be a list of strings", {"argv": ["python3", 1]}),
            ("argv must not be empty", {"argv": []}),
            ("exit_code must be an integer", {"exit_code": "0"}),
            ("exit_code must be an integer", {"exit_code": True}),
            ("exit_code must be between", {"exit_code": 999}),
            ("invalid test timestamp", {"started_at": "not-a-time"}),
            (
                "must be UTC",
                {
                    "started_at": "2026-08-20T10:00:00+01:00",
                    "finished_at": "2026-08-20T10:01:00+01:00",
                },
            ),
            ("finished_at precedes started_at", {"finished_at": "2026-08-20T09:00:00Z"}),
            ("workspace_id must be a portable identifier", {"workspace_id": "/tmp/ws-task-1"}),
            ("unsupported test fields", {"duration_seconds": 60}),
            ("repository_id is required", {"repository_id": ""}),
            ("attempt_id is required", {"attempt_id": ""}),
            ("source_tree_hash is required", {"source_tree_hash": ""}),
        )
        for message, override in cases:
            with self.subTest(message=message):
                payload = valid_result()
                payload["schema_version"] = "2.3"
                payload["acceptance_identity"] = acceptance_identity().to_dict()
                payload["tests"] = [provenance_record(**override)]
                with self.assertRaisesRegex(WorkerResultContractError, message):
                    normalize_worker_result(
                        payload,
                        request(acceptance_identity=acceptance_identity()),
                    )

    def test_argv_is_structured_and_secret_values_are_redacted(self):
        payload = valid_result()
        payload["schema_version"] = "2.3"
        payload["acceptance_identity"] = acceptance_identity().to_dict()
        payload["tests"] = [
            provenance_record(argv=["pytest", "--token", "sensitive-value", "-q"])
        ]

        result = normalize_worker_result(
            payload,
            request(acceptance_identity=acceptance_identity()),
        )

        self.assertEqual(("pytest", "--token", "[REDACTED]", "-q"), result.tests[0].argv)
        self.assertNotIn("sensitive-value", repr(result.tests[0].to_dict()))
        self.assertTrue(result.tests[0].auditable)
        self.assertTrue(result.tests[0].passed)

    def test_identity_bound_request_requires_matching_complete_provenance(self):
        bound = request(acceptance_identity=acceptance_identity())
        accepted = valid_result()
        accepted["schema_version"] = "2.3"
        accepted["acceptance_identity"] = acceptance_identity().to_dict()
        accepted["tests"] = [provenance_record()]

        normalized = normalize_worker_result(accepted, bound)

        self.assertEqual(provenance_record(), normalized.tests[0].to_dict())

        missing_identity = valid_result()
        missing_identity["schema_version"] = "2.3"
        missing_identity["tests"] = [provenance_record()]
        with self.assertRaisesRegex(
            WorkerResultContractError, "result acceptance_identity is required"
        ):
            normalize_worker_result(missing_identity, bound)

        rejected = (
            (
                "acceptance identity mismatch: attempt_id",
                {"result_identity": acceptance_identity(attempt_id="attempt-2").to_dict()},
            ),
            (
                "test attempt does not match request",
                {"attempt_id": "attempt-2"},
            ),
            ("workspace does not match", {"workspace_id": "ws-elsewhere"}),
            ("repository does not match request", {"repository_id": "secondary"}),
            ("source tree does not match request", {"source_tree_hash": "tree-2"}),
        )
        for message, override in rejected:
            with self.subTest(message=message):
                override = dict(override)
                payload = valid_result()
                payload["schema_version"] = "2.3"
                payload["acceptance_identity"] = override.pop(
                    "result_identity", acceptance_identity().to_dict()
                )
                payload["tests"] = [provenance_record(**override)]
                with self.assertRaisesRegex(WorkerResultContractError, message):
                    normalize_worker_result(payload, bound)

    def test_request_payload_propagates_portable_acceptance_identity(self):
        payload = request(acceptance_identity=acceptance_identity()).to_payload()

        self.assertEqual(acceptance_identity().to_dict(), payload["acceptance_identity"])
        self.assertEqual("2.3", payload["schema_version"])
        self.assertNotIn("workspace_path", repr(payload["acceptance_identity"]))
        self.assertNotIn("provider", payload)
        self.assertNotIn("sk-secret123", repr(payload))

    def test_request_rejects_acceptance_identity_from_another_task(self):
        with self.assertRaisesRegex(ValueError, "acceptance identity must match"):
            request(acceptance_identity=acceptance_identity("other-task"))

    def test_identity_bound_request_requires_portable_expected_workspace(self):
        item = request(acceptance_identity=acceptance_identity())

        for isolation_policy in ({"mode": "isolated"}, {"workspace_id": "/tmp/task-1"}):
            with self.subTest(isolation_policy=isolation_policy):
                with self.assertRaisesRegex(ValueError, "portable workspace_id"):
                    replace(item, isolation_policy=isolation_policy)


class WorkerDispatchTests(unittest.TestCase):
    @staticmethod
    def _bound_result(payload):
        result = valid_result(payload["task_id"])
        result["schema_version"] = "2.3"
        result["acceptance_identity"] = payload["acceptance_identity"]
        return result

    def test_acceptance_identity_partitions_replay_workers_and_events(self):
        with tempfile.TemporaryDirectory() as directory:
            store = WorkflowEventStore(Path(directory) / "events.jsonl")
            dispatcher = WorkerDispatcher(
                SequentialWorkerAdapter(self._bound_result),
                store,
            )
            tree_1 = request(acceptance_identity=acceptance_identity(tree="tree-1"))
            tree_2 = replace(
                tree_1,
                acceptance_identity=acceptance_identity(tree="tree-2"),
            )

            receipt_1 = dispatcher.dispatch(tree_1)
            result_1 = dispatcher.collect_result(receipt_1.worker_id)
            receipt_2 = dispatcher.dispatch(tree_2)
            result_2 = dispatcher.collect_result(receipt_2.worker_id)

            self.assertNotEqual(receipt_1.worker_id, receipt_2.worker_id)
            self.assertEqual("tree-1", result_1.acceptance_identity.repositories[0].source_tree_hash)
            self.assertEqual("tree-2", result_2.acceptance_identity.repositories[0].source_tree_hash)
            event_types = [event.event_type for event in store.read_all()]
            self.assertEqual(2, event_types.count("worker.requested"))
            self.assertEqual(2, event_types.count("worker.completed"))

    def test_replay_rejects_a_different_request_with_the_same_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            store = WorkflowEventStore(Path(directory) / "events.jsonl")
            dispatcher = WorkerDispatcher(
                SequentialWorkerAdapter(lambda payload: valid_result(payload["task_id"])),
                store,
            )
            original = request()
            dispatcher.dispatch(original)

            with self.assertRaisesRegex(ValueError, "replay request mismatch"):
                dispatcher.dispatch(replace(original, objective="A different objective"))

    def test_request_payload_is_bounded_and_excludes_parent_and_provider_details(self):
        payload = request().to_payload()

        self.assertEqual("execute", payload["generated_manifest"]["stage"])
        self.assertNotIn("parent_context", repr(payload))
        self.assertNotIn("provider_model", repr(payload))
        self.assertNotIn("provider", payload)
        self.assertNotIn("model", payload)
        self.assertEqual("backend", payload["provider_role"])
        self.assertEqual("high", payload["reasoning"])
        self.assertEqual("high_reasoning", request().model_tier)
        self.assertNotIn("sk-secret123", repr(payload))
        self.assertLessEqual(len(request().manifest_json().encode("utf-8")), 65536)

    def test_result_contract_normalizes_optional_knowledge_candidates(self):
        result = normalize_worker_result(valid_result(), request())

        self.assertEqual("completed", result.status)
        self.assertEqual((), result.knowledge_candidates)
        self.assertEqual(("src/example.py",), result.changed_files)

    def test_result_contract_rejects_missing_or_wrong_task_fields(self):
        missing = valid_result()
        del missing["evidence"]
        with self.assertRaisesRegex(WorkerResultContractError, "invalid_result_contract"):
            normalize_worker_result(missing, request())
        with self.assertRaisesRegex(WorkerResultContractError, "invalid_result_contract"):
            normalize_worker_result(valid_result("other-task"), request())

    def test_result_contract_revalidates_typed_results_and_malformed_status(self):
        typed = WorkerResult(
            status="unknown",
            task_id="task-1",
            summary="bad",
            changed_files=(1,),
            commits=(),
            tests=(),
            evidence=(),
            blockers=(),
        )
        with self.assertRaisesRegex(WorkerResultContractError, "invalid_result_contract"):
            normalize_worker_result(typed, request())

        malformed = valid_result()
        malformed["status"] = []
        with self.assertRaisesRegex(WorkerResultContractError, "invalid_result_contract"):
            normalize_worker_result(malformed, request())

    def test_dispatcher_emits_lifecycle_once_when_result_is_collected_repeatedly(self):
        with tempfile.TemporaryDirectory() as directory:
            store = WorkflowEventStore(Path(directory) / "events.jsonl")
            adapter = SequentialWorkerAdapter(lambda payload: valid_result(payload["task_id"]))
            dispatcher = WorkerDispatcher(adapter, store)

            receipt = dispatcher.dispatch(request())
            first = dispatcher.collect_result(receipt.worker_id)
            repeated = dispatcher.collect_result(receipt.worker_id)

            self.assertEqual(first, repeated)
            event_types = [event.event_type for event in store.read_all()]
            self.assertEqual(
                [
                    "worker.requested",
                    "worker.assigned",
                    "worker.started",
                    "worker.context_loaded",
                    "worker.progress_updated",
                    "worker.completed",
                ],
                event_types,
            )

    def test_concurrent_replay_waits_for_one_terminal_result_and_event(self):
        started = threading.Event()
        release = threading.Event()
        calls = []

        def runner(payload):
            calls.append(payload)
            started.set()
            release.wait(timeout=2)
            return valid_result(payload["task_id"])

        with tempfile.TemporaryDirectory() as directory:
            store = WorkflowEventStore(Path(directory) / "events.jsonl")
            dispatcher = WorkerDispatcher(SequentialWorkerAdapter(runner), store)
            first = dispatcher.dispatch(request())
            self.assertTrue(started.wait(timeout=1))
            self.assertEqual(WorkerState.STARTED, dispatcher.status(first.worker_id).state)

            replayed = dispatcher.dispatch(request())
            self.assertEqual(first.worker_id, replayed.worker_id)
            with ThreadPoolExecutor(max_workers=2) as executor:
                results = [
                    executor.submit(dispatcher.collect_result, first.worker_id)
                    for _ in range(2)
                ]
                time.sleep(0.02)
                self.assertFalse(any(future.done() for future in results))
                release.set()
                collected = [future.result(timeout=1) for future in results]

            self.assertEqual(1, len(calls))
            self.assertEqual(collected[0], collected[1])
            terminal = [
                event.event_type
                for event in store.read_all()
                if event.event_type in {"worker.completed", "worker.failed", "worker.cancelled"}
            ]
            self.assertEqual(["worker.completed"], terminal)

    def test_dispatch_only_adapter_is_rejected_before_native_work(self):
        calls = []
        underlying = SequentialWorkerAdapter(
            lambda payload: calls.append(payload) or valid_result(payload["task_id"])
        )

        class DispatchOnlyAdapter:
            def dispatch(self, worker_request):
                return underlying.dispatch(worker_request)

            def status(self, worker_id):
                return underlying.status(worker_id)

            def collect_result(self, worker_id):
                return underlying.collect_result(worker_id)

            def cancel(self, worker_id):
                return underlying.cancel(worker_id)

        with tempfile.TemporaryDirectory() as directory:
            store = WorkflowEventStore(Path(directory) / "events.jsonl")
            dispatcher = WorkerDispatcher(DispatchOnlyAdapter(), store)

            receipt = dispatcher.dispatch(request())
            result = dispatcher.collect_result(receipt.worker_id)

            self.assertEqual([], calls)
            self.assertEqual(WorkerState.FAILED, receipt.state)
            self.assertEqual(("worker_adapter_unsupported",), result.blockers)
            self.assertEqual(
                ["worker.requested", "worker.failed"],
                [event.event_type for event in store.read_all()],
            )

    def test_cancellation_before_start_prevents_work_and_later_events(self):
        entered_start = threading.Event()
        allow_start = threading.Event()
        calls = []

        class PausingStartAdapter(SequentialWorkerAdapter):
            def start(self, worker_id, on_started=None):
                entered_start.set()
                allow_start.wait(timeout=2)
                return super().start(worker_id, on_started=on_started)

        item = request(acceptance_identity=acceptance_identity())
        adapter = PausingStartAdapter(
            lambda payload: calls.append(payload) or valid_result(payload["task_id"])
        )
        with tempfile.TemporaryDirectory() as directory:
            store = WorkflowEventStore(Path(directory) / "events.jsonl")
            dispatcher = WorkerDispatcher(adapter, store)
            worker_id = worker_id_for("sequential", item)
            with ThreadPoolExecutor(max_workers=1) as executor:
                pending = executor.submit(dispatcher.dispatch, item)
                self.assertTrue(entered_start.wait(timeout=1))
                self.assertTrue(dispatcher.cancel(worker_id))
                allow_start.set()
                receipt = pending.result(timeout=1)

            self.assertEqual(WorkerState.CANCELLED, receipt.state)
            result = dispatcher.collect_result(worker_id)
            self.assertEqual("cancelled", result.status)
            self.assertEqual(item.acceptance_identity, result.acceptance_identity)
            self.assertEqual("2.3", result.schema_version)
            self.assertEqual([], calls)
            self.assertEqual(
                ["worker.requested", "worker.assigned", "worker.cancelled"],
                [event.event_type for event in store.read_all()],
            )

    def test_native_cancelled_exception_preserves_acceptance_identity(self):
        class CancelKind:
            value = "cancelled"

        class NativeCancelled(Exception):
            kind = CancelKind()

        item = request(acceptance_identity=acceptance_identity())
        adapter = SequentialWorkerAdapter(lambda payload: (_ for _ in ()).throw(NativeCancelled()))

        receipt = adapter.dispatch(item)
        result = adapter.collect_result(receipt.worker_id)

        self.assertEqual("cancelled", result.status)
        self.assertEqual(item.acceptance_identity, result.acceptance_identity)
        self.assertEqual("2.3", result.schema_version)

    def test_context_unavailable_fails_without_invoking_worker(self):
        calls = []
        with tempfile.TemporaryDirectory() as directory:
            store = WorkflowEventStore(Path(directory) / "events.jsonl")
            adapter = SequentialWorkerAdapter(lambda payload: calls.append(payload))
            dispatcher = WorkerDispatcher(adapter, store)

            receipt = dispatcher.dispatch(
                request(required=({"path": "missing.md", "available": False},))
            )
            result = dispatcher.collect_result(receipt.worker_id)

            self.assertEqual(WorkerState.FAILED, receipt.state)
            self.assertEqual("failed", result.status)
            self.assertEqual(("context_unavailable",), result.blockers)
            self.assertEqual([], calls)
            self.assertEqual(
                ["worker.requested", "worker.failed"],
                [event.event_type for event in store.read_all()],
            )

    def test_unavailable_primary_emits_event_and_uses_sequential_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            store = WorkflowEventStore(Path(directory) / "events.jsonl")
            unavailable = SequentialWorkerAdapter(None, available=False)
            fallback = SequentialWorkerAdapter(lambda payload: valid_result(payload["task_id"]))
            dispatcher = WorkerDispatcher(unavailable, store, fallback=fallback)

            receipt = dispatcher.dispatch(request())
            result = dispatcher.collect_result(receipt.worker_id)

            self.assertTrue(receipt.fallback_used)
            self.assertEqual("completed", result.status)
            self.assertIn(
                "worker.unavailable",
                [event.event_type for event in store.read_all()],
            )

    def test_cancel_is_idempotent_and_terminal_completion_is_not_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            store = WorkflowEventStore(Path(directory) / "events.jsonl")
            adapter = SequentialWorkerAdapter(lambda payload: valid_result(payload["task_id"]))
            dispatcher = WorkerDispatcher(adapter, store)
            receipt = dispatcher.dispatch(request())
            dispatcher.collect_result(receipt.worker_id)

            self.assertFalse(dispatcher.cancel(receipt.worker_id))
            self.assertFalse(dispatcher.cancel(receipt.worker_id))
            self.assertNotIn(
                "worker.cancelled", [event.event_type for event in store.read_all()]
            )


if __name__ == "__main__":
    unittest.main()
