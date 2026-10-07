"""Shared helpers for team-mode tests: a git repository with a team config and fake host CLIs on PATH."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

LAUNCHER = SCRIPTS / "gin-workflow"

TEAM = """team:
  host: {host}
  members:
    an@corp.com: {{roles: [ba], login: an-ba}}
    binh@corp.com: {{roles: [be_lead, be_dev], login: binh-dev}}
    chi@corp.com: {{roles: [fe_lead, fe_dev], login: chi-fe}}
    dung@corp.com: {{roles: [qe], login: dung-qe}}
    em@corp.com: {{roles: [be_dev], login: em-dev}}
  areas:
    backend: {{paths: ["services/**", "tests/services/**"], lead: be_lead, roles: [be_dev]}}
    frontend: {{paths: ["web/**"], lead: fe_lead, roles: [fe_dev]}}
  approvals:
    requirement_confirmed: [ba, be_lead, fe_lead]
    plan_approved: area_lead
    verification_passed: [qe]
"""

PLAN = """# Plan: Login

## Tasks

### Track 1: API
**Metadata:**
- Area: backend
- Owner: em@corp.com

**Files:**
- Create: `services/auth/login.py`
- Test: `tests/services/test_login.py:1-40`

### Track 2: Form
**Metadata:**
- Area: frontend
- Owner: chi@corp.com

**Files:**
- Modify: `web/login.tsx:10-20`

## Integration
- Branch: feat/login
"""

FAKE = """#!{python}
import json, sys
from pathlib import Path
here = Path(__file__).resolve().parent
with open(here / "calls.log", "a", encoding="utf-8") as log:
    log.write(json.dumps([Path(sys.argv[0]).name, *sys.argv[1:]]) + "\\n")
rules = json.loads((here / (Path(sys.argv[0]).name + ".json")).read_text(encoding="utf-8"))
argv = sys.argv[1:]
best = None
for rule in rules:
    prefix = rule["argv"]
    if argv[:len(prefix)] == prefix and (best is None or len(prefix) > len(best["argv"])):
        best = rule
if best is None:
    sys.stderr.write("fake: no rule for " + " ".join(argv) + "\\n")
    sys.exit(1)
out = best.get("stdout", "")
sys.stdout.write(out if isinstance(out, str) else json.dumps(out))
sys.stderr.write(best.get("stderr", ""))
sys.exit(best.get("exit", 0))
"""


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True).stdout


def make_team_repo(root: Path, *, email: str = "binh@corp.com", host: str = "github", team: str | None = None,
                   extra: str = "") -> Path:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", email)
    git(root, "config", "user.name", "T")
    origin = {"gitlab": "https://gitlab.corp.com/group/app.git"}.get(host, "git@github.com:org/app.git")
    git(root, "remote", "add", "origin", origin)
    (root / ".agent-workflow").mkdir()
    body = TEAM.format(host=host) if team is None else team
    (root / ".agent-workflow/config.yaml").write_text(f"schema_version: '2.7'\n{extra}{body}", encoding="utf-8")
    return root


def write(root: Path, relative: str, text: str) -> Path:
    path = Path(root) / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def fake_cli(bin_dir: Path, name: str, rules: list[dict]) -> Path:
    """An executable `name` on `bin_dir` answering by longest argv prefix; every call is logged to calls.log."""
    bin_dir = Path(bin_dir)
    bin_dir.mkdir(parents=True, exist_ok=True)
    (bin_dir / f"{name}.json").write_text(json.dumps(rules), encoding="utf-8")
    path = bin_dir / name
    path.write_text(FAKE.format(python=sys.executable), encoding="utf-8")
    path.chmod(0o755)
    return path


def calls(bin_dir: Path) -> list[list[str]]:
    log = Path(bin_dir) / "calls.log"
    if not log.is_file():
        return []
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]


def path_with(bin_dir: Path) -> dict[str, str]:
    return {"PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"}


def gh_pr(url: str = "https://github.com/org/app/pull/7", *, state: str = "MERGED", author: str = "an-ba",
          reviews: list[tuple[str, str, str]] = (), files: list[str] = (), head: str = "h" * 40,
          body: str = "") -> dict:
    return {
        "url": url, "state": state, "mergeCommit": {"oid": "m" * 40} if state == "MERGED" else None,
        "headRefOid": head, "author": {"login": author},
        "reviews": [{"author": {"login": login}, "state": review_state, "commit": {"oid": commit}}
                    for login, review_state, commit in reviews],
        "files": [{"path": item} for item in files], "body": body,
    }


def run_cli(root: Path, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(LAUNCHER), *args, "--repository", str(root)], cwd=root, text=True,
                          capture_output=True, env={**os.environ, **(env or {})}, check=False)
