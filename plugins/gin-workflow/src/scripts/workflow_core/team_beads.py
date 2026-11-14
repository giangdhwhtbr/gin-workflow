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
from .team import Area, Member, TeamConfig, TeamError
from .team_pending import _TRACK_LINE, topic_of

_EXTERNAL = re.compile(r"^external: (\S+)#(\d+)$")
_PLAN_LINE = re.compile(r"^Plan:\s*`?([^`\s]+)`?\s*$", re.M)
_REPO_LINE = re.compile(r"^Repo:\s*`?([^`\s]+)`?\s*$", re.M)
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

    for issue in tasks.without_held(_bd_json(root, ["ready", "--exclude-type", "milestone"]), held):
        labels = issue.get("labels") or []
        if any(label in excluded for label in labels):
            continue
        matches, assignee, areas, released = _matches_target(issue)
        if matches:
            ready_group.append({
                "id": issue["id"], "title": issue.get("title", ""), "assignee": assignee,
                "areas": areas, "released": released, "priority": issue.get("priority"),
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
            })
            seen.add(issue["id"])

    ready_group.sort(key=_row_priority_key)

    now = utc_now()
    expired_group: list[dict[str, Any]] = []
    for issue in tasks.without_held(_bd_json(root, ["list", "--status", "in_progress"]), held):
        labels = issue.get("labels") or []
        if any(label in excluded for label in labels):
            continue
        assignee = (issue.get("assignee") or "").lower()
        areas = {label[5:] for label in labels if label.startswith("area:")}
        if issue["id"] not in seen and assignee and assignee != member.email and claim_expired(issue, now) \
                and (areas & mine or (not areas and not team.areas)):
            expired_group.append({
                "id": issue["id"], "title": issue.get("title", ""), "assignee": assignee,
                "areas": sorted(areas), "expired_claim": assignee, "priority": issue.get("priority"),
            })
            seen.add(issue["id"])

    expired_group.sort(key=_row_priority_key)

    return ready_group + expired_group


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


def track_of(issue: Mapping[str, Any]) -> tuple[str, int, str | None] | None:
    """(topic, track number, `Repo:` path or None) from the description; None without `Plan: <path>, Track <N>`."""
    body = str(issue.get("description") or "")
    track = _TRACK_LINE.search(body)
    if track is None:
        return None
    repo = _REPO_LINE.search(body)
    return topic_of(track[1]), int(track[2]), repo[1] if repo else None


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


def _track_place(root: Path, track: tuple[str, int, str | None]) -> tuple[Path, workspace.Repo | None, str]:
    """(repository, workspace entry or None, branch `feat/<topic>-t<N>`); refuses a `Repo:` or a branch name git
    would not accept, so claim can check both before the lease."""
    topic, number, repo = track
    repo_dir, entry = _track_repo(root, repo)
    branch = f"feat/{topic}-t{number}"
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


def track_worktree(root: Path, issue: Mapping[str, Any], bead: str) -> dict[str, Any] | None:
    """The worktree `.planning/worktrees/<bead>` on `feat/<topic>-t<N>` in the track's repository: kept when it
    exists, else checked out from the local or `origin` branch, else created from `origin/<default>`; None for a
    bead without a `Plan: <path>, Track <N>` line."""
    track = track_of(issue)
    if track is None:
        return None
    repo_dir, entry, branch = _track_place(root, track)
    try:
        target = worktrees._target(repo_dir, bead, root)
        if target.exists():
            if not _worktree_of(target, repo_dir):
                raise SyncConflict(f"{target} is not a worktree of {repo_dir}; remove it")
            return {"worktree": str(target), "branch": worktrees._git(target, "rev-parse", "--abbrev-ref", "HEAD"),
                    "created": False}
        if worktrees._git(repo_dir, "branch", "--list", branch):
            worktrees.checkout(repo_dir, bead, branch, root)
        elif worktrees._git(repo_dir, "ls-remote", "--heads", "origin", f"refs/heads/{branch}"):
            worktrees._git(repo_dir, "fetch", "origin", branch)
            worktrees.checkout(repo_dir, bead, branch, root)
        else:
            default = default_branch(repo_dir, entry)
            worktrees._git(repo_dir, "fetch", "origin", default)
            worktrees.create(repo_dir, bead, branch, f"origin/{default}", root)
    except (RuntimeError, ValueError) as error:
        raise SyncConflict(str(error)) from error
    return {"worktree": str(target), "branch": branch, "created": True}


def claim(root: Path, team: TeamConfig, member: Member, bead: str) -> dict[str, Any]:
    """Claim or renew a bead; an expired lease held by someone else is taken over with a note."""
    if team.beads_remote:
        sync(root)
    issue = _show(root, bead)
    released = RELEASED in (issue.get("labels") or [])
    ineligible = [] if released else [area.name for area in _areas_of(team, issue) if not team.eligible(member, area)]
    if ineligible:
        raise SyncConflict(f"{member.email} may not own tracks in {', '.join(ineligible)}")
    track = track_of(issue)
    if track is not None:
        _track_place(root, track)  # an unusable child or branch name refuses before the lease
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
    try:
        made = track_worktree(root, issue, bead)
    except SyncConflict as error:
        raise SyncConflict(f"{error}; the claim is kept; run gin team claim {bead} again") from error
    return {"status": "renewed" if holder == member.email else "claimed", "bead": bead, "assignee": member.email,
            "expires_at": expires_at, "advisory": not team.beads_remote, **(made or {})}


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
    _write_reassign(root, team, member, bead, holder, target)
    _push(root, team, bead)
    return {"status": "reassigned", "bead": bead, "from": holder, "assignee": target.email}


