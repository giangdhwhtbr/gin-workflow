"""Milestone status and working-day schedule: pure functions over `bd list --json` rows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import json
import math
import re
import statistics
from typing import Any, Mapping, Sequence

from .prep import tracks_of

SCHEMA = 1
WORKDAY_MINUTES = 480
SPEC_DUE_DAYS = 5
POINT_SCALE = (1, 2, 3, 5, 8, 13, 21)
MEASURED_EPICS = 10
Beads = Mapping[str, Mapping[str, Any]]


@dataclass(frozen=True)
class Roadmap:
    """What `gin milestone` reads from the roadmap file."""
    deadline: date | None = None
    lanes: int | None = None
    error: str | None = None
    days_per_point: float | None = None


@dataclass(frozen=True)
class Pace:
    """Working days per story point: measured from closed epics, else assumed (roadmap line, else 1)."""
    value: float = 1.0
    measured_epics: int = 0
    assumed: bool = True

    def as_json(self) -> dict[str, Any]:
        return {"value": self.value, "measured_epics": self.measured_epics, "assumed": self.assumed}


DEFAULT_PACE = Pace()


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


def points_of(bead: Mapping[str, Any]) -> int | None:
    """The bead's `points` metadata (int or digit string) when it is on the scale, else None."""
    value = _meta(bead).get("points")
    if isinstance(value, bool) or value is None:
        return None
    text = str(value).strip()
    return int(text) if text.isascii() and text.isdigit() and int(text) in POINT_SCALE else None


def points_problem(bead: Mapping[str, Any]) -> bool:
    """`points` metadata is present but not on the scale; it is ignored."""
    return _meta(bead).get("points") not in (None, "") and points_of(bead) is None


def _day(value: Any) -> date | None:
    try:
        return parse_date(str(value or "")[:10])
    except ValueError:
        return None


def actual_days(bead: Mapping[str, Any], today: date) -> int | None:
    """Working days from `started_at` to `closed_at` (today while open), both included, at least 1;
    None when not started or closed without `closed_at`."""
    begun = _day(bead.get("started_at"))
    ended = _day(bead.get("closed_at")) if bead.get("status") == "closed" else today
    if begun is None or ended is None:
        return None
    return max(1, _workdays_before(begun, ended + timedelta(days=1)))


def measure_pace(beads: Beads, assumed: float | None, today: date) -> Pace:
    """Days per point over the MEASURED_EPICS most recently closed epics with points and actual days;
    else `assumed` (the roadmap's `Days per point:`), else 1."""
    closed = [bead for bead in beads.values()
              if bead.get("issue_type") == "epic"
              and bead.get("status") == "closed" and points_of(bead) is not None
              and actual_days(bead, today) is not None]
    closed.sort(key=lambda bead: (str(bead.get("closed_at")), bead["id"]), reverse=True)
    closed = closed[:MEASURED_EPICS]
    if closed:
        days = sum(actual_days(bead, today) or 0 for bead in closed)
        return Pace(round(days / sum(points_of(bead) or 0 for bead in closed), 2), len(closed), False)
    return Pace(float(assumed), 0, True) if assumed else DEFAULT_PACE


def epic_days(epic: Mapping[str, Any], pace: Pace = DEFAULT_PACE) -> int | None:
    """Planned days: points times the pace, rounded up, at least 1; else the day estimate; else None."""
    points = points_of(epic)
    if points is not None:
        return max(1, math.ceil(round(points * pace.value, 6)))
    return estimate_days(epic.get("estimated_minutes"))


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


def _count(value: Any) -> int | None:
    text = str(value).strip() if value is not None and not isinstance(value, bool) else ""
    return int(text) if text.isascii() and text.isdigit() else None


def _rate(value: Any) -> float | None:
    try:
        number = float(str(value)) if value is not None and not isinstance(value, bool) else None
    except ValueError:
        return None
    return number if number is not None and math.isfinite(number) and number > 0 else None


