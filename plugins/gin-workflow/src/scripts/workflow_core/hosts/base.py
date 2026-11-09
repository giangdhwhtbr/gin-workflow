"""The interface every git host adapter implements, and the files `gin team init` writes for a host."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from ..team_host import PrInfo


@dataclass(frozen=True)
class HostFiles:
    """Paths `gin team init` writes; None when the host has no such file."""
    codeowners: str | None
    template: str | None
    ci: str | None
    ci_template: str | None          # path under templates/, e.g. "team/github-ci.yml"


class HostAdapter(Protocol):
    name: str                         # "github" | "gitlab" | "gitea" | "codecommit"
    executable: str                   # "gh" | "glab" | "gt" | "aws"
    login_fix: str                    # shown when the CLI is missing or not logged in
    auth_exit_codes: tuple[int, ...]  # CLI exit codes meaning "not logged in" (gt: (4,)); () for none
    identity_key: str                 # member field approvals are matched on: "login" or "aws_identity"
    files: HostFiles
    ci_unsupported: str               # why `team init --ci` refuses when files.ci is None; "" for a generic message

    def auth_check_argv(self, root: Path) -> list[str]: ...
    def fetch_pr(self, url: str, cwd: Path) -> PrInfo: ...
    def merged_with_text(self, text: str, cwd: Path) -> list[PrInfo]: ...
    def pr_for_branch(self, branch: str, cwd: Path) -> PrInfo | None: ...   # newest PR of any state
    def repo_id(self, location: str, *, pr: bool = False) -> str: ...      # remote or PR URL -> comparable id
    def doctor_checks(self, root: Path) -> dict[str, tuple[bool, str]]: ...  # extra check name -> (ok, fix)
    def doctor_notes(self) -> list[str]: ...
