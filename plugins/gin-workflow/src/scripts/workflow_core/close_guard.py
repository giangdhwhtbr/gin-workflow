"""`task close` guard: with `project.review_ledger` on, a track closes only after its review ledger holds a
live approval, or with `--waive-review <reason> --actor <id>`, which records a `review.waived` event."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

REVIEW_WAIVED = "review.waived"


def _review_state(root: Path, bead: str) -> str | None:
    """None when the bead's ledger holds a live approval, else why it does not."""
    from review_ledger.cli import load_ledger
    from review_ledger.events import WorkflowIntegrityError

    try:
        _, projection = load_ledger(bead, str(root))
    except FileNotFoundError:
        return "no review ledger"
    except (WorkflowIntegrityError, OSError, ValueError) as error:
        return f"invalid review ledger: {error}"
    return None if projection.active_approval is not None else projection.review_state


def _record_waiver(root: Path, bead: str, epic: str, reason: str, actor: str) -> None:
    from .events import WorkflowEvent
    from .lifecycle_cli import _get_event_store

    store = _get_event_store(root)
    with store.transaction() as tx:
        workflow = next((event.workflow_id for event in reversed(tx.events)
                         if event.event_type == "orchestration.ready"
                         and isinstance(event.payload, Mapping) and event.payload.get("epic") == epic), epic)
        tx.append(WorkflowEvent.create(event_type=REVIEW_WAIVED, workflow_id=workflow, task_id=bead,
                                       actor=actor, payload={"reason": reason},
                                       idempotency_key=f"{bead}:{REVIEW_WAIVED}:{reason}"))


# Options of `bd close`, the global flags and the markdown parser that take a value in the next token.
_VALUE_FLAGS = frozenset({"-r", "--reason", "--reason-file", "--session", "--actor", "--db", "-C", "--directory",
                          "--dolt-auto-commit"})


def _split(argv: Sequence[str], waiving: bool) -> tuple[list[str], list[str], str | None, str | None]:
    """Bead ids, argv to forward, `--waive-review` value and `--actor` value; other tokens stay untouched.
    `--waive-review` (and `--actor` with it) are the only tokens removed; flag names are exact, never abbreviated."""
    ids, forward, waive, actor = [], ["close"], None, None
    tokens, i = list(argv[1:]), 0
    while i < len(tokens):
        token, i = tokens[i], i + 1
        name, eq, inline = token.partition("=")
        if name == "--waive-review" or (waiving and name == "--actor"):
            value = inline
            if not eq and i < len(tokens):
                value, i = tokens[i], i + 1
            if name == "--actor":
                actor = value
            else:
                waive = value
        elif token.startswith("-"):
            forward.append(token)
            if not eq and token in _VALUE_FLAGS and i < len(tokens):
                forward.append(tokens[i])
                i += 1
        else:
            ids.append(token)
            forward.append(token)
    return ids, forward, waive, actor


def check(root: Path, argv: Sequence[str]) -> tuple[list[str], str | None]:
    """Return the `close` argv to forward to the backend, or the error that refuses the whole close."""
    from .configuration import resolve_effective_config
    from .events import EventPersistenceError
    from .project import project_settings
    from .tasks import query_result

    waiving = any(t == "--waive-review" or t.startswith("--waive-review=") for t in argv)
    ledger = project_settings(resolve_effective_config(root, write=False).config.to_dict()).review_ledger
    if not waiving and not ledger:
        return list(argv), None
    ids, forward, waive, actor = _split(argv, waiving)
    if waiving and not (waive and waive.strip() and actor):
        return forward, "--waive-review needs a non-empty reason and --actor"
    if not ledger:
        return forward, None
    unreviewed = []
    for bead in ids:
        shown, cause = query_result(root, ["show", bead])
        if cause:
            return forward, f"{bead}: tracker unavailable: {cause}"
        record = shown[0] if isinstance(shown, list) and len(shown) == 1 else shown
        if isinstance(record, Mapping) and record.get("parent"):
            state = _review_state(root, bead)
            if state:
                unreviewed.append((bead, str(record["parent"]), state))
    if unreviewed and waive is None:
        return forward, "\n".join(f'{bead}: review ledger not approved ({state}); '
                                  f'pass --waive-review "<reason>" --actor <id>' for bead, _, state in unreviewed)
    try:
        for bead, epic, _ in unreviewed:
            _record_waiver(root, bead, epic, waive, actor)
    except (EventPersistenceError, OSError) as error:
        return forward, f"review waiver not recorded: {error}"
    return forward, None
