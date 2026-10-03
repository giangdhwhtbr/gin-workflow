"""Team mode (schema 2.7): members, areas, identity, plan tracks, and role-gated approvals."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
import subprocess
from typing import Any, Mapping

GATES = ("requirement_confirmed", "plan_approved", "verification_passed")
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
