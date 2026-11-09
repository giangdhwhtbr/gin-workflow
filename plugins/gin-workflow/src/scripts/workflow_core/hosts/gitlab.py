"""GitLab through `glab`."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from .. import team_host
from ..team import repo_slug
from .base import HostFiles

_UNSETTLED = {"checking", "approvals_syncing"}


def _gitlab_ref(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    project, marker, rest = parsed.path.strip("/").partition("/-/merge_requests/")
    if not marker or not rest.split("/")[0].isdigit():
        raise team_host.HostUnavailable(f"not a GitLab merge request URL: {url}")
    return f"{parsed.scheme}://{parsed.netloc}/{project}", rest.split("/")[0]


def _state(value: object) -> str:
    return {"opened": "open"}.get(str(value or ""), str(value or ""))


@dataclass(frozen=True)
class GitLab:
    name: str = "gitlab"
    executable: str = "glab"
    login_fix: str = "glab auth login"
    auth_exit_codes: tuple[int, ...] = ()
    identity_key: str = "login"
    files: HostFiles = field(default_factory=lambda: HostFiles(
        ".gitlab/CODEOWNERS", ".gitlab/merge_request_templates/Default.md", ".gitlab/ci/gin-workflow.yml",
        "team/gitlab-ci.yml"))
    ci_unsupported: str = ""

    def auth_check_argv(self, root: Path) -> list[str]:
        return [self.executable, "auth", "status"]

    def fetch_pr(self, url: str, cwd: Path) -> team_host.PrInfo:
        repo, iid = _gitlab_ref(url)
        host = urlparse(url).netloc
        view = ["mr", "view", iid, "-R", repo, "-F", "json"]
        data = team_host._run(self.name, view, cwd)
        project = f"projects/{data['project_id']}"
        base = f"{project}/merge_requests/{iid}"
        approvals = team_host._run(self.name, ["api", "--hostname", host, f"{base}/approvals"], cwd)
        changes = team_host._run(self.name, ["api", "--hostname", host, f"{base}/changes"], cwd)
        after = team_host._run(self.name, view, cwd)
        settings = team_host._run(self.name, ["api", "--hostname", host, f"{project}/approvals"], cwd) or {}
        versions = team_host._run(self.name, ["api", "--hostname", host, f"{base}/versions"], cwd) or []
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
        state = _state(data.get("state"))
        return team_host.PrInfo(
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

    def merged_with_text(self, text: str, cwd: Path) -> list[team_host.PrInfo]:
        rows = team_host._run(self.name, ["mr", "list", "--merged", "--search", text, "-F", "json"], cwd)
        return [team_host.PrInfo(row.get("web_url", ""), "merged", True,
                                 row.get("merge_commit_sha") or row.get("squash_commit_sha") or "", "", "", (), (),
                                 row.get("description") or "") for row in rows or []]

    def pr_for_branch(self, branch: str, cwd: Path) -> team_host.PrInfo | None:
        rows = team_host._run(self.name, ["mr", "list", "--source-branch", branch, "--all", "-F", "json"], cwd)
        if not rows:
            return None
        state = _state(rows[0].get("state"))
        return team_host.PrInfo(rows[0].get("web_url", ""), state, state == "merged",
                                rows[0].get("merge_commit_sha") or rows[0].get("squash_commit_sha") or "",
                                "", "", (), ())

    def repo_id(self, location: str, *, pr: bool = False) -> str:
        return repo_slug(location, pr=pr)

    def doctor_checks(self, root: Path) -> dict[str, tuple[bool, str]]:
        return {}

    def doctor_notes(self) -> list[str]:
        return ["GitLab Free cannot require code-owner approval; the gin check still applies"]


ADAPTER = GitLab()
