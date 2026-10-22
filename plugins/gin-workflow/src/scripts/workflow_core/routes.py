"""`gin-workflow routes resolve`: resolve plan tracks to the main harness and write the assignment manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile
from typing import Any, Mapping, Sequence

from .assignments import (
    AssignmentManifest,
    AssignmentRequest,
    AssignmentResolutionError,
    resolve_main_harness,
    validate_plan_assignments,
    write_assignments,
)
from .configuration import ConfigValidationError, load_effective_config
from .models import EffectiveConfig
from . import orchestrator_client
from .project_detect import detect_project


def resolve(
    root: Path,
    workflow_id: str,
    tracks: Sequence[Mapping[str, Any]],
    config: EffectiveConfig,
    harness: str,
) -> dict[str, Any]:
    """Every diagnostic, or the routes plus the written manifest; nothing is written on a diagnostic."""
    warnings: list[str] = []
    config_dict = config.to_dict() if hasattr(config, "to_dict") else dict(config)

    if orchestrator_client.delegates(config_dict, "routes"):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as tf:
            json.dump(list(tracks), tf)
            tracks_file = Path(tf.name)
        try:
            reply = orchestrator_client.call([
                "routes", "resolve",
                "--workflow-id", workflow_id,
                "--tracks", str(tracks_file),
                "--main-harness", harness,
                "--repository", str(root),
            ])
        except orchestrator_client.OrchestratorError as error:
            warnings.append(f"gin-orchestrator failed ({error}); routing every track to the main harness")
            reply = None
        finally:
            tracks_file.unlink(missing_ok=True)
        if reply is not None and not (
            isinstance(reply, Mapping)
            and isinstance(reply.get("diagnostics", []), list)
            and isinstance(reply.get("routes", []), list)
        ):
            warnings.append(f"gin-orchestrator failed ({orchestrator_client.FAILED}); routing every track to the main harness")
            reply = None

        if reply is not None:
            diagnostics = list(reply.get("diagnostics", []))
            if diagnostics:
                return {
                    "workflow_id": workflow_id,
                    "main_harness": harness,
                    "routes": [],
                    "diagnostics": diagnostics,
                    "warnings": warnings,
                    "manifest": None,
                }
            entries = list(reply.get("routes", []))
            manifest = None
            try:
                path = write_assignments(root, workflow_id, entries)
            except (AssignmentResolutionError, OSError) as error:
                diagnostics.append(f"workflow_id: {error}")
            else:
                manifest = str(path.relative_to(root)) if path.is_relative_to(root) else str(path)
            return {
                "workflow_id": workflow_id,
                "main_harness": harness,
                "routes": entries if manifest else [],
                "diagnostics": diagnostics,
                "warnings": warnings,
                "manifest": manifest,
            }
    else:
        warn = orchestrator_client.warning(config_dict)
        if warn is not None:
            warnings.append(warn)

    # A role the orchestrator owns routes to the main harness like any other while it is away.
    orchestrator = config_dict.get("orchestrator")
    orchestrator_roles = orchestrator.get("roles") if isinstance(orchestrator, Mapping) else None
    owned = {str(t.get("task_id", "")).strip() for t in tracks
             if isinstance(orchestrator_roles, Mapping) and t.get("provider_role") in orchestrator_roles}
    diagnostics = [f"{e.task_id}.{e.field}: {e.message}" for e in validate_plan_assignments(tracks, config)
                   if not (e.field == "provider_role" and e.task_id in owned)]
    task_ids = [str(track.get("task_id", "")).strip() for track in tracks]
    for index, task_id in enumerate(task_ids):
        if not task_id:
            diagnostics.append(f"task-{index + 1}.task_id: task_id is required")
        elif task_id in task_ids[:index]:
            diagnostics.append(f"{task_id}.task_id: duplicate task_id")
    entries: list[dict[str, Any]] = []
    if not diagnostics:
        for task_id, track in zip(task_ids, tracks):
            try:
                request = AssignmentRequest(task_id, str(track.get("provider_role", "")),
                                            str(track.get("reasoning", "")), harness, workflow_id)
                entries.append(AssignmentManifest(workflow_id, request, resolve_main_harness(request)).to_dict())
            except AssignmentResolutionError as error:
                diagnostics.append(f"{task_id}.route: {error}")
    manifest = None
    if not diagnostics:
        try:
            path = write_assignments(root, workflow_id, entries)
        except (AssignmentResolutionError, OSError) as error:
            diagnostics.append(f"workflow_id: {error}")
        else:
            manifest = str(path.relative_to(root)) if path.is_relative_to(root) else str(path)
    return {"workflow_id": workflow_id, "main_harness": harness, "routes": entries if manifest else [],
            "diagnostics": diagnostics, "warnings": warnings, "manifest": manifest}


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="gin-workflow routes")
    commands = parser.add_subparsers(dest="command", required=True)
    resolve_parser = commands.add_parser("resolve")
    resolve_parser.add_argument("--workflow-id", required=True)
    resolve_parser.add_argument("--tracks", type=Path, required=True)
    resolve_parser.add_argument("--repository", type=Path, default=Path.cwd())
    resolve_parser.add_argument("--json", action="store_true")
    args = parser.parse_args(list(argv))
    root = args.repository.resolve()
    try:
        tracks = json.loads(args.tracks.read_text(encoding="utf-8"))
        config = load_effective_config(root)
    except (OSError, json.JSONDecodeError, ConfigValidationError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    if not isinstance(tracks, list) or not all(isinstance(track, Mapping) for track in tracks):
        print("error: --tracks must be a JSON list of objects", file=sys.stderr)
        return 2
    harness = config.harness or detect_project(root).get("harness")
    if not harness:
        print("error: main harness unknown; run gin-workflow setup configure --harness <harness> --approve",
              file=sys.stderr)
        return 2
    payload = resolve(root, args.workflow_id, tracks, config, harness)
    print(json.dumps(payload))
    return 2 if payload["diagnostics"] else 0
