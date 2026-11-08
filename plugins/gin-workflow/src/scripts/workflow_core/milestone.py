"""Milestone status and working-day schedule: pure functions over `bd list --json` rows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import math
import re
from typing import Any, Mapping

SCHEMA = 1
WORKDAY_MINUTES = 480
Beads = Mapping[str, Mapping[str, Any]]


@dataclass(frozen=True)
class Roadmap:
    """What `gin milestone list` reads from the roadmap file."""
    deadline: date | None = None
    lanes: int | None = None
    error: str | None = None


class CycleError(ValueError):
    """The milestone's epics block each other in a loop."""


def parse_date(text: str) -> date:
    try:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(text)):
            raise ValueError
        return date.fromisoformat(str(text))
    except ValueError:
        raise ValueError(f"not an ISO date (YYYY-MM-DD): {text}") from None


def _meta(bead: Mapping[str, Any]) -> Mapping[str, Any]:
    meta = bead.get("metadata")
    return meta if isinstance(meta, Mapping) else {}


def period(milestone: Mapping[str, Any]) -> tuple[date, date]:
    meta = _meta(milestone)
    if not meta.get("start") or not meta.get("end"):
        raise ValueError(f"{milestone['id']} has no start/end metadata")
    return parse_date(meta["start"]), parse_date(meta["end"])


def status(milestone: Mapping[str, Any], today: date) -> str:
    if milestone.get("status") == "closed":
        return "closed"
    kickoff = _meta(milestone).get("kickoff")
    if not kickoff:
        return "planned"
    return "scheduled" if parse_date(kickoff) > today else "active"


def estimate_days(minutes: Any) -> int | None:
    if isinstance(minutes, (int, float)) and not isinstance(minutes, bool) and minutes > 0:
        return math.ceil(minutes / WORKDAY_MINUTES)
    return None


def _workday(day: date) -> date:
    """The first working day (Monday to Friday) on or after `day`."""
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day


def _last_of(start: date, days: int) -> date:
    """The last of `days` consecutive working days beginning on the working day `start`."""
    for _ in range(days - 1):
        start = _workday(start + timedelta(days=1))
    return start


def workdays_after(end: date, finish: date) -> int:
    count, day = 0, end + timedelta(days=1)
    while day <= finish:
        count += day.weekday() < 5
        day += timedelta(days=1)
    return count


def _blocks(bead: Mapping[str, Any]) -> list[str]:
    return [str(dep["depends_on_id"]) for dep in bead.get("dependencies") or []
            if dep.get("type") == "blocks" and not str(dep.get("depends_on_id", "")).startswith("external:")]


def epics_of(milestone_id: str, beads: Beads) -> list[Mapping[str, Any]]:
    return [bead for bead in beads.values() if bead.get("parent") == milestone_id and bead.get("issue_type") == "epic"]


def _milestone_of(bead: Mapping[str, Any], beads: Beads) -> str | None:
    parent = bead.get("parent")
    return parent if parent and (beads.get(parent) or {}).get("issue_type") == "milestone" else None


def lanes_of(milestone: Mapping[str, Any], default_lanes: int) -> int:
    """The milestone's `lanes` metadata (int or digit string), else the default."""
    text = str(_meta(milestone).get("lanes", ""))
    return int(text) if re.fullmatch(r"[1-9][0-9]*", text) else default_lanes


def _check_cycles(epics: Mapping[str, Mapping[str, Any]]) -> None:
    done: set[str] = set()

    def visit(epic_id: str, path: list[str]) -> None:
        if epic_id in done:
            return
        if epic_id in path:
            loop = path[path.index(epic_id):] + [epic_id]
            raise CycleError("dependency cycle: " + " -> ".join(loop))
        for dep in _blocks(epics[epic_id]):
            if dep in epics:
                visit(dep, path + [epic_id])
        done.add(epic_id)

    for epic_id in sorted(epics):
        visit(epic_id, [])


