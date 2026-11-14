"""`gin workspace`: clone the manifest's repositories and show their state."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Sequence

from .configuration import ConfigValidationError
from . import setup_service
from . import workspace as ws


def _run_git(argv: Sequence[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *argv], cwd=cwd, text=True, capture_output=True, check=False)


def clone(space: ws.Workspace, paths: Sequence[str], all_repos: bool) -> list[dict[str, Any]]:
    chosen = list(space.repos) if all_repos else [space.repo(path) for path in paths]
    if any(repo is None for repo in chosen):
        missing = [path for path, repo in zip(paths, chosen) if repo is None]
        raise ws.WorkspaceError(f"not in workspace.repos: {', '.join(missing)}")
    if not chosen:
        raise ws.WorkspaceError("name a repository path or pass --all")
    results: list[dict[str, Any]] = []
    try:
        from . import hooks, team, team_init
        try:
            team_config = team.team_for_repo(space.root)
        except Exception:
            team_config = None
        for repo in chosen:
            target = space.checkout(repo)
            if space.present(repo):
                results.append({"path": repo.path, "status": "present"})
                continue
            argv = ["clone", "--branch", repo.default_branch, *(["--depth", "1"] if repo.frozen else []),
                    repo.url, str(target)]
            done = _run_git(argv)
            if done.returncode:
                cloned = [row["path"] for row in results if row["status"] == "cloned"]
                so_far = f" (cloned so far: {', '.join(cloned)})" if cloned else ""
                raise ws.WorkspaceError(f"{repo.path}: {done.stderr.strip() or 'git clone failed'}{so_far}")
            row: dict[str, Any] = {"path": repo.path, "status": "cloned"}
            if repo.workable:
                hooks_dict: dict[str, str] = {}
                if repo.checks:
                    try:
                        hook_res = hooks.install(target)
                        if hook_res.get("status") == "missing":
                            hooks_dict["pre-commit"] = "missing"
                            hooks_dict["pre-push"] = "missing"
                        else:
                            for hook in ("pre-commit", "pre-push"):
                                if hook in hook_res.get("hooks", {}):
                                    hooks_dict[hook] = hook_res["hooks"][hook]
                    except Exception:
                        hooks_dict["pre-commit"] = "missing"
                        hooks_dict["pre-push"] = "missing"
                if team_config is not None and (target / ".githooks/commit-msg").is_file():
                    try:
                        team_res = team_init.install_hook(target)
                        hooks_dict["commit-msg"] = team_res.get("status", "missing")
                    except Exception:
                        hooks_dict["commit-msg"] = "missing"
                row["hooks"] = hooks_dict
            results.append(row)
    finally:
        ws.ensure_gitignore(space.root, [f"/{row['path']}" for row in results])
    return results


def status(space: ws.Workspace) -> list[dict[str, Any]]:
    rows = []
    for repo in space.repos:
        present = space.present(repo)
        dirty = None
        if present:
            porcelain = _run_git(["status", "--porcelain"], space.checkout(repo))
            dirty = bool(porcelain.stdout.strip()) if porcelain.returncode == 0 else None
        rows.append({"path": repo.path, "present": present,
                     "branch": ws.branch(space.checkout(repo)) if present else None,
                     "dirty": dirty, "frozen": repo.frozen})
    return rows


def _text(rows: list[dict[str, Any]]) -> str:
    width = max(len(row["path"]) for row in rows)
    lines = []
    for row in rows:
        state = "present" if row["present"] else "missing"
        tree = "" if row["dirty"] is None else ("dirty" if row["dirty"] else "clean")
        lines.append("  ".join(part for part in (row["path"].ljust(width), state, row["branch"] or "", tree,
                                                 "frozen" if row["frozen"] else "") if part))
    return "\n".join(lines)


def add(
    root: Path,
    path: str,
    *,
    url: str,
    shape: str = "",
    frozen: bool = False,
    default_branch: str | None = None,
    checks: Sequence[str] = (),
) -> dict[str, Any]:
    done = _run_git(["rev-parse", "--show-toplevel"], cwd=root)
    if done.returncode:
        raise ws.WorkspaceError(f"not a git repository: {root}")
    top = Path(done.stdout.strip()).resolve()
    config_path = top / ".agent-workflow/config.yaml"
    if not config_path.is_file():
        raise ws.WorkspaceError("not a workspace parent: run /gin:setup and answer workspace")
    yaml = ws.require_yaml()
    try:
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise ws.WorkspaceError(f"{config_path}: {error}") from error
    if not isinstance(config, dict):
        raise ws.WorkspaceError("not a workspace parent: run /gin:setup and answer workspace")
    workspace_block = config.get("workspace")
    if not isinstance(workspace_block, dict):
        raise ws.WorkspaceError("not a workspace parent: run /gin:setup and answer workspace")
    existing = workspace_block.get("repos")
    if not isinstance(existing, list):
        raise ws.WorkspaceError("not a workspace parent: run /gin:setup and answer workspace")
    parsed_checks: dict[str, str] = {}
    for item in checks:
        if "=" not in item:
            raise ws.WorkspaceError(f"--check must be NAME=COMMAND: {item}")
        name, command = item.split("=", 1)
        name = name.strip()
        command = command.strip()
        if not name or not command:
            raise ws.WorkspaceError(f"--check must be NAME=COMMAND: {item}")
        parsed_checks[name] = command
    raw: dict[str, Any] = {"path": path, "url": url}
    if shape:
        raw["shape"] = shape
    if frozen:
        raw["frozen"] = True
    if default_branch:
        raw["default_branch"] = default_branch
    if parsed_checks:
        raw["verify"] = {"checks": parsed_checks}
    ws.repos_from({"workspace": {"repos": [*existing, raw]}})
    try:
        setup_service.configure(
            top,
            assignments=[f"workspace.repos={json.dumps([*existing, raw])}"],
            approve=True,
        )
    except (setup_service.SetupError, ConfigValidationError) as error:
        raise ws.WorkspaceError(str(error)) from error
    return {"path": path, "added": True, "next": f"gin workspace clone {path}"}


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="gin workspace",
                                     description="clone the repositories of workspace.repos and show their state")
    commands = parser.add_subparsers(dest="command", required=True)
    add_parser = commands.add_parser(
        "add", help="record a repository entry in workspace.repos",
        description="record a repository entry in workspace.repos; validates the entry and writes through configure")
    add_parser.add_argument("path", help="manifest path of the repository")
    add_parser.add_argument("--url", required=True, help="git clone URL of the repository")
    add_parser.add_argument("--shape", default="", help="repository shape: frontend, backend, library, qa, beads")
    add_parser.add_argument("--frozen", action="store_true", help="mark the repository as read-only legacy code")
    add_parser.add_argument("--default-branch", default=None, help="default git branch to clone (default: main)")
    add_parser.add_argument("--check", dest="checks", action="append", default=[], metavar="NAME=COMMAND",
                            help="verification check to configure (repeatable)")
    clone_parser = commands.add_parser(
        "clone", help="clone the named entries, or every entry with --all, at their manifest paths",
        description="clone the named entries, or every entry with --all, at their manifest paths; "
                    "an entry already present is reported as present; each path is added to the parent .gitignore")
    clone_parser.add_argument("paths", nargs="*", help="manifest paths to clone")
    clone_parser.add_argument("--all", dest="all_repos", action="store_true", help="every entry of workspace.repos")
    status_parser = commands.add_parser(
        "status", help="one line per entry: path, present or missing, branch, clean or dirty, frozen",
        description="one line per entry: path, present or missing, branch, clean or dirty, frozen")
    for sub in (add_parser, clone_parser, status_parser):
        sub.add_argument("--repository", type=Path, default=None,
                         help="a directory inside the workspace (default: the current directory)")
        sub.add_argument("--json", dest="as_json", action="store_true", help="print JSON instead of text")
    args = parser.parse_args(list(argv))
    start = args.repository if args.repository is not None else Path.cwd()
    try:
        if args.command == "add":
            result = add(
                start,
                args.path,
                url=args.url,
                shape=args.shape,
                frozen=args.frozen,
                default_branch=args.default_branch,
                checks=args.checks,
            )
            print(json.dumps(result) if args.as_json else f"added {result['path']}; next: {result['next']}")
            return 0
        located = ws.locate(start)
        if located.workspace is None:
            raise ws.WorkspaceError(f"not in a workspace: {Path(start).resolve()}")
        if args.command == "clone":
            rows = clone(located.workspace, args.paths, args.all_repos)
            from .team_init import active_hooks_dir
            for row in rows:
                for hook, state in (row.get("hooks") or {}).items():
                    if state == "occupied":
                        repo = located.workspace.repo(row["path"])
                        target = located.workspace.checkout(repo) if repo else located.workspace.root / row["path"]
                        try:
                            hook_file = active_hooks_dir(target) / hook
                        except Exception:
                            hook_file = target / ".git/hooks" / hook
                        if hook == "commit-msg":
                            chain = f'add `exec "$(git rev-parse --show-toplevel)/.githooks/commit-msg" "$@"` to {hook_file} to chain it'
                        else:
                            chain = f'add `exec gin hooks run {hook} "$@"` to {hook_file} to chain it'
                        print(f"{row['path']}: {chain}", file=sys.stderr)
            if args.as_json:
                print(json.dumps({"repos": rows}))
            else:
                lines = []
                for row in rows:
                    lines.append(f"{row['path']}: {row['status']}")
                    for hook, state in (row.get("hooks") or {}).items():
                        lines.append(f"{row['path']}: {hook}: {state}")
                print("\n".join(lines))
        else:
            rows = status(located.workspace)
            print(json.dumps({"repos": rows}) if args.as_json else _text(rows))
    except (ws.WorkspaceError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0
