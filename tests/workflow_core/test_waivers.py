"""Tests for gate waiver primitives."""

from pathlib import Path
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core.events import WorkflowEventStore  # noqa: E402
from workflow_core.waivers import (  # noqa: E402
    NON_WAIVABLE_GATES,
    PROCESS_GATES,
    SAFETY_GATES,
    WAIVER_EVENT_TYPE,
    GateClass,
    GateWaiver,
    build_waiver_event,
    classify_gate,
    collect_waivers,
)


def process_waiver(gate="plan_approved", scope_hash="scope-1", waived_by="agent-1"):
    return GateWaiver(
        gate=gate,
        gate_class=GateClass.PROCESS,
        reason="single-line documentation fix",
        scope_hash=scope_hash,
        waived_by=waived_by,
    )


def safety_waiver(follow_up_task_id="gin-workflow-abc", scope_hash="scope-1"):
    return GateWaiver(
        gate="review_approved",
        gate_class=GateClass.SAFETY,
        reason="release blocked on a downstream outage",
        scope_hash=scope_hash,
        waived_by="human-1",
        follow_up_task_id=follow_up_task_id,
    )


class ClassifyGateTests(unittest.TestCase):
    def test_process_gates_classify_as_process(self):
        for gate in PROCESS_GATES:
            self.assertIs(classify_gate(gate), GateClass.PROCESS)

    def test_safety_gates_classify_as_safety(self):
        for gate in SAFETY_GATES:
            self.assertIs(classify_gate(gate), GateClass.SAFETY)

    def test_non_waivable_gates_are_rejected(self):
        for gate in NON_WAIVABLE_GATES:
            with self.assertRaisesRegex(ValueError, "not waivable"):
                classify_gate(gate)

    def test_unknown_gate_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown gate"):
            classify_gate("not_a_gate")

    def test_gate_sets_are_disjoint(self):
        self.assertFalse(PROCESS_GATES & SAFETY_GATES)
        self.assertFalse(PROCESS_GATES & NON_WAIVABLE_GATES)
        self.assertFalse(SAFETY_GATES & NON_WAIVABLE_GATES)


class GateWaiverTests(unittest.TestCase):
    def test_safety_waiver_without_follow_up_task_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "follow_up_task_id"):
            safety_waiver(follow_up_task_id=None)

    def test_safety_waiver_with_blank_follow_up_task_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "follow_up_task_id"):
            safety_waiver(follow_up_task_id="   ")

    def test_process_waiver_does_not_require_follow_up_task(self):
        waiver = process_waiver()
        self.assertIsNone(waiver.follow_up_task_id)

    def test_waiver_on_implementation_complete_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "not waivable"):
            process_waiver(gate="implementation_complete")

    def test_waiver_on_shipped_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "not waivable"):
            process_waiver(gate="shipped")

    def test_gate_class_disagreeing_with_classification_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "gate_class"):
            GateWaiver(
                gate="plan_approved",
                gate_class=GateClass.SAFETY,
                reason="mislabeled",
                scope_hash="scope-1",
                waived_by="agent-1",
                follow_up_task_id="gin-workflow-abc",
            )

    def test_empty_reason_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "reason"):
            GateWaiver(
                gate="plan_approved",
                gate_class=GateClass.PROCESS,
                reason="   ",
                scope_hash="scope-1",
                waived_by="agent-1",
            )

    def test_empty_scope_hash_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "scope_hash"):
            process_waiver(scope_hash="")

    def test_empty_waived_by_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "waived_by"):
            process_waiver(waived_by="")

    def test_waiver_is_immutable(self):
        waiver = process_waiver()
        with self.assertRaises(Exception):
            waiver.reason = "changed"

    def test_to_dict_round_trips_through_from_mapping(self):
        waiver = safety_waiver()
        self.assertEqual(waiver, GateWaiver.from_mapping(waiver.to_dict()))


