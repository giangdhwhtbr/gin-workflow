"""Passing verify runs recorded against the tree they tested, so a reviewer can skip a rerun."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Sequence

from .checkout import main_checkout
from .events import WorkflowEvent, WorkflowEventStore
from . import workspace

# Not the name of the removed verification gate: usage attribution still maps that event to the `verify` stage.
EVENT_TYPE = "checks.passed"
WORKFLOW_ID = "checks"


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=False)


def _events_path(root: Path) -> Path:
    return main_checkout(Path(root).resolve()) / ".agent-workflow/runtime/events.jsonl"


def clean_tree(root: Path) -> str | None:
    """HEAD's tree hash when no tracked file differs from HEAD; None otherwise."""
    status = _git(root, "status", "--porcelain", "--untracked-files=no")
    if status.returncode or status.stdout.strip():
        return None
    tree = _git(root, "rev-parse", "HEAD^{tree}")
    return tree.stdout.strip() if tree.returncode == 0 else None


def record(root: Path, hook: str, tree: str, commands: Sequence[str]) -> None:
    path = _events_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    WorkflowEventStore(path).append(WorkflowEvent.create(
        event_type=EVENT_TYPE, workflow_id=WORKFLOW_ID,
        payload={"tree": tree, "hook": hook, "commands": sorted(commands)}))


def check(root: Path, commit: str | None = None) -> tuple[dict[str, Any] | None, str]:
    """The newest record that ran `test` on the commit's tree, or on HEAD's tree when nothing tracked changed."""
    if commit is None:
        tree = clean_tree(root)
        if tree is None:
            return None, "tracked files differ from HEAD; commit them first"
    else:
        done = _git(root, "rev-parse", "--verify", "--quiet", f"{commit}^{{tree}}")
        if done.returncode:
            return None, f"unknown commit: {commit}"
        tree = done.stdout.strip()
    path = _events_path(root)
    events = WorkflowEventStore(path).read_all() if path.is_file() else []
    matches = [event for event in events
               if event.event_type == EVENT_TYPE and (event.payload or {}).get("tree") == tree]
    if not matches:
        return None, f"no passing check recorded for tree {tree}"
    tested = [event for event in matches
              if any(name == "test" or name.endswith(":test") for name in event.payload["commands"])]
    if not tested:
        return None, f"the checks recorded for tree {tree} ran no test command"
    newest = max(tested, key=lambda event: event.timestamp)
    return {"tree": tree, "hook": newest.payload["hook"], "commands": list(newest.payload["commands"]),
            "recorded_at": newest.timestamp}, ""


def run(root: Path) -> int:
    """Run the pre-push verify commands on the committed tree; a pass is recorded."""
    if clean_tree(root) is None:
        print("error: tracked files differ from HEAD; commit them so the record names the tree it tested",
              file=sys.stderr)
        return 2
    from .hooks import verify  # hooks imports this module

    return verify(Path(root), "pre-push")


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="gin evidence")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--repository", type=Path, default=None)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("run", parents=[common])
    checker = sub.add_parser("check", parents=[common])
    checker.add_argument("--commit")
    checker.add_argument("--json", action="store_true")
    args = parser.parse_args(list(argv))
    args.repository = workspace.repository_root(args.repository)
    root = args.repository.resolve()
    if args.command == "run":
        return run(root)
    found, reason = check(root, args.commit)
    if args.json:
        print(json.dumps({"record": found, "reason": reason}))
    elif found:
        print(f"passed {', '.join(found['commands'])} on tree {found['tree']} ({found['hook']}, {found['recorded_at']})")
    else:
        print(reason)
    return 0 if found else 1