def metadata_problems(milestone: Mapping[str, Any]) -> list[str]:
    """Names of the metadata keys (`away`, `integration`, `committed_points`, `planned_days_per_point`)
    that are present but unreadable; they are ignored."""
    meta = _meta(milestone)
    problems = []
    if meta.get("away") not in (None, "") and away_of(milestone) is None:
        problems.append("away")
    if meta.get("integration") and _integration(milestone) is None:
        problems.append("integration")
    if meta.get("committed_points") not in (None, "") and _count(meta.get("committed_points")) is None:
        problems.append("committed_points")
    if meta.get("planned_days_per_point") not in (None, "") and _rate(meta.get("planned_days_per_point")) is None:
        problems.append("planned_days_per_point")
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


def remaining_days(epic: Mapping[str, Any], beads: Beads, today: date, pace: Pace = DEFAULT_PACE) -> int | None:
    """Days left: the estimate for a not-started epic; for an in-progress one, the share of open child tracks,
    else the estimate minus the working days since `started_at`. At least 1; None when unestimated."""
    days = epic_days(epic, pace)
    if days is None or epic.get("status") != "in_progress":
        return days
    tracks = tracks_of([bead for bead in beads.values() if bead.get("parent") == epic["id"] and bead.get("issue_type") != "epic"])
    if tracks:
        still_open = sum(track.get("status") != "closed" for track in tracks)
        return max(1, math.ceil(days * still_open / len(tracks)))
    try:
        begun = parse_date(str(epic.get("started_at") or "")[:10])
    except ValueError:
        return days
    return max(1, days - _workdays_before(begun, today))


def _planned_days(epics: Mapping[str, Mapping[str, Any]], beads: Beads, today: date,
                  pace: Pace = DEFAULT_PACE) -> dict[str, int | None]:
    """Days each epic takes in the schedule: remaining days, else for an open unestimated epic the median
    estimate of the group's estimated, not-closed epics, rounded up (1 when none); a closed unestimated epic
    takes none."""
    known = [d for epic in epics.values()
             if epic.get("status") != "closed" and (d := epic_days(epic, pace)) is not None]
    assumed = math.ceil(statistics.median(known)) if known else 1
    planned: dict[str, int | None] = {}
    for epic_id, epic in epics.items():
        days = remaining_days(epic, beads, today, pace)
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
           off: Sequence[frozenset[date]] | None = None) -> dict[str, tuple[date, date, int | None]]:
    """Greedy placement on `lanes` lanes from the working day `first`: the ready epic with the earliest allowed
    start (ties by id) takes the lane that frees first. Epics whose days are None take no lane and no days.
    Returns (start, end, lane) per epic; lane counts from 1 and is None for an epic without days."""
    _check_cycles(epics)
    planned: dict[str, tuple[date, date, int | None]] = {}
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
                dep_start, dep_end, _ = planned[dep]
                estimated = days[dep] is not None
                begin = max(begin, _workday(dep_end + timedelta(days=1)) if estimated else dep_start)
            ready[epic_id] = begin
        epic_id = min(ready, key=lambda item: (ready[item], item))
        length = days[epic_id]
        if length is None:
            planned[epic_id] = (ready[epic_id], ready[epic_id], None)
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
        planned[epic_id] = (begin, end, lane + 1)
        free[lane] = _off(end + timedelta(days=1), lane_off)
    return planned


@dataclass(frozen=True)
class _Window:
    """What the warnings of an epic need from its milestone."""
    end: date
    active: bool
    kicked_off: bool
    spec_due: bool
    integration: date | None
    working_days: int


def _window(milestone: Mapping[str, Any], today: date) -> _Window:
    begin, end = period(milestone)
    state = status(milestone, today)
    return _Window(end=end, active=state == "active", kicked_off=state in ("scheduled", "active"),
                   spec_due=state == "planned" and begin <= _last_of(_workday(today), SPEC_DUE_DAYS),
                   integration=_integration(milestone),
                   working_days=_workdays_before(begin, end + timedelta(days=1)))


