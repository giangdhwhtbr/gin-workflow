"""Milestone status and working-day schedule: pure functions over `bd list --json` rows."""

from __future__ import annotations

from datetime import date, timedelta
import math
import re
from typing import Any, Mapping

SCHEMA = 1
WORKDAY_MINUTES = 480
Beads = Mapping[str, Mapping[str, Any]]


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


def schedule(milestone: Mapping[str, Any], beads: Beads, start: date, today: date) -> dict[str, Any]:
    _, end = period(milestone)
    epics = {epic["id"]: epic for epic in epics_of(milestone["id"], beads)}
    first = _workday(start)
    planned: dict[str, tuple[date, date]] = {}

    def visit(epic_id: str, path: list[str]) -> tuple[date, date]:
        if epic_id in planned:
            return planned[epic_id]
        if epic_id in path:
            loop = path[path.index(epic_id):] + [epic_id]
            raise CycleError("dependency cycle: " + " -> ".join(loop))
        begin = first
        for dep in _blocks(epics[epic_id]):
            if dep in epics:
                dep_start, dep_end = visit(dep, path + [epic_id])
                estimated = estimate_days(epics[dep].get("estimated_minutes")) is not None
                begin = max(begin, _workday(dep_end + timedelta(days=1)) if estimated else dep_start)
        days = estimate_days(epics[epic_id].get("estimated_minutes"))
        planned[epic_id] = (begin, _last_of(begin, days) if days else begin)
        return planned[epic_id]

    for epic_id in sorted(epics):
        visit(epic_id, [])
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


def show_payload(milestone: Mapping[str, Any], beads: Beads, start: date | None, today: date) -> dict[str, Any]:
    meta = _meta(milestone)
    begin, _ = period(milestone)
    schedule_start = start or (parse_date(meta["kickoff"]) if meta.get("kickoff") else begin)
    return {"schema": SCHEMA, "id": milestone["id"], "title": milestone.get("title", ""),
            "description": milestone.get("description") or "", "status": status(milestone, today),
            "start": meta["start"], "end": meta["end"], "kickoff": meta.get("kickoff"),
            "schedule_start": schedule_start.isoformat(), "preview": start is not None, "today": today.isoformat(),
            **schedule(milestone, beads, schedule_start, today)}


def list_payload(beads: Beads, today: date, include_closed: bool) -> dict[str, Any]:
    entries = []
    milestones = [bead for bead in beads.values() if bead.get("issue_type") == "milestone"]
    for milestone in sorted(milestones, key=lambda bead: (str(_meta(bead).get("start", "")), bead["id"])):
        if milestone.get("status") == "closed" and not include_closed:
            continue
        meta = _meta(milestone)
        epics = epics_of(milestone["id"], beads)
        entry = {"id": milestone["id"], "title": milestone.get("title", ""), "status": None,
                 "start": meta.get("start"), "end": meta.get("end"), "kickoff": meta.get("kickoff"),
                 "finish": None, "epics": {"total": len(epics),
                                           "closed": sum(epic.get("status") == "closed" for epic in epics)},
                 "warnings": None, "error": None}
        try:
            entry["status"] = status(milestone, today)
            begin, _ = period(milestone)
            start = parse_date(meta["kickoff"]) if meta.get("kickoff") else begin
            plan = schedule(milestone, beads, start, today)
            entry["finish"] = plan["finish"]
            entry["warnings"] = sum(len(row["warnings"]) for row in plan["epics"])
        except ValueError as error:  # CycleError included
            entry["error"] = str(error)
        entries.append(entry)
    unassigned = sum(1 for bead in beads.values()
                     if bead.get("issue_type") == "epic" and "roadmap" in (bead.get("labels") or [])
                     and bead.get("status") != "closed" and not bead.get("parent"))
    return {"schema": SCHEMA, "milestones": entries, "unassigned_epics": unassigned, "today": today.isoformat()}
