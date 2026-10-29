"""`gin-workflow routes`: resolve plan tracks and dispatch worker execution."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import json
from pathlib import Path
import sys
import tempfile
from typing import Any

from .assignments import (
    AssignmentManifest,
    AssignmentRequest,
    AssignmentResolutionError,
    _SAFE_WORKFLOW_ID,
    resolve_main_harness,
    validate_plan_assignments,
    write_assignments,
)
from .atomic import atomic_write_text
from .catalog import catalog_for, escalate, route_diagnostics
from .checkout import main_checkout
from .configuration import ConfigValidationError, load_effective_config, require_yaml
from .events import WorkflowEvent, WorkflowEventStore
from .locking import file_lock
from .models import EffectiveConfig
from . import orchestrator_client
from .project_detect import detect_project
from .provider_config import PROVIDER_DEFAULT


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

    diagnostics: list[str] = []
    if not _SAFE_WORKFLOW_ID.fullmatch(workflow_id):
        diagnostics.append(f"workflow_id: unsafe path characters in '{workflow_id}'")

    task_ids = [str(track.get("task_id", "")).strip() for track in tracks]
    for index, task_id in enumerate(task_ids):
        if not task_id:
            diagnostics.append(f"task-{index + 1}.task_id: task_id is required")
        elif task_id in task_ids[:index]:
            diagnostics.append(f"{task_id}.task_id: duplicate task_id")

    orchestrator = config_dict.get("orchestrator")
    orchestrator_roles = orchestrator.get("roles") if isinstance(orchestrator, Mapping) else None
    owned = {
        str(t.get("task_id", "")).strip()
        for t in tracks
        if isinstance(orchestrator_roles, Mapping) and t.get("provider_role") in orchestrator_roles
    }
    raw_diagnostics = validate_plan_assignments(tracks, config)
    for diag in raw_diagnostics:
        if any(f"track {tid}: unknown provider role:" in diag for tid in owned):
            continue
        diagnostics.append(diag)

    entries: list[dict[str, Any]] = []
    if not diagnostics:
        for task_id, track in zip(task_ids, tracks):
            try:
                request = AssignmentRequest(
                    task_id=task_id,
                    provider_role=str(track.get("provider_role", "")),
                    model=str(track.get("model", "")),
                    effort=track.get("effort"),
                    main_harness=harness,
                    workflow_id=workflow_id,
                )
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
    return {
        "workflow_id": workflow_id,
        "main_harness": harness,
        "routes": entries if manifest else [],
        "diagnostics": diagnostics,
        "warnings": warnings,
        "manifest": manifest,
    }


def dispatch(
    root: Path,
    workflow_id: str,
    task_id: str,
    escalate_reason: str | None = None,
) -> tuple[dict[str, Any], int]:
    """Dispatch a track route from the manifest, optionally escalating within the catalog."""
    if not _SAFE_WORKFLOW_ID.fullmatch(workflow_id):
        return {"status": "error", "message": f"unsafe workflow_id: {workflow_id}"}, 2

    manifest_path = (
        main_checkout(Path(root).resolve())
        / ".agent-workflow/runtime/assignments"
        / f"{workflow_id}.yaml"
    )
    if not manifest_path.is_file():
        return {"status": "error", "message": f"manifest not found: {manifest_path}"}, 2

    yaml = require_yaml()
    lock_path = manifest_path.with_name(f".{manifest_path.name}.lock")
    with file_lock(lock_path):
        try:
            data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, yaml.YAMLError) as error:
            return {"status": "error", "message": f"invalid manifest: {error}"}, 2
        if not isinstance(data, Mapping):
            return {"status": "error", "message": "manifest must be a mapping"}, 2

        entry: dict[str, Any] | None = None
        if "tracks" in data and isinstance(data["tracks"], Mapping) and task_id in data["tracks"]:
            track_val = data["tracks"][task_id]
            if isinstance(track_val, Mapping):
                entry = dict(track_val)
        if entry is None and "assignments" in data and isinstance(data["assignments"], Sequence):
            for item in data["assignments"]:
                if isinstance(item, Mapping) and item.get("task_id") == task_id:
                    entry = dict(item)
                    break

        if entry is None:
            return {"status": "error", "message": f"track '{task_id}' not found in manifest"}, 2

        resolved = entry.get("resolved")
        if not isinstance(resolved, Mapping):
            return {"status": "error", "message": f"track '{task_id}' has no resolved route"}, 2

        provider = str(resolved.get("provider", ""))
        if resolved.get("selection_mode") == "provider_default":
            model = PROVIDER_DEFAULT
        else:
            model = str(resolved.get("model", ""))
        effort = resolved.get("effort")
        if effort is not None:
            effort = str(effort)

        escalated = False
        reason: str | None = None

        if escalate_reason is not None:
            try:
                config = load_effective_config(root)
            except ConfigValidationError as error:
                return {"status": "error", "message": f"invalid configuration: {error}"}, 2
            config_dict = config.to_dict() if hasattr(config, "to_dict") else dict(config)
            try:
                catalog = catalog_for(config_dict, provider)
            except KeyError:
                return {"status": "error", "message": f"unknown provider harness: {provider}"}, 2

            diagnostics = route_diagnostics(catalog, model, effort)
            if diagnostics:
                return {"status": "error", "message": f"track '{task_id}': " + "; ".join(diagnostics)}, 2
            next_route = escalate(catalog, model, effort)
            if next_route is None:
                return {
                    "status": "human_decision_required",
                    "task_id": task_id,
                    "provider": provider,
                    "model": model,
                    "effort": effort,
                }, 2

            new_model, new_effort = next_route
            old_model, old_effort = model, effort
            escalation_record = {
                "from": {"model": old_model, "effort": old_effort},
                "to": {"model": new_model, "effort": new_effort},
                "reason": escalate_reason,
            }

            if "tracks" in data and isinstance(data["tracks"], Mapping) and task_id in data["tracks"]:
                t_entry = dict(data["tracks"][task_id])
                t_res = dict(t_entry.get("resolved", {}))
                t_res["model"] = new_model
                t_res["effort"] = new_effort
                t_entry["resolved"] = t_res
                escs = list(t_entry.get("escalations", []))
                escs.append(escalation_record)
                t_entry["escalations"] = escs
                data["tracks"][task_id] = t_entry

            if "assignments" in data and isinstance(data["assignments"], Sequence):
                new_assignments = []
                for item in data["assignments"]:
                    if isinstance(item, Mapping) and item.get("task_id") == task_id:
                        item_dict = dict(item)
                        i_res = dict(item_dict.get("resolved", {}))
                        i_res["model"] = new_model
                        i_res["effort"] = new_effort
                        item_dict["resolved"] = i_res
                        escs = list(item_dict.get("escalations", []))
                        escs.append(escalation_record)
                        item_dict["escalations"] = escs
                        new_assignments.append(item_dict)
                    else:
                        new_assignments.append(item)
                data["assignments"] = new_assignments

            atomic_write_text(manifest_path, yaml.safe_dump(data, sort_keys=False, allow_unicode=True))
            model = new_model
            effort = new_effort
            escalated = True
            reason = escalate_reason

    events_path = main_checkout(Path(root).resolve()) / ".agent-workflow/runtime/events.jsonl"
    events_path.parent.mkdir(parents=True, exist_ok=True)
    store = WorkflowEventStore(events_path)
    event = WorkflowEvent.create(
        event_type="route.dispatched",
        workflow_id=workflow_id,
        task_id=task_id,
        payload={
            "task_id": task_id,
            "provider": provider,
            "model": model,
            "effort": effort,
            "reason": reason,
        },
    )
    store.append(event)

    return {
        "task_id": task_id,
        "provider": provider,
        "model": model,
        "effort": effort,
        "escalated": escalated,
    }, 0


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="gin-workflow routes")
    commands = parser.add_subparsers(dest="command", required=True)

    resolve_parser = commands.add_parser("resolve")
    resolve_parser.add_argument("--workflow-id", required=True)
    resolve_parser.add_argument("--tracks", type=Path, required=True)
    resolve_parser.add_argument("--repository", type=Path, default=Path.cwd())
    resolve_parser.add_argument("--json", action="store_true")

    dispatch_parser = commands.add_parser("dispatch")
    dispatch_parser.add_argument("--workflow-id", required=True)
    dispatch_parser.add_argument("--task-id", required=True)
    dispatch_parser.add_argument("--escalate")
    dispatch_parser.add_argument("--repository", type=Path, default=Path.cwd())
    dispatch_parser.add_argument("--json", action="store_true")

    args = parser.parse_args(list(argv))
    root = args.repository.resolve()

    if args.command == "resolve":
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

    if args.command == "dispatch":
        payload, code = dispatch(root, args.workflow_id, args.task_id, args.escalate)
        print(json.dumps(payload))
        return code

    return 2
