"""Provider registry built exclusively from resolved ``EffectiveConfig`` values."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from workflow_core.ext import (
    AssignmentRequest,
    DEFAULT_CATALOGS,
    EffectiveConfig,
    PROVIDER_DEFAULT,
    PROVIDER_DEFAULT_PROVIDERS,
    ProviderModelConfig,
    RouteCandidate,
    WorkflowEventStore,
    catalog_for,
    main_checkout,
    resolve_harness_executable,
)

from .routes import resolve_assignment
from .config import ORCHESTRATOR_DEFAULTS, orchestrator_section

from .contracts import (
    EvidenceAuthority,
    EvidenceProvider,
    KnowledgeProvider,
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
    FakeReviewProvider,
    FakeTaskTrackingProvider,
    FakeWorkspaceProvider,
)
from .knowledge import ObsidianKnowledgeProvider, RepositoryKnowledgeProvider
from .review import ReviewLedgerProvider
from .task_tracking_cli import CliTaskTrackingProvider
from .workspace import WorktreeWorkspaceProvider
from .antigravity_worker import (
    AntigravityWorkerAdapter,
    antigravity_health,
)
from .opencode_worker import OpenCodeWorkerAdapter, opencode_health
from .copilot_worker import CopilotWorkerAdapter, copilot_health
from .circuit_breaker import CircuitBreakerStore
from .claude_worker import ClaudeWorkerAdapter, claude_health
from .codex_worker import CodexWorkerAdapter, codex_health
from .native_cli import NativeCliRunner
from .routed_worker import RoutedWorkerDispatcher, WorkspaceUnavailableError


class RegistryError(ValueError):
    """Raised when effective configuration selects an unknown provider."""


def _resolve_worker_agent(provider: str, agent: str | None) -> str | None:
    if not agent or not agent.strip():
        return None
    raw = agent.strip()
    if provider == "codex":
        return None
    if ":" in raw:
        plugin_prefix, stem = raw.split(":", 1)
    elif raw.startswith("gin-qa-"):
        plugin_prefix, stem = "gin-qa", raw[len("gin-qa-"):]
    elif raw.startswith("gin-workflow-"):
        plugin_prefix, stem = "gin", raw[len("gin-workflow-"):]
    elif raw.startswith("gin-"):
        plugin_prefix, stem = "gin", raw[len("gin-"):]
    else:
        plugin_prefix, stem = "gin", raw
    if plugin_prefix == "gin-workflow":
        plugin_prefix = "gin"
    if provider == "claude":
        return f"{plugin_prefix}:{stem}"
    if provider == "opencode":
        return f"{plugin_prefix}-{stem}"
    return stem


_DEFAULTS = {
    "task_tracking": "beads",
    "knowledge": "repository",
    "workspace": "worktrees",
    "review": "review-ledger",
    "evidence": "filesystem",
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
    worker: RoutedWorkerDispatcher | None = None
    worker_timeout_seconds: float = float(ORCHESTRATOR_DEFAULTS["worker"]["timeout_seconds"])
    worker_max_retries: int = int(ORCHESTRATOR_DEFAULTS["worker"]["max_retries"])
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
        state_root = main_checkout(root)
        artifacts = config.get("artifacts", {})
        if not isinstance(artifacts, Mapping):
            raise RegistryError("artifacts must be a mapping")

        task_name, _ = _entry(config, "task_tracking")
        knowledge_name, _ = _entry(config, "knowledge")
        workspace_name, workspace_options = _entry(config, "workspace")
        review_name, _ = _entry(config, "review")
        evidence_name, evidence_options = _entry(config, "evidence")

        if task_name in {"beads", "markdown"}:
            task_tracking: TaskTrackingProvider = CliTaskTrackingProvider(root)
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
                    "non-default worktree root is unsupported by worktree integration"
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
            state_root,
            evidence_options.get("index") or artifacts.get("evidence"),
            ".agent-workflow/runtime/evidence",
        )
        if evidence_authority is None and str(config.get("schema_version", "")) in ("2.3", "2.4", "2.5", "2.6", "2.7", "2.8", "2.9"):
            evidence_runtime_root = _path(state_root, artifacts.get("runtime"), ".agent-workflow/runtime")
            evidence_event_store = event_store or WorkflowEventStore(
                evidence_runtime_root / "events.jsonl"
            )
            evidence_authority = build_composite_evidence_authority(root, evidence_event_store)
        if str(config.get("schema_version", "")) in ("2.3", "2.4", "2.5", "2.6", "2.7", "2.8", "2.9") and not isinstance(
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

        worker = None
        configured_timeout = float(ORCHESTRATOR_DEFAULTS["worker"]["timeout_seconds"])
        configured_retries = int(ORCHESTRATOR_DEFAULTS["worker"]["max_retries"])
        configured_parallel = 1
        if provider_local is not None:
            for provider_name in provider_local:
                if (
                    provider_name in DEFAULT_CATALOGS
                    and provider_name not in PROVIDER_DEFAULT_PROVIDERS
                    and PROVIDER_DEFAULT in catalog_for(config, provider_name).models
                ):
                    raise RegistryError(
                        "provider_default is only supported for antigravity, opencode, and copilot"
                    )
            orchestrator = orchestrator_section(config)
            concurrency = orchestrator.get("concurrency", {})
            if not isinstance(concurrency, Mapping) or not concurrency:
                raise RegistryError("orchestrator.concurrency is required for routed workers")
            queue = orchestrator.get("queue", {})
            breaker_policy = orchestrator.get("circuit_breaker", {})
            worker_policy = orchestrator.get("worker", {})
            if not all(isinstance(value, Mapping) for value in (queue, breaker_policy, worker_policy)):
                raise RegistryError("orchestrator queue, worker, and circuit_breaker must be mappings")
            runtime_root = _path(
                state_root,
                artifacts.get("runtime"),
                ".agent-workflow/runtime",
            )
            breakers = CircuitBreakerStore(
                runtime_root / "circuit-breakers.json",
                failure_threshold=int(
                    breaker_policy.get(
                        "failure_threshold",
                        ORCHESTRATOR_DEFAULTS["circuit_breaker"]["failure_threshold"],
                    )
                ),
                cooldown_seconds=float(breaker_policy.get("cooldown_seconds", 900)),
                half_open_max_probes=int(breaker_policy.get("half_open_max_probes", 1)),
            )
            events = event_store or WorkflowEventStore(runtime_root / "events.jsonl")
            runner = native_runner or NativeCliRunner()
            timeout_seconds = float(
                worker_policy.get(
                    "timeout_seconds",
                    ORCHESTRATOR_DEFAULTS["worker"]["timeout_seconds"],
                )
            )
            configured_timeout = timeout_seconds
            configured_retries = int(
                worker_policy.get(
                    "max_retries",
                    ORCHESTRATOR_DEFAULTS["worker"]["max_retries"],
                )
            )
            configured_parallel = sum(int(limit) for limit in concurrency.values())
            health_overrides = dict(worker_health or {})
            health_cache: dict[str, Any] = {}

            def resolver(request):
                main_harness = str(config.get("harness", ""))
                is_direct = request.isolation_policy.get("mode") == "direct"
                source_harness = main_harness or ("claude" if is_direct else "")
                affinity = request.route_affinity
                if is_direct and affinity is not None and len(affinity) >= 1:
                    source_harness = str(affinity[0])
                assignment = AssignmentRequest(
                    request.task_id,
                    request.provider_role,
                    request.model,
                    request.effort,
                    source_harness,
                )
                candidates = list(resolve_assignment(assignment, config, provider_local))
                if is_direct and affinity is not None and len(affinity) >= 2:
                    aff_provider = str(affinity[0])
                    aff_model = str(affinity[1])
                    aff_effort = affinity[2] if len(affinity) > 2 and affinity[2] else None
                    if not any(
                        c.provider == aff_provider and c.model == aff_model and (c.effort == aff_effort if aff_effort is not None else True)
                        for c in candidates
                    ):
                        candidates.insert(
                            0,
                            RouteCandidate(aff_provider, aff_model, False, effort=aff_effort or request.effort),
                        )
                return tuple(candidates)

            def workspace_for(request) -> Path:
                if request.isolation_policy.get("mode") == "direct":
                    raw_supplied = request.isolation_policy.get("workspace_path")
                    if not raw_supplied:
                        raise WorkspaceUnavailableError("direct workspace mode requires workspace_path")
                    supplied_path = Path(str(raw_supplied))
                    resolved = supplied_path.resolve()
                    supported_worktree_root = worktree_root.resolve()
                    supported_repo_root = root.resolve()
                    if supplied_path.is_symlink() or not resolved.is_dir():
                        raise WorkspaceUnavailableError("direct workspace_path must be an existing non-symlink directory")
                    stage = getattr(request.generated_manifest, "stage", "execute")
                    if stage == "execute":
                        if not resolved.is_relative_to(supported_worktree_root):
                            raise WorkspaceUnavailableError("direct execute workspace violates worktree root safety")
                    else:
                        read_only_stages = frozenset({"discuss", "plan", "review", "tech-doc"})
                        read_only_roles = frozenset({"review", "research"})
                        if stage in read_only_stages or request.provider_role in read_only_roles:
                            if not (resolved.is_relative_to(supported_repo_root) or resolved.is_relative_to(supported_worktree_root)):
                                raise WorkspaceUnavailableError("direct workspace_path must reside inside repository or worktree root")
                        else:
                            if not resolved.is_relative_to(supported_worktree_root):
                                raise WorkspaceUnavailableError("direct execute workspace violates worktree root safety")
                    return resolved

                workspace_id = str(request.isolation_policy.get("workspace_id", ""))
                if not workspace_id and request.provider_role == "review":
                    return root.resolve()
                isolated = workspace.isolate(workspace_id)
                if (
                    isolated.status is not OperationStatus.SUCCESS
                    or isolated.value is None
                    or not isolated.value.isolated
                ):
                    raise WorkspaceUnavailableError(f"unknown isolated workspace: {workspace_id}")
                record = isolated.value
                if str(request.isolation_policy.get("branch", "")) != record.branch:
                    raise WorkspaceUnavailableError("isolated workspace branch does not match authoritative record")
                authoritative = record.path
                resolved = authoritative.resolve()
                supported_root = worktree_root.resolve()
                if (
                    authoritative.is_symlink()
                    or not resolved.is_dir()
                    or not resolved.is_relative_to(supported_root)
                ):
                    raise WorkspaceUnavailableError("authoritative workspace violates worktree root safety")
                supplied = request.isolation_policy.get("workspace_path")
                if supplied and Path(str(supplied)).resolve() != resolved:
                    raise WorkspaceUnavailableError("workspace_path does not match authoritative workspace")
                return resolved

            def factory(candidate, request):
                local = provider_local[candidate.provider]
                workspace_path = workspace_for(request)
                resolved_exe = (
                    resolve_harness_executable(local.executable, provider=candidate.provider)
                    or local.executable
                )
                options = {
                    "native_runner": runner,
                    "executable": resolved_exe,
                    "model": candidate.model,
                    "workspace": workspace_path,
                    "timeout_seconds": timeout_seconds,
                }
                if candidate.provider in ("claude", "codex", "antigravity", "copilot") and candidate.effort is not None:
                    options["effort"] = candidate.effort
                resolved_agent = _resolve_worker_agent(candidate.provider, getattr(request, "agent", None))
                if resolved_agent is not None:
                    options["agent"] = resolved_agent
                if candidate.provider == "claude":
                    return ClaudeWorkerAdapter(**options)
                if candidate.provider == "codex":
                    return CodexWorkerAdapter(**options)
                if candidate.provider == "antigravity":
                    return AntigravityWorkerAdapter(**options)
                if candidate.provider == "opencode":
                    return OpenCodeWorkerAdapter(**options)
                if candidate.provider == "copilot":
                    return CopilotWorkerAdapter(**options)
                raise RegistryError(f"unsupported native worker provider: {candidate.provider}")

            health_builders = {
                "claude": claude_health,
                "codex": codex_health,
                "antigravity": antigravity_health,
                "opencode": opencode_health,
                "copilot": copilot_health,
            }

            def health_for(provider: str):
                override = health_overrides.get(provider)
                if override is not None:
                    return override

                def check(_candidate):
                    effort = getattr(_candidate, "effort", None)
                    key = (provider, _candidate.model, effort or "")
                    if key not in health_cache:
                        local = provider_local.get(provider)
                        builder = health_builders.get(provider)
                        if local is None or builder is None:
                            return False
                        resolved_exe = (
                            resolve_harness_executable(local.executable, provider=provider)
                            or local.executable
                        )
                        if provider in ("claude", "codex", "antigravity", "opencode", "copilot"):
                            if provider in PROVIDER_DEFAULT_PROVIDERS and _candidate.model == PROVIDER_DEFAULT:
                                health_cache[key] = builder(resolved_exe)
                            else:
                                probe_workspace = runtime_root / "health-probe" / provider
                                probe_workspace.mkdir(parents=True, exist_ok=True)
                                probe_kwargs: dict[str, Any] = {
                                    "model": _candidate.model,
                                    "native_runner": runner,
                                    "workspace": probe_workspace,
                                }
                                if provider in ("claude", "codex", "antigravity", "copilot") and effort is not None:
                                    probe_kwargs["effort"] = effort
                                health_cache[key] = builder(
                                    resolved_exe,
                                    **probe_kwargs,
                                )
                        else:
                            health_cache[key] = builder(resolved_exe)
                    return health_cache[key]

                return check

            worker = RoutedWorkerDispatcher(
                resolver,
                factory,
                breakers,
                events,
                concurrency={str(name): int(limit) for name, limit in concurrency.items()},
                max_wait_seconds=float(
                    queue.get(
                        "max_wait_seconds",
                        ORCHESTRATOR_DEFAULTS["queue"]["max_wait_seconds"],
                    )
                ),
                health={str(name): health_for(str(name)) for name in concurrency},
            )

        return cls(
            task_tracking,
            knowledge,
            workspace,
            review,
            evidence,
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
        from .worker_scheduler import WorkerScheduler

        return WorkerScheduler(
            self.worker,
            task_tracking=self.task_tracking,
            workspace=self.workspace,
            max_parallel_workers=self.worker_max_parallel,
            max_retries=self.worker_max_retries,
            worker_timeout_seconds=self.worker_timeout_seconds,
        )
