"""Canonical source and workflow identity used by acceptance gates."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass


def _require_text(field_name: str, value: object) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} is required")


@dataclass(frozen=True)
class RepositorySnapshot:
    repository_id: str
    source_scope_hash: str
    source_tree_hash: str
    checkpoint_sha: str
    checkpoint_ref: str

    def __post_init__(self) -> None:
        for field_name in (
            "repository_id",
            "source_scope_hash",
            "source_tree_hash",
            "checkpoint_sha",
            "checkpoint_ref",
        ):
            _require_text(field_name, getattr(self, field_name))


@dataclass(frozen=True)
class AcceptanceIdentity:
    workflow_id: str
    attempt_id: str
    task_id: str
    repositories: Sequence[RepositorySnapshot]

    def __post_init__(self) -> None:
        for field_name in ("workflow_id", "attempt_id", "task_id"):
            _require_text(field_name, getattr(self, field_name))
        repositories = tuple(self.repositories)
        if not repositories:
            raise ValueError("repositories must not be empty")
        if any(not isinstance(item, RepositorySnapshot) for item in repositories):
            raise TypeError("repositories must contain RepositorySnapshot values")
        ordered = tuple(sorted(repositories, key=lambda item: item.repository_id))
        for previous, current in zip(ordered, ordered[1:]):
            if previous.repository_id == current.repository_id:
                raise ValueError(f"duplicate repository_id: {current.repository_id}")
        object.__setattr__(self, "repositories", ordered)

    def to_dict(self) -> dict[str, object]:
        return {
            "workflow_id": self.workflow_id,
            "attempt_id": self.attempt_id,
            "task_id": self.task_id,
            "repositories": [asdict(item) for item in self.repositories],
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "AcceptanceIdentity":
        if not isinstance(value, Mapping):
            raise TypeError("acceptance identity must be a mapping")
        raw_repositories = value.get("repositories")
        if not isinstance(raw_repositories, Sequence) or isinstance(raw_repositories, (str, bytes)):
            raise ValueError("repositories must be a sequence")
        repositories: list[RepositorySnapshot] = []
        for item in raw_repositories:
            if not isinstance(item, Mapping):
                raise ValueError("repository snapshots must be mappings")
            try:
                repositories.append(
                    RepositorySnapshot(
                        repository_id=item["repository_id"],
                        source_scope_hash=item["source_scope_hash"],
                        source_tree_hash=item["source_tree_hash"],
                        checkpoint_sha=item["checkpoint_sha"],
                        checkpoint_ref=item["checkpoint_ref"],
                    )
                )
            except KeyError as error:
                raise ValueError(f"missing repository field: {error.args[0]}") from error
        try:
            return cls(
                workflow_id=value["workflow_id"],
                attempt_id=value["attempt_id"],
                task_id=value["task_id"],
                repositories=tuple(repositories),
            )
        except KeyError as error:
            raise ValueError(f"missing acceptance identity field: {error.args[0]}") from error

    def require_exact_match(self, other: "AcceptanceIdentity") -> None:
        if not isinstance(other, AcceptanceIdentity):
            raise TypeError("other must be an AcceptanceIdentity")
        for field_name in ("workflow_id", "attempt_id", "task_id", "repositories"):
            if getattr(self, field_name) != getattr(other, field_name):
                raise ValueError(f"acceptance identity mismatch: {field_name}")
