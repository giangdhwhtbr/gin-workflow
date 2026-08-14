import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "plugins/gin-workflow/src/scripts"
LAUNCHER = SCRIPTS / "gin-workflow"
sys.path.insert(0, str(SCRIPTS))

from workflow_core.events import WorkflowEventStore  # noqa: E402
from workflow_core.manifests import ContextRequest, create_context_manifest  # noqa: E402
from workflow_core.configuration import load_effective_config  # noqa: E402
from workflow_core.models import EffectiveConfig  # noqa: E402
from workflow_core.router import route_next_stage  # noqa: E402
from workflow_core.worker_scheduler import WorkerScheduler, select_execution_strategy  # noqa: E402
from workflow_providers.claude_worker import ClaudeWorkerAdapter  # noqa: E402
from workflow_providers.contracts import (  # noqa: E402
    EvidenceCategory,
    EvidenceRecord,
    OperationStatus,
    TaskCreateRequest,
)
from workflow_providers.fakes import (  # noqa: E402
    FakeEvidenceProvider,
    FakeTaskTrackingProvider,
    FakeWorkspaceProvider,
)
from workflow_providers.registry import ProviderRegistry  # noqa: E402
from workflow_providers.sequential_worker import SequentialWorkerAdapter  # noqa: E402
from workflow_providers.worker_dispatch import (  # noqa: E402
    REQUIRED_RESULT_FIELDS,
    WorkerDispatcher,
    WorkerRequest,
)


SECRET_VALUE = "sk-track7-private-value"


def completed_result(payload, *, status="completed", blocker=None):
    return {
        "status": status,
        "task_id": payload["task_id"],
        "summary": "completed by deterministic fake" if status == "completed" else "failed",
        "changed_files": [f"src/{payload['task_id']}.py"] if status == "completed" else [],
        "commits": [],
        "tests": [{"command": "python3 -m unittest", "outcome": "passed"}]
        if status == "completed"
        else [],
        "evidence": [{"kind": "test", "reference": payload["task_id"]}]
        if status == "completed"
        else [],
        "blockers": [blocker] if blocker else [],
    }


def worker_request(task_id):
    return WorkerRequest(
        objective=f"Implement {task_id}",
        constraints=("Only edit the assigned files",),
        generated_manifest=create_context_manifest(
            "execute",
            ContextRequest(
                required=({"path": "src", "available": True},),
                prohibited=(
                    {"classification": "secret", "name": "FAKE_TOKEN", "value": SECRET_VALUE},
                ),
                parent_context={"history": "must not cross the worker boundary"},
            ),
        ),
        isolation_policy={
            "mode": "isolated",
            "workspace_id": f"ws-{task_id}",
            "branch": f"worker/{task_id}",
        },
        expected_output=REQUIRED_RESULT_FIELDS,
        task_id=task_id,
        workflow_id="wf-e2e",
        retry_identity=f"wf-e2e:{task_id}",
        provider_role="backend",
        reasoning="medium",
    )


