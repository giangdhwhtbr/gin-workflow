"""GitHub through `gh`."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .. import team_host
from ..team import repo_slug
from .base import HostFiles


@dataclass(frozen=True)
class GitHub:
    name: str = "github"
    executable: str = "gh"
    login_fix: str = "gh auth login"
    auth_exit_codes: tuple[int, ...] = ()
    identity_key: str = "login"
    files: HostFiles = field(default_factory=lambda: HostFiles(
        ".github/CODEOWNERS", ".github/pull_request_template.md", ".github/workflows/gin-workflow.yml",
        "team/github-ci.yml"))
    ci_unsupported: str = ""

    def auth_check_argv(self, root: Path) -> list[str]:
        return [self.executable, "auth", "status"]

    def fetch_pr(self, url: str, cwd: Path) -> team_host.PrInfo:
        data = team_host._run(self.name, ["pr", "view", url, "--json",
                                          "url,state,mergeCommit,headRefOid,author,reviews,files,body"], cwd)
        latest: dict[str, tuple[str, str]] = {}
        for review in data.get("reviews") or []:
            state = review.get("state", "")
            if state in ("APPROVED", "CHANGES_REQUESTED", "DISMISSED"):
                login = (review.get("author") or {}).get("login", "")
                latest[login] = (state, (review.get("commit") or {}).get("oid", ""))
        state = str(data.get("state", "")).lower()
        return team_host.PrInfo(
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

    def merged_with_text(self, text: str, cwd: Path) -> list[team_host.PrInfo]:
        rows = team_host._run(self.name, ["pr", "list", "--state", "merged", "--search", f'"{text}" in:body',
                                          "--json", "url,body,mergeCommit", "--limit", "100"], cwd)
        return [team_host.PrInfo(row.get("url", ""), "merged", True, (row.get("mergeCommit") or {}).get("oid", ""),
                                 "", "", (), (), row.get("body") or "") for row in rows or []]

    def pr_for_branch(self, branch: str, cwd: Path) -> team_host.PrInfo | None:
        rows = team_host._run(self.name, ["pr", "list", "--head", branch, "--state", "all",
                                          "--json", "url,state,mergeCommit"], cwd)
        if not rows:
            return None
        state = str(rows[0].get("state", "")).lower()
        return team_host.PrInfo(rows[0].get("url", ""), state, state == "merged",
                                (rows[0].get("mergeCommit") or {}).get("oid", ""), "", "", (), ())

    def repo_id(self, location: str, *, pr: bool = False) -> str:
        return repo_slug(location, pr=pr)

    def doctor_checks(self, root: Path) -> dict[str, tuple[bool, str]]:
        return {}

    def doctor_notes(self) -> list[str]:
        return []


ADAPTER = GitHub()
