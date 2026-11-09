"""Gitea through the official `gt` CLI (docs.gitea.com/cli), gitea.com and self-hosted instances alike."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import re
import subprocess
from typing import Any
from urllib.parse import urlparse

from .. import team_host
from ..executables import tool
from ..team import TeamError, origin_url, repo_slug
from .base import HostFiles

_INSTANCE = "<instance URL, including any subpath>"   # replaced by the instance the failing call targeted, when known
_PULL_URL = re.compile(r"^(?P<prefix>.*?)/(?P<owner>[^/]+)/(?P<repo>[^/]+)/pulls/(?P<number>\d+)(?:/.*)?$")
_EXPECTED = "https://<host>[/<subpath>]/<owner>/<repo>/pulls/<n>"
_PAGES = ["-f", "limit=50", "--paginate", "--slurp"]   # --slurp: all pages as one JSON array of pages
_MIN_SERVER = 28
_COUNTED = ("APPROVED", "REQUEST_CHANGES")             # COMMENT, PENDING and REQUEST_REVIEW decide nothing
_SEARCH_LIMIT = 100
_BRANCH_PAGES = "10"


def _expect(data: Any, kind: type, what: str) -> Any:
    if not isinstance(data, kind):
        raise team_host.HostUnavailable(f"gt returned unexpected JSON for {what}")
    return data


def _pull_ref(url: str) -> tuple[str, str, str, str]:
    """(instance base URL, owner, repo, number) of a PR URL; the base is everything before `/<owner>/<repo>/pulls/`."""
    parsed = urlparse(url.strip())
    match = _PULL_URL.match(parsed.path)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or not match:
        raise team_host.HostUnavailable(f"not a Gitea pull request URL: {url}; expected {_EXPECTED}")
    base = f"{parsed.scheme}://{parsed.netloc.rpartition('@')[2]}{match['prefix']}"
    return base, match["owner"], match["repo"], match["number"]


def _instance_of(remote: str) -> str:
    """The base URL of an http(s) remote (everything before `/<owner>/<repo>`); "" for any other remote."""
    parsed = urlparse(remote.strip())
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return ""
    prefix = parsed.path.strip("/").split("/")[:-2]
    return "/".join([f"{parsed.scheme}://{parsed.netloc.rpartition('@')[2]}", *prefix])


def _logged_in_instances(executable: str, host: str, cwd: Path) -> list[str]:
    """The instances `gt auth status --json` lists (one row per account) whose host name is `host`."""
    shown = _ran([executable, "auth", "status", "--json"], cwd)
    try:
        rows = json.loads(shown.stdout) if shown and shown.returncode == 0 else []
    except json.JSONDecodeError:
        rows = []
    instances = {row["host"] for row in rows if isinstance(row, dict) and isinstance(row.get("host"), str)}
    return sorted(url for url in instances if (urlparse(url).hostname or "").lower() == host)


def _ran(argv: list[str], cwd: Path) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(argv, cwd=cwd, text=True, capture_output=True, check=False, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None


@dataclass(frozen=True)
class Gitea:
    name: str = "gitea"
    executable: str = "gt"
    login_fix: str = f"gt auth login --host {_INSTANCE}"
    auth_exit_codes: tuple[int, ...] = (4,)
    identity_key: str = "login"
    files: HostFiles = field(default_factory=lambda: HostFiles(
        ".gitea/CODEOWNERS", ".gitea/PULL_REQUEST_TEMPLATE.md", ".gitea/workflows/gin-workflow.yml",
        "team/gitea-ci.yml"))
    ci_unsupported: str = ""

    def auth_check_argv(self, root: Path) -> list[str]:
        return [self.executable, "auth", "status"]

    def _gt(self, argv: list[str], cwd: Path, instance: str = _INSTANCE) -> Any:
        try:
            return team_host._run(self.name, argv, cwd)
        except team_host.HostUnavailable as error:
            raise type(error)(str(error).replace(_INSTANCE, instance)) from error

    def _pages(self, what: str, argv: list[str], cwd: Path, instance: str = _INSTANCE) -> list[dict]:
        pages = _expect(self._gt(argv, cwd, instance) or [], list, what)
        return [item for page in pages for item in _expect(page, list, what)]

    def fetch_pr(self, url: str, cwd: Path) -> team_host.PrInfo:
        base, owner, repo, number = _pull_ref(url)
        path = f"repos/{owner}/{repo}/pulls/{number}"
        data = _expect(self._gt(["api", "--host", base, path], cwd, base), dict, path)
        reviews = self._pages(f"{path}/reviews", ["api", "--host", base, f"{path}/reviews", *_PAGES], cwd, base)
        files = self._pages(f"{path}/files", ["api", "--host", base, f"{path}/files", *_PAGES], cwd, base)
        latest: dict[str, tuple[str, str, bool]] = {}
        for item in sorted(reviews, key=lambda item: item.get("id") or 0):
            login = (item.get("user") or {}).get("login", "")
            if login and item.get("state") in _COUNTED:
                latest[login] = (item["state"], item.get("commit_id") or "", bool(item.get("dismissed")))
        approvals = tuple((login, commit) for login, (state, commit, dismissed) in latest.items()
                          if state == "APPROVED" and not dismissed)
        return team_host.PrInfo(
            url=f"{base}/{owner}/{repo}/pulls/{number}",
            state="merged" if data.get("merged") else str(data.get("state", "")),
            merged=bool(data.get("merged")),
            merge_commit=data.get("merge_commit_sha") or "",
            head_sha=(data.get("head") or {}).get("sha", ""),
            author=(data.get("user") or {}).get("login", ""),
            approvals=approvals,
            files=tuple(item.get("filename", "") for item in files),
            body=data.get("body") or "",
            approval_note=("a Gitea approval carries no commit_id (it predates commit tracking): approve again"
                           if any(not commit for _, commit in approvals) else ""),
        )

    def _origin(self, cwd: Path) -> tuple[list[str], str]:
        """`--host` and the instance for a call without a PR URL: known for an http(s) origin; otherwise `gt`
        takes the instance from the cwd remote and a failure shows the placeholder login command."""
        try:
            instance = _instance_of(origin_url(cwd))
        except TeamError:
            instance = ""
        return (["--host", instance] if instance else []), instance or _INSTANCE

    def merged_with_text(self, text: str, cwd: Path) -> list[team_host.PrInfo]:
        host, instance = self._origin(cwd)
        issues = self._pages("issue search", ["api", *host, "repos/{owner}/{repo}/issues", "-f", "type=pulls", "-f", "state=closed",
                              "-f", f"q={text}", *_PAGES, "--max-pages", "2"], cwd, instance)
        found = []
        for issue in issues[:_SEARCH_LIMIT]:
            path = f"repos/{{owner}}/{{repo}}/pulls/{_expect(issue.get('number'), int, 'issue search')}"
            pull = _expect(self._gt(["api", *host, path], cwd, instance), dict, path)
            if pull.get("merged"):
                found.append(team_host.PrInfo(pull.get("html_url", ""), "merged", True,
                                              pull.get("merge_commit_sha") or "", "", "", (), (),
                                              pull.get("body") or ""))
        return found

    def pr_for_branch(self, branch: str, cwd: Path) -> team_host.PrInfo | None:
        host, instance = self._origin(cwd)
        pulls = self._pages("pull request list", ["api", *host, "repos/{owner}/{repo}/pulls", "-f", "state=all",
                                                  *_PAGES, "--max-pages", _BRANCH_PAGES], cwd, instance)
        same = [pull for pull in pulls if (pull.get("head") or {}).get("ref") == branch]
        if not same:
            return None
        newest = max(same, key=lambda pull: pull.get("number") or 0)
        merged = bool(newest.get("merged"))
        return team_host.PrInfo(newest.get("html_url", ""), "merged" if merged else str(newest.get("state", "")),
                                merged, newest.get("merge_commit_sha") or "", "", "", (), ())

    def repo_id(self, location: str, *, pr: bool = False) -> str:
        """`host/owner/repo`, lower-cased; the port and any subpath are ignored (SSH and HTTP ports differ)."""
        if pr:
            base, owner, repo, _ = _pull_ref(location)
            return f"{urlparse(base).hostname}/{owner}/{repo}".lower()
        host, _, path = repo_slug(location).partition("/")
        segments = path.split("/")
        if not host or len(segments) < 2 or not all(segments[-2:]):
            raise team_host.HostUnavailable(f"not a Gitea remote of the form <host>/<owner>/<repo>: {location!r}")
        return f"{host}/{segments[-2]}/{segments[-1]}"

    def doctor_checks(self, root: Path) -> dict[str, tuple[bool, str]]:
        executable = tool(self.executable, root)
        if executable is None:
            return {}                                   # `host_cli` already reports the missing gt
        shown = _ran([executable, "--version"], root)
        if not (shown and shown.returncode == 0 and shown.stdout.startswith("gt version ")):
            return {"gitea_cli": (False, "the gt on PATH is not the Gitea CLI (Graphite also names its CLI gt); "
                                         "install Gitea's gt (docs.gitea.com/cli) ahead of it on PATH")}
        checks = {"gitea_cli": (True, "")}
        login = f"gt auth login --host {_INSTANCE}"
        try:
            remote = origin_url(root)
        except TeamError as error:
            return {**checks, "host_login": (False, f"{error}; add the Gitea remote, then run `{login}`")}
        instance = _instance_of(remote)
        if not instance:                               # ssh://, scp-style or a path: only the host is known
            host = repo_slug(remote).partition("/")[0]
            found = _logged_in_instances(executable, host, root) if host else []
            if len(found) != 1:
                fix = login if not found else (
                    f"origin host {host} matches several logged-in instances ({', '.join(found)}): log in to one "
                    "of them only, or use an https origin remote that names the instance")
                return {**checks, "host_login": (False, fix)}
            instance = found[0]
        login = f"gt auth login --host {instance}"
        status = _ran([executable, "auth", "status", "--host", instance], root)
        checks["host_login"] = (bool(status and status.returncode == 0), login)
        if not checks["host_login"][0]:
            return checks
        answer = _ran([executable, "api", "--host", instance, "version"], root)
        try:
            version = json.loads(answer.stdout)["version"] if answer and answer.returncode == 0 else ""
        except (json.JSONDecodeError, KeyError, TypeError):
            version = ""
        major = re.match(r"\d+", version if isinstance(version, str) else "")
        if not major:
            checks["server_version"] = (False, f"could not read the Gitea version of {instance}; check the instance URL and run `{login}`")
        else:
            checks["server_version"] = (int(major.group()) >= _MIN_SERVER,
                                        f"{instance} runs Gitea {version}; gt needs Gitea {_MIN_SERVER} or later: upgrade the instance")
        return checks

    def doctor_notes(self) -> list[str]:
        return []


ADAPTER = Gitea()
