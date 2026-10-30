"""`gin-workflow milestone`: dated milestones over roadmap epics. Exit 0 ok, 1 refused or failed, 2 usage or role."""

from __future__ import annotations

import argparse
from datetime import date
import json
import os
from pathlib import Path
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


def _run(args: argparse.Namespace) -> int:
    root = args.repository.resolve()
    _config(root)
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
    raise MilestoneError(f"{args.command} is not implemented")  # Track 2 replaces this line


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
