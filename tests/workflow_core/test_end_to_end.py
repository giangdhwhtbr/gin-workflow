import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "plugins/gin-workflow/src/scripts"
LAUNCHER = SCRIPTS / "gin-workflow"
sys.path.insert(0, str(SCRIPTS))

from workflow_core.events import WorkflowEventStore  # noqa: E402
from workflow_core.assignments import RouteCandidate  # noqa: E402
from workflow_core.manifests import ContextRequest, create_context_manifest  # noqa: E402
from workflow_core.configuration import load_effective_config  # noqa: E402
from workflow_core.models import EffectiveConfig  # noqa: E402
from workflow_core.provider_config import ProviderModelConfig  # noqa: E402
from workflow_core.review_coordinator import ReviewContext, ReviewCoordinator  # noqa: E402
from workflow_core.router import route_next_stage  # noqa: E402
from workflow_core.worker_scheduler import WorkerScheduler, select_execution_strategy  # noqa: E402
from workflow_providers.claude_worker import ClaudeWorkerAdapter  # noqa: E402
from workflow_providers.contracts import (  # noqa: E402
    EvidenceCategory,
    EvidenceRecord,
    OperationStatus,
    ReviewFinding,
    ReviewStatus,
    TaskCreateRequest,
    WorkspaceRequest,
)
from workflow_providers.fakes import (  # noqa: E402
    FakeEvidenceProvider,
    FakeTaskTrackingProvider,
    FakeWorkspaceProvider,
)
from workflow_providers.registry import ProviderRegistry  # noqa: E402
from workflow_providers.circuit_breaker import CircuitState, FailureKind  # noqa: E402
from workflow_providers.native_cli import NativeCliError, NativeCliOutput  # noqa: E402
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
    def test_cross_harness_quota_fallback_review_revision_and_closure_gate(self):
        class FakeNativeRunner:
            def __init__(self):
                self.routes = []
                self.review_runs = 0

            def run(self, invocation, *, cancel_event=None):
                model = invocation.argv[invocation.argv.index("--model") + 1]
                provider = {"claude": "claude", "codex": "codex", "agy": "antigravity"}[invocation.argv[0]]
                self.routes.append((provider, model))
                if provider == "claude" and model == "opus":
                    raise NativeCliError(FailureKind.QUOTA, "classified quota")
                payload = json.loads(invocation.stdin.decode("utf-8").splitlines()[-1])
                normalized = completed_result(payload)
                if payload["objective"].startswith("Review approved implementation scope"):
                    self.review_runs += 1
                    normalized["changed_files"] = []
                    normalized["evidence"] = (
                        [{
                            "kind": "review_decision",
                            "decision": "changes_requested",
                        }, {
                            "kind": "review_finding",
                            "finding_id": "F-001",
                            "severity": "IMPORTANT",
                            "status": "open",
                            "location": "src/frontend.py:1",
                            "expected_behavior": "handle empty state",
                            "evidence": "fake-native review",
                        }]
                        if self.review_runs == 1
                        else [
                            {"kind": "review_decision", "decision": "approved"},
                            {
                                "kind": "review_finding", "finding_id": "F-001",
                                "severity": "IMPORTANT", "status": "verified",
                                "location": "src/frontend.py:1",
                                "expected_behavior": "handle empty state",
                                "evidence": "fake-native re-review passed",
                            },
                        ]
                    )
                return NativeCliOutput((normalized,))

        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            yaml = __import__("yaml")
            portable = yaml.safe_load(
                (ROOT / "plugins/gin-workflow/src/examples/config.full.yaml").read_text(encoding="utf-8")
            )
            portable["providers"] = {
                "task_tracking": "fake", "knowledge": "fake", "workspace": "fake",
                "review": "fake", "evidence": "fake", "notifications": "fake",
            }
            effective = EffectiveConfig(portable, repository)
            local_raw = yaml.safe_load(
                (ROOT / "plugins/gin-workflow/src/examples/providers.local.example.yaml").read_text(encoding="utf-8")
            )["providers"]
            local = {
                name: ProviderModelConfig(name, entry["executable"], entry["models"])
                for name, entry in local_raw.items()
            }
            runner = FakeNativeRunner()
            events = WorkflowEventStore(repository / ".agent-workflow/runtime/events.jsonl")
            registry = ProviderRegistry.from_effective_config(
                effective,
                provider_local=local,
                native_runner=runner,
                worker_health={name: (lambda _candidate: True) for name in local},
                event_store=events,
            )
            router = registry.worker
            self.assertIsNotNone(router)

            def routed(task_id, role, reasoning, retry):
                item = worker_request(task_id)
                created = registry.workspace.create(
                    WorkspaceRequest(
                        item.isolation_policy["workspace_id"],
                        item.isolation_policy["branch"],
                    ),
                    idempotency_key=f"{task_id}:workspace",
                )
                return replace(
                    item,
                    provider_role=role,
                    reasoning=reasoning,
                    retry_identity=retry,
                    isolation_policy={
                        **item.isolation_policy,
                        "workspace_path": str(created.value.path),
                    },
                )

            backend = routed("backend", "backend", "high", "backend:first")
            first = router.dispatch(backend)
            self.assertEqual("failed", router.collect_result(first.worker_id).status)
            retry = router.dispatch(replace(backend, retry_identity="backend:quota-fallback"))
            self.assertEqual("completed", router.collect_result(retry.worker_id).status)

            frontend = routed("frontend", "frontend", "medium", "frontend:first")
            frontend_receipt = router.dispatch(frontend)
            self.assertEqual("completed", router.collect_result(frontend_receipt.worker_id).status)

            coordinator = ReviewCoordinator(
                registry.review,
                require_independent=True,
                max_cycles=3,
                worker_dispatcher=router,
            )
            cycle = coordinator.request_review(
                task_id="frontend",
                cycle_number=1,
                provider_role="review",
                reasoning="high",
                implementation_route=(frontend_receipt.provider_name, frontend_receipt.model_alias),
                reviewer_candidates=(RouteCandidate("codex", "reasoning", False),),
                context=ReviewContext(
                    approved_scope=("src/frontend.py",),
                    diff="bounded diff",
                    acceptance_criteria=("renders",),
                    tests=({"command": "ui-test", "outcome": "passed"},),
                    evidence=({"kind": "test", "reference": "ui-test"},),
                ),
            )
            review_execution = coordinator.dispatch_review(
                cycle,
                replace(
                    frontend,
                    provider_role="review",
                    reasoning="high",
                    retry_identity="frontend:review:1",
                ),
            )
            self.assertEqual("changes_requested", review_execution.status)
            finding = review_execution.findings[0]
            revision = coordinator.route_revision(cycle, (finding,))
            revision_receipt = router.dispatch(
                replace(
                    frontend,
                    retry_identity=revision.revision_identity,
                    route_affinity=(revision.provider, revision.model),
                )
            )
            self.assertEqual("completed", router.collect_result(revision_receipt.worker_id).status)
            coordinator.complete_revision(cycle, revision)

            second_cycle = coordinator.request_review(
                task_id="frontend",
                cycle_number=2,
                provider_role="review",
                reasoning="high",
                implementation_route=(
                    revision_receipt.provider_name,
                    revision_receipt.model_alias,
                ),
                reviewer_candidates=(RouteCandidate("codex", "reasoning", False),),
                context=cycle.context,
            )
            approved_review = coordinator.dispatch_review(
                second_cycle,
                replace(
                    frontend,
                    provider_role="review",
                    reasoning="high",
                    retry_identity="frontend:review:2",
                ),
            )
            self.assertEqual("approved", approved_review.status)

            created = registry.task_tracking.create_task(
                TaskCreateRequest("frontend", status="in_progress"),
                idempotency_key="frontend:create",
            )
            task_id = created.value.task_id
            pending = coordinator.completion_decision(
                ReviewStatus("frontend", "changes-requested", 1, ("F-001",), (finding,)),
                acceptance_evidence_complete=False,
            )
            self.assertEqual("review_pending", pending.status)
            self.assertNotEqual("closed", registry.task_tracking.read_task(task_id).value.status)

            for evidence_id, category, outcome in (
                ("tests", EvidenceCategory.TESTS, "passed"),
                ("review", EvidenceCategory.REVIEWS, "approved"),
                ("repo", EvidenceCategory.REPOSITORY, "recorded"),
            ):
                registry.evidence.record(
                    EvidenceRecord(evidence_id, "frontend", category, outcome, evidence_id),
                    idempotency_key=evidence_id,
                )
            complete = registry.evidence.completeness("frontend").value
            approved = coordinator.completion_decision(
                ReviewStatus("frontend", "review-approved", 2, (), (replace(finding, status="verified"),)),
                acceptance_evidence_complete=complete.complete,
            )
            if approved.status == "ready_to_close":
                registry.task_tracking.update_task(
                    task_id, {"status": "closed"}, idempotency_key="frontend:close"
                )

            self.assertEqual(("codex", "reasoning", True), (retry.provider_name, retry.model_alias, retry.fallback_used))
            self.assertEqual(("antigravity", "gemini-flash"), (frontend_receipt.provider_name, frontend_receipt.model_alias))
            self.assertEqual(CircuitState.OPEN, router.breakers.state("claude", "opus").state)
            self.assertEqual(("codex", "reasoning"), cycle.reviewer_route)
            self.assertEqual(("codex", "reasoning"), (
                review_execution.receipt.provider_name,
                review_execution.receipt.model_alias,
            ))
            self.assertEqual(("antigravity", "gemini-flash"), (revision.provider, revision.model))
            self.assertEqual(2, runner.review_runs)
            self.assertTrue(complete.complete)
            self.assertEqual("closed", registry.task_tracking.read_task(task_id).value.status)
            self.assertNotIn(SECRET_VALUE, events.path.read_text(encoding="utf-8"))

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
