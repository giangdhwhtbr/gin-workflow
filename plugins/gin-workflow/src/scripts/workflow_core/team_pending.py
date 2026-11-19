"""`gin team pending`: open gate pull requests and track pull requests, with what each still needs."""

from __future__ import annotations

from pathlib import Path
import re
import subprocess
from typing import Any, Sequence

from . import tasks, team as team_core, team_host
from .team import TeamConfig, TeamError, lead_plan
from .team_host import HostUnavailable

_TRACK_LINE = re.compile(r"^Plan:\s*`?([^`,\n]+?)`?,\s*Track\s+(\d+)\b", re.MULTILINE)
_LANE_LINE = re.compile(r"^Lane:\s*`?([a-z0-9][a-z0-9-]*)`?\s*$", re.MULTILINE)
_LANE_BEAD = re.compile(r"^Plan:\s*`?([^`,\n]+?)`?,\s*Lane\s+`?([a-z0-9][a-z0-9-]*)`?\s*$", re.MULTILINE)
_EPIC_LINE = re.compile(r"^(?:Epic|Workflow):\s*(\S+)", re.MULTILINE)
_GATES = {"spec": "requirement_confirmed", "plan": "plan_approved", "ship": "ship", "quick": "ship", "track": None}


def git(root: Path, *argv: str) -> str:
    """Run one git command and return its output; the module's only git boundary (ls-remote, fetch, show)."""
    try:
        done = subprocess.run(["git", *argv], cwd=root, text=True, capture_output=True, check=False, timeout=30)
    except (OSError, subprocess.SubprocessError) as error:
        raise TeamError(f"git {argv[0]} failed: {error}") from error
    if done.returncode != 0:
        raise TeamError(f"git {argv[0]} failed: {done.stderr.strip()}")
    return done.stdout


def _beads(root: Path, argv: Sequence[str]) -> list[dict[str, Any]]:
    rows, cause = tasks.query_result(root, argv)
    if cause:
        raise TeamError(f"cannot read beads: {cause}")
    return rows or []


def topic_of(plan_path: str) -> str:
    """The plan file stem without a leading `YYYY-MM-DD-`; a lane plan `<stem>.lane-<lane>.md` has the topic of
    its lead plan."""
    return re.sub(r"^\d{4}-\d{2}-\d{2}-", "", Path(lead_plan(plan_path)).stem)


def track_lane(description: str) -> tuple[str, int, str, bool] | None:
    """(plan path, track number, lane, named) of a track bead description. The lane is its `Lane:` line, else
    the implicit `t<N>` with `named` False (a bead orchestrated before lanes). None without a
    `Plan: <path>, Track <N>` line."""
    track = _TRACK_LINE.search(description)
    if track is None:
        return None
    lane = _LANE_LINE.search(description)
    return track[1], int(track[2]), lane[1] if lane else f"t{track[2]}", lane is not None


def lane_bead(description: str) -> tuple[str, str] | None:
    """(plan path, lane) of a lane bead description (`Plan: <path>, Lane <name>`): the bead that stands for
    planning a lane the plan declares without tracks; None for any other bead."""
    found = _LANE_BEAD.search(description)
    return (found[1], found[2]) if found else None


def lane_branch(description: str) -> str | None:
    """`feat/<topic>-<lane>` of a track bead or a lane bead description; None for any other bead."""
    found = track_lane(description)
    if found is not None:
        return f"feat/{topic_of(found[0])}-{found[2]}"
    planned = lane_bead(description)
    return None if planned is None else f"feat/{topic_of(planned[0])}-{planned[1]}"


