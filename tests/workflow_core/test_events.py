from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core.events import (  # noqa: E402
    EventPersistenceError,
    WorkflowEvent,
    WorkflowEventStore,
)
from workflow_core import schemas  # noqa: E402


class WorkflowEventTests(unittest.TestCase):
    def test_append_rejects_list_payload_without_writing_it(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            store = WorkflowEventStore(path)
            invalid = WorkflowEvent(
                event_id="evt-" + ("0" * 64),
                event_type="worker.started",
                workflow_id="wf-1",
                timestamp="2026-08-09T00:00:00Z",
                task_id="worker-1",
                payload=["not", "an", "object"],
            )

            with self.assertRaisesRegex(EventPersistenceError, "payload must be an object"):
                store.append(invalid)
            self.assertFalse(path.exists())

    def test_from_mapping_rejects_missing_task_id(self):
        event = WorkflowEvent.create(
            event_type="worker.started",
            workflow_id="wf-1",
            task_id="worker-1",
        ).to_dict()
        del event["task_id"]

        with self.assertRaisesRegex(EventPersistenceError, "missing required fields: task_id"):
            WorkflowEvent.from_dict(event)

    def test_read_rejects_malformed_existing_event_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            malformed = {
                "event_id": "evt-" + ("0" * 64),
                "event_type": "worker.started",
                "workflow_id": "wf-1",
                "timestamp": "2026-08-09T00:00:00Z",
                "task_id": "worker-1",
                "payload": ["not-an-object"],
            }
            path.write_text(json.dumps(malformed) + "\n", encoding="utf-8")

            with self.assertRaisesRegex(EventPersistenceError, "payload must be an object"):
                WorkflowEventStore(path).read_all()

    def test_append_rejects_fabricated_deterministic_event_id(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            valid = WorkflowEvent.create(
                event_type="worker.started",
                workflow_id="wf-1",
                task_id="worker-1",
            )
            fabricated = WorkflowEvent(
                event_id="evt-" + ("0" * 64),
                event_type=valid.event_type,
                workflow_id=valid.workflow_id,
                timestamp=valid.timestamp,
                task_id=valid.task_id,
                payload=valid.payload,
            )

            with self.assertRaisesRegex(
                EventPersistenceError, "does not match deterministic event identity"
            ):
                WorkflowEventStore(path).append(fabricated)
            self.assertFalse(path.exists())

    def test_event_schema_accepts_serialized_event_and_rejects_missing_identity(self):
        event = WorkflowEvent.create(
            event_type="worker.started",
            workflow_id="wf-1",
            task_id="worker-1",
        )

        schemas.validate_workflow_event(event.to_dict())
        invalid = event.to_dict()
        del invalid["event_id"]
        with self.assertRaises(ValueError):
            schemas.validate_workflow_event(invalid)

    def test_event_id_is_deterministic_and_ignores_timestamp(self):
        first = WorkflowEvent.create(
            event_type="worker.completed",
            workflow_id="wf-1",
            task_id="task-1",
            payload={"status": "success"},
            timestamp="2026-08-09T00:00:00Z",
        )
        repeated = WorkflowEvent.create(
            event_type="worker.completed",
            workflow_id="wf-1",
            task_id="task-1",
            payload={"status": "success"},
            timestamp="2026-08-09T00:01:00Z",
        )

        self.assertEqual(first.event_id, repeated.event_id)

    def test_duplicate_worker_completion_is_appended_once(self):
        with tempfile.TemporaryDirectory() as directory:
            store = WorkflowEventStore(Path(directory) / "events.jsonl")
            event = WorkflowEvent.create(
                event_type="worker.completed",
                workflow_id="wf-1",
                task_id="worker-1",
                payload={"status": "success"},
            )

            self.assertTrue(store.append(event))
            self.assertFalse(store.append(event))
            self.assertEqual([event], store.read_all())

    def test_concurrent_appends_are_valid_and_deduplicate_repeats(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            events = [
                WorkflowEvent.create(
                    event_type="worker.progress_updated",
                    workflow_id="wf-1",
                    task_id=f"worker-{index}",
                    payload={"percent": index},
                )
                for index in range(20)
            ]
            attempts = events + events

            def append(event):
                return WorkflowEventStore(path).append(event)

            with ThreadPoolExecutor(max_workers=8) as executor:
                results = list(executor.map(append, attempts))

            self.assertEqual(20, sum(results))
            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(20, len(lines))
            parsed = [json.loads(line) for line in lines]
            self.assertEqual(20, len({item["event_id"] for item in parsed}))
            self.assertEqual(20, len(WorkflowEventStore(path).read_all()))


if __name__ == "__main__":
    unittest.main()