def _estimate_source(epic: Mapping[str, Any], planned_days: int | None, pace: Pace) -> str | None:
    if points_of(epic) is not None:
        return "points"
    if epic_days(epic, pace) is not None:
        return "days"
    return "assumed" if planned_days is not None else None


def _epic_warnings(epic: Mapping[str, Any], finish: date, group: Mapping[str, Any], beads: Beads,
                   window: _Window | None, today: date, planned_days: int | None, bugs: Mapping[str, int],
                   confirmed: frozenset[str] | None, pace: Pace) -> list[dict[str, Any]]:
    """Warnings of one placed epic, in `show` order. Without a milestone `window` only `unestimated`,
    `external_blocker`, and `open_bugs` apply."""
    still_open = epic.get("status") != "closed"
    warnings: list[dict[str, Any]] = []
    if window is not None and (overflow := workdays_after(window.end, finish)):
        warnings.append({"code": "overflow", "days": overflow})
    if window is not None and window.active and still_open and finish < today:
        warnings.append({"code": "late"})
    if epic_days(epic, pace) is None:
        warnings.append({"code": "unestimated"})
    if any(beads[dep].get("status") != "closed" for dep in _blocks(epic) if dep not in group and dep in beads):
        warnings.append({"code": "external_blocker"})
    if window is not None and confirmed is not None and still_open and epic["id"] not in confirmed:
        if window.kicked_off:
            warnings.append({"code": "spec_not_ready"})
        elif window.spec_due:
            warnings.append({"code": "spec_due"})
    if window is not None and window.integration and still_open and finish > window.integration:
        warnings.append({"code": "after_integration"})
    if bugs.get(epic["id"]):
        warnings.append({"code": "open_bugs", "count": bugs[epic["id"]]})
    if window is not None and still_open and planned_days is not None and planned_days > window.working_days:
        warnings.append({"code": "oversized", "days": planned_days - window.working_days})
    return warnings


def schedule(milestone: Mapping[str, Any], beads: Beads, start: date, today: date,
             default_lanes: int = 1, confirmed: frozenset[str] | None = None,
             builders: Sequence[str] = (), pace: Pace = DEFAULT_PACE) -> dict[str, Any]:
    _, end = period(milestone)
    epics = {epic["id"]: epic for epic in epics_of(milestone["id"], beads)}
    days_of = _planned_days(epics, beads, today, pace)
    planned = _place(epics, _workday(start), lanes_of(milestone, default_lanes), days_of,
                     _lane_off(milestone, builders))
    window = _window(milestone, today)
    bugs = _open_bugs(beads)
    rows = []
    for epic_id in sorted(epics, key=lambda item: (planned[item][0], item)):
        epic = epics[epic_id]
        begin, finish, _ = planned[epic_id]
        days = epic_days(epic, pace)
        points = points_of(epic)
        actual = actual_days(epic, today)
        outside = [beads[dep] for dep in _blocks(epic) if dep not in epics and dep in beads]
        rows.append({
            "id": epic_id, "title": epic.get("title", ""), "status": epic.get("status"), "estimate_days": days,
            "points": points, "points_reason": _meta(epic).get("points_reason") if points is not None else None,
            "estimate_source": _estimate_source(epic, days_of[epic_id], pace),
            "actual_days": actual,
            "actual_days_per_point": round(actual / points, 2) if actual is not None and points else None,
            "remaining_days": remaining_days(epic, beads, today, pace),
            "assumed_days": days_of[epic_id] if days is None else None,
            "spec_confirmed": None if confirmed is None else epic_id in confirmed,
            "planned_start": begin.isoformat(), "planned_end": finish.isoformat(),
            "depends_on": sorted(dep for dep in _blocks(epic) if dep in epics),
            "external_depends_on": [{"id": bead["id"], "milestone": _milestone_of(bead, beads)}
                                    for bead in sorted(outside, key=lambda bead: bead["id"])],
            "warnings": _epic_warnings(epic, finish, epics, beads, window, today, days_of[epic_id], bugs,
                                       confirmed, pace),
        })
    last = max((dates[1] for dates in planned.values()), default=None)
    return {"finish": last.isoformat() if last else None,
            "overflow_days": workdays_after(end, last) if last else 0, "epics": rows}