def candidates(root: Path, team: TeamConfig) -> list[tuple[str, str, str | None]]:
    """(branch, kind, epic) in text order: remote `spec/*`, `plan/*`, and `quick/*` heads (epic read later or none), `feat/<topic>` per
    open epic with track beads of any status when the ship gate has a policy, and `feat/<topic>-<lane>` per lane with
    an open track bead."""
    heads = [line.split("\trefs/heads/", 1)[1] for line in git(root, "ls-remote", "--heads", "origin").splitlines()
             if "\trefs/heads/" in line]
    found: list[tuple[str, str, str | None]] = [(head, "spec", None) for head in heads if head.startswith("spec/")]
    found += [(head, "plan", None) for head in heads if head.startswith("plan/")]
    found += [(head, "quick", None) for head in heads if head.startswith("quick/")]
    beads = _beads(root, ["list", "--all", "--limit", "0"])  # closed tracks still name the ship branch
    live = {bead["id"] for bead in beads if bead.get("status") in ("open", "in_progress")}
    tracks: dict[str, str] = {}
    topics: dict[str, str] = {}
    for bead in beads:
        description = bead.get("description") or ""
        found_lane = track_lane(description)
        epic = bead.get("parent")
        if not (epic and found_lane):
            continue
        topic = topic_of(found_lane[0])
        if bead["id"] in live:
            tracks[lane_branch(description)] = epic
        if epic in live:
            topics.setdefault(epic, topic)
    if team_core.has_policy("ship", team):
        found += [(f"feat/{topic}", "ship", epic) for epic, topic in topics.items()]
    return found + [(branch, "track", epic) for branch, epic in tracks.items()]


def branch_documents(root: Path, branch: str, files: Sequence[str]) -> dict[str, str]:
    """The text of each spec, plan, or SDD change `.md` file in `files`, read from `branch` on origin with one fetch."""
    from .specs import load_config, sdd_config

    changes = str(sdd_config(load_config(root))["changes"]).strip("/")
    documents = [path for path in files if path.endswith(".md")
                 and path.startswith((".planning/specs/", ".planning/plans/", f"{changes}/"))]
    if not documents:
        return {}
    git(root, "fetch", "--quiet", "origin", f"refs/heads/{branch}")
    return {path: git(root, "show", f"FETCH_HEAD:{path}") for path in documents}


def pending(root: Path, team: TeamConfig, *, workflow_id: str | None = None,
            milestone: str | None = None) -> list[dict[str, Any]]:
    """One row per open pull request of a candidate branch: gate rows carry as `missing` the reasons the gate's
    policy gives before merge, with the branch's spec or plan text as the artifact, and the note `approvals: host` under
    a `host` policy; quick rows are ship rows without an epic (no gate when ship has no policy); track rows only their
    approvers.
    A host failure before any host call has succeeded raises; after that, a failed lookup gives its row `error`."""
    keep = {workflow_id} if workflow_id else None
    if milestone:
        keep = {bead["id"] for bead in _beads(root, ["list", "--parent", milestone, "--type", "epic", "--limit", "0"])}
    rows: list[dict[str, Any]] = []
    reached = False  # a host call succeeded, so a later host failure belongs to its row
    for branch, kind, epic in candidates(root, team):
        if keep is not None and (kind == "quick" or (epic is not None and epic not in keep)):
            continue
        gate = None if kind == "quick" and not team_core.has_policy("ship", team) else _GATES[kind]
        row: dict[str, Any] = {"gate": gate, "branch": branch, "url": "", "author": "", "epic": epic,
                               "approvals": [], "missing": [], "notes": []}
        try:
            found = team_host.pr_for_branch(team.host, branch, root)
            reached = True
            if found is None or found.state != "open":
                continue
            row["url"] = found.url
            # simplified: a gate row fetches its PR here and again in verify_gate; pass the PrInfo to verify_gate
            # if the host calls become a cost.
            pr = team_host.fetch_pr(found.url, team.host, root)
            row.update(author=pr.author, approvals=list(dict.fromkeys(login for login, _ in pr.approvals)))
            text = None
            if kind in ("spec", "plan"):
                documents = branch_documents(root, branch, pr.files)
                row["epic"] = next((match[1] for match in map(_EPIC_LINE.search, documents.values()) if match), None)
                text = documents.get(team_core.resolve_artifact(pr, root, row["gate"], None))
            if row["gate"]:
                _, _, row["missing"], epic_kind = team_core.verify_gate(
                    root, team, row["gate"], found.url, notes=row["notes"], workflow_id=row["epic"], before_merge=True,
                    artifact_text=text)
                if team_core.policy_for(team, row["gate"], epic_kind) == team_core.HOST:
                    row["notes"].append("approvals: host")
        except (HostUnavailable, TeamError) as error:
            if isinstance(error, HostUnavailable) and not reached:
                raise
            row["error"] = str(error)
        if keep is None or row["epic"] in keep:
            rows.append(row)
    return rows
