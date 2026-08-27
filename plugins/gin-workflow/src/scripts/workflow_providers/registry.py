"""Provider registry built exclusively from resolved ``EffectiveConfig`` values."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from workflow_core.models import EffectiveConfig
from workflow_core.assignments import AssignmentRequest, resolve_assignment
from workflow_core.events import WorkflowEventStore
from workflow_core.provider_config import PROVIDER_DEFAULT, ProviderModelConfig

from .contracts import (
    EvidenceAuthority,
    EvidenceProvider,
    KnowledgeProvider,
    NotificationProvider,
    ProviderMetadata,
    ReviewProvider,
    TaskTrackingProvider,
    WorkspaceProvider,
    OperationStatus,
)
from .evidence import CompositeEvidenceAuthority, FileEvidenceProvider
from .evidence_authority import build_composite_evidence_authority
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
from .antigravity_worker import (
    AntigravityWorkerAdapter,
    antigravity_health,
)
from .circuit_breaker import CircuitBreakerStore
from .claude_worker import ClaudeWorkerAdapter, claude_health
from .codex_worker import CodexWorkerAdapter, codex_health
from .native_cli import NativeCliRunner
from .routed_worker import RoutedWorkerDispatcher


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
    worker: RoutedWorkerDispatcher | None = None
    worker_timeout_seconds: float = 600.0
    worker_max_retries: int = 0
    worker_max_parallel: int = 1

    @classmethod
    def from_effective_config(
        cls,
        config: EffectiveConfig,
        *,
        provider_local: Mapping[str, ProviderModelConfig] | None = None,
        native_runner: NativeCliRunner | None = None,
        worker_health: Mapping[str, Any] | None = None,
        event_store: WorkflowEventStore | None = None,
        evidence_authority: EvidenceAuthority | None = None,
    ) -> "ProviderRegistry":
        if not isinstance(config, EffectiveConfig):
            raise TypeError("ProviderRegistry requires EffectiveConfig")
        root = config.repository_root
        artifacts = config.get("artifacts", {})
        if not isinstance(artifacts, Mapping):
            raise RegistryError("artifacts must be a mapping")

        task_name, task_options = _entry(config, "task_tracking")
        knowledge_name, _ = _entry(config, "knowledge")
        workspace_name, workspace_options = _entry(config, "workspace")
        review_name, _ = _entry(config, "review")
        evidence_name, evidence_options = _entry(config, "evidence")
        notification_name, _ = _entry(config, "notifications")

        if task_name == "beads":
            try:
                task_tracking: TaskTrackingProvider = BeadsTaskTrackingProvider(
                    root,
                    executable=str(task_options.get("executable", "bd")),
                )
            except ValueError as error:
                raise RegistryError(str(error)) from error
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
        if evidence_authority is None and str(config.get("schema_version", "")) == "2.3":
            evidence_runtime_root = _path(root, artifacts.get("runtime"), ".agent-workflow/runtime")
            evidence_event_store = event_store or WorkflowEventStore(
                evidence_runtime_root / "events.jsonl"
            )
            evidence_authority = build_composite_evidence_authority(root, evidence_event_store)
        if str(config.get("schema_version", "")) == "2.3" and not isinstance(
            evidence_authority,
            CompositeEvidenceAuthority,
        ):
            raise RegistryError(
                "schema 2.3 evidence authority must be a CompositeEvidenceAuthority"
            )
        if evidence_name == "filesystem":
            evidence: EvidenceProvider = FileEvidenceProvider(
                evidence_path,
                authority=evidence_authority,
            )
        elif evidence_name == "fake":
            evidence = FakeEvidenceProvider(authority=evidence_authority)
        else:
            raise RegistryError(f"unknown evidence provider: {evidence_name}")

        if notification_name == "telegram":
            notifications: NotificationProvider = TelegramNotificationProvider(root)
        elif notification_name == "fake":
            notifications = FakeNotificationProvider()
        else:
            raise RegistryError(f"unknown notifications provider: {notification_name}")

        worker = None
        configured_timeout = 600.0
        configured_retries = 0
        configured_parallel = 1
        if provider_local is not None:
            for provider_name, local_config in provider_local.items():
                if provider_name != "antigravity" and any(
                    model == PROVIDER_DEFAULT for model in local_config.models.values()
                ):
                    raise RegistryError(
                        "provider_default is only supported for antigravity"
                    )
            routing = config.get("routing", {})
            if not isinstance(routing, Mapping):
                raise RegistryError("routing must be a mapping")
            concurrency = routing.get("concurrency", {})
            if not isinstance(concurrency, Mapping) or not concurrency:
                raise RegistryError("routing.concurrency is required for routed workers")
            queue = routing.get("queue", {})
            breaker_policy = routing.get("circuit_breaker", {})
            worker_policy = routing.get("worker", {})
            if not all(isinstance(value, Mapping) for value in (queue, breaker_policy, worker_policy)):
                raise RegistryError("routing queue, worker, and circuit_breaker must be mappings")
            runtime_root = _path(
                root,
                artifacts.get("runtime"),
                ".agent-workflow/runtime",
            )
            breakers = CircuitBreakerStore(
                runtime_root / "circuit-breakers.json",
                failure_threshold=int(breaker_policy.get("failure_threshold", 1)),
                cooldown_seconds=float(breaker_policy.get("cooldown_seconds", 900)),
                half_open_max_probes=int(breaker_policy.get("half_open_max_probes", 1)),
            )
            events = event_store or WorkflowEventStore(runtime_root / "events.jsonl")
            runner = native_runner or NativeCliRunner()
            timeout_seconds = float(worker_policy.get("timeout_seconds", 900))
            configured_timeout = timeout_seconds
            configured_retries = int(worker_policy.get("max_retries", 0))
            configured_parallel = sum(int(limit) for limit in concurrency.values())
            health_overrides = dict(worker_health or {})
            health_cache: dict[str, Any] = {}

            def resolver(request):
                assignment = AssignmentRequest(
                    request.task_id,
                    request.provider_role,
                    request.reasoning,
                    str(config.get("harness", "")),
                )
                return resolve_assignment(assignment, config, provider_local)

            def workspace_for(request) -> Path:
                workspace_id = str(request.isolation_policy.get("workspace_id", ""))
                isolated = workspace.isolate(workspace_id)
                if (
                    isolated.status is not OperationStatus.SUCCESS
                    or isolated.value is None
                    or not isolated.value.isolated
                ):
                    raise RegistryError(f"unknown isolated workspace: {workspace_id}")
                record = isolated.value
                if str(request.isolation_policy.get("branch", "")) != record.branch:
                    raise RegistryError("isolated workspace branch does not match authoritative record")
                authoritative = record.path
                resolved = authoritative.resolve()
                supported_root = worktree_root.resolve()
                if (
                    authoritative.is_symlink()
                    or not resolved.is_dir()
                    or not resolved.is_relative_to(supported_root)
                ):
                    raise RegistryError("authoritative workspace violates worktree root safety")
                supplied = request.isolation_policy.get("workspace_path")
                if supplied and Path(str(supplied)).resolve() != resolved:
                    raise RegistryError("workspace_path does not match authoritative workspace")
                return resolved

            def factory(candidate, request):
                local = provider_local[candidate.provider]
                workspace_path = workspace_for(request)
                options = {
                    "native_runner": runner,
                    "executable": local.executable,
                    "model": candidate.model,
                    "workspace": workspace_path,
                    "timeout_seconds": timeout_seconds,
                }
                if candidate.provider == "claude":
                    return ClaudeWorkerAdapter(**options)
                if candidate.provider == "codex":
                    return CodexWorkerAdapter(**options)
                if candidate.provider == "antigravity":
                    return AntigravityWorkerAdapter(**options)
                raise RegistryError(f"unsupported native worker provider: {candidate.provider}")

            health_builders = {
                "claude": claude_health,
                "codex": codex_health,
                "antigravity": antigravity_health,
            }

            def health_for(provider: str):
                override = health_overrides.get(provider)
                if override is not None:
                    return override

                def check(_candidate):
                    key = (provider, _candidate.model)
                    if key not in health_cache:
                        local = provider_local.get(provider)
                        builder = health_builders.get(provider)
                        if local is None or builder is None:
                            return False
                        if provider in ("claude", "codex"):
                            probe_workspace = runtime_root / "health-probe" / provider
                            probe_workspace.mkdir(parents=True, exist_ok=True)
                            health_cache[key] = builder(
                                local.executable,
                                model=_candidate.model,
                                native_runner=runner,
                                workspace=probe_workspace,
                            )
                        else:
                            health_cache[key] = builder(local.executable)
                    return health_cache[key]

                return check

            worker = RoutedWorkerDispatcher(
                resolver,
                factory,
                breakers,
                events,
                concurrency={str(name): int(limit) for name, limit in concurrency.items()},
                max_wait_seconds=float(queue.get("max_wait_seconds", 120)),
                health={str(name): health_for(str(name)) for name in concurrency},
            )

        return cls(
            task_tracking,
            knowledge,
            workspace,
            review,
            evidence,
            notifications,
            worker,
            configured_timeout,
            configured_retries,
            configured_parallel,
        )

    @classmethod
    def from_config(
        cls,
        config: EffectiveConfig,
        *,
        evidence_authority: EvidenceAuthority | None = None,
    ) -> "ProviderRegistry":
        """Compatibility alias for the explicit EffectiveConfig constructor."""
        return cls.from_effective_config(
            config,
            evidence_authority=evidence_authority,
        )

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
        if provider_type == "worker":
            if self.worker is None:
                raise RegistryError("worker provider requires explicit local provider configuration")
            return self.worker
        if provider_type not in self.metadata:
            raise RegistryError(f"unknown provider type: {provider_type}")
        return getattr(self, provider_type)

    def build_worker_scheduler(self):
        if self.worker is None:
            raise RegistryError("worker provider requires explicit local provider configuration")
        from workflow_core.worker_scheduler import WorkerScheduler

        return WorkerScheduler(
            self.worker,
            task_tracking=self.task_tracking,
            workspace=self.workspace,
            max_parallel_workers=self.worker_max_parallel,
            max_retries=self.worker_max_retries,
            worker_timeout_seconds=self.worker_timeout_seconds,
        )
