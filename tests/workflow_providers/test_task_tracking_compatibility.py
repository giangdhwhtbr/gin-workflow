from pathlib import Path
import json
import subprocess
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
from workflow_providers.contracts import (  # noqa: E402
    OperationStatus,
    TaskClosureRequest,
    TaskCreateRequest,
    TaskDependencyRecord,
    TaskSyncRequest,
)
from workflow_providers.fakes import FakeTaskTrackingProvider  # noqa: E402
from workflow_providers.task_tracking import BeadsTaskTrackingProvider  # noqa: E402


class CliFixture:
    def __init__(
        self,
        family="bd",
        *,
        drift="",
        create_acceptance=True,
        create_status=True,
        fail_sync=False,
        fail_close_once=False,
        missing_options=(),
    ):
        self.family = family
        self.drift = drift
        self.create_acceptance = create_acceptance
        self.create_status = create_status
        self.fail_sync = fail_sync
        self.fail_close_once = fail_close_once
        self.missing_options = frozenset(missing_options)
        self.reconciled = False
        self.backend = "dolt" if family == "bd" else "sqlite-jsonl"
        self.task = {
            "id": "task-1",
            "title": "Task",
            "status": "open",
            "notes": "implementation note",
            "acceptance_criteria": "tests pass",
        }
        self.readiness_payload = [{"id": "task-1"}]
        self.calls = []

    def __call__(self, argv, cwd):
        argv = tuple(argv)
        self.calls.append(argv)
        if argv == (self.family, "--version"):
            return subprocess.CompletedProcess(argv, 0, f"{self.family} 1.0.0", "")
        if argv == (self.family, "--help"):
            commands = "create show update close dep ready"
            if self.family == "bd":
                commands += " context"
            else:
                commands += " sync capabilities"
            return subprocess.CompletedProcess(argv, 0, commands, "")
        if argv[-1:] == ("--help",):
            command = argv[1:-1]
            if command == ("create",):
                acceptance = " --acceptance" if self.create_acceptance else ""
                if self.family == "br" and self.create_acceptance:
                    acceptance = " --acceptance-criteria"
                status = " --status" if self.create_status else ""
                text = (
                    f"--description --notes --priority --assignee"
                    f"{acceptance}{status} --json"
                )
            elif command == ("update",):
                acceptance = "--acceptance" if self.family == "bd" else "--acceptance-criteria"
                append_notes = " --append-notes" if self.family == "bd" else ""
                text = (
                    f"--title --description --notes --priority --assignee "
                    f"{acceptance}{append_notes} --status --json"
                )
            elif command == ("close",):
                text = "--reason --json"
            elif command == ("dep", "add"):
                text = "--type --json"
            elif command == ("ready",):
                text = "--json"
            elif command == ("sync",):
                text = "--status --flush-only --import-only --merge --json"
            else:
                text = "--json"
            text = " ".join(
                token for token in text.split() if token not in self.missing_options
            )
            return subprocess.CompletedProcess(argv, 0, text, "")
        if argv == ("bd", "context", "--json"):
            if self.drift:
                return subprocess.CompletedProcess(argv, 1, "", self.drift)
            payload = {
                "backend": self.backend,
                "database": "tasks",
                "project_id": "project-1",
                "repo_root": str(cwd),
            }
            return subprocess.CompletedProcess(argv, 0, json.dumps(payload), "")
        if argv == ("br", "sync", "--status", "--json"):
            payload = {
                "backend": self.backend,
                "healthy": not bool(self.drift),
                "drift": self.drift,
                "reconciled": self.reconciled,
            }
            return subprocess.CompletedProcess(argv, 0, json.dumps(payload), "")
        if len(argv) > 1 and argv[1] == "create":
            self.task["title"] = argv[2]
            if "--status" in argv:
                self.task["status"] = argv[argv.index("--status") + 1]
            if "--notes" in argv:
                self.task["notes"] = argv[argv.index("--notes") + 1]
            for flag in ("--acceptance", "--acceptance-criteria"):
                if flag in argv:
                    self.task["acceptance_criteria"] = argv[argv.index(flag) + 1]
            return subprocess.CompletedProcess(argv, 0, json.dumps(self.task), "")
        if len(argv) > 1 and argv[1] == "show":
            return subprocess.CompletedProcess(argv, 0, json.dumps(self.task), "")
        if len(argv) > 2 and argv[1:3] == ("dep", "add"):
            return subprocess.CompletedProcess(argv, 0, json.dumps({"ok": True}), "")
        if len(argv) > 1 and argv[1] == "ready":
            return subprocess.CompletedProcess(argv, 0, json.dumps(self.readiness_payload), "")
        if len(argv) > 1 and argv[1] == "update":
            if "--status" in argv:
                self.task["status"] = argv[argv.index("--status") + 1]
            if "--notes" in argv:
                self.task["notes"] = argv[argv.index("--notes") + 1]
            if "--append-notes" in argv:
                appended = argv[argv.index("--append-notes") + 1]
                self.task["notes"] = "\n".join((str(self.task.get("notes", "")), appended))
            return subprocess.CompletedProcess(argv, 0, json.dumps(self.task), "")
        if len(argv) > 1 and argv[1] == "close":
            if self.fail_close_once:
                self.fail_close_once = False
                return subprocess.CompletedProcess(argv, 1, "", "close failed")
            self.task["status"] = "closed"
            return subprocess.CompletedProcess(argv, 0, json.dumps(self.task), "")
        if len(argv) > 2 and argv[1:3] == ("sync", "--flush-only"):
            if self.fail_sync:
                return subprocess.CompletedProcess(argv, 1, "", "repository data drift")
            return subprocess.CompletedProcess(
                argv, 0, json.dumps({"affected": [".beads/issues.jsonl"]}), ""
            )
        return subprocess.CompletedProcess(argv, 1, "", f"unsupported fixture argv: {argv}")


