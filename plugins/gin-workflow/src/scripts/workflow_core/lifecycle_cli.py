"""Lifecycle command-line interface for workflow state inspection and unblocking."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

from .configuration import resolve_effective_config
from .events import WorkflowEvent, WorkflowEventStore
from .router import _STAGE_GATES, route_next_stage, _gate_status
from .waivers import (
    NON_WAIVABLE_GATES,
    GateClass,
    GateWaiver,
    build_waiver_event,
    classify_gate,
    collect_waivers,
)


def _get_event_store(repo_path: Path) -> WorkflowEventStore:
    runtime_dir = repo_path / ".agent-workflow" / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    events_path = runtime_dir / "events.jsonl"
    return WorkflowEventStore(events_path)


def _resolve_scope_hash(repo_path: Path) -> str:
    # Check planning ledgers for scope_hash if available.
    # FIXME: This picks the first matching hash from any review.json in .planning/.
    # When multiple beads are active simultaneously, this may return a hash from
    # the wrong bead. The caller should pass an explicit --scope-hash when it matters.
    planning_dir = repo_path / ".planning"
    if planning_dir.is_dir():
        candidates = list(planning_dir.glob("reviews/*/review.json")) + list(planning_dir.glob("*/review.json"))
        for review_json in candidates:
            try:
                data = json.loads(review_json.read_text("utf-8"))
                for repo in data.get("repositories", []):
                    if repo.get("source_scope_hash"):
                        return str(repo["source_scope_hash"])
            except Exception:
                pass
    return "default-scope"


def _process_gate_state(
    event_store: WorkflowEventStore, workflow_id: str
) -> dict[str, bool]:
    """Reconstruct process gates from durable events for one workflow only."""
    gates = {
        "requirement_confirmed": False,
        "plan_approved": False,
        "orchestration_ready": False,
    }
    for event in event_store.read_all():
        if event.workflow_id != workflow_id:
            continue
        payload = event.payload if isinstance(event.payload, Mapping) else {}
        if event.event_type == "requirement.confirmed":
            gates["requirement_confirmed"] = True
        elif event.event_type == "approval.recorded":
            decision = payload.get("decision")
            approved = (
                isinstance(decision, Mapping)
                and decision.get("status") == "approved"
            )
            if payload.get("action") == "plan_approved" and approved:
                gates["plan_approved"] = True
        elif event.event_type == "orchestration.ready":
            gates["orchestration_ready"] = True
    return gates


def _state_command(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    repo_path = Path(args.repository).resolve()
    resolved_config = resolve_effective_config(repo_path, write=False)
    config = resolved_config.config

    event_store = _get_event_store(repo_path)
    workflow_id = getattr(args, "workflow_id", None) or "default-workflow"
    scope_hash = getattr(args, "scope_hash", None) or _resolve_scope_hash(repo_path)

    state: dict[str, Any] = {
        "workflow_id": workflow_id,
        "audit_event_store": event_store,
        "scope_hash": scope_hash,
        **_process_gate_state(event_store, workflow_id),
    }

    decision = route_next_stage(state, config)

    waivers = collect_waivers(event_store, workflow_id=workflow_id, scope_hash=scope_hash)

    gates_status: dict[str, str] = {}
    for stage, gate in _STAGE_GATES:
        status = _gate_status(state, gate, waivers)
        if status == "waived" and gate in waivers:
            waiver = waivers[gate]
            gates_status[gate] = f"waived({waiver.reason})"
        else:
            gates_status[gate] = status

    payload = {
        "stage": decision.stage,
        "decision": decision.decision,
        "harness": config.harness,
        "is_session_harness_override": config.is_session_harness_override,
        "original_harness": config.original_harness if config.is_session_harness_override else None,
        "gates": gates_status,
        "evidence": list(decision.evidence),
        "remedies": list(decision.remedies),
    }

    exit_code = 0 if decision.decision == "route" else 1
    return payload, exit_code



def _unblock_command(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    repo_path = Path(args.repository).resolve()
    event_store = _get_event_store(repo_path)
    workflow_id = getattr(args, "workflow_id", None) or "default-workflow"
    scope_hash = getattr(args, "scope_hash", None) or _resolve_scope_hash(repo_path)
    actor = args.actor
    reason = args.reason

    if not reason.strip():
        return {"status": "error", "message": "--reason is required"}, 1

    if getattr(args, "clear_blocker", False):
        event = WorkflowEvent.create(
            event_type="blocker.cleared",
            workflow_id=workflow_id,
            payload={"reason": reason, "cleared_by": actor},
            actor=actor,
        )
        event_store.append(event)
        return {
            "status": "success",
            "message": f"Blocker cleared. Recorded event {event.event_id}",
            "event_id": event.event_id,
        }, 0

    gate = getattr(args, "gate", None)
    if not gate:
        return {
            "status": "error",
            "message": "Either --gate or --clear-blocker must be specified",
        }, 1

    if gate in NON_WAIVABLE_GATES:
        return {"status": "error", "message": f"Gate '{gate}' is non-waivable."}, 1

    try:
        gate_class = classify_gate(gate)
    except ValueError as err:
        return {"status": "error", "message": str(err)}, 1

    follow_up = getattr(args, "follow_up", None)
    if gate_class == GateClass.SAFETY and not (follow_up and follow_up.strip()):
        return {
            "status": "error",
            "message": f"Safety gate '{gate}' requires --follow-up task ID.",
        }, 1

    try:
        waiver = GateWaiver(
            gate=gate,
            gate_class=gate_class,
            reason=reason,
            scope_hash=scope_hash,
            waived_by=actor,
            follow_up_task_id=follow_up if follow_up else None,
        )
        event = build_waiver_event(waiver, workflow_id=workflow_id)
        event_store.append(event)
    except (ValueError, TypeError) as err:
        return {"status": "error", "message": str(err)}, 1

    return {
        "status": "success",
        "message": f"Waived gate '{gate}'. Recorded event {event.event_id}",
        "event_id": event.event_id,
        "gate": gate,
    }, 0


def main(arguments: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if arguments is None else arguments)
    if not argv:
        print("usage: gin-workflow {state,unblock} ...", file=sys.stderr)
        return 2

    command = argv[0]
    if command not in ("state", "unblock"):
        print(f"unknown command: {command}", file=sys.stderr)
        return 2

    parser = argparse.ArgumentParser(prog=f"gin-workflow {command}")
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--workflow-id", default="default-workflow")
    parser.add_argument("--scope-hash")

    if command == "state":
        try:
            args = parser.parse_args(argv[1:])
        except SystemExit as e:
            return e.code if isinstance(e.code, int) else 2
        payload, exit_code = _state_command(args)
        if args.format == "json":
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"Lifecycle Stage: {payload.get('stage')}")
            print(f"Routing Decision: {payload.get('decision')}")
            if payload.get("is_session_harness_override"):
                print(f"Main Harness: {payload.get('harness')} (Session Override, Configured: {payload.get('original_harness')})")
            else:
                print(f"Main Harness: {payload.get('harness')}")
            print("\nGates:")

            for gate, status in payload.get("gates", {}).items():
                print(f"  - {gate}: {status}")
            print("\nEvidence:")
            for ev in payload.get("evidence", []):
                print(f"  - {ev}")
            print("\nRemedies:")
            for rem in payload.get("remedies", []):
                print(f"  - {rem}")
        return exit_code

    if command == "unblock":
        parser.add_argument("--gate")
        parser.add_argument("--reason", required=True)
        parser.add_argument("--actor", required=True)
        parser.add_argument("--follow-up", dest="follow_up")
        parser.add_argument("--clear-blocker", action="store_true")

        try:
            args = parser.parse_args(argv[1:])
        except SystemExit as e:
            return e.code if isinstance(e.code, int) else 2

        payload, exit_code = _unblock_command(args)
        if args.format == "json":
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            if exit_code == 0:
                print(payload.get("message", "Success"))
            else:
                print(f"error: {payload.get('message', 'Failed')}", file=sys.stderr)
        return exit_code

    return 2
