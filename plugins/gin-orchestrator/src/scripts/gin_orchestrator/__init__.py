"""Lifecycle provider contracts, registry, fakes, and contained adapters."""

from .contracts import (
    EvidenceCategory,
    EvidenceCompleteness,
    EvidenceProvider,
    EvidenceQuery,
    EvidenceRecord,
    KnowledgeProposal,
    KnowledgeProposalRecord,
    KnowledgeProvider,
    KnowledgeRecord,
    OperationStatus,
    ProviderHealth,
    ProviderMetadata,
    ProviderResult,
    ReviewProvider,
    ReviewFinding,
    ReviewRequest,
    ReviewStatus,
    TaskCreateRequest,
    TaskRecord,
    TaskTrackingProvider,
    WorkspaceProvider,
    WorkspaceRecord,
    WorkspaceRequest,
)
from .evidence import FileEvidenceProvider
from .fakes import (
    FakeEvidenceProvider,
    FakeKnowledgeProvider,
    FakeReviewProvider,
    FakeTaskTrackingProvider,
    FakeWorkspaceProvider,
)
from .knowledge import ObsidianKnowledgeProvider, RepositoryKnowledgeProvider
from .registry import ProviderRegistry, RegistryError
from .review import ReviewLedgerProvider
from .routed_worker import RoutedWorkerDispatcher, RoutedWorkerReceipt
from .task_tracking_cli import CliTaskTrackingProvider
from .workspace import WorktreeWorkspaceProvider

__all__ = [
    "CliTaskTrackingProvider",
    "EvidenceCategory",
    "EvidenceCompleteness",
    "EvidenceProvider",
    "EvidenceQuery",
    "EvidenceRecord",
    "FakeEvidenceProvider",
    "FakeKnowledgeProvider",
    "FakeReviewProvider",
    "FakeTaskTrackingProvider",
    "FakeWorkspaceProvider",
    "FileEvidenceProvider",
    "KnowledgeProposal",
    "KnowledgeProposalRecord",
    "KnowledgeProvider",
    "KnowledgeRecord",
    "ObsidianKnowledgeProvider",
    "OperationStatus",
    "ProviderHealth",
    "ProviderMetadata",
    "ProviderRegistry",
    "ProviderResult",
    "RegistryError",
    "RepositoryKnowledgeProvider",
    "ReviewLedgerProvider",
    "ReviewFinding",
    "ReviewProvider",
    "ReviewRequest",
    "ReviewStatus",
    "RoutedWorkerDispatcher",
    "RoutedWorkerReceipt",
    "TaskCreateRequest",
    "TaskRecord",
    "TaskTrackingProvider",
    "WorkspaceProvider",
    "WorkspaceRecord",
    "WorkspaceRequest",
    "WorktreeWorkspaceProvider",
]