def _place(epics: Mapping[str, Mapping[str, Any]], first: date, lanes: int) -> dict[str, tuple[date, date]]:
    """Greedy placement on `lanes` lanes from the working day `first`: the ready epic with the earliest allowed
    start (ties by id) takes the lane that frees first. Unestimated epics take no lane and no days."""
    _check_cycles(epics)
    planned: dict[str, tuple[date, date]] = {}
    free = [first] * max(1, min(lanes, len(epics)))  # more lanes than epics change nothing
    while len(planned) < len(epics):
        ready: dict[str, date] = {}
        for epic_id, epic in epics.items():
            deps = [dep for dep in _blocks(epic) if dep in epics]
            if epic_id in planned or any(dep not in planned for dep in deps):
                continue
            begin = first
            for dep in deps:
                dep_start, dep_end = planned[dep]
                estimated = estimate_days(epics[dep].get("estimated_minutes")) is not None
                begin = max(begin, _workday(dep_end + timedelta(days=1)) if estimated else dep_start)
            ready[epic_id] = begin
        epic_id = min(ready, key=lambda item: (ready[item], item))
        days = estimate_days(epics[epic_id].get("estimated_minutes"))
        if days is None:
            planned[epic_id] = (ready[epic_id], ready[epic_id])
            continue
        lane = min(range(len(free)), key=lambda index: free[index])
        begin = max(ready[epic_id], free[lane])
        end = _last_of(begin, days)
        planned[epic_id] = (begin, end)
        free[lane] = _workday(end + timedelta(days=1))
    return planned


def schedule(milestone: Mapping[str, Any], beads: Beads, start: date, today: date,
             default_lanes: int = 1) -> dict[str, Any]:
    _, end = period(milestone)
    epics = {epic["id"]: epic for epic in epics_of(milestone["id"], beads)}
    planned = _place(epics, _workday(start), lanes_of(milestone, default_lanes))
    active = status(milestone, today) == "active"
    rows = []
    for epic_id in sorted(epics, key=lambda item: (planned[item][0], item)):
        epic = epics[epic_id]
        begin, finish = planned[epic_id]
        days = estimate_days(epic.get("estimated_minutes"))
        outside = [beads[dep] for dep in _blocks(epic) if dep not in epics and dep in beads]
        warnings: list[dict[str, Any]] = []
        if overflow := workdays_after(end, finish):
            warnings.append({"code": "overflow", "days": overflow})
        if active and epic.get("status") != "closed" and finish < today:
            warnings.append({"code": "late"})
        if days is None:
            warnings.append({"code": "unestimated"})
        if any(bead.get("status") != "closed" for bead in outside):
            warnings.append({"code": "external_blocker"})
        rows.append({
            "id": epic_id, "title": epic.get("title", ""), "status": epic.get("status"), "estimate_days": days,
            "planned_start": begin.isoformat(), "planned_end": finish.isoformat(),
            "depends_on": sorted(dep for dep in _blocks(epic) if dep in epics),
            "external_depends_on": [{"id": bead["id"], "milestone": _milestone_of(bead, beads)}
                                    for bead in sorted(outside, key=lambda bead: bead["id"])],
            "warnings": warnings,
        })
    last = max((dates[1] for dates in planned.values()), default=None)
    return {"finish": last.isoformat() if last else None,
            "overflow_days": workdays_after(end, last) if last else 0, "epics": rows}


def show_payload(milestone: Mapping[str, Any], beads: Beads, start: date | None, today: date,
                 default_lanes: int = 1) -> dict[str, Any]:
    meta = _meta(milestone)
    begin, _ = period(milestone)
    schedule_start = start or (parse_date(meta["kickoff"]) if meta.get("kickoff") else begin)
    return {"schema": SCHEMA, "id": milestone["id"], "title": milestone.get("title", ""),
            "description": milestone.get("description") or "", "status": status(milestone, today),
            "start": meta["start"], "end": meta["end"], "kickoff": meta.get("kickoff"),
            "schedule_start": schedule_start.isoformat(), "preview": start is not None, "today": today.isoformat(),
            "lanes": lanes_of(milestone, default_lanes),
            **schedule(milestone, beads, schedule_start, today, default_lanes)}


def _open_roadmap_epics(beads: Beads) -> dict[str, Mapping[str, Any]]:
    return {bead["id"]: bead for bead in beads.values()
            if bead.get("issue_type") == "epic" and "roadmap" in (bead.get("labels") or [])
            and bead.get("status") != "closed"}


