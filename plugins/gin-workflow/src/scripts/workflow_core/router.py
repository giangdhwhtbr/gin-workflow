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
from .models import EffectiveConfig, thaw
from .waivers import NON_WAIVABLE_GATES, GateWaiver, collect_waivers


LIFECYCLE_STAGES = (
    "discuss",
    "plan",
    "orchestrate",
    "execute",
    "ship",
    "progress",
)

_STAGE_GATES = (
    ("discuss", "requirement_confirmed"),
    ("plan", "plan_approved"),
    ("orchestrate", "orchestration_ready"),
    ("execute", "implementation_complete"),
    ("ship", "shipped"),
)

_GUARDED_ACTIONS = frozenset(
    {
        ApprovalAction.DISABLE_ISOLATION,
        ApprovalAction.CURRENT_BRANCH_EXECUTION,
        ApprovalAction.SCOPE_CHANGE,
        ApprovalAction.EXECUTION_STRATEGY_CHANGE,
        ApprovalAction.PRODUCTION_PARALLEL_WORK,
        ApprovalAction.DATA_MOVE,
    }
)
_CLOCK_SKEW_TOLERANCE = timedelta(seconds=60)


def _approval_ttl(config: EffectiveConfig | Mapping[str, Any] | None = None) -> timedelta:
    if config is not None:
        if isinstance(config, EffectiveConfig):
            policy = config.get("policy", {})
        elif isinstance(config, Mapping):
            policy = config.get("policy", {})
        else:
            policy = {}
        if isinstance(policy, Mapping):
            approval_policy = policy.get("approval", {})
            if isinstance(approval_policy, Mapping):
                ttl_seconds = approval_policy.get("ttl_seconds", 86400)
                if isinstance(ttl_seconds, (int, float)) and ttl_seconds >= 0:
                    return timedelta(seconds=ttl_seconds)
    return timedelta(seconds=86400)


def _bind_to_scope(config: EffectiveConfig | Mapping[str, Any] | None = None) -> bool:
    if config is not None:
        if isinstance(config, EffectiveConfig):
            policy = config.get("policy", {})
        elif isinstance(config, Mapping):
            policy = config.get("policy", {})
        else:
            policy = {}
        if isinstance(policy, Mapping):
            approval_policy = policy.get("approval", {})
            if isinstance(approval_policy, Mapping):
                bind = approval_policy.get("bind_to_scope", True)
                if type(bind) is bool:
                    return bind
    return True


def _scope_matches(
    request: ApprovalRequest,
    target_scope: str | Mapping[str, Any],
    bind_to_scope: bool = True,
) -> bool:
    if not bind_to_scope:
        return True
    req_hash = str(getattr(request, "scope_hash", "") or "")
    if isinstance(target_scope, Mapping):
        state_hash = str(target_scope.get("scope_hash", "") or "")
    else:
        state_hash = str(target_scope or "")
    if req_hash and state_hash:
        return req_hash == state_hash
    return True


@dataclass(frozen=True)
class RouteDecision:
    """One lifecycle action plus the facts that justified selecting it."""

    stage: str
    decision: str
    evidence: tuple[str, ...]
    remedies: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.stage not in LIFECYCLE_STAGES:
            raise ValueError(f"unsupported lifecycle stage: {self.stage}")
        if self.decision == "hold" and not self.remedies:
            raise ValueError("hold decision must include at least one remedy")


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


def _is_fresh(timestamp: datetime, now: datetime, ttl: timedelta = timedelta(seconds=86400)) -> bool:
    age = now - timestamp
    return -_CLOCK_SKEW_TOLERANCE <= age <= ttl


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
    ttl: timedelta = timedelta(seconds=86400),
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
        payload = thaw(event.payload)
        if payload.get("request") != request.to_dict():
            saw_mismatch = True
            continue
        if payload.get("decision") != decision.to_dict():
            saw_mismatch = True
            continue

        event_time = _parse_utc(event.timestamp)
        if event_time is None:
            saw_invalid = True
            continue
        if (decision_time - event_time) > _CLOCK_SKEW_TOLERANCE or not _is_fresh(event_time, now, ttl):
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


