"""Team mode (schema 2.7): members, areas, identity, plan tracks, and role-gated approvals."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

from .epic_kind import DEFAULT, KINDS, lookup
from .hosts import DEFAULT_HOST, HOSTS, adapter
from .workspace import Workspace

GATES = ("requirement_confirmed", "plan_approved", "ship", "roadmap")
ROADMAP = {"legacy": ".planning/roadmap.md", "sdd": "docs/roadmap.md"}
DEFAULT_APPROVALS: dict[str, Any] = {"requirement_confirmed": [], "plan_approved": "area_lead", "ship": []}
POLICY_GATES = ("requirement_confirmed", "plan_approved", "ship")
_WILDCARDS = re.compile(r"[*?\[]")


class TeamError(Exception):
    """Usage or configuration problem: exit 2."""


@dataclass(frozen=True)
class Member:
    email: str
    roles: tuple[str, ...]
    login: str
    aws_identity: str = ""


@dataclass(frozen=True)
class Area:
    name: str
    paths: tuple[str, ...]
    lead: str
    roles: tuple[str, ...] = ()


@dataclass(frozen=True)
class TeamConfig:
    host: str = DEFAULT_HOST
    commit_convention: str = "conventional"
    members: Mapping[str, Member] = field(default_factory=dict)
    areas: Mapping[str, Area] = field(default_factory=dict)
    approvals: Mapping[str, Any] = field(default_factory=lambda: dict(DEFAULT_APPROVALS))
    beads_remote: str = ""
    permissions: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    strict: bool = False
    claim_ttl_hours: int = 48

    def member(self, email: str) -> Member | None:
        return self.members.get(email.strip().lower())

    def by_identity(self, name: str, key: str = "login") -> Member | None:
        """The member whose `key` field (a host's `identity_key`) equals `name`, case-insensitive."""
        return next((m for m in self.members.values()
                     if name and str(getattr(m, key, "")).lower() == name.lower()), None)

    def by_login(self, login: str) -> Member | None:
        return self.by_identity(login, "login")

    def eligible(self, member: Member, area: Area) -> bool:
        return not area.roles or area.lead in member.roles or bool(set(area.roles) & set(member.roles))

    def areas_for(self, member: Member) -> list[str]:
        return [name for name, area in self.areas.items() if self.eligible(member, area)]

    def technical(self, member: Member) -> bool:
        """True when one of the member's roles leads an area or is listed in an area's roles."""
        roles = set(member.roles)
        return any(area.lead in roles or bool(roles & set(area.roles)) for area in self.areas.values())

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
    identities: dict[str, str] = {}
    for email, spec in members.items():
        key = str(email).strip().lower()
        if key in emails:
            errors.append(f"team.members: duplicate email {email} (also {emails[key]})")
        emails[key] = str(email)
        login = str(spec.get("login", "")).lower()
        if login in logins:
            errors.append(f"team.members: login {spec.get('login')} used by {logins[login]} and {email}")
        logins[login] = str(email)
        identity = str(spec.get("aws_identity", ""))
        if identity:
            if identity.lower() in identities:
                errors.append(f"team.members: aws_identity {identity} used by {identities[identity.lower()]} and {email}")
            identities[identity.lower()] = str(email)
        held.update(spec.get("roles", ()))
    needed: list[tuple[str, str]] = []
    for gate, gate_policy in (raw.get("approvals") or {}).items():
        for name, policy in policy_entries(gate, gate_policy):
            needed += [(role, f"team.approvals.{name}") for role in sum(policy_parts(policy), [])]
            if isinstance(policy, Mapping) and not any(policy_parts(policy)):
                errors.append(f"team.approvals.{name}: all and any are both empty")
    for key, roles in (raw.get("permissions") or {}).items():
        needed += [(role, f"team.permissions.{key}") for role in roles]
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
    host = raw.get("host", DEFAULT_HOST)
    if host in HOSTS and adapter(host).identity_key == "aws_identity":
        policies = [policy for gate, gate_policy in {**DEFAULT_APPROVALS, **dict(raw.get("approvals") or {})}.items()
                    for _, policy in policy_entries(gate, gate_policy)]
        approving = {role for policy in policies for role in set().union(*policy_parts(policy))}
        if "area_lead" in policies:
            approving |= {area.get("lead", "") for area in areas.values()}
        for email, spec in members.items():
            roles = sorted(approving & set(spec.get("roles", ())))
            if roles and not spec.get("aws_identity"):
                errors.append(f"team.members: {email} holds approving role {', '.join(roles)} but has no "
                              f"aws_identity (required on host {host})")
    if raw.get("strict"):
        approvals = {**DEFAULT_APPROVALS, **dict(raw.get("approvals") or {})}
        errors += [f"team.strict: team.approvals.{name} has no role policy" for gate in POLICY_GATES
                   for name, policy in policy_entries(gate, approvals.get(gate, []))
                   if not _has_policy(policy, areas)]
    return errors


def load_team(config: Mapping[str, Any]) -> TeamConfig | None:
    raw = config.get("team")
    if not isinstance(raw, Mapping):
        return None
    members = {str(email).strip().lower(): Member(str(email).strip().lower(), tuple(spec.get("roles", ())),
                                                 str(spec.get("login", "")), str(spec.get("aws_identity", "")))
               for email, spec in (raw.get("members") or {}).items()}
    areas = {name: Area(name, tuple(spec.get("paths", ())), str(spec.get("lead", "")), tuple(spec.get("roles", ())))
             for name, spec in (raw.get("areas") or {}).items()}
    approvals = {**DEFAULT_APPROVALS, **dict(raw.get("approvals") or {})}
    if "verification_passed" in approvals:
        legacy = approvals.pop("verification_passed")
        if not approvals["ship"]:
            approvals["ship"] = legacy
        print("warning: team.approvals.verification_passed is deprecated; use team.approvals.ship", file=sys.stderr)
    return TeamConfig(
        host=str(raw.get("host", DEFAULT_HOST)),
        commit_convention=str(raw.get("commit_convention", "conventional")),
        members=members,
        areas=areas,
        approvals=approvals,
        beads_remote=str((raw.get("beads_sync") or {}).get("remote", "")),
        permissions={key: tuple(roles) for key, roles in (raw.get("permissions") or {}).items()},
        strict=bool(raw.get("strict", False)),
        claim_ttl_hours=int(raw.get("claim_ttl_hours", 48)),
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
                                      "areas": team.areas_for(member), "technical": team.technical(member)}
    return {"enabled": True, "host": team.host, "me": me,
            "permissions": {key: list(roles) for key, roles in team.permissions.items()}}


@dataclass(frozen=True)
class Track:
    number: int
    title: str
    area: str
    owner: str
    files: tuple[str, ...]
    repo: str = ""


_TRACK = re.compile(r"^### Track (\d+):\s*(.*)$")
_META = re.compile(r"^-\s*(?:\*\*)?(Area|Owner|Repo)(?:\*\*)?:\s*`?([^`\s]+)`?\s*$")
_FILES_LABEL = re.compile(r"^(-\s*)?(?:\*\*)?Files(?:\*\*)?:(?:\*\*)?\s*(.*)$")
_VERB = re.compile(r"^(?:Create|Modify|Test|Delete)\b:?\s*")
_PATH = re.compile(r"`([^`\s]+)`")
_FENCE = re.compile(r"^\s*(`{3,}|~{3,})")


def _listed_paths(text: str) -> list[str]:
    """The leading comma-separated backticked paths of a Files entry, after an optional verb; line ranges dropped."""
    rest = _VERB.sub("", text.strip(), count=1)
    paths: list[str] = []
    while token := _PATH.match(rest):
        paths.append(re.sub(r":\d[\d,-]*$", "", token.group(1)))
        rest = rest[token.end():].lstrip()
        if not rest.startswith(","):
            break
        rest = rest[1:].lstrip()
    return paths


def plan_tracks(path: Path) -> list[Track]:
    """`### Track N:` sections with their Area, Owner, and the paths listed in their Files block; fenced code is
    skipped."""
    tracks: list[Track] = []
    current: dict[str, Any] | None = None
    fence = ""
    files_indent: int | None = None  # indent of the open Files label; -1 when the label is not a list item

    def close() -> None:
        if current is not None:
            tracks.append(Track(current["number"], current["title"], current["area"], current["owner"],
                                tuple(dict.fromkeys(current["files"])), current["repo"]))

    for line in Path(path).read_text(encoding="utf-8").splitlines():
        opener = _FENCE.match(line)
        if fence:
            fence = "" if line.strip() == fence else fence
            continue
        if opener:
            fence, files_indent = opener.group(1), None
            continue
        heading = _TRACK.match(line)
        if heading or (current is not None and line.startswith("## ")):
            close()
            current = None if not heading else {"number": int(heading.group(1)), "title": heading.group(2).strip(),
                                                 "area": "", "owner": "", "files": [], "repo": ""}
            files_indent = None
            continue
        if current is None:
            continue
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())
        meta = _META.match(stripped)
        if meta:
            current[meta.group(1).lower()] = meta.group(2)
            files_indent = None
            continue
        if files_indent is not None and stripped.startswith("- ") and indent > files_indent:
            current["files"] += _listed_paths(stripped[2:])
            continue
        files_indent = None
        label = _FILES_LABEL.match(stripped)
        if label:
            files_indent = indent if label.group(1) else -1
            current["files"] += _listed_paths(label.group(2))
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
    listed: dict[str, list[int]] = {}
    for track in tracks:
        for item in track.files:
            listed.setdefault(item, []).append(track.number)
    for item, numbers in listed.items():
        if len(numbers) > 1:
            names = [str(n) for n in sorted(numbers)]
            errors.append(f"`{item}` is listed by tracks {', '.join(names[:-1])} and {names[-1]}")
    return errors



