"""Tie the running Claude Code session to a workflow: a `session.bound` event each time it moves to one."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
import os
import re
import subprocess
import sys

from .events import EventPersistenceError, WorkflowEvent, WorkflowEventStore

EVENT_TYPE = "session.bound"
SESSION_VARIABLE = "CLAUDE_CODE_SESSION_ID"
UNBOUND_WORKFLOW = "default-workflow"
_SESSION_ID = re.compile(r"[A-Za-z0-9_.-]{1,128}")


def is_session_id(value: str) -> bool:
    """True for a Claude Code session id gin records: 1 to 128 letters, digits, `_`, `.`, or `-`."""
    return bool(_SESSION_ID.fullmatch(value or ""))


def folder_key(start: Path | None = None) -> str:
    """The folder a binding names: the git top level of `start` (default: the current directory), else `start`."""
    path = Path(start or Path.cwd()).resolve()
    try:
        done = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=path, capture_output=True, text=True,
                              timeout=10, check=False)
    except (OSError, subprocess.SubprocessError):
        return str(path)
    top = done.stdout.strip()
    return str(Path(top).resolve()) if done.returncode == 0 and top else str(path)


def binding_event(workflow_id: str, environ: Mapping[str, str] | None = None, *,
                  start: Path | None = None, events: Sequence[WorkflowEvent] = ()) -> WorkflowEvent | None:
    """The event that binds the session named by the environment to `workflow_id`, made in the folder of `start`.

    None when there is nothing to bind: no session id, an id with other characters, the default workflow, or a
    session whose newest binding in `events` already names this workflow and folder."""
    session_id = (os.environ if environ is None else environ).get(SESSION_VARIABLE, "")
    if workflow_id == UNBOUND_WORKFLOW or not is_session_id(session_id):
        return None
    return _next_binding(workflow_id, session_id, folder_key(start), events)


def _next_binding(workflow_id: str, session_id: str, cwd: str,
                  events: Sequence[WorkflowEvent]) -> WorkflowEvent | None:
    """A binding after the session's newest one, keyed by that event so a return to an earlier workflow is new."""
    latest = next((event for event in reversed(events)
                   if event.event_type == EVENT_TYPE and event.payload.get("session_id") == session_id), None)
    if latest is not None and latest.workflow_id == workflow_id and latest.payload.get("cwd") == cwd:
        return None
    key = f"session:{session_id}" if latest is None else f"session:{session_id}:after:{latest.event_id}"
    return WorkflowEvent.create(event_type=EVENT_TYPE, workflow_id=workflow_id,
                                payload={"session_id": session_id, "cwd": cwd}, idempotency_key=key)


def bind_session(store: WorkflowEventStore, workflow_id: str,
                 events: Sequence[WorkflowEvent] | None = None, *, start: Path | None = None) -> WorkflowEvent | None:
    """Record that the running session moved to `workflow_id` in this folder; the event when this call wrote it.

    `events` is the log as the caller already read it: a session whose newest binding there names this workflow
    and folder costs no lock and no write. The binding is bookkeeping, so a store that cannot be read or written
    is reported on stderr, never raised."""
    event = binding_event(workflow_id, start=start, events=events or ())
    if event is None:
        return None
    try:
        with store.transaction() as tx:
            event = _next_binding(workflow_id, event.payload["session_id"], event.payload["cwd"], tx.events)
            return event if event is not None and tx.append(event) else None
    except (EventPersistenceError, OSError, ValueError) as error:
        print(f"gin: session not bound: {error}", file=sys.stderr)
        return None


def bound_sessions(events: Iterable[WorkflowEvent], workflow_id: str) -> list[dict[str, str]]:
    """The `sessions` key of `gin state`: one entry per session of `workflow_id`, at its first binding, oldest first.
    A session bound from two folders, before `cwd` was recorded, or again after another workflow, has several events."""
    first: dict[str, dict[str, str]] = {}
    for event in events:
        if event.workflow_id == workflow_id and event.event_type == EVENT_TYPE:
            session_id = str(event.payload.get("session_id", ""))
            first.setdefault(session_id, {"session_id": session_id, "bound_at": event.timestamp})
    return list(first.values())
