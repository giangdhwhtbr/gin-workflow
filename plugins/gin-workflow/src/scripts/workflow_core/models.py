"""Immutable value models shared by the portable workflow core."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterator, Mapping


class WorkflowCoreError(Exception):
    """Base class for portable workflow-core errors."""


class DependencyUnavailableError(WorkflowCoreError):
    """Raised when an explicitly required runtime dependency is unavailable."""


def freeze(value: Any) -> Any:
    """Recursively convert mutable containers into immutable equivalents."""
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(freeze(item) for item in value)
    return value


def thaw(value: Any) -> Any:
    """Convert immutable model data into JSON/YAML-serializable containers."""
    if isinstance(value, Mapping):
        return {str(key): thaw(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [thaw(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted((thaw(item) for item in value), key=repr)
    if isinstance(value, Path):
        return str(value)
    return value


@dataclass(frozen=True)
class EffectiveConfig(Mapping[str, Any]):
    """Deeply immutable resolved portable configuration."""

    data: Mapping[str, Any]
    repository_root: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "data", freeze(self.data))
        object.__setattr__(self, "repository_root", Path(self.repository_root).resolve())

    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.data)

    def __len__(self) -> int:
        return len(self.data)

    def to_dict(self) -> dict[str, Any]:
        return thaw(self.data)

    @property
    def schema_version(self) -> str:
        return str(self.data["schema_version"])


@dataclass(frozen=True)
class ConfigProvenance(Mapping[str, str]):
    """Immutable mapping from resolved leaf field to its winning source."""

    sources: Mapping[str, str]
    schema_version: str = "2.1"

    def __post_init__(self) -> None:
        object.__setattr__(self, "sources", freeze(self.sources))

    def __getitem__(self, key: str) -> str:
        return self.sources[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.sources)

    def __len__(self) -> int:
        return len(self.sources)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "fields": thaw(self.sources),
        }


@dataclass(frozen=True)
class ResolvedConfig:
    """Configuration resolution result and generated artifact locations."""

    config: EffectiveConfig
    provenance: ConfigProvenance
    effective_config_path: Path
    provenance_path: Path


@dataclass(frozen=True)
class ArtifactRegistry(Mapping[str, Path]):
    """Immutable registry of explicitly configured artifact paths."""

    paths: Mapping[str, Path]

    def __post_init__(self) -> None:
        object.__setattr__(self, "paths", MappingProxyType(dict(self.paths)))

    def __getitem__(self, key: str) -> Path:
        return self.paths[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.paths)

    def __len__(self) -> int:
        return len(self.paths)

    def to_dict(self) -> dict[str, str]:
        return {name: str(path) for name, path in self.paths.items()}
