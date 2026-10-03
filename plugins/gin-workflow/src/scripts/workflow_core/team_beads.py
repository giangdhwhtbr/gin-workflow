"""Team Beads operations: my ready work, claims, cross-member placeholders, optional Dolt sync."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any

from .team import Member, TeamConfig, TeamError

_EXTERNAL = re.compile(r"^external: (\S+)#(\d+)$")
_PLAN_LINE = re.compile(r"^Plan:\s*`?([^`\s]+)`?\s*$", re.M)
_TRACKS_LINE = re.compile(r"^Tracks:\s*([\d,\s]+)$", re.M)


class SyncConflict(Exception):
    """Dolt reported a merge conflict or a rejected push: exit 1, nothing forced."""


def _bd(root: Path, argv: list[str], *, actor: str = "", timeout: int = 120) -> subprocess.CompletedProcess:
    executable = shutil.which("bd")
    if executable is None:
        raise TeamError("bd is not installed")
    env = {**os.environ, "BD_ACTOR": actor} if actor else None
    return subprocess.run([executable, *argv], cwd=root, text=True, capture_output=True, check=False,
                          env=env, timeout=timeout)


def _bd_json(root: Path, argv: list[str]) -> Any:
    completed = _bd(root, [*argv, "--json"])
    if completed.returncode != 0:
        raise TeamError(f"bd {argv[0]} failed: {completed.stderr.strip()}")
    return json.loads(completed.stdout or "[]")


def _show(root: Path, bead: str) -> dict[str, Any]:
    data = _bd_json(root, ["show", bead])
    return data[0] if isinstance(data, list) else data


def ready(root: Path, team: TeamConfig, member: Member) -> list[dict[str, Any]]:
    mine = set(team.areas_for(member))
    result = []
    for issue in _bd_json(root, ["ready"]):
        assignee = (issue.get("assignee") or "").lower()
        areas = {label[5:] for label in issue.get("labels") or [] if label.startswith("area:")}
        if assignee == member.email or (not assignee and (areas & mine or (not areas and not team.areas))):
            result.append({"id": issue["id"], "title": issue.get("title", ""), "assignee": assignee,
                           "areas": sorted(areas)})
    return result


def sync(root: Path) -> dict[str, Any]:
    for step in ("pull", "push"):
        completed = _bd(root, ["dolt", step])
        if completed.returncode != 0:
            message = (completed.stderr or completed.stdout).strip()
            if step == "pull" and "no branches found" in message:
                continue  # first sync: the remote holds no Beads data yet
            if "conflict" in message.lower() or (step == "push" and "pull" in message.lower()):
                raise SyncConflict(f"bd dolt {step}: {message}")
            raise TeamError(f"bd dolt {step} failed: {message}")
    return {"status": "synced"}


def _dolt_dir(root: Path) -> Path:
    shown = _bd(root, ["dolt", "show"]).stdout
    fields = dict(re.findall(r"^\s*(Database|Mode|Data):\s*(.+?)\s*$", shown, re.M))
    if not fields.get("Mode", "").startswith("embedded") or "Data" not in fields:
        raise TeamError("local Beads is not in embedded mode; reset it to the remote by hand")
    return Path(fields["Data"]) / fields.get("Database", "")


def reset_to_remote(root: Path) -> None:
    """Drop local unpushed Beads commits; callers sync first so only the failed claim is lost."""
    dolt = shutil.which("dolt")
    if dolt is None:
        raise TeamError("dolt is not installed; cannot reset local Beads to the remote")
    directory = _dolt_dir(root)
    for argv in (["fetch", "origin"], ["reset", "--hard", "origin/main"]):
        completed = subprocess.run([dolt, *argv], cwd=directory, text=True, capture_output=True, check=False,
                                   timeout=120)
        if completed.returncode != 0:
            raise TeamError(f"dolt {argv[0]} failed: {completed.stderr.strip()}")


def claim(root: Path, team: TeamConfig, member: Member, bead: str) -> dict[str, Any]:
    if team.beads_remote:
        sync(root)
    holder = (_show(root, bead).get("assignee") or "").lower()
    if holder and holder != member.email:
        raise SyncConflict(f"{bead} is already claimed by {holder}")
    completed = _bd(root, ["update", bead, "--claim"], actor=member.email)
    if completed.returncode != 0:
        raise SyncConflict(completed.stderr.strip() or completed.stdout.strip())
    if team.beads_remote:
        pushed = _bd(root, ["dolt", "push"])
        if pushed.returncode != 0:
            reset_to_remote(root)
            holder = (_show(root, bead).get("assignee") or "").lower() or "nobody"
            raise SyncConflict(f"push rejected; local Beads reset to the remote; {bead} is held by {holder}")
    return {"status": "claimed", "bead": bead, "assignee": member.email}


def _tracks_in(body: str) -> tuple[str, set[int]]:
    plan = _PLAN_LINE.search(body)
    tracks = _TRACKS_LINE.search(body)
    numbers = {int(item) for item in re.findall(r"\d+", tracks.group(1))} if tracks else set()
    return (plan.group(1) if plan else ""), numbers


def _delivers(body: str, plan: str, number: int) -> bool:
    named, numbers = _tracks_in(body)
    return named == plan and number in numbers


def deps(root: Path, team: TeamConfig) -> dict[str, Any]:
    from .team_host import merged_with_text

    closed, waiting = [], []
    for issue in _bd_json(root, ["list", "--status", "open"]):
        match = _EXTERNAL.match(issue.get("title", ""))
        if not match:
            continue
        plan, number = match.group(1), int(match.group(2))
        found = next((pr for pr in merged_with_text(team.host, plan, root) if _delivers(pr.body, plan, number)), None)
        if found is None:
            waiting.append(issue["id"])
            continue
        done = _bd(root, ["close", issue["id"], "--reason", f"{found.url} merged ({found.merge_commit})"])
        if done.returncode != 0:
            raise TeamError(f"bd close {issue['id']} failed: {done.stderr.strip()}")
        closed.append({"id": issue["id"], "pr": found.url})
    return {"closed": closed, "waiting": waiting}
