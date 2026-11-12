"""`gin-qa cases bug`: file a bug bead for a failed case, linked to the epic the case was written for."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any

from . import cases as tc
from .reqs import Effective, QaError

_EPIC = re.compile(r"^Epic: (\S+)$", re.MULTILINE)
_WORKFLOW = re.compile(r"^Workflow: (\S+)$", re.MULTILINE)
PRIORITY = {"high": "1", "medium": "2", "low": "3"}


def _gin_workflow(root: Path, *args: str, stdin: str = "") -> subprocess.CompletedProcess[str]:
    """`gin ...` in the repository: `task` runs bd against the current directory's database."""
    executable = shutil.which("gin")
    if executable is None:
        raise QaError("gin is not on PATH; install gin-workflow first")
    return subprocess.run([executable, *args], cwd=root, input=stdin, capture_output=True, text=True)


def _record(stdout: str) -> dict[str, Any] | None:
    """The first object of a `--json` answer: bd prints a list for show and one object for create."""
    try:
        data = json.loads(stdout)
    except ValueError:
        return None
    row = data[0] if isinstance(data, list) and data else data
    return row if isinstance(row, dict) else None


def _show(root: Path, bead: str) -> tuple[dict[str, Any] | None, str]:
    """(the bead, "") when found; (None, "") when the tracker has no such bead; (None, <stderr>) on any other failure."""
    shown = _gin_workflow(root, "task", "show", bead, "--json")
    if shown.returncode == 0:
        return _record(shown.stdout), ""
    if "no issue" in shown.stderr + shown.stdout:
        return None, ""
    return None, shown.stderr.strip() or f"gin task show exited {shown.returncode}"


def _workflow_epic(root: Path, topic: str) -> str | None:
    """The epic recorded at orchestration-ready for a `Workflow: <topic>` spec (`gin state`)."""
    state = _gin_workflow(root, "state", "--workflow-id", topic, "--repository", str(root), "--format", "json")
    try:
        epic = json.loads(state.stdout).get("epic")
    except (ValueError, AttributeError):
        return None
    return epic if isinstance(epic, str) and epic else None


def epic_of(root: Path, eff: Effective, case: tc.Case) -> list[str]:
    """Legacy: the spec named in `Source:` (its `Epic:` line, else the epic of its `Workflow:`), read from the project
    root, which holds the specs and the tracker (`root` is the QA home's repository), as a list of one or none. SDD:
    every epic of the case's REQs, in REQ order."""
    project = eff.project_root
    source = case.fields.get("Source")
    if source:
        relative = source.split("#", 1)[0].strip()
        path = (project / relative).resolve()
        if project.resolve() not in path.parents:
            raise QaError(f"{case.id}: {relative} is outside the repository")
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            raise QaError(f"{case.id}: cannot read {relative}: {getattr(error, 'strerror', None) or error}") from error
        if found := _EPIC.search(text):
            return [found.group(1)]
        topic = _WORKFLOW.search(text)
        epic = _workflow_epic(project, topic.group(1)) if topic else None
        return [epic] if epic else []
    return list(dict.fromkeys(eff.reqs[req]["epic"] for req, _ in case.reqs if eff.reqs.get(req, {}).get("epic")))


def description(case: tc.Case, run: str | None, previous: str | None, actual: str, evidence: list[str]) -> str:
    head = [f"- Case: {case.path}:{case.line}", *([f"- Run: {run}"] if run else []),
            *([f"- Previous bug: {previous}"] if previous else [])]
    sections = [("Preconditions", [f"- {item}" for item in case.preconditions]),
                ("Test data", [f"- {item}" for item in case.test_data]),
                ("Steps", [f"{number}. {step}" for number, step in enumerate(case.steps, 1)]),
                ("Expected", [f"- {item}" for item in case.expected]),
                ("Actual", [actual]),
                ("Evidence", [f"- {item}" for item in evidence])]
    return "\n\n".join(["\n".join(head), *(f"## {name}\n\n" + "\n".join(lines) for name, lines in sections if lines)])


def rerun_note(run: str | None, actual: str, evidence: list[str]) -> str:
    """One line with no double quote: a Windows .cmd shim cuts an argument at its first newline and re-parses quotes."""
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    parts = [f"Re-run {day}", *([f"Run: {run}"] if run else []), f"Actual: {actual}",
             *([f"Evidence: {', '.join(evidence)}"] if evidence else [])]
    return "; ".join(parts).replace('"', "'")


def file_bug(root: Path, eff: Effective, case_id: str, actual: str, evidence: list[str], *,
             external_ref: str | None = None, discovered_from: str | None = None,
             run: str | None = None) -> dict[str, Any]:
    """Record `failed` on a case with its open bug, or with a new bug bead filed against the case's epic."""
    for value in (actual, *evidence, *(item for item in (external_ref, discovered_from, run) if item is not None)):
        tc.one_line(value)
    case = tc.find(root, eff.cases_dir, case_id)
    project = eff.project_root  # Beads runs against the project root; the case files live under `root`
    run = run if run is not None else case.fields.get("Run")
    previous = case.fields.get("Bug")
    if previous:
        old, _ = _show(project, previous)  # a value that is not a readable bead counts as no open bug
        if old is not None and old.get("status") not in (None, "closed"):
            added = _gin_workflow(project, "task", "update", previous, "--append-notes", rerun_note(run, actual, evidence))
            if added.returncode != 0:  # before the case changes, so the tester can run this again
                raise QaError(added.stderr.strip() or f"gin task update exited {added.returncode}")
            row = tc.record_result(root, eff.cases_dir, case_id, "failed", run, previous)
            return {"tc": case_id, "bug": previous, "epic": None, "created": False, "appended": True,
                    "file": row["file"]}
    if discovered_from:
        epic = discovered_from
    else:
        epics = epic_of(root, eff, case)
        if not epics:
            raise QaError(f"no epic for {case_id}; pass --discovered-from <bead>")
        if len(epics) > 1:
            raise QaError(f"several epics for {case_id}: {', '.join(epics)}; pass --discovered-from <bead>")
        epic = epics[0]
    found, failure = _show(project, epic)
    if failure:
        raise QaError(failure)
    if found is None:
        raise QaError(f"{epic}: no such bead; pass --discovered-from <bead>")
    priority = PRIORITY.get(case.fields.get("Priority", "").strip().lower(), "2")
    # the description goes on stdin: a Windows .cmd shim cuts an argument at its first newline
    argv = ["task", "create", "-t", "bug", "--title", f"{case_id}: {case.title}".replace('"', "'"),
            "--body-file", "-", "--deps", f"discovered-from:{epic}", "-p", priority,
            *(["--external-ref", external_ref] if external_ref else []), "--json"]
    created = _gin_workflow(project, *argv, stdin=description(case, run, previous, actual, evidence))
    if created.returncode != 0:
        raise QaError(created.stderr.strip() or f"gin task create exited {created.returncode}")
    bug = (_record(created.stdout) or {}).get("id")
    if not isinstance(bug, str) or not bug:
        raise QaError(f"gin task create printed no bead id: {created.stdout.strip()[:200]!r}")
    try:
        row = tc.record_result(root, eff.cases_dir, case_id, "failed", run, bug)
    except (ValueError, OSError) as error:
        raise QaError(f"filed {bug} but could not record it: {error}; "
                      f"run gin-qa cases result {case_id} failed --bug {bug}") from error
    return {"tc": case_id, "bug": bug, "epic": epic, "created": True, "appended": False,
            "file": row["file"]}