def authorize_protected_action(
    action: ApprovalAction,
    workflow_id: str,
    request: ApprovalRequest,
    decision: ApprovalDecision,
    store: WorkflowEventStore,
    *,
    now: datetime | None = None,
    scope_hash: str = "",
    config: EffectiveConfig | Mapping[str, Any] | None = None,
) -> None:
    """Fail closed unless a protected action has fresh, persisted authorization."""
    action = ApprovalAction(action)
    if action not in _GUARDED_ACTIONS:
        raise ValueError(f"unsupported guarded action: {action.value}")
    if not workflow_id:
        raise ValueError("workflow_id is required for guarded actions")
    if not isinstance(request, ApprovalRequest):
        raise TypeError("approval_request must be an ApprovalRequest")
    if not isinstance(decision, ApprovalDecision):
        raise TypeError("approval_decision must be an ApprovalDecision")
    if not isinstance(store, WorkflowEventStore):
        raise TypeError("audit_event_store must be a WorkflowEventStore")
    if request.action is not action:
        raise PermissionError("approval request action mismatch")
    if request.workflow_id != workflow_id:
        raise PermissionError("approval request workflow mismatch")
    require_approval(decision, request)
    ttl = _approval_ttl(config)
    bind = _bind_to_scope(config)
    if not _scope_matches(request, scope_hash, bind):
        raise PermissionError("approval scope has changed")
    checked_at = now or datetime.now(timezone.utc)
    decision_time = _parse_utc(decision.decided_at)
    if decision_time is None:
        raise PermissionError("approval decision timestamp is invalid")
    if not _is_fresh(decision_time, checked_at, ttl):
        raise PermissionError("approval decision is stale")
    audit_status = _audit_status(
        store,
        workflow_id=workflow_id,
        request=request,
        decision=decision,
        decision_time=decision_time,
        now=checked_at,
        ttl=ttl,
    )
    if audit_status != "recorded":
        raise PermissionError(f"approval audit is {audit_status}")


def _guard_evidence(
    state: Mapping[str, Any],
    now: datetime,
    config: EffectiveConfig | Mapping[str, Any] | None = None,
) -> tuple[tuple[str, ...], bool, tuple[str, ...]]:
    actions = _coerce_guarded_actions(state.get("guarded_actions", ()))
    if not actions:
        return (), False, ()

    workflow_id = state.get("workflow_id")
    if not isinstance(workflow_id, str) or not workflow_id:
        raise ValueError("workflow_id is required for guarded actions")
    requests = state.get("approval_requests", {})
    decisions = state.get("approval_decisions", {})
    if not isinstance(requests, Mapping):
        raise TypeError("approval_requests must be a mapping")
    if not isinstance(decisions, Mapping):
        raise TypeError("approval_decisions must be a mapping")

    cfg = config or state.get("config")
    ttl = _approval_ttl(cfg)
    bind = _bind_to_scope(cfg)

    evidence: list[str] = []
    for action in actions:
        key = action.value
        request = requests.get(key)
        if not isinstance(request, ApprovalRequest):
            evidence.append(f"approval_request:{key}=invalid_type")
            return tuple(evidence), True, (f"re-request approval for {key}",)
        if request.action is not action:
            evidence.append(f"approval_request:{key}=action_mismatch")
            return tuple(evidence), True, (f"re-request approval for {key}",)
        if request.workflow_id != workflow_id:
            evidence.append(f"approval_request:{key}=workflow_mismatch")
            return tuple(evidence), True, (f"re-request approval for {key}",)

        decision = decisions.get(key)
        if decision is None:
            evidence.append(f"approval:{key}=missing")
            return tuple(evidence), True, (f"re-request approval for {key}",)
        if not isinstance(decision, ApprovalDecision):
            evidence.append(f"approval:{key}=invalid_type")
            return tuple(evidence), True, (f"re-request approval for {key}",)
        if decision.request_id != request.request_id:
            evidence.append(f"approval:{key}=stale")
            return tuple(evidence), True, (f"re-request approval for {key}",)
        try:
            require_approval(decision, request)
        except PermissionError:
            evidence.append(f"approval:{key}=denied")
            return tuple(evidence), True, (f"re-request approval for {key}",)

        if not _scope_matches(request, state, bind):
            evidence.append(f"approval:{key}=scope_changed")
            return tuple(evidence), True, (f"re-request approval for {key}",)

        decision_time = _parse_utc(decision.decided_at)
        if decision_time is None:
            evidence.append(f"approval:{key}=invalid_timestamp")
            return tuple(evidence), True, (f"re-request approval for {key}",)
        if not _is_fresh(decision_time, now, ttl):
            evidence.append(f"approval:{key}=stale")
            return tuple(evidence), True, (f"re-request approval for {key}",)
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
            ttl=ttl,
        )
        if audit_status != "recorded":
            evidence.append(f"audit:{key}={audit_status}")
            remedy = (
                f"re-record audit event for {key}"
                if audit_status in ("missing", "invalid", "mismatched", "stale")
                else f"re-request approval for {key}"
            )
            return tuple(evidence), True, (remedy,)
        evidence.append(f"audit:{key}=recorded")
    return tuple(evidence), False, ()


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


