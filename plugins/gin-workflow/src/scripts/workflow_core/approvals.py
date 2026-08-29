"""Portable immutable models for approval-gated workflow actions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping

from .models import freeze, thaw


class ApprovalAction(str, Enum):
    COMMIT = "commit"
    PUSH = "push"
    UPGRADE = "upgrade"
    DATA_MOVE = "data_move"
    DISABLE_ISOLATION = "disable_isolation"
    CURRENT_BRANCH_EXECUTION = "current_branch_execution"
    SCOPE_CHANGE = "scope_change"
    EXECUTION_STRATEGY_CHANGE = "execution_strategy_change"
    PRODUCTION_PARALLEL_WORK = "production_parallel_work"


class ApprovalStatus(str, Enum):
    APPROVED = "approved"
    DENIED = "denied"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class ApprovalRequest:
    request_id: str
    action: ApprovalAction
    workflow_id: str
    reason: str
    details: Mapping[str, Any] | None = None
    scope_hash: str = ""

    def __post_init__(self) -> None:
        if not self.request_id or not self.workflow_id or not self.reason:
            raise ValueError("request_id, workflow_id, and reason are required")
        object.__setattr__(self, "action", ApprovalAction(self.action))
        object.__setattr__(self, "details", freeze(self.details or {}))
        object.__setattr__(self, "scope_hash", str(self.scope_hash or ""))

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "action": self.action.value,
            "workflow_id": self.workflow_id,
            "reason": self.reason,
            "details": thaw(self.details),
            "scope_hash": self.scope_hash,
        }


@dataclass(frozen=True)
class ApprovalDecision:
    request_id: str
    status: ApprovalStatus
    decided_by: str
    decided_at: str = ""
    rationale: str | None = None

    def __post_init__(self) -> None:
        if not self.request_id or not self.decided_by:
            raise ValueError("request_id and decided_by are required")
        object.__setattr__(self, "status", ApprovalStatus(self.status))
        if not self.decided_at:
            object.__setattr__(self, "decided_at", _now())

    @property
    def approved(self) -> bool:
        return self.status is ApprovalStatus.APPROVED

    def to_dict(self) -> dict[str, Any]:
        result = {
            "request_id": self.request_id,
            "status": self.status.value,
            "decided_by": self.decided_by,
            "decided_at": self.decided_at,
        }
        if self.rationale is not None:
            result["rationale"] = self.rationale
        return result


def require_approval(decision: ApprovalDecision, request: ApprovalRequest) -> None:
    if decision.request_id != request.request_id:
        raise PermissionError("approval decision does not match the request")
    if not decision.approved:
        raise PermissionError(f"approval denied for {request.action.value}")
