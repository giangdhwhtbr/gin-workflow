"""The facade gin-orchestrator imports. Removing a name or changing a signature raises EXT_VERSION."""

from .approvals import ApprovalAction
from .assignments import (
    AssignmentManifest,
    AssignmentRequest,
    AssignmentResolutionError,
    RouteCandidate,
    validate_plan_assignments,
)
from .atomic import atomic_write_text
from .checkout import main_checkout
from .configuration import load_effective_config, require_yaml
from .events import WorkflowEvent, WorkflowEventStore
from .executable_resolver import PROVIDER_EXE_ALIASES, resolve_harness_executable
from .identity import AcceptanceIdentity, RepositorySnapshot
from .locking import file_lock
from .manifests import ContextManifest, ContextRequest, create_context_manifest
from .models import EffectiveConfig, freeze, thaw
from .notify import notify
from .provider_config import (
    CODEX_EFFORT_VALUES,
    DEFAULT_HARNESS_MODELS,
    PROVIDER_DEFAULT,
    PROVIDER_DEFAULT_PROVIDERS,
    ProviderLocalConfigError,
    ProviderModelConfig,
    REASONING_TIERS,
    TierModelTarget,
    default_provider_model_config,
)
from .router import authorize_protected_action
from .schemas import SUPPORTED_CONFIG_VERSIONS, validate_instance
from .worktrees import cleanup as cleanup_worktree, create as create_worktree

EXT_VERSION = 1

__all__ = [
    "AcceptanceIdentity",
    "ApprovalAction",
    "AssignmentManifest",
    "AssignmentRequest",
    "AssignmentResolutionError",
    "CODEX_EFFORT_VALUES",
    "ContextManifest",
    "ContextRequest",
    "DEFAULT_HARNESS_MODELS",
    "EffectiveConfig",
    "PROVIDER_DEFAULT",
    "PROVIDER_DEFAULT_PROVIDERS",
    "PROVIDER_EXE_ALIASES",
    "ProviderLocalConfigError",
    "ProviderModelConfig",
    "REASONING_TIERS",
    "RepositorySnapshot",
    "RouteCandidate",
    "SUPPORTED_CONFIG_VERSIONS",
    "TierModelTarget",
    "WorkflowEvent",
    "WorkflowEventStore",
    "atomic_write_text",
    "authorize_protected_action",
    "cleanup_worktree",
    "create_context_manifest",
    "create_worktree",
    "default_provider_model_config",
    "file_lock",
    "freeze",
    "load_effective_config",
    "main_checkout",
    "notify",
    "require_yaml",
    "resolve_harness_executable",
    "thaw",
    "validate_instance",
    "validate_plan_assignments",
]
