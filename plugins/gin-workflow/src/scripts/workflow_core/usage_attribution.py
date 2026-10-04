"""Assign usage records to (owner, stage): a track by its worktree and time span, else the workflow of the next gate."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
from typing import Any, Iterable, Mapping, Sequence

from .events import WorkflowEvent
from .usage_logs import UsageRecord, inside, parse_ts

STAGES = ("discuss", "plan", "orchestrate", "execute", "review", "verify", "ship", "quick")
UNATTRIBUTED = "unattributed"

_GATE_STAGES = {
    "requirement.confirmed": "discuss",
    "quick.completed": "quick",
    "orchestration.ready": "orchestrate",
    "verification.passed": "verify",
    "delivery.shipped": "ship",
}
_REVIEW_ENDS = {"changes-requested", "review-approved", "review-approval-invalidated"}


@dataclass(frozen=True)
class BeadSpan:
    bead: str
    parent: str | None
    start: datetime | None
    end: datetime | None
    review: tuple[tuple[datetime, datetime], ...] = ()


@dataclass(frozen=True)
class Gate:
    ts: datetime
    workflow_id: str
    stage: str


@dataclass(frozen=True)
class Worktree:
    path: Path
    branch: str


def _stage(event: WorkflowEvent) -> str | None:
    if event.event_type == "approval.recorded":
        payload = event.payload or {}
        decision = payload.get("decision")
        approved = isinstance(decision, Mapping) and decision.get("status") == "approved"
        return "plan" if payload.get("action") == "plan_approved" and approved else None
    return _GATE_STAGES.get(event.event_type)


def gates_from_events(events: Iterable[WorkflowEvent]) -> tuple[list[Gate], dict[str, str]]:
    gates: list[Gate] = []
    epic_of: dict[str, str] = {}
    for event in events:
        stage = _stage(event)
        if stage is None:
            continue
        try:
            ts = parse_ts(event.timestamp)
        except (TypeError, ValueError):
            continue
        gates.append(Gate(ts, event.workflow_id, stage))
        epic = (event.payload or {}).get("epic")
        if event.event_type == "orchestration.ready" and isinstance(epic, str) and epic:
            epic_of[event.workflow_id] = epic
    gates.sort(key=lambda gate: gate.ts)
    return gates, epic_of


def worktrees(repo: Path) -> list[Worktree]:
    """Worktrees under <repo>/.planning/worktrees with their branch ("" when detached)."""
    try:
        listed = subprocess.run(["git", "worktree", "list", "--porcelain"], cwd=repo, text=True,
                                capture_output=True, check=False, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return []
    if listed.returncode != 0:
        return []
    base = Path(os.path.realpath(repo)) / ".planning" / "worktrees"
    found: list[Worktree] = []
    path: Path | None = None
    branch = ""
    for line in listed.stdout.splitlines() + [""]:
        if line.startswith("worktree "):
            path, branch = Path(os.path.realpath(line[len("worktree "):])), ""
        elif line.startswith("branch "):
            branch = line[len("branch "):].removeprefix("refs/heads/")
        elif not line and path is not None:
            if path.parent == base:
                found.append(Worktree(path, branch))
            path = None
    return found


def review_intervals(ledger: Mapping[str, Any], *, now: datetime | None = None
                     ) -> tuple[tuple[datetime, datetime], ...]:
    now = now or datetime.now(timezone.utc)
    intervals: list[tuple[datetime, datetime]] = []
    opened: datetime | None = None
    for entry in ledger.get("events") or ():
        if not isinstance(entry, Mapping):
            continue
        try:
            ts = parse_ts(entry["timestamp"])
        except (KeyError, TypeError, ValueError):
            continue
        action = entry.get("action")
        if action == "review-requested" and opened is None:
            opened = ts
        elif action in _REVIEW_ENDS and opened is not None:
            intervals.append((opened, ts))
            opened = None
    if opened is not None:
        intervals.append((opened, now))
    return tuple(intervals)


def _in_tree(record: UsageRecord, tree: Worktree) -> bool:
    return inside(record.cwd, tree.path) or (bool(record.branch) and record.branch == tree.branch)


def attribute(records: Iterable[UsageRecord], *, repo: Path, spans: Mapping[str, BeadSpan],
              trees: Sequence[Worktree], gates: Sequence[Gate], epic_of: Mapping[str, str],
              collecting: str | None = None, now: datetime | None = None
              ) -> dict[tuple[str, str], list[UsageRecord]]:
    now = now or datetime.now(timezone.utc)
    gates = sorted(gates, key=lambda gate: gate.ts)
    owner_of = lambda workflow: epic_of.get(workflow, workflow)  # noqa: E731
    ship: tuple[datetime, datetime] | None = None
    if collecting is not None and gates:
        # Ship is the collecting epic's own work after its verification, while that is still the latest gate
        # in the repository and until the epic closes; otherwise every verified epic would claim the same records.
        last = gates[-1]
        if owner_of(last.workflow_id) == collecting and last.stage == "verify":
            span = spans.get(collecting)
            ship = (last.ts, span.end if span is not None and span.end is not None else now)
    groups: dict[tuple[str, str], list[UsageRecord]] = {}
    for record in records:
        key = _key(record, repo, spans, trees, gates, owner_of, collecting, ship, now)
        groups.setdefault(key, []).append(record)
    return groups


def _key(record, repo, spans, trees, gates, owner_of, collecting, ship, now) -> tuple[str, str]:
    for tree in trees:
        if not _in_tree(record, tree):
            continue
        name = tree.path.name
        holders = [span for span in spans.values()
                   if (span.bead == name or span.parent == name) and span.start is not None
                   and span.start <= record.ts <= (span.end or now)]
        if len(holders) != 1:
            return name, "execute"
        span = holders[0]
        in_review = any(start <= record.ts <= end for start, end in span.review)
        return span.bead, "review" if in_review else "execute"
    if inside(record.cwd, repo):
        for gate in gates:
            if gate.ts > record.ts:
                return owner_of(gate.workflow_id), gate.stage
        if ship is not None and ship[0] < record.ts <= ship[1]:
            return collecting, "ship"
    return UNATTRIBUTED, ""
