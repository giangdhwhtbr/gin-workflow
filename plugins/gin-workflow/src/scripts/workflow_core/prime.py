"""`gin prime`: the state card Claude Code shows at session start, after `/clear`, on resume, and after compaction.

It reads and never writes: no session binding, no gate, no event."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
import threading
import time
from typing import Any, Callable, Mapping, Sequence

from . import epic_kind, lifecycle_cli, tasks
from .checkout import main_checkout
from .events import WorkflowEvent, WorkflowEventStore
from .prep import is_prep
from .session_binding import EVENT_TYPE as BOUND, SESSION_VARIABLE, UNBOUND_WORKFLOW, folder_key, is_session_id

CARD_CAP = 9_500
PRE_COMPACT_CAP = 1_500
LIST_CAP = 10
OPEN_CAP = 5
OPEN_DAYS = 14
CALL_TIMEOUT = 4.0  # the shipped check that runs alone before the round, when no flag or session names the workflow
ROUND_TIMEOUT = 8.0  # the concurrent round and each Beads call in it, since concurrent bd calls queue; 4 + 8 s < 15 s
TEXT_CAP = 160  # one list item, cut with "..." beyond it
_GATE_EVENTS = frozenset({"requirement.confirmed", "approval.recorded", "orchestration.ready"})
_LOCAL_STAGES = (("discuss", "requirement_confirmed"), ("plan", "plan_approved"), ("orchestrate", "orchestration_ready"))
_EPOCH = datetime.min.replace(tzinfo=timezone.utc)


class SourceError(Exception):
    """One source of the card failed; only its line reads `unknown (<cause>)`."""


@dataclass(frozen=True)
class Found:
    workflow_id: str | None
    how: str = ""


@dataclass(frozen=True)
class Context:
    root: Path
    start: Path
    events: list[WorkflowEvent]
    settings: Any  # project.ProjectSettings
    team: Any  # team.TeamConfig | None
    beads: bool


class _Background:
    """One job on a daemon thread, joined later. A daemon thread, not an executor: the process exits without
    waiting for a stuck call."""

    def __init__(self, job: Callable[[], Any]):
        self._out: tuple[Any, str | None] | None = None
        self._started = time.monotonic()
        self._thread = threading.Thread(target=self._run, args=(job,), daemon=True)
        self._thread.start()

    def _run(self, job: Callable[[], Any]) -> None:
        try:
            self._out = (job(), None)
        except Exception as error:  # broad on purpose: a failed source marks only its own line
            self._out = (None, str(error) or type(error).__name__)

    def result(self, timeout: float) -> tuple[Any, str | None]:
        """(value, None), or (None, cause) when the job raised or ran past `timeout` seconds from its start."""
        self._thread.join(max(0.0, self._started + timeout - time.monotonic()))
        return self._out or (None, f"timed out after {timeout:g}s")


def bounded(jobs: Mapping[str, Callable[[], Any]], timeout: float,
            timeouts: Mapping[str, float] | None = None) -> dict[str, tuple[Any, str | None]]:
    """Run every job at once; each result as `_Background.result` gives it, with its own timeout when named."""
    started = {name: _Background(job) for name, job in jobs.items()}
    return {name: job.result((timeouts or {}).get(name, timeout)) for name, job in started.items()}


def query(root: Path, argv: Sequence[str]) -> Any:
    """One read-only task query of the round within ROUND_TIMEOUT; raises SourceError with the cause when it fails."""
    data, cause = tasks.query_result(root, list(argv), timeout=ROUND_TIMEOUT)
    if cause:
        raise SourceError(cause)
    return data


def _when(timestamp: str) -> datetime:
    try:
        moment = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return _EPOCH
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def recent_workflows(events: Sequence[WorkflowEvent], now: datetime) -> list[str]:
    """Workflows with a gate event and an event in the last OPEN_DAYS days, the most recently active first."""
    latest: dict[str, datetime] = {}
    gated: set[str] = set()
    for event in events:
        if event.workflow_id == UNBOUND_WORKFLOW:
            continue
        latest[event.workflow_id] = max(latest.get(event.workflow_id, _EPOCH), _when(event.timestamp))
        if event.event_type in _GATE_EVENTS:
            gated.add(event.workflow_id)
    since = now - timedelta(days=OPEN_DAYS)
    return sorted((wf for wf in gated if latest[wf] >= since), key=lambda wf: latest[wf], reverse=True)


def folder_workflows(events: Sequence[WorkflowEvent], folder: str) -> list[WorkflowEvent]:
    """The `session.bound` events made in `folder`, newest first."""
    return [event for event in reversed(events) if event.event_type == BOUND
            and event.workflow_id != UNBOUND_WORKFLOW and event.payload.get("cwd") == folder]


def local_shipped(events: Sequence[WorkflowEvent], workflow_ids: Sequence[str]) -> set[str]:
    """The workflows of `workflow_ids` with a `delivery.shipped` event."""
    wanted = set(workflow_ids)
    return {event.workflow_id for event in events
            if event.workflow_id in wanted and event.event_type == "delivery.shipped"}


def shipped_among(root: Path, events: Sequence[WorkflowEvent], workflow_ids: Sequence[str], *,
                  timeout: float) -> set[str]:
    """The shipped workflows of `workflow_ids`: a `delivery.shipped` event, or the epic of their
    `orchestration.ready` event closed. One task query for all the epics, within `timeout` seconds; raises
    SourceError with the cause when it fails."""
    done = local_shipped(events, workflow_ids)
    epics = {wf: lifecycle_cli._recorded_epic(events, wf) for wf in workflow_ids if wf not in done}
    epics = {wf: epic for wf, epic in epics.items() if epic}
    if not epics:
        return done
    ids = list(dict.fromkeys(epics.values()))
    # bd show takes about a second per id; bd list --id answers for all ids at once. The markdown list has no --id.
    argv = (["list", "--status", "closed", "--limit", "0", "--id", ",".join(ids)] if _uses_beads(root)
            else ["show", *ids])
    data, cause = tasks.query_result(root, argv, timeout=timeout)
    if cause:
        raise SourceError(cause)
    if not isinstance(data, list):
        raise SourceError("the task query did not return a list")
    closed = {str(row.get("id")) for row in data if isinstance(row, Mapping) and row.get("status") == "closed"}
    return done | {wf for wf, epic in epics.items() if epic in closed}


def resolve(events: Sequence[WorkflowEvent], *, flag: str | None, session_id: str, folder: str,
            shipped: set[str] | None) -> Found:
    """The card's workflow: the flag; the newest binding of the session; with `shipped` known, the newest binding
    made in the folder whose workflow is not shipped."""
    if flag:
        return Found(flag, "flag")
    if session_id:
        for event in reversed(events):
            if (event.event_type == BOUND and event.workflow_id != UNBOUND_WORKFLOW
                    and event.payload.get("session_id") == session_id):
                return Found(event.workflow_id, "this session")
    if shipped is not None:
        for event in folder_workflows(events, folder):
            if event.workflow_id not in shipped:
                return Found(event.workflow_id, f"last session in this folder, {event.timestamp}")
    return Found(None)


def local_stage(events: Sequence[WorkflowEvent], workflow_id: str) -> str:
    """The stage the local event log alone gives; Beads decides between execute and ship."""
    gates = lifecycle_cli._process_gate_state(events, workflow_id)
    return next((stage for stage, gate in _LOCAL_STAGES if not gates[gate]), "execute or ship")


def next_command(workflow_id: str, state: Mapping[str, Any], ready_ids: Sequence[str]) -> str | None:
    """The command that runs the next stage; None for a complete workflow."""
    if state["decision"] == "complete":
        return None
    if state["decision"] == "hold":
        return f"/gin:workflow {workflow_id}"
    if state["stage"] == "execute":
        return "/gin:execute " + " ".join(ready_ids) if ready_ids else f"/gin:workflow {workflow_id}"
    return f"/gin:{state['stage']} {workflow_id}"


def artifact_paths(events: Sequence[WorkflowEvent], workflow_id: str) -> tuple[str, str]:
    """(spec, plan): the evidence of the workflow's newest requirement and plan-approval events."""
    spec = plan = ""
    for event in events:
        if event.workflow_id != workflow_id:
            continue
        if event.event_type == "requirement.confirmed":
            spec = str(event.payload.get("evidence") or "")
        elif event.event_type == "approval.recorded" and event.payload.get("action") == "plan_approved":
            plan = str(event.payload.get("evidence") or "")
    return spec, plan


