"""Team mode (schema 2.7): members, areas, identity, plan tracks, and role-gated approvals."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
import subprocess
from typing import Any, Mapping
from urllib.parse import urlparse

GATES = ("requirement_confirmed", "plan_approved", "verification_passed", "roadmap")
ROADMAP = {"legacy": ".planning/roadmap.md", "sdd": "docs/roadmap.md"}
DEFAULT_APPROVALS: dict[str, Any] = {"requirement_confirmed": [], "plan_approved": "area_lead",
                                     "verification_passed": []}
_WILDCARDS = re.compile(r"[*?\[]")


class TeamError(Exception):
    """Usage or configuration problem: exit 2."""


@dataclass(frozen=True)
class Member:
    email: str
    roles: tuple[str, ...]
    login: str


@dataclass(frozen=True)
class Area:
    name: str
    paths: tuple[str, ...]
    lead: str
    roles: tuple[str, ...] = ()


@dataclass(frozen=True)
class TeamConfig:
    host: str = "github"
    commit_convention: str = "conventional"
    members: Mapping[str, Member] = field(default_factory=dict)
    areas: Mapping[str, Area] = field(default_factory=dict)
    approvals: Mapping[str, Any] = field(default_factory=lambda: dict(DEFAULT_APPROVALS))
    beads_remote: str = ""

    def member(self, email: str) -> Member | None:
        return self.members.get(email.strip().lower())

    def by_login(self, login: str) -> Member | None:
        return next((m for m in self.members.values() if m.login.lower() == login.lower()), None)

    def eligible(self, member: Member, area: Area) -> bool:
        return not area.roles or area.lead in member.roles or bool(set(area.roles) & set(member.roles))

    def areas_for(self, member: Member) -> list[str]:
        return [name for name, area in self.areas.items() if self.eligible(member, area)]

    def area_of(self, path: str) -> str | None:
        from .rules import _glob_regex

        return next((name for name, area in self.areas.items()
                     if any(_glob_regex(glob).match(path) for glob in area.paths)), None)


def _literal_prefix(glob: str) -> str:
    match = _WILDCARDS.search(glob)
    return glob[:match.start()] if match else glob


def validate_team(raw: Mapping[str, Any]) -> list[str]:
    """Semantic rules the JSON schema cannot express; every finding is returned."""
    errors: list[str] = []
    members = raw.get("members") or {}
    areas = raw.get("areas") or {}
    held: set[str] = set()
    emails: dict[str, str] = {}
    logins: dict[str, str] = {}
    for email, spec in members.items():
        key = str(email).strip().lower()
        if key in emails:
            errors.append(f"team.members: duplicate email {email} (also {emails[key]})")
        emails[key] = str(email)
        login = str(spec.get("login", "")).lower()
        if login in logins:
            errors.append(f"team.members: login {spec.get('login')} used by {logins[login]} and {email}")
        logins[login] = str(email)
        held.update(spec.get("roles", ()))
    needed: list[tuple[str, str]] = []
    for gate, policy in (raw.get("approvals") or {}).items():
        if isinstance(policy, list):
            needed += [(role, f"team.approvals.{gate}") for role in policy]
    for name, area in areas.items():
        needed.append((area.get("lead", ""), f"team.areas.{name}.lead"))
        needed += [(role, f"team.areas.{name}.roles") for role in area.get("roles", ())]
    for role, where in needed:
        if role not in held:
            errors.append(f"{where}: role {role} is held by no member")
    prefixes = [(name, _literal_prefix(glob)) for name, area in areas.items() for glob in area.get("paths", ())]
    for index, (name, prefix) in enumerate(prefixes):
        for other, other_prefix in prefixes[index + 1:]:
            if other != name and (prefix.startswith(other_prefix) or other_prefix.startswith(prefix)):
                errors.append(f"team.areas: {name} and {other} overlap ({prefix!r} vs {other_prefix!r})")
    return errors


def load_team(config: Mapping[str, Any]) -> TeamConfig | None:
    raw = config.get("team")
    if not isinstance(raw, Mapping):
        return None
    members = {str(email).strip().lower(): Member(str(email).strip().lower(), tuple(spec.get("roles", ())),
                                                 str(spec.get("login", "")))
               for email, spec in (raw.get("members") or {}).items()}
    areas = {name: Area(name, tuple(spec.get("paths", ())), str(spec.get("lead", "")), tuple(spec.get("roles", ())))
             for name, spec in (raw.get("areas") or {}).items()}
    return TeamConfig(
        host=str(raw.get("host", "github")),
        commit_convention=str(raw.get("commit_convention", "conventional")),
        members=members,
        areas=areas,
        approvals={**DEFAULT_APPROVALS, **dict(raw.get("approvals") or {})},
        beads_remote=str((raw.get("beads_sync") or {}).get("remote", "")),
    )


def team_for_repo(root: Path) -> TeamConfig | None:
    if not (Path(root) / ".agent-workflow/config.yaml").is_file():
        return None
    from .configuration import resolve_effective_config

    return load_team(resolve_effective_config(Path(root), write=False).config.to_dict())


def git_email(root: Path) -> str:
    completed = subprocess.run(["git", "config", "user.email"], cwd=root, text=True, capture_output=True, check=False)
    return completed.stdout.strip().lower()


def current_member(root: Path, team: TeamConfig) -> Member | None:
    return team.member(git_email(root))


def require_member(root: Path, team: TeamConfig, actor: str | None = None) -> Member:
    email = git_email(root)
    member = team.member(email)
    if member is None:
        raise TeamError(f"git user.email {email or '<unset>'} is not in team.members")
    if actor and actor.strip().lower() != member.email:
        raise TeamError(f"--actor {actor} does not match git user.email {member.email}")
    return member


def summary(root: Path, team: TeamConfig | None) -> dict[str, Any]:
    if team is None:
        return {"enabled": False, "host": None, "me": None}
    member = current_member(root, team)
    me = None if member is None else {"email": member.email, "roles": list(member.roles),
                                      "areas": team.areas_for(member)}
    return {"enabled": True, "host": team.host, "me": me}


@dataclass(frozen=True)
class Track:
    number: int
    title: str
    area: str
    owner: str
    files: tuple[str, ...]


_TRACK = re.compile(r"^### Track (\d+):\s*(.*)$")
_META = re.compile(r"^-\s*(?:\*\*)?(Area|Owner)(?:\*\*)?:\s*`?([^`\s]+)`?\s*$")
_FILES_LINE = re.compile(r"^-\s*(?:\*\*)?(Create|Modify|Test|Files)(?:\*\*)?:\s*(.*)$")
_BACKTICK = re.compile(r"`([^`]+)`")
_FENCE = re.compile(r"^\s*(`{3,}|~{3,})")


def plan_tracks(path: Path) -> list[Track]:
    """`### Track N:` sections with their Area, Owner, and backticked file paths; fenced code is skipped."""
    tracks: list[Track] = []
    current: dict[str, Any] | None = None
    fence = ""

    def close() -> None:
        if current is not None:
            tracks.append(Track(current["number"], current["title"], current["area"], current["owner"],
                                tuple(dict.fromkeys(current["files"]))))

    for line in Path(path).read_text(encoding="utf-8").splitlines():
        opener = _FENCE.match(line)
        if fence:
            fence = "" if line.strip() == fence else fence
            continue
        if opener:
            fence = opener.group(1)
            continue
        heading = _TRACK.match(line)
        if heading or (current is not None and line.startswith("## ")):
            close()
            current = None if not heading else {"number": int(heading.group(1)), "title": heading.group(2).strip(),
                                                 "area": "", "owner": "", "files": []}
            continue
        if current is None:
            continue
        meta = _META.match(line.strip())
        if meta:
            current[meta.group(1).lower()] = meta.group(2)
            continue
        listed = _FILES_LINE.match(line.strip())
        if listed:
            current["files"] += [re.sub(r":\d[\d,-]*$", "", item) for item in _BACKTICK.findall(listed.group(2))
                                 if "/" in item or "." in item]
    close()
    return tracks


def check_plan(team: TeamConfig, path: Path) -> list[str]:
    errors: list[str] = []
    tracks = plan_tracks(path)
    if not tracks:
        return [f"{path}: no '### Track N:' sections"]
    for track in tracks:
        label = f"Track {track.number}"
        if team.areas:
            area = team.areas.get(track.area)
            if not track.area:
                errors.append(f"{label}: missing Area:")
            elif area is None:
                errors.append(f"{label}: unknown area {track.area}")
            else:
                errors += [f"{label}: {item} is outside area {track.area}" for item in track.files
                           if team.area_of(item) != track.area]
        if not track.owner and not team.beads_remote:
            errors.append(f"{label}: missing Owner: (required when Beads are not shared)")
        if track.owner:
            member = team.member(track.owner)
            if member is None:
                errors.append(f"{label}: owner {track.owner} is not in team.members")
            elif track.area in team.areas and not team.eligible(member, team.areas[track.area]):
                errors.append(f"{label}: owner {track.owner} holds no role allowed in area {track.area}")
    return errors


def _approver_roles(pr: Any, team: TeamConfig, *, on_commit: str | None = None) -> dict[str, set[str]]:
    """Roles per approving login, excluding the PR author and approvals not made on `on_commit`."""
    roles: dict[str, set[str]] = {}
    for login, commit in pr.approvals:
        if login.lower() == pr.author.lower():
            continue
        if on_commit and commit != on_commit:
            continue
        member = team.by_login(login)
        if member is not None:
            roles[login] = set(member.roles)
    return roles


_SCP = re.compile(r"^[\w.-]+@([^:/]+):(.+)$")


def repo_slug(location: str, *, pr: bool = False) -> str:
    """`host/group/project` of a git remote, or with `pr` of a PR/MR URL; SSH, scp-style and HTTPS forms
    compare equal. A GitLab MR path ends the project at `/-/`; a GitHub PR path is `owner/repo/pull/N`."""
    text = location.strip()
    scp = _SCP.match(text)
    if scp and "://" not in text:
        host, path = scp.group(1), scp.group(2)
    else:
        parsed = urlparse(text)
        host, path = parsed.hostname or "", parsed.path
    path = path.strip("/")
    if pr:
        path = path.split("/-/", 1)[0] if "/-/" in path else "/".join(path.split("/")[:2])
    return f"{host}/{path.removesuffix('.git')}".lower()


def origin_slug(root: Path) -> str:
    done = subprocess.run(["git", "remote", "get-url", "origin"], cwd=root, text=True, capture_output=True,
                          check=False)
    if done.returncode != 0 or not done.stdout.strip():
        raise TeamError("no git remote 'origin'; team gates compare the PR repository with it")
    return repo_slug(done.stdout)


def _is_artifact(path: str, gate: str, changes: str) -> bool:
    if gate == "requirement_confirmed":
        return (path.startswith(".planning/specs/") and path.endswith(".md")) or (
            path.startswith(f"{changes}/") and path.endswith("/spec-delta.md"))
    return (path.startswith(".planning/plans/") and path.endswith(".md")) or (
        path.startswith(f"{changes}/") and path.endswith("/plan.md"))


def resolve_artifact(pr: Any, root: Path, gate: str, selected: str | None) -> str:
    """The spec, plan, or roadmap the gate approves: the selector, else the one candidate the PR changes."""
    from .specs import load_config, sdd_config

    cfg = sdd_config(load_config(Path(root)))
    if gate == "roadmap":
        return ROADMAP[cfg["layout"]]
    if selected:
        return selected
    kind, flag = ("spec", "--spec") if gate == "requirement_confirmed" else ("plan", "--plan")
    changes = str(cfg["changes"]).strip("/")
    candidates = [item for item in pr.files if _is_artifact(item, gate, changes)]
    if len(candidates) != 1:
        raise TeamError(f"the PR must change exactly one {kind} file (found: {', '.join(candidates) or 'none'}); "
                        f"pass {flag} <path>")
    return candidates[0]


def check_approval(gate: str, pr: Any, team: TeamConfig, *, root: Path, artifact: str = "",
                   local_head: str = "") -> list[str]:
    """Reasons the PR does not satisfy the gate's policy (empty = pass)."""
    policy = team.approvals.get(gate, [])
    reasons: list[str] = []
    expected, actual = origin_slug(Path(root)), repo_slug(pr.url, pr=True)
    if actual != expected:
        reasons.append(f"PR belongs to {actual}, not this repository ({expected})")
    if gate == "verification_passed":
        if pr.state not in ("open", "merged"):
            reasons.append(f"PR is {pr.state}")
        if local_head and pr.head_sha != local_head:
            reasons.append(f"PR head {pr.head_sha[:12]} is not local HEAD {local_head[:12]}")
        approvers = _approver_roles(pr, team, on_commit=pr.head_sha)
        if not approvers and pr.approval_note:
            reasons.append(pr.approval_note)
    else:
        if not pr.merged:
            reasons.append(f"PR is {pr.state}, not merged")
        if artifact not in pr.files:
            reasons.append(f"PR does not change {artifact}")
        approvers = _approver_roles(pr, team)
    tracks: list[Track] = []
    if gate == "plan_approved":
        plan = Path(root) / artifact
        if plan.is_file():
            reasons += check_plan(team, plan)
            tracks = plan_tracks(plan)
        else:
            reasons.append(f"{artifact} is not in this checkout; pull the merged plan")
    held = set().union(*approvers.values()) if approvers else set()
    if policy == "area_lead":
        for name in sorted({track.area for track in tracks if track.area}):
            area = team.areas.get(name)
            if area is not None and area.lead not in held:
                reasons.append(f"missing approval from {area.lead} for area {name}")
    elif policy and not held & set(policy):
        reasons.append(f"missing approval from one of {', '.join(policy)}")
    return reasons


