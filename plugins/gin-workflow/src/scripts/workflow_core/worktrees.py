"""`gin worktree`: create and remove track worktrees under `.planning/worktrees` of the repository, or of the workspace for a child repository."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess
import sys
from typing import Sequence

from . import workspace

_TRACK_ID = re.compile(r"[A-Za-z0-9._-]+")


def _git(repo: Path, *argv: str) -> str:
    completed = subprocess.run(["git", *argv], cwd=repo, text=True, capture_output=True, check=False)
    if completed.returncode:
        raise RuntimeError(completed.stderr.strip() or f"git {argv[0]} failed")
    return completed.stdout.strip()


def _target(repo: Path, track_id: str, root: Path | None = None) -> Path:
    if not _TRACK_ID.fullmatch(track_id):
        raise ValueError(f"invalid track-id '{track_id}'")
    top = root if root is not None else Path(_git(repo, "rev-parse", "--show-toplevel"))
    base_dir = (top / ".planning/worktrees").resolve()
    target = (base_dir / track_id).resolve()
    if target.parent != base_dir:
        raise ValueError("resolved path escapes worktree root")
    return target


def create(repo: Path, track_id: str, branch: str, base_ref: str | None = None, root: Path | None = None) -> Path:
    """New branch `branch` checked out at `.planning/worktrees/<track_id>`, from `base_ref` or the current branch."""
    target = _target(repo, track_id, root)
    if target.exists():
        raise ValueError(f"directory {target} already exists")
    if not branch.strip():
        raise ValueError("branch is required")
    base = base_ref or _git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    _git(repo, "worktree", "add", "-b", branch, "--", str(target), base)
    return target


def checkout(repo: Path, track_id: str, branch: str, root: Path | None = None) -> Path:
    """Existing branch `branch` checked out at `.planning/worktrees/<track_id>`; a branch that exists only on origin is created tracking it."""
    target = _target(repo, track_id, root)
    if target.exists():
        raise ValueError(f"directory {target} already exists")
    if not branch.strip():
        raise ValueError("branch is required")
    if _git(repo, "branch", "--list", branch):
        _git(repo, "worktree", "add", "--", str(target), branch)
    elif _git(repo, "branch", "-r", "--list", f"origin/{branch}"):
        _git(repo, "worktree", "add", "--track", "-b", branch, "--", str(target), f"origin/{branch}")
    else:
        raise ValueError(f"branch {branch} does not exist locally or on origin")
    return target


def cleanup(repo: Path, track_id: str, root: Path | None = None) -> Path | None:
    """Remove the track's worktree; None when it does not exist."""
    target = _target(repo, track_id, root)
    if not target.exists():
        return None
    _git(repo, "worktree", "remove", str(target))
    return target


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="gin worktree")
    commands = parser.add_subparsers(dest="command", required=True)
    create_parser = commands.add_parser("create")
    create_parser.add_argument("--repository", default=".")
    create_parser.add_argument("track_id")
    create_parser.add_argument("branch")
    create_parser.add_argument("base_ref", nargs="?")
    checkout_parser = commands.add_parser("checkout")
    checkout_parser.add_argument("--repository", default=".")
    checkout_parser.add_argument("track_id")
    checkout_parser.add_argument("branch")
    cleanup_parser = commands.add_parser("cleanup")
    cleanup_parser.add_argument("--repository", default=".")
    cleanup_parser.add_argument("track_id")
    args = parser.parse_args(list(argv))
    repo = Path(args.repository)
    try:
        located = workspace.locate(repo)
        root = located.root if located.entry is not None else None
        if args.command == "create":
            path = create(repo, args.track_id, args.branch, args.base_ref, root=root)
            print(f"Worktree created at: {path} on branch {args.branch}")
        elif args.command == "checkout":
            path = checkout(repo, args.track_id, args.branch, root=root)
            print(f"Worktree created at: {path} on branch {args.branch}")
        elif (removed := cleanup(repo, args.track_id, root=root)) is None:
            print(f"No worktree for {args.track_id}; nothing to remove.")
        else:
            print(f"Worktree {removed} removed.")
    except (ValueError, RuntimeError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0
