"""`gin-workflow routes resolve`: resolve plan tracks to the main harness and write the assignment manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
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
from .project_detect import detect_project


def resolve(
    root: Path,
    workflow_id: str,
    tracks: Sequence[Mapping[str, Any]],
    config: EffectiveConfig,
    harness: str,
) -> dict[str, Any]:
    """Every diagnostic, or the routes plus the written manifest; nothing is written on a diagnostic."""
    diagnostics = [f"{e.task_id}.{e.field}: {e.message}" for e in validate_plan_assignments(tracks, config)]
    entries: list[dict[str, Any]] = []
    if not diagnostics:
        for track in tracks:
            try:
                request = AssignmentRequest(str(track.get("task_id", "")), str(track.get("provider_role", "")),
                                            str(track.get("reasoning", "")), harness, workflow_id)
                entries.append(AssignmentManifest(workflow_id, request, resolve_main_harness(request)).to_dict())
            except AssignmentResolutionError as error:
                diagnostics.append(f"{track.get('task_id')}.route: {error}")
    manifest = None
    if not diagnostics:
        path = write_assignments(root, workflow_id, entries)
        manifest = str(path.relative_to(root)) if path.is_relative_to(root) else str(path)
    return {"workflow_id": workflow_id, "main_harness": harness, "routes": entries if manifest else [],
            "diagnostics": diagnostics, "warnings": [], "manifest": manifest}


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