def _gate_status(
    state: Mapping[str, Any], gate: str, waivers: Mapping[str, GateWaiver]
) -> str:
    """Return 'satisfied', 'waived', or 'unmet' for a lifecycle gate."""
    if gate in state:
        value = state[gate]
        if type(value) is not bool:
            raise TypeError(f"{gate} must be a boolean")
        if value:
            return "satisfied"
    if gate not in NON_WAIVABLE_GATES and gate in waivers:
        return "waived"
    return "unmet"


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
        gate = str(state.get("gate") or "<gate>")
        return RouteDecision(
            "progress",
            "hold",
            (f"blocked:{blocker}",),
            remedies=(
                "unblock --clear-blocker",
                f"unblock --gate {gate} --reason <why>",
            ),
        )

    guard_evidence, blocked_by_guard, guard_remedies = _guard_evidence(
        state, datetime.now(timezone.utc), config
    )
    if blocked_by_guard:
        return RouteDecision(
            "progress", "hold", guard_evidence, remedies=guard_remedies
        )

    store = state.get("audit_event_store")
    workflow_id = state.get("workflow_id")
    scope_hash = str(state.get("scope_hash") or "")
    if (
        isinstance(store, WorkflowEventStore)
        and isinstance(workflow_id, str)
        and workflow_id
    ):
        waivers = collect_waivers(store, workflow_id=workflow_id, scope_hash=scope_hash)
    else:
        waivers = {}

    evidence_prefix: list[str] = list(guard_evidence)
    for stage, completed_gate in _STAGE_GATES:
        status = _gate_status(state, completed_gate, waivers)
        if status == "satisfied":
            continue
        if status == "waived":
            waiver = waivers[completed_gate]
            evidence_prefix.append(f"{completed_gate}=waived({waiver.reason})")
            continue

        evidence = (*evidence_prefix, f"{completed_gate}=false")
        if not _capability_enabled(config, stage):
            return RouteDecision(
                "progress",
                "hold",
                (*evidence, f"capability:{stage}=disabled"),
                remedies=(
                    f"enable capabilities.{stage} in effective-config.yaml",
                    f"waive {completed_gate} with a recorded reason",
                ),
            )
        return RouteDecision(stage, "route", evidence)

    return RouteDecision("progress", "complete", (*evidence_prefix, "shipped=true"))