def gate_roles(gate: str, team: TeamConfig) -> set[str]:
    policy = team.approvals.get(gate, [])
    if policy == "area_lead":
        return {area.lead for area in team.areas.values()}
    return set(policy)


def has_policy(gate: str, team: TeamConfig) -> bool:
    policy = team.approvals.get(gate, [])
    return policy == "area_lead" and bool(team.areas) or isinstance(policy, list) and bool(policy)


def can_waive(member: Member, gate: str, team: TeamConfig) -> bool:
    roles = gate_roles(gate, team)
    return not roles or bool(roles & set(member.roles))


def approver_payload(pr: Any, team: TeamConfig) -> list[dict[str, Any]]:
    result = []
    for login, _commit in pr.approvals:
        member = team.by_login(login)
        if member is not None and login.lower() != pr.author.lower():
            result.append({"login": login, "email": member.email, "roles": list(member.roles)})
    return result



class TeamRejected(Exception):
    """The evidence does not satisfy the gate's policy: exit 1, nothing recorded."""

    def __init__(self, reasons: list[str]):
        super().__init__("\n".join(reasons))
        self.reasons = reasons


def _head(root: Path) -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True,
                          check=False).stdout.strip()


def verify_gate(root: Path, team: TeamConfig, gate: str, url: str, *, plan: str | None = None,
                spec: str | None = None) -> tuple[Any, str, list[str]]:
    """Fetch the PR/MR and return it, the approved artifact, and the reasons it fails the gate
    (HostUnavailable propagates)."""
    from .team_host import fetch_pr

    if not url.startswith(("https://", "http://")):
        raise TeamError(f"{gate} needs a PR/MR URL as --evidence in team mode, got {url!r}")
    pr = fetch_pr(url, team.host, Path(root))
    artifact = "" if gate == "verification_passed" else resolve_artifact(
        pr, Path(root), gate, plan if gate == "plan_approved" else spec)
    head = _head(Path(root)) if gate == "verification_passed" else ""
    return pr, artifact, check_approval(gate, pr, team, root=Path(root), artifact=artifact, local_head=head)


def authorize_record(root: Path, team: TeamConfig, gate: str, evidence: str, *, actor: str | None = None,
                     plan: str | None = None, spec: str | None = None) -> tuple[str, dict[str, Any]]:
    """Team-mode `record`: the member's email as actor plus, for a gate with a policy, the PR proof."""
    member = require_member(root, team, actor)
    if gate not in GATES or not has_policy(gate, team):
        return member.email, {}
    pr, artifact, reasons = verify_gate(root, team, gate, evidence, plan=plan, spec=spec)
    if reasons:
        raise TeamRejected(reasons)
    return member.email, {"pr_url": pr.url, "merge_commit": pr.merge_commit,
                          "approvers": approver_payload(pr, team), "repository": repo_slug(pr.url, pr=True),
                          **({"artifact": artifact} if artifact else {})}


def authorize_waiver(root: Path, team: TeamConfig, gate: str | None, *, actor: str | None = None) -> str:
    member = require_member(root, team, actor)
    if gate and not can_waive(member, gate, team):
        raise TeamError(f"waiving {gate} needs one of the roles {', '.join(sorted(gate_roles(gate, team)))}")
    return member.email
