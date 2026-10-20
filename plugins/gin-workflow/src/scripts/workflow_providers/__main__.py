"""`python -m workflow_providers`: the orchestrator CLI contract (v1) — version, health, models."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from .antigravity_worker import antigravity_health
from .claude_worker import claude_health
from .codex_worker import codex_health
from .native_cli import NativeCliRunner, list_models
from .opencode_worker import opencode_health

CONTRACT_VERSION = 1
# ponytail: no own version until the split gives this package its own release
ORCHESTRATOR_VERSION = "bundled"
HEALTH = {"claude": claude_health, "codex": codex_health, "antigravity": antigravity_health,
          "opencode": opencode_health}


def _health(args: argparse.Namespace) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    if args.model is not None:
        kwargs = {"model": args.model, "native_runner": NativeCliRunner(), "workspace": args.workspace}
        if args.provider == "codex" and args.effort is not None:
            kwargs["effort"] = args.effort
    health = HEALTH[args.provider](args.executable, **kwargs)
    return {"available": health.available, "reason": health.reason}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gin-orchestrator")
    commands = parser.add_subparsers(dest="command", required=True)
    version = commands.add_parser("version")
    health = commands.add_parser("health")
    health.add_argument("--provider", required=True, choices=tuple(HEALTH))
    health.add_argument("--executable", required=True)
    health.add_argument("--model")
    health.add_argument("--effort")
    health.add_argument("--workspace", type=Path)
    models = commands.add_parser("models")
    models.add_argument("--provider", required=True)
    for command in (version, health, models):
        command.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "version":
        payload: Any = {"contract_version": CONTRACT_VERSION, "orchestrator_version": ORCHESTRATOR_VERSION}
    elif args.command == "health":
        payload = _health(args)
    else:
        payload = list_models(args.provider)
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
