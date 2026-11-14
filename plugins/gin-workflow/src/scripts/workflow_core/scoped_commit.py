"""`gin commit`: scoped commit for BA and tester output.

Commits only the named paths, creates a branch when on a default branch,
and never pushes.
"""

from __future__ import annotations

import argparse
from datetime import date
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Sequence

from . import workspace


class ScopedCommitError(Exception):
    """Raised when a scoped commit is refused or fails."""

    def __init__(self, message: str, returncode: int = 2) -> None:
        super().__init__(message)
        self.returncode = returncode


def _branch_exists(repo: Path, name: str) -> bool:
    proc = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", f"refs/heads/{name}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode == 0


def _resolve_repo_for_path(cwd: Path, path_str: str) -> tuple[Path, Path]:
    """Return (target_path, repo_root). Raises ScopedCommitError on failure."""
    target = Path(path_str).resolve() if Path(path_str).is_absolute() else (cwd / path_str).resolve()
    anchor = target if target.is_dir() else target.parent
    while not anchor.exists() and anchor != anchor.parent:
        anchor = anchor.parent
    if not anchor.exists():
        raise ScopedCommitError(f"path does not exist: {path_str}")

    proc = subprocess.run(
        ["git", "-C", str(anchor), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise ScopedCommitError(f"path outside repository: {path_str}")

    repo_root = Path(proc.stdout.strip()).resolve()
    try:
        rel = target.relative_to(repo_root)
    except ValueError:
        raise ScopedCommitError(f"path outside repository: {path_str}")

    if not target.exists():
        # Check if tracked in the git index
        ls_proc = subprocess.run(
            ["git", "-C", str(repo_root), "ls-files", "--error-unmatch", "--", str(rel)],
            capture_output=True,
            text=True,
            check=False,
        )
        if ls_proc.returncode != 0:
            raise ScopedCommitError(f"path does not exist: {path_str}")

    return target, repo_root


def commit(
    cwd: Path,
    paths: Sequence[str],
    message: str,
    branch: str | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    """Commit only the named paths."""
    if not paths:
        raise ScopedCommitError("at least one path is required")
    if not message or not message.strip():
        raise ScopedCommitError("commit message cannot be empty")

    cwd = Path(cwd).resolve()
    resolved_pairs = [_resolve_repo_for_path(cwd, p) for p in paths]
    targets = [p[0] for p in resolved_pairs]
    repo_roots = [p[1] for p in resolved_pairs]

    primary_repo = repo_roots[0]
    for other_repo in repo_roots[1:]:
        if other_repo != primary_repo:
            raise ScopedCommitError(f"paths span multiple repositories: {primary_repo} and {other_repo}")

    # Check for detached HEAD
    sym_proc = subprocess.run(
        ["git", "-C", str(primary_repo), "symbolic-ref", "-q", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if sym_proc.returncode != 0:
        raise ScopedCommitError("HEAD is detached; commit refused")

    # Validate --branch if provided
    if branch is not None:
        ref_proc = subprocess.run(
            ["git", "-C", str(primary_repo), "check-ref-format", "--branch", branch],
            capture_output=True,
            text=True,
            check=False,
        )
        if ref_proc.returncode != 0:
            raise ScopedCommitError(f"invalid branch name: {branch}")

    # Pathspecs relative to repository root
    repo_rel_paths = [str(t.relative_to(primary_repo)) for t in targets]

    # Check git status for changes under the given paths before switching branch
    status_proc = subprocess.run(
        ["git", "-C", str(primary_repo), "status", "--porcelain", "--untracked-files=all", "--", *repo_rel_paths],
        capture_output=True,
        text=True,
        check=False,
    )
    if status_proc.returncode != 0:
        raise ScopedCommitError(status_proc.stderr.strip() or "git status failed")

    branch_proc = subprocess.run(
        ["git", "-C", str(primary_repo), "branch", "--show-current"],
        capture_output=True,
        text=True,
        check=False,
    )
    current_branch = branch_proc.stdout.strip()

    if not status_proc.stdout.strip():
        return {
            "repository": str(primary_repo),
            "branch": current_branch,
            "created_branch": False,
            "nothing_to_commit": True,
            "files": [],
            "pushed": False,
        }

    # Determine default branches
    default_branches = {"main", "master"}
    try:
        located = workspace.locate(primary_repo)
        if located.entry is not None and located.entry.default_branch:
            default_branches.add(located.entry.default_branch)
    except Exception:
        pass

    is_default = current_branch in default_branches
    should_create = is_default or (branch is not None and branch != current_branch)
    commit_branch = current_branch
    created_branch = False

    if should_create:
        if branch is not None:
            target_name = branch
        else:
            if today is None:
                today = date.today()
            first_rel = repo_rel_paths[0]
            slug = re.sub(r"[^a-z0-9]+", "-", first_rel.lower()).strip("-")[:40].rstrip("-")
            if not slug:
                slug = "changes"
            target_name = f"gin/{slug}-{today.strftime('%Y-%m-%d')}"

        candidate = target_name
        suffix = 1
        while _branch_exists(primary_repo, candidate):
            suffix += 1
            candidate = f"{target_name}-{suffix}"

        switch_proc = subprocess.run(
            ["git", "-C", str(primary_repo), "switch", "-c", candidate],
            capture_output=True,
            text=True,
            check=False,
        )
        if switch_proc.returncode != 0:
            raise ScopedCommitError(switch_proc.stderr.strip() or f"failed to create branch {candidate}")
        created_branch = True
        commit_branch = candidate

    # Stage and commit only the specified paths
    add_proc = subprocess.run(
        ["git", "-C", str(primary_repo), "add", "-A", "--", *repo_rel_paths],
        capture_output=True,
        text=True,
        check=False,
    )
    if add_proc.returncode != 0:
        raise ScopedCommitError(add_proc.stderr.strip() or "git add failed")

    commit_proc = subprocess.run(
        ["git", "-C", str(primary_repo), "commit", "--only", "-m", message, "--", *repo_rel_paths],
        capture_output=True,
        text=True,
        check=False,
    )
    if commit_proc.returncode != 0:
        err_msg = commit_proc.stderr.strip() or commit_proc.stdout.strip() or "git commit failed"
        raise ScopedCommitError(err_msg, returncode=commit_proc.returncode)

    sha_proc = subprocess.run(
        ["git", "-C", str(primary_repo), "log", "-1", "--format=%H"],
        capture_output=True,
        text=True,
        check=False,
    )
    commit_sha = sha_proc.stdout.strip()

    diff_proc = subprocess.run(
        ["git", "-C", str(primary_repo), "diff-tree", "--no-commit-id", "--name-only", "-r", commit_sha],
        capture_output=True,
        text=True,
        check=False,
    )
    committed_files = [line for line in diff_proc.stdout.splitlines() if line.strip()]

    return {
        "repository": str(primary_repo),
        "branch": commit_branch,
        "created_branch": created_branch,
        "commit": commit_sha,
        "files": committed_files,
        "pushed": False,
    }


def format_text(result: dict[str, Any], paths: Sequence[str]) -> str:
    """Format scoped commit result for text output."""
    if result.get("nothing_to_commit"):
        return f"Nothing to commit under {', '.join(paths)}."
    lines: list[str] = []
    files = result.get("files", [])
    count = len(files)
    file_word = "file" if count == 1 else "files"
    branch = result.get("branch", "")
    sha7 = (result.get("commit") or "")[:7]
    lines.append(f"Committed {count} {file_word} to {branch} ({sha7})")
    if result.get("created_branch"):
        lines.append(f"Created branch {branch}")
    for f in files:
        lines.append(f)
    lines.append("Not pushed.")
    return "\n".join(lines)


def main(argv: Sequence[str]) -> int:
    """Entry point for `gin commit`."""
    parser = argparse.ArgumentParser(prog="gin commit", description="commit only the named paths")
    parser.add_argument("paths", nargs="+", help="files or folders to commit")
    parser.add_argument("-m", "--message", required=True, help="commit message")
    parser.add_argument("--branch", default=None, help="branch name to create/use")
    parser.add_argument("--format", choices=("text", "json"), default="text", help="output format")
    try:
        args = parser.parse_args(list(argv))
    except SystemExit as exc:
        return exc.code

    cwd = Path(os.getcwd()).resolve()
    try:
        result = commit(
            cwd=cwd,
            paths=args.paths,
            message=args.message,
            branch=args.branch,
        )
    except ScopedCommitError as error:
        print(str(error), file=sys.stderr)
        return error.returncode

    if args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        print(format_text(result, args.paths))
    return 0
