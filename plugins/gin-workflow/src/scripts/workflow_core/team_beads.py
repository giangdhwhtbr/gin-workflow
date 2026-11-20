"""Team Beads operations: my ready work, claims, cross-member placeholders, optional Dolt sync."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Mapping, Sequence

from . import tasks, workspace, worktrees
from .executables import tool
from .prep import is_prep
from .team import Area, Member, TeamConfig, TeamError, plan_tracks
from .team_pending import _TRACK_LINE, lane_branch, topic_of, track_lane

_EXTERNAL = re.compile(r"^external: (\S+)#(\d+)$")
_PLAN_LINE = re.compile(r"^Plan:\s*`?([^`\s]+)`?\s*$", re.M)
_REPO_LINE = re.compile(r"^Repo:\s*`?([^`\s]+)`?\s*$", re.M)
_TRACKS_LINE = re.compile(r"^Tracks:\s*([\d,\s]+)$", re.M)
RELEASED = "released"


class SyncConflict(Exception):
    """Dolt reported a merge conflict or a rejected push: exit 1, nothing forced."""


# bd dolt pull/push talk to the Beads remote; on Windows one can take several minutes.
DOLT_TIMEOUT = 1000


def _bd(root: Path, argv: list[str], *, actor: str = "", timeout: int = 120) -> subprocess.CompletedProcess:
    executable = tool("bd", root)
    if executable is None:
        raise TeamError("bd is not installed")
    env = {**os.environ, "BD_ACTOR": actor} if actor else None
    try:
        return subprocess.run([executable, *argv], cwd=root, text=True, capture_output=True, check=False,
                              env=env, timeout=timeout)
    except subprocess.TimeoutExpired as error:
        raise TeamError(f"bd {' '.join(argv)} timed out after {timeout}s") from error


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


def _row_priority_key(row: dict[str, Any]) -> tuple[int, str]:
    priority = row.get("priority")
    if priority is not None:
        try:
            return (int(priority), str(row["id"]))
        except (ValueError, TypeError):
            pass
    return (99, str(row["id"]))


def ready(root: Path, team: TeamConfig, member: Member, exclude: Sequence[str] = ()) -> list[dict[str, Any]]:
    mine = set(team.areas_for(member))
    held = tasks.held_by_external(root, tool("bd", root) or "bd")
    if held is None:
        raise TeamError("bd ready --explain failed, so external dependencies cannot be checked")
    excluded = {part.strip() for val in exclude for part in val.split(",") if part.strip()}
    ready_group: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _matches_target(issue: Mapping[str, Any]) -> tuple[bool, str, list[str], bool]:
        assignee = (issue.get("assignee") or "").lower()
        labels = issue.get("labels") or []
        areas = {label[5:] for label in labels if label.startswith("area:")}
        released = RELEASED in labels
        matches = bool(
            assignee == member.email
            or (not assignee and (released or areas & mine or (not areas and not team.areas)))
        )
        return matches, assignee, sorted(areas), released

    now = utc_now()
    expired_group: list[dict[str, Any]] = []

    def _expired_row(issue: Mapping[str, Any], assignee: str, areas: Sequence[str]) -> dict[str, Any]:
        return {"id": issue["id"], "title": issue.get("title", ""), "assignee": assignee, "areas": sorted(areas),
                "expired_claim": assignee, "priority": issue.get("priority"), "lane": lane_of(issue),
                "branch": lane_branch(str(issue.get("description") or ""))}

    for issue in tasks.without_held(_bd_json(root, ["ready", "--exclude-type", "milestone"]), held):
        labels = issue.get("labels") or []
        if any(label in excluded for label in labels):
            continue
        matches, assignee, areas, released = _matches_target(issue)
        if not matches and assignee and claim_of(issue) and claim_expired(issue, now) and (set(areas) & mine or (not areas and not team.areas)):
            expired_group.append(_expired_row(issue, assignee, areas))
            seen.add(issue["id"])
            continue
        if matches:
            ready_group.append({
                "id": issue["id"], "title": issue.get("title", ""), "assignee": assignee,
                "areas": areas, "released": released, "priority": issue.get("priority"),
                "lane": lane_of(issue), "branch": lane_branch(str(issue.get("description") or "")),
            })
            seen.add(issue["id"])

    blocked = _bd_json(root, ["blocked"])
    preps = {row["id"]: row for row in _bd_json(root, ["list", "--label", "prep", "--status", "open", "--limit", "0"])}
    for b_row in blocked:
        bid = b_row.get("id")
        if bid not in preps:
            continue
        prep_row = preps[bid]
        parent = prep_row.get("parent")
        if not parent or b_row.get("blocked_by") != [parent]:
            continue
        if not is_prep(prep_row):
            continue
        if any(dep.get("type") == "blocks" for dep in prep_row.get("dependencies") or []):
            continue
        issue = {**b_row, **prep_row}
        labels = issue.get("labels") or []
        if any(label in excluded for label in labels):
            continue
        if issue["id"] in seen:
            continue
        matches, assignee, areas, released = _matches_target(issue)
        if matches:
            ready_group.append({
                "id": issue["id"], "title": issue.get("title", ""), "assignee": assignee,
                "areas": areas, "released": released, "priority": issue.get("priority"),
                "lane": lane_of(issue), "branch": lane_branch(str(issue.get("description") or "")),
            })
            seen.add(issue["id"])

    ready_group.sort(key=_row_priority_key)

    for issue in tasks.without_held(_bd_json(root, ["list", "--status", "in_progress"]), held):
        labels = issue.get("labels") or []
        if any(label in excluded for label in labels):
            continue
        assignee = (issue.get("assignee") or "").lower()
        areas = {label[5:] for label in labels if label.startswith("area:")}
        if issue["id"] not in seen and assignee and assignee != member.email and claim_expired(issue, now) \
                and (areas & mine or (not areas and not team.areas)):
            expired_group.append(_expired_row(issue, assignee, areas))
            seen.add(issue["id"])

    expired_group.sort(key=_row_priority_key)

    return ready_group + expired_group


def _dolt(root: Path, step: str) -> subprocess.CompletedProcess:
    """`bd dolt <step>` with the long timeout, announced on stderr so a slow remote does not look like a hang."""
    print(f"bd dolt {step} (up to {DOLT_TIMEOUT}s)...", file=sys.stderr, flush=True)
    return _bd(root, ["dolt", step], timeout=DOLT_TIMEOUT)


def sync(root: Path) -> dict[str, Any]:
    for step in ("pull", "push"):
        completed = _dolt(root, step)
        if completed.returncode != 0:
            message = (completed.stderr or completed.stdout).strip()
            if step == "pull" and "no branches found" in message:
                continue  # first sync: the remote holds no Beads data yet
            if "conflict" in message.lower() or (step == "push" and "pull" in message.lower()):
                raise SyncConflict(f"bd dolt {step}: {message}")
            raise TeamError(f"bd dolt {step} failed: {message}")
    return {"status": "synced"}


def track_of(issue: Mapping[str, Any]) -> tuple[str, int, str | None] | None:
    """(topic, track number, `Repo:` path or None) from the description; None without `Plan: <path>, Track <N>`."""
    body = str(issue.get("description") or "")
    track = _TRACK_LINE.search(body)
    if track is None:
        return None
    repo = _REPO_LINE.search(body)
    return topic_of(track[1]), int(track[2]), repo[1] if repo else None


def _lane(issue: Mapping[str, Any]) -> tuple[str, int, str, bool] | None:
    return track_lane(str(issue.get("description") or ""))


def lane_of(issue: Mapping[str, Any]) -> str | None:
    """The lane of a track bead: its `Lane:` line, else the implicit `t<N>`; None for a bead that is no track."""
    found = _lane(issue)
    return found[2] if found else None


def lane_beads(root: Path, issue: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The track beads of `issue`'s lane, any status: the children of its epic with the same plan path and
    lane. Just `issue` for a bead that is no track or has no parent."""
    own, epic = _lane(issue), issue.get("parent")
    if own is None or not epic:
        return [dict(issue)]
    rows = [row for row in _bd_json(root, ["list", "--parent", str(epic), "--all", "--limit", "0"])
            if (found := _lane(row)) is not None and (found[0], found[2]) == (own[0], own[2])]
    return rows if any(row["id"] == issue["id"] for row in rows) else [dict(issue), *rows]


