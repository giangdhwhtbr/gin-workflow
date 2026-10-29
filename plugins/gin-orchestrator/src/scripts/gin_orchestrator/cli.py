"""`python -m gin_orchestrator`: the orchestrator CLI contract (v2) — version, health, models, routes, reviewer,
doctor and configure."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Sequence
import uuid

from workflow_core.ext import (
    AssignmentManifest,
    AssignmentRequest,
    AssignmentResolutionError,
    EffectiveConfig,
    atomic_write_text,
    catalog_for,
    load_effective_config,
    main_checkout,
    require_yaml,
    tier_of,
    validate_plan_assignments,
)

from .antigravity_worker import antigravity_health
from .claude_worker import claude_health
from .codex_worker import codex_health
from .config import roles, validate_orchestrator_config
from .doctor import doctor_report
from .local_config import LOCAL_FILE, load_local_config, validate_local_config
from .native_cli import NativeCliRunner, list_models
from .opencode_worker import opencode_health
from .routes import resolve_assignment

CONTRACT_VERSION = 2
ORCHESTRATOR_VERSION = "0.2.0"
REQUIRES_GIN_WORKFLOW = ">=2.0,<3"
CAPABILITIES = ["health", "models", "routes", "reviewer", "doctor"]
HEALTH = {"claude": claude_health, "codex": codex_health, "antigravity": antigravity_health,
          "opencode": opencode_health}


class CliError(Exception):
    """A command cannot run (exit 2)."""


def _health(args: argparse.Namespace) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    if args.model is not None:
        kwargs = {"model": args.model, "native_runner": NativeCliRunner(), "workspace": args.workspace}
        if args.provider == "codex" and args.effort is not None:
            kwargs["effort"] = args.effort
    health = HEALTH[args.provider](args.executable, **kwargs)
    return {"available": health.available, "reason": health.reason}


def _routes_resolve(args: argparse.Namespace) -> dict[str, Any]:
    root = args.repository.resolve()
    tracks = json.loads(args.tracks.read_text(encoding="utf-8"))
    if not isinstance(tracks, list) or not all(isinstance(track, Mapping) for track in tracks):
        raise CliError("--tracks must be a JSON list of objects")
    config = load_effective_config(root)
    # Tracks are routes in the main harness's catalog, so validate them against it.
    merged = EffectiveConfig({**config.to_dict(), "harness": args.main_harness,
                              "routing": {**(config.get("routing") or {}), "roles": roles(config)}}, root)
    diagnostics = list(validate_plan_assignments(tracks, merged))
    task_ids = [str(track.get("task_id", "")).strip() for track in tracks]
    for index, task_id in enumerate(task_ids):
        if not task_id:
            diagnostics.append(f"task-{index + 1}.task_id: task_id is required")
        elif task_id in task_ids[:index]:
            diagnostics.append(f"{task_id}.task_id: duplicate task_id")
    entries: list[dict[str, Any]] = []
    if not diagnostics:
        local = load_local_config(root)
        for task_id, track in zip(task_ids, tracks):
            try:
                request = AssignmentRequest(
                    task_id,
                    str(track.get("provider_role", "")),
                    str(track.get("model", "")),
                    track.get("effort"),
                    args.main_harness,
                    args.workflow_id,
                )
                entries.append(AssignmentManifest(args.workflow_id, request,
                                                  resolve_assignment(request, config, local)).to_dict())
            except AssignmentResolutionError as error:
                diagnostics.append(f"{task_id}.route: {error}")
    return {"workflow_id": args.workflow_id, "main_harness": args.main_harness,
            "routes": [] if diagnostics else entries, "diagnostics": diagnostics}


def _reviewer(args: argparse.Namespace) -> list[dict[str, Any]]:
    root = args.repository.resolve()
    config = load_effective_config(root)
    review = (config.get("routing") or {}).get("review") or {}
    # --model/--effort are the implementer's route, in the implementer's catalog.
    request = AssignmentRequest(
        "reviewer",
        str(review.get("role", "review")),
        args.model,
        args.effort,
        config.harness or args.implementer,
    )
    candidates = resolve_assignment(request, config, load_local_config(root), source_harness=args.implementer)
    tier = tier_of(catalog_for(config, args.implementer), args.model)
    # `session` independence: a fresh session of the implementer's provider may review.
    independent = (bool(review.get("require_independent", True)) and tier != "low"
                   and review.get("independence", "session") != "session")
    routes = [c for c in candidates if not independent or c.provider != args.implementer]
    if not routes and review.get("allow_self_review_fallback"):
        routes = list(candidates)
    return [{"provider": c.provider, "model": c.model, "effort": c.effort,
             "actor_id": (f"reviewer:{c.provider}" if c.provider != args.implementer
                          else f"reviewer:{c.provider}:session-{uuid.uuid4().hex[:8]}")} for c in routes]


def _doctor(args: argparse.Namespace) -> dict[str, Any]:
    root = args.repository.resolve()
    return doctor_report(root, load_effective_config(root), probe=True)


def _set_nested(target: dict[str, Any], assignment: str) -> None:
    if "=" not in assignment:
        raise CliError(f"assignment must use KEY=VALUE: {assignment}")
    key, raw = assignment.split("=", 1)
    path = [part for part in key.split(".") if part]
    if not path:
        raise CliError("assignment key must not be empty")
    yaml = require_yaml()
    try:
        value = yaml.safe_load(raw)
    except yaml.YAMLError as error:
        raise CliError(f"invalid value for {key}: {error}") from error
    for part in path[:-1]:
        child = target.setdefault(part, {})
        if not isinstance(child, dict):
            raise CliError(f"cannot set {key}: {part} is not a mapping")
        target = child
    target[path[-1]] = value


def _gitignore_with_local(path: Path) -> str:
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    if Path(LOCAL_FILE).name not in lines:
        lines.append(Path(LOCAL_FILE).name)
    return "\n".join(lines) + "\n"


def _configure(args: argparse.Namespace) -> dict[str, Any]:
    root = args.repository.resolve()
    for assignment in args.set:
        if not assignment.startswith("orchestrator."):
            raise CliError(f"--set keys must start with orchestrator.: {assignment}")
    candidate = load_effective_config(root).to_dict()
    for assignment in args.set:
        _set_nested(candidate, assignment)
    validate_orchestrator_config(candidate)
    local_path = main_checkout(root) / LOCAL_FILE
    yaml = require_yaml()
    local: Any = {"schema_version": str(candidate["schema_version"])}
    if local_path.is_file():
        try:
            local = yaml.safe_load(local_path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as error:
            raise CliError(f"invalid {local_path.name}: {error}") from error
        if not isinstance(local, dict):
            raise CliError(f"invalid {local_path.name}: the top level must be a mapping")
    for assignment in args.local_set:
        _set_nested(local, assignment)
    if args.local_set:
        validate_local_config(local)
    actions = (["update .agent-workflow/config.yaml", "refresh generated configuration"] if args.set else []) + (
        [f"write {LOCAL_FILE}"] if args.local_set else [])
    if args.dry_run:
        return {"status": "would_configure", "actions": actions}
    if not args.approve:
        raise CliError("configure requires explicit --approve before changing configuration")
    # Portable keys first: gin-workflow may reject them, and then nothing local was written.
    if args.set:
        gin_workflow = shutil.which("gin-workflow")
        if gin_workflow is None:
            raise CliError("gin-workflow is not on PATH; install it with ./install.sh --plugin gin-orchestrator")
        done = subprocess.run([gin_workflow, "setup", "configure", *(a for s in args.set for a in ("--set", s)),
                               "--approve", "--format", "json", "--repository", str(root)],
                              capture_output=True, text=True, check=False)
        if done.returncode != 0:
            raise CliError(f"gin-workflow setup configure failed: {(done.stderr or done.stdout).strip()}")
    if args.local_set:
        atomic_write_text(local_path, yaml.safe_dump(local, sort_keys=True))
        ignore_path = local_path.parent / ".gitignore"
        atomic_write_text(ignore_path, _gitignore_with_local(ignore_path))
    return {"status": "configured", "actions": actions}


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
    routes = commands.add_parser("routes")
    routes_commands = routes.add_subparsers(dest="routes_command", required=True)
    resolve = routes_commands.add_parser("resolve")
    resolve.add_argument("--workflow-id", required=True)
    resolve.add_argument("--tracks", type=Path, required=True)
    resolve.add_argument("--main-harness", required=True)
    reviewer = commands.add_parser("reviewer")
    reviewer.add_argument("--base", required=True)
    reviewer.add_argument("--implementer", required=True)
    reviewer.add_argument("--model", required=True)
    reviewer.add_argument("--effort", default=None)
    doctor = commands.add_parser("doctor")
    configure = commands.add_parser("configure")
    configure.add_argument("--set", action="append", default=[])
    configure.add_argument("--local-set", action="append", default=[])
    configure.add_argument("--dry-run", action="store_true")
    configure.add_argument("--approve", action="store_true")
    for command in (version, health, models, resolve, reviewer, doctor, configure):
        command.add_argument("--json", action="store_true")
    for command in (resolve, reviewer, doctor, configure):
        command.add_argument("--repository", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    try:
        if args.command == "version":
            payload: Any = {"contract": CONTRACT_VERSION, "orchestrator_version": ORCHESTRATOR_VERSION,
                            "requires_gin_workflow": REQUIRES_GIN_WORKFLOW, "capabilities": CAPABILITIES}
        elif args.command == "health":
            payload = _health(args)
        elif args.command == "models":
            payload = list_models(args.provider)
        elif args.command == "routes":
            payload = _routes_resolve(args)
        elif args.command == "reviewer":
            payload = _reviewer(args)
        elif args.command == "doctor":
            payload = _doctor(args)
        else:
            payload = _configure(args)
    except (OSError, ValueError, CliError, AssignmentResolutionError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