def ready_tracks(root: Path, epic: str) -> list[Mapping[str, Any]]:
    if not epic:
        return []
    data = query(root, ["ready", "--parent", epic])
    return [row for row in data or () if isinstance(row, Mapping) and not is_prep(row)]


def _cut(text: str) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= TEXT_CAP else text[:TEXT_CAP - 3] + "..."


def _items(texts: Sequence[str]) -> list[str]:
    lines = [f"  - {_cut(text)}" for text in texts[:LIST_CAP]]
    return lines + ([f"  +{len(texts) - LIST_CAP} more"] if len(texts) > LIST_CAP else [])


def _inline(texts: Sequence[str]) -> str:
    shown = ", ".join(_cut(text) for text in texts[:LIST_CAP])
    return shown + (f", +{len(texts) - LIST_CAP} more" if len(texts) > LIST_CAP else "")


def _state(ctx: Context, workflow_id: str) -> dict[str, Any]:
    return lifecycle_cli.state_payload(ctx.root, workflow_id, start=ctx.start, bind=False, warnings=False)[0]


def workflow_lines(ctx: Context, found: Found, recent: Sequence[str], shipped: set[str] | None) -> list[str]:
    wf = found.workflow_id or ""
    epic = lifecycle_cli._recorded_epic(ctx.events, wf)
    spec, plan = artifact_paths(ctx.events, wf)
    others = [other for other in recent if other != wf]
    jobs: dict[str, Callable[[], Any]] = {
        "state": lambda: _state(ctx, wf),
        "kind": lambda: epic_kind.lookup(ctx.root, wf, spec or None),
        "ready": lambda: ready_tracks(ctx.root, epic),
    }
    if shipped is None and others:
        jobs["shipped"] = lambda: shipped_among(ctx.root, ctx.events, others, timeout=ROUND_TIMEOUT)
    got = bounded(jobs, ROUND_TIMEOUT)
    state, state_cause = got["state"]
    kind, kind_error = got["kind"][0] or (None, None)
    detail = [f"epic {epic}"] if epic else []
    if kind and not kind_error:
        detail.append(f"kind {kind}")
    lines = [f"gin state card (workflow found by: {found.how})",
             f"Workflow: {wf}" + (f" ({', '.join(detail)})" if detail else "")]
    if state_cause:
        lines += [f"Stage: unknown ({state_cause})", f"Gates: unknown ({state_cause})"]
    else:
        remedies = "; ".join(state["remedies"])
        lines.append(f"Stage: {state['stage']} ({state['decision']})" + (f"; remedies: {remedies}" if remedies else ""))
        lines.append("Gates: " + ", ".join(f"{gate}={status}" for gate, status in state["gates"].items()))
    if spec:
        lines.append(f"Spec: {spec}")
    if plan:
        lines.append(f"Plan: {plan}")
    ready, ready_cause = got["ready"]
    if ready_cause:
        lines.append(f"Ready tracks: unknown ({ready_cause})")
    elif ready:
        lines += ["Ready tracks:", *_items([f"{row.get('id')} {row.get('title', '')}" for row in ready])]
    if state is not None:
        command = next_command(wf, state, [str(row.get("id")) for row in ready or ()])
        if command:
            lines.append(f"Next: {command}")
    done, done_cause = (shipped, None) if shipped is not None else got.get("shipped", (set(), None))
    still_open = [other for other in others if other not in (done or set())]
    if done_cause:
        lines.append(f"Other open workflows: unknown ({done_cause})")
    elif still_open:
        lines.append("Other open workflows: " + _inline([f"{other} ({local_stage(ctx.events, other)})"
                                                          for other in still_open]))
    return lines


