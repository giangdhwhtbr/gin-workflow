"""Repository and Obsidian knowledge adapters with proposal-only mutation semantics."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from .contracts import (
    KnowledgeProposal,
    KnowledgeProposalRecord,
    KnowledgeRecord,
    ProviderBase,
    ProviderResult,
)


def _proposal_record(proposal: KnowledgeProposal) -> KnowledgeProposalRecord:
    identity = hashlib.sha256(
        f"{proposal.title}\0{proposal.body}\0{proposal.proposed_by}\0{proposal.target}".encode()
    ).hexdigest()[:16]
    return KnowledgeProposalRecord(f"proposal-{identity}", proposal)


class RepositoryKnowledgeProvider(ProviderBase):
    provider_name = "repository"
    provider_type = "knowledge"
    capabilities = frozenset({"knowledge.search", "knowledge.propose"})
    _SEARCHABLE_SUFFIXES = frozenset({".md", ".txt", ".json", ".yaml", ".yml"})

    def __init__(self, repository_root: Path) -> None:
        root = Path(repository_root).resolve()
        super().__init__(available=root.is_dir(), health_detail="repository root does not exist" if not root.is_dir() else "")
        self.repository_root = root

    def search(self, query: str) -> ProviderResult[tuple[KnowledgeRecord, ...]]:
        if guarded := self._guard():
            return guarded
        if not query.strip():
            return ProviderResult.invalid("query is required")
        needle = query.casefold()
        found: list[KnowledgeRecord] = []
        try:
            for path in self.repository_root.rglob("*"):
                relative = path.relative_to(self.repository_root)
                if any(part in {".git", "node_modules", "__pycache__"} for part in relative.parts):
                    continue
                if not path.is_file() or path.suffix.casefold() not in self._SEARCHABLE_SUFFIXES:
                    continue
                content = path.read_text(encoding="utf-8", errors="replace")
                if needle in f"{relative}\n{content}".casefold():
                    found.append(KnowledgeRecord(str(relative), path.stem, content, str(path)))
        except OSError as error:
            return ProviderResult.unavailable(f"repository knowledge unavailable: {error}")
        return ProviderResult.success(tuple(found))

    def propose(self, proposal: KnowledgeProposal, *, idempotency_key: str) -> ProviderResult[KnowledgeProposalRecord]:
        if guarded := self._guard():
            return guarded
        if replay := self._replay("propose", idempotency_key, proposal):
            return replay
        if not proposal.title.strip() or not proposal.body.strip() or not proposal.proposed_by.strip() or not idempotency_key:
            return ProviderResult.invalid("title, body, proposed_by, and idempotency_key are required")
        return self._remember("propose", idempotency_key, proposal, ProviderResult.success(_proposal_record(proposal)))


ObsidianSearch = Callable[[str], Iterable[Mapping[str, Any]]]


class ObsidianKnowledgeProvider(ProviderBase):
    provider_name = "obsidian"
    provider_type = "knowledge"
    capabilities = frozenset({"knowledge.search", "knowledge.propose"})

    def __init__(self, search_client: ObsidianSearch | None = None) -> None:
        super().__init__(available=search_client is not None, health_detail="Obsidian search client is not configured")
        self._search_client = search_client

    def search(self, query: str) -> ProviderResult[tuple[KnowledgeRecord, ...]]:
        if guarded := self._guard():
            return guarded
        if not query.strip():
            return ProviderResult.invalid("query is required")
        try:
            raw = tuple(self._search_client(query))  # type: ignore[misc]
            records = tuple(
                KnowledgeRecord(
                    str(item.get("id") or item.get("path") or index),
                    str(item.get("title") or item.get("name") or "Untitled"),
                    str(item.get("body") or item.get("content") or ""),
                    str(item.get("path") or "obsidian"),
                )
                for index, item in enumerate(raw)
            )
        except Exception as error:  # external MCP/client boundary
            return ProviderResult.unavailable(f"Obsidian knowledge unavailable: {error}")
        return ProviderResult.success(records)

    def propose(self, proposal: KnowledgeProposal, *, idempotency_key: str) -> ProviderResult[KnowledgeProposalRecord]:
        if replay := self._replay("propose", idempotency_key, proposal):
            return replay
        if not proposal.title.strip() or not proposal.body.strip() or not proposal.proposed_by.strip() or not idempotency_key:
            return ProviderResult.invalid("title, body, proposed_by, and idempotency_key are required")
        # Deliberately returns a candidate; permanent Obsidian writes require reconciliation authority.
        return self._remember("propose", idempotency_key, proposal, ProviderResult.success(_proposal_record(proposal)))
