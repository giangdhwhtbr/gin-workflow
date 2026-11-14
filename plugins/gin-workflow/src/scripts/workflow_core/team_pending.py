"""`gin team pending`: open gate pull requests and track pull requests, with what each still needs."""

from __future__ import annotations

from pathlib import Path
import re
import subprocess
from typing import Any, Sequence

from . import tasks, team as team_core, team_host
from .team import TeamConfig, TeamError
from .team_host import HostUnavailable

_TRACK_LINE = re.compile(r"^Plan:\s*`?([^`,\n]+?)`?,\s*Track\s+(\d+)\b", re.MULTILINE)
_EPIC_LINE = re.compile(r"^(?:Epic|Workflow):\s*(\S+)", re.MULTILINE)
_GATES = {"spec": "requirement_confirmed", "plan": "plan_approved", "ship": "ship", "track": None}


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
    """The plan file stem without a leading `YYYY-MM-DD-`."""
    return re.sub(r"^\d{4}-\d{2}-\d{2}-", "", Path(plan_path).stem)


def candidates(root: Path, team: TeamConfig) -> list[tuple[str, str, str | None]]:
    """(branch, kind, epic) in text order: remote `spec/*` and `plan/*` heads (epic read later), `feat/<topic>` per
    open epic with track beads of any status when the ship gate has roles, and `feat/<topic>-t<N>` per open track
    bead."""
    heads = [line.split("\trefs/heads/", 1)[1] for line in git(root, "ls-remote", "--heads", "origin").splitlines()
             if "\trefs/heads/" in line]
    found: list[tuple[str, str, str | None]] = [(head, "spec", None) for head in heads if head.startswith("spec/")]
    found += [(head, "plan", None) for head in heads if head.startswith("plan/")]
    beads = _beads(root, ["list", "--all", "--limit", "0"])  # closed tracks still name the ship branch
    live = {bead["id"] for bead in beads if bead.get("status") in ("open", "in_progress")}
    tracks: dict[str, str] = {}
    topics: dict[str, str] = {}
    for bead in beads:
        match = _TRACK_LINE.search(bead.get("description") or "")
        epic = bead.get("parent")
        if not (epic and match):
            continue
        topic = topic_of(match[1])
        if bead["id"] in live:
            tracks[f"feat/{topic}-t{match[2]}"] = epic
        if epic in live:
            topics.setdefault(epic, topic)
    if team_core.gate_roles("ship", team):
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
    policy gives before merge, with the branch's spec or plan text as the artifact; track rows only their approvers.
    A host failure before any host call has succeeded raises; after that, a failed lookup gives its row `error`."""
    keep = {workflow_id} if workflow_id else None
    if milestone:
        keep = {bead["id"] for bead in _beads(root, ["list", "--parent", milestone, "--type", "epic", "--limit", "0"])}
    rows: list[dict[str, Any]] = []
    reached = False  # a host call succeeded, so a later host failure belongs to its row
    for branch, kind, epic in candidates(root, team):
        if keep is not None and epic is not None and epic not in keep:
            continue
        row: dict[str, Any] = {"gate": _GATES[kind], "branch": branch, "url": "", "author": "", "epic": epic,
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
                row["missing"] = team_core.verify_gate(root, team, row["gate"], found.url, notes=row["notes"],
                                                       workflow_id=row["epic"], before_merge=True,
                                                       artifact_text=text)[2]
        except (HostUnavailable, TeamError) as error:
            if isinstance(error, HostUnavailable) and not reached:
                raise
            row["error"] = str(error)
        if keep is None or row["epic"] in keep:
            rows.append(row)
    return rows
