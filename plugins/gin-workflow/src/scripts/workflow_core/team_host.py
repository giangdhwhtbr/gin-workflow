"""Git host facade: one `PrInfo` view of a pull/merge request, fetched by the adapter of `team.host`
(`workflow_core.hosts`)."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
from typing import Any
from .executables import tool


class HostUnavailable(Exception):
    """The host CLI is missing, unauthenticated, or unreachable: exit 2, nothing recorded."""


@dataclass(frozen=True)
class PrInfo:
    url: str
    state: str                              # open | merged | closed
    merged: bool
    merge_commit: str
    head_sha: str
    author: str
    approvals: tuple[tuple[str, str], ...]  # (login, commit the approval was made on; "" when unknown)
    files: tuple[str, ...]
    body: str = ""
    approval_note: str = ""                 # why approvals carry no commit (GitLab), shown when none count


def _run(host: str, argv: list[str], cwd: Path) -> Any:
    """Run the host's CLI with `argv` and parse its JSON; adapters call it as `team_host._run` so tests can patch it."""
    from .hosts import adapter

    spec = adapter(host)
    name, fix = spec.executable, spec.login_fix
    executable = tool(name, cwd)
    if executable is None:
        raise HostUnavailable(f"{name} is not installed; install it, then run {fix}")
    try:
        completed = subprocess.run([executable, *argv], cwd=cwd, text=True, capture_output=True, check=False,
                                   timeout=60)
    except (OSError, subprocess.SubprocessError) as error:
        raise HostUnavailable(f"{name} failed: {error}") from error
    if completed.returncode in spec.auth_exit_codes:
        raise HostUnavailable(f"{name} is not logged in: run {fix}")
    if completed.returncode != 0:
        raise HostUnavailable(f"{name} {argv[0]} failed: {completed.stderr.strip()} (check `{fix}`)")
    try:
        return json.loads(completed.stdout or "null")
    except json.JSONDecodeError as error:
        raise HostUnavailable(f"{name} returned non-JSON output") from error


def fetch_pr(url: str, host: str, cwd: Path) -> PrInfo:
    from .hosts import adapter

    return adapter(host).fetch_pr(url, cwd)


def merged_with_text(host: str, text: str, cwd: Path) -> list[PrInfo]:
    """Merged PRs/MRs whose description mentions `text` (url, body, merge commit only)."""
    from .hosts import adapter

    return adapter(host).merged_with_text(text, cwd)


def pr_for_branch(host: str, branch: str, cwd: Path) -> PrInfo | None:
    """The newest PR/MR of any state from `branch` (url, state, merge commit only), or None."""
    from .hosts import adapter

    return adapter(host).pr_for_branch(branch, cwd)