def no_workflow_lines(ctx: Context, open_ids: Sequence[str]) -> list[str]:
    lines = ["gin state card: no workflow is bound to this session or this folder"]
    if not open_ids:
        return [*lines, "Open workflows: none; start one with /gin:discuss"]
    shown = list(open_ids[:OPEN_CAP])
    got = bounded({wf: (lambda wf=wf: _state(ctx, wf)) for wf in shown}, ROUND_TIMEOUT)
    lines.append("Open workflows:")
    for wf in shown:
        state, cause = got[wf]
        if cause:
            lines.append(f"  - {wf}: unknown ({cause})")
            continue
        command = next_command(wf, state, [])
        lines.append(f"  - {wf}: {state['stage']}" + (f", next: {command}" if command else ""))
    if len(open_ids) > OPEN_CAP:
        lines.append(f"  +{len(open_ids) - OPEN_CAP} more")
    return lines


def finish(lines: Sequence[str]) -> str:
    return "\n".join(lines)[:CARD_CAP]


def render(ctx: Context, found: Found, recent: Sequence[str], shipped: set[str] | None) -> str:
    if found.workflow_id is None:
        lines = no_workflow_lines(ctx, [wf for wf in recent if wf not in (shipped or set())])
    else:
        lines = workflow_lines(ctx, found, recent, shipped)
    return finish(lines)