def check_plan_repos(space: Workspace, path: Path) -> list[str]:
    """Workspace rules for a plan: every track names one workable `Repo:` and lists files inside it."""
    errors: list[str] = []
    for track in plan_tracks(path):
        label = f"Track {track.number}"
        if not track.repo:
            errors.append(f"{label}: missing Repo:")
            continue
        repo = space.repo(track.repo)
        if repo is None:
            errors.append(f"{label}: Repo: {track.repo} is not in workspace.repos")
            continue
        if repo.frozen:
            errors.append(f"{label}: Repo: {track.repo} is frozen")
        elif repo.shape == "beads":
            errors.append(f"{label}: Repo: {track.repo} is the beads repository")
        errors += [f"{label}: `{item}` is outside repo {track.repo}" for item in track.files
                   if space.repo_of(item) != repo]
    return errors


def _approver_roles(pr: Any, team: TeamConfig, *, on_commit: str | None = None) -> dict[str, set[str]]:
    """Roles per approving login, excluding the PR author and approvals not made on `on_commit`."""
    roles: dict[str, set[str]] = {}
    key = adapter(team.host).identity_key
    for login, commit in pr.approvals:
        if login.lower() == pr.author.lower():
            continue
        if on_commit and commit != on_commit:
            continue
        member = team.by_identity(login, key)
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


