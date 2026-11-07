"""Team Beads operations: my ready work, claims, cross-member placeholders, optional Dolt sync."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any, Mapping

from . import tasks
from .executables import tool
from .team import Area, Member, TeamConfig, TeamError

_EXTERNAL = re.compile(r"^external: (\S+)#(\d+)$")
_PLAN_LINE = re.compile(r"^Plan:\s*`?([^`\s]+)`?\s*$", re.M)
_TRACKS_LINE = re.compile(r"^Tracks:\s*([\d,\s]+)$", re.M)
RELEASED = "released"


class SyncConflict(Exception):
    """Dolt reported a merge conflict or a rejected push: exit 1, nothing forced."""


def _bd(root: Path, argv: list[str], *, actor: str = "", timeout: int = 120) -> subprocess.CompletedProcess:
    executable = tool("bd", root)
    if executable is None:
        raise TeamError("bd is not installed")
    env = {**os.environ, "BD_ACTOR": actor} if actor else None
    return subprocess.run([executable, *argv], cwd=root, text=True, capture_output=True, check=False,
                          env=env, timeout=timeout)


def _bd_json(root: Path, argv: list[str], *, timeout: int = 120) -> Any:
    completed = _bd(root, [*argv, "--json"], timeout=timeout)
    if completed.returncode != 0:
        raise TeamError(f"bd {argv[0]} failed: {completed.stderr.strip()}")
    return json.loads(completed.stdout or "[]")


def _show(root: Path, bead: str, *, timeout: int = 120) -> dict[str, Any]:
    data = _bd_json(root, ["show", bead], timeout=timeout)
    return data[0] if isinstance(data, list) else data


_STAMP = "%Y-%m-%dT%H:%M:%SZ"  # lexicographic order equals time order; every lease comparison uses it


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime(_STAMP)


def _expires(team: TeamConfig) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=team.claim_ttl_hours)).strftime(_STAMP)


def metadata_json(issue: Mapping[str, Any], key: str) -> dict[str, Any]:
    """A JSON object stored under `metadata.<key>` (bd returns it parsed or as a string); {} when absent."""
    metadata = issue.get("metadata") if isinstance(issue.get("metadata"), Mapping) else {}
    value = metadata.get(key)
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return {}
    return dict(value) if isinstance(value, Mapping) else {}


def claim_of(issue: Mapping[str, Any]) -> dict[str, Any]:
    return metadata_json(issue, "claim")


def claim_expired(issue: Mapping[str, Any], now: str) -> bool:
    """True when the claim lease is past, or the bead was claimed before leases existed."""
    expires_at = str(claim_of(issue).get("expires_at") or "")
    return expires_at < now


def _areas_of(team: TeamConfig, issue: Mapping[str, Any]) -> list[Area]:
    return [team.areas[name] for label in issue.get("labels") or [] if label.startswith("area:")
            if (name := label[5:]) in team.areas]


def ready(root: Path, team: TeamConfig, member: Member) -> list[dict[str, Any]]:
    mine = set(team.areas_for(member))
    held = tasks.held_by_external(root, tool("bd", root) or "bd")
    if held is None:
        raise TeamError("bd ready --explain failed, so external dependencies cannot be checked")
    result = []
    for issue in tasks.without_held(_bd_json(root, ["ready", "--exclude-type", "milestone"]), held):
        assignee = (issue.get("assignee") or "").lower()
        labels = issue.get("labels") or []
        areas = {label[5:] for label in labels if label.startswith("area:")}
        released = RELEASED in labels
        if assignee == member.email or (not assignee and (released or areas & mine or (not areas and not team.areas))):
            result.append({"id": issue["id"], "title": issue.get("title", ""), "assignee": assignee,
                           "areas": sorted(areas), "released": released})
    seen = {row["id"] for row in result}
    now = utc_now()
    for issue in tasks.without_held(_bd_json(root, ["list", "--status", "in_progress"]), held):
        assignee = (issue.get("assignee") or "").lower()
        areas = {label[5:] for label in issue.get("labels") or [] if label.startswith("area:")}
        if issue["id"] not in seen and assignee and assignee != member.email and claim_expired(issue, now) \
                and (areas & mine or (not areas and not team.areas)):
            result.append({"id": issue["id"], "title": issue.get("title", ""), "assignee": assignee,
                           "areas": sorted(areas), "expired_claim": assignee})
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


def claim(root: Path, team: TeamConfig, member: Member, bead: str) -> dict[str, Any]:
    """Claim or renew a bead; an expired lease held by someone else is taken over with a note."""
    if team.beads_remote:
        sync(root)
    issue = _show(root, bead)
    released = RELEASED in (issue.get("labels") or [])
    ineligible = [] if released else [area.name for area in _areas_of(team, issue) if not team.eligible(member, area)]
    if ineligible:
        raise SyncConflict(f"{member.email} may not own tracks in {', '.join(ineligible)}")
    holder = (issue.get("assignee") or "").lower()
    expires_at = _expires(team)
    lease = json.dumps({"holder": member.email, "expires_at": expires_at})
    if holder and holder != member.email:
        if not claim_expired(issue, utc_now()):
            raise SyncConflict(f"{bead} is already claimed by {holder} until {claim_of(issue)['expires_at']}")
        argv = ["update", bead, "--assignee", member.email, "--status", "in_progress",
                "--append-notes", f"took over expired claim from {holder}", "--set-metadata", f"claim={lease}"]
    else:
        argv = ["update", bead, "--claim", "--set-metadata", f"claim={lease}"]
    if released:
        argv += ["--remove-label", RELEASED]
    completed = _bd(root, argv, actor=member.email)
    if completed.returncode != 0:
        raise SyncConflict(completed.stderr.strip() or completed.stdout.strip())
    _push(root, team, bead)
    return {"status": "renewed" if holder == member.email else "claimed", "bead": bead, "assignee": member.email,
            "expires_at": expires_at, "advisory": not team.beads_remote}


def push(root: Path, team: TeamConfig) -> None:
    """Push local Beads without ever resetting them: a rejected push leaves the local write in place."""
    if team.beads_remote:
        pushed = _bd(root, ["dolt", "push"])
        if pushed.returncode != 0:
            raise SyncConflict(f"bd dolt push: {(pushed.stderr or pushed.stdout).strip()}")


def _push(root: Path, team: TeamConfig, bead: str) -> None:
    """Push the local write; a rejected push syncs once and retries. Local Beads are never reset."""
    if not team.beads_remote or _bd(root, ["dolt", "push"]).returncode == 0:
        return
    try:
        sync(root)
    except (SyncConflict, TeamError) as error:
        raise SyncConflict(f"push rejected for {bead}; local Beads kept, run gin team sync ({error})") from error


def reassign(root: Path, team: TeamConfig, member: Member, bead: str, email: str) -> dict[str, Any]:
    """Hand a track to another member: only the current assignee or the lead of one of its areas may."""
    target = team.member(email)
    if target is None:
        raise TeamError(f"{email} is not a team member")
    if team.beads_remote:
        sync(root)
    issue = _show(root, bead)
    if issue.get("status") == "closed":
        raise SyncConflict(f"{bead} is closed")
    holder = (issue.get("assignee") or "").lower()
    areas = _areas_of(team, issue)
    if holder != member.email and not any(area.lead in member.roles for area in areas):
        raise SyncConflict(f"only {holder or 'an area lead'} or the lead of its area may reassign {bead}")
    if holder == target.email:
        raise SyncConflict(f"{bead} is already assigned to {target.email}")
    ineligible = [area.name for area in areas if not team.eligible(target, area)]
    if ineligible:
        raise SyncConflict(f"{target.email} may not own tracks in {', '.join(ineligible)}")
    note = f"reassigned {holder or 'nobody'} -> {target.email} by {member.email}"
    completed = _bd(root, ["update", bead, "--assignee", target.email, "--append-notes", note,
                           "--set-metadata", f'claim={json.dumps({"holder": target.email, "expires_at": _expires(team)})}'], actor=member.email)
    if completed.returncode != 0:
        raise SyncConflict(completed.stderr.strip() or completed.stdout.strip())
    _push(root, team, bead)
    return {"status": "reassigned", "bead": bead, "from": holder, "assignee": target.email}


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

    closed, waiting, unresolved = [], [], []
    for issue in _bd_json(root, ["list", "--status", "open"]):
        match = _EXTERNAL.match(issue.get("title", ""))
        if not match:
            continue
        plan, number = match.group(1), int(match.group(2))
        found = next((pr for pr in merged_with_text(team.host, plan, root) if _delivers(pr.body, plan, number)), None)
        if found is None:
            waiting.append(issue["id"])
            continue
        if not found.merge_commit:
            unresolved.append({"id": issue["id"], "pr": found.url})
            continue
        noted = _bd(root, ["update", issue["id"], "--set-metadata", f"merge_commit={found.merge_commit}"])
        if noted.returncode != 0:
            raise TeamError(f"bd update {issue['id']} failed: {noted.stderr.strip()}")
        done = _bd(root, ["close", issue["id"], "--reason", f"{found.url} merged ({found.merge_commit})"])
        if done.returncode != 0:
            raise TeamError(f"bd close {issue['id']} failed: {done.stderr.strip()}")
        closed.append({"id": issue["id"], "pr": found.url})
    return {"closed": closed, "waiting": waiting, "unresolved": unresolved}


def _has_commit(root: Path, commit: str) -> bool:
    return bool(commit) and subprocess.run(["git", "merge-base", "--is-ancestor", commit, "HEAD"], cwd=root,
                                           capture_output=True, check=False).returncode == 0


def deps_for(root: Path, bead: str) -> dict[str, Any]:
    """The bead's `external:` placeholders: ok only when closed with its merge commit in this workspace."""
    ok, missing = [], []
    for dep in _show(root, bead).get("dependencies") or []:
        match = _EXTERNAL.match(dep.get("title", ""))
        if not match:
            continue
        commit = str((dep.get("metadata") or {}).get("merge_commit", ""))
        if dep.get("status") != "closed":
            missing.append({"id": dep["id"], "reason": f"{match.group(1)}#{match.group(2)} has not merged; run team deps"})
        elif not commit:
            missing.append({"id": dep["id"], "reason": "no merge commit recorded; run team deps"})
        elif not _has_commit(root, commit):
            missing.append({"id": dep["id"], "reason": f"fetch/rebase onto the plan's integration branch to include {commit}"})
        else:
            ok.append(dep["id"])
    return {"bead": bead, "ok": ok, "missing": missing}


