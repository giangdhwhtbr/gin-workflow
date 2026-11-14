"""Command-line interface for deterministic repository setup."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Sequence

from .bundles import BundleError
from .configuration import ConfigValidationError
from .migrations import CURRENT_VERSION, MigrationError
from .models import DependencyUnavailableError
from .project import RIGORS, SHAPES, STAGES
from .setup_service import COMMANDS, SetupError


CLI_VERSION = "3.0"
TOP_COMMANDS = ("setup", "state", "unblock", "record", "quick-check", "rules", "specs", "docs", "team", "usage",
                "reviewer", "hooks", "evidence", "task", "routes", "paths", "goal", "worktree", "workspace", "milestone")


ACTIONS = {
    "detect": "detect project stage, shape, monorepo, stack, packages, verify commands, and code-index state",
    "preset": "turn --project-stage, --project-shape, --rigor, --task-tracking (plus --monorepo, --workspace, "
              "--stack-intent) into --set assignments",
    "models": "list the models a provider CLI reports (--provider)",
    "init": "first setup: write .agent-workflow/config.yaml, the generated files, executables.local.yaml, "
            "and the AGENTS.md block (--dry-run previews; --approve adds a missing block)",
    "configure": "change repository configuration (--set key=value)",
    "refresh": "regenerate .agent-workflow/generated/ from the current configuration, rewrite "
               "executables.local.yaml, and re-render an existing AGENTS.md block",
    "update": "propose, then with --approve apply, a schema migration (--to-version)",
    "doctor": "check configuration, the main harness executable, verify commands, hooks, external CLI paths, "
              "the code index, and the AGENTS.md block (--probe asks the orchestrator for provider health)",
    "status": "show whether the repository is initialized and the generated files exist",
    "diff": "show how the generated configuration differs from what the current inputs would produce",
    "rollback": "restore a validated backup (--backup PATH)",
    "export-bundle": "write a portable configuration bundle (--output PATH)",
    "verify-bundle": "check a portable configuration bundle (--bundle PATH)",
    "harness-override": "set (--harness), show, or clear (--clear) a session override of the main harness",
}


def _parser() -> argparse.ArgumentParser:
    actions = "\n".join(f"  {name:<18} {ACTIONS[name]}" for name in COMMANDS)
    parser = argparse.ArgumentParser(prog="gin setup", formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description=f"configure a repository outside the lifecycle\n\nactions:\n{actions}")
    parser.add_argument("action", choices=tuple(COMMANDS), metavar="action", help="one of the actions above")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--repository", type=Path, default=None)
    parser.add_argument("--harness", choices=("claude", "codex", "antigravity", "opencode", "copilot"))
    parser.add_argument("--non-interactive", action="store_true")
    parser.add_argument("--approve", action="store_true")
    parser.add_argument("--set", dest="assignments", action="append", default=[])
    parser.add_argument("--to-version", dest="target_version", default=CURRENT_VERSION)
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--clear", action="store_true")
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--project-stage", choices=STAGES)
    parser.add_argument("--project-shape", choices=SHAPES)
    parser.add_argument("--rigor", choices=RIGORS)
    parser.add_argument("--task-tracking", choices=("markdown", "beads"))
    parser.add_argument("--monorepo", action="store_true")
    parser.add_argument("--workspace", action="store_true")
    parser.add_argument("--stack-intent", default="")
    parser.add_argument("--provider", choices=("claude", "codex", "antigravity", "opencode", "copilot"))
    return parser



def _emit(payload: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(f"status: {payload.get('status', 'unknown')}")
    if payload.get("message"):
        print(payload["message"])
    for action in payload.get("actions", []):
        print(f"- {action}")


def main(arguments: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if arguments is None else arguments)
    if argv == ["--version"]:
        print(f"gin {CLI_VERSION}")
        return 0
    if not argv or argv[0] not in TOP_COMMANDS:
        print(f"usage: gin {{{','.join(TOP_COMMANDS)}}} <command>", file=sys.stderr)
        return 2
    from . import workspace
    try:
        if argv[0] == "routes":
            from .routes import main as routes_main
            return routes_main(argv[1:])
        if argv[0] == "paths":
            import json
            print(json.dumps({"lib_dir": str(Path(__file__).resolve().parents[1])}))
            return 0
        if argv[0] == "goal":
            from .goal import main as goal_main
            return goal_main(argv[1:])
        if argv[0] == "worktree":
            from .worktrees import main as worktrees_main
            return worktrees_main(argv[1:])
        if argv[0] == "workspace":
            from .workspace_cli import main as workspace_main
            return workspace_main(argv[1:])
        if argv[0] == "task":
            from .tasks import main as tasks_main
            return tasks_main(argv[1:])
        if argv[0] == "hooks":
            from .hooks import main as hooks_main
            return hooks_main(argv[1:])
        if argv[0] == "rules":
            from .rules import main as rules_main
            return rules_main(argv[1:])
        if argv[0] == "docs":
            from .docs_check import main as docs_main
            return docs_main(argv[1:])
        if argv[0] == "specs":
            from .specs_cli import main as specs_main
            return specs_main(argv[1:])
        if argv[0] == "team":
            from .team_cli import main as team_main
            return team_main(argv[1:])
        if argv[0] == "milestone":
            from .milestone_cli import main as milestone_main
            return milestone_main(argv[1:])
        if argv[0] == "evidence":
            from .verification import main as evidence_main
            return evidence_main(argv[1:])
        if argv[0] == "usage":
            from .usage_cli import main as usage_main
            return usage_main(argv[1:])
        if argv[0] == "reviewer":
            from .reviewer import main as reviewer_main
            return reviewer_main(argv[1:])
        if argv[0] in ("state", "unblock", "record", "quick-check"):
            from .lifecycle_cli import main as lifecycle_main
            return lifecycle_main(argv)
    except workspace.WorkspaceError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    parsed = _parser().parse_args(argv[1:])
    options = vars(parsed)
    action = options.pop("action")
    output_format = options.pop("format")
    try:
        if action == "doctor" and options.get("repository") is None:
            here = workspace.current(Path.cwd())
            if here.checkout is not None:
                options["current"] = here.checkout
        options["repository"] = workspace.repository_root(options["repository"])
        payload = COMMANDS[action](**options)
    except DependencyUnavailableError as error:
        message = str(error)
        _emit(
            {
                "status": "dependency_unavailable",
                "dependency": message.split("'", 2)[1] if "'" in message else "unknown",
                "message": message,
                "actions": [],
            },
            output_format,
        )
        return 3
    except (SetupError, MigrationError, BundleError, ConfigValidationError, FileNotFoundError, ValueError) as error:
        _emit(
            {
                "status": getattr(error, "status", "error"),
                "message": str(error),
                "actions": [],
            },
            output_format,
        )
        return 2
    _emit(payload, output_format)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
