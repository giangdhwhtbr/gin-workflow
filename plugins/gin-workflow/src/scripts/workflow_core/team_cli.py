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
    return parser


def _emit(payload: dict[str, Any], output_format: str, text: str) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True) if output_format == "json" else text)


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
    member = team_core.require_member(root, team)
    payload = {"email": member.email, "login": member.login, "roles": list(member.roles),
               "areas": team.areas_for(member)}
    _emit(payload, args.format, f"{member.email} ({member.login}) roles: {', '.join(member.roles)}; "
                                f"areas: {', '.join(payload['areas']) or '-'}")
    return 0


def main(arguments: Sequence[str]) -> int:
    try:
        args = _parser().parse_args(list(arguments))
    except SystemExit as error:
        return error.code if isinstance(error.code, int) else 2
    try:
        return _run(args)
    except (team_core.TeamError, ValueError) as error:
        print(f"team error: {error}", file=sys.stderr)
        return 2
