"""AWS CodeCommit through `aws codecommit`: a stub until the adapter is built (gin-workflow-uj2o.3)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .. import team_host
from .base import HostFiles


@dataclass(frozen=True)
class CodeCommit:
    name: str = "codecommit"
    executable: str = "aws"
    login_fix: str = "aws configure or aws sso login"
    auth_exit_codes: tuple[int, ...] = ()
    identity_key: str = "login"
    files: HostFiles = field(default_factory=lambda: HostFiles(None, None, None, None))
    ci_unsupported: str = ""

    def auth_check_argv(self, root: Path) -> list[str]:
        return [self.executable, "--version"]

    def _not_built(self, *args: Any, **kwargs: Any) -> Any:
        raise team_host.HostUnavailable(f"{self.name} support is not built yet")

    fetch_pr = merged_with_text = pr_for_branch = repo_id = doctor_checks = doctor_notes = _not_built


ADAPTER = CodeCommit()
