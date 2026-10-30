"""`gin-workflow milestone`: dated milestones over roadmap epics. Exit 0 ok, 1 refused or failed, 2 usage or role."""

from __future__ import annotations

import argparse
from datetime import date
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any, Sequence

from . import milestone as core


class MilestoneError(Exception):
    """Refused or failed request: exit 1."""


def _today() -> date:
    return date.today()


def _parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--repository", type=Path, default=Path.cwd())
    parser = argparse.ArgumentParser(prog="gin-workflow milestone")
    sub = parser.add_subparsers(dest="command", required=True)
    item = sub.add_parser("create", parents=[common])
    item.add_argument("title")
    item.add_argument("--start", required=True)
    item.add_argument("--end", required=True)
    item = sub.add_parser("update", parents=[common])
    item.add_argument("id")
    item.add_argument("--title")
    item.add_argument("--start")
    item.add_argument("--end")
    item = sub.add_parser("kickstart", parents=[common])
    item.add_argument("id")
    item.add_argument("--date")
    item = sub.add_parser("move", parents=[common])
    item.add_argument("epics", nargs="+")
    item.add_argument("--to", required=True)
    item = sub.add_parser("estimate", parents=[common])
    item.add_argument("epic")
    item.add_argument("days")
    sub.add_parser("close", parents=[common]).add_argument("id")
    item = sub.add_parser("list", parents=[common])
    item.add_argument("--all", action="store_true")
    item.add_argument("--json", action="store_true")
    item = sub.add_parser("show", parents=[common])
    item.add_argument("id")
    item.add_argument("--start")
    item.add_argument("--json", action="store_true")
    return parser


def _config(root: Path) -> dict[str, Any]:
    from .configuration import resolve_effective_config
    from .tasks import backend_name

    if not (root / ".agent-workflow/config.yaml").is_file():
        raise MilestoneError("gin-workflow setup is required; run /setup once")
    config = resolve_effective_config(root, write=False).config.to_dict()
    if backend_name(config) != "beads":
        raise MilestoneError("milestones need providers.task_tracking: beads")
    return config


def _bd(root: Path, argv: list[str], actor: str = "") -> str:
    executable = shutil.which("bd")
    if executable is None:
        raise MilestoneError("bd is not installed")
    env = {**os.environ, "BD_ACTOR": actor} if actor else None
    done = subprocess.run([executable, *argv], cwd=root, text=True, capture_output=True, check=False,
                          env=env, stdin=subprocess.DEVNULL, timeout=120)
    if done.returncode != 0:
        raise MilestoneError(f"bd {argv[0]} failed: {(done.stderr or done.stdout).strip()}")
    return done.stdout


def _beads(root: Path) -> dict[str, dict[str, Any]]:
    rows = json.JSONDecoder().raw_decode(_bd(root, ["list", "--all", "--limit", "0", "--json"]).lstrip())[0]
    return {row["id"]: row for row in rows}


def _milestone(beads: dict[str, dict[str, Any]], bead_id: str) -> dict[str, Any]:
    bead = beads.get(bead_id)
    if bead is None:
        raise MilestoneError(f"{bead_id} not found")
    if bead.get("issue_type") != "milestone":
        raise MilestoneError(f"{bead_id} is not a milestone")
    return bead


def _date(text: str) -> date:
    try:
        return core.parse_date(text)
    except ValueError as error:
        raise MilestoneError(str(error)) from None


def _list_text(payload: dict[str, Any]) -> str:
    lines = []
    for entry in payload["milestones"]:
        detail = (f"error: {entry['error']}" if entry["error"] else
                  f"epics {entry['epics']['closed']}/{entry['epics']['total']}  warnings {entry['warnings']}")
        lines.append(f"{entry['id']}  {entry['status']:<9} {entry['start']}..{entry['end']}  {detail}")
    lines.append(f"unassigned roadmap epics: {payload['unassigned_epics']}")
    return "\n".join(lines)


def _show_text(payload: dict[str, Any]) -> str:
    lines = [f"{payload['id']} {payload['title']} [{payload['status']}] {payload['start']}..{payload['end']}, "
             f"schedule from {payload['schedule_start']}{' (preview)' if payload['preview'] else ''}"]
    for row in payload["epics"]:
        codes = ",".join(warning["code"] for warning in row["warnings"])
        days = row["estimate_days"] if row["estimate_days"] is not None else "-"
        lines.append(f"  {row['id']} {row['planned_start']}..{row['planned_end']} {days}d {codes}".rstrip())
    lines.append(f"finish {payload['finish'] or '-'}, overflow {payload['overflow_days']} working days")
    return "\n".join(lines)


def _open(beads: dict[str, dict[str, Any]], bead_id: str) -> dict[str, Any]:
    bead = _milestone(beads, bead_id)
    if bead.get("status") == "closed":
        raise MilestoneError(f"{bead_id} is closed")
    return bead


def _check_period(start: date, end: date) -> None:
    if start > end:
        raise MilestoneError(f"start {start.isoformat()} is after end {end.isoformat()}")