def origin_url(root: Path) -> str:
    done = subprocess.run(["git", "remote", "get-url", "origin"], cwd=root, text=True, capture_output=True,
                          check=False)
    if done.returncode != 0 or not done.stdout.strip():
        raise TeamError("no git remote 'origin'; team gates compare the PR repository with it")
    return done.stdout.strip()


def repo_for_pr(root: Path, team: TeamConfig, pr_url: str, cwd: Path | None = None) -> tuple[str, Path, list[str]]:
    """The URL a ship PR must match, the directory whose HEAD the `ship` gate compares, and the repository ids a
    workspace accepts. The parent when the PR is its own; else the `workspace.repos` entry with the PR's
    repository, taking HEAD from `cwd` when it is that child's checkout or one of its worktrees."""
    from .checkout import main_checkout
    from . import workspace as workspace_core

    host = adapter(team.host)
    parent = origin_url(Path(root))
    wanted = host.repo_id(pr_url, pr=True)
    if wanted == host.repo_id(parent):
        return parent, Path(root), []
    space = workspace_core.load(Path(root))
    if space is None:
        return parent, Path(root), []
    accepted = [host.repo_id(parent)] + [host.repo_id(entry.url) for entry in space.repos if entry.url]
    for entry in space.repos:
        if entry.url and host.repo_id(entry.url) == wanted:
            checkout = space.checkout(entry)
            if not (checkout / ".git").exists():
                raise TeamError(f"{entry.path} is not cloned; run gin workspace clone {entry.path}")
            here = Path(cwd or Path.cwd()).resolve()
            same = main_checkout(here) == checkout.resolve()
            return entry.url, (here if same else checkout), accepted
    return parent, Path(root), accepted


def _is_artifact(path: str, gate: str, changes: str) -> bool:
    from .specs import CHANGE_FILES

    legacy, role = (".planning/specs/", "spec-delta") if gate == "requirement_confirmed" else (".planning/plans/", "plan")
    return (path.startswith(legacy) and path.endswith(".md")) or (
        path.startswith(f"{changes}/") and path.endswith((f"/{role}.md", f"/{CHANGE_FILES[role]}")))


