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
from workflow_core.assignments import (  # noqa: E402
    AssignmentRequest,
    RouteCandidate,
    validate_plan_assignments,
)
from workflow_core.identity import AcceptanceIdentity, RepositorySnapshot  # noqa: E402
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
    ReviewOutcomeRequest,
    ReviewRequest,
    TaskClosureRequest,
    ReviewFinding,
    ReviewStatus,
    TaskCreateRequest,
    WorkspaceRequest,
)
from workflow_providers.evidence import CompositeEvidenceAuthority  # noqa: E402
from workflow_providers.fakes import (  # noqa: E402
    FakeEvidenceProvider,
    FakeTaskTrackingProvider,
    FakeWorkspaceProvider,
)
from workflow_providers.registry import ProviderRegistry  # noqa: E402
from workflow_providers.circuit_breaker import CircuitState, FailureKind  # noqa: E402
from workflow_providers.native_cli import (  # noqa: E402
    NativeCliError,
    NativeCliOutput,
    NativeHealth,
)
from workflow_providers.review import ReviewLedgerProvider  # noqa: E402
from workflow_providers.task_tracking import BeadsTaskTrackingProvider  # noqa: E402
from workflow_providers.sequential_worker import SequentialWorkerAdapter  # noqa: E402
from workflow_providers.worker_dispatch import (  # noqa: E402
    REQUIRED_RESULT_FIELDS,
    WorkerDispatcher,
    WorkerRequest,
    WorkerResultContractError,
    normalize_worker_result,
)
from tests.workflow_providers.test_task_tracking_compatibility import (  # noqa: E402
    CliFixture,
)


SECRET_VALUE = "sk-track7-private-value"


