"""Tie the running Claude Code session to a workflow: one `session.bound` event per session and workflow."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
import os
import re
import sys

from .events import EventPersistenceError, WorkflowEvent, WorkflowEventStore

EVENT_TYPE = "session.bound"
SESSION_VARIABLE = "CLAUDE_CODE_SESSION_ID"
UNBOUND_WORKFLOW = "default-workflow"
_SESSION_ID = re.compile(r"[A-Za-z0-9_.-]{1,128}")


def binding_event(workflow_id: str, environ: Mapping[str, str] | None = None) -> WorkflowEvent | None:
    """The event that binds the session named by the environment to `workflow_id`.

    None when there is nothing to bind: no session id, an id with other characters, or the default workflow."""
    session_id = (os.environ if environ is None else environ).get(SESSION_VARIABLE, "")
    if workflow_id == UNBOUND_WORKFLOW or not _SESSION_ID.fullmatch(session_id):
        return None
    return WorkflowEvent.create(event_type=EVENT_TYPE, workflow_id=workflow_id,
                                payload={"session_id": session_id}, idempotency_key=f"session:{session_id}")


def bind_session(store: WorkflowEventStore, workflow_id: str,
                 events: Sequence[WorkflowEvent] | None = None) -> WorkflowEvent | None:
    """Record once that the running session worked on `workflow_id`; the event when this call wrote it.

    `events` is the log as the caller already read it: a binding found there costs no lock and no write.
    The binding is bookkeeping, so a store that cannot be read or written is reported on stderr, never raised."""
    event = binding_event(workflow_id)
    if event is None or any(item.event_id == event.event_id for item in events or ()):
        return None
    try:
        return event if store.append(event) else None
    except (EventPersistenceError, OSError, ValueError) as error:
        print(f"gin: session not bound: {error}", file=sys.stderr)
        return None


def bound_sessions(events: Iterable[WorkflowEvent], workflow_id: str) -> list[dict[str, str]]:
    """The `sessions` key of `gin state`: the bindings of `workflow_id` in log order, oldest first."""
    return [{"session_id": str(event.payload.get("session_id", "")), "bound_at": event.timestamp}
            for event in events if event.workflow_id == workflow_id and event.event_type == EVENT_TYPE]
