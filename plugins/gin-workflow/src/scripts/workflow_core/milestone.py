"""Milestone status and working-day schedule: pure functions over `bd list --json` rows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import json
import math
import re
import statistics
from typing import Any, Mapping, Sequence

SCHEMA = 1
WORKDAY_MINUTES = 480
SPEC_DUE_DAYS = 5
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


_BUILDING = re.compile(r"dev|be_.+|fe_.+|.+_dev|.+_lead")


def is_building_role(role: str) -> bool:
    return bool(_BUILDING.fullmatch(str(role)))


def _ranges(spec: Any) -> frozenset[date]:
    """Dates of `["D", "D..D", ...]`; raises ValueError on a malformed entry or a reversed range."""
    if not isinstance(spec, list):
        raise ValueError("away ranges must be a list")
    found: set[date] = set()
    for item in spec:
        first, _, last = str(item).partition("..")
        begin, end = parse_date(first), parse_date(last or first)
        if begin > end:
            raise ValueError(f"reversed range: {item}")
        found.update(begin + timedelta(days=n) for n in range((end - begin).days + 1))
    return frozenset(found)


def away_of(milestone: Mapping[str, Any]) -> dict[str, list[str]] | None:
    """The milestone's `away` metadata as {member: [range, ...]}; {} when absent, None when malformed."""
    value = _meta(milestone).get("away")
    if value in (None, ""):
        return {}
    try:
        value = json.loads(value) if isinstance(value, str) else value
        if not isinstance(value, Mapping):
            raise ValueError("away must be an object")
        for spec in value.values():
            _ranges(spec)
    except ValueError:  # json.JSONDecodeError is a ValueError
        return None
    return {str(member): [str(item) for item in spec] for member, spec in value.items()}


def _integration(milestone: Mapping[str, Any]) -> date | None:
    try:
        value = _meta(milestone).get("integration")
        return parse_date(value) if value else None
    except ValueError:
        return None


def metadata_problems(milestone: Mapping[str, Any]) -> list[str]:
    """Names of the metadata keys (`away`, `integration`) that are present but unreadable; they are ignored."""
    meta = _meta(milestone)
    problems = []
    if meta.get("away") not in (None, "") and away_of(milestone) is None:
        problems.append("away")
    if meta.get("integration") and _integration(milestone) is None:
        problems.append("integration")
    return problems


def _open_bugs(beads: Beads) -> dict[str, int]:
    counts: dict[str, int] = {}
    for bead in beads.values():
        if bead.get("issue_type") != "bug" or bead.get("status") == "closed":
            continue
        for dep in bead.get("dependencies") or []:
            if dep.get("type") == "discovered-from":
                target = str(dep.get("depends_on_id"))
                counts[target] = counts.get(target, 0) + 1
    return counts


def _off(day: date, off: frozenset[date]) -> date:
    """The first working day on or after `day` that is not in `off`."""
    while day.weekday() >= 5 or day in off:
        day += timedelta(days=1)
    return day


def _lane_off(milestone: Mapping[str, Any], builders: Sequence[str]) -> list[frozenset[date]] | None:
    """Days off per lane when lanes come from building members: lane n is builders[n]."""
    away = away_of(milestone)
    if not builders or lanes_of(milestone, 0) or not away:
        return None
    return [_ranges(away.get(member, [])) for member in builders]


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


def _workdays_before(begin: date, end: date) -> int:
    """Working days from `begin` up to, not including, `end`."""
    count, day = 0, begin
    while day < end:
        count += day.weekday() < 5
        day += timedelta(days=1)
    return count


