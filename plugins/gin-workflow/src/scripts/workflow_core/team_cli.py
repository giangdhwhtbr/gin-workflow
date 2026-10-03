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
    item = sub.add_parser("init", parents=[common])
    item.add_argument("--ci", action="store_true")
    item.add_argument("--force", action="store_true")
    sub.add_parser("codeowners", parents=[common]).add_argument("--check", action="store_true")
    sub.add_parser("hooks", parents=[common])
    sub.add_parser("whoami", parents=[common])
    item = sub.add_parser("check", parents=[common])
    item.add_argument("url")
    item.add_argument("--gate", required=True, choices=team_core.GATES)
    item.add_argument("--plan")
    sub.add_parser("check-plan", parents=[common]).add_argument("plan", type=Path)
    sub.add_parser("ready", parents=[common])
    sub.add_parser("claim", parents=[common]).add_argument("bead")
    sub.add_parser("deps", parents=[common])
    sub.add_parser("sync", parents=[common])
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
    if args.command in ("init", "codeowners", "hooks"):
        from . import team_init

        if args.command == "init":
            result = team_init.init(root, team, config, ci=args.ci, force=args.force)
            lines = [f"wrote {item}" for item in result["written"]]
            lines += [f"unchanged {item}" for item in result["unchanged"]]
            lines += [f"skipped {item} (no marker; --force overwrites)" for item in result["skipped"]]
            _emit(result, args.format, "\n".join(lines))
            return 0
        if args.command == "hooks":
            result = team_init.install_hook(root)
            _emit(result, args.format, f"{result['status']}: {result['path']}")
            return {"active": 0, "installed": 0, "missing": 2, "occupied": 1}[result["status"]]
        if args.check:
            drift = team_init.codeowners_drift(root, team, config)
            path = team_init.codeowners_path(team)
            return _findings([f"{path} is out of date; run gin-workflow team init"] if drift else [],
                             args.format, "ok")
        text = team_init.codeowners(team, config)
        _emit({"path": team_init.codeowners_path(team), "text": text}, args.format, text.rstrip("\n"))
        return 0
    if args.command == "check-plan":
        return _findings(team_core.check_plan(team, args.plan), args.format, "ok")
    if args.command == "check":
        pr, reasons = team_core.verify_gate(root, team, args.gate, args.url, plan=args.plan)
        payload = {"status": "rejected" if reasons else "ok", "gate": args.gate, "url": pr.url, "reasons": reasons,
                   "approvers": team_core.approver_payload(pr, team)}
        _emit(payload, args.format, "\n".join(reasons) if reasons else f"ok: {args.gate} {pr.url}")
        return 1 if reasons else 0
    member = team_core.require_member(root, team)
    if args.command == "whoami":
        payload = {"email": member.email, "login": member.login, "roles": list(member.roles),
                   "areas": team.areas_for(member)}
        _emit(payload, args.format, f"{member.email} ({member.login}) roles: {', '.join(member.roles)}; "
                                    f"areas: {', '.join(payload['areas']) or '-'}")
        return 0
    from . import team_beads

    try:
        if args.command == "ready":
            rows = team_beads.ready(root, team, member)
            _emit({"ready": rows}, args.format, "\n".join(f"{row['id']} {row['title']}" for row in rows))
            return 0
        if args.command == "claim":
            result = team_beads.claim(root, team, member, args.bead)
            _emit(result, args.format, f"claimed {args.bead}")
            return 0
        if args.command == "deps":
            result = team_beads.deps(root, team)
            lines = [f"closed {row['id']} ({row['pr']})" for row in result["closed"]]
            lines += [f"waiting {item}" for item in result["waiting"]]
            _emit(result, args.format, "\n".join(lines) or "no external placeholders")
            return 0
        if not team.beads_remote:
            raise team_core.TeamError("team.beads_sync.remote is not set")
        _emit(team_beads.sync(root), args.format, "synced")
        return 0
    except team_beads.SyncConflict as conflict:
        _emit({"status": "conflict", "message": str(conflict)}, args.format, f"conflict: {conflict}")
        return 1


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