def _deltaless_proposals(files: Sequence[str], root: Path, changes: str) -> list[str]:
    """The proposal of each change folder the PR touches that has no spec delta, in the PR or in the checkout: a
    technical change may have none (epic-kinds R6), so its proposal holds the requirement and the `Kind:` line."""
    from .specs import CHANGE_FILES, change_file

    names = {*CHANGE_FILES.values(), *(f"{role}.md" for role in CHANGE_FILES)}
    touched = {item.rsplit("/", 1)[0] for item in files
               if item.startswith(f"{changes}/") and item.rsplit("/", 1)[-1] in names}
    with_delta = {item.rsplit("/", 1)[0] for item in files if _is_artifact(item, "requirement_confirmed", changes)}
    return [f"{folder}/{change_file(root / folder, 'proposal').name}" for folder in sorted(touched - with_delta)
            if not change_file(root / folder, "spec-delta").is_file()]


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
    if gate == "requirement_confirmed":
        candidates += _deltaless_proposals(pr.files, Path(root), changes)
    if len(candidates) != 1:
        raise TeamError(f"the PR must change exactly one {kind} file (found: {', '.join(candidates) or 'none'}); "
                        f"pass {flag} <path>")
    return candidates[0]


def check_approval(gate: str, pr: Any, team: TeamConfig, *, root: Path, artifact: str = "",
                   local_head: str = "", expected_repo: str = "", accepted: Sequence[str] = (),
                   notes: list[str] | None = None, kind: str | None = None) -> list[str]:
    """Reasons the PR does not satisfy the gate's policy for the epic `kind` (empty = pass); skipped sole-holder
    roles are appended to `notes` when given."""
    policy = policy_for(team, "ship" if gate == "shipped" else gate, kind)
    reasons: list[str] = []
    host = adapter(team.host)
    expected, actual = host.repo_id(expected_repo or origin_url(Path(root))), host.repo_id(pr.url, pr=True)
    if actual != expected:
        also = f"; accepted: {', '.join(accepted)}" if accepted else ""
        reasons.append(f"PR belongs to {actual}, not this repository ({expected}){also}")
    if gate in ("ship", "shipped"):
        if gate == "shipped" and not pr.merged:
            reasons.append(f"PR is {pr.state}, not merged")
        elif pr.state not in ("open", "merged"):
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
    author = team.by_identity(pr.author, adapter(team.host).identity_key)
    if policy == "area_lead":
        for name in sorted({track.area for track in tracks if track.area}):
            area = team.areas.get(name)
            if area is not None and area.lead not in held:
                others = sorted(held & {other.lead for other in team.areas.values() if other.lead != area.lead})
                if _sole_holder(team, area.lead, author) and others:
                    if notes is not None:
                        notes.append(f"{area.lead} for area {name} skipped: the author is its only holder; "
                                     f"approved by {others[0]}")
                else:
                    reasons.append(f"missing approval from {area.lead} for area {name}")
    elif isinstance(policy, Mapping):
        required, optional = policy_parts(policy)
        for role in required:
            if role in held:
                continue
            if _sole_holder(team, role, author):
                if not optional:
                    reasons.append(f"{role} has no holder other than the author; add a holder or an `any` role")
                elif notes is not None:
                    notes.append(f"{role} skipped: the author is its only holder")
                continue
            reasons.append(f"missing approval from {role}")
        if optional and not held & set(optional):
            reasons.append(f"missing approval from one of {', '.join(optional)}")
    elif policy and not held & set(policy):
        reasons.append(f"missing approval from one of {', '.join(policy)}")
    return reasons


def _kind_map(policy: Any) -> bool:
    """A per-kind `requirement_confirmed` map: its `capability` key tells it from an `{all, any}` policy."""
    return isinstance(policy, Mapping) and "capability" in policy


def policy_entries(gate: str, policy: Any) -> list[tuple[str, Any]]:
    """(name, policy) for each policy a gate holds: `<gate>.<kind>` per entry of a kind map, else the gate."""
    return [(f"{gate}.{kind}", entry) for kind, entry in policy.items()] if _kind_map(policy) else [(gate, policy)]


def policy_for(team: TeamConfig, gate: str, kind: str | None = None) -> Any:
    """The gate's policy; a kind map gives the entry of `kind` (default capability), else its capability entry."""
    policy = team.approvals.get(gate, [])
    return policy.get(kind or DEFAULT, policy["capability"]) if _kind_map(policy) else policy


def policy_parts(policy: Any) -> tuple[list[str], list[str]]:
    """(roles that must each approve, roles of which one must approve)."""
    if isinstance(policy, Mapping):
        return list(policy.get("all") or []), list(policy.get("any") or [])
    if isinstance(policy, list):
        return [], list(policy)
    return [], []


def policy_roles(policy: Any, team: TeamConfig) -> set[str]:
    """Every role that can approve under the policy; `area_lead` gives the area leads."""
    if policy == "area_lead":
        return {area.lead for area in team.areas.values()}
    return set().union(*policy_parts(policy))


