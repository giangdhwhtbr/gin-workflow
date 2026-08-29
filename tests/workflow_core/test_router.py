from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core.approvals import (  # noqa: E402
    ApprovalAction,
    ApprovalDecision,
    ApprovalRequest,
    ApprovalStatus,
)
from workflow_core.events import WorkflowEvent, WorkflowEventStore  # noqa: E402
from workflow_core.models import EffectiveConfig  # noqa: E402
from workflow_core.router import RouteDecision, route_next_stage  # noqa: E402
from workflow_core.waivers import GateClass, GateWaiver, build_waiver_event  # noqa: E402


def iso(value):
    return value.isoformat().replace("+00:00", "Z")


class WorkflowRouterTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.store_number = 0

    def config(self, *, capabilities=None):
        return EffectiveConfig(
            {"schema_version": "2.1", "capabilities": capabilities or {}},
            self.root,
        )

    def route(self, state, config=None):
        return route_next_stage(state, config or self.config())

    def new_store(self):
        self.store_number += 1
        return WorkflowEventStore(self.root / f"audit-{self.store_number}.jsonl")

    def authorization(
        self,
        *,
        action=ApprovalAction.CURRENT_BRANCH_EXECUTION,
        workflow_id="wf-1",
        decision_age=timedelta(minutes=1),
        event_age=timedelta(seconds=30),
    ):
        now = datetime.now(timezone.utc)
        request = ApprovalRequest(
            request_id="approval-1",
            action=action,
            workflow_id=workflow_id,
            reason="protected execution boundary",
        )
        decision = ApprovalDecision(
            request_id=request.request_id,
            status=ApprovalStatus.APPROVED,
            decided_by="user-1",
            decided_at=iso(now - decision_age),
        )
        event = WorkflowEvent.create(
            event_type="approval.recorded",
            workflow_id=workflow_id,
            actor=decision.decided_by,
            timestamp=iso(now - event_age),
            payload={"request": request.to_dict(), "decision": decision.to_dict()},
        )
        return request, decision, event

    def guarded_state(self, request, decision, store, *, candidates=()):
        action = ApprovalAction.CURRENT_BRANCH_EXECUTION.value
        return {
            "workflow_id": "wf-1",
            "requirement_confirmed": True,
            "plan_approved": True,
            "guarded_actions": (action,),
            "approval_requests": {action: request},
            "approval_decisions": {action: decision},
            "audit_event_store": store,
            "audit_events": candidates,
        }

    def test_routes_only_the_earliest_incomplete_lifecycle_stage(self):
        cases = (
            ({}, "discuss", "requirement_confirmed=false"),
            ({"requirement_confirmed": True}, "plan", "plan_approved=false"),
            (
                {"requirement_confirmed": True, "plan_approved": True},
                "orchestrate",
                "orchestration_ready=false",
            ),
            (
                {
                    "requirement_confirmed": True,
                    "plan_approved": True,
                    "orchestration_ready": True,
                },
                "execute",
                "implementation_complete=false",
            ),
            (
                {
                    "requirement_confirmed": True,
                    "plan_approved": True,
                    "orchestration_ready": True,
                    "implementation_complete": True,
                },
                "verify",
                "verification_passed=false",
            ),
            (
                {
                    "requirement_confirmed": True,
                    "plan_approved": True,
                    "orchestration_ready": True,
                    "implementation_complete": True,
                    "verification_passed": True,
                },
                "ship",
                "shipped=false",
            ),
        )

        for state, expected_stage, expected_evidence in cases:
            with self.subTest(expected_stage=expected_stage):
                result = self.route(state)
                self.assertEqual(expected_stage, result.stage)
                self.assertEqual("route", result.decision)
                self.assertIn(expected_evidence, result.evidence)

    def test_routes_completed_workflow_to_read_only_progress(self):
        result = self.route(
            {
                "requirement_confirmed": True,
                "plan_approved": True,
                "orchestration_ready": True,
                "implementation_complete": True,
                "verification_passed": True,
                "shipped": True,
            }
        )
        self.assertEqual("progress", result.stage)
        self.assertEqual("complete", result.decision)
        self.assertIn("shipped=true", result.evidence)

    def test_routes_blocked_workflow_to_progress_without_advancing(self):
        result = self.route(
            {"requirement_confirmed": True, "blocked": True, "blocker": "unavailable"}
        )
        self.assertEqual("progress", result.stage)
        self.assertEqual("hold", result.decision)
        self.assertIn("blocked:unavailable", result.evidence)

    def test_explicitly_disabled_stage_capability_holds_at_progress(self):
        result = self.route(
            {"requirement_confirmed": True, "plan_approved": True},
            self.config(capabilities={"orchestrate": False}),
        )
        self.assertEqual("progress", result.stage)
        self.assertEqual("hold", result.decision)
        self.assertIn("capability:orchestrate=disabled", result.evidence)

    def test_guarded_action_requires_event_reread_from_typed_persisted_store(self):
        request, decision, event = self.authorization()
        store = self.new_store()
        self.assertTrue(store.append(event))

        result = self.route(self.guarded_state(request, decision, store))

        self.assertEqual("orchestrate", result.stage)
        self.assertIn("approval:current_branch_execution=approved", result.evidence)
        self.assertIn("audit:current_branch_execution=recorded", result.evidence)

    def test_data_move_authorization_round_trips_list_bearing_details(self):
        now = datetime.now(timezone.utc)
        request = ApprovalRequest(
            "approval-data-move",
            ApprovalAction.DATA_MOVE,
            "wf-1",
            "sync task data",
            details={"mode": "flush", "paths": [".beads/issues.jsonl"]},
        )
        decision = ApprovalDecision(
            request.request_id,
            ApprovalStatus.APPROVED,
            "user-1",
            decided_at=iso(now - timedelta(seconds=2)),
        )
        event = WorkflowEvent.create(
            event_type="approval.recorded",
            workflow_id="wf-1",
            actor="user-1",
            timestamp=iso(now - timedelta(seconds=1)),
            payload={"request": request.to_dict(), "decision": decision.to_dict()},
        )
        store = self.new_store()
        store.append(event)
        state = {
            "workflow_id": "wf-1",
            "requirement_confirmed": True,
            "plan_approved": True,
            "guarded_actions": (ApprovalAction.DATA_MOVE.value,),
            "approval_requests": {ApprovalAction.DATA_MOVE.value: request},
            "approval_decisions": {ApprovalAction.DATA_MOVE.value: decision},
            "audit_event_store": store,
        }

        result = self.route(state)

        self.assertIn("approval:data_move=approved", result.evidence)
        self.assertIn("audit:data_move=recorded", result.evidence)

    def test_in_memory_event_candidate_cannot_authorize_protected_action(self):
        request, decision, event = self.authorization()
        empty_store = self.new_store()

        result = self.route(
            self.guarded_state(request, decision, empty_store, candidates=(event, event.to_dict()))
        )

        self.assertEqual("progress", result.stage)
        self.assertEqual("hold", result.decision)
        self.assertIn("audit:current_branch_execution=missing", result.evidence)

    def test_rejects_non_store_audit_source(self):
        request, decision, _ = self.authorization()
        state = self.guarded_state(request, decision, object())

        with self.assertRaisesRegex(TypeError, "WorkflowEventStore"):
            self.route(state)

    def test_guarded_action_needs_current_real_approval_and_audit(self):
        request, decision, _ = self.authorization()
        action = ApprovalAction.CURRENT_BRANCH_EXECUTION.value
        state = {
            "workflow_id": "wf-1",
            "requirement_confirmed": True,
            "plan_approved": True,
            "guarded_actions": (action,),
            "approval_requests": {action: request},
            "approval_decisions": {},
        }
        no_approval = self.route(state)
        self.assertIn(f"approval:{action}=missing", no_approval.evidence)

        state["approval_decisions"] = {action: decision}
        state["audit_event_store"] = self.new_store()
        no_audit = self.route(state)
        self.assertIn(f"audit:{action}=missing", no_audit.evidence)

    def test_rejects_fabricated_untyped_approval_mappings(self):
        request, decision, event = self.authorization()
        store = self.new_store()
        store.append(event)
        cases = (
            (
                self.guarded_state(request.to_dict(), decision, store),
                "approval_request:current_branch_execution=invalid_type",
            ),
            (
                self.guarded_state(request, decision.to_dict(), store),
                "approval:current_branch_execution=invalid_type",
            ),
        )
        for state, expected in cases:
            with self.subTest(expected=expected):
                result = self.route(state)
                self.assertEqual("progress", result.stage)
                self.assertIn(expected, result.evidence)

    def test_rejects_malformed_persisted_stream(self):
        request, decision, _ = self.authorization()
        store = self.new_store()
        store.path.write_text('{"fabricated": true}\n', encoding="utf-8")

        result = self.route(self.guarded_state(request, decision, store))

        self.assertEqual("progress", result.stage)
        self.assertIn("audit:current_branch_execution=invalid", result.evidence)

    def test_rejects_stale_and_mismatched_authorization(self):
        request, decision, event = self.authorization()
        stale_decision = ApprovalDecision(
            request_id="old-approval",
            status=ApprovalStatus.APPROVED,
            decided_by="user-1",
            decided_at=decision.decided_at,
        )
        wrong_request, wrong_decision, wrong_event = self.authorization(
            action=ApprovalAction.SCOPE_CHANGE
        )
        other_request, other_decision, other_event = self.authorization(
            workflow_id="wf-other"
        )
        cases = []
        for candidate_request, candidate_decision, candidate_event in (
            (request, stale_decision, event),
            (wrong_request, wrong_decision, wrong_event),
            (other_request, other_decision, other_event),
        ):
            store = self.new_store()
            store.append(candidate_event)
            cases.append(self.guarded_state(candidate_request, candidate_decision, store))

        for state in cases:
            with self.subTest(state=state):
                result = self.route(state)
                self.assertEqual("progress", result.stage)
                self.assertEqual("hold", result.decision)

    def test_rejects_decision_older_than_five_minutes(self):
        request, decision, event = self.authorization(
            decision_age=timedelta(minutes=6), event_age=timedelta(minutes=1)
        )
        store = self.new_store()
        store.append(event)

        result = self.route(self.guarded_state(request, decision, store))

        self.assertEqual("progress", result.stage)
        self.assertIn("approval:current_branch_execution=stale", result.evidence)

    def test_rejects_event_older_than_five_minutes(self):
        request, decision, event = self.authorization(
            decision_age=timedelta(minutes=4), event_age=timedelta(minutes=6)
        )
        store = self.new_store()
        store.append(event)

        result = self.route(self.guarded_state(request, decision, store))

        self.assertEqual("progress", result.stage)
        self.assertIn("audit:current_branch_execution=stale", result.evidence)

    def test_rejects_six_year_old_decision_and_event(self):
        age = timedelta(days=365 * 6)
        request, decision, event = self.authorization(decision_age=age, event_age=age)
        store = self.new_store()
        store.append(event)

        result = self.route(self.guarded_state(request, decision, store))

        self.assertEqual("progress", result.stage)
        self.assertEqual("hold", result.decision)

    def test_completion_gates_require_boolean_values(self):
        with self.assertRaisesRegex(TypeError, "requirement_confirmed must be a boolean"):
            self.route({"requirement_confirmed": "true"})

    def test_stage_capability_flags_require_boolean_values(self):
        with self.assertRaisesRegex(TypeError, "capability orchestrate must be a boolean"):
            self.route(
                {"requirement_confirmed": True, "plan_approved": True},
                self.config(capabilities={"orchestrate": "false"}),
            )

    def test_rejects_untyped_config_and_non_mapping_state_at_the_boundary(self):
        with self.assertRaisesRegex(TypeError, "state must be a mapping"):
            self.route([], self.config())
        with self.assertRaisesRegex(TypeError, "EffectiveConfig"):
            self.route({}, {"schema_version": "2.1"})

    def test_route_decision_requires_remedies_for_hold_decision(self):
        with self.assertRaisesRegex(ValueError, "hold decision must include at least one remedy"):
            RouteDecision("progress", "hold", ("blocked:test",))
        decision = RouteDecision(
            "progress", "hold", ("blocked:test",), remedies=("unblock --clear-blocker",)
        )
        self.assertEqual(("unblock --clear-blocker",), decision.remedies)

    def test_hold_decisions_return_remedies(self):
        # 1. Blocked hold
        result_blocked = self.route({"blocked": True, "blocker": "unavailable"})
        self.assertEqual("hold", result_blocked.decision)
        self.assertTrue(len(result_blocked.remedies) >= 1)
        self.assertIn("unblock --clear-blocker", result_blocked.remedies)

        # 2. Guard failure hold
        request, decision, _ = self.authorization()
        state_guard = self.guarded_state(request, decision, self.new_store())
        # Store is empty, so audit is missing
        result_guard = self.route(state_guard)
        self.assertEqual("hold", result_guard.decision)
        self.assertTrue(len(result_guard.remedies) >= 1)
        self.assertIn("re-record audit event for current_branch_execution", result_guard.remedies)

        # 3. Capability disabled hold
        result_cap = self.route(
            {"requirement_confirmed": True, "plan_approved": True},
            self.config(capabilities={"orchestrate": False}),
        )
        self.assertEqual("hold", result_cap.decision)
        self.assertTrue(len(result_cap.remedies) >= 1)
        self.assertIn("enable capabilities.orchestrate in effective-config.yaml", result_cap.remedies)

    def test_valid_process_waiver_routes_past_unmet_gate_with_evidence(self):
        store = self.new_store()
        waiver = GateWaiver(
            gate="plan_approved",
            gate_class=GateClass.PROCESS,
            reason="trivial single line change",
            scope_hash="scope-abc",
            waived_by="agent-1",
        )
        event = build_waiver_event(waiver, workflow_id="wf-1")
        store.append(event)

        state = {
            "workflow_id": "wf-1",
            "scope_hash": "scope-abc",
            "requirement_confirmed": True,
            # plan_approved is absent
            "audit_event_store": store,
        }

        result = self.route(state)
        self.assertEqual("orchestrate", result.stage)
        self.assertEqual("route", result.decision)
        self.assertIn("plan_approved=waived(trivial single line change)", result.evidence)
        self.assertIn("orchestration_ready=false", result.evidence)

    def test_waiver_for_non_waivable_gate_does_not_pass_gate(self):
        store = self.new_store()
        event = WorkflowEvent.create(
            event_type="gate.waived",
            workflow_id="wf-1",
            actor="agent-1",
            payload={
                "gate": "implementation_complete",
                "gate_class": "process",
                "reason": "urgent fix",
                "scope_hash": "scope-abc",
                "waived_by": "agent-1",
            },
        )
        store.append(event)

        state = {
            "workflow_id": "wf-1",
            "scope_hash": "scope-abc",
            "requirement_confirmed": True,
            "plan_approved": True,
            "orchestration_ready": True,
            # implementation_complete is absent
            "audit_event_store": store,
        }

        result = self.route(state)
        self.assertEqual("execute", result.stage)
        self.assertEqual("route", result.decision)
        self.assertIn("implementation_complete=false", result.evidence)

    def test_waiver_with_mismatched_scope_hash_is_ignored(self):
        store = self.new_store()
        waiver = GateWaiver(
            gate="plan_approved",
            gate_class=GateClass.PROCESS,
            reason="typo fix",
            scope_hash="scope-different",
            waived_by="agent-1",
        )
        store.append(build_waiver_event(waiver, workflow_id="wf-1"))

        state = {
            "workflow_id": "wf-1",
            "scope_hash": "scope-current",
            "requirement_confirmed": True,
            "audit_event_store": store,
        }

        result = self.route(state)
        self.assertEqual("plan", result.stage)
        self.assertEqual("route", result.decision)
        self.assertIn("plan_approved=false", result.evidence)


if __name__ == "__main__":
    unittest.main()

