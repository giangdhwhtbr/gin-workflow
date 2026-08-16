"""Filesystem evidence index adapter."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
import json
import fcntl
import os
from pathlib import Path
import threading
import tempfile
from typing import Any

from .contracts import (
    EvidenceCategory,
    EvidenceCompleteness,
    EvidenceQuery,
    EvidenceRecord,
    evidence_outcome_succeeds,
    OperationStatus,
    ProviderBase,
    ProviderResult,
)


class FileEvidenceProvider(ProviderBase):
    provider_name = "filesystem"
    provider_type = "evidence"
    capabilities = frozenset({"evidence.record", "evidence.query", "evidence.completeness"})

    def __init__(self, index_path: Path) -> None:
        super().__init__()
        candidate = Path(index_path)
        self.index_path = candidate if candidate.suffix else candidate / "index.json"
        self._lock = threading.RLock()

    @contextmanager
    def _file_lock(self, *, exclusive: bool):
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self.index_path.with_name(f".{self.index_path.name}.lock")
        with lock_path.open("a+b") as handle:
            operation = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
            fcntl.flock(handle.fileno(), operation)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def _load(self) -> list[EvidenceRecord]:
        if not self.index_path.exists():
            return []
        data = json.loads(self.index_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("records"), list):
            raise ValueError("evidence index must contain a records list")
        records: list[EvidenceRecord] = []
        for raw in data["records"]:
            if not isinstance(raw, dict):
                raise ValueError("evidence records must be objects")
            records.append(
                EvidenceRecord(
                    evidence_id=str(raw["evidence_id"]),
                    task_id=str(raw["task_id"]),
                    category=EvidenceCategory(str(raw["category"])),
                    outcome=str(raw["outcome"]),
                    reference=str(raw["reference"]),
                    details=raw.get("details", {}),
                )
            )
        return records

    def _write(self, records: list[EvidenceRecord]) -> None:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": "1.0",
            "records": [
                {**asdict(record), "category": record.category.value} for record in records
            ],
        }
        descriptor, temporary_name = tempfile.mkstemp(
            dir=self.index_path.parent,
            prefix=f".{self.index_path.name}.",
            suffix=".tmp",
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.index_path)
        finally:
            if temporary.exists():
                temporary.unlink()

    @staticmethod
    def _validate(evidence: EvidenceRecord, idempotency_key: str) -> str | None:
        if not evidence.evidence_id.strip():
            return "evidence_id is required"
        if not evidence.task_id.strip():
            return "task_id is required"
        if not evidence.outcome.strip() or not evidence.reference.strip():
            return "outcome and reference are required"
        if not idempotency_key:
            return "idempotency_key is required"
        return None

    def record(self, evidence: EvidenceRecord, *, idempotency_key: str) -> ProviderResult[EvidenceRecord]:
        if guarded := self._guard():
            return guarded
        if replay := self._replay("record", idempotency_key, evidence):
            return replay
        if error := self._validate(evidence, idempotency_key):
            return ProviderResult.invalid(error)
        with self._lock, self._file_lock(exclusive=True):
            try:
                records = self._load()
                existing = next((item for item in records if item.evidence_id == evidence.evidence_id), None)
                if existing is not None:
                    if existing == evidence:
                        return self._remember(
                            "record", idempotency_key, evidence,
                            ProviderResult.success(existing, idempotent=True),
                        )
                    return ProviderResult.invalid(
                        f"evidence_id already exists with different content: {evidence.evidence_id}"
                    )
                records.append(evidence)
                self._write(records)
            except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
                return ProviderResult.unavailable(f"evidence index unavailable: {error}")
        return self._remember("record", idempotency_key, evidence, ProviderResult.success(evidence))

    def query(self, query: EvidenceQuery) -> ProviderResult[tuple[EvidenceRecord, ...]]:
        if guarded := self._guard():
            return guarded
        with self._lock, self._file_lock(exclusive=False):
            try:
                records = self._load()
            except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
                return ProviderResult.unavailable(f"evidence index unavailable: {error}")
        found = tuple(
            item
            for item in records
            if (query.task_id is None or item.task_id == query.task_id)
            and (query.category is None or item.category is query.category)
        )
        return ProviderResult.success(found)

    def completeness(self, task_id: str) -> ProviderResult[EvidenceCompleteness]:
        if not task_id.strip():
            return ProviderResult.invalid("task_id is required")
        queried = self.query(EvidenceQuery(task_id=task_id))
        if queried.status is not OperationStatus.SUCCESS:
            return ProviderResult(queried.status, message=queried.message)
        evidence = queried.value or ()
        present = {
            item.category.value
            for item in evidence
            if evidence_outcome_succeeds(item.category, item.outcome)
        }
        missing = tuple(category.value for category in EvidenceCategory if category.value not in present)
        return ProviderResult.success(EvidenceCompleteness(task_id, not missing, missing, evidence))
