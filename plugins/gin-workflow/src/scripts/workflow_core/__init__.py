"""Portable, provider-neutral workflow core for gin-workflow v2.1."""

from .approvals import (
    ApprovalAction,
    ApprovalDecision,
    ApprovalRequest,
    ApprovalStatus,
    require_approval,
)
from .artifacts import ArtifactResolutionError, build_artifact_registry, resolve_artifact
from .configuration import (
    BUILT_IN_DEFAULTS,
    ConfigValidationError,
    load_effective_config,
    resolve_effective_config,
    validate_portable_config,
)
from .events import (
    EventPersistenceError,
    EventStore,
    WorkflowEvent,
    WorkflowEventStore,
    append_workflow_event,
)
from .manifests import ContextManifest, ContextRequest, create_context_manifest
from .models import (
    ArtifactRegistry,
    ConfigProvenance,
    DependencyUnavailableError,
    EffectiveConfig,
    ResolvedConfig,
    WorkflowCoreError,
)

__all__ = [
    "ApprovalAction",
    "ApprovalDecision",
    "ApprovalRequest",
    "ApprovalStatus",
    "ArtifactRegistry",
    "ArtifactResolutionError",
    "BUILT_IN_DEFAULTS",
    "ConfigProvenance",
    "ConfigValidationError",
    "ContextManifest",
    "ContextRequest",
    "DependencyUnavailableError",
    "EffectiveConfig",
    "EventPersistenceError",
    "EventStore",
    "ResolvedConfig",
    "WorkflowCoreError",
    "WorkflowEvent",
    "WorkflowEventStore",
    "append_workflow_event",
    "build_artifact_registry",
    "create_context_manifest",
    "load_effective_config",
    "require_approval",
    "resolve_artifact",
    "resolve_effective_config",
    "validate_portable_config",
]