def completed_result(payload, *, status="completed", blocker=None):
    result = {
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
    identity = payload.get("acceptance_identity")
    if identity is not None and status == "completed":
        repository = identity["repositories"][0]
        result.update(
            {
                "schema_version": "2.3",
                "acceptance_identity": identity,
                "tests": [
                    {
                        "argv": ["python3", "-m", "unittest"],
                        "exit_code": 0,
                        "started_at": "2026-08-20T09:58:00Z",
                        "finished_at": "2026-08-20T09:59:00Z",
                        "workspace_id": payload["isolation_policy"]["workspace_id"],
                        "repository_id": repository["repository_id"],
                        "attempt_id": identity["attempt_id"],
                        "source_tree_hash": repository["source_tree_hash"],
                    }
                ],
            }
        )
    return result


def evidence_fixture(task_id="frontend"):
    identity = AcceptanceIdentity(
        "wf-e2e",
        "attempt-1",
        task_id,
        (
            RepositorySnapshot(
                "primary",
                "scope-e2e",
                "tree-e2e",
                "checkpoint-e2e",
                f"refs/gin/review/{task_id}",
            ),
        ),
    )
    raw_identity = identity.to_dict()
    worker_store = {
        "worker-e2e": {
            "task_id": task_id,
            "worker_id": "worker-e2e",
            "status": "completed",
            "schema_version": "2.3",
            "request_acceptance_identity": raw_identity,
            "result_acceptance_identity": raw_identity,
            "request_workspace_id": f"ws-{task_id}",
            "tests": [
                {
                    "argv": ["python3", "-m", "unittest"],
                    "exit_code": 0,
                    "started_at": "2026-08-20T09:58:00Z",
                    "finished_at": "2026-08-20T09:59:00Z",
                    "workspace_id": f"ws-{task_id}",
                    "repository_id": "primary",
                    "attempt_id": "attempt-1",
                    "source_tree_hash": "tree-e2e",
                }
            ],
            "recorded_at": "2026-08-20T10:00:00Z",
        }
    }
    checkpoint_store = {
        "checkpoint-event-e2e": {
            "task_id": task_id,
            "checkpoint_event_id": "checkpoint-event-e2e",
            "acceptance_identity": raw_identity,
            "repositories": raw_identity["repositories"],
            "recorded_at": "2026-08-20T10:01:00Z",
        }
    }
    review_store = {
        "review-event-e2e": {
            "task_id": task_id,
            "review_event_id": "review-event-e2e",
            "ledger_revision": 7,
            "acceptance_identity": raw_identity,
            "status": "approved",
            "terminal": True,
            "recorded_at": "2026-08-20T10:01:30Z",
            "verification_event_id": "verification-event-e2e",
        }
    }
    verification_store = {
        "verification-event-e2e": {
            "task_id": task_id,
            "verification_event_id": "verification-event-e2e",
            "review_event_id": "review-event-e2e",
            "acceptance_identity": raw_identity,
            "status": "passed",
            "recorded_at": "2026-08-20T10:02:00Z",
        }
    }
    authority = CompositeEvidenceAuthority(
        worker_resolver=worker_store.get,
        checkpoint_resolver=checkpoint_store.get,
        review_resolver=review_store.get,
        verification_resolver=verification_store.get,
    )
    return identity, authority, (
        ("tests", EvidenceCategory.TESTS, "worker-e2e"),
        ("repo", EvidenceCategory.REPOSITORY, "checkpoint-event-e2e"),
        ("review", EvidenceCategory.REVIEWS, "review-event-e2e"),
    )


def record_from_authority(authority, evidence_id, category, reference):
    canonical = authority.resolve(category, reference)
    return EvidenceRecord(
        evidence_id=evidence_id,
        task_id=canonical["task_id"],
        category=category,
        outcome=canonical["outcome"],
        reference=reference,
        details=canonical["details"],
        acceptance_identity=AcceptanceIdentity.from_mapping(
            canonical["acceptance_identity"]
        ),
        recorded_at=canonical["recorded_at"],
    )


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
            portable["routing"]["circuit_breaker"]["failure_threshold"] = 1
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
            identity, authority, evidence_references = evidence_fixture("frontend")
            registry = ProviderRegistry.from_effective_config(
                effective,
                provider_local=local,
                native_runner=runner,
                worker_health={
                    **{name: (lambda _candidate: True) for name in local},
                    "antigravity": lambda _candidate: NativeHealth(
                        True, "ready", True
                    ),
                },
                event_store=events,
                evidence_authority=authority,
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

            for evidence_id, category, reference in evidence_references:
                registry.evidence.record(
                    record_from_authority(
                        authority, evidence_id, category, reference
                    ),
                    idempotency_key=evidence_id,
                )
            complete = registry.evidence.completeness("frontend", identity).value
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

    def test_acceptance_identity_survives_checkpoint_review_evidence_and_task_closure(self):
        from review_ledger.cli import (
            initialize_ledger,
            load_ledger,
            mutate_ledger,
            start_review,
        )

        class IdentityNativeRunner:
            def run(self, invocation, *, cancel_event=None):
                payload = json.loads(invocation.stdin.decode("utf-8").splitlines()[-1])
                return NativeCliOutput((completed_result(payload),))

        task_id = "integrity-e2e"
        workflow_id = "wf-integrity-e2e"
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            subprocess.run(
                ["git", "init"], cwd=repository, check=True, capture_output=True
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"], cwd=repository, check=True
            )
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"],
                cwd=repository,
                check=True,
            )
            (repository / "src").mkdir()
            (repository / "src/app.py").write_text("value = 1\n", encoding="utf-8")
            subprocess.run(["git", "add", "src/app.py"], cwd=repository, check=True)
            subprocess.run(
                ["git", "commit", "-m", "base"],
                cwd=repository,
                check=True,
                capture_output=True,
            )
            (repository / "src/app.py").write_text("value = 2\n", encoding="utf-8")
            (repository / "src/new.py").write_text("new = True\n", encoding="utf-8")
            head_before = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repository,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            index_before = subprocess.run(
                ["git", "diff", "--cached", "--binary"],
                cwd=repository,
                check=True,
                capture_output=True,
            ).stdout
            source_status_before = subprocess.run(
                ["git", "status", "--porcelain=v1", "--", "src"],
                cwd=repository,
                check=True,
                capture_output=True,
                text=True,
            ).stdout

            scope = {
                "included_paths": ["src"],
                "excluded_artifact_paths": [],
                "allowed_generated_paths": [],
                "nested_repository_paths": [],
            }
            checkpoint = initialize_ledger(
                bead_id=task_id,
                repository_id="primary",
                role="primary",
                repo_path=str(repository),
                review_ref=f"refs/gin/review/{task_id}",
                base_ref="HEAD",
                scope=scope,
                actor_role="worker",
                actor_id="worker-e2e",
                base_dir=str(repository),
            )
            self.assertEqual(
                head_before,
                subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=repository,
                    check=True,
                    capture_output=True,
                    text=True,
                ).stdout.strip(),
            )
            self.assertEqual(
                index_before,
                subprocess.run(
                    ["git", "diff", "--cached", "--binary"],
                    cwd=repository,
                    check=True,
                    capture_output=True,
                ).stdout,
            )
            self.assertEqual(
                source_status_before,
                subprocess.run(
                    ["git", "status", "--porcelain=v1", "--", "src"],
                    cwd=repository,
                    check=True,
                    capture_output=True,
                    text=True,
                ).stdout,
            )
            _, initial_projection = load_ledger(task_id, str(repository))
            stored_repository = initial_projection.repositories[0]
            identity = AcceptanceIdentity(
                workflow_id,
                "attempt-1",
                task_id,
                (
                    RepositorySnapshot(
                        "primary",
                        checkpoint.source_scope_hash,
                        checkpoint.source_tree_hash,
                        checkpoint.checkpoint_sha,
                        checkpoint.checkpoint_ref,
                    ),
                ),
            )

            portable = EffectiveConfig(
                {
                    "schema_version": "2.3",
                    "harness": "codex",
                    "providers": {
                        "task_tracking": "fake",
                        "knowledge": "fake",
                        "workspace": "fake",
                        "review": "review-ledger",
                        "evidence": "fake",
                        "notifications": "fake",
                    },
                    "routing": {
                        "roles": {
                            "backend": {"preferred": ["codex"], "fallback": []}
                        },
                        "concurrency": {"codex": 1},
                        "queue": {"max_wait_seconds": 0},
                        "worker": {"timeout_seconds": 30, "max_retries": 0},
                        "circuit_breaker": {
                            "failure_threshold": 1,
                            "cooldown_seconds": 10,
                            "half_open_max_probes": 1,
                        },
                    },
                },
                repository,
            )
            plan_request = AssignmentRequest(
                task_id, "backend", "high", "codex", workflow_id
            )
            self.assertEqual((), validate_plan_assignments((plan_request,), portable))

            task_cli = CliFixture("bd")
            task_cli.task["id"] = task_id
            task_cli.task["status"] = "in_progress"
            task_cli.readiness_payload = [{"id": task_id}]
            tasks = BeadsTaskTrackingProvider(repository, runner=task_cli)
            self.assertTrue(tasks.preflight().value.healthy)
            created_task = tasks.create_task(
                TaskCreateRequest(
                    task_id,
                    status="in_progress",
                    notes=("identity-bound implementation",),
                    acceptance_criteria=("all authoritative evidence is complete",),
                ),
                idempotency_key="create-e2e",
            )
            self.assertIs(OperationStatus.SUCCESS, created_task.status)
            self.assertTrue(tasks.readiness(task_id).value.ready)

            worker_store = {}
            checkpoint_store = {}
            review_store = {}
            verification_store = {}
            authority = CompositeEvidenceAuthority(
                worker_resolver=worker_store.get,
                checkpoint_resolver=checkpoint_store.get,
                review_resolver=review_store.get,
                verification_resolver=verification_store.get,
            )
            registry = ProviderRegistry.from_effective_config(
                portable,
                provider_local={
                    "codex": ProviderModelConfig(
                        "codex", "codex", {"high": "reasoning"}
                    )
                },
                native_runner=IdentityNativeRunner(),
                worker_health={
                    "codex": lambda _candidate: NativeHealth(True, "ready", True)
                },
                event_store=WorkflowEventStore(
                    repository / ".agent-workflow/runtime/events.jsonl"
                ),
                evidence_authority=authority,
            )
            workspace = registry.workspace.create(
                WorkspaceRequest(f"ws-{task_id}", f"worker/{task_id}"),
                idempotency_key="workspace-e2e",
            ).value
            request = replace(
                worker_request(task_id),
                workflow_id=workflow_id,
                retry_identity=f"{workflow_id}:{task_id}:attempt-1",
                acceptance_identity=identity,
                reasoning="high",
                isolation_policy={
                    "mode": "isolated",
                    "workspace_id": f"ws-{task_id}",
                    "branch": f"worker/{task_id}",
                    "workspace_path": str(workspace.path),
                },
            )
            receipt = registry.worker.dispatch(request)
            result = registry.worker.collect_result(receipt.worker_id)
            self.assertEqual(identity, result.acceptance_identity)
            self.assertEqual(("completed", "2.3"), (result.status, result.schema_version), result)
            self.assertTrue(all(test.passed and test.auditable for test in result.tests))
            worker_store[receipt.worker_id] = {
                "task_id": task_id,
                "worker_id": receipt.worker_id,
                "status": result.status,
                "schema_version": result.schema_version,
                "request_acceptance_identity": identity.to_dict(),
                "result_acceptance_identity": result.acceptance_identity.to_dict(),
                "request_workspace_id": request.isolation_policy["workspace_id"],
                "tests": [test.to_dict() for test in result.tests],
                "recorded_at": "2026-08-20T10:00:00Z",
            }

            requested = registry.review.request(
                ReviewRequest(task_id, "worker-e2e"), idempotency_key="review-request"
            )
            self.assertIs(OperationStatus.SUCCESS, requested.status)
            _, leased = start_review(
                task_id,
                "reviewer-e2e",
                requested_lease_id="lease-e2e",
                base_dir=str(repository),
            )
            self.assertEqual("lease-e2e", leased.active_lease.lease_id)
            review_status = registry.review.status(task_id).value
            approved = registry.review.record_outcome(
                ReviewOutcomeRequest(
                    task_id=task_id,
                    actor_id="reviewer-e2e",
                    decision="approved",
                    lease_id="lease-e2e",
                    acceptance_identity=identity,
                    expected_ledger_revision=review_status.ledger_revision,
                ),
                idempotency_key="review-approved",
            )
            self.assertIs(OperationStatus.SUCCESS, approved.status, approved.message)
            log, approved_projection = load_ledger(task_id, str(repository))
            approval_event = log.events[-1]
            self.assertEqual("review-approved", approval_event.action)
            approved_repository = approval_event.payload["approved_repositories"][0]
            self.assertEqual(
                identity.to_dict()["repositories"][0],
                {
                    field: approved_repository[field]
                    for field in (
                        "repository_id",
                        "source_scope_hash",
                        "source_tree_hash",
                        "checkpoint_sha",
                        "checkpoint_ref",
                    )
                },
            )

            mutate_ledger(
                task_id,
                "verification-started",
                {},
                "verifier",
                "verifier-e2e",
                base_dir=str(repository),
                lease_id="lease-e2e",
            )
            log, _ = mutate_ledger(
                task_id,
                "verification-passed",
                {},
                "verifier",
                "verifier-e2e",
                base_dir=str(repository),
                lease_id="lease-e2e",
            )
            verification_event = log.events[-1]
            checkpoint_event = log.events[0]
            review_reference = approved_projection.review_event_id
            checkpoint_store[checkpoint_event.event_id] = {
                "task_id": task_id,
                "checkpoint_event_id": checkpoint_event.event_id,
                "acceptance_identity": identity.to_dict(),
                "repositories": identity.to_dict()["repositories"],
                "recorded_at": checkpoint_event.timestamp,
            }
            review_store[review_reference] = {
                "task_id": task_id,
                "review_event_id": review_reference,
                "ledger_revision": approved_projection.ledger_revision,
                "acceptance_identity": identity.to_dict(),
                "status": "approved",
                "terminal": True,
                "recorded_at": approval_event.timestamp,
                "verification_event_id": verification_event.event_id,
            }
            verification_store[verification_event.event_id] = {
                "task_id": task_id,
                "verification_event_id": verification_event.event_id,
                "review_event_id": review_reference,
                "acceptance_identity": identity.to_dict(),
                "status": "passed",
                "recorded_at": verification_event.timestamp,
            }
            evidence_references = (
                ("tests-e2e", EvidenceCategory.TESTS, receipt.worker_id),
                ("repository-e2e", EvidenceCategory.REPOSITORY, checkpoint_event.event_id),
                ("review-e2e", EvidenceCategory.REVIEWS, review_reference),
            )
            for evidence_id, category, reference in evidence_references:
                recorded = registry.evidence.record(
                    record_from_authority(authority, evidence_id, category, reference),
                    idempotency_key=evidence_id,
                )
                self.assertIs(OperationStatus.SUCCESS, recorded.status, recorded.message)
            complete = registry.evidence.completeness(task_id, identity).value
            self.assertTrue(complete.complete, complete.diagnostics)

            closed = tasks.close_task(
                TaskClosureRequest(
                    task_id,
                    "authoritative acceptance complete",
                    tuple(record.evidence_id for record in complete.evidence),
                ),
                idempotency_key="close-e2e",
            )
            self.assertIs(OperationStatus.SUCCESS, closed.status, closed.message)
            self.assertEqual("closed", closed.value.status)
            self.assertEqual(
                tuple(record.evidence_id for record in complete.evidence),
                closed.value.acceptance_evidence,
            )
            self.assertEqual(
                stored_repository["checkpoint_ref"], identity.repositories[0].checkpoint_ref
            )

    def test_single_field_adversarial_variants_fail_closed(self):
        from review_ledger.cli import initialize_ledger, load_ledger, mutate_ledger, start_review

        task_id = "adversarial"
        identity, authority, references = evidence_fixture(task_id)
        canonical = {
            category: record_from_authority(authority, evidence_id, category, reference)
            for evidence_id, category, reference in references
        }
        repository = identity.repositories[0]
        identity_variants = (
            AcceptanceIdentity(
                identity.workflow_id,
                identity.attempt_id,
                identity.task_id,
                (replace(repository, source_scope_hash="scope-other"),),
            ),
            AcceptanceIdentity(
                identity.workflow_id,
                identity.attempt_id,
                identity.task_id,
                (replace(repository, source_tree_hash="tree-other"),),
            ),
            AcceptanceIdentity(
                identity.workflow_id,
                identity.attempt_id,
                identity.task_id,
                (replace(repository, checkpoint_ref="refs/gin/review/other"),),
            ),
            AcceptanceIdentity(
                identity.workflow_id,
                "attempt-other",
                identity.task_id,
                identity.repositories,
            ),
            AcceptanceIdentity(
                identity.workflow_id,
                identity.attempt_id,
                "task-other",
                identity.repositories,
            ),
        )
        evidence_variants = [
            replace(canonical[EvidenceCategory.REPOSITORY], acceptance_identity=variant)
            for variant in identity_variants
        ]
        review_record = canonical[EvidenceCategory.REVIEWS]
        evidence_variants.extend(
            (
                replace(review_record, reference="review-event-other"),
                replace(review_record, recorded_at="2026-08-20T09:00:00Z"),
                replace(
                    canonical[EvidenceCategory.TESTS],
                    details={
                        **canonical[EvidenceCategory.TESTS].details,
                        "tests": [
                            {
                                **canonical[EvidenceCategory.TESTS].details["tests"][0],
                                "exit_code": 1,
                            }
                        ],
                    },
                ),
            )
        )
        for index, variant in enumerate(evidence_variants):
            with self.subTest(boundary="evidence", index=index):
                provider = FakeEvidenceProvider(authority=authority)
                rejected = provider.record(variant, idempotency_key=f"variant-{index}")
                self.assertIs(OperationStatus.INVALID, rejected.status)
                self.assertFalse(provider.completeness(task_id, identity).value.complete)

        request = replace(
            worker_request(task_id),
            acceptance_identity=identity,
            isolation_policy={"mode": "isolated", "workspace_id": f"ws-{task_id}"},
        )
        accepted_payload = completed_result(request.to_payload())
        worker_variants = (
            {
                **accepted_payload,
                "tests": [
                    {**accepted_payload["tests"][0], "workspace_id": "ws-other"}
                ],
            },
        )
        for payload in worker_variants:
            with self.subTest(boundary="worker", tests=payload["tests"]):
                with self.assertRaises(WorkerResultContractError):
                    normalize_worker_result(payload, request)

        unhealthy_cli = CliFixture("bd", drift="database/jsonl mismatch")
        unhealthy_tasks = BeadsTaskTrackingProvider(Path.cwd(), runner=unhealthy_cli)
        unavailable = unhealthy_tasks.create_task(
            TaskCreateRequest("must-not-mutate"), idempotency_key="unhealthy"
        )
        self.assertIs(OperationStatus.UNAVAILABLE, unavailable.status)
        self.assertFalse(
            any(
                len(call) > 1 and call[1] == "create" and "--help" not in call
                for call in unhealthy_cli.calls
            )
        )

        with tempfile.TemporaryDirectory() as directory:
            repository_root = Path(directory)
            subprocess.run(
                ["git", "init"], cwd=repository_root, check=True, capture_output=True
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"],
                cwd=repository_root,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"],
                cwd=repository_root,
                check=True,
            )
            (repository_root / "src").mkdir()
            (repository_root / "src/app.py").write_text("ok = True\n", encoding="utf-8")
            subprocess.run(["git", "add", "src/app.py"], cwd=repository_root, check=True)
            subprocess.run(
                ["git", "commit", "-m", "base"],
                cwd=repository_root,
                check=True,
                capture_output=True,
            )
            initialize_ledger(
                bead_id="lease-adversarial",
                repository_id="primary",
                role="primary",
                repo_path=str(repository_root),
                review_ref="refs/gin/review/lease-adversarial",
                base_ref="HEAD",
                scope={"included_paths": ["src"]},
                actor_role="worker",
                actor_id="worker",
                base_dir=str(repository_root),
            )
            reviews = ReviewLedgerProvider(repository_root)
            reviews.request(
                ReviewRequest("lease-adversarial", "worker"),
                idempotency_key="request",
            )
            start_review(
                "lease-adversarial",
                "reviewer",
                requested_lease_id="lease-valid",
                base_dir=str(repository_root),
            )
            _, before = load_ledger("lease-adversarial", str(repository_root))
            with self.assertRaisesRegex(Exception, "lease"):
                mutate_ledger(
                    "lease-adversarial",
                    "finding-created",
                    {"finding_id": "F-001", "severity": "IMPORTANT"},
                    "reviewer",
                    "reviewer",
                    base_dir=str(repository_root),
                    lease_id="lease-other",
                )
            _, after = load_ledger("lease-adversarial", str(repository_root))
            self.assertEqual(before.ledger_revision, after.ledger_revision)

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
            _, authority, _ = evidence_fixture("setup-task")
            registry = ProviderRegistry.from_effective_config(
                effective, evidence_authority=authority
            )
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
        identity, authority, references = evidence_fixture("track-7")
        provider = FakeEvidenceProvider(authority=authority)
        state = {
            "requirement_confirmed": True,
            "plan_approved": True,
            "orchestration_ready": True,
            "implementation_complete": True,
        }
        config = EffectiveConfig({"schema_version": "2.3"}, Path.cwd())
        for evidence_id, category, reference in references[1:]:
            recorded = provider.record(
                record_from_authority(authority, evidence_id, category, reference),
                idempotency_key=evidence_id,
            )
            self.assertIs(OperationStatus.SUCCESS, recorded.status)

        incomplete = provider.completeness("track-7", identity).value
        verify = route_next_stage({**state, "verification_passed": incomplete.complete}, config)
        self.assertFalse(incomplete.complete)
        self.assertEqual(("tests",), incomplete.missing_categories)
        self.assertEqual("verify", verify.stage)

        tests_record = record_from_authority(
            authority, "tests-passed", EvidenceCategory.TESTS, "worker-e2e"
        )
        provider.record(tests_record, idempotency_key="tests-passed")
        complete = provider.completeness("track-7", identity).value
        ship = route_next_stage({**state, "verification_passed": complete.complete}, config)

        self.assertTrue(complete.complete)
        self.assertEqual((), complete.missing_categories)
        self.assertEqual("ship", ship.stage)


if __name__ == "__main__":
    unittest.main()