class BuildWaiverEventTests(unittest.TestCase):
    def test_event_carries_waiver_payload_and_actor(self):
        waiver = process_waiver()
        event = build_waiver_event(waiver, workflow_id="wf-1")

        self.assertEqual(WAIVER_EVENT_TYPE, event.event_type)
        self.assertEqual("wf-1", event.workflow_id)
        self.assertEqual("agent-1", event.actor)
        self.assertEqual(waiver.to_dict(), dict(event.payload))

    def test_event_round_trips_through_the_event_store(self):
        waiver = process_waiver()
        event = build_waiver_event(waiver, workflow_id="wf-1", task_id="gin-workflow-640")

        with tempfile.TemporaryDirectory() as directory:
            store = WorkflowEventStore(Path(directory) / "events.jsonl")
            self.assertTrue(store.append(event))
            persisted = store.read_all()

        self.assertEqual(1, len(persisted))
        self.assertEqual(event.event_id, persisted[0].event_id)
        self.assertEqual("gin-workflow-640", persisted[0].task_id)


class CollectWaiversTests(unittest.TestCase):
    def collect(self, events, *, workflow_id="wf-1", scope_hash="scope-1", raw_lines=()):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            store = WorkflowEventStore(path)
            for event in events:
                store.append(event)
            if raw_lines:
                with path.open("a", encoding="utf-8") as handle:
                    for line in raw_lines:
                        handle.write(line + "\n")
            return collect_waivers(store, workflow_id=workflow_id, scope_hash=scope_hash)

    def test_matching_waiver_is_returned_keyed_by_gate(self):
        waiver = process_waiver()
        found = self.collect([build_waiver_event(waiver, workflow_id="wf-1")])

        self.assertEqual({"plan_approved"}, set(found))
        self.assertEqual(waiver, found["plan_approved"])

    def test_waiver_from_another_workflow_is_ignored(self):
        event = build_waiver_event(process_waiver(), workflow_id="wf-other")
        self.assertEqual({}, self.collect([event]))

    def test_waiver_recorded_under_another_scope_hash_is_ignored(self):
        event = build_waiver_event(
            process_waiver(scope_hash="scope-2"), workflow_id="wf-1"
        )
        self.assertEqual({}, self.collect([event]))

    def test_unrelated_event_types_are_ignored(self):
        from workflow_core.events import WorkflowEvent

        event = WorkflowEvent.create(
            event_type="worker.started", workflow_id="wf-1", task_id="t-1"
        )
        self.assertEqual({}, self.collect([event]))

    def test_corrupted_stream_yields_no_waivers_without_raising(self):
        # WorkflowEventStore.read_all() rejects the whole stream on any bad
        # line. Fail closed: a corrupted audit log must never grant a waiver,
        # and must not raise into the router either.
        event = build_waiver_event(process_waiver(), workflow_id="wf-1")

        self.assertEqual({}, self.collect([event], raw_lines=("{not json",)))

    def test_event_with_malformed_waiver_payload_is_skipped(self):
        from workflow_core.events import WorkflowEvent

        event = WorkflowEvent.create(
            event_type=WAIVER_EVENT_TYPE,
            workflow_id="wf-1",
            payload={"gate": "plan_approved", "scope_hash": "scope-1"},
        )
        self.assertEqual({}, self.collect([event]))

    def test_latest_waiver_wins_for_the_same_gate(self):
        first = build_waiver_event(process_waiver(waived_by="agent-1"), workflow_id="wf-1")
        second = build_waiver_event(process_waiver(waived_by="agent-2"), workflow_id="wf-1")
        found = self.collect([first, second])

        self.assertEqual("agent-2", found["plan_approved"].waived_by)

    def test_safety_and_process_waivers_are_collected_together(self):
        events = [
            build_waiver_event(process_waiver(), workflow_id="wf-1"),
            build_waiver_event(safety_waiver(), workflow_id="wf-1"),
        ]
        found = self.collect(events)

        self.assertEqual({"plan_approved", "review_approved"}, set(found))
        self.assertEqual(
            "gin-workflow-abc", found["review_approved"].follow_up_task_id
        )


if __name__ == "__main__":
    unittest.main()