def pre_compact_text(events: Sequence[WorkflowEvent], flag: str | None, session_id: str, folder: str) -> str:
    """What the compaction summary keeps. Local reads only: no Beads call."""
    shipped = local_shipped(events, [event.workflow_id for event in folder_workflows(events, folder)])
    found = resolve(events, flag=flag, session_id=session_id, folder=folder, shipped=shipped)
    if found.workflow_id:
        keep = (f"- keep the workflow id {found.workflow_id} and its stage "
                f"({local_stage(events, found.workflow_id)} by the local event log)")
    else:
        keep = "- keep the gin workflow id and the stage being worked on"
    lines = [
        "gin: in the compaction summary,",
        keep,
        "- keep, word for word, each decision and answer the user gave in this chat that is not yet in the spec, "
        "the plan, or a bead",
        "- keep, word for word, the question waiting for the user's answer",
        "- keep the files being changed and why",
        "- drop tool output and file contents; they can be read again",
        "- the gin state card returns after compaction by itself; do not copy it",
    ]
    return "\n".join(lines)[:PRE_COMPACT_CAP]


def _hook_input(stream: Any) -> dict[str, Any]:
    try:
        value = json.loads(stream.read() or "{}")
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _session_id(hook_input: Mapping[str, Any]) -> str:
    value = str(hook_input.get("session_id") or os.environ.get(SESSION_VARIABLE, ""))
    return value if is_session_id(value) else ""


def _events(root: Path) -> tuple[list[WorkflowEvent], str | None]:
    path = main_checkout(root) / ".agent-workflow/runtime/events.jsonl"
    if not path.is_file():
        return [], None
    events, cause = lifecycle_cli._read_events(WorkflowEventStore(path))
    return events or [], cause


def _uses_beads(root: Path) -> bool:
    from .configuration import ConfigValidationError

    try:
        return tasks.backend(root) == "beads"
    except ConfigValidationError:
        return False


def _run(args: argparse.Namespace, start: Path) -> str:
    from .configuration import resolve_effective_config
    from .project import project_settings
    from .team import load_team
    from .workspace import repository_root

    root = repository_root(args.repository)
    if not (root / ".agent-workflow/config.yaml").is_file():
        return ""
    session_id = _session_id(_hook_input(sys.stdin) if args.hook else {})
    events, cause = _events(root)
    if cause:
        return f"gin state card: {cause}"
    folder = folder_key(start)
    if args.pre_compact:
        return pre_compact_text(events, args.workflow_id, session_id, folder)
    config = resolve_effective_config(root, write=False).config.to_dict()
    ctx = Context(root, start, events, project_settings(config), load_team(config), _uses_beads(root))
    recent = recent_workflows(events, datetime.now(timezone.utc))
    found = resolve(events, flag=args.workflow_id, session_id=session_id, folder=folder, shipped=None)
    shipped = None
    if found.workflow_id is None:
        candidates = [*(event.workflow_id for event in folder_workflows(events, folder)), *recent]
        candidates = list(dict.fromkeys(candidates))
        try:
            shipped = shipped_among(root, events, candidates, timeout=CALL_TIMEOUT)
        except SourceError:
            # simplified: the folder lookup then counts only `delivery.shipped` events
            shipped = local_shipped(events, candidates)
        found = resolve(events, flag=None, session_id="", folder=folder, shipped=shipped)
    return render(ctx, found, recent, shipped)


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="gin prime", description="print the workflow state card")
    parser.add_argument("--repository", type=Path, default=None)
    parser.add_argument("--workflow-id", default=None)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--hook", action="store_true", help="read the hook input JSON on stdin; always exit 0")
    mode.add_argument("--pre-compact", action="store_true",
                      help="print what the compaction summary keeps; no Beads call")
    try:
        args = parser.parse_args(list(argv))
    except SystemExit as error:
        return error.code if isinstance(error.code, int) else 2
    quiet = args.hook or args.pre_compact
    start = Path(args.repository) if args.repository is not None else Path.cwd()
    try:
        from . import version_pin
        from .cli import CLI_VERSION

        pin = version_pin.verdict(CLI_VERSION, start)
        if pin.status in ("older", "invalid", "newer_major"):
            if quiet:
                return 0  # `gin version --hook` already warns
            print(f"error: {version_pin.message(pin, CLI_VERSION)}", file=sys.stderr)
            return 2
        text = _run(args, start)
    except Exception as error:  # broad on purpose: a hook never fails the session start
        if not quiet:
            raise
        print(f"gin prime: {error}", file=sys.stderr)
        return 0
    if text:
        print(text)
    return 0