def _create(root: Path, args: argparse.Namespace, beads: dict[str, dict[str, Any]], actor: str) -> tuple[str, str]:
    start, end = _date(args.start), _date(args.end)
    _check_period(start, end)
    meta = json.dumps({"start": start.isoformat(), "end": end.isoformat()})
    out = _bd(root, ["create", args.title, "--type", "milestone", "--metadata", meta, "--json"], actor)
    return json.JSONDecoder().raw_decode(out.lstrip())[0]["id"], "milestone"


def _update(root: Path, args: argparse.Namespace, beads: dict[str, dict[str, Any]], actor: str) -> tuple[str, str]:
    start, end = core.period(_open(beads, args.id))
    start, end = (_date(args.start) if args.start else start), (_date(args.end) if args.end else end)
    _check_period(start, end)
    argv = ["update", args.id, "--set-metadata", f"start={start.isoformat()}",
            "--set-metadata", f"end={end.isoformat()}"] + (["--title", args.title] if args.title else [])
    _bd(root, argv, actor)
    return f"updated {args.id}", "update"


def _kickstart(root: Path, args: argparse.Namespace, beads: dict[str, dict[str, Any]], actor: str) -> tuple[str, str]:
    _open(beads, args.id)
    day = _date(args.date) if args.date else _today()
    _bd(root, ["update", args.id, "--set-metadata", f"kickoff={day.isoformat()}"], actor)
    return f"kickoff of {args.id} set to {day.isoformat()}", "kickoff"


def _move(root: Path, args: argparse.Namespace, beads: dict[str, dict[str, Any]], actor: str) -> tuple[str, str]:
    if args.to != "none":
        _open(beads, args.to)
    for epic in args.epics:
        bead = beads.get(epic)
        if bead is None:
            raise MilestoneError(f"{epic} not found")
        if bead.get("issue_type") != "epic":
            raise MilestoneError(f"{epic} is not an epic")
        parent = bead.get("parent")
        if parent and beads.get(parent, {}).get("issue_type") != "milestone":
            raise MilestoneError(f"{epic} is under {parent}, which is not a milestone")
        if parent and beads[parent].get("status") == "closed":
            raise MilestoneError(f"{epic} is in closed milestone {parent}")
    done: list[str] = []
    for epic in args.epics:
        try:
            _bd(root, ["update", epic, "--parent", "" if args.to == "none" else args.to], actor)
        except MilestoneError as error:
            raise MilestoneError(f"moved {', '.join(done) or 'none'}; {epic} failed: {error}") from None
        done.append(epic)
    return f"moved {', '.join(args.epics)} to {args.to}", "membership"


def _estimate(root: Path, args: argparse.Namespace, beads: dict[str, dict[str, Any]], actor: str) -> tuple[str, str]:
    if not re.fullmatch(r"[1-9][0-9]*", args.days):
        raise MilestoneError("estimate must be a positive whole number of working days")
    bead = beads.get(args.epic)
    if bead is None:
        raise MilestoneError(f"{args.epic} not found")
    if bead.get("issue_type") != "epic":
        raise MilestoneError(f"{args.epic} is not an epic")
    _bd(root, ["update", args.epic, "--estimate", str(int(args.days) * core.WORKDAY_MINUTES)], actor)
    return f"estimate of {args.epic} set to {args.days} working days", "estimate"


def _close(root: Path, args: argparse.Namespace, beads: dict[str, dict[str, Any]], actor: str) -> tuple[str, str]:
    _open(beads, args.id)
    open_epics = sorted(e["id"] for e in core.epics_of(args.id, beads) if e.get("status") != "closed")
    if open_epics:
        raise MilestoneError("open epics: " + ", ".join(open_epics))
    _bd(root, ["close", args.id], actor)
    return f"closed {args.id}", "close"


WRITES = {"create": _create, "update": _update, "kickstart": _kickstart, "move": _move,
          "estimate": _estimate, "close": _close}


def _write(root: Path, config: dict[str, Any], args: argparse.Namespace) -> int:
    text, _change = WRITES[args.command](root, args, _beads(root), "")
    print(text)
    return 0


def _run(args: argparse.Namespace) -> int:
    root = args.repository.resolve()
    config = _config(root)
    if args.command == "list":
        payload = core.list_payload(_beads(root), _today(), args.all)
        print(json.dumps(payload, indent=2) if args.json else _list_text(payload))
        return 0
    if args.command == "show":
        beads = _beads(root)
        start = _date(args.start) if args.start else None
        payload = core.show_payload(_milestone(beads, args.id), beads, start, _today())
        print(json.dumps(payload, indent=2) if args.json else _show_text(payload))
        return 0
    return _write(root, config, args)


def main(arguments: Sequence[str]) -> int:
    from .configuration import ConfigValidationError

    try:
        args = _parser().parse_args(list(arguments))
    except SystemExit as error:
        return error.code if isinstance(error.code, int) else 2
    try:
        return _run(args)
    except (MilestoneError, ConfigValidationError, ValueError) as error:  # ValueError: CycleError, bad metadata
        print(f"milestone error: {error}", file=sys.stderr)
        return 1