def _moved_in_after(epic: Mapping[str, Any], milestone_id: str, kickoff: date) -> bool:
    """The epic's latest move into `milestone_id` (its `milestone_moves`) is dated after `kickoff`."""
    stored = _meta(epic).get("milestone_moves")
    try:
        moves = json.loads(stored) if isinstance(stored, str) else list(stored or [])
    except (ValueError, TypeError):
        return False
    into = [move for move in moves if isinstance(move, Mapping) and move.get("to") == milestone_id]
    when = _day(into[-1].get("at")) if into else None
    return when is not None and when > kickoff


def velocity(milestone: Mapping[str, Any], beads: Beads, today: date) -> dict[str, Any]:
    """KPIs of one milestone: the kick-start snapshot against its closed epics with points."""
    meta = _meta(milestone)
    epics = epics_of(milestone["id"], beads)
    committed = _count(meta.get("committed_points"))
    planned = _rate(meta.get("planned_days_per_point"))
    closed = [epic for epic in epics if epic.get("status") == "closed" and points_of(epic) is not None]
    completed = sum(points_of(epic) or 0 for epic in closed)
    measured = [(points_of(epic) or 0, days) for epic in closed if (days := actual_days(epic, today)) is not None]
    pace = round(sum(d for _, d in measured) / sum(p for p, _ in measured), 2) if measured else None
    kickoff = _day(meta.get("kickoff"))
    added = sum(points_of(epic) or 0 for epic in epics
                if kickoff is not None and _moved_in_after(epic, milestone["id"], kickoff))
    return {"committed_points": committed, "completed_points": completed, "added_points": added,
            "say_do": round(completed / committed, 2) if committed else None,
            "days_per_point": pace, "planned_days_per_point": planned,
            "accuracy": round(planned / pace, 2) if planned and pace else None}


def show_payload(milestone: Mapping[str, Any], beads: Beads, start: date | None, today: date,
                 default_lanes: int = 1, confirmed: frozenset[str] | None = None,
                 deadline: date | None = None, builders: Sequence[str] = (),
                 pace: Pace = DEFAULT_PACE) -> dict[str, Any]:
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
            "days_per_point": pace.as_json(), "velocity": velocity(milestone, beads, today),
            **schedule(milestone, beads, schedule_start, today, default_lanes, confirmed, builders, pace=pace)}


def _open_roadmap_epics(beads: Beads) -> dict[str, Mapping[str, Any]]:
    """Roadmap epics the forecast plans: a `deferred` one is set aside in Beads, so it is left out like a closed one."""
    return {bead["id"]: bead for bead in beads.values()
            if bead.get("issue_type") == "epic" and "roadmap" in (bead.get("labels") or [])
            and bead.get("status") not in ("closed", "deferred")}