def _write_reassign(root: Path, team: TeamConfig, member: Member, bead: str, holder: str, target: Member) -> None:
    note = f"reassigned {holder or 'nobody'} -> {target.email} by {member.email}"
    completed = _bd(root, ["update", bead, "--assignee", target.email, "--append-notes", note,
                           "--set-metadata", f'claim={json.dumps({"holder": target.email, "expires_at": _expires(team)})}'], actor=member.email)
    if completed.returncode != 0:
        raise SyncConflict(completed.stderr.strip() or completed.stdout.strip())


def handoff_of(issue: Mapping[str, Any]) -> dict[str, Any]:
    return metadata_json(issue, "handoff")


def _track_worktree(root: Path, bead: str, worktree: str | None) -> Path:
    path = Path(worktree).resolve() if worktree else worktrees._target(root, bead)
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
    """Push the parent branch that holds a workspace child track's ledger: when it has commits its upstream lacks,
    or when it is a `feat/` branch without an upstream."""
    root = workspace.ledger_root(worktree)
    if root.resolve() == worktree.resolve():
        return
    try:
        branch = worktrees._git(root, "rev-parse", "--abbrev-ref", "HEAD")
    except RuntimeError as error:
        raise SyncConflict(f"cannot read the branch of {root}, which holds the review ledger: {error}") from error
    try:
        push = int(worktrees._git(root, "rev-list", "--count", "@{u}..HEAD")) > 0
    except RuntimeError:  # no upstream
        push = branch.startswith("feat/")
    if push:
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


def handoff(root: Path, team: TeamConfig, member: Member, bead: str, *, email: str | None = None,
            release: bool = False, worktree: str | None = None) -> dict[str, Any]:
    """Push the track branch and review ref, record the branch on the bead, then reassign or release it."""
    from review_ledger.git_adapter import GitAdapterError, push_review_ref

    if bool(email) == release:
        raise TeamError("pass exactly one of <email> or --release")
    path = _track_worktree(root, bead, worktree)
    try:
        dirty = worktrees._git(path, "status", "--porcelain")
    except RuntimeError as error:
        raise SyncConflict(f"{path} is not a git worktree: {error}") from error
    if dirty:
        raise SyncConflict(f"{bead}: uncommitted changes in {path}:\n{dirty}")
    if team.beads_remote:
        sync(root)
    issue = _show(root, bead)
    holder = (issue.get("assignee") or "").lower()
    target = None
    if email:
        holder, target = _reassign_target(team, member, bead, issue, email)
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
    ref = _ledger_ref(path, bead)
    if _local_ref(path, ref):
        try:
            push_review_ref(str(path), ref)
        except GitAdapterError as error:
            raise SyncConflict(f"review ref push failed for {ref}: {error}") from error
    elif _ledger_file(path, bead).is_file():
        print(f"no local review ref {ref} for {bead}; nothing to push", file=sys.stderr)
    else:
        print(f"no review ledger for {bead}", file=sys.stderr)
    _push_ledger_branch(path)
    meta = json.dumps({"branch": branch, "from": member.email, "to": target.email if target else None, "at": utc_now()})
    completed = _bd(root, ["update", bead, "--set-metadata", f"handoff={meta}"], actor=member.email)
    if completed.returncode != 0:
        raise SyncConflict(completed.stderr.strip() or completed.stdout.strip())
    if target:
        _write_reassign(root, team, member, bead, holder, target)
    else:
        completed = _bd(root, ["update", bead, "--assignee", "", "--status", "open", "--unset-metadata", "claim",
                               "--add-label", RELEASED, "--append-notes", f"released to the pool by {member.email}"],
                        actor=member.email)
        if completed.returncode != 0:
            raise SyncConflict(completed.stderr.strip() or completed.stdout.strip())
    _push(root, team, bead)
    print(f"next: gin team takeover {bead}", file=sys.stderr)
    result: dict[str, Any] = {"status": "handed-off" if target else "released", "bead": bead, "branch": branch}
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
    try:
        worktrees._git(repo_dir, "fetch", "origin", branch)
        path = worktrees.checkout(repo_dir, bead, branch, root)
    except (RuntimeError, ValueError) as error:
        raise SyncConflict(str(error)) from error
    try:
        ref = _ledger_ref(path, bead)
        if ref.startswith("refs/gin/review/"):
            try:
                worktrees._git(path, "fetch", "origin", f"+{ref}:{ref}")
            except RuntimeError:
                print(f"no review ref {ref} on origin for {bead}", file=sys.stderr)
        else:
            print(f"ignoring review ref {ref} from the ledger: not under refs/gin/review/", file=sys.stderr)
        result = claim(root, team, member, bead)
    except SyncConflict as error:
        raise SyncConflict(f"{error}; worktree left at {path}; remove it with gin worktree cleanup {bead}") from error
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
