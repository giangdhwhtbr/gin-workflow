"""`gin team` command line: exit 0 ok, 1 findings or rejection, 2 usage, configuration, or host error."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Sequence

from . import team as team_core, workspace
from .hosts import adapter


def _parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--repository", type=Path, default=None)
    common.add_argument("--format", choices=("text", "json"), default="text")
    parser = argparse.ArgumentParser(prog="gin team")
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
    item.add_argument("--spec")
    item.add_argument("--workflow-id", help="the epic bead whose kind: label picks the requirement_confirmed policy")
    sub.add_parser("check-plan", parents=[common]).add_argument("plan", type=Path)
    item = sub.add_parser("pending", parents=[common])
    group = item.add_mutually_exclusive_group()
    group.add_argument("--workflow-id")
    group.add_argument("--milestone")
    item = sub.add_parser("ready", parents=[common])
    item.add_argument("--exclude-label", action="append")
    sub.add_parser("claim", parents=[common]).add_argument("bead")
    item = sub.add_parser("reassign", parents=[common])
    item.add_argument("bead")
    item.add_argument("email")
    item = sub.add_parser("handoff", parents=[common])
    item.add_argument("bead")
    item.add_argument("email", nargs="?")
    item.add_argument("--release", action="store_true")
    item.add_argument("--worktree")
    item = sub.add_parser("takeover", parents=[common])
    item.add_argument("bead")
    item.add_argument("--branch")
    sub.add_parser("deps", parents=[common]).add_argument("--bead")
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
        raise team_core.TeamError("gin setup is required; run /setup once")
    config = resolve_effective_config(root, write=False).config.to_dict()
    team = team_core.load_team(config)
    if team is None:
        raise team_core.TeamError("team mode is off: add team: to .agent-workflow/config.yaml "
                                  "(/gin:team-setup)")
    if args.command in ("init", "codeowners", "hooks"):
        from . import team_init

        if args.command == "init":
            result = team_init.init(root, team, config, ci=args.ci, force=args.force)
            lines = [f"wrote {item}" for item in result["written"]]
            lines += [f"unchanged {item}" for item in result["unchanged"]]
            lines += [f"skipped {item} (no marker; --force overwrites)" for item in result["skipped"]]
            gap = team_init.gate_policy_gap(team)
            if gap:
                lines.append(f"warning: gates without a role policy: {', '.join(gap)} (set team.approvals.<gate>, "
                             "or team.strict: true to require one)")
            _emit({**result, "warnings": gap}, args.format, "\n".join(lines))
            return 0
        if args.command == "hooks":
            result = team_init.install_hook(root)
            _emit(result, args.format, f"{result['status']}: {result['path']}")
            return {"active": 0, "installed": 0, "missing": 2, "occupied": 1}[result["status"]]
        if args.check:
            drift = team_init.codeowners_drift(root, team, config)
            path = team_init.codeowners_path(team)
            return _findings([f"{path} is out of date; run gin team init"] if drift else [],
                             args.format, "ok")
        if team_init.codeowners_path(team) is None:
            raise team_core.TeamError(f"team.host {team.host} has no CODEOWNERS file")
        text = team_init.codeowners(team, config)
        _emit({"path": team_init.codeowners_path(team), "text": text}, args.format, text.rstrip("\n"))
        return 0
    if args.command == "check-plan":
        findings = team_core.check_plan(team, args.plan)
        located = workspace.locate(args.repository)
        if located.workspace is not None:
            findings += team_core.check_plan_repos(located.workspace, args.plan)
        return _findings(findings, args.format, "ok")
    if args.command == "check":
        notes: list[str] = []
        pr, artifact, reasons, kind = team_core.verify_gate(root, team, args.gate, args.url, plan=args.plan,
                                                            spec=args.spec, notes=notes, workflow_id=args.workflow_id)
        key = adapter(team.host).identity_key
        for member in team.members.values():
            if not getattr(member, key):
                print(f"warning: {member.email} has no {key}; its approvals cannot be matched", file=sys.stderr)
        payload = {"status": "rejected" if reasons else "ok", "gate": args.gate, "url": pr.url, "reasons": reasons,
                   "approvers": team_core.approver_payload(pr, team, on_commit=pr.head_sha if args.gate == "ship" else None),
                   "artifact": artifact, "notes": notes, "kind": kind}
        _emit(payload, args.format, "\n".join([*(f"note: {note}" for note in notes),
                                               *(reasons or [f"ok: {args.gate} {pr.url}"])]))
        return 1 if reasons else 0
    if args.command == "pending":
        from . import team_pending

        rows = team_pending.pending(root, team, workflow_id=args.workflow_id, milestone=args.milestone)
        _emit({"pending": rows}, args.format, "\n".join(
            f"{row['gate'] or 'track'} {row['url'] or row['branch']} {row['epic'] or '-'} "
            f"missing: {', '.join(row['missing']) or '-'}" + (f" (error: {row['error']})" if "error" in row else "")
            for row in rows))
        return 0
    member = team_core.require_member(root, team)
    if args.command == "whoami":
        payload = {"email": member.email, "login": member.login, "roles": list(member.roles),
                   "areas": team.areas_for(member), "technical": team.technical(member)}
        _emit(payload, args.format, f"{member.email} ({member.login}) roles: {', '.join(member.roles)}; "
                                    f"areas: {', '.join(payload['areas']) or '-'}; "
                                    f"technical: {'yes' if payload['technical'] else 'no'}")
        return 0
    from . import team_beads

    try:
        if args.command == "ready":
            rows = team_beads.ready(root, team, member, exclude=args.exclude_label or ())
            _emit({"ready": rows}, args.format, "\n".join(
                f"{row['id']} {row['title']}" + (f" (expired claim: {row['expired_claim']})" if row.get("expired_claim") else "")
                for row in rows))
            return 0
        if args.command == "claim":
            result = team_beads.claim(root, team, member, args.bead)
            _emit(result, args.format, f"{result['status']} {args.bead}"
                  + (" (advisory: no Beads remote, teammates cannot see this claim)" if result["advisory"] else ""))
            return 0
        if args.command == "reassign":
            result = team_beads.reassign(root, team, member, args.bead, args.email)
            _emit(result, args.format, f"reassigned {args.bead} to {result['assignee']}")
            return 0
        if args.command == "handoff":
            if bool(args.email) == args.release:
                raise team_core.TeamError("pass exactly one of <email> or --release")
            result = team_beads.handoff(root, team, member, args.bead, email=args.email, release=args.release,
                                        worktree=args.worktree)
            _emit(result, args.format, f"{result['status']} {args.bead} on {result['branch']}"
                  + (f" -> {result['assignee']}" if result.get("assignee") else ""))
            return 0
        if args.command == "takeover":
            result = team_beads.takeover(root, team, member, args.bead, branch=args.branch)
            _emit(result, args.format, f"{result['status']} {args.bead} at {result['worktree']} on {result['branch']}")
            return 0
        if args.command == "deps" and args.bead:
            result = team_beads.deps_for(root, args.bead)
            lines = [f"ok {item}" for item in result["ok"]]
            lines += [f"missing {row['id']}: {row['reason']}" for row in result["missing"]]
            _emit(result, args.format, "\n".join(lines) or f"{args.bead} has no external dependencies")
            return 1 if result["missing"] else 0
        if args.command == "deps":
            result = team_beads.deps(root, team)
            lines = [f"closed {row['id']} ({row['pr']})" for row in result["closed"]]
            lines += [f"waiting {item}" for item in result["waiting"]]
            lines += [f"unresolved {row['id']}: {row['pr']} merged without a merge commit" for row in result["unresolved"]]
            _emit(result, args.format, "\n".join(lines) or "no external placeholders")
            return 1 if result["unresolved"] else 0
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
    args.repository = workspace.repository_root(args.repository)
    try:
        return _run(args)
    except (team_core.TeamError, HostUnavailable, ValueError) as error:
        print(f"team error: {error}", file=sys.stderr)
        return 2
