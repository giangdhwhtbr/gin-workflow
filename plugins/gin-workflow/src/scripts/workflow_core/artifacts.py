"""Side-effect-free named artifact resolution."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .models import ArtifactRegistry, EffectiveConfig


ARTIFACT_NAMES = frozenset(
    {"plans", "beads", "worktrees", "knowledge", "evidence", "runtime"}
)


class ArtifactResolutionError(KeyError):
    """Raised when an artifact has no explicit configured path."""


def _config_data(config: EffectiveConfig | Mapping[str, Any]) -> Mapping[str, Any]:
    if isinstance(config, EffectiveConfig):
        return config.data
    return config


def _repository_root(config: EffectiveConfig | Mapping[str, Any]) -> Path:
    if isinstance(config, EffectiveConfig):
        return config.repository_root
    root = config.get("repository_root")
    if root is None:
        raise ArtifactResolutionError(
            "relative artifact paths require EffectiveConfig.repository_root"
        )
    return Path(root).resolve()


def resolve_artifact(config: EffectiveConfig | Mapping[str, Any], name: str) -> Path:
    """Return exactly the configured artifact path without filesystem mutation."""
    if name not in ARTIFACT_NAMES:
        raise ArtifactResolutionError(f"unknown artifact name: {name}")
    artifacts = _config_data(config).get("artifacts")
    if not isinstance(artifacts, Mapping) or name not in artifacts:
        raise ArtifactResolutionError(f"artifact path is not configured: {name}")
    raw_path = artifacts[name]
    if not isinstance(raw_path, (str, Path)) or not str(raw_path).strip():
        raise ArtifactResolutionError(f"artifact path must be a non-empty path: {name}")
    path = Path(raw_path).expanduser()
    if path.is_absolute():
        return path
    return _repository_root(config) / path


def build_artifact_registry(config: EffectiveConfig | Mapping[str, Any]) -> ArtifactRegistry:
    return ArtifactRegistry({name: resolve_artifact(config, name) for name in ARTIFACT_NAMES})