def forecast(beads: Beads, today: date, roadmap: Roadmap, default_lanes: int) -> dict[str, Any] | None:
    """When every open roadmap epic finishes: open milestones in `end` order on their own lanes, one after
    another, then the unassigned pool on `default_lanes`. None when no roadmap epic is open. On a cycle or bad
    milestone metadata, `error` is set and `finish` covers only the groups placed before it."""
    epics = _open_roadmap_epics(beads)
    if not epics:
        return None
    result: dict[str, Any] = {
        "deadline": roadmap.deadline.isoformat() if roadmap.deadline else None, "lanes": default_lanes,
        "start": today.isoformat(), "finish": None, "overflow_days": 0, "open_epics": len(epics),
        "unestimated": sum(estimate_days(epic.get("estimated_minutes")) is None for epic in epics.values()),
        "error": roadmap.error}
    milestones = sorted((bead for bead in beads.values()
                         if bead.get("issue_type") == "milestone" and bead.get("status") != "closed"),
                        key=lambda bead: (str(_meta(bead).get("end", "")), bead["id"]))
    groups: list[tuple[Mapping[str, Any] | None, dict[str, Mapping[str, Any]]]] = [
        (m, {k: v for k, v in epics.items() if v.get("parent") == m["id"]}) for m in milestones]
    owned = {k for _, group in groups for k in group}
    groups.append((None, {k: v for k, v in epics.items() if k not in owned}))
    cursor, ends = _workday(today), []
    try:
        for milestone, group in groups:
            if not group:
                continue
            if milestone is None:
                first, lanes = cursor, default_lanes
            else:
                begin, _ = period(milestone)
                meta = _meta(milestone)
                first = max(cursor, parse_date(meta["kickoff"]) if meta.get("kickoff") else begin)
                lanes = lanes_of(milestone, default_lanes)
            planned = _place(group, _workday(first), lanes)
            group_ends = [planned[k][1] for k, v in group.items() if estimate_days(v.get("estimated_minutes")) is not None]
            if group_ends:
                ends.append(max(group_ends))
                cursor = _workday(max(group_ends) + timedelta(days=1))
    except ValueError as error:  # CycleError and bad milestone metadata
        result["error"] = str(error)
    if ends:
        finish = max(ends)
        result["finish"] = finish.isoformat()
        if roadmap.deadline:
            result["overflow_days"] = workdays_after(roadmap.deadline, finish)
    return result


def list_payload(beads: Beads, today: date, include_closed: bool, roadmap: Roadmap | None = None,
                 default_lanes: int = 1) -> dict[str, Any]:
    roadmap = roadmap or Roadmap()
    entries = []
    milestones = [bead for bead in beads.values() if bead.get("issue_type") == "milestone"]
    for milestone in sorted(milestones, key=lambda bead: (str(_meta(bead).get("start", "")), bead["id"])):
        if milestone.get("status") == "closed" and not include_closed:
            continue
        meta = _meta(milestone)
        epics = epics_of(milestone["id"], beads)
        entry = {"id": milestone["id"], "title": milestone.get("title", ""),
                 "status": "closed" if milestone.get("status") == "closed" else "planned",
                 "start": meta.get("start"), "end": meta.get("end"), "kickoff": meta.get("kickoff"),
                 "lanes": lanes_of(milestone, default_lanes),
                 "finish": None, "epics": {"total": len(epics),
                                           "closed": sum(epic.get("status") == "closed" for epic in epics)},
                 "warnings": None, "error": None}
        try:
            entry["status"] = status(milestone, today)
            begin, _ = period(milestone)
            start = parse_date(meta["kickoff"]) if meta.get("kickoff") else begin
            plan = schedule(milestone, beads, start, today, default_lanes)
            entry["finish"] = plan["finish"]
            entry["warnings"] = sum(len(row["warnings"]) for row in plan["epics"])
        except ValueError as error:  # CycleError included
            entry["error"] = str(error)
        entries.append(entry)
    unassigned = sum(1 for bead in _open_roadmap_epics(beads).values() if not bead.get("parent"))
    return {"schema": SCHEMA, "milestones": entries, "unassigned_epics": unassigned, "today": today.isoformat(),
            "forecast": forecast(beads, today, roadmap, default_lanes)}
