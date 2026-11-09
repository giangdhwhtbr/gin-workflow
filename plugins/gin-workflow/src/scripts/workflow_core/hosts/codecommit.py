"""AWS CodeCommit through `aws codecommit`; approvers are matched to members by `aws_identity`."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import re
from typing import Any

from .. import team_host
from .base import HostFiles

_CONSOLE = re.compile(r"^https://([a-z0-9-]+)\.console\.aws\.amazon\.com/codesuite/codecommit/repositories/"
                      r"([\w.-]+)/pull-requests/(\d+)/?(?:[?#].*)?$")
_HTTPS_SSH = re.compile(r"^(?:https|ssh)://(?:[^@/]+@)?git-codecommit\.([a-z0-9-]+)\.amazonaws\.com(?:\.cn)?"
                        r"/v1/repos/([\w.-]+)/?$")
_REMOTE_CLI = re.compile(r"^codecommit(?:::([a-z0-9-]+))?://(?:[^@/]+@)?([\w.-]+)/?$")
_PR_FORM = "https://<region>.console.aws.amazon.com/codesuite/codecommit/repositories/<repo>/pull-requests/<id>"
_REMOTE_FORM = ("codecommit::<region>://<repo>, codecommit://[<profile>@]<repo> (with AWS_REGION), or "
                "https://git-codecommit.<region>.amazonaws.com/v1/repos/<repo>")
_MAX_SEARCH = 100


def _name(arn: str) -> str:
    """The member-facing name of an IAM ARN: `user/<name>` gives the name, `assumed-role/<role>/<session>` gives
    `<role>/<session>`, so a session named after a member under another role matches no member; any other ARN is
    returned whole, so it matches no member."""
    resource = arn.split(":", 5)[5] if arn.startswith("arn:") and arn.count(":") >= 5 else ""
    parts = resource.split("/")
    if parts[0] == "assumed-role" and len(parts) == 3:
        return f"{parts[1]}/{parts[2]}"
    if parts[0] in ("user", "federated-user") and len(parts) >= 2:
        return parts[-1]
    return arn


def _env_region() -> str:
    return os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or ""


def _console(region: str, repo: str, number: str) -> str:
    return f"https://{region}.console.aws.amazon.com/codesuite/codecommit/repositories/{repo}/pull-requests/{number}" \
           f"?region={region}"


@dataclass(frozen=True)
class CodeCommit:
    name: str = "codecommit"
    executable: str = "aws"
    login_fix: str = "aws configure or aws sso login"
    auth_exit_codes: tuple[int, ...] = ()
    identity_key: str = "aws_identity"
    files: HostFiles = field(default_factory=lambda: HostFiles(None, None, None, None))
    ci_unsupported: str = "CodeCommit has no CI workflow file; use CodeBuild or CodePipeline"

    def auth_check_argv(self, root: Path) -> list[str]:
        return [self.executable, "sts", "get-caller-identity"]

    def _aws(self, region: str, argv: list[str], cwd: Path) -> dict[str, Any]:
        data = team_host._run(self.name, ["codecommit", *argv, "--region", region, "--output", "json"], cwd)
        if not isinstance(data, dict):
            raise team_host.HostUnavailable(f"aws codecommit {argv[0]} returned unexpected output")
        return data

    def _paged(self, region: str, argv: list[str], key: str, cwd: Path) -> list[Any]:
        items: list[Any] = []
        token = ""
        while True:
            data = self._aws(region, [*argv, *(["--starting-token", token] if token else [])], cwd)
            items += data.get(key) or []
            token = data.get("NextToken") or data.get("nextToken") or ""
            if not token:
                return items

    def _pull_request(self, region: str, number: str, cwd: Path) -> tuple[dict[str, Any], dict[str, Any]]:
        """The pull request and its first target, validated."""
        pr = self._aws(region, ["get-pull-request", "--pull-request-id", number], cwd).get("pullRequest")
        targets = pr.get("pullRequestTargets") if isinstance(pr, dict) else None
        if not targets or not isinstance(targets[0], dict):
            raise team_host.HostUnavailable("aws codecommit get-pull-request returned unexpected output")
        return pr, targets[0]

    def _info(self, url: str, pr: dict[str, Any], target: dict[str, Any], approvals: tuple[tuple[str, str], ...] = (),
              files: tuple[str, ...] = ()) -> team_host.PrInfo:
        merged = bool((target.get("mergeMetadata") or {}).get("isMerged"))
        state = "open" if pr.get("pullRequestStatus") == "OPEN" else "merged" if merged else "closed"
        return team_host.PrInfo(url=url, state=state, merged=state == "merged",
                                merge_commit=(target.get("mergeMetadata") or {}).get("mergeCommitId") or "",
                                head_sha=target.get("sourceCommit", ""),
                                author=_name(pr.get("authorArn", "")), approvals=approvals, files=files,
                                body=pr.get("description") or "")

    def fetch_pr(self, url: str, cwd: Path) -> team_host.PrInfo:
        region, repo, number = self._parse_pr(url)
        pr, target = self._pull_request(region, number, cwd)
        if target.get("repositoryName") != repo:
            raise team_host.HostUnavailable(
                f"pull request {number} belongs to repository {target.get('repositoryName')}, not {repo}")
        source = target.get("sourceCommit", "")
        states = self._aws(region, ["get-pull-request-approval-states", "--pull-request-id", number,
                                    "--revision-id", pr.get("revisionId", "")], cwd)
        approvals = tuple((_name(item.get("userArn", "")), source) for item in states.get("approvals") or []
                          if item.get("approvalState") == "APPROVE")
        changes = self._paged(region, ["get-differences", "--repository-name", repo, "--before-commit-specifier",
                                       target.get("mergeBase") or target.get("destinationCommit", ""),
                                       "--after-commit-specifier", source], "differences", cwd)
        files = tuple((item.get("afterBlob") or item.get("beforeBlob") or {}).get("path", "") for item in changes)
        return self._info(url, pr, target, approvals, files)

    def _listing(self, cwd: Path, status: str | None) -> tuple[str, str, list[str]]:
        """Region, repository, and pull request ids (newest first, at most 100) of the origin remote."""
        region, repo = self._origin(cwd)
        ids = self._paged(region, ["list-pull-requests", "--repository-name", repo,
                                   *(["--pull-request-status", status] if status else [])], "pullRequestIds", cwd)
        return region, repo, sorted(ids, key=int, reverse=True)[:_MAX_SEARCH]

    def merged_with_text(self, text: str, cwd: Path) -> list[team_host.PrInfo]:
        region, repo, ids = self._listing(cwd, "CLOSED")
        found = []
        for number in ids:
            pr, target = self._pull_request(region, number, cwd)
            info = self._info(_console(region, repo, number), pr, target)
            if info.merged and text in info.body:
                found.append(info)
        return found

    def pr_for_branch(self, branch: str, cwd: Path) -> team_host.PrInfo | None:
        region, repo, ids = self._listing(cwd, None)
        for number in ids:
            pr, target = self._pull_request(region, number, cwd)
            if target.get("sourceReference") == f"refs/heads/{branch}":
                return self._info(_console(region, repo, number), pr, target)
        return None

    def _parse_pr(self, url: str) -> tuple[str, str, str]:
        match = _CONSOLE.match(url.strip())
        if match is None:
            raise team_host.HostUnavailable(f"not a CodeCommit pull request URL; expected {_PR_FORM}")
        return match.groups()

    def _origin(self, cwd: Path) -> tuple[str, str]:
        from ..team import TeamError, origin_url

        try:
            return self._parse_remote(origin_url(cwd))
        except TeamError as error:
            raise team_host.HostUnavailable(str(error)) from error

    def _parse_remote(self, remote: str) -> tuple[str, str]:
        text = remote.strip()
        match = _HTTPS_SSH.match(text) or _REMOTE_CLI.match(text)
        if match is None:
            raise team_host.HostUnavailable(f"origin is not a CodeCommit remote; expected {_REMOTE_FORM}")
        region = match.group(1) or _env_region()
        if not region:
            raise team_host.HostUnavailable("the AWS region of origin is unknown; set AWS_REGION or use "
                                            "codecommit::<region>://<repo>")
        return region, match.group(2)

    def repo_id(self, location: str, *, pr: bool = False) -> str:
        if pr:
            region, repo, _ = self._parse_pr(location)
        else:
            region, repo = self._parse_remote(location)
        return f"codecommit/{region}/{repo}"

    def doctor_checks(self, root: Path) -> dict[str, tuple[bool, str]]:
        return {}

    def doctor_notes(self) -> list[str]:
        return ["CodeCommit does not enforce code owners; create an approval rule template (see docs/guides/team.md)"]


ADAPTER = CodeCommit()
