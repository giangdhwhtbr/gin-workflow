"""Where a repository's local, untracked workflow state lives."""

from __future__ import annotations

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
