"""`gin points`: story points of any open epic. Exit 0 ok, 1 refused or failed, 2 usage or role."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

from . import milestone as core, milestone_cli, workspace
from .milestone_cli import Denied, MilestoneError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gin points")
    parser.add_argument("epic")
    parser.add_argument("n")
    parser.add_argument("--reason", required=True)
    parser.add_argument("--stage", choices=("roadmap", "discuss", "close"), default="roadmap")
    parser.add_argument("--repository", type=Path, default=None)
    return parser


def _trace_points(root: Path, bead: Mapping[str, Any], epic: str, to: int, stage: str, actor: str) -> None:
    """Append {from, to, at, actor, stage} to the epic's `points_history`; a failure warns, never rolls back."""
    try:
        metadata = bead.get("metadata")
        stored = metadata.get("points_history") if isinstance(metadata, Mapping) else None
        history = json.loads(stored) if isinstance(stored, str) else list(stored or [])
        history.append({"from": core.points_of(bead), "to": to, "stage": stage,
                        "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "actor": actor or "unknown"})
        milestone_cli._bd(root, ["update", epic, "--set-metadata", f"points_history={json.dumps(history)}"], actor)
    except (MilestoneError, ValueError, TypeError, AttributeError) as error:
        print(f"warning: points of {epic} set but points_history not recorded: {error}", file=sys.stderr)


def _points(root: Path, args: argparse.Namespace, beads: dict[str, dict[str, Any]], actor: str) -> tuple[str, str]:
    if not (args.n.isascii() and args.n.isdigit()) or int(args.n) not in core.POINT_SCALE:
        raise MilestoneError("points must be one of " + ", ".join(map(str, core.POINT_SCALE)))
    if not args.reason.strip():
        raise MilestoneError("--reason must not be empty")
    bead = beads.get(args.epic)
    if bead is None:
        raise MilestoneError(f"{args.epic} not found")
    if bead.get("issue_type") != "epic":
        raise MilestoneError(f"{args.epic} is not an epic")
    if bead.get("status") == "closed":
        raise MilestoneError(f"{args.epic} is closed")
    parent = beads.get(bead.get("parent") or "") or {}
    meta = parent.get("metadata") if isinstance(parent.get("metadata"), Mapping) else {}
    if parent.get("issue_type") == "milestone" and meta.get("kickoff") and args.stage != "close":
        raise MilestoneError(f"points of {args.epic} are locked since the kick-start of {parent['id']}; "
                             "change them through /milestone-close")
    milestone_cli._bd(root, ["update", args.epic, "--set-metadata", f"points={int(args.n)}",
                             "--set-metadata", f"points_reason={args.reason}"], actor)
    _trace_points(root, bead, args.epic, int(args.n), args.stage, actor)
    return f"points of {args.epic} set to {int(args.n)}", "points"


def main(arguments: Sequence[str]) -> int:
    from .configuration import ConfigValidationError

    try:
        args = _parser().parse_args(list(arguments))
    except SystemExit as error:
        return error.code if isinstance(error.code, int) else 2
    args.repository = workspace.repository_root(args.repository)
    try:
        root = args.repository.resolve()
        return milestone_cli._write(root, milestone_cli._config(root), args, _points)
    except Denied as error:
        print(f"points error: {error}", file=sys.stderr)
        return 2
    except (MilestoneError, ConfigValidationError, ValueError) as error:
        print(f"points error: {error}", file=sys.stderr)
        return 1
