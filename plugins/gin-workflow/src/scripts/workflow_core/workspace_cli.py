"""`gin workspace`: clone the manifest's repositories and show their state."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Sequence

from . import workspace as ws


def _run_git(argv: Sequence[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *argv], cwd=cwd, text=True, capture_output=True, check=False)


def clone(space: ws.Workspace, paths: Sequence[str], all_repos: bool) -> list[dict[str, Any]]:
    chosen = list(space.repos) if all_repos else [space.repo(path) for path in paths]
    if any(repo is None for repo in chosen):
        missing = [path for path, repo in zip(paths, chosen) if repo is None]
        raise ws.WorkspaceError(f"not in workspace.repos: {', '.join(missing)}")
    if not chosen:
        raise ws.WorkspaceError("name a repository path or pass --all")
    results: list[dict[str, Any]] = []
    try:
        for repo in chosen:
            target = space.checkout(repo)
            if space.present(repo):
                results.append({"path": repo.path, "status": "present"})
                continue
            argv = ["clone", "--branch", repo.default_branch, *(["--depth", "1"] if repo.frozen else []),
                    repo.url, str(target)]
            done = _run_git(argv)
            if done.returncode:
                cloned = [row["path"] for row in results if row["status"] == "cloned"]
                so_far = f" (cloned so far: {', '.join(cloned)})" if cloned else ""
                raise ws.WorkspaceError(f"{repo.path}: {done.stderr.strip() or 'git clone failed'}{so_far}")
            results.append({"path": repo.path, "status": "cloned"})
    finally:
        ws.ensure_gitignore(space.root, [f"/{row['path']}" for row in results])
    return results


def status(space: ws.Workspace) -> list[dict[str, Any]]:
    rows = []
    for repo in space.repos:
        present = space.present(repo)
        dirty = None
        if present:
            porcelain = _run_git(["status", "--porcelain"], space.checkout(repo))
            dirty = bool(porcelain.stdout.strip()) if porcelain.returncode == 0 else None
        rows.append({"path": repo.path, "present": present,
                     "branch": ws.branch(space.checkout(repo)) if present else None,
                     "dirty": dirty, "frozen": repo.frozen})
    return rows


def _text(rows: list[dict[str, Any]]) -> str:
    width = max(len(row["path"]) for row in rows)
    lines = []
    for row in rows:
        state = "present" if row["present"] else "missing"
        tree = "" if row["dirty"] is None else ("dirty" if row["dirty"] else "clean")
        lines.append("  ".join(part for part in (row["path"].ljust(width), state, row["branch"] or "", tree,
                                                 "frozen" if row["frozen"] else "") if part))
    return "\n".join(lines)


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="gin workspace",
                                     description="clone the repositories of workspace.repos and show their state")
    commands = parser.add_subparsers(dest="command", required=True)
    clone_parser = commands.add_parser(
        "clone", help="clone the named entries, or every entry with --all, at their manifest paths",
        description="clone the named entries, or every entry with --all, at their manifest paths; "
                    "an entry already present is reported as present; each path is added to the parent .gitignore")
    clone_parser.add_argument("paths", nargs="*", help="manifest paths to clone")
    clone_parser.add_argument("--all", dest="all_repos", action="store_true", help="every entry of workspace.repos")
    status_parser = commands.add_parser(
        "status", help="one line per entry: path, present or missing, branch, clean or dirty, frozen",
        description="one line per entry: path, present or missing, branch, clean or dirty, frozen")
    for sub in (clone_parser, status_parser):
        sub.add_argument("--repository", type=Path, default=None,
                         help="a directory inside the workspace (default: the current directory)")
        sub.add_argument("--json", dest="as_json", action="store_true", help="print JSON instead of text")
    args = parser.parse_args(list(argv))
    start = args.repository if args.repository is not None else Path.cwd()
    try:
        located = ws.locate(start)
        if located.workspace is None:
            raise ws.WorkspaceError(f"not in a workspace: {Path(start).resolve()}")
        if args.command == "clone":
            rows = clone(located.workspace, args.paths, args.all_repos)
            print(json.dumps({"repos": rows}) if args.as_json else
                  "\n".join(f"{row['path']}: {row['status']}" for row in rows))
        else:
            rows = status(located.workspace)
            print(json.dumps({"repos": rows}) if args.as_json else _text(rows))
    except (ws.WorkspaceError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0
