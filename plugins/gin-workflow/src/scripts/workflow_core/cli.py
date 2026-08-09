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
from .setup_service import COMMANDS, SetupError


CLI_VERSION = "2.1"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gin-workflow setup")
    parser.add_argument("action", choices=tuple(COMMANDS))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--harness", choices=("claude", "codex", "antigravity"))
    parser.add_argument("--non-interactive", action="store_true")
    parser.add_argument("--approve", action="store_true")
    parser.add_argument("--set", dest="assignments", action="append", default=[])
    parser.add_argument("--to-version", dest="target_version", default=CURRENT_VERSION)
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--bundle", type=Path)
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
        print(f"gin-workflow {CLI_VERSION}")
        return 0
    if not argv or argv[0] != "setup":
        print("usage: gin-workflow setup <command>", file=sys.stderr)
        return 2
    parsed = _parser().parse_args(argv[1:])
    options = vars(parsed)
    action = options.pop("action")
    output_format = options.pop("format")
    try:
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
