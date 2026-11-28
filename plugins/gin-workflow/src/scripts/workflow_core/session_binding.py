"""Tie the running Claude Code session to a workflow: one `session.bound` event per session and workflow."""

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
                  start: Path | None = None) -> WorkflowEvent | None:
    """The event that binds the session named by the environment to `workflow_id`, made in the folder of `start`.

    None when there is nothing to bind: no session id, an id with other characters, or the default workflow."""
    session_id = (os.environ if environ is None else environ).get(SESSION_VARIABLE, "")
    if workflow_id == UNBOUND_WORKFLOW or not is_session_id(session_id):
        return None
    return WorkflowEvent.create(event_type=EVENT_TYPE, workflow_id=workflow_id,
                                payload={"session_id": session_id, "cwd": folder_key(start)},
                                idempotency_key=f"session:{session_id}")


def bind_session(store: WorkflowEventStore, workflow_id: str,
                 events: Sequence[WorkflowEvent] | None = None, *, start: Path | None = None) -> WorkflowEvent | None:
    """Record once per folder that the running session worked on `workflow_id`; the event when this call wrote it.

    `events` is the log as the caller already read it: a binding found there costs no lock and no write.
    The binding is bookkeeping, so a store that cannot be read or written is reported on stderr, never raised."""
    event = binding_event(workflow_id, start=start)
    if event is None or any(item.event_id == event.event_id for item in events or ()):
        return None
    try:
        return event if store.append(event) else None
    except (EventPersistenceError, OSError, ValueError) as error:
        print(f"gin: session not bound: {error}", file=sys.stderr)
        return None


def bound_sessions(events: Iterable[WorkflowEvent], workflow_id: str) -> list[dict[str, str]]:
    """The `sessions` key of `gin state`: one entry per session of `workflow_id`, at its first binding, oldest first.
    A session bound from two folders, or before `cwd` was recorded, has several events."""
    first: dict[str, dict[str, str]] = {}
    for event in events:
        if event.workflow_id == workflow_id and event.event_type == EVENT_TYPE:
            session_id = str(event.payload.get("session_id", ""))
            first.setdefault(session_id, {"session_id": session_id, "bound_at": event.timestamp})
    return list(first.values())
