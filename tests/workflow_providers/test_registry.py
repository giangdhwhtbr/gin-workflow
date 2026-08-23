from dataclasses import replace
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core.models import EffectiveConfig  # noqa: E402
from workflow_core.manifests import ContextRequest, create_context_manifest  # noqa: E402
from workflow_core.identity import AcceptanceIdentity, RepositorySnapshot  # noqa: E402
from workflow_core.provider_config import ProviderModelConfig  # noqa: E402
from workflow_providers.contracts import (  # noqa: E402
    EvidenceCategory,
    EvidenceRecord,
    OperationStatus,
    WorkspaceRequest,
)
from workflow_providers.evidence import CompositeEvidenceAuthority, FileEvidenceProvider  # noqa: E402
from workflow_providers.fakes import (  # noqa: E402
    FakeEvidenceProvider,
    FakeKnowledgeProvider,
    FakeNotificationProvider,
    FakeReviewProvider,
    FakeTaskTrackingProvider,
    FakeWorkspaceProvider,
)
from workflow_providers.knowledge import RepositoryKnowledgeProvider  # noqa: E402
from workflow_providers.notifications import TelegramNotificationProvider  # noqa: E402
from workflow_providers.native_cli import NativeCliOutput, NativeHealth  # noqa: E402
from workflow_providers.registry import ProviderRegistry, RegistryError  # noqa: E402
from workflow_providers.routed_worker import RoutedWorkerDispatcher  # noqa: E402
from workflow_providers.review import ReviewLedgerProvider  # noqa: E402
from workflow_providers.task_tracking import BeadsTaskTrackingProvider  # noqa: E402
from workflow_providers.workspace import WorktreeWorkspaceProvider  # noqa: E402
from workflow_providers.worker_dispatch import REQUIRED_RESULT_FIELDS, WorkerRequest  # noqa: E402


