"""`gin team complete`: closes an epic once every track bead is closed and every pull request merged."""

from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Any

from . import team_beads, team_host, team_pending, workspace
from .team import Member, TeamConfig, TeamError


def _child_sort_key(child: dict[str, Any]) -> tuple[int, int, str]:
    track = team_beads.track_of(child)
    if track is not None:
        return (0, track[1], str(child.get("id") or ""))
    return (1, 0, str(child.get("id") or ""))


def complete(root: Path, team: TeamConfig, member: Member, epic: str) -> dict[str, Any]:
    """Close `epic` if every child bead is closed and every track pull request has merged."""
    if not any(area.lead in member.roles for area in team.areas.values()):
        raise TeamError("only an area lead completes an epic")

    issue = team_beads._show(root, epic)
    if issue.get("issue_type") != "epic":
        raise TeamError(f"{epic} is not an epic")

    children = sorted(team_pending._beads(root, ["list", "--parent", epic, "--all", "--limit", "0"]),
                      key=_child_sort_key)
    missing: list[str] = []
    pull_requests: list[str] = []
    first_topic: str | None = None

    for child in children:
        if "prep" not in (child.get("labels") or []) and child.get("status") != "closed":
            missing.append(f"{child['id']} is {child.get('status')}")

        track = team_beads.track_of(child)
        if track is not None:
            if first_topic is None:
                first_topic = track[0]
            try:
                repo_dir, _entry, branch = team_beads._track_place(root, track)
            except team_beads.SyncConflict as conflict:
                missing.append(f"{child['id']}: {conflict}")
                continue

            pr = team_host.pr_for_branch(team.host, branch, repo_dir)
            if pr is None:
                missing.append(f"{branch}: no pull request")
            elif pr.state != "merged":
                missing.append(f"{branch}: {pr.state}")
            else:
                if pr.url not in pull_requests:
                    pull_requests.append(pr.url)

    if first_topic is not None:
        space = workspace.locate(root).workspace
        if space is not None:
            ref = f"refs/heads/feat/{first_topic}"
            try:
                proc = subprocess.run(["git", "ls-remote", "--heads", "origin", ref],
                                      cwd=root, text=True, capture_output=True, check=False)
            except (OSError, subprocess.SubprocessError) as error:
                raise TeamError(f"git ls-remote failed in parent repository {root}: {error}") from error
            if proc.returncode != 0:
                raise TeamError(f"git ls-remote failed in parent repository {root}: {proc.stderr.strip()}")
            if proc.stdout.strip():
                parent_branch = f"feat/{first_topic}"
                parent_pr = team_host.pr_for_branch(team.host, parent_branch, root)
                if parent_pr is None:
                    missing.append(f"{parent_branch}: no pull request")
                elif parent_pr.state != "merged":
                    missing.append(f"{parent_branch}: {parent_pr.state}")
                else:
                    if parent_pr.url not in pull_requests:
                        pull_requests.append(parent_pr.url)

    if missing:
        return {"status": "incomplete", "epic": epic, "pull_requests": pull_requests, "missing": missing}

    reason = f"shipped: {', '.join(pull_requests)}" if pull_requests else "shipped"
    argv = ["close", epic, "--reason", reason]
    if any(child.get("status") != "closed" for child in children):
        argv.append("--force")  # only open prep children remain; bd refuses to close an epic over them
    completed = team_beads._bd(root, argv, actor=member.email)
    if completed.returncode != 0:
        raise TeamError(f"bd close failed: {completed.stderr.strip()}")

    return {"status": "completed", "epic": epic, "pull_requests": pull_requests, "missing": []}