def _sole_holder(team: TeamConfig, role: str, author: Member | None) -> bool:
    """True when `author` holds `role` and no other member does."""
    return author is not None and role in author.roles and all(
        member is author for member in team.members.values() if role in member.roles)


def gate_roles(gate: str, team: TeamConfig, kind: str | None = None) -> set[str]:
    return policy_roles(policy_for(team, gate, kind), team)


def _has_policy(policy: Any, areas: Mapping[str, Any]) -> bool:
    return policy == "area_lead" and bool(areas) or bool(set().union(*policy_parts(policy)))


def has_policy(gate: str, team: TeamConfig, kind: str | None = None) -> bool:
    return _has_policy(policy_for(team, gate, kind), team.areas)


def needs_pr(gate: str, team: TeamConfig) -> bool:
    """True when recording `gate` needs PR proof: it has a policy for any epic kind. The kind is known only once the
    PR names its spec, so `record` and doctor's `spec_review` check use this, not one kind's policy."""
    return any(has_policy(gate, team, kind) for kind in KINDS)


def can_waive(member: Member, gate: str, team: TeamConfig, kind: str | None = None) -> bool:
    roles = gate_roles(gate, team, kind)
    return not roles or bool(roles & set(member.roles))


def approver_payload(pr: Any, team: TeamConfig, *, on_commit: str | None = None) -> list[dict[str, Any]]:
    result = []
    key = adapter(team.host).identity_key
    for login in _approver_roles(pr, team, on_commit=on_commit):
        member = team.by_identity(login, key)
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
                spec: str | None = None, notes: list[str] | None = None,
                workflow_id: str | None = None) -> tuple[Any, str, list[str], str | None]:
    """Fetch the PR/MR and return it, the approved artifact, the reasons it fails the gate, and the epic kind whose
    policy applied: for requirement_confirmed, `epic_kind.lookup` of `workflow_id` and the resolved spec (a kind
    mismatch is the one reason), else None. HostUnavailable propagates; skipped sole-holder roles are appended to
    `notes` when given."""
    from .team_host import fetch_pr

    if not url.startswith(("https://", "http://")):
        raise TeamError(f"{gate} needs a PR/MR URL as --evidence in team mode, got {url!r}")
    pr = fetch_pr(url, team.host, Path(root))
    artifact = "" if gate in ("ship", "shipped") else resolve_artifact(
        pr, Path(root), gate, plan if gate == "plan_approved" else spec)
    kind, mismatch = lookup(Path(root), workflow_id, artifact) if gate == "requirement_confirmed" else (None, None)
    if mismatch:
        return pr, artifact, [mismatch], kind
    expected, head_dir, accepted = (repo_for_pr(Path(root), team, url) if gate in ("ship", "shipped")
                                    else ("", Path(root), []))
    head = _head(head_dir) if gate == "ship" else ""
    reasons = check_approval(gate, pr, team, root=Path(root), artifact=artifact, local_head=head,
                             expected_repo=expected, accepted=accepted, notes=notes, kind=kind)
    return pr, artifact, reasons, kind


def authorize_record(root: Path, team: TeamConfig, gate: str, evidence: str, *, actor: str | None = None,
                     plan: str | None = None, spec: str | None = None,
                     workflow_id: str | None = None) -> tuple[str, dict[str, Any]]:
    """Team-mode `record`: the member's email as actor plus, for a gate that `needs_pr`, the PR proof."""
    member = require_member(root, team, actor)
    if (gate not in GATES and gate != "shipped") or not needs_pr("ship" if gate == "shipped" else gate, team):
        return member.email, {}
    if gate == "shipped" and not evidence.startswith(("https://", "http://")):
        raise TeamError("shipped needs the PR URL as --evidence in team mode")
    pr, artifact, reasons, _ = verify_gate(root, team, gate, evidence, plan=plan, spec=spec, workflow_id=workflow_id)
    if reasons:
        raise TeamRejected(reasons)
    return member.email, {"pr_url": pr.url, "merge_commit": pr.merge_commit,
                          "approvers": approver_payload(pr, team, on_commit=pr.head_sha if gate == "shipped" else None),
                          "repository": adapter(team.host).repo_id(pr.url, pr=True),
                          **({"artifact": artifact} if artifact else {})}


def authorize_waiver(root: Path, team: TeamConfig, gate: str | None, *, actor: str | None = None,
                     kind: str | None = None) -> str:
    member = require_member(root, team, actor)
    if gate and not can_waive(member, gate, team, kind):
        raise TeamError(f"waiving {gate} needs one of the roles {', '.join(sorted(gate_roles(gate, team, kind)))}")
    return member.email
