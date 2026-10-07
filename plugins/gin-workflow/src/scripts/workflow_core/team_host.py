"""Git host adapters: one `PrInfo` view of a GitHub PR (`gh`) or GitLab MR (`glab`)."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any
from urllib.parse import urlparse

_EXECUTABLE = {"github": "gh", "gitlab": "glab"}
_LOGIN_FIX = {"github": "gh auth login", "gitlab": "glab auth login"}


class HostUnavailable(Exception):
    """The host CLI is missing, unauthenticated, or unreachable: exit 2, nothing recorded."""


@dataclass(frozen=True)
class PrInfo:
    url: str
    state: str                              # open | merged | closed
    merged: bool
    merge_commit: str
    head_sha: str
    author: str
    approvals: tuple[tuple[str, str], ...]  # (login, commit the approval was made on; "" when unknown)
    files: tuple[str, ...]
    body: str = ""
    approval_note: str = ""                 # why approvals carry no commit (GitLab), shown when none count


def _run(host: str, argv: list[str], cwd: Path) -> Any:
    executable = shutil.which(_EXECUTABLE[host])
    if executable is None:
        raise HostUnavailable(f"{_EXECUTABLE[host]} is not installed; install it, then run {_LOGIN_FIX[host]}")
    try:
        completed = subprocess.run([executable, *argv], cwd=cwd, text=True, capture_output=True, check=False,
                                   timeout=60)
    except (OSError, subprocess.SubprocessError) as error:
        raise HostUnavailable(f"{_EXECUTABLE[host]} failed: {error}") from error
    if completed.returncode != 0:
        raise HostUnavailable(f"{_EXECUTABLE[host]} {argv[0]} failed: {completed.stderr.strip()} "
                              f"(check `{_LOGIN_FIX[host]}`)")
    try:
        return json.loads(completed.stdout or "null")
    except json.JSONDecodeError as error:
        raise HostUnavailable(f"{_EXECUTABLE[host]} returned non-JSON output") from error


def _github(url: str, cwd: Path) -> PrInfo:
    data = _run("github", ["pr", "view", url, "--json",
                           "url,state,mergeCommit,headRefOid,author,reviews,files,body"], cwd)
    latest: dict[str, tuple[str, str]] = {}
    for review in data.get("reviews") or []:
        state = review.get("state", "")
        if state in ("APPROVED", "CHANGES_REQUESTED", "DISMISSED"):
            login = (review.get("author") or {}).get("login", "")
            latest[login] = (state, (review.get("commit") or {}).get("oid", ""))
    state = str(data.get("state", "")).lower()
    return PrInfo(
        url=data.get("url", url),
        state=state,
        merged=state == "merged",
        merge_commit=(data.get("mergeCommit") or {}).get("oid", ""),
        head_sha=data.get("headRefOid", ""),
        author=(data.get("author") or {}).get("login", ""),
        approvals=tuple((login, commit) for login, (review_state, commit) in latest.items()
                        if review_state == "APPROVED"),
        files=tuple(item.get("path", "") for item in data.get("files") or []),
        body=data.get("body") or "",
    )


def _gitlab_ref(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    project, marker, rest = parsed.path.strip("/").partition("/-/merge_requests/")
    if not marker or not rest.split("/")[0].isdigit():
        raise HostUnavailable(f"not a GitLab merge request URL: {url}")
    return f"{parsed.scheme}://{parsed.netloc}/{project}", rest.split("/")[0]


_UNSETTLED = {"checking", "approvals_syncing"}


def _gitlab(url: str, cwd: Path) -> PrInfo:
    repo, iid = _gitlab_ref(url)
    host = urlparse(url).netloc
    view = ["mr", "view", iid, "-R", repo, "-F", "json"]
    data = _run("gitlab", view, cwd)
    project = f"projects/{data['project_id']}"
    base = f"{project}/merge_requests/{iid}"
    approvals = _run("gitlab", ["api", "--hostname", host, f"{base}/approvals"], cwd)
    changes = _run("gitlab", ["api", "--hostname", host, f"{base}/changes"], cwd)
    after = _run("gitlab", view, cwd)
    settings = _run("gitlab", ["api", "--hostname", host, f"{project}/approvals"], cwd) or {}
    versions = _run("gitlab", ["api", "--hostname", host, f"{base}/versions"], cwd) or []
    head = data.get("sha", "")
    commit, note = "", ""
    if not settings.get("reset_approvals_on_push"):
        note = ("GitLab approvals are not tied to a commit: enable 'Reset approvals on push' "
                "(reset_approvals_on_push) on the project")
    elif (after.get("sha") != head
          or {data.get("detailed_merge_status"), after.get("detailed_merge_status")} & _UNSETTLED
          or not any(item.get("head_commit_sha") == head and item.get("patch_id_sha") for item in versions)):
        note = "approvals still syncing; retry"
    else:
        commit = head
    state = {"opened": "open"}.get(str(data.get("state", "")), str(data.get("state", "")))
    return PrInfo(
        url=data.get("web_url", url),
        state=state,
        merged=state == "merged",
        merge_commit=data.get("merge_commit_sha") or data.get("squash_commit_sha") or "",
        head_sha=head,
        author=(data.get("author") or {}).get("username", ""),
        approvals=tuple(((item.get("user") or {}).get("username", ""), commit)
                        for item in approvals.get("approved_by") or []),
        files=tuple(item.get("new_path", "") for item in changes.get("changes") or []),
        body=data.get("description") or "",
        approval_note=note,
    )


def fetch_pr(url: str, host: str, cwd: Path) -> PrInfo:
    return _github(url, cwd) if host == "github" else _gitlab(url, cwd)


def merged_with_text(host: str, text: str, cwd: Path) -> list[PrInfo]:
    """Merged PRs/MRs whose description mentions `text` (url, body, merge commit only)."""
    if host == "github":
        rows = _run("github", ["pr", "list", "--state", "merged", "--search", f'"{text}" in:body',
                               "--json", "url,body,mergeCommit", "--limit", "100"], cwd)
        return [PrInfo(row.get("url", ""), "merged", True, (row.get("mergeCommit") or {}).get("oid", ""),
                       "", "", (), (), row.get("body") or "") for row in rows or []]
    rows = _run("gitlab", ["mr", "list", "--merged", "--search", text, "-F", "json"], cwd)
    return [PrInfo(row.get("web_url", ""), "merged", True, row.get("merge_commit_sha") or "", "", "", (), (),
                   row.get("description") or "") for row in rows or []]
