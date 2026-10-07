"""Lifecycle command-line interface for workflow state inspection, gate recording, and unblocking."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Mapping, Sequence

from .checkout import main_checkout
from .configuration import resolve_effective_config
from .events import WorkflowEvent, WorkflowEventStore
from .project import project_settings
from .team import load_team, summary as team_summary, team_for_repo
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
    runtime_dir = main_checkout(repo_path) / ".agent-workflow" / "runtime"
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


def _beads_json(repo_path: Path, argv: list[str]) -> Any:
    """Run one read-only Beads query; None when Beads is unavailable or fails."""
    executable = shutil.which("bd")
    if executable is None:
        return None
    try:
        completed = subprocess.run(
            [executable, *argv, "--json"], cwd=repo_path, text=True, capture_output=True, check=False, timeout=30
        )
        return json.loads(completed.stdout) if completed.returncode == 0 else None
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return None


def _recorded_epic(event_store: WorkflowEventStore, workflow_id: str) -> str:
    epic = ""
    for event in event_store.read_all():
        payload = event.payload if isinstance(event.payload, Mapping) else {}
        if event.workflow_id == workflow_id and event.event_type == "orchestration.ready" and payload.get("epic"):
            epic = str(payload["epic"])
    return epic


def _delivery_gate_state(
    repo_path: Path, event_store: WorkflowEventStore, workflow_id: str
) -> dict[str, bool]:
    """Derive delivery gates: implementation from closed epic children, verification from
    its recorded event, shipped from the closed epic (closed only after a confirmed merge).

    A standalone bead recorded as its own epic has no children: implementation is the bead
    itself closed, and shipped comes from an explicit `record shipped` after the merge."""
    gates = {
        "implementation_complete": False,
        "verification_passed": any(
            event.workflow_id == workflow_id and event.event_type == "verification.passed"
            for event in event_store.read_all()
        ),
        "shipped": False,
    }
    epic = _recorded_epic(event_store, workflow_id)
    if not epic:
        return gates
    children = _beads_json(repo_path, ["list", "--parent", epic, "--all", "--limit", "0"])
    if children == []:
        gates["implementation_complete"] = _bead_closed(repo_path, epic)
        gates["shipped"] = gates["implementation_complete"] and any(
            event.workflow_id == workflow_id and event.event_type == "delivery.shipped"
            for event in event_store.read_all()
        )
        return gates
    if isinstance(children, list) and children and all(
        isinstance(child, Mapping) and child.get("status") == "closed" for child in children
    ):
        gates["implementation_complete"] = True
        gates["shipped"] = _bead_closed(repo_path, epic)
    return gates


def _standalone_requirement(repo_path: Path, event_store: WorkflowEventStore, workflow_id: str) -> bool:
    """A standalone bead, recorded as its own epic with no children, carries its requirement and
    scope in its description, so it needs no separate discuss or plan gate."""
    epic = _recorded_epic(event_store, workflow_id)
    return bool(epic) and _beads_json(repo_path, ["list", "--parent", epic, "--all", "--limit", "0"]) == []


def _bead_closed(repo_path: Path, bead_id: str) -> bool:
    shown = _beads_json(repo_path, ["show", bead_id])
    record = shown[0] if isinstance(shown, list) and len(shown) == 1 else shown
    return isinstance(record, Mapping) and record.get("status") == "closed"


_RECORDABLE_GATES = {
    "requirement-confirmed": ("requirement.confirmed", {}),
    "plan-approved": ("approval.recorded", {"action": "plan_approved", "decision": {"status": "approved"}}),
    "orchestration-ready": ("orchestration.ready", {}),
    "verification-passed": ("verification.passed", {}),
    "quick-completed": ("quick.completed", {}),
    "shipped": ("delivery.shipped", {}),
}


def _record_command(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    event_type, base_payload = _RECORDABLE_GATES[args.gate]
    if args.epic and args.gate != "orchestration-ready":
        return {"status": "error", "message": "--epic applies only to orchestration-ready"}, 2
    store = _get_event_store(Path(args.repository).resolve())
    if args.gate == "shipped":
        epic = _recorded_epic(store, args.workflow_id)
        if not epic or _beads_json(Path(args.repository).resolve(), ["list", "--parent", epic, "--all", "--limit", "0"]) != []:
            return {"status": "error", "message": "shipped is recordable only for a standalone bead recorded as its own "
                    "epic (orchestration-ready --epic <bead>); an epic with children ships by closing it"}, 2
    actor, team_payload = args.actor, {}
    team = team_for_repo(Path(args.repository).resolve())
    if team is not None:
        from .team import TeamError, TeamRejected, authorize_record
        from .team_host import HostUnavailable

        try:
            actor, team_payload = authorize_record(Path(args.repository).resolve(), team, args.gate.replace("-", "_"),
                                                   args.evidence, actor=args.actor, plan=args.plan,
                                                   spec=args.spec)
        except (TeamError, HostUnavailable) as error:
            return {"status": "error", "message": str(error)}, 2
        except TeamRejected as rejected:
            return {"status": "rejected", "message": str(rejected), "reasons": rejected.reasons}, 1
    elif not actor:
        return {"status": "error", "message": "--actor is required"}, 2
    payload = {**base_payload, "evidence": args.evidence, **team_payload}
    if args.epic:
        payload["epic"] = args.epic
    event = WorkflowEvent.create(
        event_type=event_type,
        workflow_id=args.workflow_id,
        actor=actor,
        payload=payload,
        idempotency_key=f"{args.workflow_id}:{args.gate}:{args.evidence}",
    )
    appended = store.append(event)
    return {
        "status": "recorded" if appended else "already_recorded",
        "gate": args.gate,
        "event_type": event_type,
        "workflow_id": args.workflow_id,
        "message": f"{args.gate} recorded for {args.workflow_id}",
    }, 0


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
        **_delivery_gate_state(repo_path, event_store, workflow_id),
    }
    if _standalone_requirement(repo_path, event_store, workflow_id):
        state["requirement_confirmed"] = state["plan_approved"] = True

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
        "remedies": list(decision.remedies),        "project": {**project_settings(config.to_dict()).to_dict(),
                    "team": team_summary(repo_path, load_team(config.to_dict()))},
        "recent_quick": [
            {"timestamp": event.timestamp, "evidence": event.payload.get("evidence", "")}
            for event in event_store.read_all()
            if event.workflow_id == workflow_id and event.event_type == "quick.completed"
        ][-5:],
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

    team = team_for_repo(repo_path)
    if team is not None:
        from .team import TeamError, authorize_waiver

        try:
            actor = authorize_waiver(repo_path, team, None if args.clear_blocker else args.gate, actor=actor)
        except TeamError as error:
            return {"status": "error", "message": str(error)}, 2
    elif not actor:
        return {"status": "error", "message": "--actor is required"}, 2

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


_QUICK_COMMANDS = {"easy": ("lint", "typecheck", "test"), "standard": ("lint", "typecheck", "test", "build"),
                   "strict": ("lint", "typecheck", "test", "build", "e2e")}


def _quick_check_command(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    repo_path = Path(args.repository).resolve()
    config = resolve_effective_config(repo_path, write=False).config
    settings = project_settings(config.to_dict())
    commands = {k: v for k, v in settings.verify_commands.items() if k in _QUICK_COMMANDS[settings.rigor]}
    base = {"rigor": settings.rigor, "verify_commands": commands,
            "review": "self_check" if settings.rigor == "easy" else "independent"}
    if settings.rigor == "strict":
        store = _get_event_store(repo_path)
        waivers = collect_waivers(store, workflow_id=args.workflow_id,
                                  scope_hash=getattr(args, "scope_hash", None) or _resolve_scope_hash(repo_path))
        if "requirement_confirmed" not in waivers:
            return {**base, "decision": "refused",
                    "reason": "strict rigor requires /discuss; waive requirement_confirmed with gin-workflow unblock to use /quick"}, 4
    if args.changed_files > settings.quick_max_files or args.modules > 1:
        return {**base, "decision": "escalate",
                "reason": f"{args.changed_files} files / {args.modules} modules exceeds quick limits "
                          f"({settings.quick_max_files} files, 1 module); use the full lifecycle"}, 3
    return {**base, "decision": "allowed", "reason": "within quick limits"}, 0


def main(arguments: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if arguments is None else arguments)
    if not argv:
        print("usage: gin-workflow {state,unblock,record,quick-check} ...", file=sys.stderr)
        return 2

    command = argv[0]
    if command not in ("state", "unblock", "record", "quick-check"):
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

    if command == "quick-check":
        parser.add_argument("--changed-files", type=int, required=True)
        parser.add_argument("--modules", type=int, default=1)
        try:
            args = parser.parse_args(argv[1:])
        except SystemExit as e:
            return e.code if isinstance(e.code, int) else 2
        payload, exit_code = _quick_check_command(args)
        if args.format == "json":
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"{payload['decision']}: {payload['reason']}")
            print(f"Rigor: {payload['rigor']}; review: {payload['review']}")
            for name, command_line in payload["verify_commands"].items():
                print(f"  - {name}: {command_line}")
        return exit_code

    if command == "unblock":
        parser.add_argument("--gate")
        parser.add_argument("--reason", required=True)
        parser.add_argument("--actor", default="", help="required unless team mode derives it from git user.email")
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

    if command == "record":
        parser.add_argument("gate", choices=tuple(_RECORDABLE_GATES))
        parser.add_argument("--evidence", required=True)
        parser.add_argument("--actor", default="", help="required unless team mode derives it from git user.email")
        parser.add_argument("--plan", help="team mode: the plan file a plan-approved PR approves")
        parser.add_argument("--spec", help="team mode: the spec file a requirement-confirmed PR approves")
        parser.add_argument("--epic", default="", help="parent bead whose closed children prove implementation_complete")
        try:
            args = parser.parse_args(argv[1:])
        except SystemExit as e:
            return e.code if isinstance(e.code, int) else 2
        payload, exit_code = _record_command(args)
        if args.format == "json":
            print(json.dumps(payload, indent=2, sort_keys=True))
        elif exit_code:
            print(f"error: {payload['message']}", file=sys.stderr)
        else:
            print(payload["message"])
        return exit_code

    return 2