def _lane_targets(root: Path, issue: Mapping[str, Any],
                  beads: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """`issue`, then the other open tracks of its lane in track order: what a lane command writes to. `beads` is
    the lane when the caller has read it already."""
    lane = lane_beads(root, issue) if beads is None else beads
    others = [row for row in lane if row["id"] != issue["id"] and row.get("status") != "closed"]
    return [dict(issue), *sorted(others, key=lambda row: (_lane(row) or ("", 0))[1])]


def _lane_key(issue: Mapping[str, Any], bead: str) -> str:
    """The worktree id of the bead's lane: `<epic>-<lane>` for a named lane, else the bead id."""
    found, epic = _lane(issue), issue.get("parent")
    return f"{epic}-{found[2]}" if found and found[3] and epic else bead


def default_branch(repo: Path, entry: workspace.Repo | None) -> str:
    """A child's `default_branch`; else the branch `origin/HEAD` of `repo` names; else `main`."""
    if entry is not None:
        return entry.default_branch
    try:
        head = worktrees._git(repo, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    except RuntimeError:
        return "main"
    return head.removeprefix("origin/") or "main"


def _track_repo(root: Path, repo: str | None) -> tuple[Path, workspace.Repo | None]:
    """The track's repository: the cloned, workable workspace child its `Repo:` names, else `root`."""
    if repo is None:
        return root, None
    space = workspace.locate(root).workspace
    entry = space.repo(repo) if space is not None else None
    if entry is None:
        raise SyncConflict(f"Repo: {repo} is not in workspace.repos")
    if entry.frozen:
        raise SyncConflict(f"Repo: {repo} is frozen")
    if entry.shape == "beads":
        raise SyncConflict(f"Repo: {repo} is the beads repository")
    if not space.present(entry):
        raise SyncConflict(f"{repo} is not cloned; run gin workspace clone {repo}")
    return space.checkout(entry), entry


def _track_place(root: Path, track: tuple[str, int, str | None],
                 lane: str) -> tuple[Path, workspace.Repo | None, str]:
    """(repository, workspace entry or None, branch `feat/<topic>-<lane>`); refuses a `Repo:` or a branch name git
    would not accept, so claim can check both before the lease."""
    topic, _number, repo = track
    repo_dir, entry = _track_repo(root, repo)
    branch = f"feat/{topic}-{lane}"
    try:
        worktrees._git(repo_dir, "check-ref-format", "--branch", branch)
    except RuntimeError as error:
        raise SyncConflict(f"invalid track branch {branch!r} from the Plan: line: {error}") from error
    return repo_dir, entry, branch


def _worktree_of(target: Path, repo_dir: Path) -> bool:
    """True when `target` is the top of a worktree that shares the git directory of `repo_dir`."""
    try:
        top, common = worktrees._git(target, "rev-parse", "--path-format=absolute", "--show-toplevel",
                                     "--git-common-dir").splitlines()
    except (RuntimeError, ValueError):  # not inside a git repository, or not the two lines asked for
        return False
    own = worktrees._git(repo_dir, "rev-parse", "--path-format=absolute", "--git-common-dir")
    return Path(top).resolve() == target.resolve() and Path(common).resolve() == Path(own).resolve()


def _restart_delivered(team: TeamConfig, repo_dir: Path, entry: workspace.Repo | None, target: Path,
                       branch: str) -> str | None:
    """Start `branch` again from `origin/<default>` in the worktree `target` when its newest pull request has
    merged and the branch still sits on that pull request's head. Returns what happened, a warning when the
    branch has commits made after the merged head, or None when there is nothing to do. A host that cannot be
    reached leaves the branch as it is."""
    from . import team_host

    try:
        found = team_host.pr_for_branch(team.host, branch, repo_dir)
        if found is None or found.state != "merged":
            return None
        merged_head = team_host.fetch_pr(found.url, team.host, repo_dir).head_sha
    except team_host.HostUnavailable as error:
        return f"cannot ask the host whether {branch} has merged: {error}"
    default = default_branch(repo_dir, entry)
    worktrees._git(repo_dir, "fetch", "origin", default)
    if worktrees._git(target, "rev-parse", "HEAD") == merged_head:
        if worktrees._git(target, "status", "--porcelain"):
            raise SyncConflict(f"{target} has uncommitted changes; commit or remove them, then claim again")
        worktrees._git(target, "checkout", "-B", branch, f"origin/{default}")
        return (f"{branch} restarted from origin/{default} after {found.url} merged; if the host kept the "
                f"merged branch, delete it on origin before the next push")
    if found.merge_commit:
        try:
            worktrees._git(target, "merge-base", "--is-ancestor", found.merge_commit, "HEAD")
            return None  # the merged pull request is already in the branch: restarted earlier, or merged in
        except RuntimeError:  # not an ancestor, or not in this clone
            pass
    try:
        worktrees._git(target, "merge-base", "--is-ancestor", merged_head, "HEAD")
    except RuntimeError:  # restarted earlier, or the merged head is not in this clone
        return None
    if worktrees._git(target, "rev-list", "--count", f"{merged_head}..HEAD", f"^origin/{default}") != "0":
        return f"{branch} has commits after its merged pull request {found.url}; merge origin/{default} into it"
    return None


def track_worktree(root: Path, team: TeamConfig, issue: Mapping[str, Any], bead: str, *,
                   delivered: bool = False) -> dict[str, Any] | None:
    """The lane's worktree (`.planning/worktrees/<epic>-<lane>`, or `<bead>` for the implicit lane) on
    `feat/<topic>-<lane>` in the track's repository: kept when it exists, else checked out from the local or
    `origin` branch, else created from `origin/<default>`. When `delivered`, a worktree that exists or was just
    checked out from a branch is restarted from `origin/<default>` if its pull request merged; the result of that
    restart is the `note`. None for a bead without a `Plan: <path>, Track <N>` line."""
    track, lane = track_of(issue), lane_of(issue)
    if track is None or lane is None:
        return None
    repo_dir, entry, branch = _track_place(root, track, lane)
    key = _lane_key(issue, bead)
    try:
        target = worktrees._target(repo_dir, key, root)
        if target.exists():
            if not _worktree_of(target, repo_dir):
                raise SyncConflict(f"{target} is not a worktree of {repo_dir}; remove it")
            note = _restart_delivered(team, repo_dir, entry, target, branch) if delivered else None
            made = {"worktree": str(target), "branch": worktrees._git(target, "rev-parse", "--abbrev-ref", "HEAD"),
                    "created": False}
            return {**made, "note": note} if note else made
        if worktrees._git(repo_dir, "branch", "--list", branch):
            worktrees.checkout(repo_dir, key, branch, root)
        elif worktrees._git(repo_dir, "ls-remote", "--heads", "origin", f"refs/heads/{branch}"):
            worktrees._git(repo_dir, "fetch", "origin", branch)
            worktrees.checkout(repo_dir, key, branch, root)
        else:
            default = default_branch(repo_dir, entry)
            worktrees._git(repo_dir, "fetch", "origin", default)
            worktrees.create(repo_dir, key, branch, f"origin/{default}", root)
            return {"worktree": str(target), "branch": branch, "created": True}
        note = _restart_delivered(team, repo_dir, entry, target, branch) if delivered else None
    except (RuntimeError, ValueError) as error:
        raise SyncConflict(str(error)) from error
    made = {"worktree": str(target), "branch": branch, "created": True}
    return {**made, "note": note} if note else made


def claim(root: Path, team: TeamConfig, member: Member, bead: str) -> dict[str, Any]:
    """Claim or renew the lane of a bead: one lease on every open track of it, the named bead `in_progress`; an
    expired lease held by someone else is taken over with a note."""
    if team.beads_remote:
        sync(root)
    issue = _show(root, bead)
    own = _lane(issue)
    lane = lane_beads(root, issue)
    targets = _lane_targets(root, issue, lane)
    now = utc_now()
    for target in targets:
        labels = target.get("labels") or []
        ineligible = [] if RELEASED in labels else [area.name for area in _areas_of(team, target)
                                                    if not team.eligible(member, area)]
        if ineligible:
            raise SyncConflict(f"{member.email} may not own tracks in {', '.join(ineligible)}")
        holder = (target.get("assignee") or "").lower()
        if holder and holder != member.email and not claim_expired(target, now):
            until = claim_of(target)["expires_at"]
            raise SyncConflict(f"lane {own[2]} is claimed by {holder} until {until} ({target['id']})"
                               if own and own[3] else f"{bead} is already claimed by {holder} until {until}")
    track = track_of(issue)
    if track is not None:
        _track_place(root, track, own[2])  # an unusable child or branch name refuses before the lease
    named_holder = (issue.get("assignee") or "").lower()
    expires_at = _expires(team)
    lease = json.dumps({"holder": member.email, "expires_at": expires_at})
    for target in targets:
        holder = (target.get("assignee") or "").lower()
        if target["id"] == bead and not holder:
            argv = ["update", bead, "--claim"]
        else:
            argv = ["update", target["id"], "--assignee", member.email]
            if target["id"] == bead:
                argv += ["--status", "in_progress"]
            if holder and holder != member.email:
                argv += ["--append-notes", f"took over expired claim from {holder}"]
        argv += ["--set-metadata", f"claim={lease}"]
        if RELEASED in (target.get("labels") or []):
            argv += ["--remove-label", RELEASED]
        completed = _bd(root, argv, actor=member.email)
        if completed.returncode != 0:
            raise SyncConflict(completed.stderr.strip() or completed.stdout.strip())
    _push(root, team, bead)
    delivered = any(row.get("status") == "closed" for row in lane)
    try:
        made = track_worktree(root, team, issue, bead, delivered=delivered)
    except SyncConflict as error:
        raise SyncConflict(f"{error}; the claim is kept; run gin team claim {bead} again") from error
    return {"status": "renewed" if named_holder == member.email else "claimed", "bead": bead,
            "lane": own[2] if own else None, "beads": [target["id"] for target in targets],
            "assignee": member.email, "expires_at": expires_at, "advisory": not team.beads_remote, **(made or {})}


def push(root: Path, team: TeamConfig) -> None:
    """Push local Beads without ever resetting them: a rejected push leaves the local write in place."""
    if team.beads_remote:
        pushed = _dolt(root, "push")
        if pushed.returncode != 0:
            raise SyncConflict(f"bd dolt push: {(pushed.stderr or pushed.stdout).strip()}")


def _push(root: Path, team: TeamConfig, bead: str) -> None:
    """Push the local write; a rejected push syncs once and retries. Local Beads are never reset."""
    if not team.beads_remote:
        return
    try:
        if _dolt(root, "push").returncode == 0:
            return
    except TeamError as error:
        raise SyncConflict(f"push of {bead} failed; local Beads kept, run gin team sync ({error})") from error
    try:
        sync(root)
    except (SyncConflict, TeamError) as error:
        raise SyncConflict(f"push rejected for {bead}; local Beads kept, run gin team sync ({error})") from error


def _reassign_target(team: TeamConfig, member: Member, bead: str, issue: Mapping[str, Any], email: str) -> tuple[str, Member]:
    """(holder, target) after the reassign rules: authority, open bead, member target, eligible target."""
    target = team.member(email)
    if target is None:
        raise TeamError(f"{email} is not a team member")
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
    return holder, target


def reassign(root: Path, team: TeamConfig, member: Member, bead: str, email: str) -> dict[str, Any]:
    """Hand a track to another member: only the current assignee or the lead of one of its areas may."""
    if team.member(email) is None:
        raise TeamError(f"{email} is not a team member")
    if team.beads_remote:
        sync(root)
    issue = _show(root, bead)
    holder, target = _reassign_target(team, member, bead, issue, email)
    targets = _lane_targets(root, issue)
    _check_lane_owner(team, target, targets[1:])
    for row in targets:
        if row["id"] == bead or (row.get("assignee") or "").lower() != target.email:
            _write_reassign(root, team, member, row["id"], (row.get("assignee") or "").lower(), target)
    _push(root, team, bead)
    return {"status": "reassigned", "bead": bead, "from": holder, "assignee": target.email,
            "lane": lane_of(issue), "beads": [row["id"] for row in targets]}


def _check_lane_owner(team: TeamConfig, target: Member, rows: Sequence[Mapping[str, Any]]) -> None:
    """Refuse before any write when `target` may not own tracks in an area of the other tracks of the lane."""
    for row in rows:
        ineligible = [area.name for area in _areas_of(team, row) if not team.eligible(target, area)]
        if ineligible:
            raise SyncConflict(f"{target.email} may not own tracks in {', '.join(ineligible)}")


def _write_reassign(root: Path, team: TeamConfig, member: Member, bead: str, holder: str, target: Member) -> None:
    note = f"reassigned {holder or 'nobody'} -> {target.email} by {member.email}"
    completed = _bd(root, ["update", bead, "--assignee", target.email, "--append-notes", note,
                           "--set-metadata", f'claim={json.dumps({"holder": target.email, "expires_at": _expires(team)})}'], actor=member.email)
    if completed.returncode != 0:
        raise SyncConflict(completed.stderr.strip() or completed.stdout.strip())


def handoff_of(issue: Mapping[str, Any]) -> dict[str, Any]:
    return metadata_json(issue, "handoff")


def _track_worktree(root: Path, key: str, bead: str, worktree: str | None) -> Path:
    path = Path(worktree).resolve() if worktree else worktrees._target(root, key)
    if not path.is_dir():
        raise SyncConflict(f"no worktree for {bead}; pass --worktree <path>")
    return path


def _ledger_file(worktree: Path, bead: str) -> Path:
    """The bead's review ledger: in the parent for a workspace child's track worktree, else in `worktree`."""
    return workspace.ledger_root(worktree) / ".planning/reviews" / bead / "review.json"


def _ledger_ref(worktree: Path, bead: str) -> str:
    """The review ref the bead's ledger names, else the default refs/gin/review/<bead>."""
    ledger = _ledger_file(worktree, bead)
    default = f"refs/gin/review/{bead}"
    if not ledger.is_file():
        return default
    try:
        repos = json.loads(ledger.read_text(encoding="utf-8")).get("repositories") or [{}]
        first = repos[0] if isinstance(repos, list) and repos and isinstance(repos[0], dict) else {}
    except (OSError, ValueError, AttributeError) as error:
        raise SyncConflict(f"cannot read review ledger {ledger}: {error}") from error
    return first.get("checkpoint_ref") or first.get("review_ref") or default


def _push_ledger_branch(worktree: Path) -> None:
    """Push the parent's `feat/` branch that holds a workspace child track's ledger: when it has commits its upstream
    lacks, or when it has no upstream. Any other branch with such commits is refused, never pushed."""
    root = workspace.ledger_root(worktree)
    if root.resolve() == worktree.resolve():
        return
    try:
        branch = worktrees._git(root, "rev-parse", "--abbrev-ref", "HEAD")
    except RuntimeError as error:
        raise SyncConflict(f"cannot read the branch of {root}, which holds the review ledger: {error}") from error
    try:
        ahead: int | None = int(worktrees._git(root, "rev-list", "--count", "@{u}..HEAD"))
    except RuntimeError:  # no upstream
        ahead = None
    if not branch.startswith("feat/"):
        if ahead:
            raise SyncConflict(f"{branch} in {root} has commits that are not pushed; commit the review ledger on the "
                               f"parent's feat/<topic> and hand off again")
        return  # nothing unpushed, or no upstream to compare with
    if ahead is None or ahead > 0:
        try:
            worktrees._git(root, "push", "-u", "origin", branch)
        except RuntimeError as error:
            raise SyncConflict(f"git push of {branch} in {root} failed: {error}") from error


def _pull_ledger_branch(root: Path) -> None:
    """`git pull --rebase` of the branch `root` is on when it has an upstream, so the ledger read next is current."""
    try:
        worktrees._git(root, "rev-parse", "--abbrev-ref", "@{u}")
    except RuntimeError:  # no upstream: nothing to pull
        return
    branch = worktrees._git(root, "rev-parse", "--abbrev-ref", "HEAD")
    try:
        worktrees._git(root, "pull", "--rebase")
    except RuntimeError as error:
        raise SyncConflict(f"git pull --rebase of {branch} in {root} failed: {error}") from error


def _local_ref(worktree: Path, ref: str) -> bool:
    try:
        worktrees._git(worktree, "rev-parse", "--verify", "--quiet", ref)
    except RuntimeError:
        return False
    return True


def _push_review_ref(path: Path, bead: str, push_review_ref: Any, error_type: type[Exception]) -> None:
    ref = _ledger_ref(path, bead)
    if _local_ref(path, ref):
        try:
            push_review_ref(str(path), ref)
        except error_type as error:
            raise SyncConflict(f"review ref push failed for {ref}: {error}") from error
    elif _ledger_file(path, bead).is_file():
        print(f"no local review ref {ref} for {bead}; nothing to push", file=sys.stderr)
    else:
        print(f"no review ledger for {bead}", file=sys.stderr)


def handoff(root: Path, team: TeamConfig, member: Member, bead: str, *, email: str | None = None,
            release: bool = False, worktree: str | None = None) -> dict[str, Any]:
    """Push the track branch and review ref, record the branch on the bead, then reassign or release it."""
    from review_ledger.git_adapter import GitAdapterError, push_review_ref

    if bool(email) == release:
        raise TeamError("pass exactly one of <email> or --release")
    if team.beads_remote:
        sync(root)
    issue = _show(root, bead)
    path = _track_worktree(root, _lane_key(issue, bead), bead, worktree)
    try:
        dirty = worktrees._git(path, "status", "--porcelain")
    except RuntimeError as error:
        raise SyncConflict(f"{path} is not a git worktree: {error}") from error
    if dirty:
        raise SyncConflict(f"{bead}: uncommitted changes in {path}:\n{dirty}")
    targets = _lane_targets(root, issue)
    holder = (issue.get("assignee") or "").lower()
    target = None
    if email:
        holder, target = _reassign_target(team, member, bead, issue, email)
        _check_lane_owner(team, target, targets[1:])
    else:
        if issue.get("status") == "closed":
            raise SyncConflict(f"{bead} is closed")
        areas = _areas_of(team, issue)
        if holder != member.email and not any(area.lead in member.roles for area in areas):
            raise SyncConflict(f"only {holder or 'an area lead'} or the lead of its area may release {bead}")
    branch = worktrees._git(path, "rev-parse", "--abbrev-ref", "HEAD")
    if branch == "HEAD":
        raise SyncConflict(f"{path} is on a detached HEAD; check out the track branch first")
    try:
        worktrees._git(path, "push", "-u", "origin", branch)
    except RuntimeError as error:
        raise SyncConflict(f"git push of {branch} failed: {error}") from error
    for row in targets:
        _push_review_ref(path, row["id"], push_review_ref, GitAdapterError)
    _push_ledger_branch(path)
    meta = json.dumps({"branch": branch, "from": member.email, "to": target.email if target else None, "at": utc_now()})
    for row in targets:
        completed = _bd(root, ["update", row["id"], "--set-metadata", f"handoff={meta}"], actor=member.email)
        if completed.returncode != 0:
            raise SyncConflict(completed.stderr.strip() or completed.stdout.strip())
        if target:
            _write_reassign(root, team, member, row["id"], (row.get("assignee") or "").lower(), target)
        else:
            completed = _bd(root, ["update", row["id"], "--assignee", "", "--status", "open", "--unset-metadata",
                                   "claim", "--add-label", RELEASED, "--append-notes",
                                   f"released to the pool by {member.email}"], actor=member.email)
            if completed.returncode != 0:
                raise SyncConflict(completed.stderr.strip() or completed.stdout.strip())
    _push(root, team, bead)
    print(f"next: gin team takeover {bead}", file=sys.stderr)
    result: dict[str, Any] = {"status": "handed-off" if target else "released", "bead": bead, "branch": branch,
                              "lane": lane_of(issue), "beads": [row["id"] for row in targets]}
    if target:
        result["assignee"] = target.email
    return result


def takeover(root: Path, team: TeamConfig, member: Member, bead: str, *, branch: str | None = None) -> dict[str, Any]:
    """Fetch the handed-off branch in the track's repository (the bead's workspace `Repo:`, else `root`), check it
    out at .planning/worktrees/<bead>, fetch the review ref, claim."""
    git_dir = (root / worktrees._git(root, "rev-parse", "--git-dir")).resolve()
    common = (root / worktrees._git(root, "rev-parse", "--git-common-dir")).resolve()
    if team.beads_remote:
        sync(root)
    issue = _show(root, bead)
    track = track_of(issue)
    repo_dir, entry = _track_repo(root, track[2] if track else None)
    if entry is None and git_dir != common:
        raise SyncConflict("run gin team takeover from the main checkout, not a linked worktree")
    branch = branch or str(handoff_of(issue).get("branch") or "")
    if not branch:
        raise SyncConflict(f"no handoff branch recorded for {bead}; pass --branch <name>")
    if branch.startswith("-"):
        raise SyncConflict(f"refusing branch name {branch!r} from the handoff metadata: it starts with '-'")
    try:
        worktrees._git(root, "check-ref-format", "--branch", branch)
    except RuntimeError as error:
        raise SyncConflict(f"invalid branch name {branch!r} in the handoff metadata: {error}") from error
    if entry is not None:  # a workspace child's ledger lives on the parent's branch: read its latest state
        _pull_ledger_branch(root)
    key = _lane_key(issue, bead)
    try:
        worktrees._git(repo_dir, "fetch", "origin", branch)
        path = worktrees.checkout(repo_dir, key, branch, root)
    except (RuntimeError, ValueError) as error:
        raise SyncConflict(str(error)) from error
    try:
        for row in _lane_targets(root, issue):
            ref = _ledger_ref(path, row["id"])
            if ref.startswith("refs/gin/review/"):
                try:
                    worktrees._git(path, "fetch", "origin", f"+{ref}:{ref}")
                except RuntimeError:
                    print(f"no review ref {ref} on origin for {row['id']}", file=sys.stderr)
            else:
                print(f"ignoring review ref {ref} from the ledger: not under refs/gin/review/", file=sys.stderr)
        result = claim(root, team, member, bead)
    except SyncConflict as error:
        raise SyncConflict(f"{error}; worktree left at {path}; remove it with gin worktree cleanup {key}") from error
    print(f"next: gin team deps --bead {bead}", file=sys.stderr)
    return {**result, "branch": branch, "worktree": str(path), "created": True}


def _tracks_in(body: str) -> tuple[str, set[int]]:
    plan = _PLAN_LINE.search(body)
    tracks = _TRACKS_LINE.search(body)
    numbers = {int(item) for item in re.findall(r"\d+", tracks.group(1))} if tracks else set()
    return (plan.group(1) if plan else ""), numbers


def _delivers(body: str, plan: str, number: int) -> bool:
    named, numbers = _tracks_in(body)
    return named == plan and number in numbers


def _blocking_repo(root: Path, plan: str, number: int) -> tuple[Path, str | None]:
    """The repository of track `number` in `root / plan` and its `Repo:` path (`.` for the parent of a workspace);
    `(root, None)` outside a workspace, where the plan is not read. Raises SyncConflict when the plan or track is
    not in this checkout or the child is not workable."""
    if workspace.locate(root).workspace is None:
        return root, None
    path = (root / plan).resolve()
    try:
        tracks = plan_tracks(path) if path.is_relative_to(root.resolve()) else None
    except (OSError, UnicodeDecodeError):
        tracks = None
    if tracks is None:
        raise SyncConflict(f"{plan} is not in this checkout; pull the merged plan")
    track = next((track for track in tracks if track.number == number), None)
    if track is None:
        raise SyncConflict(f"track {number} is not in {plan}")
    return (_track_repo(root, track.repo)[0], track.repo) if track.repo else (root, ".")


def deps(root: Path, team: TeamConfig) -> dict[str, Any]:
    from .team_host import merged_with_text

    closed, waiting, unresolved, reasons = [], [], [], {}
    for issue in _bd_json(root, ["list", "--status", "open"]):
        match = _EXTERNAL.match(issue.get("title", ""))
        if not match:
            continue
        plan, number = match.group(1), int(match.group(2))
        try:
            repo_dir, repo = _blocking_repo(root, plan, number)
        except SyncConflict as error:
            waiting.append(issue["id"])
            reasons[issue["id"]] = str(error)
            continue
        found = next((pr for pr in merged_with_text(team.host, plan, repo_dir) if _delivers(pr.body, plan, number)), None)
        if found is None:
            waiting.append(issue["id"])
            continue
        if not found.merge_commit:
            unresolved.append({"id": issue["id"], "pr": found.url})
            continue
        noted = _bd(root, ["update", issue["id"], "--set-metadata", f"merge_commit={found.merge_commit}"]
                    + (["--set-metadata", f"repo={repo}"] if repo else []))
        if noted.returncode != 0:
            raise TeamError(f"bd update {issue['id']} failed: {noted.stderr.strip()}")
        done = _bd(root, ["close", issue["id"], "--reason", f"{found.url} merged ({found.merge_commit})"])
        if done.returncode != 0:
            raise TeamError(f"bd close {issue['id']} failed: {done.stderr.strip()}")
        closed.append({"id": issue["id"], "pr": found.url})
    return {"closed": closed, "waiting": waiting, "unresolved": unresolved, "reasons": reasons}


def _has_commit(repo: Path, commit: str, ref: str = "HEAD") -> bool:
    return bool(commit) and subprocess.run(["git", "merge-base", "--is-ancestor", commit, ref], cwd=repo,
                                           capture_output=True, check=False).returncode == 0


def _reach_reason(root: Path, here: str | None, repo: str | None, commit: str, cwd: Path) -> str:
    """Why `commit` is not reachable from the repository the placeholder names; "" when it is. `here` is the
    current repository (None for the parent); `repo` is the placeholder's `repo` (`.` parent, None unrecorded)."""
    if repo is None or repo == (here or "."):
        top = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=cwd, text=True, capture_output=True,
                             check=False).stdout.strip()
        if top and _has_commit(Path(top), commit):
            return ""
        return f"fetch/rebase onto the plan's integration branch to include {commit}"
    repo_dir, entry = _track_repo(root, None if repo == "." else repo)
    branch = default_branch(repo_dir, entry)
    ref = f"refs/remotes/origin/{branch}"
    if subprocess.run(["git", "rev-parse", "--verify", "--quiet", ref], cwd=repo_dir, capture_output=True,
                      check=False).returncode != 0:
        return f"origin/{branch} does not exist in {repo_dir}; run git -C {repo_dir} remote set-head origin -a"
    if _has_commit(repo_dir, commit, ref):
        return ""
    return f"{commit} is not on origin/{branch} of {repo_dir}; run git -C {repo_dir} fetch origin"


def deps_for(root: Path, bead: str, cwd: Path | None = None) -> dict[str, Any]:
    """The bead's `external:` placeholders: ok only when closed with its merge commit in this workspace."""
    cwd = Path.cwd() if cwd is None else cwd
    entry = workspace.locate(cwd).entry
    here = entry.path if entry is not None else None
    ok, missing = [], []
    for dep in _show(root, bead).get("dependencies") or []:
        match = _EXTERNAL.match(dep.get("title", ""))
        if not match:
            continue
        metadata = dep.get("metadata") or {}
        commit = str(metadata.get("merge_commit", ""))
        if dep.get("status") != "closed":
            missing.append({"id": dep["id"], "reason": f"{match.group(1)}#{match.group(2)} has not merged; run team deps"})
        elif not commit:
            missing.append({"id": dep["id"], "reason": "no merge commit recorded; run team deps"})
        else:
            try:
                reason = _reach_reason(root, here, metadata.get("repo") or None, commit, cwd)
            except SyncConflict as error:
                reason = str(error)
            if reason:
                missing.append({"id": dep["id"], "reason": reason})
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
