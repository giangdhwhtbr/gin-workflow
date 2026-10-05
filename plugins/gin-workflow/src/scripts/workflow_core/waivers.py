"""Gate waivers: bypassing a lifecycle gate leaves an auditable record.

A gate is never removed. It is either satisfied, or waived by an actor who
stated a reason, against a named scope, with a follow-up task when the gate
protects safety rather than process.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .events import EventPersistenceError, WorkflowEvent, WorkflowEventStore
from .models import thaw


class GateClass(str, Enum):
    PROCESS = "process"
    SAFETY = "safety"


# Ceremony an agent may skip on its own authority, stating why.
PROCESS_GATES = frozenset(
    {"requirement_confirmed", "plan_approved", "orchestration_ready"}
)
# Bypass requires human approval and a follow-up task. `review_approved` is
# deliberately not a router gate (see docs/concepts/lifecycle.md); it is
# classified here so that waiving independent review is recorded the same way.
SAFETY_GATES = frozenset({"verification_passed", "review_approved"})
# `implementation_complete` states a fact, not a formality, and `shipped` is
# terminal. Neither is meaningfully waivable.
NON_WAIVABLE_GATES = frozenset({"implementation_complete", "shipped"})

WAIVER_EVENT_TYPE = "gate.waived"


def classify_gate(gate: str) -> GateClass:
    """Return the waiver class of a gate, or reject one that cannot be waived."""
    if gate in PROCESS_GATES:
        return GateClass.PROCESS
    if gate in SAFETY_GATES:
        return GateClass.SAFETY
    if gate in NON_WAIVABLE_GATES:
        raise ValueError(f"gate is not waivable: {gate}")
    raise ValueError(f"unknown gate: {gate}")


@dataclass(frozen=True)
class GateWaiver:
    gate: str
    gate_class: GateClass
    reason: str
    scope_hash: str
    waived_by: str
    follow_up_task_id: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("gate", "reason", "scope_hash", "waived_by"):
            if not str(getattr(self, field_name) or "").strip():
                raise ValueError(f"{field_name} is required")
        object.__setattr__(self, "gate_class", GateClass(self.gate_class))

        classified = classify_gate(self.gate)
        if classified is not self.gate_class:
            raise ValueError(
                f"gate_class {self.gate_class.value} disagrees with "
                f"gate {self.gate}, which is {classified.value}"
            )
        if self.gate_class is GateClass.SAFETY and not str(
            self.follow_up_task_id or ""
        ).strip():
            raise ValueError(
                f"follow_up_task_id is required to waive safety gate {self.gate}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate": self.gate,
            "gate_class": self.gate_class.value,
            "reason": self.reason,
            "scope_hash": self.scope_hash,
            "waived_by": self.waived_by,
            "follow_up_task_id": self.follow_up_task_id,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "GateWaiver":
        if not isinstance(value, Mapping):
            raise TypeError("waiver payload must be a mapping")
        unknown = set(value).difference(
            {
                "gate",
                "gate_class",
                "reason",
                "scope_hash",
                "waived_by",
                "follow_up_task_id",
            }
        )
        if unknown:
            raise ValueError(f"unexpected waiver fields: {', '.join(sorted(unknown))}")
        return cls(
            gate=str(value["gate"]),
            gate_class=GateClass(value["gate_class"]),
            reason=str(value["reason"]),
            scope_hash=str(value["scope_hash"]),
            waived_by=str(value["waived_by"]),
            follow_up_task_id=value.get("follow_up_task_id"),
        )


def build_waiver_event(
    waiver: GateWaiver, *, workflow_id: str, task_id: str | None = None
) -> WorkflowEvent:
    """Render one waiver as a durable, deterministic audit event."""
    if not isinstance(waiver, GateWaiver):
        raise TypeError("waiver must be a GateWaiver")
    return WorkflowEvent.create(
        event_type=WAIVER_EVENT_TYPE,
        workflow_id=workflow_id,
        task_id=task_id,
        payload=waiver.to_dict(),
        actor=waiver.waived_by,
    )


def collect_waivers(
    store: WorkflowEventStore, *, workflow_id: str, scope_hash: str
) -> dict[str, GateWaiver]:
    """Return the newest valid waiver per gate for one workflow and scope.

    Fails closed: an unreadable stream yields no waivers rather than raising,
    and a malformed waiver payload is skipped rather than trusted.
    """
    if not isinstance(store, WorkflowEventStore):
        raise TypeError("store must be a WorkflowEventStore")
    if not workflow_id or not scope_hash:
        return {}
    try:
        events = store.read_all()
    except (EventPersistenceError, OSError, ValueError):
        return {}

    waivers: dict[str, GateWaiver] = {}
    for event in events:
        if event.event_type != WAIVER_EVENT_TYPE or event.workflow_id != workflow_id:
            continue
        # Revalidate the serialized form the way the router revalidates audit
        # events, so a hand-edited record cannot slip through.
        try:
            revalidated = WorkflowEvent.from_mapping(event.to_dict())
            waiver = GateWaiver.from_mapping(thaw(revalidated.payload))
        except (EventPersistenceError, KeyError, TypeError, ValueError):
            continue
        if waiver.scope_hash != scope_hash:
            continue
        waivers[waiver.gate] = waiver
    return waivers
