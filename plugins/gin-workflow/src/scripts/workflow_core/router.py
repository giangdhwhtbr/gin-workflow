"""Guarded single-stage routing for the portable workflow lifecycle."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from .approvals import (
    ApprovalAction,
    ApprovalDecision,
    ApprovalRequest,
    require_approval,
)
from .events import EventPersistenceError, WorkflowEvent, WorkflowEventStore
from .models import EffectiveConfig


LIFECYCLE_STAGES = (
    "discuss",
    "plan",
    "orchestrate",
    "execute",
    "verify",
    "ship",
    "progress",
)

_STAGE_GATES = (
    ("discuss", "requirement_confirmed"),
    ("plan", "plan_approved"),
    ("orchestrate", "orchestration_ready"),
    ("execute", "implementation_complete"),
    ("verify", "verification_passed"),
    ("ship", "shipped"),
)

_GUARDED_ACTIONS = frozenset(
    {
        ApprovalAction.DISABLE_ISOLATION,
        ApprovalAction.CURRENT_BRANCH_EXECUTION,
        ApprovalAction.SCOPE_CHANGE,
        ApprovalAction.EXECUTION_STRATEGY_CHANGE,
        ApprovalAction.PRODUCTION_PARALLEL_WORK,
    }
)
_APPROVAL_FRESHNESS = timedelta(minutes=5)


@dataclass(frozen=True)
class RouteDecision:
    """One lifecycle action plus the facts that justified selecting it."""

    stage: str
    decision: str
    evidence: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.stage not in LIFECYCLE_STAGES:
            raise ValueError(f"unsupported lifecycle stage: {self.stage}")


def _coerce_guarded_actions(value: object) -> tuple[ApprovalAction, ...]:
    if not isinstance(value, (list, tuple, set, frozenset)):
        raise TypeError("guarded_actions must be a collection")
    try:
        actions = tuple(ApprovalAction(action) for action in value)
    except ValueError as error:
        raise ValueError(f"unsupported guarded action: {error}") from error
    unsupported = set(actions).difference(_GUARDED_ACTIONS)
    if unsupported:
        rendered = ", ".join(sorted(action.value for action in unsupported))
        raise ValueError(f"unsupported guarded actions: {rendered}")
    return tuple(sorted(set(actions), key=lambda action: action.value))


def _parse_utc(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _is_fresh(timestamp: datetime, now: datetime) -> bool:
    age = now - timestamp
    return timedelta(0) <= age <= _APPROVAL_FRESHNESS


def _revalidate_audit_event(value: object) -> WorkflowEvent | None:
    try:
        if isinstance(value, WorkflowEvent):
            event = value
        elif isinstance(value, Mapping):
            event = WorkflowEvent.from_mapping(value)
        else:
            return None
        return WorkflowEvent.from_mapping(event.to_dict())
    except (EventPersistenceError, TypeError, ValueError):
        return None


def _audit_status(
    store: WorkflowEventStore,
    *,
    workflow_id: str,
    request: ApprovalRequest,
    decision: ApprovalDecision,
    decision_time: datetime,
    now: datetime,
) -> str:
    try:
        persisted_events = store.read_all()
    except (EventPersistenceError, OSError, ValueError):
        return "invalid"
    if not persisted_events:
        return "missing"

    saw_invalid = False
    saw_mismatch = False
    saw_stale = False
    for value in persisted_events:
        event = _revalidate_audit_event(value)
        if event is None:
            saw_invalid = True
            continue
        if event.event_type != "approval.recorded":
            continue
        if event.workflow_id != workflow_id:
            saw_mismatch = True
            continue
        if event.actor != decision.decided_by:
            saw_mismatch = True
            continue
        if not isinstance(event.payload, Mapping):
            saw_invalid = True
            continue
        if event.payload.get("request") != request.to_dict():
            saw_mismatch = True
            continue
        if event.payload.get("decision") != decision.to_dict():
            saw_mismatch = True
            continue

        event_time = _parse_utc(event.timestamp)
        if event_time is None:
            saw_invalid = True
            continue
        if event_time < decision_time or not _is_fresh(event_time, now):
            saw_stale = True
            continue
        return "recorded"

    if saw_stale:
        return "stale"
    if saw_invalid:
        return "invalid"
    if saw_mismatch:
        return "mismatched"
    return "missing"


def _guard_evidence(
    state: Mapping[str, Any], now: datetime
) -> tuple[tuple[str, ...], bool]:
    actions = _coerce_guarded_actions(state.get("guarded_actions", ()))
    if not actions:
        return (), False

    workflow_id = state.get("workflow_id")
    if not isinstance(workflow_id, str) or not workflow_id:
        raise ValueError("workflow_id is required for guarded actions")
    requests = state.get("approval_requests", {})
    decisions = state.get("approval_decisions", {})
    if not isinstance(requests, Mapping):
        raise TypeError("approval_requests must be a mapping")
    if not isinstance(decisions, Mapping):
        raise TypeError("approval_decisions must be a mapping")

    evidence: list[str] = []
    for action in actions:
        key = action.value
        request = requests.get(key)
        if not isinstance(request, ApprovalRequest):
            evidence.append(f"approval_request:{key}=invalid_type")
            return tuple(evidence), True
        if request.action is not action:
            evidence.append(f"approval_request:{key}=action_mismatch")
            return tuple(evidence), True
        if request.workflow_id != workflow_id:
            evidence.append(f"approval_request:{key}=workflow_mismatch")
            return tuple(evidence), True

        decision = decisions.get(key)
        if decision is None:
            evidence.append(f"approval:{key}=missing")
            return tuple(evidence), True
        if not isinstance(decision, ApprovalDecision):
            evidence.append(f"approval:{key}=invalid_type")
            return tuple(evidence), True
        if decision.request_id != request.request_id:
            evidence.append(f"approval:{key}=stale")
            return tuple(evidence), True
        try:
            require_approval(decision, request)
        except PermissionError:
            evidence.append(f"approval:{key}=denied")
            return tuple(evidence), True

        decision_time = _parse_utc(decision.decided_at)
        if decision_time is None:
            evidence.append(f"approval:{key}=invalid_timestamp")
            return tuple(evidence), True
        if not _is_fresh(decision_time, now):
            evidence.append(f"approval:{key}=stale")
            return tuple(evidence), True
        evidence.append(f"approval:{key}=approved")

        store = state.get("audit_event_store")
        if not isinstance(store, WorkflowEventStore):
            raise TypeError("audit_event_store must be a WorkflowEventStore")
        audit_status = _audit_status(
            store,
            workflow_id=workflow_id,
            request=request,
            decision=decision,
            decision_time=decision_time,
            now=now,
        )
        if audit_status != "recorded":
            evidence.append(f"audit:{key}={audit_status}")
            return tuple(evidence), True
        evidence.append(f"audit:{key}=recorded")
    return tuple(evidence), False


def _capability_enabled(config: EffectiveConfig, stage: str) -> bool:
    capabilities = config.get("capabilities", {})
    if not isinstance(capabilities, Mapping):
        raise TypeError("EffectiveConfig capabilities must be a mapping")
    key = stage if stage in capabilities else f"lifecycle.{stage}"
    if key not in capabilities:
        return True
    value = capabilities[key]
    if type(value) is not bool:
        raise TypeError(f"capability {stage} must be a boolean")
    return value


def _gate_complete(state: Mapping[str, Any], gate: str) -> bool:
    if gate not in state:
        return False
    value = state[gate]
    if type(value) is not bool:
        raise TypeError(f"{gate} must be a boolean")
    return value


def route_next_stage(
    state: Mapping[str, Any], config: EffectiveConfig
) -> RouteDecision:
    """Select exactly one next stage after evaluating lifecycle and safety guards."""
    if not isinstance(state, Mapping):
        raise TypeError("state must be a mapping")
    if not isinstance(config, EffectiveConfig):
        raise TypeError("config must be an EffectiveConfig")

    if state.get("blocked") or state.get("status") == "blocked":
        blocker = str(state.get("blocker") or "unspecified")
        return RouteDecision("progress", "hold", (f"blocked:{blocker}",))

    guard_evidence, blocked_by_guard = _guard_evidence(
        state, datetime.now(timezone.utc)
    )
    if blocked_by_guard:
        return RouteDecision("progress", "hold", guard_evidence)

    for stage, completed_gate in _STAGE_GATES:
        if _gate_complete(state, completed_gate):
            continue
        evidence = (*guard_evidence, f"{completed_gate}=false")
        if not _capability_enabled(config, stage):
            return RouteDecision(
                "progress",
                "hold",
                (*evidence, f"capability:{stage}=disabled"),
            )
        return RouteDecision(stage, "route", evidence)

    return RouteDecision("progress", "complete", (*guard_evidence, "shipped=true"))