class WorkflowEndToEndTests(unittest.TestCase):
    def run_setup(self, repository, *arguments):
        environment = os.environ.copy()
        environment["FAKE_PROVIDER_TOKEN"] = SECRET_VALUE
        return subprocess.run(
            [
                sys.executable,
                str(LAUNCHER),
                "setup",
                *arguments,
                "--repository",
                str(repository),
                "--format",
                "json",
                "--non-interactive",
            ],
            cwd=ROOT,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_setup_is_idempotent_and_lifecycle_consumes_generated_effective_config_only(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)

            first = self.run_setup(
                repository, "init", "--harness", "codex", "--approve"
            )
            first_snapshot = {
                path.relative_to(repository): path.read_bytes()
                for path in repository.rglob("*")
                if path.is_file()
            }
            second = self.run_setup(repository, "init", "--harness", "codex")
            second_snapshot = {
                path.relative_to(repository): path.read_bytes()
                for path in repository.rglob("*")
                if path.is_file()
            }
            configured = self.run_setup(
                repository,
                "configure",
                "--approve",
                "--set",
                "providers.task_tracking=fake",
                "--set",
                "providers.knowledge=fake",
                "--set",
                "providers.workspace=fake",
                "--set",
                "providers.review=fake",
                "--set",
                "providers.evidence=fake",
                "--set",
                "providers.notifications=fake",
                "--set",
                "integrations.fake.api_key=secret_ref:env:FAKE_PROVIDER_TOKEN",
            )

            self.assertEqual(0, first.returncode, first.stderr)
            self.assertEqual("initialized", json.loads(first.stdout)["status"])
            self.assertEqual(0, second.returncode, second.stderr)
            self.assertEqual("already_initialized", json.loads(second.stdout)["status"])
            self.assertEqual(first_snapshot, second_snapshot)
            self.assertEqual(0, configured.returncode, configured.stderr)

            workflow = repository / ".agent-workflow"
            effective_path = workflow / "generated/effective-config.yaml"
            provenance_path = workflow / "generated/config-provenance.yaml"
            effective_text = effective_path.read_text(encoding="utf-8")
            serialized_artifacts = effective_text + provenance_path.read_text(encoding="utf-8")
            self.assertNotIn(SECRET_VALUE, serialized_artifacts)
            self.assertIn("secret_ref:env:FAKE_PROVIDER_TOKEN", effective_text)

            effective = load_effective_config(repository)
            registry = ProviderRegistry.from_effective_config(effective)
            self.assertIsInstance(registry.task_tracking, FakeTaskTrackingProvider)
            self.assertIsInstance(registry.evidence, FakeEvidenceProvider)

            decision = route_next_stage(
                {
                    "requirement_confirmed": True,
                    "plan_approved": True,
                    "orchestration_ready": True,
                },
                effective,
            )
            self.assertEqual(("execute", "route"), (decision.stage, decision.decision))
            with self.assertRaisesRegex(TypeError, "EffectiveConfig"):
                route_next_stage({}, effective.to_dict())

    def test_direct_and_parallel_routes_preserve_partial_worker_completion(self):
        direct = select_execution_strategy(task_count=3, parallelizable=True)
        parallel = select_execution_strategy(task_count=4, parallelizable=True)

        self.assertEqual(("direct", "sequential"), (direct.mode, direct.workers.mode))
        self.assertEqual(("worker", "parallel"), (parallel.mode, parallel.workers.mode))

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            task_tracking = FakeTaskTrackingProvider()
            requests = tuple(worker_request(f"track-{index}") for index in range(1, 5))
            for request in requests:
                created = task_tracking.create_task(
                    TaskCreateRequest(request.task_id),
                    idempotency_key=f"create:{request.task_id}",
                )
                self.assertIs(OperationStatus.SUCCESS, created.status)

            calls = []

            def fake_worker(payload):
                calls.append(payload["task_id"])
                if payload["task_id"] == "track-4":
                    return completed_result(
                        payload, status="failed", blocker="deterministic_failure"
                    )
                return completed_result(payload)

            scheduler = WorkerScheduler(
                WorkerDispatcher(
                    SequentialWorkerAdapter(fake_worker),
                    WorkflowEventStore(root / "runtime/events.jsonl"),
                ),
                task_tracking=task_tracking,
                workspace=FakeWorkspaceProvider(root / "worktrees"),
                max_parallel_workers=2,
            )

            outcome = scheduler.schedule(requests)

            self.assertEqual(
                ("track-1", "track-2", "track-3"),
                tuple(result.task_id for result in outcome.completed),
            )
            self.assertEqual(("track-4",), tuple(result.task_id for result in outcome.failed))
            self.assertEqual(("deterministic_failure",), outcome.failed[0].blockers)
            self.assertEqual({request.task_id for request in requests}, set(calls))

    def test_unavailable_native_worker_falls_back_without_exposing_secret_context(self):
        captured_payloads = []

        def fallback_runner(payload):
            captured_payloads.append(payload)
            return completed_result(payload)

        with tempfile.TemporaryDirectory() as directory:
            event_store = WorkflowEventStore(Path(directory) / "events.jsonl")
            dispatcher = WorkerDispatcher(
                ClaudeWorkerAdapter(),
                event_store,
                fallback=SequentialWorkerAdapter(fallback_runner),
            )

            receipt = dispatcher.dispatch(worker_request("fallback-task"))
            result = dispatcher.collect_result(receipt.worker_id)

            self.assertTrue(receipt.fallback_used)
            self.assertEqual("completed", result.status)
            self.assertEqual(1, len(captured_payloads))
            self.assertNotIn(SECRET_VALUE, json.dumps(captured_payloads[0], sort_keys=True))
            self.assertNotIn(SECRET_VALUE, event_store.path.read_text(encoding="utf-8"))
            self.assertEqual(
                [
                    "worker.requested",
                    "worker.unavailable",
                    "worker.assigned",
                    "worker.started",
                    "worker.context_loaded",
                    "worker.progress_updated",
                    "worker.completed",
                ],
                [event.event_type for event in event_store.read_all()],
            )

    def test_verification_evidence_gates_shipping_until_every_category_succeeds(self):
        provider = FakeEvidenceProvider()
        state = {
            "requirement_confirmed": True,
            "plan_approved": True,
            "orchestration_ready": True,
            "implementation_complete": True,
        }
        config = EffectiveConfig({"schema_version": "2.1"}, Path.cwd())
        fixtures = (
            ("tests-failed", EvidenceCategory.TESTS, "failed"),
            ("review-approved", EvidenceCategory.REVIEWS, "approved"),
            ("repository-recorded", EvidenceCategory.REPOSITORY, "recorded"),
        )
        for evidence_id, category, outcome in fixtures:
            recorded = provider.record(
                EvidenceRecord(
                    evidence_id=evidence_id,
                    task_id="track-7",
                    category=category,
                    outcome=outcome,
                    reference=evidence_id,
                ),
                idempotency_key=evidence_id,
            )
            self.assertIs(OperationStatus.SUCCESS, recorded.status)

        incomplete = provider.completeness("track-7").value
        verify = route_next_stage({**state, "verification_passed": incomplete.complete}, config)
        self.assertFalse(incomplete.complete)
        self.assertEqual(("tests",), incomplete.missing_categories)
        self.assertEqual("verify", verify.stage)

        provider.record(
            EvidenceRecord(
                evidence_id="tests-passed",
                task_id="track-7",
                category=EvidenceCategory.TESTS,
                outcome="passed",
                reference="python3 -m unittest discover -s tests -p test_*.py -v",
            ),
            idempotency_key="tests-passed",
        )
        complete = provider.completeness("track-7").value
        ship = route_next_stage({**state, "verification_passed": complete.complete}, config)

        self.assertTrue(complete.complete)
        self.assertEqual((), complete.missing_categories)
        self.assertEqual("ship", ship.stage)


if __name__ == "__main__":
    unittest.main()