def forecast(beads: Beads, today: date, roadmap: Roadmap, default_lanes: int,
             builders: Sequence[str] = (), pace: Pace = DEFAULT_PACE,
             confirmed: frozenset[str] | None = None) -> dict[str, Any] | None:
    """When every open roadmap epic finishes: open milestones in `end` order on their own lanes, one after
    another, then the unassigned pool on `default_lanes`. `milestones` holds the chained dates of each open
    milestone and `epics` a row per placed epic. None when no roadmap epic is open. On a cycle or bad
    milestone metadata, `error` is set and `finish`, `milestones`, and `epics` cover only the groups placed
    before it."""
    epics = _open_roadmap_epics(beads)
    if not epics:
        return None
    milestones = sorted((bead for bead in beads.values()
                         if bead.get("issue_type") == "milestone" and bead.get("status") != "closed"),
                        key=lambda bead: (str(_meta(bead).get("end", "")), bead["id"]))
    result: dict[str, Any] = {
        "deadline": roadmap.deadline.isoformat() if roadmap.deadline else None, "lanes": default_lanes,
        "start": today.isoformat(), "finish": None, "overflow_days": 0, "open_epics": len(epics),
        "unestimated": sum(epic_days(epic, pace) is None for epic in epics.values()),
        "error": roadmap.error,
        "milestones": [{"id": m["id"], "start": None, "finish": None, "overflow_days": 0} for m in milestones],
        "epics": []}
    chained = {entry["id"]: entry for entry in result["milestones"]}
    groups: list[tuple[Mapping[str, Any] | None, dict[str, Mapping[str, Any]]]] = [
        (m, {k: v for k, v in epics.items() if v.get("parent") == m["id"]}) for m in milestones]
    owned = {k for _, group in groups for k in group}
    groups.append((None, {k: v for k, v in epics.items() if k not in owned}))
    bugs = _open_bugs(beads)
    cursor, ends = _workday(today), []
    try:
        for milestone, group in groups:
            if not group:
                continue
            off, window = None, None
            if milestone is None:
                first, lanes = cursor, default_lanes
            else:
                begin, end = period(milestone)
                meta = _meta(milestone)
                first = max(cursor, parse_date(meta["kickoff"]) if meta.get("kickoff") else begin)
                lanes = lanes_of(milestone, default_lanes)
                off = _lane_off(milestone, builders)
                window = _window(milestone, today)
            days_of = _planned_days(group, beads, today, pace)
            planned = _place(group, _workday(first), lanes, days_of, off)
            for epic_id, epic in group.items():
                placed_start, placed_end, lane = planned[epic_id]
                result["epics"].append({
                    "id": epic_id, "title": epic.get("title", ""), "status": epic.get("status"),
                    "milestone": milestone["id"] if milestone is not None else None, "lane": lane,
                    "planned_start": placed_start.isoformat(), "planned_end": placed_end.isoformat(),
                    "remaining_days": remaining_days(epic, beads, today, pace),
                    "estimate_source": _estimate_source(epic, days_of[epic_id], pace),
                    "warnings": _epic_warnings(epic, placed_end, group, beads, window, today, days_of[epic_id],
                                               bugs, confirmed, pace)})
            group_ends = [planned[k][1] for k in group if days_of[k] is not None]
            if group_ends:
                ends.append(max(group_ends))
                cursor = _workday(max(group_ends) + timedelta(days=1))
                if milestone is not None:
                    chained[milestone["id"]].update(start=_workday(first).isoformat(),
                                                    finish=max(group_ends).isoformat(),
                                                    overflow_days=workdays_after(end, max(group_ends)))
    except ValueError as error:  # CycleError and bad milestone metadata
        result["error"] = str(error)
    result["epics"].sort(key=lambda row: (row["planned_start"], row["id"]))
    if ends:
        finish = max(ends)
        result["finish"] = finish.isoformat()
        if roadmap.deadline:
            result["overflow_days"] = workdays_after(roadmap.deadline, finish)
    return result


def list_payload(beads: Beads, today: date, include_closed: bool, roadmap: Roadmap | None = None,
                 default_lanes: int = 1, confirmed: frozenset[str] | None = None,
                 builders: Sequence[str] = (), pace: Pace = DEFAULT_PACE) -> dict[str, Any]:
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
                 "warnings": None, "error": None, "velocity": velocity(milestone, beads, today)}
        try:
            entry["status"] = status(milestone, today)
            begin, _ = period(milestone)
            start = parse_date(meta["kickoff"]) if meta.get("kickoff") else begin
            plan = schedule(milestone, beads, start, today, default_lanes, confirmed, builders, pace=pace)
            entry["finish"] = plan["finish"]
            entry["warnings"] = sum(len(row["warnings"]) for row in plan["epics"])
        except ValueError as error:  # CycleError included
            entry["error"] = str(error)
        entries.append(entry)
    unassigned = sum(1 for bead in _open_roadmap_epics(beads).values() if not bead.get("parent"))
    return {"schema": SCHEMA, "milestones": entries, "unassigned_epics": unassigned, "today": today.isoformat(),
            "days_per_point": pace.as_json(),
            "forecast": forecast(beads, today, roadmap, default_lanes, builders, pace=pace, confirmed=confirmed)}
