"""`gin-workflow team` command line: exit 0 ok, 1 findings or rejection, 2 usage, configuration, or host error."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Sequence

from . import team as team_core


def _parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--repository", type=Path, default=Path.cwd())
    common.add_argument("--format", choices=("text", "json"), default="text")
    parser = argparse.ArgumentParser(prog="gin-workflow team")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("whoami", parents=[common])
    item = sub.add_parser("check", parents=[common])
    item.add_argument("url")
    item.add_argument("--gate", required=True, choices=team_core.GATES)
    item.add_argument("--plan")
    sub.add_parser("check-plan", parents=[common]).add_argument("plan", type=Path)
    return parser


def _emit(payload: dict[str, Any], output_format: str, text: str) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True) if output_format == "json" else text)


def _findings(errors: list[str], output_format: str, ok: str) -> int:
    _emit({"status": "findings" if errors else "ok", "findings": errors}, output_format,
          "\n".join(errors) if errors else ok)
    return 1 if errors else 0


def _run(args: argparse.Namespace) -> int:
    from .configuration import resolve_effective_config

    root = args.repository.resolve()
    if not (root / ".agent-workflow/config.yaml").is_file():
        raise team_core.TeamError("gin-workflow setup is required; run /setup once")
    config = resolve_effective_config(root, write=False).config.to_dict()
    team = team_core.load_team(config)
    if team is None:
        raise team_core.TeamError("team mode is off: add team: to .agent-workflow/config.yaml "
                                  "(/gin-workflow:team-setup)")
    if args.command == "check-plan":
        return _findings(team_core.check_plan(team, args.plan), args.format, "ok")
    if args.command == "check":
        pr, reasons = team_core.verify_gate(root, team, args.gate, args.url, plan=args.plan)
        payload = {"status": "rejected" if reasons else "ok", "gate": args.gate, "url": pr.url, "reasons": reasons,
                   "approvers": team_core.approver_payload(pr, team)}
        _emit(payload, args.format, "\n".join(reasons) if reasons else f"ok: {args.gate} {pr.url}")
        return 1 if reasons else 0
    member = team_core.require_member(root, team)
    payload = {"email": member.email, "login": member.login, "roles": list(member.roles),
               "areas": team.areas_for(member)}
    _emit(payload, args.format, f"{member.email} ({member.login}) roles: {', '.join(member.roles)}; "
                                f"areas: {', '.join(payload['areas']) or '-'}")
    return 0


def main(arguments: Sequence[str]) -> int:
    from .team_host import HostUnavailable

    try:
        args = _parser().parse_args(list(arguments))
    except SystemExit as error:
        return error.code if isinstance(error.code, int) else 2
    try:
        return _run(args)
    except (team_core.TeamError, HostUnavailable, ValueError) as error:
        print(f"team error: {error}", file=sys.stderr)
        return 2
