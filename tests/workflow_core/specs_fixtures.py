"""Shared helpers for SDD spec tests: a temporary git repository with an sdd config."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

LAUNCHER = SCRIPTS / "gin-workflow"

AUTH_SPEC = """# Auth

## Purpose

Sign-in.

## Requirements

### REQ-AUTH-001: Sign in with password
The system SHALL sign a user in with a valid password.

#### Scenario: valid password
- GIVEN a registered user
- WHEN they submit the right password
- THEN they are signed in

### REQ-AUTH-002: Reject wrong password
The system SHALL reject a wrong password.

#### Scenario: wrong password
- GIVEN a registered user
- WHEN they submit a wrong password
- THEN they see "Invalid credentials"
"""

ADDED_BLOCK = """### REQ-AUTH-003: Lock account after failed logins
The system SHALL lock an account for 15 minutes after 5 failed logins.

#### Scenario: fifth failure locks
- GIVEN a user with 4 failed logins
- WHEN the next login fails
- THEN the account is locked
"""


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True).stdout


def make_repo(root: Path, *, layout: str = "sdd", extra: str = "") -> Path:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "T")
    (root / ".agent-workflow").mkdir()
    (root / ".agent-workflow/config.yaml").write_text(
        f"schema_version: '2.6'\nartifacts:\n  layout: {layout}\n{extra}", encoding="utf-8")
    return root


def write(root: Path, relative: str, text: str) -> Path:
    path = Path(root) / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def commit_all(root: Path, message: str = "c") -> None:
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", message)


def delta(*, added: str = "", modified: str = "", removed: str = "") -> str:
    return f"# Spec Delta\n\n## ADDED\n\n{added}\n## MODIFIED\n\n{modified}\n## REMOVED\n\n{removed}"


def make_change(root: Path, name: str = "ep-1-lockout", *, epic: str = "ep-1", spec_delta: str = "") -> Path:
    change = Path(root) / "docs/changes" / name
    write(root, f"docs/changes/{name}/proposal.md", f"# Lockout\n\nEpic: {epic}\n")
    write(root, f"docs/changes/{name}/spec-delta.md", spec_delta or delta(added=ADDED_BLOCK))
    write(root, f"docs/changes/{name}/tests.md", "| TC | REQ | type | evidence |\n|---|---|---|---|\n")
    return change
