from pathlib import Path
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core.models import EffectiveConfig  # noqa: E402
from workflow_core.manifests import ContextRequest, create_context_manifest  # noqa: E402
from workflow_core.provider_config import ProviderModelConfig  # noqa: E402
from workflow_providers.contracts import WorkspaceRequest  # noqa: E402
from workflow_providers.evidence import FileEvidenceProvider  # noqa: E402
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
from workflow_providers.registry import ProviderRegistry, RegistryError  # noqa: E402
from workflow_providers.routed_worker import RoutedWorkerDispatcher  # noqa: E402
from workflow_providers.review import ReviewLedgerProvider  # noqa: E402
from workflow_providers.task_tracking import BeadsTaskTrackingProvider  # noqa: E402
from workflow_providers.workspace import WorktreeWorkspaceProvider  # noqa: E402
from workflow_providers.worker_dispatch import REQUIRED_RESULT_FIELDS, WorkerRequest  # noqa: E402


class ProviderRegistryTests(unittest.TestCase):
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
