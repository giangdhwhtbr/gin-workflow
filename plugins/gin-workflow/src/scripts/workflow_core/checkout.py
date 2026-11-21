"""Where a repository's local, untracked workflow state lives."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess


def main_checkout(repo: Path) -> Path:
    """The repository's main checkout, also when `repo` is one of its linked worktrees."""
    try:
        done = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=repo,
                              text=True, capture_output=True, check=False, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return repo
    common = Path(done.stdout.strip())
    return common.parent.resolve() if done.returncode == 0 and common.name == ".git" else repo


@dataclass(frozen=True)
class Worktree:
    path: Path
    branch: str


def _inside(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
    except ValueError:
        return False
    return True


def worktrees(repo: Path) -> list[Worktree]:
    """Git worktrees inside the repository (`.planning/worktrees`, harness-native ones too) with their branch."""
    try:
        listed = subprocess.run(["git", "worktree", "list", "--porcelain"], cwd=repo, text=True,
                                capture_output=True, check=False, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return []
    if listed.returncode != 0:
        return []
    base = Path(os.path.realpath(repo))
    found: list[Worktree] = []
    path: Path | None = None
    branch = ""
    for line in listed.stdout.splitlines() + [""]:
        if line.startswith("worktree "):
            path, branch = Path(os.path.realpath(line[len("worktree "):])), ""
        elif line.startswith("branch "):
            branch = line[len("branch "):].removeprefix("refs/heads/")
        elif not line and path is not None:
            if path != base and _inside(path, base):
                found.append(Worktree(path, branch))
            path = None
    return found