def remaining_days(epic: Mapping[str, Any], beads: Beads, today: date) -> int | None:
    """Days left: the estimate for a not-started epic; for an in-progress one, the share of open child tracks,
    else the estimate minus the working days since `started_at`. At least 1; None when unestimated."""
    days = estimate_days(epic.get("estimated_minutes"))
    if days is None or epic.get("status") != "in_progress":
        return days
    tracks = [bead for bead in beads.values() if bead.get("parent") == epic["id"] and bead.get("issue_type") != "epic"]
    if tracks:
        still_open = sum(track.get("status") != "closed" for track in tracks)
        return max(1, math.ceil(days * still_open / len(tracks)))
    try:
        begun = parse_date(str(epic.get("started_at") or "")[:10])
    except ValueError:
        return days
    return max(1, days - _workdays_before(begun, today))


def _planned_days(epics: Mapping[str, Mapping[str, Any]], beads: Beads, today: date) -> dict[str, int | None]:
    """Days each epic takes in the schedule: remaining days, else for an open unestimated epic the median
    estimate of the group's estimated, not-closed epics, rounded up (1 when none); a closed unestimated epic
    takes none."""
    known = [d for epic in epics.values()
             if epic.get("status") != "closed" and (d := estimate_days(epic.get("estimated_minutes"))) is not None]
    assumed = math.ceil(statistics.median(known)) if known else 1
    planned: dict[str, int | None] = {}
    for epic_id, epic in epics.items():
        days = remaining_days(epic, beads, today)
        planned[epic_id] = assumed if days is None and epic.get("status") != "closed" else days
    return planned


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


def _place(epics: Mapping[str, Mapping[str, Any]], first: date, lanes: int,
           days: Mapping[str, int | None],
           off: Sequence[frozenset[date]] | None = None) -> dict[str, tuple[date, date]]:
    """Greedy placement on `lanes` lanes from the working day `first`: the ready epic with the earliest allowed
    start (ties by id) takes the lane that frees first. Epics whose days are None take no lane and no days."""
    _check_cycles(epics)
    planned: dict[str, tuple[date, date]] = {}
    # more lanes than epics change nothing, unless lanes differ by days off: then every lane may win
    free = [first] * max(1, lanes if off else min(lanes, len(epics)))
    while len(planned) < len(epics):
        ready: dict[str, date] = {}
        for epic_id, epic in epics.items():
            deps = [dep for dep in _blocks(epic) if dep in epics]
            if epic_id in planned or any(dep not in planned for dep in deps):
                continue
            begin = first
            for dep in deps:
                dep_start, dep_end = planned[dep]
                estimated = days[dep] is not None
                begin = max(begin, _workday(dep_end + timedelta(days=1)) if estimated else dep_start)
            ready[epic_id] = begin
        epic_id = min(ready, key=lambda item: (ready[item], item))
        length = days[epic_id]
        if length is None:
            planned[epic_id] = (ready[epic_id], ready[epic_id])
            continue
        def lane_off_of(index: int) -> frozenset[date]:
            return off[index] if off and index < len(off) else frozenset()

        lane = min(range(len(free)), key=lambda index: (
            _off(max(ready[epic_id], free[index]), lane_off_of(index)), free[index], index))
        lane_off = lane_off_of(lane)
        begin = _off(max(ready[epic_id], free[lane]), lane_off)
        end = begin
        for _ in range(length - 1):
            end = _off(end + timedelta(days=1), lane_off)
        planned[epic_id] = (begin, end)
        free[lane] = _off(end + timedelta(days=1), lane_off)
    return planned


