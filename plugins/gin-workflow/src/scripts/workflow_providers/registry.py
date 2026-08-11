"""Provider registry built exclusively from resolved ``EffectiveConfig`` values."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from workflow_core.models import EffectiveConfig

from .contracts import (
    EvidenceProvider,
    KnowledgeProvider,
    NotificationProvider,
    ProviderMetadata,
    ReviewProvider,
    TaskTrackingProvider,
    WorkspaceProvider,
)
from .evidence import FileEvidenceProvider
from .fakes import (
    FakeEvidenceProvider,
    FakeKnowledgeProvider,
    FakeNotificationProvider,
    FakeReviewProvider,
    FakeTaskTrackingProvider,
    FakeWorkspaceProvider,
)
from .knowledge import ObsidianKnowledgeProvider, RepositoryKnowledgeProvider
from .notifications import TelegramNotificationProvider
from .review import ReviewLedgerProvider
from .task_tracking import BeadsTaskTrackingProvider
from .workspace import WorktreeWorkspaceProvider


class RegistryError(ValueError):
    """Raised when effective configuration selects an unknown provider."""


_DEFAULTS = {
    "task_tracking": "beads",
    "knowledge": "repository",
    "workspace": "worktrees",
    "review": "review-ledger",
    "evidence": "filesystem",
    "notifications": "telegram",
}


def _entry(config: EffectiveConfig, provider_type: str) -> tuple[str, Mapping[str, Any]]:
    providers = config.get("providers", {})
    if not isinstance(providers, Mapping):
        raise RegistryError("providers must be a mapping")
    raw = providers.get(provider_type, _DEFAULTS[provider_type])
    if isinstance(raw, str):
        return raw, {}
    if isinstance(raw, Mapping):
        name = raw.get("name", raw.get("type"))
        if not isinstance(name, str) or not name:
            raise RegistryError(f"providers.{provider_type} must declare name")
        return name, raw
    raise RegistryError(f"providers.{provider_type} must be a provider name or mapping")


def _path(root: Path, value: object, default: str) -> Path:
    candidate = Path(str(value or default))
    return candidate if candidate.is_absolute() else root / candidate


@dataclass(frozen=True)
class ProviderRegistry:
    task_tracking: TaskTrackingProvider
    knowledge: KnowledgeProvider
    workspace: WorkspaceProvider
    review: ReviewProvider
    evidence: EvidenceProvider
    notifications: NotificationProvider

    @classmethod
    def from_effective_config(cls, config: EffectiveConfig) -> "ProviderRegistry":
        if not isinstance(config, EffectiveConfig):
            raise TypeError("ProviderRegistry requires EffectiveConfig")
        root = config.repository_root
        artifacts = config.get("artifacts", {})
        if not isinstance(artifacts, Mapping):
            raise RegistryError("artifacts must be a mapping")

        task_name, _ = _entry(config, "task_tracking")
        knowledge_name, _ = _entry(config, "knowledge")
        workspace_name, workspace_options = _entry(config, "workspace")
        review_name, _ = _entry(config, "review")
        evidence_name, evidence_options = _entry(config, "evidence")
        notification_name, _ = _entry(config, "notifications")

        if task_name == "beads":
            task_tracking: TaskTrackingProvider = BeadsTaskTrackingProvider(root)
        elif task_name == "fake":
            task_tracking = FakeTaskTrackingProvider()
        else:
            raise RegistryError(f"unknown task_tracking provider: {task_name}")

        if knowledge_name == "repository":
            knowledge: KnowledgeProvider = RepositoryKnowledgeProvider(root)
        elif knowledge_name == "obsidian":
            knowledge = ObsidianKnowledgeProvider()
        elif knowledge_name == "fake":
            knowledge = FakeKnowledgeProvider()
        else:
            raise RegistryError(f"unknown knowledge provider: {knowledge_name}")

        worktree_root = _path(
            root,
            workspace_options.get("root") or artifacts.get("worktrees"),
            ".planning/worktrees",
        )
        if workspace_name in {"worktrees", "git-worktrees"}:
            supported_worktree_root = (root / ".planning/worktrees").resolve()
            if worktree_root.resolve() != supported_worktree_root:
                raise RegistryError(
                    "non-default worktree root is unsupported by worktree safety scripts"
                )
            workspace: WorkspaceProvider = WorktreeWorkspaceProvider(
                root, worktree_root=worktree_root
            )
        elif workspace_name == "fake":
            workspace = FakeWorkspaceProvider(worktree_root)
        else:
            raise RegistryError(f"unknown workspace provider: {workspace_name}")

        if review_name == "review-ledger":
            review: ReviewProvider = ReviewLedgerProvider(root)
        elif review_name == "fake":
            review = FakeReviewProvider()
        else:
            raise RegistryError(f"unknown review provider: {review_name}")

        evidence_path = _path(
            root,
            evidence_options.get("index") or artifacts.get("evidence"),
            ".agent-workflow/runtime/evidence",
        )
        if evidence_name == "filesystem":
            evidence: EvidenceProvider = FileEvidenceProvider(evidence_path)
        elif evidence_name == "fake":
            evidence = FakeEvidenceProvider()
        else:
            raise RegistryError(f"unknown evidence provider: {evidence_name}")

        if notification_name == "telegram":
            notifications: NotificationProvider = TelegramNotificationProvider(root)
        elif notification_name == "fake":
            notifications = FakeNotificationProvider()
        else:
            raise RegistryError(f"unknown notifications provider: {notification_name}")

        return cls(task_tracking, knowledge, workspace, review, evidence, notifications)

    @classmethod
    def from_config(cls, config: EffectiveConfig) -> "ProviderRegistry":
        """Compatibility alias for the explicit EffectiveConfig constructor."""
        return cls.from_effective_config(config)

    @property
    def metadata(self) -> Mapping[str, ProviderMetadata]:
        return {
            "task_tracking": self.task_tracking.metadata,
            "knowledge": self.knowledge.metadata,
            "workspace": self.workspace.metadata,
            "review": self.review.metadata,
            "evidence": self.evidence.metadata,
            "notifications": self.notifications.metadata,
        }

    def get(self, provider_type: str):
        if provider_type not in self.metadata:
            raise RegistryError(f"unknown provider type: {provider_type}")
        return getattr(self, provider_type)