class TaskTrackingCompatibilityTests(unittest.TestCase):
    def test_preflight_is_cached_for_reads_but_refreshed_before_mutation(self):
        fixture = CliFixture("bd")
        provider = BeadsTaskTrackingProvider(Path.cwd(), runner=fixture)

        first = provider.preflight()
        second = provider.preflight()
        provider.create_task(TaskCreateRequest("Task"), idempotency_key="create")

        self.assertEqual(first.value, second.value)
        self.assertEqual(2, fixture.calls.count(("bd", "--version")))

    def test_fake_persists_notes_acceptance_dependencies_readiness_and_closure(self):
        provider = FakeTaskTrackingProvider()
        dependency = provider.create_task(TaskCreateRequest("dependency"), idempotency_key="dep")
        created = provider.create_task(
            TaskCreateRequest(
                "Task",
                notes=("implementation note",),
                acceptance_criteria=("tests pass",),
            ),
            idempotency_key="create",
        )
        edge = TaskDependencyRecord(created.value.task_id, dependency.value.task_id)

        first_edge = provider.add_dependency(edge, idempotency_key="edge")
        replayed_edge = provider.add_dependency(edge, idempotency_key="edge")
        blocked = provider.readiness(created.value.task_id)
        provider.close_task(
            TaskClosureRequest(dependency.value.task_id, "done", ("unit tests",)),
            idempotency_key="close-dependency",
        )
        ready = provider.readiness(created.value.task_id)
        closed = provider.close_task(
            TaskClosureRequest(created.value.task_id, "accepted", ("tests:0", "review:approved")),
            idempotency_key="close-task",
        )

        self.assertEqual(("implementation note",), created.value.notes)
        self.assertEqual(("tests pass",), created.value.acceptance_criteria)
        self.assertTrue(replayed_edge.idempotent)
        self.assertEqual((dependency.value.task_id,), blocked.value.blockers)
        self.assertTrue(ready.value.ready)
        self.assertEqual("closed", closed.value.status)
        self.assertEqual(("tests:0", "review:approved"), closed.value.acceptance_evidence)

        replayed_close = provider.close_task(
            TaskClosureRequest(created.value.task_id, "accepted", ("tests:0", "review:approved")),
            idempotency_key="close-task",
        )
        preview = TaskSyncRequest("flush", dry_run=True, workflow_id="wf-1")
        first_sync = provider.sync(preview, idempotency_key="preview")
        replayed_sync = provider.sync(preview, idempotency_key="preview")
        self.assertTrue(replayed_close.idempotent)
        self.assertFalse(first_sync.idempotent)
        self.assertTrue(replayed_sync.idempotent)

    def test_capability_or_drift_failure_stops_before_task_mutation(self):
        for fixture, expected in (
            (CliFixture(create_acceptance=False), "task.create.acceptance"),
            (CliFixture(drift="database/jsonl mismatch"), "database/jsonl mismatch"),
        ):
            with self.subTest(expected=expected):
                provider = BeadsTaskTrackingProvider(Path.cwd(), runner=fixture)
                result = provider.create_task(
                    TaskCreateRequest("Task", acceptance_criteria=("tests pass",)),
                    idempotency_key="create",
                )
                self.assertIs(OperationStatus.UNAVAILABLE, result.status)
                self.assertIn(expected, result.message)
                self.assertFalse(
                    any(
                        len(call) > 1 and call[1] == "create" and "--help" not in call
                        for call in fixture.calls
                    )
                )

    def test_every_emitted_optional_flag_requires_proven_capability(self):
        cases = (
            (CliFixture(missing_options=("--description",)), TaskCreateRequest("Task", description="body"), "task.create.description"),
            (CliFixture(missing_options=("--priority",)), TaskCreateRequest("Task", attributes={"priority": "P1"}), "task.create.priority"),
            (CliFixture(missing_options=("--assignee",)), TaskCreateRequest("Task", attributes={"assignee": "worker"}), "task.create.assignee"),
        )
        for fixture, request, expected in cases:
            with self.subTest(expected=expected):
                provider = BeadsTaskTrackingProvider(Path.cwd(), runner=fixture)
                result = provider.create_task(request, idempotency_key="create")
                self.assertIs(OperationStatus.UNAVAILABLE, result.status)
                self.assertIn(expected, result.message)
                self.assertFalse(
                    any(call[1] == "create" and "--help" not in call for call in fixture.calls)
                )

    def test_replay_revalidates_backend_identity_before_returning_cached_success(self):
        fixture = CliFixture("bd")
        provider = BeadsTaskTrackingProvider(Path.cwd(), runner=fixture)
        request = TaskCreateRequest("Task")
        first = provider.create_task(request, idempotency_key="create")
        fixture.backend = "other-store"

        replay = provider.create_task(request, idempotency_key="create")

        self.assertIs(OperationStatus.SUCCESS, first.status)
        self.assertIs(OperationStatus.UNAVAILABLE, replay.status)
        self.assertIn("backend identity changed", replay.message)
        self.assertEqual(
            1,
            len([
                call for call in fixture.calls
                if call[1] == "create" and "--help" not in call
            ]),
        )

    def test_incomplete_backend_status_fails_closed_before_mutation(self):
        class EmptyStatus(CliFixture):
            def __call__(self, argv, cwd):
                if tuple(argv) == ("bd", "context", "--json"):
                    self.calls.append(tuple(argv))
                    return subprocess.CompletedProcess(argv, 0, "{}", "")
                return super().__call__(argv, cwd)

        fixture = EmptyStatus("bd")
        provider = BeadsTaskTrackingProvider(Path.cwd(), runner=fixture)

        preflight = provider.preflight()
        result = provider.create_task(TaskCreateRequest("Task"), idempotency_key="create")

        self.assertFalse(preflight.value.healthy)
        self.assertIs(OperationStatus.UNAVAILABLE, result.status)
        self.assertFalse(
            any(call[1] == "create" and "--help" not in call for call in fixture.calls)
        )

    def test_default_open_create_does_not_require_or_emit_unproven_status_flag(self):
        fixture = CliFixture(create_status=False)
        provider = BeadsTaskTrackingProvider(Path.cwd(), runner=fixture)

        created = provider.create_task(TaskCreateRequest("Task"), idempotency_key="open")
        rejected = provider.create_task(
            TaskCreateRequest("Started", status="in_progress"),
            idempotency_key="started",
        )

        mutation = next(
            call for call in fixture.calls
            if len(call) > 1 and call[1] == "create" and "--help" not in call
        )
        self.assertIs(OperationStatus.SUCCESS, created.status)
        self.assertNotIn("--status", mutation)
        self.assertIs(OperationStatus.UNAVAILABLE, rejected.status)
        self.assertIn("task.create.status", rejected.message)

    def test_bd_maps_notes_acceptance_dependency_readiness_and_closure(self):
        fixture = CliFixture("bd")
        provider = BeadsTaskTrackingProvider(Path.cwd(), runner=fixture)
        created = provider.create_task(
            TaskCreateRequest(
                "Task", notes=("implementation note",), acceptance_criteria=("tests pass",)
            ),
            idempotency_key="create",
        )
        dependency = provider.add_dependency(
            TaskDependencyRecord("task-1", "task-0"), idempotency_key="dependency"
        )
        readiness = provider.readiness("task-1")
        closed = provider.close_task(
            TaskClosureRequest("task-1", "accepted", ("tests:0",)),
            idempotency_key="close",
        )

        self.assertIs(OperationStatus.SUCCESS, created.status)
        create_call = next(
            call
            for call in fixture.calls
            if len(call) > 1 and call[1] == "create" and "--help" not in call
        )
        self.assertIn("--notes", create_call)
        self.assertIn("--acceptance", create_call)
        self.assertIs(OperationStatus.SUCCESS, dependency.status)
        self.assertTrue(readiness.value.ready)
        self.assertEqual("closed", closed.value.status)
        self.assertTrue(any(call[1:3] == ("dep", "add") for call in fixture.calls))
        self.assertTrue(any(call[1] == "close" and "--reason" in call for call in fixture.calls))

    def test_br_uses_its_proven_acceptance_criteria_option(self):
        fixture = CliFixture("br")
        provider = BeadsTaskTrackingProvider(Path.cwd(), runner=fixture, executable="br")

        result = provider.create_task(
            TaskCreateRequest("Task", acceptance_criteria=("tests pass",)),
            idempotency_key="create",
        )

        mutation = next(
            call for call in fixture.calls
            if len(call) > 1 and call[1] == "create" and "--help" not in call
        )
        self.assertIs(OperationStatus.SUCCESS, result.status)
        self.assertIn("--acceptance-criteria", mutation)
        self.assertNotIn("--acceptance", mutation)

    def test_close_rechecks_preflight_after_persisting_evidence(self):
        class DriftAfterEvidence(CliFixture):
            def __call__(self, argv, cwd):
                result = super().__call__(argv, cwd)
                if len(argv) > 1 and argv[1] == "update" and "--help" not in argv:
                    self.drift = "backend changed after evidence write"
                return result

        fixture = DriftAfterEvidence("bd")
        provider = BeadsTaskTrackingProvider(Path.cwd(), runner=fixture)

        result = provider.close_task(
            TaskClosureRequest("task-1", "accepted", ("tests:0",)),
            idempotency_key="close",
        )

        self.assertIs(OperationStatus.UNAVAILABLE, result.status)
        self.assertIn("backend changed", result.message)
        self.assertFalse(
            any(
                len(call) > 1 and call[1] == "close" and "--help" not in call
                for call in fixture.calls
            )
        )

    def test_close_retry_deduplicates_durable_marker_and_read_round_trips_provenance(self):
        fixture = CliFixture("bd", fail_close_once=True)
        provider = BeadsTaskTrackingProvider(Path.cwd(), runner=fixture)
        request = TaskClosureRequest("task-1", "accepted", ("tests:0", "review:approved"))

        first = provider.close_task(request, idempotency_key="close")
        retried = provider.close_task(request, idempotency_key="close")
        reread = provider.read_task("task-1")

        evidence_updates = [
            call for call in fixture.calls
            if call[1] == "update" and "--help" not in call
        ]
        self.assertIs(OperationStatus.UNAVAILABLE, first.status)
        self.assertIs(OperationStatus.SUCCESS, retried.status)
        self.assertEqual(1, len(evidence_updates))
        self.assertIn("implementation note", reread.value.notes[0])
        self.assertEqual(request.acceptance_evidence, reread.value.acceptance_evidence)
        self.assertEqual(request.closure_reason, reread.value.closure_reason)

    def test_readiness_rejects_non_boolean_and_mismatched_task_identity(self):
        cases = (
            {"ready": True, "blockers": []},
            {"task_id": "task-1", "ready": "false", "blockers": []},
            {"task_id": "other", "ready": True, "blockers": []},
        )
        for payload in cases:
            with self.subTest(payload=payload):
                fixture = CliFixture("bd")
                fixture.readiness_payload = payload
                provider = BeadsTaskTrackingProvider(Path.cwd(), runner=fixture)

                result = provider.readiness("task-1")

                self.assertIs(OperationStatus.UNAVAILABLE, result.status)
                self.assertIn("malformed or mismatched", result.message)

    def test_guarded_br_sync_is_dry_run_first_and_fails_closed_without_audit(self):
        fixture = CliFixture("br")
        provider = BeadsTaskTrackingProvider(Path.cwd(), runner=fixture, executable="br")
        request = TaskSyncRequest("flush", dry_run=True, workflow_id="wf-1")

        preview = provider.sync(request, idempotency_key="preview")
        denied = provider.sync(
            TaskSyncRequest("flush", dry_run=False, workflow_id="wf-1"),
            idempotency_key="sync",
        )

        self.assertIs(OperationStatus.SUCCESS, preview.status)
        self.assertTrue(preview.value.dry_run)
        self.assertEqual(("br", "sync", "--flush-only", "--json"), preview.value.command)
        self.assertIs(OperationStatus.INVALID, denied.status)
        self.assertFalse(any(call[1:3] == ("sync", "--flush-only") for call in fixture.calls))

    def test_sync_dry_run_remains_available_for_drift_diagnostics(self):
        fixture = CliFixture("br", drift="database/jsonl mismatch")
        provider = BeadsTaskTrackingProvider(Path.cwd(), runner=fixture, executable="br")

        preflight = provider.preflight()
        preview = provider.sync(
            TaskSyncRequest("flush", dry_run=True, workflow_id="wf-1"),
            idempotency_key="preview",
        )

        self.assertFalse(preflight.value.healthy)
        self.assertEqual("database/jsonl mismatch", preflight.value.drift)
        self.assertIs(OperationStatus.SUCCESS, preview.status)
        self.assertTrue(preview.value.dry_run)
        self.assertFalse(any(call[1:3] == ("sync", "--flush-only") for call in fixture.calls))

    def test_guarded_br_sync_requires_matching_fresh_persisted_data_move_approval(self):
        fixture = CliFixture("br")
        provider = BeadsTaskTrackingProvider(Path.cwd(), runner=fixture, executable="br")
        sync = TaskSyncRequest("flush", dry_run=False, workflow_id="wf-1")
        approval = ApprovalRequest(
            "approval-sync", ApprovalAction.DATA_MOVE, "wf-1", "flush task data",
            details={
                "mode": "flush",
                "backend": "sqlite-jsonl",
                "paths": [".beads/issues.jsonl"],
            },
        )
        decision = ApprovalDecision(
            approval.request_id, ApprovalStatus.APPROVED, "user-1"
        )
        with tempfile.TemporaryDirectory() as directory:
            store = WorkflowEventStore(Path(directory) / "events.jsonl")
            event = WorkflowEvent.create(
                event_type="approval.recorded",
                workflow_id="wf-1",
                actor="user-1",
                payload={"request": approval.to_dict(), "decision": decision.to_dict()},
            )
            store.append(event)

            result = provider.sync(
                sync,
                approval_request=approval,
                approval_decision=decision,
                audit_event_store=store,
                idempotency_key="sync",
            )

        self.assertIs(OperationStatus.SUCCESS, result.status)
        self.assertEqual((".beads/issues.jsonl",), result.value.affected)
        self.assertIn(("br", "sync", "--flush-only", "--json"), fixture.calls)

    def test_data_move_approval_for_another_backend_cannot_authorize_sync(self):
        fixture = CliFixture("br")
        provider = BeadsTaskTrackingProvider(Path.cwd(), runner=fixture, executable="br")
        approval = ApprovalRequest(
            "approval-sync",
            ApprovalAction.DATA_MOVE,
            "wf-1",
            "flush other backend",
            details={"mode": "flush", "backend": "other"},
        )
        decision = ApprovalDecision(approval.request_id, ApprovalStatus.APPROVED, "user-1")
        with tempfile.TemporaryDirectory() as directory:
            store = WorkflowEventStore(Path(directory) / "events.jsonl")
            store.append(
                WorkflowEvent.create(
                    event_type="approval.recorded",
                    workflow_id="wf-1",
                    actor="user-1",
                    payload={"request": approval.to_dict(), "decision": decision.to_dict()},
                )
            )
            result = provider.sync(
                TaskSyncRequest("flush", dry_run=False, workflow_id="wf-1"),
                approval_request=approval,
                approval_decision=decision,
                audit_event_store=store,
                idempotency_key="sync",
            )

        self.assertIs(OperationStatus.INVALID, result.status)
        self.assertIn("mode and backend", result.message)
        self.assertFalse(any(call[1:3] == ("sync", "--flush-only") for call in fixture.calls))

    def test_failed_sync_latches_drift_before_mutation_until_status_reconciles(self):
        fixture = CliFixture("br", fail_sync=True)
        provider = BeadsTaskTrackingProvider(Path.cwd(), runner=fixture, executable="br")
        sync = TaskSyncRequest("flush", dry_run=False, workflow_id="wf-1")
        approval = ApprovalRequest(
            "approval-sync",
            ApprovalAction.DATA_MOVE,
            "wf-1",
            "flush task data",
            details={"mode": "flush", "backend": "sqlite-jsonl"},
        )
        decision = ApprovalDecision(approval.request_id, ApprovalStatus.APPROVED, "user-1")
        with tempfile.TemporaryDirectory() as directory:
            store = WorkflowEventStore(Path(directory) / "events.jsonl")
            store.append(
                WorkflowEvent.create(
                    event_type="approval.recorded",
                    workflow_id="wf-1",
                    actor="user-1",
                    payload={"request": approval.to_dict(), "decision": decision.to_dict()},
                )
            )
            failed = provider.sync(
                sync,
                approval_request=approval,
                approval_decision=decision,
                audit_event_store=store,
                idempotency_key="sync",
            )

        blocked = provider.create_task(TaskCreateRequest("Task"), idempotency_key="blocked")
        fixture.reconciled = True
        recovered = provider.create_task(TaskCreateRequest("Task"), idempotency_key="recovered")

        self.assertIs(OperationStatus.UNAVAILABLE, failed.status)
        self.assertIn("repository data drift", blocked.message)
        self.assertIs(OperationStatus.SUCCESS, recovered.status)


if __name__ == "__main__":
    unittest.main()