def gates_of(issue: Mapping[str, Any]) -> dict[str, Any]:
    return metadata_json(issue, "gates")


def write_gate(root: Path, epic: str, gate: str, proof: Mapping[str, Any], *, actor: str) -> None:
    """Merge one proven gate into the epic bead's `gates` metadata; other gates are kept."""
    gates = {**gates_of(_show(root, epic)), gate: dict(proof)}
    completed = _bd(root, ["update", epic, "--set-metadata", f"gates={json.dumps(gates, sort_keys=True)}"], actor=actor)
    if completed.returncode != 0:
        raise TeamError(f"bd update {epic} --set-metadata gates failed: {completed.stderr.strip()}")


def epic_for(root: Path, workflow_id: str, recorded: str) -> str:
    """The bead that shares a workflow's gates: the bead's id when the workflow id names one, else the recorded
    epic, else the epic labelled workflow:<id>; "" when none exists. Raises TeamError when bd is unavailable."""
    shown = _bd(root, ["show", workflow_id, "--json"], timeout=30)
    if shown.returncode == 0:
        data = json.loads(shown.stdout or "[]")
        row = data[0] if isinstance(data, list) and data else data
        return str(row.get("id") or workflow_id) if isinstance(row, dict) else workflow_id
    if recorded:
        return recorded
    rows = [row for row in _bd_json(root, ["list", "--label", f"workflow:{workflow_id}", "--all", "--limit", "0"],
                                    timeout=30) if row.get("issue_type") == "epic"]
    return str(rows[0]["id"]) if rows else ""


def shared_gates(root: Path, workflow_id: str, recorded: str) -> tuple[str, dict[str, Any], str | None]:
    """(epic, its `gates` metadata, None), or ("", {}, cause) when the tracker cannot answer."""
    try:
        epic = epic_for(root, workflow_id, recorded)
        return epic, (gates_of(_show(root, epic, timeout=30)) if epic else {}), None
    except (TeamError, OSError, subprocess.SubprocessError, json.JSONDecodeError) as error:
        return "", {}, f"tracker unavailable: {error}"
