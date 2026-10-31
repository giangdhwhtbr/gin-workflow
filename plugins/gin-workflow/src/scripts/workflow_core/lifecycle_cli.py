"""Lifecycle command-line interface for workflow state inspection, gate recording, and unblocking."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping, Sequence

from .artifacts import ArtifactResolutionError, resolve_artifact
from .catalog import catalog_for
from .checkout import main_checkout
from .configuration import resolve_effective_config
from .events import EventPersistenceError, WorkflowEvent, WorkflowEventStore
from .project import project_settings
from . import orchestrator_client
from .team import load_team, summary as team_summary, team_for_repo
from .router import _STAGE_GATES, route_next_stage, _gate_status
from .waivers import (
    NON_WAIVABLE_GATES,
    GateClass,
    GateWaiver,
    build_waiver_event,
    classify_gate,
    collect_waivers,
    waivers_from_events,
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


def _read_events(store: WorkflowEventStore) -> tuple[list[WorkflowEvent] | None, str | None]:
    try:
        return store.read_all(), None
    except (EventPersistenceError, OSError, ValueError) as error:
        return None, f"event log unreadable: {error}; waivers not applied"


def _process_gate_state(events: Sequence[WorkflowEvent], workflow_id: str) -> dict[str, bool | None]:
    """Reconstruct process gates from durable events for one workflow only."""
    gates: dict[str, bool | None] = {
        "requirement_confirmed": False,
        "plan_approved": False,
        "orchestration_ready": False,
    }
    for event in events:
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


def _beads_json(repo_path: Path, argv: list[str]) -> tuple[Any, str | None]:
    """Run one read-only task query on the configured backend: (data, None), or (None, cause) when it fails."""
    from .tasks import query_result

    return query_result(repo_path, argv)


def _recorded_epic(events: Sequence[WorkflowEvent], workflow_id: str) -> str:
    epic = ""
    for event in events:
        payload = event.payload if isinstance(event.payload, Mapping) else {}
        if event.workflow_id == workflow_id and event.event_type == "orchestration.ready" and payload.get("epic"):
            epic = str(payload["epic"])
    return epic


def _bead_closed(repo_path: Path, bead_id: str) -> tuple[bool, str | None]:
    shown, cause = _beads_json(repo_path, ["show", bead_id])
    record = shown[0] if isinstance(shown, list) and len(shown) == 1 else shown
    return isinstance(record, Mapping) and record.get("status") == "closed", cause


def _delivery_state(
    repo_path: Path, events: Sequence[WorkflowEvent], workflow_id: str
) -> tuple[dict[str, bool | None], bool | None, str | None]:
    """Derive delivery gates: implementation from closed epic children, shipped from the closed epic
    (closed only after a confirmed merge). A standalone bead recorded as its own epic has no children:
    implementation is the bead itself closed, and shipped comes from an explicit `record shipped`.
    A standalone bead also carries its requirement and scope, so it needs no discuss or plan gate.

    Returns the gates, whether the epic is standalone, and the tracker failure; None marks a value
    that failure left unknown."""
    unknown: dict[str, bool | None] = {"implementation_complete": None, "shipped": None}
    epic = _recorded_epic(events, workflow_id)
    if not epic:
        return {"implementation_complete": False, "shipped": False}, False, None
    children, cause = _beads_json(repo_path, ["list", "--parent", epic, "--all", "--limit", "0"])
    if cause:
        return unknown, None, cause
    if children == []:
        closed, cause = _bead_closed(repo_path, epic)
        if cause:
            return unknown, True, cause
        shipped = closed and any(
            event.workflow_id == workflow_id and event.event_type == "delivery.shipped" for event in events
        )
        return {"implementation_complete": closed, "shipped": shipped}, True, None
    if isinstance(children, list) and all(
        isinstance(child, Mapping) and child.get("status") == "closed" for child in children
    ):
        closed, cause = _bead_closed(repo_path, epic)
        return {"implementation_complete": True, "shipped": None if cause else closed}, False, cause
    return {"implementation_complete": False, "shipped": False}, False, None


REMOVED_VERIFY_MESSAGE = ("the verify stage and verification_passed gate were removed; quality checks run in git hooks "
                          "(gin-workflow hooks install)")
_RECORDABLE_GATES = {
    "requirement-confirmed": ("requirement.confirmed", {}),
    "plan-approved": ("approval.recorded", {"action": "plan_approved", "decision": {"status": "approved"}}),
    "orchestration-ready": ("orchestration.ready", {}),
    "quick-completed": ("quick.completed", {}),
    "shipped": ("delivery.shipped", {}),
}
_PROCESS_GATES = ("requirement-confirmed", "plan-approved", "orchestration-ready")


def _record_refusal(
    repo_path: Path, events: Sequence[WorkflowEvent], args: argparse.Namespace
) -> tuple[dict[str, Any], int] | None:
    """The result for a record that the current events and tracker forbid or already hold, else None."""
    # simplified: a hung bd can hold the lock for two 30 s queries (~LOCK_TIMEOUT);
    # pass a shorter per-query timeout if waiters time out.
    if args.gate in _PROCESS_GATES and _delivery_state(repo_path, events, args.workflow_id)[0]["shipped"]:
        return {"status": "error", "message": f"workflow {args.workflow_id} is already shipped; "
                "pass --workflow-id <new-id> for new work"}, 2
    if args.gate != "shipped":
        return None
    if any(event.workflow_id == args.workflow_id and event.event_type == "delivery.shipped" for event in events):
        return {"status": "already_recorded", "gate": args.gate, "event_type": "delivery.shipped",
                "workflow_id": args.workflow_id, "message": f"{args.workflow_id} is already shipped"}, 0
    epic = _recorded_epic(events, args.workflow_id)
    children, cause = (None, None) if not epic else _beads_json(
        repo_path, ["list", "--parent", epic, "--all", "--limit", "0"])
    if cause:
        return {"status": "error", "message": f"shipped not recorded: tracker unavailable: {cause}"}, 2
    if children != []:
        return {"status": "error", "message": "shipped is recordable only for a standalone bead recorded as its own "
                "epic (orchestration-ready --epic <bead>); an epic with children ships by closing it"}, 2
    return None


def _spec_lint_errors(repo_path: Path, evidence: str) -> list[str]:
    """Legacy-layout spec lint for a Markdown evidence file; other evidence is not checked."""
    from .specs import lint_design_spec

    path = repo_path / evidence
    if not evidence.endswith(".md") or not path.is_file():
        return []
    config = resolve_effective_config(repo_path, write=False).config.to_dict()
    if project_settings(config).layout != "legacy":
        return []
    return lint_design_spec(path)


def _record_command(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    event_type, base_payload = _RECORDABLE_GATES[args.gate]
    if args.epic and args.gate != "orchestration-ready":
        return {"status": "error", "message": "--epic applies only to orchestration-ready"}, 2
    if args.gate == "requirement-confirmed":
        errors = _spec_lint_errors(Path(args.repository).resolve(), args.evidence)
        if errors:
            return {"status": "rejected", "message": "requirement-confirmed refused: spec lint failed\n"
                    + "\n".join(errors)}, 1
    store = _get_event_store(Path(args.repository).resolve())
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
    try:
        with store.transaction() as tx:
            refusal = _record_refusal(Path(args.repository).resolve(), tx.events, args)
            if refusal is not None:
                return refusal
            appended = tx.append(event)
    except (EventPersistenceError, RuntimeError, OSError) as error:
        return {"status": "error", "message": f"{args.gate} not recorded for {args.workflow_id}: {error}"}, 1
    return {
        "status": "recorded" if appended else "already_recorded",
        "gate": args.gate,
        "event_type": event_type,
        "workflow_id": args.workflow_id,
        "message": f"{args.gate} recorded for {args.workflow_id}",
    }, 0


def _knowledge_warning(repo_path: Path, config: Any, events: Sequence[WorkflowEvent] | None,
                       workflow_id: str, gates: Mapping[str, bool | None]) -> str | None:
    """Ship-time reminder: no commit touched the knowledge directory since orchestration-ready."""
    ready = [e for e in events or () if e.workflow_id == workflow_id and e.event_type == "orchestration.ready"]
    if not ready or not gates.get("implementation_complete"):
        return None
    try:
        knowledge = resolve_artifact(config, "knowledge")
    except ArtifactResolutionError:
        return None
    since = ready[-1].timestamp
    try:
        done = subprocess.run(["git", "log", f"--since={since}", "--format=%H", "--", str(knowledge)],
                              cwd=repo_path, capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    if done.returncode or done.stdout.strip():
        return None
    shown = knowledge.relative_to(repo_path) if knowledge.is_relative_to(repo_path) else knowledge
    return f"no commit changed {shown} since orchestration-ready ({since}); reconcile knowledge (gin-knowledge) before ship"


def _state_command(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    repo_path = Path(args.repository).resolve()
    resolved_config = resolve_effective_config(repo_path, write=False)
    config = resolved_config.config

    event_store = _get_event_store(repo_path)
    workflow_id = getattr(args, "workflow_id", None) or "default-workflow"
    scope_hash = getattr(args, "scope_hash", None) or _resolve_scope_hash(repo_path)

    events, log_error = _read_events(event_store)
    if events is None:
        gates_state: dict[str, bool | None] = {gate: None for _, gate in _STAGE_GATES}
        causes, waivers = [log_error], {}
    else:
        gates_state = _process_gate_state(events, workflow_id)
        delivery, standalone, tracker_error = _delivery_state(repo_path, events, workflow_id)
        gates_state.update(delivery)
        for gate in ("requirement_confirmed", "plan_approved"):
            if standalone:
                gates_state[gate] = True
            elif standalone is None and not gates_state[gate]:
                gates_state[gate] = None
        causes = [f"tracker unavailable: {tracker_error}"] if tracker_error else []
        waivers = waivers_from_events(events, workflow_id=workflow_id, scope_hash=scope_hash)

    state: dict[str, Any] = {
        "workflow_id": workflow_id,
        "audit_event_store": event_store,
        "scope_hash": scope_hash,
        "waivers": waivers,
        "unknown_causes": causes,
        **gates_state,
    }
    decision = route_next_stage(state, config)

    gates_status: dict[str, str] = {}
    for stage, gate in _STAGE_GATES:
        status = _gate_status(state, gate, waivers)
        gates_status[gate] = f"waived({waivers[gate].reason})" if status == "waived" else status

    catalog_payload = None
    if config.harness:
        catalog = catalog_for(config.to_dict(), config.harness)
        catalog_payload = {"harness": config.harness, "models": list(catalog.models), "efforts": list(catalog.efforts)}

    payload = {
        "stage": decision.stage,
        "decision": decision.decision,
        "harness": config.harness,
        "is_session_harness_override": config.is_session_harness_override,
        "original_harness": config.original_harness if config.is_session_harness_override else None,
        "catalog": catalog_payload,
        "gates": gates_status,
        "evidence": list(decision.evidence),
        "remedies": list(decision.remedies),
        "project": {**project_settings(config.to_dict()).to_dict(),
                    "team": team_summary(repo_path, load_team(config.to_dict()))},
        "extensions": {"orchestrator": orchestrator_client.status()},
        "warnings": [w for w in (orchestrator_client.warning(config.to_dict()), *causes,
                                 _knowledge_warning(repo_path, config, events, workflow_id, gates_state)) if w],
        "recent_quick": [
            {"timestamp": event.timestamp, "evidence": event.payload.get("evidence", "")}
            for event in events or ()
            if event.workflow_id == workflow_id and event.event_type == "quick.completed"
        ][-5:],
        "review_waivers": [
            {"task_id": event.task_id, "reason": event.payload.get("reason", ""), "actor": event.actor}
            for event in events or ()
            if event.workflow_id == workflow_id and event.event_type == "review.waived"
        ],
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

    if gate == "verification_passed":
        return {"status": "error", "message": REMOVED_VERIFY_MESSAGE}, 2

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
            for warn in payload.get("warnings", []):
                print(f"Warning: {warn}")
        return exit_code

    if command == "quick-check":
        parser.add_argument("--changed-files", type=int, required=True)
        parser.add_argument("--modules", type=int, default=1,
                            help="source modules the change touches; a module's tests and docs count as that module")
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
        if argv[1:2] == ["verification-passed"]:
            print(f"error: {REMOVED_VERIFY_MESSAGE}", file=sys.stderr)
            return 2
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