class ProviderRegistryTests(unittest.TestCase):
    @staticmethod
    def evidence_config(root):
        return EffectiveConfig(
            {
                "schema_version": "2.3",
                "providers": {
                    "task_tracking": "fake",
                    "knowledge": "fake",
                    "workspace": "fake",
                    "review": "fake",
                    "evidence": "fake",
                    "notifications": "fake",
                },
            },
            Path(root),
        )

    def antigravity_config(self, root):
        return EffectiveConfig(
            {
                "schema_version": "2.3",
                "harness": "codex",
                "providers": {
                    "task_tracking": "fake", "knowledge": "fake", "workspace": "fake",
                    "review": "fake", "evidence": "fake", "notifications": "fake",
                },
                "routing": {
                    "roles": {
                        "backend": {
                            "preferred": ["antigravity"],
                            "fallback": ["codex"],
                        }
                    },
                    "concurrency": {"antigravity": 1, "codex": 1},
                    "queue": {"max_wait_seconds": 0},
                    "worker": {"timeout_seconds": 17, "max_retries": 0},
                    "circuit_breaker": {
                        "failure_threshold": 1,
                        "cooldown_seconds": 10,
                        "half_open_max_probes": 1,
                    },
                },
            },
            Path(root),
        )

    @staticmethod
    def composite_authority():
        identity = AcceptanceIdentity(
            workflow_id="wf-1",
            attempt_id="attempt-1",
            task_id="task-1",
            repositories=(
                RepositorySnapshot(
                    "primary",
                    "scope-1",
                    "tree-1",
                    "checkpoint-1",
                    "refs/gin/review/task-1",
                ),
            ),
        ).to_dict()
        test_results = [
            {
                "argv": ["python3", "-m", "unittest"],
                "exit_code": 0,
                "started_at": "2026-08-20T09:58:00Z",
                "finished_at": "2026-08-20T09:59:00Z",
                "workspace_id": "ws-task-1",
                "repository_id": "primary",
                "attempt_id": "attempt-1",
                "source_tree_hash": "tree-1",
            }
        ]
        worker_store = {
            "worker-1": {
                "task_id": "task-1",
                "worker_id": "worker-1",
                "status": "completed",
                "schema_version": "2.3",
                "request_acceptance_identity": identity,
                "result_acceptance_identity": identity,
                "request_workspace_id": "ws-task-1",
                "tests": test_results,
                "recorded_at": "2026-08-20T10:00:00Z",
            }
        }
        checkpoint_store = {
            "checkpoint-event-1": {
                "task_id": "task-1",
                "checkpoint_event_id": "checkpoint-event-1",
                "acceptance_identity": identity,
                "repositories": identity["repositories"],
                "recorded_at": "2026-08-20T10:01:00Z",
            }
        }
        review_store = {
            "review-event-1": {
                "task_id": "task-1",
                "review_event_id": "review-event-1",
                "ledger_revision": 7,
                "acceptance_identity": identity,
                "status": "approved",
                "terminal": True,
                "recorded_at": "2026-08-20T10:01:30Z",
                "verification_event_id": "verification-event-1",
            }
        }
        verification_store = {
            "verification-event-1": {
                "task_id": "task-1",
                "verification_event_id": "verification-event-1",
                "review_event_id": "review-event-1",
                "acceptance_identity": identity,
                "status": "passed",
                "recorded_at": "2026-08-20T10:02:00Z",
            }
        }
        return CompositeEvidenceAuthority(
            worker_resolver=worker_store.get,
            checkpoint_resolver=checkpoint_store.get,
            review_resolver=review_store.get,
            verification_resolver=verification_store.get,
        )

    def test_schema_23_registry_requires_authoritative_evidence_sources(self):
        class EchoAuthority:
            def resolve(self, _category, _reference):
                return {}

        with tempfile.TemporaryDirectory() as directory:
            for authority in (None, EchoAuthority()):
                with self.subTest(authority=authority):
                    with self.assertRaisesRegex(RegistryError, "CompositeEvidenceAuthority"):
                        ProviderRegistry.from_effective_config(
                            self.evidence_config(directory),
                            evidence_authority=authority,
                        )

    def test_registry_wires_independent_composite_authority_and_rejects_forgery(self):
        authority = self.composite_authority()
        with tempfile.TemporaryDirectory() as directory:
            registry = ProviderRegistry.from_config(
                self.evidence_config(directory),
                evidence_authority=authority,
            )
            references = (
                ("test", EvidenceCategory.TESTS, "worker-1"),
                ("repo", EvidenceCategory.REPOSITORY, "checkpoint-event-1"),
                ("review", EvidenceCategory.REVIEWS, "review-event-1"),
            )
            records = []
            for evidence_id, category, reference in references:
                canonical = authority.resolve(category, reference)
                records.append(
                    EvidenceRecord(
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
                )
            for record in records:
                self.assertIs(
                    OperationStatus.SUCCESS,
                    registry.evidence.record(
                        record,
                        idempotency_key=record.evidence_id,
                    ).status,
                )
            complete = registry.evidence.completeness(
                "task-1",
                records[0].acceptance_identity,
            )
            forged = replace(
                records[0],
                evidence_id="forged",
                details={
                    **records[0].details,
                    "tests": [
                        {
                            **records[0].details["tests"][0],
                            "workspace_id": "ws-forged",
                        }
                    ],
                },
            )

            rejected = registry.evidence.record(forged, idempotency_key="forged")

            self.assertTrue(complete.value.complete)
            self.assertIs(OperationStatus.INVALID, rejected.status)
            self.assertIn("authoritative", rejected.message)
    def routed_config(self, root):
        return EffectiveConfig(
            {
                "schema_version": "2.2",
                "harness": "codex",
                "providers": {
                    "task_tracking": "fake", "knowledge": "fake", "workspace": "fake",
                    "review": "fake", "evidence": "fake", "notifications": "fake",
                },
                "routing": {
                    "roles": {"backend": {"preferred": ["claude"], "fallback": []}},
                    "concurrency": {"claude": 2},
                    "queue": {"max_wait_seconds": 0},
                    "worker": {"timeout_seconds": 17, "max_retries": 3},
                    "circuit_breaker": {"failure_threshold": 1, "cooldown_seconds": 10, "half_open_max_probes": 1},
                },
            },
            Path(root),
        )

    def local(self):
        return {
            "claude": ProviderModelConfig(
                "claude", "claude", {"low": "haiku", "medium": "sonnet", "high": "opus"}
            )
        }

    def test_routed_worker_requires_explicit_machine_local_provider_injection(self):
        with tempfile.TemporaryDirectory() as directory:
            config = EffectiveConfig(
                {
                    "schema_version": "2.2",
                    "harness": "codex",
                    "providers": {
                        "task_tracking": "fake", "knowledge": "fake", "workspace": "fake",
                        "review": "fake", "evidence": "fake", "notifications": "fake",
                    },
                    "routing": {
                        "roles": {"backend": {"preferred": ["claude"], "fallback": ["main_harness"]}},
                        "concurrency": {"claude": 1, "codex": 1},
                        "queue": {"max_wait_seconds": 0},
                        "circuit_breaker": {"failure_threshold": 1, "cooldown_seconds": 10, "half_open_max_probes": 1},
                    },
                },
                Path(directory),
            )
            local = {
                "claude": ProviderModelConfig("claude", "claude", {"low": "haiku", "medium": "sonnet", "high": "opus"}),
                "codex": ProviderModelConfig("codex", "codex", {"low": "mini", "medium": "coding", "high": "reasoning"}),
            }

            without_local = ProviderRegistry.from_effective_config(config)
            with_local = ProviderRegistry.from_effective_config(config, provider_local=local)

            self.assertIsNone(without_local.worker)
            self.assertIsInstance(with_local.worker, RoutedWorkerDispatcher)

    def test_registry_routes_provider_default_without_model_and_rejects_explicit_mode(self):
        class Runner:
            def __init__(self):
                self.invocations = []

            def run(self, invocation, *, cancel_event=None):
                self.invocations.append(invocation)
                return NativeCliOutput(({
                    "status": "completed",
                    "task_id": "api",
                    "summary": "done",
                    "changed_files": [],
                    "commits": [],
                    "tests": [],
                    "evidence": [],
                    "blockers": [],
                },))

        for antigravity_model, expected_provider in (
            ("provider_default", "antigravity"),
            ("gemini-pro", "codex"),
        ):
            with self.subTest(model=antigravity_model), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                runner = Runner()
                local = {
                    "antigravity": ProviderModelConfig(
                        "antigravity", "agy", {
                            "low": antigravity_model,
                            "medium": antigravity_model,
                            "high": antigravity_model,
                        }
                    ),
                    "codex": ProviderModelConfig(
                        "codex", "codex", {
                            "low": "mini", "medium": "coding", "high": "reasoning"
                        }
                    ),
                }
                registry = ProviderRegistry.from_effective_config(
                    self.antigravity_config(root),
                    provider_local=local,
                    evidence_authority=self.composite_authority(),
                    native_runner=runner,
                    worker_health={
                        "antigravity": lambda candidate: NativeHealth(
                            True, "explicit_model_selection_unverified", False
                        ),
                        "codex": lambda candidate: True,
                    },
                )
                registry.workspace.create(
                    WorkspaceRequest("ws-api", "task/api"), idempotency_key="create"
                )
                worker_request = WorkerRequest(
                    "Implement", (), create_context_manifest("execute", ContextRequest()),
                    {"mode": "isolated", "workspace_id": "ws-api", "branch": "task/api"},
                    REQUIRED_RESULT_FIELDS, "api", "wf", "try-1", "backend", "high",
                )

                receipt = registry.worker.dispatch(worker_request)
                normalized = registry.worker.collect_result(receipt.worker_id)

                self.assertEqual("completed", normalized.status)
                self.assertEqual(expected_provider, receipt.provider_name)
                if expected_provider == "antigravity":
                    self.assertEqual(("agy", "--print", "--sandbox"), runner.invocations[0].argv)
                else:
                    self.assertEqual(("codex", "exec"), runner.invocations[0].argv[:2])

    def test_registry_rejects_provider_default_for_non_antigravity_injection(self):
        with tempfile.TemporaryDirectory() as directory:
            local = {
                "codex": ProviderModelConfig(
                    "codex", "codex", {
                        "low": "provider_default",
                        "medium": "provider_default",
                        "high": "provider_default",
                    }
                )
            }

            with self.assertRaisesRegex(
                RegistryError, "provider_default is only supported for antigravity"
            ):
                ProviderRegistry.from_effective_config(
                    self.routed_config(directory), provider_local=local
                )

    def test_builds_every_selected_fake_from_effective_config(self):
        with tempfile.TemporaryDirectory() as directory:
            config = EffectiveConfig(
                {
                    "schema_version": "2.1",
                    "providers": {
                        "task_tracking": "fake",
                        "knowledge": "fake",
                        "workspace": "fake",
                        "review": "fake",
                        "evidence": "fake",
                        "notifications": "fake",
                    },
                },
                Path(directory),
            )

            registry = ProviderRegistry.from_config(config)

            self.assertIsInstance(registry.task_tracking, FakeTaskTrackingProvider)
            self.assertIsInstance(registry.knowledge, FakeKnowledgeProvider)
            self.assertIsInstance(registry.workspace, FakeWorkspaceProvider)
            self.assertIsInstance(registry.review, FakeReviewProvider)
            self.assertIsInstance(registry.evidence, FakeEvidenceProvider)
            self.assertIsInstance(registry.notifications, FakeNotificationProvider)

    def test_builds_registry_through_exact_from_effective_config_api(self):
        with tempfile.TemporaryDirectory() as directory:
            config = EffectiveConfig(
                {
                    "schema_version": "2.1",
                    "providers": {
                        "task_tracking": "fake",
                        "knowledge": "fake",
                        "workspace": "fake",
                        "review": "fake",
                        "evidence": "fake",
                        "notifications": "fake",
                    },
                },
                Path(directory),
            )

            registry = ProviderRegistry.from_effective_config(config)

            self.assertIsInstance(registry.task_tracking, FakeTaskTrackingProvider)

    def test_default_registry_contains_only_the_existing_provider_integrations(self):
        with tempfile.TemporaryDirectory() as directory:
            config = EffectiveConfig(
                {
                    "schema_version": "2.1",
                    "artifacts": {
                        "worktrees": ".planning/worktrees",
                        "knowledge": ".planning/knowledge",
                        "evidence": ".agent-workflow/runtime/evidence",
                    },
                },
                Path(directory),
            )

            registry = ProviderRegistry.from_config(config)

            self.assertIsInstance(registry.task_tracking, BeadsTaskTrackingProvider)
            self.assertIsInstance(registry.knowledge, RepositoryKnowledgeProvider)
            self.assertIsInstance(registry.workspace, WorktreeWorkspaceProvider)
            self.assertIsInstance(registry.review, ReviewLedgerProvider)
            self.assertIsInstance(registry.evidence, FileEvidenceProvider)
            self.assertIsInstance(registry.notifications, TelegramNotificationProvider)

    def test_rejects_nondefault_worktree_root_that_safety_scripts_cannot_honor(self):
        with tempfile.TemporaryDirectory() as directory:
            config = EffectiveConfig(
                {
                    "schema_version": "2.1",
                    "artifacts": {"worktrees": ".custom/worktrees"},
                },
                Path(directory),
            )

            with self.assertRaisesRegex(RegistryError, "non-default worktree root"):
                ProviderRegistry.from_config(config)

    def test_rejects_unknown_provider_without_falling_back(self):
        config = EffectiveConfig(
            {"schema_version": "2.1", "providers": {"task_tracking": "not-real"}},
            Path.cwd(),
        )

        with self.assertRaisesRegex(RegistryError, "task_tracking.*not-real"):
            ProviderRegistry.from_config(config)

    def test_worker_uses_authoritative_workspace_record_and_rejects_path_mismatch(self):
        class Runner:
            def __init__(self):
                self.invocations = []

            def run(self, invocation, *, cancel_event=None):
                self.invocations.append(invocation)
                raise AssertionError("must not execute outside authoritative workspace")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runner = Runner()
            registry = ProviderRegistry.from_effective_config(
                self.routed_config(root),
                provider_local=self.local(),
                native_runner=runner,
                worker_health={"claude": lambda candidate: True},
            )
            registry.workspace.create(
                WorkspaceRequest("ws-api", "task/api"), idempotency_key="create"
            )
            request = WorkerRequest(
                "Implement", (), create_context_manifest("execute", ContextRequest()),
                {
                    "mode": "isolated",
                    "workspace_id": "ws-api",
                    "branch": "task/api",
                    "workspace_path": str(root),
                },
                REQUIRED_RESULT_FIELDS, "api", "wf", "try-1", "backend", "high",
            )

            receipt = registry.worker.dispatch(request)
            result = registry.worker.collect_result(receipt.worker_id)

            self.assertEqual(("worker_routes_unavailable",), result.blockers)
            self.assertEqual([], runner.invocations)

    def test_registry_builds_scheduler_from_configured_worker_runtime_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = ProviderRegistry.from_effective_config(
                self.routed_config(directory),
                provider_local=self.local(),
                worker_health={"claude": lambda candidate: True},
            )

            scheduler = registry.build_worker_scheduler()

            self.assertEqual(17, scheduler.worker_timeout_seconds)
            self.assertEqual(3, scheduler.max_retries)
            self.assertEqual(2, scheduler.max_parallel_workers)


if __name__ == "__main__":
    unittest.main()
