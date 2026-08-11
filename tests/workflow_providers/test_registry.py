from pathlib import Path
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core.models import EffectiveConfig  # noqa: E402
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
from workflow_providers.review import ReviewLedgerProvider  # noqa: E402
from workflow_providers.task_tracking import BeadsTaskTrackingProvider  # noqa: E402
from workflow_providers.workspace import WorktreeWorkspaceProvider  # noqa: E402


class ProviderRegistryTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