def schedule(milestone: Mapping[str, Any], beads: Beads, start: date, today: date,
             default_lanes: int = 1, confirmed: frozenset[str] | None = None,
             builders: Sequence[str] = ()) -> dict[str, Any]:
    start_day, end = period(milestone)
    epics = {epic["id"]: epic for epic in epics_of(milestone["id"], beads)}
    days_of = _planned_days(epics, beads, today)
    planned = _place(epics, _workday(start), lanes_of(milestone, default_lanes), days_of,
                     _lane_off(milestone, builders))
    active = status(milestone, today) == "active"
    kicked_off = status(milestone, today) in ("scheduled", "active")
    due = status(milestone, today) == "planned" and start_day <= _last_of(_workday(today), SPEC_DUE_DAYS)
    integration = _integration(milestone)
    bugs = _open_bugs(beads)
    span_days = _workdays_before(start_day, end + timedelta(days=1))
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
        if confirmed is not None and epic.get("status") != "closed" and epic_id not in confirmed:
            if kicked_off:
                warnings.append({"code": "spec_not_ready"})
            elif due:
                warnings.append({"code": "spec_due"})
        still_open = epic.get("status") != "closed"
        if integration and still_open and finish > integration:
            warnings.append({"code": "after_integration"})
        if bugs.get(epic_id):
            warnings.append({"code": "open_bugs", "count": bugs[epic_id]})
        if still_open and days_of[epic_id] is not None and days_of[epic_id] > span_days:
            warnings.append({"code": "oversized", "days": days_of[epic_id] - span_days})
        rows.append({
            "id": epic_id, "title": epic.get("title", ""), "status": epic.get("status"), "estimate_days": days,
            "remaining_days": remaining_days(epic, beads, today),
            "assumed_days": days_of[epic_id] if days is None else None,
            "spec_confirmed": None if confirmed is None else epic_id in confirmed,
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
                 default_lanes: int = 1, confirmed: frozenset[str] | None = None,
                 deadline: date | None = None, builders: Sequence[str] = ()) -> dict[str, Any]:
    meta = _meta(milestone)
    begin, _ = period(milestone)
    schedule_start = start or (parse_date(meta["kickoff"]) if meta.get("kickoff") else begin)
    return {"schema": SCHEMA, "id": milestone["id"], "title": milestone.get("title", ""),
            "description": milestone.get("description") or "", "status": status(milestone, today),
            "start": meta["start"], "end": meta["end"], "kickoff": meta.get("kickoff"),
            "schedule_start": schedule_start.isoformat(), "preview": start is not None, "today": today.isoformat(),
            "lanes": lanes_of(milestone, default_lanes), "away": away_of(milestone) or {},
            "integration": i.isoformat() if (i := _integration(milestone)) else None,
            "deadline": deadline.isoformat() if deadline else None,
            **schedule(milestone, beads, schedule_start, today, default_lanes, confirmed, builders)}


def _open_roadmap_epics(beads: Beads) -> dict[str, Mapping[str, Any]]:
    return {bead["id"]: bead for bead in beads.values()
            if bead.get("issue_type") == "epic" and "roadmap" in (bead.get("labels") or [])
            and bead.get("status") != "closed"}


def forecast(beads: Beads, today: date, roadmap: Roadmap, default_lanes: int,
             builders: Sequence[str] = ()) -> dict[str, Any] | None:
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
            off = None
            if milestone is None:
                first, lanes = cursor, default_lanes
            else:
                begin, _ = period(milestone)
                meta = _meta(milestone)
                first = max(cursor, parse_date(meta["kickoff"]) if meta.get("kickoff") else begin)
                lanes = lanes_of(milestone, default_lanes)
                off = _lane_off(milestone, builders)
            days_of = _planned_days(group, beads, today)
            planned = _place(group, _workday(first), lanes, days_of, off)
            group_ends = [planned[k][1] for k in group if days_of[k] is not None]
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
                 default_lanes: int = 1, confirmed: frozenset[str] | None = None,
                 builders: Sequence[str] = ()) -> dict[str, Any]:
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
            plan = schedule(milestone, beads, start, today, default_lanes, confirmed, builders)
            entry["finish"] = plan["finish"]
            entry["warnings"] = sum(len(row["warnings"]) for row in plan["epics"])
        except ValueError as error:  # CycleError included
            entry["error"] = str(error)
        entries.append(entry)
    unassigned = sum(1 for bead in _open_roadmap_epics(beads).values() if not bead.get("parent"))
    return {"schema": SCHEMA, "milestones": entries, "unassigned_epics": unassigned, "today": today.isoformat(),
            "forecast": forecast(beads, today, roadmap, default_lanes, builders)}
